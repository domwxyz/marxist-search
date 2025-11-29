"""
Pydantic models for API requests and responses.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


# ============================================================================
# Search Models
# ============================================================================

class SearchFilters(BaseModel):
    """Search filter parameters."""

    source: Optional[str] = Field(None, description="Filter by article source")
    author: Optional[str] = Field(None, description="Filter by article author")
    date_range: Optional[str] = Field(
        None,
        description="Date range preset: past_week, past_month, past_3months, past_year, 2020s, 2010s, 2000s, 1990s"
    )
    start_date: Optional[str] = Field(None, description="Custom start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Custom end date (YYYY-MM-DD)")
    published_year: Optional[int] = Field(None, description="Filter by specific year")
    min_word_count: Optional[int] = Field(None, description="Minimum word count")

    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        """Validate date format."""
        if v is not None:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v


class SearchRequest(BaseModel):
    """Search request body."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    filters: Optional[SearchFilters] = Field(default_factory=SearchFilters, description="Search filters")
    limit: int = Field(50, ge=1, le=100, description="Maximum results to return")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class SearchResult(BaseModel):
    """Individual search result."""

    id: str = Field(..., description="Document ID (e.g., 'a_12345' or 'c_12345_0')")
    article_id: int = Field(..., description="Article ID")
    title: str = Field(..., description="Article title")
    url: str = Field(..., description="Article URL")
    source: str = Field(..., description="Article source")
    author: str = Field(..., description="Article author")
    published_date: str = Field(..., description="Publication date")
    excerpt: str = Field(..., description="Article excerpt")
    matched_phrase: Optional[str] = Field(None, description="Matched exact phrase for highlighting")
    score: float = Field(..., description="Search relevance score")
    matched_sections: int = Field(..., description="Number of matched sections")
    word_count: int = Field(..., description="Article word count")
    tags: List[str] = Field(default_factory=list, description="Article tags")
    terms: List[str] = Field(default_factory=list, description="Extracted terms")
    recency_boost: Optional[float] = Field(None, description="Recency boost applied")
    original_score: Optional[float] = Field(None, description="Original score before boost")


class SearchResponse(BaseModel):
    """Search response."""

    results: List[SearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Total unique articles found")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Result offset")
    query_time_ms: int = Field(..., description="Query execution time in milliseconds")
    query: str = Field(..., description="Original search query")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Applied filters")


# ============================================================================
# Author Models
# ============================================================================

class Author(BaseModel):
    """Author information."""

    name: str = Field(..., description="Author name")
    article_count: int = Field(..., description="Number of articles")
    latest_article: Optional[str] = Field(None, description="Date of latest article")
    earliest_article: Optional[str] = Field(None, description="Date of earliest article")


class AuthorsResponse(BaseModel):
    """Top authors response."""

    authors: List[Author] = Field(..., description="List of authors")
    total: int = Field(..., description="Total authors returned")


# ============================================================================
# Source Models
# ============================================================================

class Source(BaseModel):
    """Article source information."""

    name: str = Field(..., description="Source name")
    article_count: int = Field(..., description="Number of articles")
    latest_article: Optional[str] = Field(None, description="Date of latest article")
    earliest_article: Optional[str] = Field(None, description="Date of earliest article")


class SourcesResponse(BaseModel):
    """Sources response."""

    sources: List[Source] = Field(..., description="List of sources")
    total: int = Field(..., description="Total sources")


# ============================================================================
# Statistics Models
# ============================================================================

class DateRange(BaseModel):
    """Date range information."""

    earliest: Optional[str] = Field(None, description="Earliest article date")
    latest: Optional[str] = Field(None, description="Latest article date")


class StatsResponse(BaseModel):
    """Index statistics response."""

    total_articles: int = Field(..., description="Total articles in database")
    indexed_articles: int = Field(..., description="Articles in search index")
    total_chunks: int = Field(..., description="Total article chunks")
    date_range: DateRange = Field(..., description="Date range of articles")
    sources_count: int = Field(..., description="Number of sources")
    index_document_count: int = Field(..., description="Documents in txtai index")
    index_loaded: bool = Field(..., description="Whether index is loaded")


# ============================================================================
# Health Models
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    index_loaded: bool = Field(..., description="Whether index is loaded")
    index_document_count: int = Field(..., description="Documents in index")
    database_connected: bool = Field(..., description="Database connection status")
    uptime_seconds: Optional[int] = Field(None, description="Service uptime in seconds")


# ============================================================================
# Error Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
