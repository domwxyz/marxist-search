# Marxist Search - Backend

A RAG-based semantic search engine for Marxist theoretical and analytical articles.

## Overview

This backend service implements the archiving and search functionality for a corpus of ~16,000 articles from Marxist publications. The system uses:

- **RSS Feed Archiving**: Automated fetching with pagination support
- **Content Extraction**: Full-text extraction using feedparser and trafilatura
- **Text Normalization**: Cleaning and preparing content for indexing
- **Vector Search**: txtai with BAAI/bge-small-en-v1.5 embeddings
- **Storage**: SQLite for metadata and content

## Current Implementation Status

### ✅ Completed: Archiving Services

The archiving portion of the backend is fully implemented:

1. **RSS Feed Fetcher** (`src/ingestion/rss_fetcher.py`)
   - Pagination support for WordPress and Joomla feeds
   - Concurrent async fetching of multiple feeds
   - Duplicate detection and filtering
   - HTTP caching support

2. **Content Extractor** (`src/ingestion/content_extractor.py`)
   - Intelligent detection of full content in RSS feeds
   - Fallback to trafilatura for summary-only feeds
   - Tag/category extraction
   - Author and date parsing

3. **Text Normalizer** (`src/ingestion/text_normalizer.py`)
   - HTML entity decoding
   - Tag removal and cleanup
   - Whitespace normalization
   - Author name normalization

4. **Database Management** (`src/ingestion/database.py`)
   - Complete schema implementation
   - Tables for articles, chunks, feeds, authors, terms
   - Proper indexing for performance

5. **Article Storage** (`src/ingestion/article_storage.py`)
   - Batch saving with duplicate detection
   - Author statistics tracking
   - RSS feed health monitoring

6. **Archiving Service** (`src/ingestion/archiving_service.py`)
   - Orchestrates the complete archiving pipeline
   - Processes all feeds concurrently
   - Comprehensive statistics and reporting

### ✅ Completed: Embedding & Indexing Services

The embedding and indexing system is fully implemented:

1. **Article Chunking** (`src/indexing/chunking.py`)
   - Chunks articles longer than 3,500 words
   - Paragraph-boundary chunking (preserves natural breaks)
   - Configurable chunk size (1,000 words) and overlap (200 words)
   - Stores chunks in database for tracking

2. **txtai Manager** (`src/indexing/txtai_manager.py`)
   - Manages txtai embeddings index
   - Uses BAAI/bge-small-en-v1.5 for embeddings
   - Hybrid search (semantic + BM25 keyword search)
   - Index persistence and loading

3. **Indexing Service** (`src/indexing/indexing_service.py`)
   - Orchestrates chunking and indexing pipeline
   - Loads articles from database
   - Creates embeddings for articles and chunks
   - Updates database with indexing status

4. **General Purpose CLI** (`src/cli/marxist_cli.py`)
   - Archive management (`archive run`, `archive list`)
   - Index management (`index build`, `index info`)
   - Database initialization (`init-db`)
   - Comprehensive statistics (`stats`)

## Directory Structure

```
backend/
├── src/
│   ├── ingestion/          # Archiving services
│   │   ├── rss_fetcher.py         # RSS feed fetching with pagination
│   │   ├── content_extractor.py   # Content extraction
│   │   ├── text_normalizer.py     # Text normalization
│   │   ├── article_storage.py     # Database storage
│   │   ├── archiving_service.py   # Main orchestrator
│   │   └── database.py            # Database management
│   ├── indexing/           # Embedding and indexing
│   │   ├── chunking.py            # Article chunking
│   │   ├── txtai_manager.py       # txtai index manager
│   │   └── indexing_service.py    # Index building orchestrator
│   ├── cli/                # Command-line tools
│   │   ├── marxist_cli.py         # General purpose CLI
│   │   └── archive_cli.py         # Legacy archiving CLI (deprecated)
│   ├── api/                # FastAPI endpoints (TODO)
│   └── search/             # Search functionality (TODO)
├── config/
│   ├── rss_feeds.json             # RSS feed configuration
│   └── search_config.py           # Application configuration
├── data/                   # Data directory (gitignored)
│   ├── articles.db                # SQLite database
│   ├── cache/                     # JSON caches
│   └── txtai/                     # Vector index
├── requirements.txt
└── README.md
```

## Installation

### Prerequisites

- Python 3.11+
- pip

### Setup

1. **Create virtual environment**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize database**:
   ```bash
   python -m src.cli.marxist_cli init-db
   ```

## Usage

### CLI Commands

The Marxist Search CLI (`marxist_cli.py`) provides a comprehensive interface for managing the search engine.

#### Database Initialization

```bash
# Initialize the database schema
python -m src.cli.marxist_cli init-db
```

#### Archiving Commands

```bash
# Archive all configured RSS feeds
python -m src.cli.marxist_cli archive run

# Archive a specific feed
python -m src.cli.marxist_cli archive run --feed-url "https://www.marxist.com/rss.xml"

# List all configured feeds
python -m src.cli.marxist_cli archive list
```

The archiving process will:
- Fetch RSS feeds with pagination support
- Extract full article content (from RSS or web)
- Normalize and clean text
- Store articles in the database

