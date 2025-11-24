"""
Custom BM25 scorer for post-processing search results.

This implements BM25 scoring in pure Python to avoid txtai's upsert corruption
issue while still providing keyword matching benefits for hybrid search.
"""

import re
import math
from typing import List, Dict, Set
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class BM25Scorer:
    """
    Simplified BM25 implementation for post-processing search results.

    BM25 formula:
    score(D,Q) = Σ IDF(qi) * (f(qi,D) * (k1 + 1)) / (f(qi,D) + k1 * (1 - b + b * |D| / avgdl))

    Where:
    - D = document
    - Q = query
    - qi = query term i
    - f(qi,D) = frequency of qi in D
    - |D| = length of document D
    - avgdl = average document length in collection
    - k1, b = tuning parameters (typically k1=1.5, b=0.75)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 scorer.

        Args:
            k1: Term frequency saturation parameter (1.2-2.0, default 1.5)
            b: Length normalization parameter (0-1, default 0.75)
        """
        self.k1 = k1
        self.b = b

    def score_results(
        self,
        query: str,
        results: List[Dict],
        text_field: str = 'text',
        title_field: str = 'title'
    ) -> List[Dict]:
        """
        Score search results using BM25 and combine with existing scores.

        Args:
            query: Search query string
            results: List of result dictionaries with content
            text_field: Field containing document text
            title_field: Field containing document title

        Returns:
            Results with updated 'bm25_score' field added
        """
        if not results or not query:
            return results

        # Extract query terms (lowercase, remove punctuation)
        query_terms = self._tokenize(query)
        if not query_terms:
            return results

        # Calculate document lengths and average
        doc_lengths = []
        for result in results:
            text = result.get(text_field, '') or ''
            title = result.get(title_field, '') or ''
            # Weight title text more heavily (count it 3x)
            combined_text = f"{title} {title} {title} {text}"
            doc_lengths.append(len(self._tokenize(combined_text)))

        if not doc_lengths:
            return results

        avgdl = sum(doc_lengths) / len(doc_lengths)

        # Calculate IDF for each query term
        idf_scores = self._calculate_idf(query_terms, results, text_field, title_field)

        # Score each document
        for i, result in enumerate(results):
            text = result.get(text_field, '') or ''
            title = result.get(title_field, '') or ''
            # Weight title more heavily
            combined_text = f"{title} {title} {title} {text}"

            # Calculate BM25 score
            bm25_score = self._calculate_bm25(
                query_terms,
                combined_text,
                doc_lengths[i],
                avgdl,
                idf_scores
            )

            result['bm25_score'] = bm25_score

        return results

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.

        Args:
            text: Input text

        Returns:
            List of lowercase tokens
        """
        # Lowercase and extract words (alphanumeric + basic punctuation)
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _calculate_idf(
        self,
        query_terms: List[str],
        results: List[Dict],
        text_field: str,
        title_field: str
    ) -> Dict[str, float]:
        """
        Calculate IDF (Inverse Document Frequency) for query terms.

        IDF(qi) = log((N - n(qi) + 0.5) / (n(qi) + 0.5))

        Where:
        - N = total number of documents
        - n(qi) = number of documents containing qi

        Args:
            query_terms: List of query terms
            results: List of result documents
            text_field: Field containing document text
            title_field: Field containing document title

        Returns:
            Dict mapping term -> IDF score
        """
        N = len(results)
        term_doc_counts = Counter()

        # Count documents containing each query term
        for result in results:
            text = result.get(text_field, '') or ''
            title = result.get(title_field, '') or ''
            combined_text = f"{title} {text}"

            doc_tokens = set(self._tokenize(combined_text))

            for term in query_terms:
                if term in doc_tokens:
                    term_doc_counts[term] += 1

        # Calculate IDF for each term
        idf_scores = {}
        for term in query_terms:
            n = term_doc_counts[term]
            # Add smoothing to avoid division by zero
            idf = math.log((N - n + 0.5) / (n + 0.5) + 1.0)
            idf_scores[term] = max(0.0, idf)  # Ensure non-negative

        return idf_scores

    def _calculate_bm25(
        self,
        query_terms: List[str],
        document: str,
        doc_length: int,
        avgdl: float,
        idf_scores: Dict[str, float]
    ) -> float:
        """
        Calculate BM25 score for a document given a query.

        Args:
            query_terms: List of query terms
            document: Document text
            doc_length: Length of document in tokens
            avgdl: Average document length in collection
            idf_scores: Pre-calculated IDF scores

        Returns:
            BM25 score
        """
        if doc_length == 0:
            return 0.0

        # Tokenize and count term frequencies
        doc_tokens = self._tokenize(document)
        term_freqs = Counter(doc_tokens)

        # Calculate BM25 score
        score = 0.0
        for term in query_terms:
            if term not in idf_scores:
                continue

            f = term_freqs.get(term, 0)
            if f == 0:
                continue

            idf = idf_scores[term]

            # BM25 formula
            numerator = f * (self.k1 + 1)
            denominator = f + self.k1 * (1 - self.b + self.b * doc_length / avgdl)

            score += idf * (numerator / denominator)

        return score


def combine_scores(
    semantic_score: float,
    bm25_score: float,
    semantic_weight: float = 0.7,
    bm25_weight: float = 0.3
) -> float:
    """
    Combine semantic and BM25 scores with configurable weights.

    Args:
        semantic_score: Score from semantic search (0-1)
        bm25_score: Score from BM25 (raw score)
        semantic_weight: Weight for semantic score (0-1)
        bm25_weight: Weight for BM25 score (0-1)

    Returns:
        Combined score
    """
    # Normalize BM25 score to roughly 0-1 range using sigmoid-like function
    # Most BM25 scores are in 0-20 range, so divide by 10 for rough normalization
    normalized_bm25 = min(1.0, bm25_score / 10.0)

    combined = (semantic_score * semantic_weight) + (normalized_bm25 * bm25_weight)
    return combined
