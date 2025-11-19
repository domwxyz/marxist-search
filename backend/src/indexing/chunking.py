"""
Article chunking service for long documents.

Splits articles longer than threshold into smaller chunks for better search results.
"""

import re
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class ArticleChunker:
    """Chunks long articles into smaller segments for indexing."""

    def __init__(
        self,
        threshold_words: int = 3500,
        chunk_size_words: int = 1000,
        overlap_words: int = 200,
        prefer_section_breaks: bool = True
    ):
        """
        Initialize article chunker.

        Args:
            threshold_words: Minimum word count before chunking
            chunk_size_words: Target size for each chunk
            overlap_words: Number of words to overlap between chunks
            prefer_section_breaks: Try to chunk on natural boundaries
        """
        self.threshold_words = threshold_words
        self.chunk_size_words = chunk_size_words
        self.overlap_words = overlap_words
        self.prefer_section_breaks = prefer_section_breaks

        # Section break patterns (ordered by preference)
        self.section_patterns = [
            r'\n#{1,3}\s+',  # Markdown headers
            r'\n\n+',        # Multiple newlines (paragraph breaks)
            r'\n',           # Single newline
            r'\.\s+',        # Sentence breaks
        ]

    def should_chunk(self, text: str) -> bool:
        """
        Determine if article should be chunked.

        Args:
            text: Article text

        Returns:
            True if article should be chunked
        """
        word_count = len(text.split())
        return word_count > self.threshold_words

    def chunk_article(self, article: Dict) -> List[Dict]:
        """
        Chunk a single article if it exceeds threshold.

        Args:
            article: Article dictionary with content and metadata

        Returns:
            List of chunk dictionaries (empty if no chunking needed)
        """
        content = article.get('content', '')
        word_count = article.get('word_count', len(content.split()))

        if word_count <= self.threshold_words:
            return []

        logger.info(f"Chunking article {article.get('id')} ({word_count} words)")

        chunks = self._create_chunks(content)

        # Create chunk dictionaries with metadata
        chunk_dicts = []
        for idx, (chunk_text, start_pos) in enumerate(chunks):
            chunk_dict = {
                'article_id': article['id'],
                'chunk_index': idx,
                'content': chunk_text,
                'word_count': len(chunk_text.split()),
                'start_position': start_pos,
            }
            chunk_dicts.append(chunk_dict)

        logger.info(f"Created {len(chunk_dicts)} chunks for article {article.get('id')}")
        return chunk_dicts

    def _create_chunks(self, text: str) -> List[Tuple[str, int]]:
        """
        Create overlapping chunks from text.

        Args:
            text: Full article text

        Returns:
            List of (chunk_text, start_position) tuples
        """
        if self.prefer_section_breaks:
            return self._chunk_by_sections(text)
        else:
            return self._chunk_by_words(text)

    def _chunk_by_sections(self, text: str) -> List[Tuple[str, int]]:
        """
        Chunk text by natural section breaks (paragraphs, headers).

        Args:
            text: Full article text

        Returns:
            List of (chunk_text, start_position) tuples
        """
        # Split into paragraphs
        paragraphs = re.split(r'\n\n+', text)

        chunks = []
        current_chunk = []
        current_word_count = 0
        current_start_pos = 0
        chunk_start_pos = 0

        for para in paragraphs:
            para_words = len(para.split())

            # If adding this paragraph would exceed chunk size
            if current_word_count + para_words > self.chunk_size_words and current_chunk:
                # Save current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append((chunk_text, chunk_start_pos))

                # Start new chunk with overlap
                # Keep last few paragraphs for overlap
                overlap_paras = self._get_overlap_paragraphs(current_chunk)
                current_chunk = overlap_paras + [para]
                chunk_start_pos = current_start_pos
                current_word_count = sum(len(p.split()) for p in current_chunk)
            else:
                # Add paragraph to current chunk
                current_chunk.append(para)
                current_word_count += para_words

            current_start_pos += len(para) + 2  # +2 for \n\n

        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append((chunk_text, chunk_start_pos))

        return chunks

    def _get_overlap_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """
        Get paragraphs for overlap from end of chunk.

        Args:
            paragraphs: List of paragraphs in current chunk

        Returns:
            List of paragraphs to use as overlap
        """
        overlap_paras = []
        overlap_words = 0

        # Work backwards to get overlap
        for para in reversed(paragraphs):
            para_words = len(para.split())
            if overlap_words + para_words > self.overlap_words:
                break
            overlap_paras.insert(0, para)
            overlap_words += para_words

        return overlap_paras

    def _chunk_by_words(self, text: str) -> List[Tuple[str, int]]:
        """
        Chunk text by word count (fallback method).

        Args:
            text: Full article text

        Returns:
            List of (chunk_text, start_position) tuples
        """
        words = text.split()
        chunks = []
        start_idx = 0

        while start_idx < len(words):
            # Get chunk of words
            end_idx = min(start_idx + self.chunk_size_words, len(words))
            chunk_words = words[start_idx:end_idx]
            chunk_text = ' '.join(chunk_words)

            # Calculate character position (approximate)
            start_pos = len(' '.join(words[:start_idx]))

            chunks.append((chunk_text, start_pos))

            # Move forward, accounting for overlap
            start_idx += self.chunk_size_words - self.overlap_words

        return chunks


def chunk_articles_batch(
    articles: List[Dict],
    threshold_words: int = 3500,
    chunk_size_words: int = 1000,
    overlap_words: int = 200
) -> Dict[int, List[Dict]]:
    """
    Chunk a batch of articles.

    Args:
        articles: List of article dictionaries
        threshold_words: Minimum word count before chunking
        chunk_size_words: Target size for each chunk
        overlap_words: Number of words to overlap

    Returns:
        Dictionary mapping article_id to list of chunks
    """
    chunker = ArticleChunker(
        threshold_words=threshold_words,
        chunk_size_words=chunk_size_words,
        overlap_words=overlap_words
    )

    chunked_articles = {}

    for article in articles:
        chunks = chunker.chunk_article(article)
        if chunks:
            chunked_articles[article['id']] = chunks

    return chunked_articles
