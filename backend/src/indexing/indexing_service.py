"""
Indexing service that orchestrates chunking and embedding of articles.
"""

import sqlite3
import json
from typing import Dict, List
from datetime import datetime, UTC
from pathlib import Path
import logging

from .chunking import ArticleChunker
from .txtai_manager import TxtaiManager
from ..ingestion.database import Database
from ..common.id_utils import make_article_id, make_chunk_id
from config.search_config import TITLE_WEIGHT_MULTIPLIER

logger = logging.getLogger("indexing")


class IndexingService:
    """
    Orchestrates the indexing process.

    This service:
    1. Loads articles from database
    2. Chunks long articles
    3. Generates embeddings and builds txtai index
    4. Updates database with indexing status
    """

    def __init__(
        self,
        db_path: str,
        index_path: str,
        chunk_threshold: int = 3500,
        chunk_size: int = 1000,
        overlap: int = 200
    ):
        """
        Initialize indexing service.

        Args:
            db_path: Path to SQLite database
            index_path: Path to txtai index
            chunk_threshold: Word count threshold for chunking
            chunk_size: Target chunk size in words
            overlap: Overlap between chunks in words
        """
        self.db_path = db_path
        self.index_path = index_path

        # Initialize components
        self.db = Database(db_path)
        self.txtai_manager = TxtaiManager(index_path)
        self.chunker = ArticleChunker(
            threshold_words=chunk_threshold,
            chunk_size_words=chunk_size,
            overlap_words=overlap
        )

        logger.info(f"Indexing service initialized")

    def build_index(self, force: bool = False) -> Dict:
        """
        Build complete txtai index from all articles.

        Args:
            force: Force rebuild if index exists

        Returns:
            Statistics dictionary
        """
        start_time = datetime.now(UTC)

        logger.info("Starting index building process...")

        # Check if index exists
        if self.txtai_manager.index_exists() and not force:
            logger.warning("Index already exists. Use force=True to rebuild.")
            return {
                'error': 'Index already exists. Use force=True to rebuild.',
                'duration_seconds': 0
            }

        # Create new index
        self.txtai_manager.create_index(force=force)

        # Load articles from database
        articles = self._load_articles()

        if not articles:
            logger.warning("No articles found in database")
            return {
                'articles_processed': 0,
                'articles_chunked': 0,
                'chunks_created': 0,
                'total_indexed': 0,
                'duration_seconds': 0
            }

        logger.info(f"Loaded {len(articles)} articles from database")

        # Process articles and create documents for indexing
        stats = {
            'articles_processed': 0,
            'articles_chunked': 0,
            'chunks_created': 0,
            'total_indexed': 0
        }

        all_documents = []

        for article in articles:
            stats['articles_processed'] += 1

            # Check if article should be chunked
            if self.chunker.should_chunk(article['content']):
                # Chunk the article
                chunks = self.chunker.chunk_article(article)

                if chunks:
                    stats['articles_chunked'] += 1
                    stats['chunks_created'] += len(chunks)

                    # Save chunks to database
                    self._save_chunks(chunks)

                    # Mark article as chunked
                    self._mark_article_chunked(article['id'])

                    # Add chunks to documents for indexing
                    for chunk in chunks:
                        chunk_doc = self._prepare_chunk_document(chunk, article)
                        all_documents.append(chunk_doc)
                else:
                    # Chunking failed, index article normally
                    article_doc = self._prepare_article_document(article)
                    all_documents.append(article_doc)
            else:
                # Article doesn't need chunking
                article_doc = self._prepare_article_document(article)
                all_documents.append(article_doc)

        # Index all documents
        logger.info(f"Indexing {len(all_documents)} documents (articles + chunks)...")
        self.txtai_manager.index_documents(all_documents)

        # Save the index
        self.txtai_manager.save_index()

        stats['total_indexed'] = len(all_documents)

        # Mark all articles as indexed
        self._mark_articles_indexed()

        # Calculate duration
        end_time = datetime.now(UTC)
        stats['duration_seconds'] = (end_time - start_time).total_seconds()

        logger.info(f"Index building complete in {stats['duration_seconds']:.2f}s")
        logger.info(f"Indexed {stats['total_indexed']} items "
                   f"({stats['articles_processed']} articles, "
                   f"{stats['chunks_created']} chunks)")

        return stats

    def update_index(self) -> Dict:
        """
        Incrementally update index with unindexed articles.

        Only indexes articles where indexed=0 in database.
        Much faster than full rebuild for regular updates.

        Returns:
            Statistics dictionary
        """
        start_time = datetime.now(UTC)

        logger.info("Starting incremental index update...")

        # Check if index exists
        if not self.txtai_manager.index_exists():
            logger.error("No index found. Run build_index() first.")
            return {
                'error': 'No index found. Run build_index() first.',
                'duration_seconds': 0
            }

        # Load index
        self.txtai_manager.load_index()

        # Load only unindexed articles
        articles = self._load_unindexed_articles()

        if not articles:
            logger.info("No new articles to index")
            return {
                'articles_processed': 0,
                'articles_chunked': 0,
                'chunks_created': 0,
                'total_indexed': 0,
                'duration_seconds': 0
            }

        logger.info(f"Found {len(articles)} unindexed articles")

        # Process articles and create documents for indexing
        stats = {
            'articles_processed': 0,
            'articles_chunked': 0,
            'chunks_created': 0,
            'total_indexed': 0
        }

        all_documents = []

        for article in articles:
            stats['articles_processed'] += 1

            # Check if article should be chunked
            if self.chunker.should_chunk(article['content']):
                # Chunk the article
                chunks = self.chunker.chunk_article(article)

                if chunks:
                    stats['articles_chunked'] += 1
                    stats['chunks_created'] += len(chunks)

                    # Save chunks to database
                    self._save_chunks(chunks)

                    # Mark article as chunked
                    self._mark_article_chunked(article['id'])

                    # Add chunks to documents for indexing
                    for chunk in chunks:
                        chunk_doc = self._prepare_chunk_document(chunk, article)
                        all_documents.append(chunk_doc)
                else:
                    # Chunking failed, index article normally
                    article_doc = self._prepare_article_document(article)
                    all_documents.append(article_doc)
            else:
                # Article doesn't need chunking
                article_doc = self._prepare_article_document(article)
                all_documents.append(article_doc)

        # Upsert documents to existing index
        logger.info(f"Adding {len(all_documents)} new documents to index...")
        self.txtai_manager.upsert_documents(all_documents)

        stats['total_indexed'] = len(all_documents)

        # Mark newly indexed articles
        article_ids = [article['id'] for article in articles]
        self._mark_specific_articles_indexed(article_ids)

        # Calculate duration
        end_time = datetime.now(UTC)
        stats['duration_seconds'] = (end_time - start_time).total_seconds()

        logger.info(f"Incremental index update complete in {stats['duration_seconds']:.2f}s")
        logger.info(f"Added {stats['total_indexed']} new items "
                   f"({stats['articles_processed']} articles, "
                   f"{stats['chunks_created']} chunks)")

        return stats

    def _load_unindexed_articles(self) -> List[Dict]:
        """
        Load only unindexed articles from database.

        Returns:
            List of article dictionaries where indexed=0
        """
        conn = self.db.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, url, title, content, summary, source, author,
                   published_date, word_count, tags_json, terms_json
            FROM articles
            WHERE indexed = 0
            ORDER BY published_date DESC
        """)

        articles = []
        for row in cursor.fetchall():
            # Parse tags JSON
            tags = []
            if row[9]:  # tags_json
                try:
                    tags = json.loads(row[9])
                except:
                    pass

            # Parse terms JSON
            terms = []
            if row[10]:  # terms_json
                try:
                    terms = json.loads(row[10])
                except:
                    pass

            # Extract year and month from published_date
            try:
                if isinstance(row[7], str):
                    pub_date = datetime.fromisoformat(row[7])
                else:
                    pub_date = row[7]
                pub_year = pub_date.year
                pub_month = pub_date.month
            except:
                pub_year = 0
                pub_month = 0

            article = {
                'id': row[0],
                'url': row[1],
                'title': row[2],
                'content': row[3],
                'summary': row[4],
                'source': row[5],
                'author': row[6],
                'published_date': row[7],
                'published_year': pub_year,
                'published_month': pub_month,
                'word_count': row[8] or 0,
                'tags': tags,
                'terms': terms
            }
            articles.append(article)

        return articles


    def _mark_specific_articles_indexed(self, article_ids: List[int]):
        """
        Mark specific articles as indexed.

        Args:
            article_ids: List of article IDs to mark
        """
        if not article_ids:
            return

        conn = self.db.connect()
        cursor = conn.cursor()

        placeholders = ','.join('?' * len(article_ids))
        cursor.execute(
            f"UPDATE articles SET indexed = 1 WHERE id IN ({placeholders})",
            article_ids
        )

        conn.commit()
        logger.info(f"Marked {len(article_ids)} articles as indexed")

    def _load_articles(self) -> List[Dict]:
        """
        Load all articles from database.

        Returns:
            List of article dictionaries
        """
        conn = self.db.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, url, title, content, summary, source, author,
                   published_date, word_count, tags_json, terms_json
            FROM articles
            ORDER BY published_date DESC
        """)

        articles = []
        for row in cursor.fetchall():
            # Parse tags JSON
            tags = []
            if row[9]:  # tags_json
                try:
                    tags = json.loads(row[9])
                except:
                    pass

            # Parse terms JSON
            terms = []
            if row[10]:  # terms_json
                try:
                    terms = json.loads(row[10])
                except:
                    pass

            # Extract year and month from published_date
            try:
                if isinstance(row[7], str):
                    pub_date = datetime.fromisoformat(row[7])
                else:
                    pub_date = row[7]
                pub_year = pub_date.year
                pub_month = pub_date.month
            except:
                pub_year = 0
                pub_month = 0

            article = {
                'id': row[0],
                'url': row[1],
                'title': row[2],
                'content': row[3],
                'summary': row[4],
                'source': row[5],
                'author': row[6],
                'published_date': row[7],
                'published_year': pub_year,
                'published_month': pub_month,
                'word_count': row[8] or 0,
                'tags': tags,
                'terms': terms
            }
            articles.append(article)

        return articles

    def _prepare_article_document(self, article: Dict) -> Dict:
        """
        Prepare article for indexing.

        For non-chunked articles, prepend title N times to weight title matching
        in semantic search. This ensures articles with matching titles rank higher.

        Args:
            article: Article dictionary

        Returns:
            Document dictionary for txtai
        """
        # Prepend title N times to content for semantic weighting
        title = article['title']
        content = article['content']

        # Weight title by repeating it before content
        title_prefix = (title + ". ") * TITLE_WEIGHT_MULTIPLIER
        weighted_content = title_prefix + content

        return {
            'id': make_article_id(article['id']),
            'article_id': article['id'],
            'title': title,
            'content': weighted_content,  # Content with title prefix
            'url': article['url'],
            'source': article['source'],
            'author': article.get('author', ''),
            'published_date': article['published_date'],
            'published_year': article.get('published_year', 0),
            'published_month': article.get('published_month', 0),
            'word_count': article.get('word_count', 0),
            'is_chunk': False,
            'chunk_index': 0,
            'tags': article.get('tags', []),
            'terms': article.get('terms', [])
        }

    def _prepare_chunk_document(
        self,
        chunk: Dict,
        article: Dict
    ) -> Dict:
        """
        Prepare chunk for indexing.

        Only the FIRST chunk (chunk_index=0) gets title weighting.
        This ensures title matching works without causing duplicate
        results from all chunks of the same article.

        Args:
            chunk: Chunk dictionary
            article: Parent article dictionary

        Returns:
            Document dictionary for txtai
        """
        title = article['title']
        content = chunk['content']
        chunk_index = chunk['chunk_index']

        # Only prepend title to FIRST chunk for title weighting
        # Other chunks get pure semantic embeddings without title boost
        if chunk_index == 0:
            title_prefix = (title + ". ") * TITLE_WEIGHT_MULTIPLIER
            weighted_content = title_prefix + content
        else:
            weighted_content = content

        return {
            'id': make_chunk_id(article['id'], chunk_index),
            'article_id': article['id'],
            'title': title,
            'content': weighted_content,  # Title prefix only on first chunk
            'url': article['url'],
            'source': article['source'],
            'author': article.get('author', ''),
            'published_date': article['published_date'],
            'published_year': article.get('published_year', 0),
            'published_month': article.get('published_month', 0),
            'word_count': chunk.get('word_count', 0),
            'is_chunk': True,
            'chunk_index': chunk_index,
            'tags': article.get('tags', []),
            'terms': article.get('terms', [])
        }

    def _save_chunks(self, chunks: List[Dict]):
        """
        Save chunks to database.

        Args:
            chunks: List of chunk dictionaries
        """
        conn = self.db.connect()
        cursor = conn.cursor()

        for chunk in chunks:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO article_chunks
                    (article_id, chunk_index, content, word_count, start_position)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    chunk['article_id'],
                    chunk['chunk_index'],
                    chunk['content'],
                    chunk['word_count'],
                    chunk['start_position']
                ))
            except Exception as e:
                logger.error(f"Error saving chunk: {e}")

        conn.commit()

    def _mark_article_chunked(self, article_id: int):
        """
        Mark article as chunked in database.

        Args:
            article_id: Article ID
        """
        conn = self.db.connect()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE articles
            SET is_chunked = 1
            WHERE id = ?
        """, (article_id,))

        conn.commit()

    def _mark_articles_indexed(self):
        """Mark all articles as indexed."""
        conn = self.db.connect()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE articles
            SET indexed = 1
            WHERE indexed = 0
        """)

        conn.commit()
        logger.info(f"Marked {cursor.rowcount} articles as indexed")

    def close(self):
        """Close database and index connections."""
        if self.db:
            self.db.close()
        if self.txtai_manager:
            self.txtai_manager.close()


