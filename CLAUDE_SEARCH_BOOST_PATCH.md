# Search Engine Boost Refinement Patch

## Overview

This document specifies changes to improve search ranking by introducing:
1. **Exact Phrase Presence Boost** - Binary boost when query phrase literally appears in title/content
2. **Inverse Semantic Confidence Signal** - Boost for high-semantic, low-keyword matches (conceptual discovery)
3. **Semantic Score Distribution Normalization** - Adaptive filtering based on score distribution shape
4. **Diminishing Returns on Length Penalty** - Log-normalization for article length in keyword density

All changes are contained to:
- `backend/config/search_config.py`
- `backend/src/search/search_engine.py`

---

## 1. Exact Phrase Presence Boost

### Purpose
Boost articles where the query (or quoted phrase) appears literally in title or content. Separate from keyword density - this is a binary "phrase exists" signal.

### Config Changes (`search_config.py`)

Add to `RERANKING_CONFIG`:

```python
# Exact phrase presence boost (binary signals, applied before density boost)
# Checks if the full query phrase appears as-is in title or content
"phrase_presence_boost": {
    "enabled": True,
    "phrase_in_title": 0.08,      # Full phrase appears in title
    "phrase_in_content": 0.06,    # Full phrase appears anywhere in content
    "all_terms_in_title": 0.04,   # All query terms in title (not as phrase)
},
```

### Implementation (`search_engine.py`)

**New method: `_apply_phrase_presence_boost()`**

```python
def _apply_phrase_presence_boost(self, results: List[Dict], query_terms: List[str], exact_phrases: List[str]) -> List[Dict]:
    """
    Apply binary boost when query phrase literally appears in title/content.
    
    Different from keyword density - this rewards exact matches heavily.
    Applied BEFORE keyword density boost in the pipeline.
    
    Args:
        results: Deduplicated search results (must have 'title', may have 'text')
        query_terms: Parsed semantic terms from query
        exact_phrases: Explicit quoted phrases from query
        
    Returns:
        Results with phrase_presence_boost applied to scores
    """
```

Logic:
1. Construct search phrases: combine `exact_phrases` + full `" ".join(query_terms)` if len >= 2
2. For each result:
   - Check title for phrase match (case-insensitive, word boundaries)
   - If phrase in title: apply `phrase_in_title` boost, continue to next result
   - If not in title but all terms in title: apply `all_terms_in_title` boost
3. For `phrase_in_content`: need content - either already fetched (keyword boost candidates) or batch fetch for top N
4. Track boost applied in `result['phrase_presence_boost']`

**Integration point in `search()` method:**

Insert after `_apply_title_term_boost()`, before `_apply_keyword_boost()`:

```python
# 1. Title term boost (existing)
if query_terms:
    deduplicated = self._apply_title_term_boost(deduplicated, query_terms)

# 2. NEW: Phrase presence boost (binary exact match signal)
deduplicated = self._apply_phrase_presence_boost(
    deduplicated, 
    query_terms, 
    parsed_query.exact_phrases
)

# 3. Keyword frequency boost (existing)
# ...
```

**Query-length scaling applies** - use `_get_query_length_multiplier()` to scale the boost values.

---

## 2. Inverse Semantic Confidence Signal

### Purpose
When an article scores high semantically (>0.70) but has zero/minimal keyword matches, it found conceptual relevance the user didn't explicitly search for. Give a small bonus to surface these "discovery" results.

### Config Changes (`search_config.py`)

Add to `RERANKING_CONFIG`:

```python
# Inverse semantic confidence: boost high-semantic, low-keyword results
# Rewards the model for finding conceptually related content without keyword overlap
"semantic_discovery_boost": {
    "enabled": True,
    "min_semantic_score": 0.70,   # Must score this high semantically
    "max_keyword_hits": 1,        # Must have this few keyword matches (0 or 1)
    "boost": 0.025,               # Small bonus for "conceptual discovery"
},
```

### Implementation (`search_engine.py`)

**New method: `_apply_semantic_discovery_boost()`**

```python
def _apply_semantic_discovery_boost(self, results: List[Dict], query_terms: List[str]) -> List[Dict]:
    """
    Boost results with high semantic score but low keyword overlap.
    
    These are "conceptual discoveries" - the model found relevant content
    that doesn't contain the user's exact terms.
    
    Args:
        results: Results after keyword boost (will have keyword_boost field if applicable)
        query_terms: Query terms to check for presence
        
    Returns:
        Results with semantic_discovery_boost applied where applicable
    """
```

Logic:
1. For each result where `result.get('score') >= min_semantic_score` (original semantic, before boosts):
   - Check if `result.get('keyword_boost', 0) <= threshold` OR count keyword hits manually
   - If low keyword presence: apply boost
2. Track in `result['semantic_discovery_boost']`

**Note:** Need to preserve original semantic score before boosts. Add `result['base_semantic_score'] = result['score']` early in pipeline.

**Integration point:** After `_apply_keyword_boost()`, before `_apply_recency_boost()`.

---

## 3. Semantic Score Distribution Normalization

### Purpose
Use the shape of the score distribution to adjust filtering aggressiveness. Tight clusters = semantic isn't differentiating well, be stricter. Wide spread = clear gradient, trust semantic more.

