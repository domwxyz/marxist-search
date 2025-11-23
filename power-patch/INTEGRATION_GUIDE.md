# Power-User Search Syntax - Integration Guide

## Overview
This guide shows how to integrate advanced search syntax into your Marxist Search Engine.

**Features:**
- ✅ Exact phrase matching: `"permanent revolution"`
- ✅ Title-specific search: `title:"The Labour Theory"`
- ✅ Author filtering: `author:"Alan Woods"`
- ✅ Combined queries: `title:"Theory" author:"Woods" capitalism`
- ✅ SQL injection prevention
- ✅ Input sanitization
- ✅ Parameterized queries throughout

---

## Backend Integration

### Step 1: Copy the Query Parser

Copy `query_parser.py` to your backend:
```bash
cp query_parser.py backend/src/search/query_parser.py
```

### Step 2: Modify search_engine.py

File: `backend/src/search/search_engine.py`

**A. Add import at the top:**
```python
from .query_parser import QueryParser, ParsedQuery
```

**B. Add to SearchEngine.__init__() method (around line 40):**
```python
# Initialize query parser for power-user syntax
self.query_parser = QueryParser()
```

**C. Replace the entire search() method** with the version in `search_engine_modifications.py`

**D. Add the two new helper methods** at the end of the SearchEngine class:
- `_filter_by_exact_phrases()`
- `_filter_by_title_phrases()`

Both methods are in `search_engine_modifications.py`

---

## Frontend Integration

### Step 1: Copy Syntax Helper Component

Copy the component to your frontend:
```bash
cp SearchSyntaxHelper.jsx frontend/src/components/SearchSyntaxHelper.jsx
```

### Step 2: Modify App.js

File: `frontend/src/App.js`

**A. Add import:**
```javascript
import SearchSyntaxHelper from './components/SearchSyntaxHelper';
```

**B. Add the component after the SearchBar:**
```javascript
{/* Search Interface Container */}
<div className="space-y-6">
  {/* Search Bar */}
  <SearchBar
    query={query}
    onQueryChange={setQuery}
    onSearch={handleSearch}
  />

  {/* ADD THIS: Syntax Helper */}
  <SearchSyntaxHelper />

  {/* Filter Panel */}
  <FilterPanel
    filters={filters}
    onFilterChange={updateFilter}
    onClearFilters={clearFilters}
  />
</div>
```

---

## Security Features ✅

### 1. Input Sanitization
All user inputs are sanitized in `query_parser.py`:
- Null byte removal
- Length limits (max 1000 chars total, 500 per field)
- Whitespace normalization
- No eval() or exec() calls

### 2. SQL Injection Prevention
- **All database queries use parameterized queries**
- Field names validated against whitelist (`VALID_FIELDS`)
- No string concatenation in SQL
- Content matching done in Python (post-filter), not SQL

Example (safe):
```python
cursor.execute(
    "SELECT * FROM articles WHERE id IN (?, ?, ?)",
    [id1, id2, id3]  # ✅ Parameterized - SAFE
)
```

vs. (unsafe - NOT USED):
```python
cursor.execute(
    f"SELECT * FROM articles WHERE id IN ({ids})"  # ❌ String formatting - UNSAFE
)
```

### 3. Field Name Validation
```python
VALID_FIELDS = {'title', 'author'}  # Whitelist

if field_name not in self.VALID_FIELDS:
    logger.warning(f"Invalid field name: {field_name}")
    continue  # Skip invalid fields
```

### 4. Exact Matching Security
- Exact phrase matching done **in Python**, not SQL
- Fetches content via parameterized query
- Uses Python string matching (`in` operator)
- No regex user input in SQL

---

## Testing

### Test Queries

**1. Basic exact phrase:**
```
"permanent revolution"
```
Expected: Only articles containing that exact phrase

**2. Title search:**
```
title:"The Labour Theory"
```
Expected: Articles with "The Labour Theory" in title

**3. Author filter:**
```
author:"Alan Woods"
```
Expected: Only articles by Alan Woods

**4. Combined query:**
```
title:"Revolution" author:"Woods" capitalism imperialism
```
Expected: Articles by Woods with "Revolution" in title, about capitalism/imperialism

**5. Multiple exact phrases:**
```
"dialectical materialism" "class struggle" USSR
```
Expected: Articles containing both exact phrases + semantic match for USSR

