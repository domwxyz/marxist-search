"""
Article storage module for saving articles to the database.
"""

import sqlite3
import json
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import logging

from .term_extractor import TermExtractor

logger = logging.getLogger(__name__)


class ArticleStorage:
    """Manages storing articles in the SQLite database."""

    def __init__(
        self,
        db_connection: sqlite3.Connection,
        terms_config_path: Optional[str] = None
    ):
        """
        Initialize article storage.

        Args:
            db_connection: SQLite database connection
            terms_config_path: Path to terms_config.json (optional)
        """
        self.db = db_connection
        self.term_extractor = None

        # Initialize term extractor if config provided
        if terms_config_path:
            try:
                self.term_extractor = TermExtractor(terms_config_path)
                logger.info("Term extractor initialized for article storage")
            except Exception as e:
                logger.warning(f"Could not initialize term extractor: {e}")
                self.term_extractor = None

    def save_article(self, article: Dict, source: str) -> Optional[int]:
        """
        Save a single article to the database.

        Args:
            article: Article dictionary with content and metadata
            source: Name of the RSS feed source

        Returns:
            Article ID if saved, None if duplicate or error
        """
        try:
            cursor = self.db.cursor()

            # Check if article already exists
            cursor.execute(
                "SELECT id FROM articles WHERE url = ? OR guid = ?",
                (article['url'], article.get('guid', ''))
            )
            existing = cursor.fetchone()

            if existing:
                logger.debug(f"Article already exists: {article['url']}")
                return None

            # Prepare tags JSON
            tags_json = json.dumps(article.get('tags_json', []))

            # Extract special terms if extractor is available
            terms_json = None
            term_mentions = []

            if self.term_extractor:
                try:
                    terms_json, term_mentions = self.term_extractor.extract_and_format(
                        article['title'],
                        article['content']
                    )
                except Exception as e:
                    logger.warning(f"Error extracting terms: {e}")

            # Insert article
            cursor.execute("""
                INSERT INTO articles (
                    url, guid, title, content, summary, source, author,
                    published_date, fetched_date, word_count, tags_json, terms_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article['url'],
                article.get('guid', ''),
                article['title'],
                article['content'],
                article.get('summary', ''),
                source,
                article.get('author'),
                article['published_date'],
                article['fetched_date'],
                article.get('word_count', 0),
                tags_json,
                terms_json
            ))

            article_id = cursor.lastrowid

            # Save term mentions if extracted
            if term_mentions:
                try:
                    self._save_term_mentions(article_id, term_mentions)
                except Exception as e:
                    logger.warning(f"Error saving term mentions: {e}")

            # Update author statistics
            self._update_author_stats(
                article.get('author'),
                article['published_date']
            )

            self.db.commit()
            logger.info(f"Saved article: {article['title'][:50]}... (ID: {article_id})")
            return article_id

        except sqlite3.IntegrityError as e:
            logger.warning(f"Duplicate article detected: {article['url']} - {e}")
            return None
        except Exception as e:
            logger.error(f"Error saving article {article.get('url', 'unknown')}: {e}")
            self.db.rollback()
            return None

    def save_articles_batch(self, articles: List[Dict], source: str) -> Dict[str, int]:
        """
        Save multiple articles in a batch.

        Args:
            articles: List of article dictionaries
            source: Name of the RSS feed source

        Returns:
            Dictionary with statistics (saved, duplicates, errors)
        """
        stats = {
            'saved': 0,
            'duplicates': 0,
            'errors': 0
        }

        for article in articles:
            article_id = self.save_article(article, source)
            if article_id:
                stats['saved'] += 1
            else:
                stats['duplicates'] += 1

        logger.info(f"Batch save complete - Saved: {stats['saved']}, "
                   f"Duplicates: {stats['duplicates']}, Errors: {stats['errors']}")
        return stats

    def _update_author_stats(self, author: Optional[str], published_date: datetime):
        """
        Update author statistics.

        Args:
            author: Author name
            published_date: Publication date
        """
        if not author:
            return

        try:
            cursor = self.db.cursor()

            # Check if author exists
            cursor.execute(
                "SELECT article_count, latest_article_date, first_article_date FROM author_stats WHERE author = ?",
                (author,)
            )
            existing = cursor.fetchone()

            if existing:
                article_count, latest_date, first_date = existing

                # Parse dates if they're strings
                if isinstance(latest_date, str):
                    latest_date = datetime.fromisoformat(latest_date)
                if isinstance(first_date, str):
                    first_date = datetime.fromisoformat(first_date)

                # Update statistics
                new_latest = max(published_date, latest_date) if latest_date else published_date
                new_first = min(published_date, first_date) if first_date else published_date

                cursor.execute("""
                    UPDATE author_stats
                    SET article_count = article_count + 1,
                        latest_article_date = ?,
                        first_article_date = ?
                    WHERE author = ?
                """, (new_latest, new_first, author))
            else:
                # Insert new author
                cursor.execute("""
                    INSERT INTO author_stats (author, article_count, latest_article_date, first_article_date)
                    VALUES (?, 1, ?, ?)
                """, (author, published_date, published_date))

        except Exception as e:
            logger.error(f"Error updating author stats for {author}: {e}")

    def _save_term_mentions(self, article_id: int, term_mentions: List[Dict]):
        """
        Save term mentions to database.

        Args:
            article_id: Article ID
            term_mentions: List of term mention dictionaries
        """
        try:
            cursor = self.db.cursor()

            for term_info in term_mentions:
                cursor.execute("""
                    INSERT INTO term_mentions (article_id, term_text, term_type, mention_count)
                    VALUES (?, ?, ?, ?)
                """, (
                    article_id,
                    term_info['term_text'],
                    term_info['term_type'],
                    term_info['mention_count']
                ))

            logger.debug(f"Saved {len(term_mentions)} term mentions for article {article_id}")

        except Exception as e:
            logger.error(f"Error saving term mentions for article {article_id}: {e}")

    def update_feed_stats(self, feed_url: str, success: bool, etag: Optional[str] = None,
                         last_modified: Optional[str] = None):
        """
        Update RSS feed statistics.

        Args:
            feed_url: URL of the RSS feed
            success: Whether the fetch was successful
            etag: ETag header from response
            last_modified: Last-Modified header from response
        """
        try:
            cursor = self.db.cursor()

            # Check if feed exists
            cursor.execute("SELECT id, consecutive_failures FROM rss_feeds WHERE url = ?", (feed_url,))
            existing = cursor.fetchone()

            now = datetime.utcnow()

            if success:
                # Reset consecutive failures on success
                if existing:
                    cursor.execute("""
                        UPDATE rss_feeds
                        SET last_checked = ?,
                            last_modified = ?,
                            etag = ?,
                            consecutive_failures = 0,
                            status = 'active'
                        WHERE url = ?
                    """, (now, last_modified, etag, feed_url))
                else:
                    # This shouldn't happen if feeds are pre-populated, but handle it
                    logger.warning(f"Feed {feed_url} not found in database, skipping stats update")
            else:
                # Increment consecutive failures
                if existing:
                    failures = existing[1] + 1
                    status = 'active'

                    if failures >= 10:
                        status = 'failing'
                    elif failures >= 3:
                        status = 'degraded'

                    cursor.execute("""
                        UPDATE rss_feeds
                        SET last_checked = ?,
                            consecutive_failures = ?,
                            status = ?
                        WHERE url = ?
                    """, (now, failures, status, feed_url))

                    if status != 'active':
                        logger.warning(f"Feed {feed_url} status changed to: {status}")

            self.db.commit()

        except Exception as e:
            logger.error(f"Error updating feed stats for {feed_url}: {e}")
            self.db.rollback()

    def get_article_count(self, source: Optional[str] = None) -> int:
        """
        Get count of articles in database.

        Args:
            source: Optional source filter

        Returns:
            Article count
        """
        try:
            cursor = self.db.cursor()

            if source:
                cursor.execute("SELECT COUNT(*) FROM articles WHERE source = ?", (source,))
            else:
                cursor.execute("SELECT COUNT(*) FROM articles")

            result = cursor.fetchone()
            return result[0] if result else 0

        except Exception as e:
            logger.error(f"Error getting article count: {e}")
            return 0

    def get_recent_articles(self, limit: int = 10) -> List[Dict]:
        """
        Get most recent articles.

        Args:
            limit: Maximum number of articles to return

        Returns:
            List of article dictionaries
        """
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT id, url, title, source, author, published_date, word_count
                FROM articles
                ORDER BY published_date DESC
                LIMIT ?
            """, (limit,))

            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'url': row[1],
                    'title': row[2],
                    'source': row[3],
                    'author': row[4],
                    'published_date': row[5],
                    'word_count': row[6]
                })

            return articles

        except Exception as e:
            logger.error(f"Error getting recent articles: {e}")
            return []

    def initialize_feeds(self, feeds_config: List[Dict]):
        """
        Initialize RSS feeds in database from configuration.

        Args:
            feeds_config: List of feed configurations
        """
        try:
            cursor = self.db.cursor()

            for feed in feeds_config:
                if not feed.get('enabled', True):
                    continue

                # Check if feed already exists
                cursor.execute("SELECT id FROM rss_feeds WHERE url = ?", (feed['url'],))
                existing = cursor.fetchone()

                if not existing:
                    cursor.execute("""
                        INSERT INTO rss_feeds (url, name, pagination_type, limit_increment)
                        VALUES (?, ?, ?, ?)
                    """, (
                        feed['url'],
                        feed['name'],
                        feed.get('pagination_type', 'standard'),
                        feed.get('limit_increment', 5)
                    ))
                    logger.info(f"Initialized feed: {feed['name']}")

            self.db.commit()

        except Exception as e:
            logger.error(f"Error initializing feeds: {e}")
            self.db.rollback()
