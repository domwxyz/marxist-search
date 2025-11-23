"""
MODIFICATIONS TO backend/src/search/search_engine.py

Add these imports at the top:
"""
from ..query_parser import QueryParser, ParsedQuery

"""
Add this to SearchEngine.__init__:
"""
# Initialize query parser for power-user syntax
self.query_parser = QueryParser()

"""
REPLACE the search() method with this enhanced version:
"""

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
    
    # Expand query with synonyms if enabled
    original_query = semantic_query
    if self.enable_query_expansion and self.term_extractor and semantic_query:
        try:
            expanded = self._expand_query(semantic_query)
            if expanded != semantic_query:
                logger.info(f"Query expanded: '{semantic_query}' -> '{expanded}'")
                semantic_query = expanded
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
    
    logger.info(
        f"Executing search: semantic_query='{semantic_query}', "
        f"filters={filters}, limit={limit}, "
        f"exact_phrases={parsed_query.exact_phrases}, "
        f"title_phrases={parsed_query.title_phrases}"
    )
    
    start_time = datetime.now()
    
    # Execute txtai search (semantic + BM25)
    try:
        raw_results = self._execute_txtai_search(
            query=semantic_query if semantic_query else query,
            limit=8000
        )
        logger.debug(f"txtai returned {len(raw_results)} raw results")
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise
    
    # Apply filters
    if filters:
        filtered_results = self._apply_filters(raw_results, filters)
        logger.debug(f"Filtered {len(raw_results)} -> {len(filtered_results)} results")
    else:
        filtered_results = raw_results
    
    # Apply exact phrase matching (post-filter for security)
    if parsed_query.exact_phrases:
        filtered_results = self._filter_by_exact_phrases(
            filtered_results, 
            parsed_query.exact_phrases
        )
        logger.debug(
            f"Exact phrase filter: {len(filtered_results)} results match "
            f"{len(parsed_query.exact_phrases)} phrases"
        )
    
    # Apply title phrase matching
    if parsed_query.title_phrases:
        filtered_results = self._filter_by_title_phrases(
            filtered_results,
            parsed_query.title_phrases
        )
        logger.debug(
            f"Title phrase filter: {len(filtered_results)} results"
        )
    
    # Deduplicate and rank
    deduplicated = self._deduplicate_results(filtered_results)
    total_count = len(deduplicated)
    
    # Apply recency boosting
    boosted = self._apply_recency_boost(deduplicated)
    
    # Sort by final score
    sorted_results = sorted(boosted, key=lambda x: x['score'], reverse=True)
    
    # Paginate
    paginated = sorted_results[offset:offset + limit]
    
    # Fetch full content for paginated results
    paginated_with_content = self._enrich_with_content(paginated)
    
    # Format results
    formatted = self._format_results(paginated_with_content, query)
    
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


"""
ADD these new helper methods to SearchEngine class:
"""

def _filter_by_exact_phrases(
    self,
    results: List[Dict],
    exact_phrases: List[str]
) -> List[Dict]:
    """
    Filter results to only those containing ALL exact phrases.
    
    Security: Done in Python, no SQL injection possible.
    
    Args:
        results: Results to filter
        exact_phrases: List of phrases that must match exactly
        
    Returns:
        Filtered results
    """
    if not exact_phrases:
        return results
    
    self.connect_db()
    
    # Get content for all results (we need it to check exact matches)
    result_ids = [r['id'] for r in results]
    
    if not result_ids:
        return []
    
    cursor = self.db_conn.cursor()
    placeholders = ','.join('?' * len(result_ids))
    
    # Fetch content for all results
    # Security: Using parameterized query, safe from injection
    query = f"""
        SELECT
            COALESCE(ac.id, a.id) as id,
            COALESCE(ac.content, a.content) as content,
            a.title as title
        FROM articles a
        LEFT JOIN article_chunks ac ON ac.article_id = a.id
        WHERE a.id IN ({placeholders}) OR ac.id IN ({placeholders})
    """
    
    cursor.execute(query, result_ids + result_ids)
    
    # Build content map
    content_map = {}
    for row in cursor.fetchall():
        # Combine title and content for searching
        full_text = f"{row['title']} {row['content']}"
        content_map[row['id']] = full_text.lower()
    
    # Filter results that contain ALL exact phrases
    filtered = []
    for result in results:
        result_id = result.get('id')
        content = content_map.get(result_id, '').lower()
        
        if not content:
            continue
        
        # Check if ALL phrases are present
        all_present = all(
            phrase.lower() in content 
            for phrase in exact_phrases
        )
        
        if all_present:
            filtered.append(result)
    
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
