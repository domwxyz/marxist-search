"""
FastAPI main application for Marxist Search Engine.
"""

import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import router, init_search_engine, shutdown_search_engine
from config.search_config import (
    LOG_CONFIG,
    INDEX_PATH,
    DATABASE_PATH,
    ENVIRONMENT,
    DEBUG
)

# Configure logging
logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger('api')


# ============================================================================
# Application Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Marxist Search API...")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Debug mode: {DEBUG}")

    try:
        # Initialize search engine
        init_search_engine(index_path=INDEX_PATH, db_path=DATABASE_PATH)
        logger.info("Search engine loaded successfully")

    except Exception as e:
        logger.error(f"Failed to initialize search engine: {e}")
        raise

    logger.info("API startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Marxist Search API...")
    shutdown_search_engine()
    logger.info("Shutdown complete")


# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(
    title="Marxist Search API",
    description="Semantic search API for Marxist theoretical articles",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if DEBUG else None,
    redoc_url="/redoc" if DEBUG else None
)

# ============================================================================
# CORS Configuration
# ============================================================================

# Allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        # Add production domain when deployed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Include Routers
# ============================================================================

app.include_router(router)


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/")
async def root():
    """
    Root endpoint - API information.
    """
    return {
        "name": "Marxist Search API",
        "version": "1.0.0",
        "description": "Semantic search engine for Marxist theoretical articles",
        "endpoints": {
            "search": "/api/v1/search",
            "authors": "/api/v1/top-authors",
            "sources": "/api/v1/sources",
            "stats": "/api/v1/stats",
            "health": "/api/v1/health"
        },
        "documentation": "/docs" if DEBUG else None
    }


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Resource not found",
            "code": "NOT_FOUND",
            "details": {
                "path": str(request.url.path)
            }
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
            "details": {
                "message": str(exc) if DEBUG else "An unexpected error occurred"
            }
        }
    )


# ============================================================================
# Development Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",  # Use fully qualified module path
        host="0.0.0.0",
        port=8000,
        reload=DEBUG,
        log_level="info"
    )
