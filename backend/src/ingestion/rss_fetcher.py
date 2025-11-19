"""
RSS feed fetcher with pagination support for different CMS types.
"""

import asyncio
from typing import List, Dict, Set, Optional
from datetime import datetime
import logging

import feedparser
import aiohttp

logger = logging.getLogger(__name__)


class RSSFetcher:
    """Fetches RSS feed entries with pagination support for different CMS types."""

    def __init__(self, feed_configs: Dict[str, Dict]):
        """
        Initialize RSS fetcher.

        Args:
            feed_configs: Dictionary mapping feed URLs to their configuration
        """
        self.feed_configs = feed_configs
        self.user_agent = 'Mozilla/5.0 (compatible; MarxistSearchBot/1.0)'

    async def fetch_all_feeds(self, feed_urls: List[str]) -> Dict[str, List[Dict]]:
        """
        Fetch all RSS feeds concurrently.

        Args:
            feed_urls: List of feed URLs to fetch

        Returns:
            Dictionary mapping feed URLs to their entries
        """
        tasks = [self.fetch_rss_entries(url) for url in feed_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        feed_results = {}
        for url, result in zip(feed_urls, results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching {url}: {result}")
                feed_results[url] = []
            else:
                feed_results[url] = result

        return feed_results

    async def fetch_new_feeds(
        self,
        feed_urls: List[str],
        existing_urls: Set[str],
        max_consecutive_duplicates: int = 5
    ) -> Dict[str, List[Dict]]:
        """
        Fetch only new entries from RSS feeds (incremental update).

        Stops pagination after encountering N consecutive duplicate URLs.
        This is efficient because RSS feeds are sorted newest-first.

        Args:
            feed_urls: List of feed URLs to fetch
            existing_urls: Set of URLs already in database
            max_consecutive_duplicates: Stop after this many consecutive duplicates

        Returns:
            Dictionary mapping feed URLs to their new entries
        """
        tasks = [
            self.fetch_new_entries(url, existing_urls, max_consecutive_duplicates)
            for url in feed_urls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        feed_results = {}
        for url, result in zip(feed_urls, results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching {url}: {result}")
                feed_results[url] = []
            else:
                feed_results[url] = result

        return feed_results

    async def fetch_new_entries(
        self,
        feed_url: str,
        existing_urls: Set[str],
        max_consecutive_duplicates: int = 5
    ) -> List[Dict]:
        """
        Fetch only new entries from a single RSS feed (incremental update).

        Stops pagination after encountering N consecutive duplicate URLs.

        Args:
            feed_url: URL of the RSS feed to fetch
            existing_urls: Set of URLs already in database
            max_consecutive_duplicates: Stop after this many consecutive duplicates

        Returns:
            List of new feed entries
        """
        entries = []
        seen_urls: Set[str] = set()
        consecutive_duplicates = 0

        logger.info(f"Fetching new articles from {feed_url}")

        # Get feed configuration
        feed_config = self.feed_configs.get(feed_url, {"pagination_type": "standard"})
        pagination_type = feed_config.get("pagination_type", "standard")

        # Initialize pagination variables
        page = 1
        limitstart = 0
        limit_increment = feed_config.get("limit_increment", 5)
        has_more = True
        consecutive_failures = 0
        max_consecutive_failures = 3

        while has_more:
            # Build URL based on pagination type
            current_url = self._build_paginated_url(
                feed_url, pagination_type, page, limitstart
            )

            pagination_desc = self._get_pagination_description(
                pagination_type, page, limitstart
            )

            logger.info(f"Fetching from URL: {current_url}")

            # Fetch and parse feed with retry logic
            feed = await self._fetch_feed_with_retry(current_url, max_retries=2)

            # Handle failed fetch
            if not feed:
                consecutive_failures += 1
                logger.warning(
                    f"Failed to fetch {pagination_desc} "
                    f"(consecutive failures: {consecutive_failures}/{max_consecutive_failures})"
                )

                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"Stopping pagination after {max_consecutive_failures} consecutive failures"
                    )
                    break

                # Skip this page and try next one
                if pagination_type == "joomla":
                    limitstart += limit_increment
                elif pagination_type == "wordpress":
                    page += 1
                else:
                    has_more = False

                await asyncio.sleep(1.0)
                continue

            # Handle empty feed
            if not feed.entries:
                logger.info(f"No entries found on {pagination_desc}.")
                consecutive_failures += 1

                if consecutive_failures >= max_consecutive_failures:
                    logger.info(
                        f"Stopping pagination after {max_consecutive_failures} "
                        f"consecutive pages with no entries"
                    )
                    break

                # Try next page
                if pagination_type == "joomla":
                    limitstart += limit_increment
                elif pagination_type == "wordpress":
                    page += 1
                else:
                    has_more = False

                await asyncio.sleep(0.5)
                continue

            # Reset failure counter on successful fetch
            consecutive_failures = 0

            logger.info(f"Processing {pagination_desc}... Found {len(feed.entries)} entries.")

            # Process entries and check for duplicates
            new_entries_on_page = 0

            for entry in feed.entries:
                entry_url = entry.get('link', '')

                # Skip empty URLs
                if not entry_url:
                    continue

                # Skip if already processed in this session
                if entry_url in seen_urls:
                    continue

                # Check if URL already exists in database
                if entry_url in existing_urls:
                    consecutive_duplicates += 1
                    logger.debug(
                        f"Duplicate found: {entry_url[:50]}... "
                        f"({consecutive_duplicates}/{max_consecutive_duplicates})"
                    )

                    # Stop if we've hit too many consecutive duplicates
                    if consecutive_duplicates >= max_consecutive_duplicates:
                        logger.info(
                            f"Stopping: found {max_consecutive_duplicates} consecutive duplicates. "
                            f"Reached articles already in database."
                        )
                        has_more = False
                        break

                    continue

                # This is a new entry!
                consecutive_duplicates = 0  # Reset counter
                seen_urls.add(entry_url)
                entries.append(entry)
                new_entries_on_page += 1

            logger.info(
                f"Added {new_entries_on_page} new entries "
                f"(total new so far: {len(entries)}, "
                f"consecutive dupes: {consecutive_duplicates})"
            )

            # Stop if we hit the duplicate threshold
            if consecutive_duplicates >= max_consecutive_duplicates:
                break

            # Update pagination parameters
            if pagination_type == "joomla":
                limitstart += limit_increment
                logger.info(f"Moving to limitstart={limitstart}...")
            elif pagination_type == "wordpress":
                page += 1
                logger.info(f"Moving to page {page}...")
            else:
                # Standard pagination - only process first page
                has_more = False

            # Check for standard RSS pagination links
            next_page = self._find_next_page_link(feed)
            if next_page and next_page != current_url:
                logger.info(f"Found 'next' link: {next_page}")
                feed_url = next_page
                # Reset pagination counters if switching to different URL
                if pagination_type == "joomla":
                    limitstart = 0
                elif pagination_type == "wordpress":
                    page = 1

            # Respect server resources
            await asyncio.sleep(0.2)

        logger.info(f"Finished fetching new entries. Total new entries: {len(entries)}")
        return entries

    async def fetch_rss_entries(self, feed_url: str) -> List[Dict]:
        """
        Fetch all entries from RSS feed with pagination support for different CMS types.

        Args:
            feed_url: URL of the RSS feed to fetch

        Returns:
            List of feed entries (dictionaries)
        """
        entries = []
        seen_urls: Set[str] = set()

        logger.info(f"Fetching articles from {feed_url}")

        # Get feed configuration
        feed_config = self.feed_configs.get(feed_url, {"pagination_type": "standard"})
        pagination_type = feed_config.get("pagination_type", "standard")

        # Initialize pagination variables
        page = 1  # For WordPress
        limitstart = 0  # For Joomla
        limit_increment = feed_config.get("limit_increment", 5)
        has_more = True
        consecutive_failures = 0  # Track consecutive failed fetches
        max_consecutive_failures = 3  # Stop after 3 consecutive failures

        while has_more:
            # Build URL based on pagination type
            current_url = self._build_paginated_url(
                feed_url, pagination_type, page, limitstart
            )

            pagination_desc = self._get_pagination_description(
                pagination_type, page, limitstart
            )

            logger.info(f"Fetching from URL: {current_url}")

            # Fetch and parse feed with retry logic
            feed = await self._fetch_feed_with_retry(current_url, max_retries=2)

            # Handle failed fetch
            if not feed:
                consecutive_failures += 1
                logger.warning(
                    f"Failed to fetch {pagination_desc} "
                    f"(consecutive failures: {consecutive_failures}/{max_consecutive_failures})"
                )

                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"Stopping pagination after {max_consecutive_failures} consecutive failures"
                    )
                    has_more = False
                    break

                # Skip this page and try next one
                if pagination_type == "joomla":
                    limitstart += limit_increment
                elif pagination_type == "wordpress":
                    page += 1
                else:
                    has_more = False

                await asyncio.sleep(1.0)  # Wait longer before retry
                continue

            # Handle empty feed
            if not feed.entries:
                logger.info(f"No entries found on {pagination_desc}.")
                consecutive_failures += 1

                if consecutive_failures >= max_consecutive_failures:
                    logger.info(
                        f"Stopping pagination after {max_consecutive_failures} "
                        f"consecutive pages with no entries"
                    )
                    has_more = False
                    break

                # Try next page
                if pagination_type == "joomla":
                    limitstart += limit_increment
                elif pagination_type == "wordpress":
                    page += 1
                else:
                    has_more = False

                await asyncio.sleep(0.5)
                continue

            # Reset failure counter on successful fetch
            consecutive_failures = 0

            logger.info(f"Processing {pagination_desc}... Found {len(feed.entries)} entries.")

            # Process entries
            new_entries = self._process_entries(feed.entries, seen_urls)
            entries.extend(new_entries)

            logger.info(f"Added {len(new_entries)} new entries (total so far: {len(entries)}).")

            # Check if we should continue pagination
            if len(new_entries) == 0:
                logger.info("No new entries found on this page (all duplicates).")
                # Don't stop immediately - might be a page of all duplicates
                # Continue to next page

            # Update pagination parameters
            if pagination_type == "joomla":
                limitstart += limit_increment
                logger.info(f"Moving to limitstart={limitstart}...")
            elif pagination_type == "wordpress":
                page += 1
                logger.info(f"Moving to page {page}...")
            else:
                # Standard pagination - only process first page
                has_more = False

            # Check for standard RSS pagination links
            next_page = self._find_next_page_link(feed)
            if next_page and next_page != current_url:
                logger.info(f"Found 'next' link: {next_page}")
                feed_url = next_page
                # Reset pagination counters if switching to different URL
                if pagination_type == "joomla":
                    limitstart = 0
                elif pagination_type == "wordpress":
                    page = 1

            # Respect server resources
            await asyncio.sleep(0.2)

        logger.info(f"Finished fetching all pages. Total entries: {len(entries)}")
        return entries

    def _build_paginated_url(
        self, feed_url: str, pagination_type: str, page: int, limitstart: int
    ) -> str:
        """
        Build paginated URL based on CMS type.

        Args:
            feed_url: Base feed URL
            pagination_type: Type of pagination (wordpress, joomla, standard)
            page: Current page number (for WordPress)
            limitstart: Current offset (for Joomla)

        Returns:
            Paginated URL
        """
        if pagination_type == "joomla":
            # Joomla pagination with limitstart
            if "format=feed" in feed_url:
                base_url = feed_url.split("?")[0]
                return f"{base_url}?format=feed&limitstart={limitstart}"
            else:
                separator = "&" if "?" in feed_url else "?"
                return f"{feed_url}{separator}format=feed&limitstart={limitstart}"

        elif pagination_type == "wordpress":
            # WordPress pagination
            if page > 1:
                return f"{feed_url.rstrip('/')}/?paged={page}"
            return feed_url

        else:
            # Standard/unknown pagination
            return feed_url

    def _get_pagination_description(
        self, pagination_type: str, page: int, limitstart: int
    ) -> str:
        """
        Get human-readable pagination description.

        Args:
            pagination_type: Type of pagination
            page: Current page number
            limitstart: Current offset

        Returns:
            Description string
        """
        if pagination_type == "joomla":
            return f"limitstart={limitstart}"
        elif pagination_type == "wordpress":
            return f"page {page}"
        else:
            return "first page"

    async def _fetch_feed_with_retry(
        self, url: str, max_retries: int = 2
    ) -> Optional[feedparser.FeedParserDict]:
        """
        Fetch and parse RSS feed with retry logic.

        Args:
            url: Feed URL to fetch
            max_retries: Maximum number of retry attempts

        Returns:
            Parsed feed or None on error
        """
        for attempt in range(max_retries + 1):
            if attempt > 0:
                wait_time = min(2 ** attempt, 5)  # Exponential backoff: 2s, 4s, max 5s
                logger.info(f"Retry attempt {attempt}/{max_retries} after {wait_time}s...")
                await asyncio.sleep(wait_time)

            feed = await self._fetch_feed(url)

            if feed:
                return feed

            logger.warning(f"Fetch attempt {attempt + 1}/{max_retries + 1} failed for {url}")

        return None

    async def _fetch_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """
        Fetch and parse RSS feed using async aiohttp.

        Uses aiohttp for fast async HTTP, then feedparser for parsing.

        Args:
            url: Feed URL to fetch

        Returns:
            Parsed feed or None on error
        """
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {'User-Agent': self.user_agent}

                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"HTTP {response.status} for {url}")
                        return None

                    content = await response.read()

                    # Parse with feedparser (fast, no I/O)
                    feed = feedparser.parse(content)

                    # Check if feedparser encountered an error
                    if hasattr(feed, 'bozo') and feed.bozo and feed.bozo_exception:
                        logger.warning(f"Feed parse warning for {url}: {feed.bozo_exception}")
                        # Still return feed if there are entries
                        if feed.entries:
                            return feed
                        return None

                    return feed

        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching {url}")
            return None
        except aiohttp.ClientError as e:
            logger.warning(f"HTTP error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

    def _process_entries(
        self, entries: List, seen_urls: Set[str]
    ) -> List[Dict]:
        """
        Process feed entries and filter duplicates.

        Args:
            entries: List of feed entries
            seen_urls: Set of already seen URLs

        Returns:
            List of new entries
        """
        new_entries = []

        for entry in entries:
            entry_url = entry.get('link', '')

            # Skip duplicates and empty URLs
            if not entry_url or entry_url in seen_urls:
                continue

            # Mark as seen and add to results
            seen_urls.add(entry_url)
            new_entries.append(entry)

        return new_entries

    def _find_next_page_link(self, feed: feedparser.FeedParserDict) -> Optional[str]:
        """
        Find 'next' page link in feed metadata.

        Args:
            feed: Parsed feed

        Returns:
            Next page URL or None
        """
        for link in feed.feed.get("links", []):
            if link.get("rel") == "next":
                return link.get("href")
        return None


def load_feed_configs(config_path: str) -> Dict[str, Dict]:
    """
    Load feed configurations from JSON file.

    Args:
        config_path: Path to rss_feeds.json

    Returns:
        Dictionary mapping feed URLs to their configurations
    """
    import json
    from pathlib import Path

    config_file = Path(config_path)
    if not config_file.exists():
        logger.warning(f"Config file not found: {config_path}")
        return {}

    with open(config_file, 'r') as f:
        config = json.load(f)

    # Create mapping of URL to config
    feed_configs = {}
    for feed in config.get("feeds", []):
        if feed.get("enabled", True):
            url = feed["url"]
            feed_configs[url] = feed

    return feed_configs
