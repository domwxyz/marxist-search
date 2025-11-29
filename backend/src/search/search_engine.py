"""
Core search engine implementation with filtering and deduplication.
"""

import sqlite3
import threading
import re
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import json
import math

from txtai.embeddings import Embeddings

from .filters import SearchFilters
from .query_parser import QueryParser, ParsedQuery
from ..ingestion.term_extractor import TermExtractor
from ..common.id_utils import parse_txtai_id, extract_article_id
from config.search_config import (
    SEARCH_CONFIG,
    INDEX_PATH,
    DATABASE_PATH,
    TERMS_CONFIG,
    RERANKING_CONFIG
)

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

        # Initialize query parser for power-user syntax
        self.query_parser = QueryParser()

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
        Execute search with power-user syntax support.

        Supports:
        - Exact phrases: "quoted text"
        - Title search: title:"The Labour Theory"
        - Author search: author:"Alan Woods"
        - Combined: title:"Theory" author:"Woods" capitalism

        Args:
            query: Search query (may contain power-user syntax)
            filters: Optional filters from UI
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            Search results with metadata
        """
        if self.embeddings is None:
            raise RuntimeError("Index not loaded. Call load_index() first.")

        filters = filters or {}

        # Parse query for power-user syntax
        try:
            parsed_query = self.query_parser.parse(query)
        except ValueError as e:
            logger.error(f"Query parsing failed: {e}")
            return {
                'results': [],
                'total': 0,
                'page': 1,
                'limit': limit,
                'offset': offset,
                'query_time_ms': 0,
                'query': query,
                'error': str(e)
            }

        if not parsed_query.has_content():
            logger.warning("Empty query after parsing")
            return {
                'results': [],
                'total': 0,
                'page': 1,
                'limit': limit,
                'offset': offset,
                'query_time_ms': 0,
                'query': query
            }

        # Merge parsed query filters with UI filters
        # Power-user syntax takes precedence
        filters = self.query_parser.build_filters_from_parsed(parsed_query, filters)

        # Get semantic query for vector search
        semantic_query = parsed_query.get_semantic_query()

        # Expand query with synonyms if enabled (only for semantic search)
        original_query = semantic_query
        
        logger.info(
            f"Executing search: query='{query}', "
            f"semantic_terms={parsed_query.semantic_terms}, "
            f"exact_phrases={parsed_query.exact_phrases}, "
            f"title_phrases={parsed_query.title_phrases}, "
            f"author_filter={parsed_query.author_filter}"
        )

        start_time = datetime.now()

        # Determine search strategy based on query composition
        has_semantic_terms = bool(parsed_query.semantic_terms)
        has_exact_phrases = bool(parsed_query.exact_phrases)
        has_title_phrases = bool(parsed_query.title_phrases)

        # Determine if this is a pure phrase query (phrases but no semantic terms)
        # These should use semantic search with the phrase as query for relevance ranking
        is_pure_phrase_query = (not has_semantic_terms) and (has_exact_phrases or has_title_phrases)

        # Check if this is a filter-only query (no searchable content at all)
        is_filter_only = not has_semantic_terms and not has_exact_phrases and not has_title_phrases

        # Use database search ONLY for filter-only queries (author/source/date only)
        # For pure phrase queries, use semantic search for better performance
        if is_filter_only:
            logger.info("Using database search (filter-only query)")
            raw_results = self._search_database_for_phrases(
                exact_phrases=None,
                title_phrases=None,
                filters=filters,
                limit=8000
            )
            # Filters already applied in SQL
            filtered_results = raw_results
            needs_exact_phrase_filter = False
            needs_title_phrase_filter = False
        else:
            # Semantic search for all other queries (semantic terms, pure phrases, or combined)
            # For pure phrase queries, semantic_query contains the phrase text
            if is_pure_phrase_query:
                logger.info(f"Pure phrase query - using semantic search with: '{semantic_query}'")

            # Optionally expand with synonyms (but not for pure phrase queries)
            if self.enable_query_expansion and self.term_extractor and semantic_query and not is_pure_phrase_query:
                try:
                    expanded = self._expand_query(semantic_query)
                    if expanded != semantic_query:
                        logger.info(f"Query expanded: '{semantic_query}' -> '{expanded}'")
                        semantic_query = expanded
                except Exception as e:
                    logger.warning(f"Query expansion failed: {e}")

            try:
                # For pure phrase queries, use total index size as limit to ensure we get ALL matches
                # that will be filtered for exact phrase. This ensures complete results while
                # maintaining semantic relevance ranking.
                if is_pure_phrase_query:
                    # Get total documents in index
                    total_docs = self.embeddings.count() if self.embeddings else 50000
                    search_limit = total_docs
                    logger.info(f"Pure phrase query: searching all {search_limit} documents for phrase matches")
                else:
                    search_limit = 8000

                raw_results = self._execute_txtai_search(
                    query=semantic_query if semantic_query else query,
                    limit=search_limit
                )
                logger.debug(f"txtai returned {len(raw_results)} raw results (limit={search_limit})")
            except Exception as e:
                logger.error(f"Search failed: {e}")
                raise

            needs_exact_phrase_filter = has_exact_phrases
            needs_title_phrase_filter = has_title_phrases

        # Apply filters (source, author, date)
        # Semantic search and pure phrase queries need Python filtering
        # Filter-only database search already applied filters in SQL
        if filters and not is_filter_only:
            filtered_results = self._apply_filters(raw_results, filters)
            logger.debug(f"Filtered {len(raw_results)} -> {len(filtered_results)} results")
        else:
            filtered_results = raw_results

        # Apply exact phrase matching with regex (for word boundary accuracy)
        if needs_exact_phrase_filter and parsed_query.exact_phrases:
            filtered_results = self._filter_by_exact_phrases(
                filtered_results,
                parsed_query.exact_phrases
            )
            logger.debug(
                f"Exact phrase filter: {len(filtered_results)} results match "
                f"{len(parsed_query.exact_phrases)} phrases"
            )

        # Apply title phrase matching
        if needs_title_phrase_filter and parsed_query.title_phrases:
            filtered_results = self._filter_by_title_phrases(
                filtered_results,
                parsed_query.title_phrases
            )
            logger.debug(
                f"Title phrase filter: {len(filtered_results)} results"
            )

        # Deduplicate results
        deduplicated = self._deduplicate_results(filtered_results)
        total_count = len(deduplicated)

        # === Multi-signal reranking ===
        query_terms = parsed_query.semantic_terms

        # 1. Title term boost (free - no content fetch needed)
        if query_terms:
            deduplicated = self._apply_title_term_boost(deduplicated, query_terms)

        # 2. Keyword frequency boost on top candidates
        max_terms = RERANKING_CONFIG['keyword_max_query_terms']
        if query_terms and len(query_terms) <= max_terms:
            deduplicated = self._apply_keyword_boost(deduplicated, query_terms)

        # 3. Recency boost
        boosted = self._apply_recency_boost(deduplicated)

        # Sort by final combined score
        sorted_results = sorted(boosted, key=lambda x: x['score'], reverse=True)

        # Paginate
        paginated = sorted_results[offset:offset + limit]

        # Fetch content for results that don't have it yet
        # (top_n from keyword boost already have content)
        paginated_with_content = self._ensure_content(paginated)

        # Format results with matched phrase info for highlighting
        formatted = self._format_results(
            paginated_with_content,
            query,
            parsed_query.exact_phrases
        )

        # Calculate query time
        query_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        logger.info(
            f"Search completed: {len(formatted)} results returned, "
            f"{total_count} total unique articles, {query_time_ms}ms"
        )

        return {
            'results': formatted,
            'total': total_count,
            'page': (offset // limit) + 1 if limit > 0 else 1,
            'limit': limit,
            'offset': offset,
            'query_time_ms': query_time_ms,
            'query': query,
            'parsed_query': {
                'semantic_terms': parsed_query.semantic_terms,
                'exact_phrases': parsed_query.exact_phrases,
                'title_phrases': parsed_query.title_phrases,
                'author_filter': parsed_query.author_filter
            },
            'filters': filters
        }

    def _expand_query(self, query: str) -> str:
        """
        Expand query with synonyms and aliases (bidirectional).

        Examples:
        - "USSR" -> "(USSR OR Soviet Union)"
        - "Soviet Union" -> "(Soviet Union OR USSR)"
        - "proletariat" -> "(proletariat OR working class OR workers OR wage laborers)"
        - "UN peacekeeping" -> "(UN OR United Nations) peacekeeping"

        Args:
            query: Original search query

        Returns:
            Expanded query with synonyms and aliases
        """
        if not self.term_extractor:
            return query

        # First, check for multi-word canonical terms in the query
        # This handles cases like "Soviet Union" -> add "USSR"
        query_lower = query.lower()
        for canonical_lower, aliases in self.term_extractor.reverse_alias_mapping.items():
            if canonical_lower in query_lower:
                # Found a canonical term, add its aliases
                original_canonical = self.term_extractor._get_original_term(canonical_lower)
                all_variants = [original_canonical] + aliases
                variant_clause = " OR ".join(f'"{v}"' for v in all_variants)
                # Replace the canonical term with the OR clause
                query = query.replace(original_canonical, f"({variant_clause})")
                query = query.replace(canonical_lower, f"({variant_clause})")

        # Then do word-by-word expansion for synonyms and single-word aliases
        words = query.split()
        expanded_parts = []

        for word in words:
            # Skip if already expanded (contains parentheses)
            if '(' in word or ')' in word:
                expanded_parts.append(word)
                continue

            # Clean word (remove punctuation for matching)
            clean_word = word.strip('.,!?;:')

            # Get synonyms for this word
            synonyms = self.term_extractor.get_synonyms_for_query(clean_word)

            # Check if it's a single-word alias (e.g., "USSR", "UN", "IMT")
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

    def _apply_filters(self, results: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """
        Apply filters to search results in Python (safer than SQL WHERE).

        This avoids SQLite cursor recursion issues while providing the same
        filtering functionality.

        Args:
            results: Raw search results from txtai
            filters: Filter parameters (source, author, date_range, etc.)

        Returns:
            Filtered list of results
        """
        filtered = []

        for result in results:
            # Source filter
            if filters.get('source'):
                if result.get('source') != filters['source']:
                    continue

            # Author filter (word-based matching with boundaries)
            author_filter = filters.get('author')
            if author_filter and author_filter.strip():
                author = result.get('author')
                if not author or not isinstance(author, str):
                    continue

                # Split filter into words and check each appears as whole word
                filter_words = author_filter.split()
                author_lower = author.lower()

                # All filter words must appear as whole words in author field
                all_words_match = all(
                    re.search(r'\b' + re.escape(word.lower()) + r'\b', author_lower)
                    for word in filter_words
                )

                if not all_words_match:
                    continue

            # Year filter
            if filters.get('published_year'):
                if result.get('published_year') != int(filters['published_year']):
                    continue

            # Word count filter
            if filters.get('min_word_count'):
                word_count = result.get('word_count', 0)
                if word_count < int(filters['min_word_count']):
                    continue

            # Date range filters
            if not self._matches_date_filter(result, filters):
                continue

            # Passed all filters
            filtered.append(result)

        return filtered

    def _matches_date_filter(self, result: Dict, filters: Dict[str, Any]) -> bool:
        """
        Check if result matches date filter criteria.

        Supports:
        - Date range presets: past_week, past_month, past_3months, past_year
        - Decade ranges: 2020s, 2010s, 2000s, 1990s
        - Custom ranges: start_date, end_date

        Args:
            result: Search result with published_date
            filters: Filter parameters

        Returns:
            True if matches date filter (or no date filter), False otherwise
        """
        date_range = filters.get('date_range', '').lower()
        published_date_str = result.get('published_date')

        # No date filter
        if not date_range and not filters.get('start_date') and not filters.get('end_date'):
            return True

        # Parse published date
        if not published_date_str:
            return False

        try:
            # Parse ISO format date
            if isinstance(published_date_str, str):
                pub_date = datetime.fromisoformat(published_date_str.replace('Z', '+00:00'))
                if pub_date.tzinfo is not None:
                    pub_date = pub_date.replace(tzinfo=None)
            else:
                pub_date = published_date_str
                if hasattr(pub_date, 'tzinfo') and pub_date.tzinfo is not None:
                    pub_date = pub_date.replace(tzinfo=None)
        except (ValueError, AttributeError):
            return False

        # Date range presets
        now = datetime.now()

        if date_range == 'past_week':
            cutoff = now - timedelta(days=7)
            return pub_date >= cutoff
        elif date_range == 'past_month':
            cutoff = now - timedelta(days=30)
            return pub_date >= cutoff
        elif date_range == 'past_3months':
            cutoff = now - timedelta(days=90)
            return pub_date >= cutoff
        elif date_range == 'past_year':
            cutoff = now - timedelta(days=365)
            return pub_date >= cutoff

        # Decade ranges (use published_year from result)
        published_year = result.get('published_year')
        if date_range == '2020s':
            return published_year >= 2020 and published_year <= 2029
        elif date_range == '2010s':
            return published_year >= 2010 and published_year <= 2019
        elif date_range == '2000s':
            return published_year >= 2000 and published_year <= 2009
        elif date_range == '1990s':
            return published_year >= 1990 and published_year <= 1999

        # Custom date range
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')

        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                return start <= pub_date <= end
            except ValueError:
                return False
        elif start_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                return pub_date >= start
            except ValueError:
                return False
        elif end_date:
            try:
                end = datetime.strptime(end_date, '%Y-%m-%d')
                return pub_date <= end
            except ValueError:
                return False

        return True

    def _execute_txtai_search(
        self,
        query: str,
        limit: int
    ) -> List:
        """
        Execute txtai hybrid search (semantic only, no content storage).

        With content=False, txtai only stores embeddings - no SQL database.
        We use the Python API instead of SQL queries.

        Thread-safe read operation.
        """
        # With content=False, use Python API (not SQL)
        # txtai doesn't have an internal database to query
        # Returns list of tuples: (id, score)
        results = self.embeddings.search(query, limit)

        # Fetch lightweight metadata for filtering (no full content)
        # This is MUCH faster than fetching full content for all 8000 results
        enriched_results = self._enrich_with_filter_metadata(results)

        return enriched_results
        
    def _search_database_for_phrases(
        self,
        exact_phrases: List[str] = None,
        title_phrases: List[str] = None,
        filters: Dict[str, Any] = None,
        limit: Optional[int] = 8000
    ) -> List[Dict]:
        """
        Search database directly for documents matching phrases and/or filters.

        This bypasses semantic search for pure phrase/filter queries to ensure
        ALL matching documents are found, not just semantically similar ones.

        Args:
            exact_phrases: Phrases that must appear in content or title
            title_phrases: Phrases that must appear in title only
            filters: Optional filters (author, source, date) to apply in SQL
            limit: Maximum results (None for unlimited)

        Returns:
            List of result dicts with metadata (no content yet)
        """
        self.connect_db()
        cursor = self.db_conn.cursor()
        
        conditions = []
        params = []
        
        # Exact phrase conditions (must appear in content OR title)
        if exact_phrases:
            for phrase in exact_phrases:
                conditions.append("(LOWER(a.content) LIKE ? ESCAPE '\\' OR LOWER(a.title) LIKE ? ESCAPE '\\')")
                escaped_phrase = phrase.lower().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                pattern = f"%{escaped_phrase}%"
                params.extend([pattern, pattern])
        
        # Title phrase conditions (must appear in title)
        if title_phrases:
            for phrase in title_phrases:
                conditions.append("LOWER(a.title) LIKE ? ESCAPE '\\'")
                escaped_phrase = phrase.lower().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                params.append(f"%{escaped_phrase}%")
        
        # Apply filters directly in SQL for efficiency
        if filters:
            # Author filter
            if filters.get('author'):
                # Use LIKE for partial matching (e.g., "Alan Woods" matches "Alan Woods and John Smith")
                author = filters['author'].replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                conditions.append("LOWER(a.author) LIKE ? ESCAPE '\\'")
                params.append(f"%{author.lower()}%")
            
            # Source filter
            if filters.get('source'):
                conditions.append("a.source = ?")
                params.append(filters['source'])
            
            # Date range filters
            date_range = filters.get('date_range', '').lower()
            if date_range == 'past_week':
                conditions.append("a.published_date >= date('now', '-7 days')")
            elif date_range == 'past_month':
                conditions.append("a.published_date >= date('now', '-30 days')")
            elif date_range == 'past_3months':
                conditions.append("a.published_date >= date('now', '-90 days')")
            elif date_range == 'past_year':
                conditions.append("a.published_date >= date('now', '-365 days')")
            elif date_range == '2020s':
                conditions.append("CAST(strftime('%Y', a.published_date) AS INTEGER) BETWEEN 2020 AND 2029")
            elif date_range == '2010s':
                conditions.append("CAST(strftime('%Y', a.published_date) AS INTEGER) BETWEEN 2010 AND 2019")
            elif date_range == '2000s':
                conditions.append("CAST(strftime('%Y', a.published_date) AS INTEGER) BETWEEN 2000 AND 2009")
            elif date_range == '1990s':
                conditions.append("CAST(strftime('%Y', a.published_date) AS INTEGER) BETWEEN 1990 AND 1999")
            
            # Custom date range
            if filters.get('start_date'):
                conditions.append("a.published_date >= ?")
                params.append(filters['start_date'])
            if filters.get('end_date'):
                conditions.append("a.published_date <= ?")
                params.append(filters['end_date'])
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Build query with optional LIMIT
        query = f"""
            SELECT
                a.id as article_id,
                a.title,
                a.url,
                a.source,
                a.author,
                a.published_date,
                a.word_count,
                a.terms_json as terms,
                a.tags_json as tags,
                CAST(strftime('%Y', a.published_date) AS INTEGER) as published_year,
                CAST(strftime('%m', a.published_date) AS INTEGER) as published_month,
                a.is_chunked,
                a.id as id
            FROM articles a
            WHERE {where_clause} AND a.indexed = 1
            ORDER BY a.published_date DESC
        """

        # Only add LIMIT if specified
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            # Format ID as txtai string format for compatibility with _enrich_with_content()
            article_id = row['article_id']
            txtai_id = f"a_{article_id}"

            result = {
                'id': txtai_id,
                'article_id': article_id,
                'title': row['title'],
                'url': row['url'],
                'source': row['source'],
                'author': row['author'],
                'published_date': row['published_date'],
                'published_year': row['published_year'],
                'published_month': row['published_month'],
                'word_count': row['word_count'],
                'is_chunk': False,
                'chunk_index': 0,
                'tags': row['tags'],
                'terms': row['terms'],
                'score': 1.0,
                'text': None
            }
            results.append(result)
        
        logger.info(f"Database search found {len(results)} matches (filters applied in SQL)")
        return results

    def _score_results_semantically(
        self,
        results: List[Dict],
        query: str
    ) -> List[Dict]:
        """
        Score an arbitrary list of results semantically against a query.

        This is used for pure phrase queries where we fetch ALL matching articles
        from the database, then rank them by semantic relevance instead of by date.

        Args:
            results: List of results from database search (no scores yet)
            query: Query string to score against

        Returns:
            Results with updated semantic scores, sorted by score descending
        """
        if not results or not query:
            return results

        logger.info(f"Scoring {len(results)} database results semantically against query: '{query}'")

        # Fetch content for all results
        results_with_content = self._enrich_with_content(results)

        # Build list of texts to score (title + content for each result)
        texts_to_score = []
        result_indices = []  # Track which result each text belongs to

        for i, result in enumerate(results_with_content):
            title = result.get('title', '')
            content = result.get('text', '')

            # Combine title and content for scoring
            full_text = f"{title} {content}".strip()

            if full_text:
                texts_to_score.append(full_text)
                result_indices.append(i)

        if not texts_to_score:
            logger.warning("No content to score semantically")
            return results

        # Compute semantic similarity scores using txtai
        # similarity() returns a list of scores in the same order as texts
        try:
            scores = self.embeddings.similarity(query, texts_to_score)
            logger.debug(f"Computed {len(scores)} semantic similarity scores")
        except Exception as e:
            logger.error(f"Semantic scoring failed: {e}")
            # Fall back to original results without semantic scores
            return results

        # Update scores in results
        for score, result_idx in zip(scores, result_indices):
            results_with_content[result_idx]['score'] = float(score)

        # Sort by semantic score (descending)
        sorted_results = sorted(results_with_content, key=lambda x: x.get('score', 0.0), reverse=True)

        logger.info(f"Semantically scored and sorted {len(sorted_results)} results")
        return sorted_results

    def _enrich_with_filter_metadata(self, results: List) -> List[Dict]:
        """
        Enrich txtai results with lightweight metadata for filtering.

        This fetches ONLY the fields needed for filtering, not full content.
        Full content is fetched later for only the final paginated results.

        Args:
            results: List of tuples (id, score) from txtai with content=False

        Returns:
            List of dicts with filter metadata (no content)
        """
        if not results:
            return []

        self.connect_db()

        enriched = []

        # With content=False, txtai returns tuples: (id, score)
        # IDs are now strings like "a_12345" or "c_12345_0"
        txtai_ids = [r[0] for r in results]  # r[0] is the string id
        score_map = {r[0]: r[1] for r in results}  # r[0]=id, r[1]=score

        # Parse IDs to determine what to fetch
        article_ids = set()
        chunk_lookups = []  # List of (article_id, chunk_index) tuples

        for txtai_id in txtai_ids:
            parsed = parse_txtai_id(txtai_id)
            if parsed.type == 'article':
                article_ids.add(parsed.article_id)
            else:  # chunk
                chunk_lookups.append((parsed.article_id, parsed.chunk_index))

        cursor = self.db_conn.cursor()

        # Fetch article metadata for non-chunked articles
        if article_ids:
            placeholders = ','.join('?' * len(article_ids))
            query = f"""
                SELECT
                    a.id as article_id,
                    a.title,
                    a.url,
                    a.source,
                    a.author,
                    a.published_date,
                    a.word_count,
                    a.terms_json as terms,
                    a.tags_json as tags,
                    CAST(strftime('%Y', a.published_date) AS INTEGER) as published_year,
                    CAST(strftime('%m', a.published_date) AS INTEGER) as published_month
                FROM articles a
                WHERE a.id IN ({placeholders})
            """
            cursor.execute(query, list(article_ids))

            for row in cursor.fetchall():
                txtai_id = f"a_{row['article_id']}"
                result = {
                    'id': txtai_id,
                    'article_id': row['article_id'],
                    'title': row['title'],
                    'url': row['url'],
                    'source': row['source'],
                    'author': row['author'],
                    'published_date': row['published_date'],
                    'published_year': row['published_year'],
                    'published_month': row['published_month'],
                    'word_count': row['word_count'],
                    'is_chunk': False,
                    'chunk_index': 0,
                    'tags': row['tags'],
                    'terms': row['terms'],
                    'score': score_map.get(txtai_id, 0.0),
                    'text': None  # No content yet - will be fetched later if needed
                }
                enriched.append(result)

        # Fetch chunk metadata
        if chunk_lookups:
            # Query chunks with their parent article metadata
            for article_id, chunk_index in chunk_lookups:
                query = """
                    SELECT
                        a.id as article_id,
                        a.title,
                        a.url,
                        a.source,
                        a.author,
                        a.published_date,
                        CAST(strftime('%Y', a.published_date) AS INTEGER) as published_year,
                        CAST(strftime('%m', a.published_date) AS INTEGER) as published_month,
                        a.terms_json as terms,
                        a.tags_json as tags,
                        ac.word_count,
                        ac.chunk_index
                    FROM articles a
                    JOIN article_chunks ac ON ac.article_id = a.id
                    WHERE a.id = ? AND ac.chunk_index = ?
                """
                cursor.execute(query, (article_id, chunk_index))
                row = cursor.fetchone()

                if row:
                    txtai_id = f"c_{article_id}_{chunk_index}"
                    result = {
                        'id': txtai_id,
                        'article_id': row['article_id'],
                        'title': row['title'],
                        'url': row['url'],
                        'source': row['source'],
                        'author': row['author'],
                        'published_date': row['published_date'],
                        'published_year': row['published_year'],
                        'published_month': row['published_month'],
                        'word_count': row['word_count'],
                        'is_chunk': True,
                        'chunk_index': row['chunk_index'],
                        'tags': row['tags'],
                        'terms': row['terms'],
                        'score': score_map.get(txtai_id, 0.0),
                        'text': None  # No content yet - will be fetched later if needed
                    }
                    enriched.append(result)

        logger.debug(f"Enriched {len(enriched)} results with filter metadata (no content)")

        return enriched

    def _enrich_with_content(self, results: List[Dict]) -> List[Dict]:
        """
        Enrich results with full content from articles.db.

        This is called AFTER filtering/deduplication/pagination, so we only
        fetch content for the small set of final results (e.g., 10-50 articles)
        instead of all 8000 initial results.

        Args:
            results: List of result dicts that already have metadata but no content

        Returns:
            Same results enriched with 'text' field from articles.db
        """
        if not results:
            return []

        self.connect_db()

        # Parse IDs to determine what to fetch
        article_ids = set()
        chunk_lookups = []  # List of (txtai_id, article_id, chunk_index) tuples

        for result in results:
            txtai_id = result.get('id')
            if not txtai_id:
                continue

            parsed = parse_txtai_id(txtai_id)
            if parsed.type == 'article':
                article_ids.add(parsed.article_id)
            else:  # chunk
                chunk_lookups.append((txtai_id, parsed.article_id, parsed.chunk_index))

        cursor = self.db_conn.cursor()
        content_map = {}

        # Fetch content for non-chunked articles
        if article_ids:
            placeholders = ','.join('?' * len(article_ids))
            query = f"""
                SELECT id, content as text
                FROM articles
                WHERE id IN ({placeholders})
            """
            cursor.execute(query, list(article_ids))

            for row in cursor.fetchall():
                txtai_id = f"a_{row['id']}"
                content_map[txtai_id] = row['text']

        # Fetch content for chunks
        for txtai_id, article_id, chunk_index in chunk_lookups:
            query = """
                SELECT content as text
                FROM article_chunks
                WHERE article_id = ? AND chunk_index = ?
            """
            cursor.execute(query, (article_id, chunk_index))
            row = cursor.fetchone()

            if row:
                content_map[txtai_id] = row['text']

        # Add content to results
        for result in results:
            result['text'] = content_map.get(result['id'], '')

        logger.debug(f"Enriched {len(results)} final results with content")

        return results

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """
        Deduplicate results by article_id.

        When multiple chunks from the same article match:
        - Keep only the highest-scoring chunk
        - Track how many chunks matched (matched_sections)
        """
        article_groups = defaultdict(list)

        # Group results by article_id (extract from string ID)
        for result in results:
            # Extract article_id from string txtai ID
            txtai_id = result.get('id')
            if txtai_id and isinstance(txtai_id, str):
                article_id = extract_article_id(txtai_id)
            else:
                # Fallback to article_id field if available
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
        - < 7 days: +0.07
        - < 30 days: +0.05
        - < 90 days: +0.03
        - < 1 year: +0.02
        - < 3 years: +0.01
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
                if age_days < 7:
                    boost = self.recency_boosts['7_days']
                elif age_days < 30:
                    boost = self.recency_boosts['30_days']
                elif age_days < 90:
                    boost = self.recency_boosts['90_days']
                elif age_days < 365:
                    boost = self.recency_boosts['1_year']
                elif age_days < 365 * 3:
                    boost = self.recency_boosts['3_years']

                if boost > 0:
                    result['original_score'] = result['score']
                    result['score'] = result['score'] + boost
                    result['recency_boost'] = boost

            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse date '{published_date}': {e}")
                continue

        return results

    def _apply_title_term_boost(self, results: List[Dict], query_terms: List[str]) -> List[Dict]:
        """
        Boost results where query terms appear in the title.
        
        This is essentially free since title is already in result metadata.
        Rewards "obvious" matches where the query directly matches the title.
        
        Args:
            results: Deduplicated search results
            query_terms: Parsed query terms (semantic_terms from parser)
            
        Returns:
            Results with title boost applied to scores
        """
        if not query_terms:
            return results
        
        max_boost = RERANKING_CONFIG['title_boost_max']
        
        for result in results:
            title_lower = result.get('title', '').lower()
            
            # Count how many query terms appear in title (whole word match)
            terms_in_title = sum(
                1 for term in query_terms 
                if re.search(r'\b' + re.escape(term.lower()) + r'\b', title_lower)
            )
            
            if terms_in_title > 0:
                # Boost based on coverage (what % of query terms are in title)
                coverage = terms_in_title / len(query_terms)
                boost = max_boost * coverage
                result['title_boost'] = round(boost, 4)
                result['score'] += boost
        
        return results

    def _apply_keyword_boost(self, results: List[Dict], query_terms: List[str]) -> List[Dict]:
        """
        Apply lightweight keyword frequency boost to top candidates.
        
        Fetches content for top N results only, applies log-scaled term 
        frequency scoring (pseudo-BM25), then re-sorts. This catches cases
        where semantically similar but keyword-sparse results outrank
        documents that actually contain the query terms frequently.
        
        Args:
            results: Results after deduplication (sorted by semantic score)
            query_terms: Parsed query terms
            
        Returns:
            Results with keyword boost applied and re-sorted
        """
        if not query_terms or not results:
            return results
        
        top_n = RERANKING_CONFIG['keyword_rerank_top_n']
        max_boost = RERANKING_CONFIG['keyword_boost_max']
        scale = RERANKING_CONFIG['keyword_boost_scale']
        
        # Split into top candidates (to rerank) and tail (keep as-is)
        top_candidates = results[:top_n]
        tail = results[top_n:]
        
        # Fetch content for top candidates only
        top_with_content = self._enrich_with_content(top_candidates)
        
        # Apply term frequency boost
        for result in top_with_content:
            content = result.get('text', '').lower()
            if not content:
                continue
            
            total_tf_score = 0
            for term in query_terms:
                # Count occurrences (whole word matching)
                pattern = r'\b' + re.escape(term.lower()) + r'\b'
                count = len(re.findall(pattern, content))
                
                # Log-scaled TF (diminishing returns after ~10 mentions)
                if count > 0:
                    import math
                    tf = 1 + math.log(1 + count)
                    total_tf_score += tf
            
            # Normalize by number of query terms
            avg_tf = total_tf_score / len(query_terms)
            
            # Scale to configured max boost
            boost = min(max_boost, avg_tf * scale)
            result['keyword_boost'] = round(boost, 4)
            result['score'] += boost
        
        # Re-sort top candidates by new combined score
        top_with_content.sort(key=lambda x: x['score'], reverse=True)
        
        # Combine: reranked top + unchanged tail
        return top_with_content + tail

    def _ensure_content(self, results: List[Dict]) -> List[Dict]:
        """
        Fetch content only for results that don't already have it.
        
        Avoids double-fetching for results that went through keyword boost.
        
        Args:
            results: Results, some may already have 'text' field
            
        Returns:
            All results with 'text' field populated
        """
        needs_content = [r for r in results if not r.get('text')]
        
        if needs_content:
            enriched = self._enrich_with_content(needs_content)
            enriched_map = {r['id']: r for r in enriched}
            for r in needs_content:
                if r['id'] in enriched_map:
                    r['text'] = enriched_map[r['id']].get('text', '')
        
        return results

    def _format_results(
        self,
        results: List[Dict],
        query: str,
        exact_phrases: List[str] = None
    ) -> List[Dict]:
        """
        Format results with excerpts and clean metadata.

        Creates smart excerpts that include matched exact phrases.

        Returns list of formatted result dictionaries.
        """
        formatted = []

        for result in results:
            # Extract content for excerpt
            content = result.get('text', '')
            if not content:
                content = result.get('content', '')

            title = result.get('title', '')

            # Create smart excerpt that shows matched phrase if available
            excerpt, matched_phrase = self._create_smart_excerpt(
                content,
                title,
                exact_phrases or []
            )

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
                'matched_phrase': matched_phrase,  # For frontend highlighting
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

    def _create_smart_excerpt(
        self,
        content: str,
        title: str,
        exact_phrases: List[str],
        excerpt_length: int = 200,
        context_chars: int = 100
    ) -> tuple[str, str | None]:
        """
        Create smart excerpt that includes the first matched exact phrase.

        Uses whole-word matching with regex to avoid matching substrings
        (e.g., "labor" won't match "elaborate").

        If an exact phrase is found in the content, creates an excerpt centered
        around that phrase. Prefers matches in the article body over title, but
        will use title matches if that's the only occurrence. Otherwise, returns
        the first 200 characters.

        Args:
            content: Full article content
            title: Article title
            exact_phrases: List of exact phrases to look for
            excerpt_length: Target excerpt length
            context_chars: Characters of context before/after match

        Returns:
            Tuple of (excerpt, matched_phrase) where matched_phrase is None
            if no phrase was found in content
        """
        if not content:
            return '', None

        content_lower = content.lower()
        title_lower = title.lower()

        # Try each exact phrase with whole-word matching
        for phrase in exact_phrases:
            phrase_lower = phrase.lower()

            # Use regex with word boundaries for whole-word matching
            pattern = r'\b' + re.escape(phrase_lower) + r'\b'
            match = re.search(pattern, content_lower)

            if not match:
                continue

            pos = match.start()

            # Check if this match is in the title portion that appears in content
            # If so, try to find a match in the actual body for a better excerpt
            title_in_content_pos = content_lower.find(title_lower)
            if title_in_content_pos != -1:
                title_end_pos = title_in_content_pos + len(title_lower)
                # If match is within title portion, prefer a body occurrence if available
                if pos < title_end_pos:
                    # Look for the phrase after the title for a better excerpt
                    match_after_title = re.search(pattern, content_lower[title_end_pos:])
                    if match_after_title:
                        # Found in body too - use that for better context
                        pos = title_end_pos + match_after_title.start()
                    # If not found after title, still use the title occurrence (don't skip!)

            # Found a match! Create excerpt around it
            start = max(0, pos - context_chars)
            end = min(len(content), pos + len(phrase) + context_chars)

            excerpt = content[start:end].strip()

            # Add ellipsis if needed
            if start > 0:
                excerpt = '...' + excerpt
            if end < len(content):
                excerpt = excerpt + '...'

            return excerpt, phrase

        # No exact phrase found in content, return default excerpt
        excerpt = content[:excerpt_length]
        if len(content) > excerpt_length:
            excerpt += '...'
        return excerpt.strip(), None

    def _filter_by_exact_phrases(
        self,
        results: List[Dict],
        exact_phrases: List[str]
    ) -> List[Dict]:
        """
        Filter results to only those containing ALL exact phrases.

        Uses whole-word regex matching to avoid false positives
        (e.g., "labor" won't match "elaborate").

        Security: Done in Python, no SQL injection possible.

        Args:
            results: Results to filter
            exact_phrases: List of phrases that must match exactly

        Returns:
            Filtered results
        """
        if not exact_phrases:
            return results

        if not results:
            return []

        self.connect_db()

        # Parse IDs to determine what to fetch
        article_ids = set()
        chunk_lookups = []  # List of (txtai_id, article_id, chunk_index) tuples

        for result in results:
            txtai_id = result.get('id')
            if not txtai_id:
                continue

            parsed = parse_txtai_id(txtai_id)
            if parsed.type == 'article':
                article_ids.add(parsed.article_id)
            else:  # chunk
                chunk_lookups.append((txtai_id, parsed.article_id, parsed.chunk_index))

        cursor = self.db_conn.cursor()
        content_map = {}

        # Fetch content for non-chunked articles
        if article_ids:
            placeholders = ','.join('?' * len(article_ids))
            query = f"""
                SELECT id, title, content
                FROM articles
                WHERE id IN ({placeholders})
            """
            cursor.execute(query, list(article_ids))

            for row in cursor.fetchall():
                txtai_id = f"a_{row['id']}"
                full_text = f"{row['title'] or ''} {row['content'] or ''}"
                content_map[txtai_id] = full_text.lower()

        # Fetch content for chunks
        for txtai_id, article_id, chunk_index in chunk_lookups:
            query = """
                SELECT a.title, ac.content
                FROM articles a
                JOIN article_chunks ac ON ac.article_id = a.id
                WHERE a.id = ? AND ac.chunk_index = ?
            """
            cursor.execute(query, (article_id, chunk_index))
            row = cursor.fetchone()

            if row:
                full_text = f"{row['title'] or ''} {row['content'] or ''}"
                content_map[txtai_id] = full_text.lower()

        # Filter results that contain ALL exact phrases (whole-word matching)
        filtered = []
        for result in results:
            result_id = result.get('id')
            content = content_map.get(result_id, '').lower()

            if not content:
                # If no content found in map, skip this result
                logger.debug(f"No content found for result id {result_id}")
                continue

            # Check if ALL phrases are present as whole words/phrases
            all_present = True
            for phrase in exact_phrases:
                # Use regex with word boundaries for whole-word matching
                pattern = r'\b' + re.escape(phrase.lower()) + r'\b'
                if not re.search(pattern, content):
                    all_present = False
                    break

            if all_present:
                filtered.append(result)

        logger.debug(f"Exact phrase filter: {len(results)} -> {len(filtered)} results")
        return filtered

    def _filter_by_title_phrases(
        self,
        results: List[Dict],
        title_phrases: List[str]
    ) -> List[Dict]:
        """
        Filter results to only those with titles containing ALL specified phrases.

        Security: Done in Python, no SQL injection possible.

        Args:
            results: Results to filter
            title_phrases: List of phrases that must appear in title

        Returns:
            Filtered results
        """
        if not title_phrases:
            return results

        # Filter by checking title field (already in results)
        filtered = []
        for result in results:
            title = result.get('title', '').lower()

            # Check if ALL title phrases are present
            all_present = all(
                phrase.lower() in title
                for phrase in title_phrases
            )

            if all_present:
                filtered.append(result)

        return filtered

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