### Config Changes (`search_config.py`)

Modify `SEMANTIC_FILTER_CONFIG["hybrid"]`:

```python
"hybrid": {
    "min_absolute_threshold": 0.52,
    "std_multiplier": 2.0,              # Base multiplier
    "use_median": False,
    
    # NEW: Distribution-aware adjustment
    "distribution_adaptive": True,
    "tight_cluster_std_threshold": 0.05,  # If std < this, distribution is tight
    "tight_cluster_multiplier": 1.0,      # Use tighter filtering (mean - 1.0*std)
    "wide_spread_std_threshold": 0.12,    # If std > this, distribution has clear gradient
    "wide_spread_multiplier": 2.5,        # Trust semantic more (mean - 2.5*std)
},
```

### Implementation (`search_engine.py`)

Modify `_filter_by_semantic_score()` in the `strategy == 'hybrid'` block:

```python
if strategy == 'hybrid':
    config = SEMANTIC_FILTER_CONFIG['hybrid']
    min_threshold = config.get('min_absolute_threshold', 0.35)
    base_std_multiplier = config.get('std_multiplier', 2.0)
    use_median = config.get('use_median', False)
    
    # NEW: Distribution-adaptive multiplier
    if config.get('distribution_adaptive', False):
        tight_threshold = config.get('tight_cluster_std_threshold', 0.05)
        wide_threshold = config.get('wide_spread_std_threshold', 0.12)
        
        if std_dev < tight_threshold:
            # Tight cluster - semantic not differentiating well
            std_multiplier = config.get('tight_cluster_multiplier', 1.0)
            logger.debug(f"Tight score cluster (std={std_dev:.3f}), using stricter filtering")
        elif std_dev > wide_threshold:
            # Wide spread - clear relevance gradient
            std_multiplier = config.get('wide_spread_multiplier', 2.5)
            logger.debug(f"Wide score spread (std={std_dev:.3f}), trusting semantic ranking")
        else:
            std_multiplier = base_std_multiplier
    else:
        std_multiplier = base_std_multiplier
    
    center = median_score if use_median else mean_score
    statistical_threshold = center - (std_multiplier * std_dev)
    threshold = max(min_threshold, statistical_threshold)
```

---

## 4. Diminishing Returns on Length Penalty

### Purpose
Long comprehensive articles shouldn't be over-penalized in keyword density. Use log-normalization instead of linear division.

### Config Changes (`search_config.py`)

Modify `RERANKING_CONFIG`:

```python
# Keyword frequency boost
"keyword_boost_max": 0.10,
"keyword_boost_scale": 0.025,
"keyword_density_scale": 1000,
"keyword_rerank_top_n": 200,
"keyword_max_query_terms": 5,

# NEW: Length normalization strategy
"keyword_length_normalization": "log",  # "linear" or "log"
"keyword_log_base_offset": 100,         # log(word_count + offset) - prevents log(0)
```

### Implementation (`search_engine.py`)

Modify `_apply_keyword_boost()`:

```python
# Current:
# density = (count / word_count) * density_scale

# New:
length_norm = RERANKING_CONFIG.get('keyword_length_normalization', 'linear')
log_offset = RERANKING_CONFIG.get('keyword_log_base_offset', 100)

if length_norm == 'log':
    # Diminishing penalty for long articles
    normalized_length = math.log(word_count + log_offset)
    density = (count / normalized_length) * density_scale
else:
    # Original linear normalization
    density = (count / word_count) * density_scale
```

This means:
- 500 word article: `log(600) ≈ 6.4` → density = count/6.4 * scale
- 5000 word article: `log(5100) ≈ 8.5` → density = count/8.5 * scale
- 15000 word article: `log(15100) ≈ 9.6` → density = count/9.6 * scale

Long articles get ~50% less penalty vs linear (instead of 30x less density, it's ~1.5x less).

---

## 5. Query Length Threshold Adjustment

### Config Changes (`search_config.py`)

Modify `RERANKING_CONFIG["query_length_scaling"]`:

```python
"query_length_scaling": {
    "enabled": True,
    "short_query_terms": 3,         # 1-3 terms = full boost (100%) - was 2
    "medium_query_terms": 4,        # 4 terms = medium boost - was 3
    "medium_query_multiplier": 0.5, # 50% boost for medium
    "long_query_multiplier": 0.25,  # 5+ terms = 25% boost (semantic focus)
},
```

### Implementation

No code changes needed - `_get_query_length_multiplier()` already reads these config values.

---

## Implementation Order

1. **Config changes first** - Add all new config sections
2. **Preserve base semantic score** - Add `result['base_semantic_score']` early in search pipeline
3. **Distribution-adaptive filtering** - Modify `_filter_by_semantic_score()`
4. **Log length normalization** - Modify `_apply_keyword_boost()`
5. **Phrase presence boost** - New method + integration
6. **Semantic discovery boost** - New method + integration
7. **Query length thresholds** - Config-only change

---

## Rollback

If issues arise, each feature has an `enabled` flag in config:
- `phrase_presence_boost.enabled`
- `semantic_discovery_boost.enabled`  
- `hybrid.distribution_adaptive`
- `keyword_length_normalization: "linear"` (revert to original)
