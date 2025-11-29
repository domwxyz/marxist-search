# Marxist Search - Backend

Python backend for the Marxist Search semantic search engine. Handles RSS ingestion, content extraction, term extraction, embedding generation, vector indexing, and search API.

## Overview

The backend provides a complete pipeline from RSS feeds to searchable vector index:

- **Ingestion**: RSS feed fetching with CMS-specific pagination, content extraction, text normalization
- **Term Extraction**: Automatic extraction of Marxist terms with synonym and alias support
- **Indexing**: Vector embeddings with Alibaba-NLP/gte-base-en-v1.5, automatic chunking, txtai index management (content=False, no internal storage)
- **Search**: Pure semantic search with custom multi-signal reranking (title boost, keyword boost, recency boost), power-user syntax (exact phrases, title/author filters), filtering, and deduplication
- **API**: FastAPI REST API with async request handling and thread pooling
- **CLI**: Comprehensive command-line interface for all operations
- **Analytics**: Search query tracking and term usage analytics

## Technology Stack

- **Python 3.11+**
- **Web Framework**: FastAPI + uvicorn
- **Vector Search**: txtai with Alibaba-NLP/gte-base-en-v1.5 embeddings
- **Database**: SQLite with full-text search support
- **Content Processing**: feedparser (RSS), trafilatura (web scraping)
- **CLI**: Click + Rich (terminal formatting)
- **Async**: aiohttp for concurrent HTTP requests

## Directory Structure

```
backend/
├── src/
│   ├── ingestion/              # RSS and content ingestion
│   │   ├── rss_fetcher.py         # RSS fetching with pagination
│   │   ├── content_extractor.py   # Full-text extraction
│   │   ├── term_extractor.py      # Special term extraction
│   │   ├── text_normalizer.py     # Text cleaning and normalization
│   │   ├── article_storage.py     # Database storage operations
│   │   ├── archiving_service.py   # Ingestion orchestrator
│   │   └── database.py            # Database schema and management
│   ├── indexing/               # Embedding and indexing
│   │   ├── chunking.py            # Article chunking for long documents
│   │   ├── txtai_manager.py       # txtai index management
│   │   └── indexing_service.py    # Indexing orchestrator
│   ├── search/                 # Search engine
│   │   ├── search_engine.py       # Core search with filtering
│   │   ├── filters.py             # Search filter helpers
│   │   └── analytics_tracker.py   # Search analytics
│   ├── api/                    # FastAPI application
│   │   ├── main.py                # FastAPI app with lifespan management
│   │   ├── routes.py              # API endpoints
│   │   └── models.py              # Pydantic request/response models
│   ├── cli/                    # Command-line interface
│   │   └── marxist_cli.py         # Unified CLI for all operations
│   └── scripts/                # Automation scripts
│       └── incremental_update.py  # Automated update script
├── config/
│   ├── rss_feeds.json          # RSS feed configuration (3 sources)
│   ├── terms_config.json       # Special terms, synonyms, aliases
│   ├── search_config.py        # Application configuration
│   └── analytics_config.json   # Analytics configuration
├── data/                       # Data directory (gitignored)
│   ├── articles.db             # SQLite database
│   ├── cache/                  # JSON cache files
│   └── txtai/                  # Vector index files
├── requirements.txt
└── README.md
```

## Installation

### Prerequisites

- Python 3.11 or higher
- pip and venv

### Setup

1. **Create virtual environment**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize database**:
   ```bash
   python -m src.cli.marxist_cli init-db
   ```

## CLI Usage

The unified CLI (`marxist_cli.py`) provides all backend functionality:

### Database Management

```bash
# Initialize database schema
python -m src.cli.marxist_cli init-db
```

### Archiving Commands

```bash
# Archive all configured RSS feeds
python -m src.cli.marxist_cli archive run

# Incremental update (stops after 5 consecutive duplicates)
python -m src.cli.marxist_cli archive update

# Archive specific feed
python -m src.cli.marxist_cli archive run --feed-url "https://www.marxist.com/rss.xml"

# List configured feeds
python -m src.cli.marxist_cli archive list
```

The archiving process:
- Fetches RSS feeds with CMS-specific pagination
- Extracts full article content (from RSS or web)
- Extracts special terms (150+ tracked terms)
- Normalizes and cleans text
- Stores articles in SQLite database

### Indexing Commands

