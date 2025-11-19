# Marxist Search Engine

A RAG-based semantic search engine for Marxist theoretical and analytical articles from the Revolutionary Communist International (RCI) and related organizations.

## Overview

This project implements a lightweight, cost-effective search engine for a 25-year corpus of Marxist articles (~16,000 articles). The system enables users to search across news content and retrieve relevant articles using semantic search powered by vector embeddings.

### Key Features

- **Semantic Search**: Natural language queries using BAAI/bge-small-en-v1.5 embeddings
- **RSS Archiving**: Automated fetching from multiple RSS feeds with pagination support
- **Content Extraction**: Intelligent full-text extraction using feedparser and trafilatura
- **Text Normalization**: Clean and prepare content for accurate indexing
- **Cost Efficient**: No LLM hosting costs, runs on single DigitalOcean droplet
- **Fast**: Sub-second query response times with concurrent user support

### Technology Stack

**Backend**:
- Python 3.11+
- FastAPI (API server)
- txtai (vector search)
- SQLite (metadata storage)
- feedparser (RSS parsing)
- trafilatura (web scraping)
- BAAI/bge-small-en-v1.5 (embeddings)

**Frontend**:
- React 18+
- Create React App
- TailwindCSS 3
- Fetch API

## Project Status

### ✅ Completed: Archiving Services

The article archiving system is fully implemented and functional:

- **RSS Feed Fetcher**: Concurrent fetching with WordPress/Joomla pagination support
- **Content Extractor**: Intelligent full-text extraction from RSS or web
- **Text Normalizer**: Comprehensive text cleaning and normalization
- **Database Schema**: Complete SQLite schema with proper indexing
- **Article Storage**: Batch saving with duplicate detection
- **Archiving Orchestrator**: End-to-end pipeline from RSS to database

### ✅ Completed: Embedding & Indexing Services

The embedding and indexing system is fully implemented:

- **Article Chunking**: Intelligent chunking of long articles (>3,500 words) with paragraph-boundary preservation
- **txtai Manager**: Complete txtai integration with BAAI/bge-small-en-v1.5 embeddings
- **Hybrid Search**: Semantic + BM25 keyword search support
- **Indexing Service**: End-to-end pipeline from database to searchable index
- **General Purpose CLI**: Comprehensive command-line interface for all operations

### ✅ Completed: Search Engine & API

The search functionality is fully implemented:

- **Search Engine Service**: Core search with filtering, deduplication, and recency boosting
- **Filter System**: Support for date ranges, source, author, and custom filters
- **Smart Deduplication**: Groups article chunks and returns highest-scoring matches
- **FastAPI REST API**: Complete REST API with all endpoints
- **CLI Search Command**: Test search functionality from command line
- **Thread-Safe Operations**: Concurrent search handling with thread pool

### ✅ Completed: Frontend

The React frontend is fully implemented:

- **Search Interface**: Clean, responsive search bar with debounced input
- **Advanced Filters**: Source, author, and date range filtering
- **Results Display**: Formatted article cards with metadata
- **Pagination**: Configurable page size (10/25/50/100) with navigation
- **Statistics Dashboard**: Real-time index statistics
- **Error Handling**: User-friendly error messages
- **API Integration**: Full integration with FastAPI backend

### 🚧 TODO: Remaining Components

- **Term Extraction**: Extract and track special terms/entities
- **Incremental Updates**: Automated RSS polling and index updates (partially complete)
- **Deployment**: Production deployment scripts

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip
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
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up frontend**:
   ```bash
   cd frontend
   npm install
   cp .env.example .env
   # Edit .env to configure API URL if needed
   ```

4. **Initialize database**:
   ```bash
   cd backend
   python -m src.cli.archive_cli init-db
   ```

### Usage

The Marxist Search CLI provides commands for archiving and indexing:

#### Archive Articles from RSS Feeds

```bash
# Initialize database
python -m src.cli.marxist_cli init-db

# Archive all configured feeds
python -m src.cli.marxist_cli archive run

# Archive a specific feed
python -m src.cli.marxist_cli archive run --feed-url "https://www.marxist.com/rss.xml"

# List configured feeds
python -m src.cli.marxist_cli archive list
```

#### Build Search Index

```bash
# Build txtai vector index from archived articles
python -m src.cli.marxist_cli index build

# View index information
python -m src.cli.marxist_cli index info

# View comprehensive statistics
python -m src.cli.marxist_cli stats
```

#### Search Articles

```bash
# Basic search
python -m src.cli.marxist_cli search "climate change"

# Search with filters
python -m src.cli.marxist_cli search "revolution" --source "In Defence of Marxism"
python -m src.cli.marxist_cli search "capitalism" --date-range past_year --limit 20
python -m src.cli.marxist_cli search "imperialism" --author "Alan Woods"

# Custom date range
python -m src.cli.marxist_cli search "palestine" --start-date 2023-01-01 --end-date 2024-12-31
```

#### Run the Application

**Backend (FastAPI Server)**:
```bash
cd backend
# Development server
python -m src.api.main

# Or use uvicorn directly
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Access API documentation at http://localhost:8000/docs
```