def build_index(
    db_path: str,
    index_path: str,
    force: bool = False,
    chunk_threshold: int = 3500,
    chunk_size: int = 1000,
    overlap: int = 200
) -> Dict:
    """
    Build txtai index from archived articles.

    Args:
        db_path: Path to SQLite database
        index_path: Path to txtai index
        force: Force rebuild if index exists
        chunk_threshold: Word count threshold for chunking
        chunk_size: Target chunk size
        overlap: Overlap between chunks

    Returns:
        Statistics dictionary
    """
    service = IndexingService(
        db_path=db_path,
        index_path=index_path,
        chunk_threshold=chunk_threshold,
        chunk_size=chunk_size,
        overlap=overlap
    )

    try:
        stats = service.build_index(force=force)
        return stats
    finally:
        service.close()


def update_index(
    db_path: str,
    index_path: str,
    chunk_threshold: int = 3500,
    chunk_size: int = 1000,
    overlap: int = 200
) -> Dict:
    """
    Incrementally update txtai index with new articles.

    Only indexes articles where indexed=0 in database.
    Much faster than full rebuild for regular updates.

    Args:
        db_path: Path to SQLite database
        index_path: Path to txtai index
        chunk_threshold: Word count threshold for chunking
        chunk_size: Target chunk size
        overlap: Overlap between chunks

    Returns:
        Statistics dictionary
    """
    service = IndexingService(
        db_path=db_path,
        index_path=index_path,
        chunk_threshold=chunk_threshold,
        chunk_size=chunk_size,
        overlap=overlap
    )

    try:
        stats = service.update_index()
        return stats
    finally:
        service.close()
