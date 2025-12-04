"""
FastAPI route handlers for search API.
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse

from .models import (
    SearchRequest,
    SearchResponse,
    AuthorsResponse,
    SourcesResponse,
    StatsResponse,
    HealthResponse,
    ErrorResponse
)
from src.search.search_engine import SearchEngine
from config.search_config import CONCURRENCY_CONFIG

logger = logging.getLogger('api')

# Thread pool for CPU-bound search operations
search_executor = ThreadPoolExecutor(
    max_workers=CONCURRENCY_CONFIG['search_thread_pool_size']
)

# Global search engine instance (loaded on startup)
search_engine: SearchEngine = None

# Track service start time
service_start_time = datetime.now()


# ============================================================================
# Dependency Injection
# ============================================================================

def get_search_engine() -> SearchEngine:
    """Get the global search engine instance."""
    if search_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Search engine not initialized"
        )
    return search_engine


# ============================================================================
# API Router
# ============================================================================

router = APIRouter(prefix="/api/v1", tags=["search"])


# ============================================================================
# Search Endpoints
# ============================================================================

@router.post("/search", response_model=SearchResponse)
async def search_articles(
    request: SearchRequest,
    engine: SearchEngine = Depends(get_search_engine)
):
    """
    Execute semantic search with filters.

    Performs hybrid search (semantic + BM25) with optional filtering by:
    - Source
    - Author
    - Date range
    - Year

    Returns deduplicated results with relevance scores and excerpts.
    """
    try:
        logger.info(
            f"Search request: query='{request.query}', "
            f"filters={request.filters.dict(exclude_none=True)}, "
            f"limit={request.limit}, offset={request.offset}"
        )

        # Convert filters to dictionary
        filters_dict = request.filters.dict(exclude_none=True) if request.filters else {}

        # Offload CPU-bound search to thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            search_executor,
            lambda: engine.search(
                query=request.query,
                filters=filters_dict,
                limit=request.limit,
                offset=request.offset
            )
        )

        logger.info(
            f"Search completed: {result['total']} total results, "
            f"{len(result['results'])} returned, "
            f"{result['query_time_ms']}ms"
        )

        return result

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Search execution failed",
                "code": "SEARCH_FAILED",
                "details": {"message": str(e)}
            }
        )


# ============================================================================
# Author Endpoints
# ============================================================================

@router.get("/top-authors", response_model=AuthorsResponse)
async def get_top_authors(
    min_articles: int = Query(10, ge=1, description="Minimum article count"),
    limit: int = Query(15, ge=1, le=100, description="Maximum authors to return"),
    engine: SearchEngine = Depends(get_search_engine)
):
    """
    Get top authors by article count.

    Returns authors with at least `min_articles` articles,
    ordered by article count (descending).
    """
    try:
        logger.info(f"Fetching top authors: min_articles={min_articles}, limit={limit}")

        # Offload to thread pool
        loop = asyncio.get_event_loop()
        authors = await loop.run_in_executor(
            search_executor,
            lambda: engine.get_top_authors(min_articles=min_articles, limit=limit)
        )

        logger.info(f"Retrieved {len(authors)} authors")

        return {
            "authors": authors,
            "total": len(authors)
        }

    except Exception as e:
        logger.error(f"Failed to fetch authors: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to fetch authors",
                "code": "AUTHORS_FAILED",
                "details": {"message": str(e)}
            }
        )


# ============================================================================
# Source Endpoints
# ============================================================================

@router.get("/sources", response_model=SourcesResponse)
async def get_sources(
    engine: SearchEngine = Depends(get_search_engine)
):
    """
    Get list of all article sources.

    Returns all sources with article counts and date ranges.
    """
    try:
        logger.info("Fetching sources")

        # Offload to thread pool
        loop = asyncio.get_event_loop()
        sources = await loop.run_in_executor(
            search_executor,
            lambda: engine.get_sources()
        )

        logger.info(f"Retrieved {len(sources)} sources")

        return {
            "sources": sources,
            "total": len(sources)
        }

    except Exception as e:
        logger.error(f"Failed to fetch sources: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to fetch sources",
                "code": "SOURCES_FAILED",
                "details": {"message": str(e)}
            }
        )


# ============================================================================
# Statistics Endpoints
# ============================================================================

@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    engine: SearchEngine = Depends(get_search_engine)
):
    """
    Get index and database statistics.

    Returns:
    - Total articles
    - Indexed articles
    - Total chunks
    - Date range
    - Source count
    - Index document count
    """
    try:
        logger.info("Fetching statistics")

        # Offload to thread pool
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(
            search_executor,
            lambda: engine.get_stats()
        )

        logger.info(f"Statistics retrieved: {stats['indexed_articles']} indexed articles")

        return stats

    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to fetch statistics",
                "code": "STATS_FAILED",
                "details": {"message": str(e)}
            }
        )


# ============================================================================
# Health Check Endpoint
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check(
    engine: SearchEngine = Depends(get_search_engine)
):
    """
    Health check endpoint.

    Returns service status and basic metrics.
    """
    try:
        # Calculate uptime
        uptime = (datetime.now() - service_start_time).total_seconds()

        # Check index status
        index_loaded = engine.embeddings is not None
        index_count = engine.embeddings.count() if index_loaded else 0

        # Check database connection
        db_connected = False
        try:
            engine.connect_db()
            db_connected = engine.db_conn is not None
        except Exception:
            pass

        status = "healthy" if (index_loaded and db_connected) else "degraded"

        return {
            "status": status,
            "index_loaded": index_loaded,
            "index_document_count": index_count,
            "database_connected": db_connected,
            "uptime_seconds": int(uptime)
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


# ============================================================================
# Index Reload Endpoint
# ============================================================================

@router.post("/reload-index")
async def reload_index(
    engine: SearchEngine = Depends(get_search_engine)
):
    """
    Reload txtai index from disk to pick up incremental updates.

    This endpoint should be called after the incremental update service
    adds new articles to the index on disk. It refreshes the in-memory
    index without restarting the API.

    Returns:
        Statistics about the reload (old count, new count, documents added)
    """
    try:
        logger.info("Received index reload request")

        # Offload to thread pool (reload is thread-safe but CPU-bound)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            search_executor,
            lambda: engine.reload_index()
        )

        logger.info(
            f"Index reload complete: {result['old_count']} -> {result['new_count']} "
            f"documents ({result['documents_added']:+d} change)"
        )

        return {
            "success": True,
            "message": "Index reloaded successfully",
            "old_count": result['old_count'],
            "new_count": result['new_count'],
            "documents_added": result['documents_added'],
            "index_path": result['index_path']
        }

    except Exception as e:
        logger.error(f"Failed to reload index: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to reload index",
                "code": "RELOAD_FAILED",
                "details": {"message": str(e)}
            }
        )


# ============================================================================
# Initialization
# ============================================================================

def init_search_engine(index_path: str = None, db_path: str = None):
    """
    Initialize the global search engine instance.

    This should be called during application startup.
    """
    global search_engine

    logger.info("Initializing search engine...")

    try:
        search_engine = SearchEngine(index_path=index_path, db_path=db_path)
        search_engine.load_index()
        search_engine.connect_db()

        logger.info("Search engine initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize search engine: {e}")
        raise


def shutdown_search_engine():
    """
    Cleanup search engine on shutdown.

    This should be called during application shutdown.
    """
    global search_engine

    if search_engine:
        logger.info("Shutting down search engine...")
        search_engine.close()
        search_engine = None

    # Shutdown thread pool
    search_executor.shutdown(wait=True)
    logger.info("Thread pool shut down")
