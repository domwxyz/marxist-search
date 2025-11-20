"""
txtai index manager for embedding and search.
"""

from pathlib import Path
from typing import List, Dict, Optional
import logging
import json

from txtai.embeddings import Embeddings

logger = logging.getLogger(__name__)


class TxtaiManager:
    """Manages txtai embeddings index."""

    def __init__(self, index_path: str, config: Optional[Dict] = None):
        """
        Initialize txtai manager.

        Args:
            index_path: Path to store/load the index
            config: txtai configuration (uses default if None)
        """
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Default configuration for txtai 7.x
        self.config = config or {
            "path": "BAAI/bge-small-en-v1.5",
            "content": True,  # Enable content storage in SQLite
            "keyword": True,  # Enable hybrid search (semantic + BM25)
            # In txtai 7.x, 'columns' is just for field mapping, not SQL schema
            # All fields in the metadata dict are automatically stored
            # Note: Removed ann/faiss configuration to avoid nflip compatibility issues
            # txtai will use its default index configuration which is compatible
        }

        self.embeddings: Optional[Embeddings] = None

    def index_exists(self) -> bool:
        """
        Check if index exists on disk.

        Returns:
            True if index exists
        """
        # Check for txtai index directory/files
        config_file = self.index_path / "config.json"
        return config_file.exists()

    def create_index(self, force: bool = False):
        """
        Create a new embeddings index.

        Args:
            force: If True, recreate index even if exists
        """
        if self.index_exists() and not force:
            logger.warning("Index already exists. Use force=True to recreate.")
            return

        logger.info("Creating new txtai embeddings index...")
        logger.info(f"Using model: {self.config['path']}")

        self.embeddings = Embeddings(self.config)

        logger.info("txtai index created successfully")

    def load_index(self):
        """Load existing index from disk."""
        if not self.index_exists():
            raise FileNotFoundError(f"No index found at {self.index_path}")

        logger.info(f"Loading txtai index from {self.index_path}...")

        self.embeddings = Embeddings()
        self.embeddings.load(str(self.index_path))

        logger.info("Index loaded successfully")

    def index_documents(self, documents: List[Dict]):
        """
        Index a batch of documents.

        Args:
            documents: List of document dictionaries
        """
        if self.embeddings is None:
            raise RuntimeError("Index not created or loaded. Call create_index() or load_index() first.")

        logger.info(f"Indexing {len(documents)} documents...")

        # Transform documents to txtai 7.x format
        # With content storage, txtai expects flat dictionaries with all fields
        txtai_docs = []

        for idx, doc in enumerate(documents):
            # Create flat dictionary with all fields
            # In txtai 7.x, all fields are stored at the same level
            txtai_doc = {
                'id': doc.get('id', idx),
                'text': doc.get('content', ''),  # 'text' is the indexed content field
                'article_id': doc.get('article_id', doc.get('id')),
                'title': doc.get('title', ''),
                'url': doc.get('url', ''),
                'source': doc.get('source', ''),
                'author': doc.get('author', ''),
                'published_date': str(doc.get('published_date', '')),
                'published_year': doc.get('published_year', 0),
                'published_month': doc.get('published_month', 0),
                'word_count': doc.get('word_count', 0),
                'is_chunk': doc.get('is_chunk', False),
                'chunk_index': doc.get('chunk_index', 0),
                'terms': json.dumps(doc.get('terms', [])),
                'tags': json.dumps(doc.get('tags', []))
            }

            txtai_docs.append(txtai_doc)

        # Index the documents
        self.embeddings.index(txtai_docs)

        logger.info(f"Successfully indexed {len(documents)} documents")

    def save_index(self):
        """Save index to disk."""
        if self.embeddings is None:
            raise RuntimeError("No index to save")

        logger.info(f"Saving index to {self.index_path}...")

        self.embeddings.save(str(self.index_path))

        logger.info("Index saved successfully")

    def upsert_documents(self, documents: List[Dict]):
        """
        Add or update documents in the index.

        Args:
            documents: List of document dictionaries
        """
        if self.embeddings is None:
            raise RuntimeError("Index not created or loaded")

        logger.info(f"Upserting {len(documents)} documents...")

        # Transform documents to txtai 7.x format
        # With content storage, txtai expects flat dictionaries with all fields
        txtai_docs = []

        for idx, doc in enumerate(documents):
            # Create flat dictionary with all fields
            txtai_doc = {
                'id': doc.get('id', idx),
                'text': doc.get('content', ''),  # 'text' is the indexed content field
                'article_id': doc.get('article_id', doc.get('id')),
                'title': doc.get('title', ''),
                'url': doc.get('url', ''),
                'source': doc.get('source', ''),
                'author': doc.get('author', ''),
                'published_date': str(doc.get('published_date', '')),
                'published_year': doc.get('published_year', 0),
                'published_month': doc.get('published_month', 0),
                'word_count': doc.get('word_count', 0),
                'is_chunk': doc.get('is_chunk', False),
                'chunk_index': doc.get('chunk_index', 0),
                'terms': json.dumps(doc.get('terms', [])),
                'tags': json.dumps(doc.get('tags', []))
            }

            txtai_docs.append(txtai_doc)

        # Upsert
        self.embeddings.upsert(txtai_docs)
        self.save_index()

        logger.info(f"Successfully upserted {len(documents)} documents")

    def search(
        self,
        query: str,
        limit: int = 10,
        where: Optional[str] = None,
        weights: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search the index.

        Args:
            query: Search query
            limit: Maximum results to return
            where: SQL WHERE clause for filtering
            weights: Hybrid search weights {"semantic": 0.7, "bm25": 0.3}

        Returns:
            List of search results
        """
        if self.embeddings is None:
            raise RuntimeError("Index not loaded")

        # Default hybrid weights
        if weights is None:
            weights = {"semantic": 0.7, "bm25": 0.3}

        # Build search parameters
        params = {
            "limit": limit
        }

        if where:
            params["where"] = where

        if weights:
            params["weights"] = weights

        # Execute search
        results = self.embeddings.search(query, **params)

        return results

    def count(self) -> int:
        """
        Get count of indexed documents.

        Returns:
            Number of documents in index
        """
        if self.embeddings is None:
            return 0

        return self.embeddings.count()

    def get_index_info(self) -> Dict:
        """
        Get information about the index.

        Returns:
            Dictionary with index information
        """
        info = {
            'path': str(self.index_path),
            'exists': self.index_exists(),
            'loaded': self.embeddings is not None,
            'count': 0,
            'status': 'unknown'
        }

        if self.embeddings is not None:
            info['count'] = self.embeddings.count()
            info['status'] = 'loaded'
        elif self.index_exists():
            info['status'] = 'exists (not loaded)'
        else:
            info['status'] = 'not created'

        return info

    def close(self):
        """Close the index."""
        if self.embeddings:
            self.embeddings.close()
            self.embeddings = None
            logger.info("Index closed")