```bash
# Build txtai vector index from archived articles
python -m src.cli.marxist_cli index build

# Update index with new articles only
python -m src.cli.marxist_cli index update

# Force rebuild of existing index
python -m src.cli.marxist_cli index build --force

# View index information
python -m src.cli.marxist_cli index info
```

The indexing process:
- Loads articles from database
- Chunks long articles (>5500 words)
- Repeats titles 5x for weighting
- Generates embeddings with gte-base-en-v1.5
- Builds txtai index with pure semantic search

### Search Commands

```bash
# Basic search
python -m src.cli.marxist_cli search "climate change"

# Search with filters
python -m src.cli.marxist_cli search "imperialism" --author "Alan Woods"
python -m src.cli.marxist_cli search "revolution" --source "In Defence of Marxism"
python -m src.cli.marxist_cli search "capitalism" --date-range past_year
python -m src.cli.marxist_cli search "palestine" --start-date 2023-01-01 --end-date 2024-12-31

# Advanced search syntax
python -m src.cli.marxist_cli search '"permanent revolution"'
python -m src.cli.marxist_cli search 'title:"Labour Theory"'
python -m src.cli.marxist_cli search 'author:"Alan Woods"'
python -m src.cli.marxist_cli search 'title:"Theory" author:"Woods" capitalism'

# Limit results
python -m src.cli.marxist_cli search "socialism" --limit 20
```

## Advanced Search Syntax

The search engine supports power-user syntax for precise queries:

**Exact Phrase Search**: Use double quotes for exact phrase matching in content
```bash
python -m src.cli.marxist_cli search '"permanent revolution"'
```

**Title Search**: Search only in article titles using `title:`
```bash
python -m src.cli.marxist_cli search 'title:"The Labour Theory"'
```

**Author Filter**: Filter by specific author using `author:`
```bash
python -m src.cli.marxist_cli search 'author:"Alan Woods"'
```

**Combined Queries**: Combine multiple syntax elements with semantic search
```bash
python -m src.cli.marxist_cli search 'title:"Theory" author:"Woods" capitalism'
python -m src.cli.marxist_cli search '"dialectical materialism" USSR title:"Revolution"'
```

**Syntax Rules**:
- `"text"` - Exact phrase match in content (uses whole-word boundaries)
- `title:"text"` - Search in article titles only
- `author:"Name"` - Filter by author
- Regular words use semantic search (similar meaning)
- All syntax elements can be combined in a single query

### Statistics

```bash
# View comprehensive statistics
python -m src.cli.marxist_cli stats
```

Shows:
- Archive statistics (total articles, recent articles)
- Index statistics (indexed documents, model info)
- Feed configurations and status
- Author statistics

## Running the API Server

```bash
# Development server with auto-reload
python -m src.api.main

# Or use uvicorn directly
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Production (without reload)
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

API available at:
- Base URL: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`

## API Endpoints

### POST /api/v1/search
Search articles with natural language query and filters. Supports advanced search syntax.

**Request Body**:
```json
{
  "query": "climate change",
  "source": "In Defence of Marxism",
  "author": "Alan Woods",
  "date_range": "past_year",
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "limit": 10
}
```

**Advanced Search Syntax Examples**:
```json
{"query": "\"permanent revolution\""}
{"query": "title:\"Labour Theory\""}
{"query": "author:\"Alan Woods\""}
{"query": "title:\"Theory\" author:\"Woods\" capitalism"}
```

**Response**:
```json
{
  "results": [
    {
      "id": 123,
      "title": "Article Title",
      "content": "Article excerpt...",
      "url": "https://example.com/article",
      "source": "In Defence of Marxism",
      "author": "Alan Woods",
      "published_date": "2024-01-15",
      "score": 0.92,
      "tags": ["climate", "environment"]
    }
  ],
  "total": 42,
  "query": "climate change",
  "filters_applied": {...}
}
```

### GET /api/v1/top-authors
Get top authors by article count.

**Response**:
```json
{
  "authors": [
    {"name": "Alan Woods", "article_count": 450, "earliest": "2000-01-01", "latest": "2024-01-15"},
    {"name": "Jorge Martin", "article_count": 312, "earliest": "2002-03-12", "latest": "2024-01-10"}
  ]
}
```

### GET /api/v1/sources
List all article sources.

**Response**:
```json
{
  "sources": ["In Defence of Marxism", "Revolutionary Communists of America", "RCP"]
}
```

