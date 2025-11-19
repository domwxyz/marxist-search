"""
Database initialization and management for the Marxist search engine.
"""

import sqlite3
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    """Manages SQLite database connections and schema."""

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """
        Create and return a database connection.

        Returns:
            SQLite connection object
        """
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def initialize_schema(self):
        """Create all database tables and indexes."""
        conn = self.connect()
        cursor = conn.cursor()

        # Articles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                guid TEXT UNIQUE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                source TEXT NOT NULL,
                author TEXT,
                published_date DATETIME NOT NULL,
                fetched_date DATETIME NOT NULL,
                word_count INTEGER,
                is_chunked BOOLEAN DEFAULT 0,
                indexed BOOLEAN DEFAULT 0,
                embedding_version TEXT DEFAULT '1.0',
                terms_json TEXT,
                tags_json TEXT
            )
        """)

        # Article chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                word_count INTEGER,
                start_position INTEGER,
                FOREIGN KEY (article_id) REFERENCES articles(id),
                UNIQUE(article_id, chunk_index)
            )
        """)

        # Author statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS author_stats (
                author TEXT PRIMARY KEY,
                article_count INTEGER DEFAULT 0,
                latest_article_date DATETIME,
                first_article_date DATETIME
            )
        """)

        # RSS feeds table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rss_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                pagination_type TEXT DEFAULT 'standard',
                limit_increment INTEGER DEFAULT 5,
                last_checked DATETIME,
                last_modified DATETIME,
                etag TEXT,
                status TEXT DEFAULT 'active',
                consecutive_failures INTEGER DEFAULT 0,
                article_count INTEGER DEFAULT 0
            )
        """)

        # Term mentions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS term_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                term_text TEXT NOT NULL,
                term_type TEXT,
                mention_count INTEGER DEFAULT 1,
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
        """)

        # Search logs table (optional)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                filters_json TEXT,
                result_count INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_published_date ON articles(published_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_author ON articles(author)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexed ON articles(indexed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_term_text ON term_mentions(term_text)")

        conn.commit()
        logger.info("Database schema initialized successfully")

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def init_database(db_path: str) -> Database:
    """
    Initialize database with schema.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Database instance
    """
    db = Database(db_path)
    db.initialize_schema()
    return db