**Frontend (React App)**:
```bash
cd frontend
# Development server (hot reload)
npm start
# Opens at http://localhost:3000

# Production build
npm run build
# Creates optimized build in build/ folder
```

**API Endpoints**:
- `POST /api/v1/search` - Search articles with filters
- `GET /api/v1/top-authors` - Get top authors by article count
- `GET /api/v1/sources` - List all article sources
- `GET /api/v1/stats` - Get index statistics
- `GET /api/v1/health` - Health check endpoint

**Complete Workflow**:
1. Initialize database: `python -m src.cli.marxist_cli init-db`
2. Archive articles: `python -m src.cli.marxist_cli archive run`
3. Build index: `python -m src.cli.marxist_cli index build`
4. Start backend: `python -m src.api.main`
5. Start frontend: `npm start` (in frontend directory)
6. Open http://localhost:3000 in browser

## Project Structure

```
marxist-search/
├── backend/                    # Backend services
│   ├── src/
│   │   ├── ingestion/         # RSS fetching and archiving
│   │   ├── indexing/          # Embedding and indexing
│   │   ├── search/            # Search functionality
│   │   ├── api/               # FastAPI endpoints
│   │   └── cli/               # Command-line tools
│   ├── config/                # Configuration files
│   │   ├── rss_feeds.json     # RSS feed configuration
│   │   └── search_config.py   # Application settings
│   ├── data/                  # Data directory (gitignored)
│   ├── requirements.txt
│   └── README.md
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── hooks/             # Custom hooks
│   │   ├── utils/             # API client
│   │   ├── App.js             # Main app
│   │   └── index.js           # Entry point
│   ├── public/                # Static assets
│   ├── package.json
│   └── README.md
├── marxist_search_design.txt  # Technical design document
├── LICENSE
└── README.md
```

## Configuration

### RSS Feeds

Edit `backend/config/rss_feeds.json` to configure RSS feeds:

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
- `wordpress`: WordPress-style pagination
- `joomla`: Joomla-style pagination
- `standard`: No pagination

## Documentation

- **Technical Design**: See `marxist_search_design.txt` for complete system architecture
- **Backend README**: See `backend/README.md` for detailed backend documentation
- **Frontend README**: See `frontend/README.md` for frontend documentation
- **API Documentation**: Available at `http://localhost:8000/docs` when backend is running

## Development Roadmap

### Phase 1: Archiving ✅ (Completed)
- [x] RSS feed fetching with pagination
- [x] Content extraction from RSS and web
- [x] Text normalization and cleaning
- [x] Database schema and storage
- [x] CLI tools for testing

### Phase 2: Indexing ✅ (Completed)
- [x] Article chunking for long documents
- [x] Embedding generation with bge-small-en-v1.5
- [x] txtai index creation and management
- [x] General purpose CLI
- [ ] Incremental index updates
- [ ] Special term extraction

### Phase 3: Search ✅ (Completed)
- [x] Search engine implementation
- [x] Filtering by date, source, author
- [x] Result ranking and deduplication
- [x] FastAPI endpoints
- [x] CLI search command
- [x] Thread-safe concurrent search
- [ ] Search performance optimization (can be done later)

### Phase 4: Frontend ✅ (Completed)
- [x] React application setup (Create React App + TailwindCSS)
- [x] Search interface with debouncing
- [x] Filter components (source, author, date)
- [x] Results display with metadata
- [x] Pagination with configurable page size
- [x] Statistics dashboard
- [x] API integration
- [x] Error handling

### Phase 5: Deployment 📋 (Planned)
- [ ] Production configuration
- [ ] Nginx setup
- [ ] Systemd services
- [ ] Monitoring and logging
- [ ] Backup strategy

## Architecture Highlights

### Pagination Support

The RSS fetcher intelligently handles different CMS types:

- **WordPress**: Automatically paginates through `?paged=N` URLs
- **Joomla**: Uses `?format=feed&limitstart=N` pagination
- **Standard**: Checks for RSS `<link rel="next">` tags

### Content Extraction Strategy

1. Check if RSS feed contains full content (>200 characters)
2. If only summary available, fetch full text from URL using trafilatura
3. Extract metadata (title, author, date, tags) from RSS
4. Normalize all text before storage

### Database Design

- **Articles**: Full content and metadata
- **Article Chunks**: Chunks for long articles (>3500 words)
- **RSS Feeds**: Feed status and health tracking
- **Author Stats**: Article counts and date ranges
- **Term Mentions**: Special term occurrences (for future analytics)

## Performance Targets

- **Single query latency**: <100ms (95th percentile)
- **Concurrent users**: 10-20 simultaneous users
- **Index size**: ~2GB in RAM
- **Database size**: ~200MB (SQLite)
- **Throughput**: 200-300 queries/minute

## Contributing

This is currently a private project. For questions or issues, please refer to the technical design document.

## License

See LICENSE file for details.

## Acknowledgments

Based on the theoretical and analytical work of the Revolutionary Communist International (RCI) and related organizations.
