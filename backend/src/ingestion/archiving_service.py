"""
Main archiving service that orchestrates RSS fetching, content extraction,
and storage of articles.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from .rss_fetcher import RSSFetcher, load_feed_configs
from .content_extractor import ContentExtractor
from .text_normalizer import normalize_articles_batch
from .article_storage import ArticleStorage
from .database import Database

logger = logging.getLogger("ingestion")


class ArchivingService:
    """
    Orchestrates the archiving process for RSS feeds.

    This service:
    1. Fetches RSS feeds with pagination support
    2. Extracts full article content (from RSS or via trafilatura)
    3. Normalizes text content
    4. Stores articles in the database
    """

    def __init__(
        self,
        db_path: str,
        rss_config_path: str,
        min_content_length: int = 200,
        terms_config_path: Optional[str] = None
    ):
        """
        Initialize archiving service.

        Args:
            db_path: Path to SQLite database
            rss_config_path: Path to RSS feeds configuration JSON
            min_content_length: Minimum content length for full text detection
            terms_config_path: Path to terms_config.json (optional)
        """
        self.db_path = db_path
        self.rss_config_path = rss_config_path
        self.min_content_length = min_content_length
        self.terms_config_path = terms_config_path

        # Initialize database
        self.db = Database(db_path)
        self.db.initialize_schema()

        # Load feed configurations
        self.feed_configs = load_feed_configs(rss_config_path)
        if not self.feed_configs:
            logger.warning("No feed configurations loaded")

        # Initialize components
        self.rss_fetcher = RSSFetcher(self.feed_configs)
        self.content_extractor = ContentExtractor(min_content_length=min_content_length)

        logger.info(f"Archiving service initialized with {len(self.feed_configs)} feeds")

    async def archive_all_feeds(self) -> Dict[str, any]:
        """
        Archive articles from all configured RSS feeds.

        Returns:
            Statistics dictionary with results
        """
        logger.info("Starting archiving process for all feeds")
        start_time = datetime.utcnow()

        # Get list of enabled feeds
        feed_urls = list(self.feed_configs.keys())
        logger.info(f"Processing {len(feed_urls)} feeds")

        # Fetch all RSS feeds concurrently
        logger.info("Fetching RSS feeds...")
        feed_results = await self.rss_fetcher.fetch_all_feeds(feed_urls)

        # Process each feed's entries
        total_stats = {
            'feeds_processed': 0,
            'feeds_failed': 0,
            'total_entries': 0,
            'articles_extracted': 0,
            'articles_saved': 0,
            'duplicates': 0,
            'errors': 0,
            'feed_details': {}
        }

        for feed_url, entries in feed_results.items():
            feed_name = self.feed_configs[feed_url].get('name', feed_url)
            logger.info(f"Processing {feed_name}: {len(entries)} entries")

            if not entries:
                total_stats['feeds_failed'] += 1
                self._update_feed_stats(feed_url, success=False)
                continue

            total_stats['feeds_processed'] += 1
            total_stats['total_entries'] += len(entries)

            # Extract content from entries
            logger.info(f"Extracting content from {len(entries)} entries...")
            articles = await self.content_extractor.extract_from_entries(entries)

            total_stats['articles_extracted'] += len(articles)
            logger.info(f"Extracted {len(articles)} articles")

            if not articles:
                logger.warning(f"No articles extracted from {feed_name}")
                continue

            # Normalize articles
            logger.info(f"Normalizing {len(articles)} articles...")
            normalized_articles = normalize_articles_batch(articles)

            # Store articles
            logger.info(f"Storing {len(normalized_articles)} articles...")
            save_stats = self._save_articles(normalized_articles, feed_name)

            total_stats['articles_saved'] += save_stats['saved']
            total_stats['duplicates'] += save_stats['duplicates']
            total_stats['errors'] += save_stats['errors']

            # Store feed-specific stats
            total_stats['feed_details'][feed_name] = {
                'entries': len(entries),
                'extracted': len(articles),
                'saved': save_stats['saved'],
                'duplicates': save_stats['duplicates']
            }

            # Update feed statistics
            self._update_feed_stats(feed_url, success=True)

            logger.info(f"Completed {feed_name}: "
                       f"{save_stats['saved']} saved, "
                       f"{save_stats['duplicates']} duplicates")

        # Calculate duration
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        total_stats['duration_seconds'] = duration

        logger.info(f"Archiving complete in {duration:.2f}s - "
                   f"Saved: {total_stats['articles_saved']}, "
                   f"Duplicates: {total_stats['duplicates']}")

        return total_stats

    async def update_feeds(self, max_consecutive_duplicates: int = 5) -> Dict[str, any]:
        """
        Incremental update: fetch only new articles from RSS feeds.

        Stops fetching from each feed after encountering N consecutive
        articles that already exist in the database.

        Args:
            max_consecutive_duplicates: Stop after this many consecutive duplicates

        Returns:
            Statistics dictionary with results
        """
        logger.info("Starting incremental update for all feeds")
        start_time = datetime.utcnow()

        # Get list of enabled feeds
        feed_urls = list(self.feed_configs.keys())
        logger.info(f"Checking {len(feed_urls)} feeds for new articles")

        # Get existing article URLs from database
        logger.info("Loading existing article URLs from database...")
        existing_urls = self._get_existing_urls()
        logger.info(f"Found {len(existing_urls)} existing articles in database")

        # Fetch only new entries from RSS feeds
        logger.info("Fetching new RSS entries...")
        feed_results = await self.rss_fetcher.fetch_new_feeds(
            feed_urls,
            existing_urls,
            max_consecutive_duplicates
        )

        # Process each feed's new entries
        total_stats = {
            'feeds_processed': 0,
            'feeds_failed': 0,
            'total_entries': 0,
            'articles_extracted': 0,
            'articles_saved': 0,
            'duplicates': 0,
            'errors': 0,
            'feed_details': {}
        }

        for feed_url, entries in feed_results.items():
            feed_name = self.feed_configs[feed_url].get('name', feed_url)
            logger.info(f"Processing {feed_name}: {len(entries)} new entries")

            if not entries:
                logger.info(f"No new entries for {feed_name}")
                total_stats['feeds_processed'] += 1
                self._update_feed_stats(feed_url, success=True)
                total_stats['feed_details'][feed_name] = {
                    'entries': 0,
                    'extracted': 0,
                    'saved': 0,
                    'duplicates': 0
                }
                continue

            total_stats['feeds_processed'] += 1
            total_stats['total_entries'] += len(entries)

            # Extract content from entries
            logger.info(f"Extracting content from {len(entries)} new entries...")
            articles = await self.content_extractor.extract_from_entries(entries)

            total_stats['articles_extracted'] += len(articles)
            logger.info(f"Extracted {len(articles)} articles")

            if not articles:
                logger.warning(f"No articles extracted from {feed_name}")
                continue

            # Normalize articles
            logger.info(f"Normalizing {len(articles)} articles...")
            normalized_articles = normalize_articles_batch(articles)

            # Store articles
            logger.info(f"Storing {len(normalized_articles)} articles...")
            save_stats = self._save_articles(normalized_articles, feed_name)

            total_stats['articles_saved'] += save_stats['saved']
            total_stats['duplicates'] += save_stats['duplicates']
            total_stats['errors'] += save_stats['errors']

            # Store feed-specific stats
            total_stats['feed_details'][feed_name] = {
                'entries': len(entries),
                'extracted': len(articles),
                'saved': save_stats['saved'],
                'duplicates': save_stats['duplicates']
            }

            # Update feed statistics
            self._update_feed_stats(feed_url, success=True)

            logger.info(f"Completed {feed_name}: "
                       f"{save_stats['saved']} saved, "
                       f"{save_stats['duplicates']} duplicates")

        # Calculate duration
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        total_stats['duration_seconds'] = duration

        logger.info(f"Incremental update complete in {duration:.2f}s - "
                   f"Saved: {total_stats['articles_saved']}, "
                   f"Duplicates: {total_stats['duplicates']}")

        return total_stats

    def _get_existing_urls(self) -> set:
        """
        Get set of all existing article URLs from database.

        Returns:
            Set of article URLs
        """
        conn = self.db.connect()
        cursor = conn.cursor()

        cursor.execute("SELECT url FROM articles")
        rows = cursor.fetchall()

        existing_urls = {row['url'] for row in rows}
        return existing_urls

    async def archive_single_feed(self, feed_url: str) -> Dict[str, any]:
        """
        Archive articles from a single RSS feed.

        Args:
            feed_url: URL of the feed to archive

        Returns:
            Statistics dictionary with results
        """
        if feed_url not in self.feed_configs:
            logger.error(f"Feed URL not found in configuration: {feed_url}")
            return {'error': 'Feed not found in configuration'}

        feed_name = self.feed_configs[feed_url].get('name', feed_url)
        logger.info(f"Starting archiving process for feed: {feed_name}")
        start_time = datetime.utcnow()

        # Fetch RSS entries
        entries = await self.rss_fetcher.fetch_rss_entries(feed_url)

        if not entries:
            logger.warning(f"No entries fetched from {feed_name}")
            self._update_feed_stats(feed_url, success=False)
            return {
                'feed': feed_name,
                'entries': 0,
                'saved': 0,
                'duplicates': 0,
                'errors': 0
            }

        # Extract content
        logger.info(f"Extracting content from {len(entries)} entries...")
        articles = await self.content_extractor.extract_from_entries(entries)

        if not articles:
            logger.warning(f"No articles extracted from {feed_name}")
            return {
                'feed': feed_name,
                'entries': len(entries),
                'extracted': 0,
                'saved': 0,
                'duplicates': 0,
                'errors': 0
            }

        # Normalize articles
        logger.info(f"Normalizing {len(articles)} articles...")
        normalized_articles = normalize_articles_batch(articles)

        # Store articles
        logger.info(f"Storing {len(normalized_articles)} articles...")
        save_stats = self._save_articles(normalized_articles, feed_name)

        # Update feed statistics
        self._update_feed_stats(feed_url, success=True)

        # Calculate duration
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        stats = {
            'feed': feed_name,
            'entries': len(entries),
            'extracted': len(articles),
            'saved': save_stats['saved'],
            'duplicates': save_stats['duplicates'],
            'errors': save_stats['errors'],
            'duration_seconds': duration
        }

        logger.info(f"Completed {feed_name} in {duration:.2f}s - "
                   f"{save_stats['saved']} saved, "
                   f"{save_stats['duplicates']} duplicates")

        return stats

    def _save_articles(self, articles: List[Dict], source: str) -> Dict[str, int]:
        """
        Save articles to database.

        Args:
            articles: List of article dictionaries
            source: Source feed name

        Returns:
            Statistics dictionary
        """
        conn = self.db.connect()
        storage = ArticleStorage(conn, terms_config_path=self.terms_config_path)

        # Initialize feeds in database if not already done
        feed_configs_list = [config for config in self.feed_configs.values()]
        storage.initialize_feeds(feed_configs_list)

        return storage.save_articles_batch(articles, source)

    def _update_feed_stats(self, feed_url: str, success: bool):
        """
        Update feed statistics in database.

        Args:
            feed_url: URL of the feed
            success: Whether the fetch was successful
        """
        conn = self.db.connect()
        storage = ArticleStorage(conn)
        storage.update_feed_stats(feed_url, success)

    def get_statistics(self) -> Dict[str, any]:
        """
        Get current archiving statistics.

        Returns:
            Statistics dictionary
        """
        conn = self.db.connect()
        storage = ArticleStorage(conn)

        return {
            'total_articles': storage.get_article_count(),
            'recent_articles': storage.get_recent_articles(limit=10),
            'feeds_configured': len(self.feed_configs)
        }

    def close(self):
        """Close database connections and cleanup."""
        if self.db:
            self.db.close()
            logger.info("Archiving service closed")


async def run_archiving(
    db_path: str,
    rss_config_path: str,
    feed_url: Optional[str] = None,
    terms_config_path: Optional[str] = None
) -> Dict[str, any]:
    """
    Run the archiving process.

    Args:
        db_path: Path to SQLite database
        rss_config_path: Path to RSS feeds configuration
        feed_url: Optional specific feed URL to process (None for all feeds)
        terms_config_path: Path to terms_config.json (optional)

    Returns:
        Statistics dictionary
    """
    service = ArchivingService(
        db_path,
        rss_config_path,
        terms_config_path=terms_config_path
    )

    try:
        if feed_url:
            stats = await service.archive_single_feed(feed_url)
        else:
            stats = await service.archive_all_feeds()

        return stats
    finally:
        service.close()


async def run_update(
    db_path: str,
    rss_config_path: str,
    max_consecutive_duplicates: int = 5,
    terms_config_path: Optional[str] = None
) -> Dict[str, any]:
    """
    Run incremental update to fetch only new articles.

    Args:
        db_path: Path to SQLite database
        rss_config_path: Path to RSS feeds configuration
        max_consecutive_duplicates: Stop after this many consecutive duplicates
        terms_config_path: Path to terms_config.json (optional)

    Returns:
        Statistics dictionary
    """
    service = ArchivingService(
        db_path,
        rss_config_path,
        terms_config_path=terms_config_path
    )

    try:
        stats = await service.update_feeds(max_consecutive_duplicates)
        return stats
    finally:
        service.close()
