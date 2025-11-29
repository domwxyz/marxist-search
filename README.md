# Marxist Search Engine

A semantic search engine for Marxist theoretical and analytical articles from the Revolutionary Communist International (RCI) and related organizations. Enables natural language search across a 25-year corpus of ~16,000 articles using vector embeddings and hybrid search.

## Features

- **Semantic Search**: Natural language queries using BAAI/bge-base-en-v1.5 embeddings with custom multi-signal reranking
- **Advanced Search Syntax**: Power-user syntax with exact phrase matching (`"quoted text"`), title search (`title:"text"`), and author filtering (`author:"Name"`)
- **RSS Archiving**: Automated fetching from multiple RSS feeds with CMS-specific pagination (WordPress, Joomla)
- **Content Extraction**: Full-text extraction from RSS feeds and web pages using trafilatura
- **Special Term Extraction**: Automatic extraction of Marxist terms across 6 categories (people, organizations, concepts, geographic, historical events, movements)
- **Query Expansion**: Synonym support with synonym groups and alias resolution (e.g., "USSR" → "Soviet Union")
- **Advanced Filtering**: Search by date range (including decade-specific: 1990s, 2000s, 2010s, 2020s), source, and author
- **Search Analytics**: Track search queries, term usage, and result patterns
- **Incremental Updates**: Automated RSS polling and index updates every 30 minutes via systemd timer
- **Modern UI**: React frontend with responsive design and TailwindCSS
- **Production Ready**: Complete deployment automation with systemd, nginx, and SSL support

## Technology Stack

**Backend**:
- Python 3.11+ with FastAPI
- txtai (vector embeddings only, content=False) with BAAI/bge-base-en-v1.5 embeddings
- SQLite (metadata and full content storage)
- feedparser (RSS parsing) + trafilatura (web scraping)
- Click CLI with Rich formatting

**Frontend**:
- React 19 + TailwindCSS 3
- Create React App build system
- Responsive design

**Deployment**:
- Systemd services (API + automated updates)
- Nginx reverse proxy
- Let's Encrypt SSL

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Node.js 14+ and npm
- Virtual environment (recommended)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/marxist-search.git
   cd marxist-search
   ```

2. **Set up backend**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Initialize database**:
   ```bash
   python -m src.cli.marxist_cli init-db
   ```

4. **Archive articles from RSS feeds**:
   ```bash
   # Archive all configured feeds (~16,000 articles, may take 30-60 minutes)
   python -m src.cli.marxist_cli archive run
   ```

5. **Build search index**:
   ```bash
   # Generate embeddings and build txtai index
   python -m src.cli.marxist_cli index build
   ```

6. **Set up frontend**:
   ```bash
   cd ../frontend
   npm install
   cp .env.example .env
   # Edit .env to configure API URL if needed
   ```

### Running the Application

**Backend (Terminal 1)**:
```bash
cd backend
source venv/bin/activate
python -m src.api.main
# API available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

**Frontend (Terminal 2)**:
```bash
cd frontend
npm start
# Opens at http://localhost:3000
```

### CLI Commands

```bash
# Database initialization
python -m src.cli.marxist_cli init-db

# Archiving
python -m src.cli.marxist_cli archive run              # Archive all feeds
python -m src.cli.marxist_cli archive update           # Incremental update
python -m src.cli.marxist_cli archive list             # List configured feeds

# Indexing
python -m src.cli.marxist_cli index build              # Build index
python -m src.cli.marxist_cli index update             # Update index with new articles
python -m src.cli.marxist_cli index info               # Index statistics

# Search
python -m src.cli.marxist_cli search "climate change"
python -m src.cli.marxist_cli search "imperialism" --author "Alan Woods"
python -m src.cli.marxist_cli search "palestine" --date-range past_year

# Advanced search syntax
python -m src.cli.marxist_cli search '"permanent revolution"'              # Exact phrase
python -m src.cli.marxist_cli search 'title:"Labour Theory"'               # Title search
python -m src.cli.marxist_cli search 'author:"Alan Woods"'                 # Author filter
python -m src.cli.marxist_cli search 'title:"Theory" author:"Woods" capitalism'  # Combined

# Statistics
python -m src.cli.marxist_cli stats                    # Comprehensive statistics
```

## Advanced Search Syntax

The search engine supports power-user syntax for precise queries:

### Exact Phrase Search
Use double quotes to search for exact phrases in article content:
```
"permanent revolution"
```

### Title Search
Search only in article titles using `title:`:
```
title:"The Labour Theory"
```

### Author Filter
Filter by specific author using `author:`:
```
author:"Alan Woods"
```