### GET /api/v1/stats
Get database and index statistics.

**Response**:
```json
{
  "database": {
    "total_articles": 16234,
    "indexed_articles": 16234,
    "sources": 3,
    "authors": 187,
    "date_range": {"earliest": "2000-01-01", "latest": "2024-01-15"}
  },
  "index": {
    "total_documents": 18452,
    "model": "BAAI/bge-small-en-v1.5",
    "backend": "numpy"
  }
}
```

### GET /api/v1/health
Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Configuration

### RSS Feeds (`config/rss_feeds.json`)

Configure RSS sources with pagination support:

```json
{
  "feeds": [
    {
      "name": "In Defence of Marxism",
      "url": "https://marxist.com/index.php?format=feed",
      "pagination_type": "joomla",
      "limit_increment": 5,
      "enabled": true,
      "organization": "RCI",
      "language": "en",
      "region": "international"
    },
    {
      "name": "Revolutionary Communists of America",
      "url": "https://communistusa.org/feed/",
      "pagination_type": "wordpress",
      "limit_increment": 1,
      "enabled": true,
      "organization": "RCA",
      "language": "en",
      "region": "usa"
    },
    {
      "name": "Revolutionary Communist Party",
      "url": "https://communist.red/feed",
      "pagination_type": "wordpress",
      "limit_increment": 1,
      "enabled": true,
      "organization": "RCP-UK",
      "language": "en",
      "region": "uk"
    }
  ]
}
```

**Pagination Types**:
- `wordpress`: WordPress pagination (`?paged=N`)
- `joomla`: Joomla pagination (`?format=feed&limitstart=N`)
- `standard`: No pagination (single page)

### Special Terms (`config/terms_config.json`)

Configure term extraction, synonyms, and aliases:

```json
{
  "synonyms": {
    "proletariat": ["working class", "workers", "wage laborers"],
    "bourgeoisie": ["capitalist class", "ruling class", "capitalists"],
    "capitalism": ["capitalist system"]
  },
  "terms": {
    "people": ["Karl Marx", "Friedrich Engels", "Vladimir Lenin", "Leon Trotsky"],
    "organizations": ["IMT", "RCI", "NATO", "United Nations"],
    "concepts": ["permanent revolution", "dialectical materialism", "surplus value"],
    "geographic": ["Venezuela", "China", "Russia", "Cuba"],
    "historical_events": ["Russian Revolution", "Spanish Civil War"],
    "movements": ["labor movement", "climate movement"]
  },
  "aliases": {
    "UN": "United Nations",
    "USSR": "Soviet Union",
    "IMT": "International Marxist Tendency"
  }
}
```

**Features**:
- **Synonyms**: Synonym groups for query expansion
- **Terms**: Tracked terms across 6 categories (people, organizations, concepts, geographic locations, historical events, movements)
- **Aliases**: Bidirectional aliases (e.g., "USSR" ↔ "Soviet Union")
- Terms are extracted from article titles and content
- Stored in `term_mentions` table for analytics

### Application Settings (`config/search_config.py`)

Central configuration for the entire backend:

```python
# Database paths (can be overridden via environment variables)
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/articles.db")
TXTAI_INDEX_PATH = os.getenv("INDEX_PATH", "data/txtai")

# txtai configuration
TXTAI_CONFIG = {
    "path": "BAAI/bge-small-en-v1.5",
    "backend": "numpy",  # CPU-only, exact search
    "content": False,    # No internal content storage - content fetched from SQLite
    "keyword": False     # BM25 disabled to prevent index corruption during incremental updates
}

# Chunking configuration
CHUNKING_CONFIG = {
    "threshold_words": 3500,  # Chunk articles longer than this
    "chunk_size_words": 1000,  # Target chunk size
    "overlap_words": 200,  # Overlap between chunks
    "prefer_section_breaks": True,  # Break on paragraph boundaries
    "section_markers": ["\n\n", "\n"]  # Paragraph markers
}

# Search configuration - pure semantic search
SEARCH_CONFIG = {
    "semantic_weight": 1.0,   # Pure semantic search (100%)
    "bm25_weight": 0.0,       # BM25 disabled (0%)
    "recency_boost": {
        "7_days": 0.07,    # Additive boost (not multiplicative)
        "30_days": 0.05,
        "90_days": 0.03,
        "1_year": 0.02,
        "3_years": 0.01
    }
}

# Reranking configuration - custom multi-signal reranking
RERANKING_CONFIG = {
    "title_boost_max": 0.08,           # Maximum boost when all query terms in title
    "keyword_boost_max": 0.06,         # Maximum keyword frequency boost
    "keyword_boost_scale": 0.02,       # Scaling factor for log TF score
    "keyword_rerank_top_n": 150,       # Number of top candidates to rerank
    "keyword_max_query_terms": 5,      # Skip keyword boost for longer queries (perf)
}

# Title weighting - applied during indexing
TITLE_WEIGHT_MULTIPLIER = 5  # Repeat titles 5x in embeddings

# Concurrency configuration
CONCURRENCY_CONFIG = {
    "search_thread_pool_size": 4,
    "max_concurrent_searches": 24
}
```

