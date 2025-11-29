# ID System & Embedding Model Patch v2

## Overview

This patch fixes the incremental indexing ID collision bug and upgrades to a longer-context embedding model. The new model is a drop-in replacement requiring no special prefixes or code complexity.

## Model Change

| Property | Old (bge-small-en-v1.5) | New (gte-base-en-v1.5) |
|----------|-------------------------|------------------------|
| Context | 512 tokens (~400 words) | 8192 tokens (~6000 words) |
| Dimensions | 384 | 768 |
| Prefixes | None | None |
| Path | `sentence-transformers/all-MiniLM-L6-v2` or similar | `Alibaba-NLP/gte-base-en-v1.5` |

## Prerequisites

These files should already be in place:
- `src/common/__init__.py` — Empty init file
- `src/common/id_utils.py` — String ID utilities

---

## File: `config/search_config.py`

Update the model path. Find the txtai/embedding config section and change:

```python
# OLD:
"path": "sentence-transformers/bge-small-en-v1.5"  # or whatever current model

# NEW:
"path": "Alibaba-NLP/gte-base-en-v1.5"
```

Also update chunking thresholds to take advantage of longer context:

```python
# OLD chunking config:
CHUNKING_CONFIG = {
    "threshold_words": 3500,
    "chunk_size_words": 1000,
    "overlap_words": 200,
}

# NEW chunking config:
CHUNKING_CONFIG = {
    "threshold_words": 5500,   # Model handles ~6000 words
    "chunk_size_words": 2000,  # Larger chunks now useful
    "overlap_words": 300,      # ~15% overlap
}
```

---

## File: `src/indexing/indexing_service.py`

### Changes Required

**1. Add import at top:**
```python
from src.common.id_utils import make_article_id, make_chunk_id
```

**2. Update `_prepare_article_document()` method:**

Change the ID from integer to string:

```python
# OLD:
return {
    'id': article['id'],
    ...
}

# NEW:
return {
    'id': make_article_id(article['id']),
    ...
}
```

**3. Update `_prepare_chunk_document()` method:**

Remove the `txtai_id` parameter. Compute ID from article_id + chunk_index:

```python
# OLD signature:
def _prepare_chunk_document(self, chunk: Dict, article: Dict, txtai_id: int) -> Dict:
    return {
        'id': txtai_id,
        ...
    }

# NEW signature:
def _prepare_chunk_document(self, chunk: Dict, article: Dict) -> Dict:
    return {
        'id': make_chunk_id(article['id'], chunk['chunk_index']),
        ...
    }
```

**4. Remove `next_chunk_id` tracking from `build_index()` and `update_index()`:**

The chunk ID is now deterministic. Remove all code that:
- Calculates `next_chunk_id`
- Passes `next_chunk_id` to `_prepare_chunk_document()`
- Increments `next_chunk_id`

```python
# OLD pattern (remove):
next_chunk_id = self._get_next_chunk_id()
for chunk in chunks:
    doc = self._prepare_chunk_document(chunk, article, next_chunk_id)
    next_chunk_id += 1

# NEW pattern:
for chunk in chunks:
    doc = self._prepare_chunk_document(chunk, article)
```

**5. Delete `_get_next_chunk_id()` method entirely** — no longer needed.

---

## File: `src/search/search_engine.py`

### Changes Required

**1. Add imports at top:**
```python
from src.common.id_utils import parse_txtai_id, extract_article_id
```

**2. Update result processing to handle string IDs:**

Anywhere you extract an ID from search results and use it for database lookups, parse it first:

```python
# OLD:
article_id = result[0]  # Was integer
cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))

# NEW:
txtai_id = result[0]  # Now string like "a_12345" or "c_12345_0"
parsed = parse_txtai_id(txtai_id)
article_id = parsed.article_id  # Always the integer article ID
cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
```

**3. Update `_deduplicate_results()` to use extract_article_id():**

```python
def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
    article_groups = defaultdict(list)
    
    for result in results:
        # Extract article_id from string ID
        article_id = extract_article_id(result['id'])
        article_groups[article_id].append(result)
    
    # Keep highest scoring result per article
    deduplicated = []
    for article_id, group in article_groups.items():
        best = max(group, key=lambda x: x.get('score', 0))
        deduplicated.append(best)
    
    return deduplicated
```

**4. Update enrichment methods to handle both article and chunk IDs:**

When fetching content/metadata, check if it's a chunk:

```python
parsed = parse_txtai_id(txtai_id)

if parsed.type == 'article':
    # Fetch from articles table
    cursor.execute("SELECT content FROM articles WHERE id = ?", (parsed.article_id,))
else:
    # Fetch from article_chunks table
    cursor.execute("""
        SELECT content FROM article_chunks 
        WHERE article_id = ? AND chunk_index = ?
    """, (parsed.article_id, parsed.chunk_index))
```

---

## File: `src/indexing/txtai_manager.py`

### No Changes Required

The new model path in config will be picked up automatically. txtai handles the model change transparently.

---

## File: `src/indexing/chunking.py`

### No Changes Required

Reads thresholds from config, which is already updated.