### Combined Queries
Combine multiple syntax elements with regular semantic search:
```
title:"Theory" author:"Woods" capitalism
"dialectical materialism" USSR title:"Revolution"
```

**Syntax Rules**:
- `"text"` - Exact phrase match in content (uses whole-word boundaries)
- `title:"text"` - Search in article titles only
- `author:"Name"` - Filter by author
- Regular words use semantic search (similar meaning)
- All syntax elements can be combined in a single query

## Project Structure

```
marxist-search/
├── backend/                    # Python backend
│   ├── src/
│   │   ├── ingestion/         # RSS fetching, content extraction, term extraction
│   │   ├── indexing/          # Embedding generation, chunking, txtai management
│   │   ├── search/            # Search engine, filters, analytics
│   │   ├── api/               # FastAPI application and routes
│   │   ├── cli/               # Command-line interface
│   │   └── scripts/           # Automation scripts (incremental updates)
│   ├── config/
│   │   ├── rss_feeds.json     # RSS feed configuration (3 sources)
│   │   ├── terms_config.json  # Special terms, synonyms, aliases
│   │   └── search_config.py   # Application settings
│   ├── data/                  # Data directory (gitignored)
│   │   ├── articles.db        # SQLite database
│   │   └── txtai/             # Vector index
│   └── requirements.txt
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/        # UI components (SearchBar, Filters, Results, etc.)
│   │   ├── hooks/             # Custom React hooks (useSearch, useFilters)
│   │   └── utils/             # API client
│   ├── public/                # Static assets (logo, favicon)
│   └── package.json
├── deployment/                 # Deployment automation
│   ├── deploy.sh              # Automated deployment script
│   ├── systemd/               # Systemd service files
│   │   ├── marxist-search-api.service
│   │   ├── marxist-search-update.service
│   │   └── marxist-search-update.timer
│   ├── scripts/               # Health check, backup
│   └── nginx.conf             # Nginx configuration
└── README.md
```

## Configuration

### RSS Feeds

Edit `backend/config/rss_feeds.json` to configure RSS sources:

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
    }
  ]
}
```

**Pagination Types**:
- `wordpress`: WordPress-style (`?paged=N`)
- `joomla`: Joomla-style (`?format=feed&limitstart=N`)
- `standard`: No pagination

### Special Terms

Edit `backend/config/terms_config.json` to configure term extraction:

```json
{
  "synonyms": {
    "proletariat": ["working class", "workers", "wage laborers"],
    "bourgeoisie": ["capitalist class", "ruling class", "capitalists"]
  },
  "terms": {
    "people": ["Karl Marx", "Friedrich Engels", "Leon Trotsky"],
    "organizations": ["IMT", "RCI", "NATO"],
    "concepts": ["permanent revolution", "dialectical materialism"]
  },
  "aliases": {
    "UN": "United Nations",
    "USSR": "Soviet Union"
  }
}
```

The system automatically extracts terms from articles, resolves aliases, tracks occurrences, and uses them for query expansion.

### Search Configuration

Edit `backend/config/search_config.py` for advanced settings:

- **Chunking**: Threshold (3500 words), chunk size (1000 words), overlap (200 words), paragraph-boundary preservation
- **Search Strategy**: Pure semantic search (100%) - BM25 disabled to prevent index corruption during incremental updates
- **Title Weighting**: 5x repetition for semantic relevance (applied during indexing)
- **Custom Reranking**: Multi-signal reranking applied after semantic search
  - Title term boost (max +0.08): Rewards results where query terms appear in title
  - Keyword frequency boost (max +0.06): Pseudo-BM25 on top 150 candidates using log-scaled term frequency
  - Recency boost: Additive boosts (+0.07 for 7 days, +0.05 for 30 days, +0.03 for 90 days, +0.02 for 1 year, +0.01 for 3 years)
- **txtai Configuration**: numpy backend (CPU-only, exact search), content storage disabled (content=False)
- **Content Storage**: All content stored in SQLite (articles.db), fetched on-demand for final results only
- **Environment Variables**: DATA_DIR, DATABASE_PATH, INDEX_PATH can be overridden for production deployments

## API Endpoints

- `POST /api/v1/search` - Search articles with filters
- `GET /api/v1/top-authors` - Get top authors by article count
- `GET /api/v1/sources` - List all article sources
- `GET /api/v1/stats` - Database and index statistics
- `GET /api/v1/health` - Health check endpoint

Full API documentation available at `http://localhost:8000/docs` when backend is running.

## Deployment

### Automated Deployment

```bash
cd deployment
sudo ./deploy.sh yourdomain.com
```