## Database Schema

### articles
Full article content and metadata.

```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
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
);
```

### article_chunks
Chunks for long articles (>3500 words).

```sql
CREATE TABLE article_chunks (
    id INTEGER PRIMARY KEY,
    article_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    word_count INTEGER,
    start_position INTEGER,
    FOREIGN KEY (article_id) REFERENCES articles (id)
);
```

### rss_feeds
Feed status and health tracking.

```sql
CREATE TABLE rss_feeds (
    id INTEGER PRIMARY KEY,
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
);
```

### author_stats
Author statistics and metadata.

```sql
CREATE TABLE author_stats (
    author TEXT PRIMARY KEY,
    article_count INTEGER DEFAULT 0,
    first_article_date DATETIME,
    latest_article_date DATETIME
);
```

### term_mentions
Special term occurrences for analytics.

```sql
CREATE TABLE term_mentions (
    id INTEGER PRIMARY KEY,
    article_id INTEGER NOT NULL,
    term_text TEXT NOT NULL,
    term_type TEXT NOT NULL,
    mention_count INTEGER DEFAULT 1,
    FOREIGN KEY (article_id) REFERENCES articles (id)
);
```

### search_logs
Search query logging for analytics.

```sql
CREATE TABLE search_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    filters_json TEXT,
    result_count INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Features

### Pagination Support

The RSS fetcher handles different CMS pagination schemes:

**WordPress**:
- URL: `?paged=1`, `?paged=2`, etc.
- Increments page number automatically
- Stops when no new entries found

**Joomla**:
- URL: `?format=feed&limitstart=0`, `?format=feed&limitstart=5`, etc.
- Increments by configured amount
- Stops when no new entries found

**Standard**:
- No pagination
- Processes first page only
- Checks for RSS `<link rel="next">` tags

### Content Extraction

Intelligent full-text extraction strategy:

1. Check if RSS feed contains full content (>200 chars)
2. If only summary, fetch full text from URL using trafilatura
3. Extract metadata (title, author, date, tags) from RSS
4. Normalize all text before storage

### Special Term Extraction

Automatic extraction of Marxist terminology:

- **Special Terms** across 6 categories
- **Synonym Groups** for query expansion
- **Aliases** with bidirectional resolution
- Terms extracted from titles and content
- Stored in `term_mentions` for analytics
- Used for improved search relevance

### Chunking Strategy

Long articles are automatically chunked:

- **Threshold**: Articles >3500 words are chunked
- **Chunk Size**: ~1000 words per chunk
- **Overlap**: 200 words between chunks
- **Boundary Preservation**: Chunks break on paragraph boundaries
- Each chunk indexed separately
- Smart deduplication returns highest-scoring chunk per article

### Search Architecture

Pure semantic search with custom multi-signal reranking:

- **Semantic Search (100%)**: Vector similarity with bge-small-en-v1.5 embeddings
  - BM25 disabled in txtai (`keyword: False`) to prevent index corruption during incremental updates
  - Content not stored in txtai (`content: False`) - all content fetched from SQLite database instead
- **Title Weighting**: Titles repeated 5x during indexing for better semantic relevance
- **Query Expansion**: Synonyms and aliases automatically expand queries
- **Custom Reranking**: Multi-signal reranking applied after semantic search retrieval
  - **Title Term Boost**: Rewards results where query terms appear in title (max +0.08)
  - **Keyword Frequency Boost**: Pseudo-BM25 on top 150 candidates using log-scaled term frequency (max +0.06)
  - **Recency Boost**: Additive boosts for recent articles (7 days: +0.07, 30 days: +0.05, 90 days: +0.03, 1 year: +0.02, 3 years: +0.01)
- **Smart Deduplication**: Groups chunks by article, returns highest-scoring chunk per article
- **On-Demand Content Fetching**: Content fetched from SQLite only for final paginated results (not for all 8000 candidates)

### Text Normalization

All article text is normalized:

- HTML entities decoded
- HTML tags removed
- Excessive whitespace cleaned
- Email addresses redacted
- Paragraph structure preserved
- Consistent encoding (UTF-8)

### Duplicate Detection

Articles are deduplicated by:
- URL (primary check)
- GUID (fallback check)
- Duplicates counted but not stored

## Automation

### Incremental Updates

The `incremental_update.py` script is designed for systemd/cron automation:

```bash
# Manual run
python -m src.scripts.incremental_update

