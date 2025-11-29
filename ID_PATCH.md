# ID System & Embedding Model Patch

## Overview

This patch fixes the incremental indexing bug and upgrades the embedding model. Apply these changes in order.

## Prerequisites

Two files have already been created and should be placed in the codebase:

1. **`src/common/__init__.py`** — Empty init file
2. **`src/common/id_utils.py`** — String ID utilities (already complete)
3. **`config/search_config.py`** — Updated config (already complete, replace existing)

## Core Changes

### 1. New ID Scheme

All txtai documents now use string IDs:

```python
from src.common.id_utils import make_article_id, make_chunk_id, parse_txtai_id, extract_article_id

# Articles: "a_{article_id}"
txtai_id = make_article_id(12345)  # "a_12345"

# Chunks: "c_{article_id}_{chunk_index}"  
txtai_id = make_chunk_id(12345, 0)  # "c_12345_0"
```

### 2. Nomic Model Task Prefixes (CRITICAL)

The new model requires prefixes for proper embedding alignment:

```python
from config.search_config import EMBEDDING_PREFIX_DOCUMENT, EMBEDDING_PREFIX_QUERY

# When INDEXING documents:
text_to_embed = EMBEDDING_PREFIX_DOCUMENT + content  # "search_document: <content>"

# When SEARCHING:
query_to_embed = EMBEDDING_PREFIX_QUERY + query  # "search_query: <query>"
```

---

## File: `src/indexing/indexing_service.py`

### Changes Required

**1. Add imports at top:**
```python
from src.common.id_utils import make_article_id, make_chunk_id
from config.search_config import EMBEDDING_PREFIX_DOCUMENT
```

**2. Update `_prepare_article_document()` method:**

- Change `'id': article['id']` to `'id': make_article_id(article['id'])`
- Prepend `EMBEDDING_PREFIX_DOCUMENT` to the content field

```python
def _prepare_article_document(self, article: Dict) -> Dict:
    title = article['title']
    content = article['content']
    
    # Weight title by repeating it before content
    title_prefix = (title + ". ") * TITLE_WEIGHT_MULTIPLIER
    weighted_content = title_prefix + content
    
    # Add nomic task prefix for proper embedding
    prefixed_content = EMBEDDING_PREFIX_DOCUMENT + weighted_content

    return {
        'id': make_article_id(article['id']),  # CHANGED: String ID
        'article_id': article['id'],
        'content': prefixed_content,  # CHANGED: With prefix
        # ... rest unchanged
    }
```

**3. Update `_prepare_chunk_document()` method:**

- Change signature: remove `txtai_id` parameter, compute internally
- Use `make_chunk_id(article['id'], chunk['chunk_index'])`
- Prepend `EMBEDDING_PREFIX_DOCUMENT` to content

```python
def _prepare_chunk_document(self, chunk: Dict, article: Dict) -> Dict:
    title = article['title']
    content = chunk['content']
    chunk_index = chunk['chunk_index']

    # Only prepend title to FIRST chunk
    if chunk_index == 0:
        title_prefix = (title + ". ") * TITLE_WEIGHT_MULTIPLIER
        weighted_content = title_prefix + content
    else:
        weighted_content = content
    
    # Add nomic task prefix
    prefixed_content = EMBEDDING_PREFIX_DOCUMENT + weighted_content

    return {
        'id': make_chunk_id(article['id'], chunk_index),  # CHANGED: String ID
        'article_id': article['id'],
        'content': prefixed_content,  # CHANGED: With prefix
        # ... rest unchanged
    }
```

**4. Simplify `build_index()` and `update_index()` loops:**

Remove all `next_chunk_id` tracking. The chunk ID is now deterministic from article_id + chunk_index.

```python
# OLD (remove this pattern):
next_chunk_id = ...
for chunk in chunks:
    chunk_doc = self._prepare_chunk_document(chunk, article, next_chunk_id)
    next_chunk_id += 1

# NEW:
for chunk in chunks:
    chunk_doc = self._prepare_chunk_document(chunk, article)
    all_documents.append(chunk_doc)
```

**5. Remove `_get_next_chunk_id()` method entirely** — no longer needed.

**6. Simplify `_save_chunks()` method:**

No longer needs to return IDs. Just save chunks to database.

```python
def _save_chunks(self, chunks: List[Dict]):
    """Save chunks to database."""
    conn = self.db.connect()
    cursor = conn.cursor()
    for chunk in chunks:
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
    conn.commit()
```

---

## File: `src/search/search_engine.py`

### Changes Required

**1. Add imports at top:**
```python
from src.common.id_utils import (
    parse_txtai_id, 
    extract_article_id, 
    is_chunk_id,
    ParsedChunkId
)
from config.search_config import EMBEDDING_PREFIX_QUERY
```