The deployment script:
- Installs system dependencies (Python 3.11, nginx, Node.js)
- Creates application user and directory structure
- Builds backend virtual environment
- Builds frontend production bundle
- Configures nginx reverse proxy
- Sets up systemd services
- Configures SSL with Let's Encrypt
- Sets up firewall (UFW)
- Configures log rotation

### Systemd Services

**API Service**: Runs FastAPI backend with uvicorn
```bash
sudo systemctl start marxist-search-api
sudo systemctl enable marxist-search-api
```

**Automated Updates**: Runs incremental updates every 30 minutes
```bash
sudo systemctl start marxist-search-update.timer
sudo systemctl enable marxist-search-update.timer
```

The update timer automatically:
1. Fetches new articles from RSS feeds
2. Extracts special terms
3. Updates the txtai index
4. Logs to `/var/log/news-search/ingestion.log`

## Architecture Highlights

### Search Architecture

Pure semantic search with custom multi-signal reranking:
- **Semantic Search (100%)**: Vector similarity using bge-base-en-v1.5 embeddings
  - BM25 disabled in txtai to prevent index corruption during incremental updates
  - Content not stored in txtai (content=False) - fetched from SQLite instead
- **Title Weighting**: Titles repeated 5x in embeddings for better relevance (only applied to first chunk of multi-chunk articles)
- **Query Expansion**: Synonym groups and aliases automatically expand queries
- **Custom Reranking**: Multi-signal scoring applied after semantic search
  - **Title Term Boost**: Rewards results where query terms appear in title (+0.08 max)
  - **Keyword Frequency Boost**: Pseudo-BM25 on top 150 candidates using log-scaled term frequency (+0.06 max)
  - **Recency Boosting**: Additive score boosts for recent articles (7 days: +0.07, 30 days: +0.05, 90 days: +0.03, 1 year: +0.02, 3 years: +0.01)

### Chunking Strategy

Long articles (>3500 words) are automatically chunked:
- Paragraph-boundary preservation for context
- 1000-word chunks with 200-word overlap
- Smart deduplication returns highest-scoring chunk per article

### Pagination Support

RSS fetcher handles different CMS types:
- **WordPress**: `?paged=N` pagination
- **Joomla**: `?format=feed&limitstart=N` pagination
- **Standard**: Checks for `<link rel="next">` tags

### Content Extraction

Intelligent full-text extraction:
1. Check RSS feed for full content (>200 chars)
2. Fallback to web scraping with trafilatura
3. Extract metadata (title, author, date, tags)
4. Normalize text before storage

### Database Schema

- **articles**: Full content, metadata, extracted terms, embedding version (16,000+ rows)
- **article_chunks**: Chunks for long articles with start position tracking
- **rss_feeds**: Feed status, health tracking, ETags, and last modified timestamps
- **author_stats**: Article counts and date ranges per author
- **term_mentions**: Special term occurrences for analytics
- **search_logs**: Search query logging for analytics

## Performance

- **Query Latency**: <200ms (95th percentile with numpy backend)
- **Concurrent Users**: 10-20 simultaneous users
- **Index Size**: ~2GB in RAM
- **Database Size**: ~200MB (SQLite)
- **Throughput**: 200-300 queries/minute
- **Update Frequency**: Every 30 minutes (systemd timer)

## Troubleshooting

### FAISS AttributeError: 'IndexIVFFlat' object has no attribute 'nflip'

**Solution**: The project uses numpy backend to avoid FAISS compatibility issues:

```bash
cd backend
rm -rf data/txtai
python -m src.cli.marxist_cli index build
```

The numpy backend provides CPU-only exact search without FAISS dependencies.

### Database Locked Error

**Cause**: SQLite doesn't support high concurrency

**Solution**: Ensure only one process accesses the database at a time. For production with high concurrency, consider PostgreSQL.

### Slow Search Performance

**Solutions**:
- Ensure index is loaded into RAM
- Check `search_thread_pool_size` in config
- Consider switching to `hnsw` backend for faster approximate search (requires hnswlib)

### Out of Memory During Indexing

**Solutions**:
- Index in smaller batches
- Increase system RAM
- Use a machine with more memory for initial indexing

## Documentation

- **Technical Design**: See `marxist_search_design.txt` for complete architecture
- **Backend README**: See `backend/README.md` for detailed backend documentation
- **Frontend README**: See `frontend/README.md` for frontend documentation
- **Deployment Guide**: See `deployment/deployment_guide.txt` for comprehensive deployment instructions

## Contributing

This is currently a private project. For questions or issues, please refer to the technical design document.

## License

See LICENSE file for details.

## Acknowledgments

Built for searching the theoretical and analytical work of the Revolutionary Communist International (RCI) and related organizations.
