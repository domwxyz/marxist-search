"""
Term extraction module for identifying special Marxist terms and entities.

This module:
1. Extracts special terms from article content
2. Resolves aliases to canonical terms
3. Tracks term occurrences for analytics
4. Stores terms for improved search relevance
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger("ingestion")


class TermExtractor:
    """
    Extracts special terms, entities, and concepts from article text.

    Features:
    - Case-insensitive term matching
    - Alias resolution (e.g., "UN" -> "United Nations")
    - Synonym tracking for analytics
    - Categorized term extraction (people, organizations, concepts, etc.)
    """

    def __init__(self, config_path: str):
        """
        Initialize term extractor.

        Args:
            config_path: Path to terms_config.json
        """
        self.config_path = Path(config_path)

        # Load configuration
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)

        self.synonyms = self.config.get('synonyms', {})
        self.terms = self.config.get('terms', {})
        self.aliases = self.config.get('aliases', {})

        # Build lookup structures for efficient matching
        self._build_lookup_structures()

        logger.info(f"Loaded term extractor with {self._count_total_terms()} terms")

    def _count_total_terms(self) -> int:
        """Count total number of terms across all categories."""
        count = 0
        for category in self.terms.values():
            count += len(category)
        return count

    def _build_lookup_structures(self):
        """
        Build efficient lookup structures for term matching.

        Creates:
        - term_to_category: Maps each term to its category
        - compiled_patterns: Regex patterns for each term
        - alias_mapping: Maps aliases to canonical terms
        - reverse_alias_mapping: Maps canonical terms to their aliases
        """
        self.term_to_category = {}
        self.compiled_patterns = {}

        # Build term-to-category mapping and regex patterns
        for category, term_list in self.terms.items():
            for term in term_list:
                term_lower = term.lower()
                self.term_to_category[term_lower] = category

                # Create regex pattern for whole word matching
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(term) + r'\b'
                self.compiled_patterns[term_lower] = re.compile(
                    pattern,
                    re.IGNORECASE
                )

        # Build alias mapping (lowercase for case-insensitive lookup)
        # alias -> canonical
        self.alias_mapping = {
            alias.lower(): canonical.lower()
            for alias, canonical in self.aliases.items()
        }

        # Build reverse alias mapping (canonical -> list of aliases)
        # This allows searching "Soviet Union" to also find "USSR"
        self.reverse_alias_mapping = defaultdict(list)
        for alias, canonical in self.aliases.items():
            self.reverse_alias_mapping[canonical.lower()].append(alias)

        logger.debug(f"Built lookup structures: "
                    f"{len(self.term_to_category)} terms, "
                    f"{len(self.alias_mapping)} aliases, "
                    f"{len(self.reverse_alias_mapping)} reverse aliases")

    def extract_terms(
        self,
        title: str,
        content: str
    ) -> Dict[str, List[Dict]]:
        """
        Extract special terms from article title and content.

        Args:
            title: Article title
            content: Article content

        Returns:
            Dictionary mapping categories to lists of term mentions:
            {
                "people": [
                    {"term": "Karl Marx", "count": 5},
                    {"term": "Lenin", "count": 2}
                ],
                "organizations": [...],
                ...
            }
        """
        # Combine title and content for searching
        # Weight title matches more heavily by including it twice
        combined_text = f"{title} {title} {content}"

        # Track term counts by category
        category_terms = defaultdict(lambda: defaultdict(int))

        # Search for each term
        for term_lower, pattern in self.compiled_patterns.items():
            matches = pattern.findall(combined_text)

            if matches:
                count = len(matches)
                category = self.term_to_category[term_lower]

                # Use original case from config for display
                original_term = self._get_original_term(term_lower)
                category_terms[category][original_term] = count

        # Resolve aliases in the text
        alias_matches = self._extract_aliases(combined_text)
        for canonical_term, count in alias_matches.items():
            category = self.term_to_category.get(canonical_term.lower())
            if category:
                original_term = self._get_original_term(canonical_term.lower())
                category_terms[category][original_term] += count

        # Convert to list format
        result = {}
        for category, terms_dict in category_terms.items():
            result[category] = [
                {"term": term, "count": count}
                for term, count in sorted(
                    terms_dict.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ]

        return result

    def _get_original_term(self, term_lower: str) -> str:
        """
        Get original case term from lowercase term.

        Args:
            term_lower: Lowercase term

        Returns:
            Original case term from config
        """
        for category, term_list in self.terms.items():
            for term in term_list:
                if term.lower() == term_lower:
                    return term
        return term_lower

    def _extract_aliases(self, text: str) -> Dict[str, int]:
        """
        Extract aliases and map them to canonical terms.

        Args:
            text: Text to search

        Returns:
            Dictionary mapping canonical terms to counts
        """
        canonical_counts = defaultdict(int)

        for alias, canonical_lower in self.alias_mapping.items():
            # Create regex pattern for alias
            pattern = r'\b' + re.escape(alias) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)

            if matches:
                canonical_counts[canonical_lower] += len(matches)

        return canonical_counts

    def extract_and_format(
        self,
        title: str,
        content: str
    ) -> Tuple[str, List[Dict]]:
        """
        Extract terms and format for database storage.

        Args:
            title: Article title
            content: Article content

        Returns:
            Tuple of (terms_json_string, term_mentions_list)
            - terms_json_string: JSON string for articles.terms_json field
            - term_mentions_list: List of dicts for term_mentions table
        """
        # Extract terms
        category_terms = self.extract_terms(title, content)

        # Flatten for database storage
        all_terms = []
        term_mentions = []

        for category, terms_list in category_terms.items():
            for term_info in terms_list:
                all_terms.append(term_info['term'])
                term_mentions.append({
                    'term_text': term_info['term'],
                    'term_type': category,
                    'mention_count': term_info['count']
                })

        # Create JSON string for terms_json field
        terms_json = json.dumps(all_terms)

        return terms_json, term_mentions

    def get_synonyms_for_query(self, query: str) -> List[str]:
        """
        Get synonyms for a search query term.

        Useful for query expansion in search.

        Args:
            query: Search query term

        Returns:
            List of synonyms (including original term)
        """
        query_lower = query.lower()

        # Check if query is a synonym base term
        if query_lower in self.synonyms:
            return [query] + self.synonyms[query_lower]

        # Check if query is a synonym of a base term
        for base_term, synonym_list in self.synonyms.items():
            if query_lower in [s.lower() for s in synonym_list]:
                return [base_term] + synonym_list

        # No synonyms found
        return [query]

    def expand_query_with_synonyms(self, query: str) -> str:
        """
        Expand a search query with synonyms.

        Args:
            query: Original search query

        Returns:
            Expanded query with OR-ed synonyms
        """
        words = query.split()
        expanded_parts = []

        for word in words:
            synonyms = self.get_synonyms_for_query(word)
            if len(synonyms) > 1:
                # Create OR clause for synonyms
                synonym_clause = " OR ".join(f'"{s}"' for s in synonyms[:4])  # Limit to 4
                expanded_parts.append(f"({synonym_clause})")
            else:
                expanded_parts.append(word)

        return " ".join(expanded_parts)

    def get_stats(self) -> Dict:
        """
        Get statistics about loaded terms.

        Returns:
            Dictionary with term statistics
        """
        stats = {
            'total_terms': self._count_total_terms(),
            'total_synonyms': sum(len(syns) for syns in self.synonyms.values()),
            'total_aliases': len(self.aliases),
            'categories': {}
        }

        for category, term_list in self.terms.items():
            stats['categories'][category] = len(term_list)

        return stats


def extract_terms_from_article(
    article: Dict,
    config_path: str
) -> Tuple[str, List[Dict]]:
    """
    Convenience function to extract terms from an article dictionary.

    Args:
        article: Article dictionary with 'title' and 'content' keys
        config_path: Path to terms_config.json

    Returns:
        Tuple of (terms_json_string, term_mentions_list)
    """
    extractor = TermExtractor(config_path)
    return extractor.extract_and_format(
        article.get('title', ''),
        article.get('content', '')
    )