**6. Complex combined:**
```
title:"Theory" author:"Alan Woods" "permanent revolution" capitalism
```
Expected: All conditions must be met

### Security Tests

**Try these malicious inputs (should all be handled safely):**

1. SQL Injection attempt:
```
author:"'; DROP TABLE articles; --"
```
✅ Handled by parameterized queries

2. XSS attempt:
```
title:"<script>alert('xss')</script>"
```
✅ Sanitized, treated as literal text

3. Null bytes:
```
author:"Alan\x00Woods"
```
✅ Null bytes removed

4. Extremely long query:
```
capitalism imperialism ... (2000 chars)
```
✅ Rejected (max 1000 chars)

---

## Example Usage

### Simple Semantic Search
```
Query: capitalism imperialism
Result: Semantic search across all content
```

### Exact Phrase
```
Query: "permanent revolution"
Result: Only articles with that exact phrase
```

### Title-Specific Search
```
Query: title:"The Labour Theory of Value"
Result: Articles with that phrase in title only
```

### Author Filter
```
Query: author:"Jorge Martin"
Result: All articles by Jorge Martin
```

### Combined Advanced Query
```
Query: title:"Palestine" author:"Alan Woods" "permanent revolution" zionism
Result: 
- Title must contain "Palestine"
- Author must be "Alan Woods"  
- Content must contain exact phrase "permanent revolution"
- Semantic search for "zionism"
```

### Real-World Example
```
Query: title:"Russia" "October Revolution" author:"Alan Woods" bolsheviks
Result: Articles by Alan Woods about Russia, containing "October Revolution" 
exactly, with semantic match for bolsheviks
```

---

## API Response Changes

The search response now includes parsed query details:

```json
{
  "results": [...],
  "total": 42,
  "query": "title:\"Theory\" capitalism",
  "parsed_query": {
    "semantic_terms": ["capitalism"],
    "exact_phrases": [],
    "title_phrases": ["Theory"],
    "author_filter": null
  },
  "query_time_ms": 145
}
```

---

## Troubleshooting

### No results with exact phrase
**Problem:** `"permanent revolution"` returns no results

**Check:**
1. Is the phrase actually in any articles? (Try without quotes first)
2. Check spelling and capitalization (matching is case-insensitive)
3. Check backend logs for parsing errors

### Title search not working
**Problem:** `title:"Theory"` returns wrong results

**Check:**
1. Ensure quotes are properly closed
2. Check backend logs for "Title phrase filter" debug message
3. Verify articles actually have that phrase in title field

### Author filter ignored
**Problem:** `author:"Alan Woods"` shows other authors

**Check:**
1. Author name must match exactly as stored in database
2. Check database for actual author name format:
   ```sql
   SELECT DISTINCT author FROM articles WHERE author LIKE '%Woods%';
   ```
3. Use the exact format from database

---

## Performance Notes

- **Exact phrase matching** requires fetching content, so may be slightly slower
- **Title matching** is fast (uses existing metadata)
- **Author filtering** is fast (indexed in database)
- Recommend combining with date filters for better performance

---

## Future Enhancements (Optional)

Consider adding:
1. `tag:"climate"` - Search by tag
2. `source:"In Defence of Marxism"` - Filter by source
3. `date:2024` or `year:2024` - Date/year syntax
4. Boolean operators: `AND`, `OR`, `NOT`
5. Wildcard matching: `"permanent *"` (match partial phrases)

---

## Summary

✅ **Files to modify:**
- Copy `query_parser.py` → `backend/src/search/query_parser.py`
- Modify `backend/src/search/search_engine.py` (add import, modify search(), add 2 methods)
- Copy `SearchSyntaxHelper.jsx` → `frontend/src/components/SearchSyntaxHelper.jsx`
- Modify `frontend/src/App.js` (add import, add component)

✅ **Security measures:**
- Input sanitization ✓
- Parameterized queries ✓  
- Field name whitelist ✓
- Length limits ✓
- Python-based matching (no SQL injection) ✓

✅ **Features:**
- Exact phrase matching ✓
- Title-specific search ✓
- Author filtering via syntax ✓
- Combined queries ✓
- Backward compatible (existing queries still work) ✓

**No database schema changes required!**