**2. Update `_execute_txtai_search()` method:**

Prepend query prefix before searching:

```python
def _execute_txtai_search(self, query: str, limit: int) -> List:
    # Add nomic task prefix for proper embedding alignment
    prefixed_query = EMBEDDING_PREFIX_QUERY + query
    
    results = self.embeddings.search(prefixed_query, limit)
    # ... rest of method
```

**3. Update `_enrich_with_filter_metadata()` method:**

Parse string IDs and separate articles from chunks:

```python
def _enrich_with_filter_metadata(self, results: List) -> List[Dict]:
    if not results:
        return []

    self.connect_db()
    enriched = []
    
    # Separate article IDs from chunk info
    article_ids = []
    chunk_lookups = []  # List of (article_id, chunk_index)
    score_map = {}
    
    for r in results:
        txtai_id = r[0]  # String ID now
        score = r[1]
        score_map[txtai_id] = score
        
        parsed = parse_txtai_id(txtai_id)
        if parsed.type == 'article':
            article_ids.append(parsed.article_id)
        else:  # chunk
            chunk_lookups.append((parsed.article_id, parsed.chunk_index))

    cursor = self.db_conn.cursor()
    
    # Fetch non-chunked articles
    if article_ids:
        placeholders = ','.join('?' * len(article_ids))
        cursor.execute(f"""
            SELECT id, title, url, source, author, published_date, word_count,
                   terms_json, tags_json,
                   CAST(strftime('%Y', published_date) AS INTEGER) as published_year,
                   CAST(strftime('%m', published_date) AS INTEGER) as published_month
            FROM articles WHERE id IN ({placeholders})
        """, article_ids)
        
        for row in cursor.fetchall():
            txtai_id = f"a_{row['id']}"
            enriched.append({
                'id': txtai_id,
                'article_id': row['id'],
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
                'tags': row['tags_json'],
                'terms': row['terms_json'],
                'score': score_map.get(txtai_id, 0.0),
                'text': None
            })
    
    # Fetch chunks (need to join with articles for metadata)
    if chunk_lookups:
        # Build query for all chunks
        conditions = ' OR '.join(
            f'(ac.article_id = ? AND ac.chunk_index = ?)' 
            for _ in chunk_lookups
        )
        params = [val for pair in chunk_lookups for val in pair]
        
        cursor.execute(f"""
            SELECT ac.article_id, ac.chunk_index, ac.word_count as chunk_word_count,
                   a.title, a.url, a.source, a.author, a.published_date, 
                   a.word_count, a.terms_json, a.tags_json,
                   CAST(strftime('%Y', a.published_date) AS INTEGER) as published_year,
                   CAST(strftime('%m', a.published_date) AS INTEGER) as published_month
            FROM article_chunks ac
            JOIN articles a ON ac.article_id = a.id
            WHERE {conditions}
        """, params)
        
        for row in cursor.fetchall():
            txtai_id = f"c_{row['article_id']}_{row['chunk_index']}"
            enriched.append({
                'id': txtai_id,
                'article_id': row['article_id'],
                'title': row['title'],
                'url': row['url'],
                'source': row['source'],
                'author': row['author'],
                'published_date': row['published_date'],
                'published_year': row['published_year'],
                'published_month': row['published_month'],
                'word_count': row['chunk_word_count'] or row['word_count'],
                'is_chunk': True,
                'chunk_index': row['chunk_index'],
                'tags': row['tags_json'],
                'terms': row['terms_json'],
                'score': score_map.get(txtai_id, 0.0),
                'text': None
            })

    return enriched
```

**4. Update `_enrich_with_content()` method:**

Similar pattern — parse string IDs, fetch content separately for articles vs chunks.

**5. Update `_filter_by_exact_phrases()` method:**

Same pattern — parse string IDs when fetching content for filtering.

**6. Update `_deduplicate_results()` method:**

Use `extract_article_id()` for grouping:

```python
def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
    article_groups = defaultdict(list)

    for result in results:
        # Use the string ID to extract article_id
        article_id = extract_article_id(result['id'])
        article_groups[article_id].append(result)

    # ... rest unchanged (keep highest scoring per article)
```

---

## File: `src/indexing/txtai_manager.py`

### Changes Required

**1. Verify config is imported:**
```python
from config.search_config import TXTAI_CONFIG
```

**2. No other changes needed** — txtai handles string IDs natively.

---

## File: `src/indexing/chunking.py`

### No Changes Required

The chunking module reads from `CHUNKING_CONFIG` which is already updated in the new config file. The new thresholds (5500/2000/300) will be used automatically.

---
