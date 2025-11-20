"""
Core search engine implementation with filtering and deduplication.
"""

import sqlite3
import threading
from typing import List, Dict, Optional, Any
from datetime import datetime
from collections import defaultdict
import logging
import json

from txtai.embeddings import Embeddings

from .filters import SearchFilters
from ..ingestion.term_extractor import TermExtractor
from config.search_config import SEARCH_CONFIG, INDEX_PATH, DATABASE_PATH, TERMS_CONFIG

logger = logging.getLogger('search')


class SearchEngine:
    """
    Thread-safe search engine with filtering and deduplication.

    Features:
    - Hybrid search (semantic + BM25)
    - Filtering by date, source, author
    - Smart deduplication of article chunks
    - Recency boosting
    - Thread-safe operations
    """

    def __init__(
        self,
        index_path: str = None,
        db_path: str = None,
        enable_query_expansion: bool = True
    ):
        """
        Initialize search engine.

        Args:
            index_path: Path to txtai index
            db_path: Path to SQLite database
            enable_query_expansion: Enable automatic query expansion with synonyms/aliases
        """
        self.index_path = index_path or INDEX_PATH
        self.db_path = db_path or DATABASE_PATH

        self.embeddings: Optional[Embeddings] = None
        self.db_conn: Optional[sqlite3.Connection] = None
        self.rw_lock = threading.RLock()

        # Search configuration
        self.semantic_weight = SEARCH_CONFIG['semantic_weight']
        self.bm25_weight = SEARCH_CONFIG['bm25_weight']
        self.recency_boosts = SEARCH_CONFIG['recency_boost']

        # Initialize term extractor for query expansion
        self.term_extractor = None
        self.enable_query_expansion = enable_query_expansion
        if enable_query_expansion:
            try:
                self.term_extractor = TermExtractor(TERMS_CONFIG)
                logger.info("Query expansion enabled with term extractor")
            except Exception as e:
                logger.warning(f"Could not initialize term extractor: {e}")
                self.enable_query_expansion = False

    def load_index(self):
        """Load txtai index into memory (thread-safe)."""
        with self.rw_lock:
            if self.embeddings is not None:
                logger.warning("Index already loaded")
                return

            logger.info(f"Loading txtai index from {self.index_path}...")

            try:
                self.embeddings = Embeddings()
                self.embeddings.load(self.index_path)

                count = self.embeddings.count()
                logger.info(f"Index loaded successfully with {count} documents")

            except Exception as e:
                logger.error(f"Failed to load index: {e}")
                raise

    def connect_db(self):
        """Create database connection."""
        if self.db_conn is None:
            self.db_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.db_conn.row_factory = sqlite3.Row

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Execute search with filtering and deduplication.

        Args:
            query: Search query string
            filters: Optional filters (source, author, date_range, etc.)
            limit: Maximum results to return (after deduplication)
            offset: Offset for pagination

        Returns:
            Dictionary with search results and metadata
        """
        if self.embeddings is None:
            raise RuntimeError("Index not loaded. Call load_index() first.")

        filters = filters or {}

        # Expand query with synonyms and aliases if enabled
        original_query = query
        if self.enable_query_expansion and self.term_extractor:
            try:
                expanded_query = self._expand_query(query)
                if expanded_query != query:
                    logger.info(f"Query expanded: '{query}' -> '{expanded_query}'")
                    query = expanded_query
            except Exception as e:
                logger.warning(f"Query expansion failed, using original query: {e}")

        logger.info(f"Executing search: query='{query}', filters={filters}, limit={limit}")

        start_time = datetime.now()

        # Build WHERE clause from filters
        where_clause = SearchFilters.build_where_clause(filters)

        # Calculate search limit (fetch more to account for deduplication)
        # We fetch 3x the limit to ensure we have enough after deduplication
        search_limit = (limit + offset) * 3

        # Execute txtai search
        try:
            raw_results = self._execute_txtai_search(
                query=query,
                where=where_clause,
                limit=search_limit
            )

            logger.debug(f"txtai returned {len(raw_results)} raw results")

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

        # Deduplicate and rank results
        deduplicated = self._deduplicate_results(raw_results)

        # Apply recency boosting
        boosted = self._apply_recency_boost(deduplicated)

        # Sort by final score
        sorted_results = sorted(boosted, key=lambda x: x['score'], reverse=True)

        # Apply pagination
        paginated = sorted_results[offset:offset + limit]

        # Format results with excerpts
        formatted = self._format_results(paginated, query)

        # Calculate query time
        query_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        logger.info(
            f"Search completed: {len(formatted)} results returned, "
            f"{len(deduplicated)} unique articles, "
            f"{query_time_ms}ms"
        )

        return {
            'results': formatted,
            'total': len(deduplicated),
            'page': (offset // limit) + 1 if limit > 0 else 1,
            'limit': limit,
            'offset': offset,
            'query_time_ms': query_time_ms,
            'query': query,
            'original_query': original_query,
            'query_expanded': query != original_query,
            'filters': filters
        }

    def _expand_query(self, query: str) -> str:
        """
        Expand query with synonyms and aliases.

        Examples:
        - "USSR" -> "USSR OR Soviet Union"
        - "proletariat" -> "proletariat OR working class OR workers OR wage laborers"
        - "UN peacekeeping" -> "(UN OR United Nations) peacekeeping"

        Args:
            query: Original search query

        Returns:
            Expanded query with synonyms and aliases
        """
        if not self.term_extractor:
            return query

        # Split query into words
        words = query.split()
        expanded_parts = []

        for word in words:
            # Clean word (remove punctuation for matching)
            clean_word = word.strip('.,!?;:')

            # Get synonyms for this word
            synonyms = self.term_extractor.get_synonyms_for_query(clean_word)

            # Check if it's an alias
            alias_match = self.term_extractor.alias_mapping.get(clean_word.lower())
            if alias_match:
                # Add both the alias and the canonical term
                canonical = self.term_extractor._get_original_term(alias_match)
                synonyms_set = set(synonyms + [canonical, clean_word])
                synonyms = list(synonyms_set)

            if len(synonyms) > 1:
                # Create OR clause for synonyms (limit to 5 for performance)
                unique_synonyms = list(set(synonyms[:5]))
                synonym_clause = " OR ".join(f'"{s}"' for s in unique_synonyms)
                expanded_parts.append(f"({synonym_clause})")
            else:
                # No expansion needed, keep original word
                expanded_parts.append(word)

        expanded = " ".join(expanded_parts)
        return expanded

    def _execute_txtai_search(
        self,
        query: str,
        where: Optional[str],
        limit: int
    ) -> List[Dict]:
        """
        Execute txtai hybrid search.

        Thread-safe read operation.
        """
        # Build SQL query for txtai 7.x with content storage
        # This retrieves all metadata fields from the stored documents
        sql_query = f"""
            SELECT id, text, article_id, title, url, source, author,
                   published_date, published_year, published_month,
                   word_count, is_chunk, chunk_index, tags, terms, score
            FROM txtai
            WHERE similar('{query.replace("'", "''")}', {self.semantic_weight})
        """

        # Add WHERE clause if filters provided
        if where:
            # Insert WHERE conditions after the similar() clause
            sql_query = sql_query.replace(
                f"WHERE similar('{query.replace("'", "''")}', {self.semantic_weight})",
                f"WHERE similar('{query.replace("'", "''")}', {self.semantic_weight}) AND ({where})"
            )

        # Add LIMIT clause
        sql_query += f" LIMIT {limit}"

        # Execute SQL search (thread-safe)
        results = self.embeddings.search(sql_query)

        return results

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """
        Deduplicate results by article_id.

        When multiple chunks from the same article match:
        - Keep only the highest-scoring chunk
        - Track how many chunks matched (matched_sections)
        """
        article_groups = defaultdict(list)

        # Group results by article_id
        for result in results:
            article_id = result.get('article_id', result.get('id'))
            article_groups[article_id].append(result)

        deduplicated = []

        for article_id, chunks in article_groups.items():
            # Sort chunks by score (descending)
            sorted_chunks = sorted(chunks, key=lambda x: x['score'], reverse=True)

            # Take the highest-scoring chunk
            best_chunk = sorted_chunks[0]

            # Add metadata about matched sections
            best_chunk['matched_sections'] = len(chunks)
            best_chunk['is_multi_chunk'] = len(chunks) > 1

            deduplicated.append(best_chunk)

        logger.debug(
            f"Deduplication: {len(results)} chunks -> {len(deduplicated)} unique articles"
        )

        return deduplicated

    def _apply_recency_boost(self, results: List[Dict]) -> List[Dict]:
        """
        Apply recency boost to search scores.

        Boost formula:
        - < 30 days: +0.05
        - < 90 days: +0.02
        - < 1 year: +0.01
        """
        now = datetime.now()

        for result in results:
            published_date = result.get('published_date')

            if not published_date:
                continue

            # Parse date
            try:
                if isinstance(published_date, str):
                    # Parse ISO format and remove timezone info to make it naive
                    pub_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
                    # Remove timezone info to match naive datetime.now()
                    if pub_date.tzinfo is not None:
                        pub_date = pub_date.replace(tzinfo=None)
                else:
                    pub_date = published_date
                    # Ensure it's naive
                    if hasattr(pub_date, 'tzinfo') and pub_date.tzinfo is not None:
                        pub_date = pub_date.replace(tzinfo=None)

                # Calculate age (both datetimes are now naive)
                age_days = (now - pub_date).days

                # Apply boost
                boost = 0.0
                if age_days < 30:
                    boost = self.recency_boosts['30_days']
                elif age_days < 90:
                    boost = self.recency_boosts['90_days']
                elif age_days < 365:
                    boost = self.recency_boosts['1_year']

                if boost > 0:
                    result['original_score'] = result['score']
                    result['score'] = result['score'] + boost
                    result['recency_boost'] = boost

            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse date '{published_date}': {e}")
                continue

        return results

    def _format_results(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Format results with excerpts and clean metadata.

        Returns list of formatted result dictionaries.
        """
        formatted = []

        for result in results:
            # Extract content for excerpt
            content = result.get('text', '')
            if not content:
                content = result.get('content', '')

            # Create excerpt (first 200 characters)
            excerpt = content[:200] + '...' if len(content) > 200 else content
            excerpt = excerpt.strip()

            # Parse tags and terms from JSON strings
            tags = result.get('tags', '[]')
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except (json.JSONDecodeError, TypeError):
                    tags = []

            terms = result.get('terms', '[]')
            if isinstance(terms, str):
                try:
                    terms = json.loads(terms)
                except (json.JSONDecodeError, TypeError):
                    terms = []

            formatted_result = {
                'id': result.get('id'),
                'article_id': result.get('article_id'),
                'title': result.get('title') or 'Untitled',
                'url': result.get('url') or '',
                'source': result.get('source') or '',
                'author': result.get('author') or 'Unknown',
                'published_date': result.get('published_date') or '',
                'excerpt': excerpt,
                'score': round(result.get('score', 0.0), 4),
                'matched_sections': result.get('matched_sections', 1),
                'word_count': result.get('word_count', 0),
                'tags': tags,
                'terms': terms
            }

            # Add debugging info if available
            if 'recency_boost' in result:
                formatted_result['recency_boost'] = result['recency_boost']
                formatted_result['original_score'] = result.get('original_score')

            formatted.append(formatted_result)

        return formatted

    def get_sources(self) -> List[Dict[str, Any]]:
        """
        Get list of all article sources with counts.

        Returns:
            List of source dictionaries
        """
        self.connect_db()

        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT
                source,
                COUNT(*) as article_count,
                MAX(published_date) as latest_article,
                MIN(published_date) as earliest_article
            FROM articles
            WHERE indexed = 1
            GROUP BY source
            ORDER BY article_count DESC
        """)

        sources = []
        for row in cursor.fetchall():
            sources.append({
                'name': row['source'],
                'article_count': row['article_count'],
                'latest_article': row['latest_article'],
                'earliest_article': row['earliest_article']
            })

        return sources

    def get_top_authors(self, min_articles: int = 10, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Get top authors by article count.

        Args:
            min_articles: Minimum article count threshold
            limit: Maximum authors to return

        Returns:
            List of author dictionaries
        """
        self.connect_db()

        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT
                author,
                COUNT(*) as article_count,
                MAX(published_date) as latest_article,
                MIN(published_date) as earliest_article
            FROM articles
            WHERE indexed = 1
              AND author IS NOT NULL
              AND author != ''
            GROUP BY author
            HAVING article_count >= ?
            ORDER BY article_count DESC
            LIMIT ?
        """, (min_articles, limit))

        authors = []
        for row in cursor.fetchall():
            authors.append({
                'name': row['author'],
                'article_count': row['article_count'],
                'latest_article': row['latest_article'],
                'earliest_article': row['earliest_article']
            })

        return authors

    def get_stats(self) -> Dict[str, Any]:
        """
        Get index and database statistics.

        Returns:
            Dictionary with statistics
        """
        self.connect_db()

        cursor = self.db_conn.cursor()

        # Total articles
        cursor.execute("SELECT COUNT(*) as count FROM articles")
        total_articles = cursor.fetchone()['count']

        # Indexed articles
        cursor.execute("SELECT COUNT(*) as count FROM articles WHERE indexed = 1")
        indexed_articles = cursor.fetchone()['count']

        # Total chunks
        cursor.execute("SELECT COUNT(*) as count FROM article_chunks")
        total_chunks = cursor.fetchone()['count']

        # Date range
        cursor.execute("""
            SELECT
                MIN(published_date) as earliest,
                MAX(published_date) as latest
            FROM articles
            WHERE indexed = 1
        """)
        date_row = cursor.fetchone()

        # Source count
        cursor.execute("SELECT COUNT(DISTINCT source) as count FROM articles WHERE indexed = 1")
        sources_count = cursor.fetchone()['count']

        # Index count
        index_count = self.embeddings.count() if self.embeddings else 0

        stats = {
            'total_articles': total_articles,
            'indexed_articles': indexed_articles,
            'total_chunks': total_chunks,
            'date_range': {
                'earliest': date_row['earliest'] if date_row else None,
                'latest': date_row['latest'] if date_row else None
            },
            'sources_count': sources_count,
            'index_document_count': index_count,
            'index_loaded': self.embeddings is not None
        }

        return stats

    def close(self):
        """Close connections and cleanup."""
        with self.rw_lock:
            if self.embeddings:
                self.embeddings.close()
                self.embeddings = None

            if self.db_conn:
                self.db_conn.close()
                self.db_conn = None

        logger.info("Search engine closed")
