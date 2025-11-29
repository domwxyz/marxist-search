"""
Configuration settings for the Marxist search engine.
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"

# Data directory - use environment variable in production, local path in development
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "cache").mkdir(exist_ok=True)
(DATA_DIR / "txtai").mkdir(exist_ok=True)

# Database paths - support environment variable overrides for production
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "articles.db"))
INDEX_PATH = os.getenv("INDEX_PATH", str(DATA_DIR / "txtai"))
CACHE_PATH = os.getenv("CACHE_PATH", str(DATA_DIR / "cache"))

# Configuration file paths
RSS_FEEDS_CONFIG = str(CONFIG_DIR / "rss_feeds.json")
TERMS_CONFIG = str(CONFIG_DIR / "terms_config.json")
ANALYTICS_CONFIG = str(CONFIG_DIR / "analytics_config.json")


# EMBEDDING MODEL CONFIGURATION

# Model: nomic-ai/nomic-embed-text-v1.5
# Context window: 8192 tokens (~6000 words)
# Dimensions: 768
# 
# IMPORTANT: This model requires task instruction prefixes!
# Documents: "search_document: <text>"
# Queries:   "search_query: <text>"

TXTAI_CONFIG = {
    # Nomic embed model with 8192 token context window
    "path": "nomic-ai/nomic-embed-text-v1.5",
    
    # Disable content storage - content fetched from articles.db
    # This eliminates txtai's internal SQLite database entirely
    "content": False,
    
    # Disable BM25 keyword search to prevent index corruption during upserts
    # Pure semantic search is used; exact phrase matching handled separately
    "keyword": False,
    
    # Use numpy backend for CPU-only exact search
    # More reliable than FAISS, no additional dependencies needed
    "backend": "numpy",
    
    # Trust remote code (required for nomic model)
    "trust_remote_code": True
}


# NOMIC MODEL TASK PREFIXES (CRITICAL!)
#
# The nomic model requires specific prefixes for documents and queries.
# Without these, the embeddings won't be in the same semantic space!

# Prefix for documents when indexing
EMBEDDING_PREFIX_DOCUMENT = "search_document: "

# Prefix for queries when searching  
EMBEDDING_PREFIX_QUERY = "search_query: "


# CHUNKING CONFIGURATION
#
# Updated to match nomic model's 8192 token (~6000 word) context window
# 
# Content distribution:
#   - Podcast summaries: 300-500 words    → Single unit (100% embedded)
#   - Short reports:     800-1200 words   → Single unit (100% embedded)
#   - Typical articles:  1500-2500 words  → Single unit (100% embedded)
#   - Long analysis:     3500-5500 words  → Single unit (100% embedded)
#   - Alan Woods epic:   30,000 words     → ~15 chunks (each 100% embedded)

CHUNKING_CONFIG = {
    # Chunk articles longer than this (words)
    # Set to 5500 to stay safely under 6000 word model capacity
    "threshold_words": 5500,
    
    # Target chunk size (words)
    # Larger chunks now useful since model can handle them
    "chunk_size_words": 2000,
    
    # Overlap between chunks (words)
    # ~15% overlap maintains context continuity at boundaries
    "overlap_words": 300,
    
    # Try to break on paragraph boundaries for cleaner chunks
    "prefer_section_breaks": True,
    
    # Section break markers (in priority order)
    "section_markers": ["##", "###", "\n\n"]
}


# SEARCH CONFIGURATION

SEARCH_CONFIG = {
    # Pure semantic search with nomic embeddings
    # BM25 disabled to prevent index corruption during incremental updates
    # Exact phrase matching handled via SQLite queries
    "semantic_weight": 1.0,
    "bm25_weight": 0.0,
    
    # Recency boost (additive, not multiplicative)
    # Recent articles get a small score bump
    "recency_boost": {
        "7_days": 0.07,
        "30_days": 0.05,
        "90_days": 0.03,
        "1_year": 0.02,
        "3_years": 0.01
    }
}


# RERANKING CONFIGURATION
#
# Applied after semantic search to boost results with query term matches

RERANKING_CONFIG = {
    # Title term boost: rewards results where query terms appear in title
    "title_boost_max": 0.08,
    
    # Keyword frequency boost: pseudo-BM25 on top candidates
    "keyword_boost_max": 0.06,
    "keyword_boost_scale": 0.02,
    "keyword_rerank_top_n": 150,
    
    # Skip keyword boost for very long queries (performance)
    "keyword_max_query_terms": 5,
}


# TITLE WEIGHTING
#
# Prepend article title N times to content before embedding
# This weights title matching in semantic search results
# 
# With nomic's larger context, the title still gets priority but
# the full article content is also captured.
#
# Only applies to:
#   - Non-chunked articles (always)
#   - First chunk of chunked articles (chunk_index=0)

TITLE_WEIGHT_MULTIPLIER = 5


# CONTENT EXTRACTION

CONTENT_CONFIG = {
    "min_content_length": 200,
    "fetch_timeout": 30,
    "user_agent": "Mozilla/5.0 (compatible; MarxistSearchBot/1.0)"
}


# RSS CONFIGURATION

RSS_CONFIG = {
    "poll_interval_minutes": 30,
    "concurrent_fetches": 5,
    "timeout_seconds": 30,
    "failure_threshold_degraded": 3,
    "failure_threshold_failing": 10,
    "respect_robots_txt": True
}


# CONCURRENCY CONFIGURATION

CONCURRENCY_CONFIG = {
    "uvicorn_workers": 3,
    "search_thread_pool_size": 4,
    "max_concurrent_searches": 24,
    "search_timeout_seconds": 5.0,
    "rss_concurrent_fetches": 5
}


# LOGGING CONFIGURATION

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path("/var/log/news-search") if os.path.exists("/var/log/news-search") else BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        },
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": "standard",
            "stream": "ext://sys.stdout"
        },
        "api": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "api.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "json",
            "level": LOG_LEVEL
        },
        "ingestion": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "ingestion.log"),
            "maxBytes": 10485760,
            "backupCount": 5,
            "formatter": "json",
            "level": LOG_LEVEL
        },
        "search": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "search.log"),
            "maxBytes": 10485760,
            "backupCount": 5,
            "formatter": "json",
            "level": LOG_LEVEL
        },
        "errors": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "errors.log"),
            "maxBytes": 10485760,
            "backupCount": 5,
            "formatter": "json",
            "level": "ERROR"
        }
    },
    "loggers": {
        "api": {
            "handlers": ["console", "api", "errors"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "ingestion": {
            "handlers": ["console", "ingestion", "errors"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "search": {
            "handlers": ["console", "search", "errors"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "": {  # Root logger
            "handlers": ["console", "errors"],
            "level": LOG_LEVEL
        }
    }
}


# API CONFIGURATION

API_CONFIG = {
    "host": os.getenv("API_HOST", "0.0.0.0"),
    "port": int(os.getenv("API_PORT", "8000")),
    "reload": os.getenv("RELOAD", "false").lower() == "true",
    "log_level": LOG_LEVEL.lower()
}


# ENVIRONMENT

DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
