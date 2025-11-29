"""
Content extraction from RSS entries and web pages.
"""

import asyncio
from typing import Dict, Optional, Tuple
from datetime import datetime, UTC
import logging
import re

import aiohttp
from trafilatura import extract
from trafilatura.settings import use_config

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extracts full article content from RSS entries and web pages."""

    def __init__(self, min_content_length: int = 200):
        """
        Initialize content extractor.

        Args:
            min_content_length: Minimum length to consider content as "full text"
        """
        self.min_content_length = min_content_length
        self.user_agent = 'Mozilla/5.0 (compatible; MarxistSearchBot/1.0)'

        # Configure trafilatura for better extraction
        self.trafilatura_config = use_config()
        self.trafilatura_config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")

    async def extract_from_entries(self, entries: list) -> list:
        """
        Extract full content from list of RSS entries.

        Args:
            entries: List of feedparser entries

        Returns:
            List of extracted articles with full content
        """
        tasks = [self.extract_from_entry(entry) for entry in entries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        articles = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error extracting content: {result}")
                continue
            if result:
                articles.append(result)

        return articles

    async def extract_from_entry(self, entry: Dict) -> Optional[Dict]:
        """
        Extract full content from a single RSS entry.

        Args:
            entry: Feedparser entry dictionary

        Returns:
            Dictionary with article data or None if extraction failed
        """
        try:
            # Extract basic metadata from RSS entry
            url = entry.get('link', '')
            guid = entry.get('id', entry.get('guid', ''))
            title = entry.get('title', '')
            summary = entry.get('summary', entry.get('description', ''))
            author = entry.get('author', entry.get('dc:creator', ''))
            published_date = self._parse_date(entry)

            if not url or not title:
                logger.warning(f"Missing required fields (url or title) in entry")
                return None

            # Check if full content is available in RSS feed
            content = entry.get('content', [{}])[0].get('value', '')
            if not content:
                content = entry.get('description', '')

            # Determine if we need to fetch full text
            needs_fetch = self._needs_full_text_fetch(content, summary)

            if needs_fetch:
                logger.info(f"Fetching full text for: {title[:50]}...")
                full_text = await self._fetch_full_text(url)
                if full_text:
                    content = full_text
                else:
                    logger.warning(f"Could not fetch full text for {url}, using summary")
                    content = summary or content
            else:
                logger.info(f"Full content available in RSS for: {title[:50]}...")

            # Extract tags/categories
            tags = self._extract_tags(entry)

            # Calculate word count
            word_count = len(content.split())

            article = {
                'url': url,
                'guid': guid,
                'title': title,
                'content': content,
                'summary': summary,
                'author': author,
                'published_date': published_date,
                'fetched_date': datetime.now(UTC),
                'word_count': word_count,
                'tags_json': tags,
            }

            return article

        except Exception as e:
            logger.error(f"Error extracting entry: {e}")
            return None

    def _needs_full_text_fetch(self, content: str, summary: str) -> bool:
        """
        Determine if we need to fetch full text from the web page.

        Args:
            content: Content from RSS feed
            summary: Summary from RSS feed

        Returns:
            True if full text fetch is needed
        """
        # If content is empty, definitely need to fetch
        if not content:
            return True

        # If content is very short, it's likely just a summary
        if len(content) < self.min_content_length:
            return True

        # If content and summary are identical and short, need to fetch
        if content == summary and len(content) < 500:
            return True

        # If content is much longer than minimum, assume it's full text
        return False

    async def _fetch_full_text(self, url: str) -> Optional[str]:
        """
        Fetch full article text using trafilatura.

        Args:
            url: URL of the article

        Returns:
            Extracted text or None if extraction failed
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': self.user_agent}
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        logger.warning(f"HTTP {response.status} for {url}")
                        return None

                    html = await response.text()

                    # Extract text using trafilatura
                    text = extract(
                        html,
                        config=self.trafilatura_config,
                        include_comments=False,
                        include_tables=True,
                        no_fallback=False,
                    )

                    if text and len(text) > self.min_content_length:
                        return text
                    else:
                        logger.warning(f"Extracted text too short for {url}")
                        return None

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching full text from {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching full text from {url}: {e}")
            return None

    def _parse_date(self, entry: Dict) -> datetime:
        """
        Parse publication date from RSS entry.

        Args:
            entry: Feedparser entry

        Returns:
            Parsed datetime or current time if parsing failed
        """
        # Try different date fields
        date_fields = [
            'published_parsed',
            'updated_parsed',
            'created_parsed',
        ]

        for field in date_fields:
            if field in entry and entry[field]:
                try:
                    import time
                    return datetime.fromtimestamp(time.mktime(entry[field]))
                except Exception as e:
                    logger.warning(f"Error parsing {field}: {e}")
                    continue

        # Fallback to string parsing
        date_str_fields = ['published', 'updated', 'created']
        for field in date_str_fields:
            if field in entry and entry[field]:
                try:
                    from dateutil import parser
                    return parser.parse(entry[field])
                except Exception as e:
                    logger.warning(f"Error parsing date string {field}: {e}")
                    continue

        # Last resort - use current time
        logger.warning(f"Could not parse date for entry, using current time")
        return datetime.now(UTC)

    def _extract_tags(self, entry: Dict) -> list:
        """
        Extract tags/categories from RSS entry.

        Args:
            entry: Feedparser entry

        Returns:
            List of tag strings
        """
        tags = []

        # Extract from tags field
        if 'tags' in entry:
            for tag in entry['tags']:
                term = tag.get('term', '')
                if term:
                    tags.append(term)

        # Extract from categories
        if 'categories' in entry:
            for category in entry['categories']:
                if isinstance(category, tuple) and len(category) > 0:
                    tags.append(category[0])
                elif isinstance(category, str):
                    tags.append(category)

        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)

        return unique_tags


async def extract_content_batch(
    entries: list, min_content_length: int = 200
) -> list:
    """
    Extract content from a batch of RSS entries.

    Args:
        entries: List of feedparser entries
        min_content_length: Minimum content length threshold

    Returns:
        List of extracted articles
    """
    extractor = ContentExtractor(min_content_length=min_content_length)
    return await extractor.extract_from_entries(entries)
