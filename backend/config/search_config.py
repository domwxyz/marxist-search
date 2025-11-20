"""
Configuration settings for the Marxist search engine.
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "cache").mkdir(exist_ok=True)
(DATA_DIR / "txtai").mkdir(exist_ok=True)

# Database paths
DATABASE_PATH = str(DATA_DIR / "articles.db")
INDEX_PATH = str(DATA_DIR / "txtai")
CACHE_PATH = str(DATA_DIR / "cache")

# Configuration file paths
RSS_FEEDS_CONFIG = str(CONFIG_DIR / "rss_feeds.json")
TERMS_CONFIG = str(CONFIG_DIR / "terms_config.json")
ANALYTICS_CONFIG = str(CONFIG_DIR / "analytics_config.json")

# txtai Configuration
TXTAI_CONFIG = {
    "path": "BAAI/bge-small-en-v1.5",
    "content": True,
    "keyword": True,
    "columns": {
        "id": "INTEGER PRIMARY KEY",
        "article_id": "INTEGER",
        "title": "TEXT",
        "url": "TEXT",
        "source": "TEXT",
        "author": "TEXT",
        "published_date": "DATETIME",
        "published_year": "INTEGER",
        "published_month": "INTEGER",
        "word_count": "INTEGER",
        "is_chunk": "BOOLEAN",
        "terms": "TEXT",
        "tags": "TEXT"
    }
    # Note: Removed faiss configuration to avoid nflip compatibility issues
    # txtai will use its default index configuration which is compatible
}

# Chunking Configuration
CHUNKING_CONFIG = {
    "threshold_words": 3500,
    "chunk_size_words": 1000,
    "overlap_words": 200,
    "prefer_section_breaks": True,
    "section_markers": ["##", "###", "\n\n"]
}

# Search Configuration
SEARCH_CONFIG = {
    "semantic_weight": 0.7,
    "bm25_weight": 0.3,
    "recency_boost": {
        "30_days": 0.05,
        "90_days": 0.02,
        "1_year": 0.01
    }
}

# Content Extraction Configuration
CONTENT_CONFIG = {
    "min_content_length": 200,
    "fetch_timeout": 30,
    "user_agent": "Mozilla/5.0 (compatible; MarxistSearchBot/1.0)"
}

# RSS Configuration
RSS_CONFIG = {
    "poll_interval_minutes": 30,
    "concurrent_fetches": 5,
    "timeout_seconds": 30,
    "failure_threshold_degraded": 3,
    "failure_threshold_failing": 10,
    "respect_robots_txt": True
}

# Concurrency Configuration
CONCURRENCY_CONFIG = {
    "uvicorn_workers": 1,
    "search_thread_pool_size": 4,
    "max_concurrent_searches": 10,
    "search_timeout_seconds": 5.0,
    "rss_concurrent_fetches": 5
}

# Logging Configuration
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

# API Configuration
API_CONFIG = {
    "host": os.getenv("API_HOST", "0.0.0.0"),
    "port": int(os.getenv("API_PORT", "8000")),
    "reload": os.getenv("RELOAD", "false").lower() == "true",
    "log_level": LOG_LEVEL.lower()
}

# Development/Production mode
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
