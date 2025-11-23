# Marxist Search - Power User Syntax Quick Reference

## Basic Syntax

| Syntax | Example | Description |
|--------|---------|-------------|
| `word word` | `capitalism imperialism` | Semantic search (finds related concepts) |
| `"exact phrase"` | `"permanent revolution"` | Must match exactly in content |
| `title:"phrase"` | `title:"Labour Theory"` | Search only in article titles |
| `author:"Name"` | `author:"Alan Woods"` | Filter by specific author |

## Combining Syntax

You can combine multiple syntax elements in one query:

```
title:"Revolution" author:"Woods" "dialectical materialism" capitalism
```

This query:
- ✓ Title must contain "Revolution"
- ✓ Author must be "Alan Woods"
- ✓ Content must contain exact phrase "dialectical materialism"
- ✓ Semantic search for "capitalism"

## Examples

### Simple Searches
```
capitalism
→ Semantic search for capitalism and related concepts

"permanent revolution"
→ Articles containing that exact phrase

title:"Palestine"
→ Articles with "Palestine" in the title

author:"Jorge Martin"
→ All articles by Jorge Martin
```

### Advanced Searches
```
title:"Russia" author:"Alan Woods" bolsheviks
→ Articles by Alan Woods with "Russia" in title, about bolsheviks

"class struggle" "dialectical materialism" USSR
→ Articles containing both exact phrases, with semantic match for USSR

title:"Climate" "global warming" capitalism
→ Climate articles containing "global warming", about capitalism

author:"Alan Woods" "permanent revolution" imperialism
→ Alan Woods articles with exact phrase, about imperialism
```

### Research Queries
```
title:"The Bolshevik Revolution" author:"Alan Woods"
→ Find specific article by title and author

"surplus value" "labor theory of value" capitalism
→ Economic theory articles with both exact phrases

title:"Lenin" "state and revolution" bolshevism
→ Lenin articles mentioning "state and revolution" exactly
```

## Tips

1. **Quotes matter**: `"permanent revolution"` (exact) vs `permanent revolution` (semantic)

2. **Case insensitive**: `title:"THEORY"` same as `title:"theory"`

3. **Author names**: Use exact format from database
   - ✓ `author:"Alan Woods"` 
   - ✗ `author:"Woods, Alan"`
   
4. **Combine with UI filters**: Power-user syntax overrides UI filters for author

5. **Multiple phrases**: All exact phrases must be present
   - `"A" "B" "C"` → Must contain all three

## Common Patterns

**Find specific article:**
```
title:"The Labour Theory of Value" author:"Alan Woods"
```

**Theory + practice:**
```
"permanent revolution" palestine gaza
```

**Historical research:**
```
title:"Russia" "October Revolution" author:"Ted Grant"
```

**Economic analysis:**
```
"surplus value" capitalism imperialism
```

**Contemporary issues:**
```
title:"Palestine" "genocide" "apartheid"
```

## What NOT to do

❌ Don't forget closing quotes:
```
"permanent revolution
→ Won't work correctly
```

❌ Don't use unsupported fields:
```
content:"text"  
→ Use regular "text" instead
```

❌ Don't try SQL injection:
```
author:"'; DROP TABLE articles; --"
→ Safely sanitized, won't work
```

## Performance Tips

- Exact phrase matching is slightly slower (needs to fetch content)
- Title matching is very fast
- Author filtering is very fast
- Combine with date filters in UI for better performance

## Still not finding what you need?

1. Try without quotes first to see if content exists
2. Check spelling
3. Try different variations of names
4. Use broader semantic terms
5. Check date range filters in UI

---

**Remember**: Regular semantic search still works great! Only use power-user syntax when you need exact matching or specific field searches.
