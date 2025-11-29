"""
ID utilities for txtai document identification.

This module provides a consistent ID scheme for all documents in the txtai index:

    Non-chunked articles:  "a_{article_id}"        → "a_12345"
    Chunks:                "c_{article_id}_{idx}"  → "c_12345_0", "c_12345_1"

Why string IDs:
    - Zero collision risk (prefixes prevent overlap)
    - Self-documenting (ID encodes what it is)
    - Deterministic (same article always gets same ID)
    - Chunks encode their parent article relationship
    - Future-proof (can add "summary_", "translation_" etc.)

Usage:
    from src.common.id_utils import make_article_id, make_chunk_id, parse_txtai_id

    # Indexing
    txtai_id = make_article_id(article['id'])  # "a_12345"
    txtai_id = make_chunk_id(article['id'], chunk_index)  # "c_12345_0"

    # Search result processing
    parsed = parse_txtai_id("c_12345_2")
    # {'type': 'chunk', 'article_id': 12345, 'chunk_index': 2}
"""

from typing import Dict, List, Tuple, Union
from dataclasses import dataclass


# ID Prefixes
ARTICLE_PREFIX = "a_"
CHUNK_PREFIX = "c_"


@dataclass
class ParsedArticleId:
    """Parsed article ID."""
    type: str  # Always "article"
    article_id: int


@dataclass
class ParsedChunkId:
    """Parsed chunk ID."""
    type: str  # Always "chunk"
    article_id: int
    chunk_index: int


ParsedId = Union[ParsedArticleId, ParsedChunkId]


def make_article_id(article_id: int) -> str:
    """
    Generate txtai ID for a non-chunked article.
    
    Args:
        article_id: Database article ID
        
    Returns:
        String ID like "a_12345"
        
    Example:
        >>> make_article_id(12345)
        'a_12345'
    """
    return f"{ARTICLE_PREFIX}{article_id}"


def make_chunk_id(article_id: int, chunk_index: int) -> str:
    """
    Generate txtai ID for a chunk.
    
    Args:
        article_id: Database article ID (parent article)
        chunk_index: Zero-based chunk index
        
    Returns:
        String ID like "c_12345_0"
        
    Example:
        >>> make_chunk_id(12345, 0)
        'c_12345_0'
        >>> make_chunk_id(12345, 3)
        'c_12345_3'
    """
    return f"{CHUNK_PREFIX}{article_id}_{chunk_index}"


def parse_txtai_id(txtai_id: str) -> ParsedId:
    """
    Parse txtai ID to extract type and article info.
    
    Args:
        txtai_id: String ID from txtai search results
        
    Returns:
        ParsedArticleId or ParsedChunkId dataclass
        
    Raises:
        ValueError: If ID format is unrecognized
        
    Examples:
        >>> parse_txtai_id("a_12345")
        ParsedArticleId(type='article', article_id=12345)
        
        >>> parse_txtai_id("c_12345_2")
        ParsedChunkId(type='chunk', article_id=12345, chunk_index=2)
    """
    if txtai_id.startswith(ARTICLE_PREFIX):
        # Article: "a_12345"
        try:
            article_id = int(txtai_id[len(ARTICLE_PREFIX):])
            return ParsedArticleId(type='article', article_id=article_id)
        except ValueError:
            raise ValueError(f"Invalid article ID format: {txtai_id}")
    
    elif txtai_id.startswith(CHUNK_PREFIX):
        # Chunk: "c_12345_2"
        try:
            parts = txtai_id[len(CHUNK_PREFIX):].split('_')
            if len(parts) != 2:
                raise ValueError(f"Invalid chunk ID format: {txtai_id}")
            article_id = int(parts[0])
            chunk_index = int(parts[1])
            return ParsedChunkId(
                type='chunk',
                article_id=article_id,
                chunk_index=chunk_index
            )
        except (ValueError, IndexError):
            raise ValueError(f"Invalid chunk ID format: {txtai_id}")
    
    else:
        raise ValueError(f"Unknown txtai ID format: {txtai_id}")


def extract_article_id(txtai_id: str) -> int:
    """
    Extract article_id from any txtai ID.
    
    Convenience function for deduplication and grouping.
    
    Args:
        txtai_id: String ID from txtai search results
        
    Returns:
        The article ID (works for both articles and chunks)
        
    Examples:
        >>> extract_article_id("a_12345")
        12345
        >>> extract_article_id("c_12345_2")
        12345
    """
    parsed = parse_txtai_id(txtai_id)
    return parsed.article_id


def is_article_id(txtai_id: str) -> bool:
    """
    Check if txtai ID is an article (not a chunk).
    
    Args:
        txtai_id: String ID to check
        
    Returns:
        True if this is an article ID
        
    Example:
        >>> is_article_id("a_12345")
        True
        >>> is_article_id("c_12345_0")
        False
    """
    return txtai_id.startswith(ARTICLE_PREFIX)


def is_chunk_id(txtai_id: str) -> bool:
    """
    Check if txtai ID is a chunk.
    
    Args:
        txtai_id: String ID to check
        
    Returns:
        True if this is a chunk ID
        
    Example:
        >>> is_chunk_id("c_12345_0")
        True
        >>> is_chunk_id("a_12345")
        False
    """
    return txtai_id.startswith(CHUNK_PREFIX)


def group_by_article(txtai_ids: List[str]) -> Dict[int, List[str]]:
    """
    Group txtai IDs by their parent article.
    
    Useful for deduplication - groups all chunks/articles by article_id.
    
    Args:
        txtai_ids: List of txtai IDs
        
    Returns:
        Dict mapping article_id to list of txtai_ids
        
    Example:
        >>> group_by_article(["a_100", "c_200_0", "c_200_1", "a_300"])
        {100: ["a_100"], 200: ["c_200_0", "c_200_1"], 300: ["a_300"]}
    """
    groups: Dict[int, List[str]] = {}
    
    for txtai_id in txtai_ids:
        article_id = extract_article_id(txtai_id)
        if article_id not in groups:
            groups[article_id] = []
        groups[article_id].append(txtai_id)
    
    return groups


def batch_extract_article_ids(txtai_ids: List[str]) -> Tuple[List[int], List[Tuple[int, int]]]:
    """
    Extract article IDs and chunk info from a batch of txtai IDs.
    
    Separates into articles and chunks for efficient database queries.
    
    Args:
        txtai_ids: List of txtai IDs from search results
        
    Returns:
        Tuple of:
            - List of article IDs (for non-chunked articles)
            - List of (article_id, chunk_index) tuples (for chunks)
            
    Example:
        >>> batch_extract_article_ids(["a_100", "c_200_0", "c_200_1", "a_300"])
        ([100, 300], [(200, 0), (200, 1)])
    """
    article_ids: List[int] = []
    chunk_info: List[Tuple[int, int]] = []
    
    for txtai_id in txtai_ids:
        parsed = parse_txtai_id(txtai_id)
        
        if isinstance(parsed, ParsedArticleId):
            article_ids.append(parsed.article_id)
        else:  # ParsedChunkId
            chunk_info.append((parsed.article_id, parsed.chunk_index))
    
    return article_ids, chunk_info