#### Indexing Commands

```bash
# Build txtai vector index from archived articles
python -m src.cli.marxist_cli index build

# Force rebuild of existing index
python -m src.cli.marxist_cli index build --force

# View index information
python -m src.cli.marxist_cli index info
```

The indexing process will:
- Load articles from database
- Chunk long articles (>3,500 words)
- Generate embeddings using bge-small-en-v1.5
- Build and save txtai index

#### Statistics

```bash
# View comprehensive statistics
python -m src.cli.marxist_cli stats
```

Shows:
- Archive statistics (total articles, recent articles)
- Index statistics (indexed documents, status)
- Feed configurations

## Configuration

### RSS Feeds Configuration

Edit `config/rss_feeds.json` to add or modify RSS feeds:

```json
{
  "feeds": [
    {
      "name": "In Defence of Marxism",
      "url": "https://www.marxist.com/rss.xml",
      "pagination_type": "joomla",
      "limit_increment": 5,
      "enabled": true,
      "organization": "RCI"
    }
  ]
}
```

**Pagination Types**:
- `wordpress`: WordPress pagination (?paged=N)
- `joomla`: Joomla pagination (?format=feed&limitstart=N)
- `standard`: No pagination (single page only)

### Application Configuration

Edit `config/search_config.py` for application settings:

- Database paths
- Content extraction settings
- Logging configuration
- RSS fetch settings

## Database Schema

### Articles Table

Stores full article content and metadata:

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
    tags_json TEXT
);
```

### RSS Feeds Table

Tracks feed status and health:

```sql
CREATE TABLE rss_feeds (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    pagination_type TEXT DEFAULT 'standard',
    last_checked DATETIME,
    status TEXT DEFAULT 'active',
    consecutive_failures INTEGER DEFAULT 0
);
```

See `src/ingestion/database.py` for complete schema.

## Features

### Pagination Support

The RSS fetcher supports different pagination schemes:

**WordPress**:
- URL pattern: `?paged=1`, `?paged=2`, etc.
- Automatically increments page number
- Stops when no new entries found

**Joomla**:
- URL pattern: `?format=feed&limitstart=0`, `?format=feed&limitstart=5`, etc.
- Increments by configurable amount
- Stops when no new entries found

**Standard**:
- No pagination
- Processes first page only
- Checks for RSS `<link rel="next">` tags

### Content Extraction

The extractor intelligently determines how to get full article text:

1. **Check RSS feed**: If content field has full text (>200 chars), use it
2. **Fallback to web scraping**: If only summary available, fetch from URL using trafilatura
3. **Metadata extraction**: Always extract title, author, date, tags from RSS

### Text Normalization

All article text is normalized before storage:

- HTML entities decoded
- HTML tags removed
- Excessive whitespace cleaned
- Email addresses redacted
- Paragraph structure preserved

### Duplicate Detection

Articles are deduplicated by:
- URL (primary check)
- GUID (fallback check)
- Duplicates are counted but not stored

## Architecture

### Async/Await Pattern

The archiving service uses async/await for efficient concurrent processing:

```python
# Fetch all feeds concurrently
feed_results = await rss_fetcher.fetch_all_feeds(feed_urls)

# Extract content from all entries concurrently
articles = await content_extractor.extract_from_entries(entries)
```

This allows:
- Multiple feeds fetched in parallel
- Multiple articles extracted simultaneously
- Efficient use of I/O waiting time

### Modular Design

Each component has a single responsibility:

- `RSSFetcher`: Fetch and parse RSS feeds
- `ContentExtractor`: Extract full article content
- `TextNormalizer`: Clean and normalize text
- `ArticleStorage`: Save to database
- `ArchivingService`: Orchestrate the pipeline

## Next Steps

### TODO: Indexing Services

- Implement chunking for long articles
- Generate embeddings using txtai
- Build vector index
- Support incremental updates

### TODO: Search Services

- Implement semantic search
- Add filtering (date, source, author)
- Score and rank results
- Deduplicate chunks

### TODO: API Endpoints

- FastAPI application
- Search endpoint
- Statistics endpoints
- Health checks

### TODO: Term Extraction

- Load terms from `terms_config.json`
- Extract special terms from articles
- Store in `term_mentions` table

## Troubleshooting

### Issue: No articles extracted

**Possible causes**:
- Feed URLs are example/placeholder URLs
- Network connectivity issues
- Trafilatura can't extract content from the site

**Solutions**:
- Update `config/rss_feeds.json` with actual feed URLs
- Check network connectivity
- Verify feeds are accessible in browser

### Issue: Database locked errors

**Cause**: SQLite doesn't support high concurrency

**Solutions**:
- Ensure only one archiving process runs at a time
- Consider PostgreSQL for production

### Issue: Missing dependencies

**Solution**:
```bash
pip install -r requirements.txt
```

## Development

### Testing

```bash
# Run with verbose logging
export LOG_LEVEL=DEBUG
python -m src.cli.archive_cli archive
```

### Adding New Feeds

1. Add feed to `config/rss_feeds.json`
2. Set correct `pagination_type`
3. Run archive command
4. Check logs for issues

## License

See LICENSE file in repository root.

## Contact

For issues and questions, please refer to the project documentation.