# Systemd timer (every 30 minutes)
sudo systemctl start marxist-search-update.timer
sudo systemctl enable marxist-search-update.timer
```

The script:
1. Fetches new articles from RSS feeds (stops after 5 consecutive duplicates)
2. Extracts special terms
3. Updates txtai index with new articles only
4. Logs to stdout/stderr (captured by systemd)

## Architecture

### Async/Await Pattern

The ingestion service uses async/await for efficient concurrent processing:

```python
# Fetch all feeds concurrently
feed_results = await rss_fetcher.fetch_all_feeds(feed_urls)

# Extract content from all entries concurrently
articles = await content_extractor.extract_from_entries(entries)
```

Benefits:
- Multiple feeds fetched in parallel
- Multiple articles extracted simultaneously
- Efficient use of I/O waiting time

### Modular Design

Each component has a single responsibility:

- **RSSFetcher**: Fetch and parse RSS feeds
- **ContentExtractor**: Extract full article content
- **TermExtractor**: Extract special terms and entities
- **TextNormalizer**: Clean and normalize text
- **ArticleStorage**: Database operations
- **ArchivingService**: Orchestrate the ingestion pipeline
- **TxtaiManager**: Manage vector index
- **SearchEngine**: Execute searches with filters
- **AnalyticsTracker**: Track search analytics

### Thread Safety

The search engine uses thread pooling for CPU-bound operations:

```python
# Search operations run in thread pool
search_results = await asyncio.to_thread(search_engine.search, query, filters)
```

This allows the FastAPI server to remain responsive while performing CPU-intensive vector search.

## Performance

- **Archiving**: ~500 articles/minute (depends on network and site response)
- **Indexing**: ~100 articles/second (CPU-bound)
- **Search**: <200ms query latency (95th percentile with numpy backend)
- **Concurrent Searches**: 10-20 simultaneous users supported
- **Index Size**: ~2GB in RAM for 16,000 articles
- **Database Size**: ~200MB (SQLite)

## Troubleshooting

### FAISS AttributeError

**Error**: `AttributeError: 'IndexIVFFlat' object has no attribute 'nflip'`

**Solution**: The project uses numpy backend to avoid FAISS issues:
```bash
rm -rf data/txtai
python -m src.cli.marxist_cli index build
```

### Database Locked

**Cause**: SQLite doesn't support high concurrency

**Solutions**:
- Ensure only one archiving process runs at a time
- For production with high concurrency, consider PostgreSQL

### Missing Dependencies

**Solution**:
```bash
pip install -r requirements.txt
```

### Slow Search Performance

**Solutions**:
- Ensure index is loaded into RAM
- Check `SEARCH_THREAD_POOL_SIZE` in config
- Consider `hnsw` backend for faster approximate search (requires hnswlib)

### Out of Memory During Indexing

**Solutions**:
- Index in smaller batches
- Increase system RAM
- Use a machine with more memory for initial indexing

## Development

### Testing Archive Pipeline

```bash
# Run with verbose logging
export LOG_LEVEL=DEBUG
python -m src.cli.marxist_cli archive run

# Test specific feed
python -m src.cli.marxist_cli archive run --feed-url "https://www.marxist.com/rss.xml"
```

### Testing Search

```bash
# CLI search
python -m src.cli.marxist_cli search "test query"

# API search (requires running server)
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "limit": 10}'
```

### Adding New Feeds

1. Add feed to `config/rss_feeds.json`
2. Set correct `pagination_type`
3. Run `python -m src.cli.marxist_cli archive run`
4. Check logs for issues

## License

See LICENSE file in repository root.
