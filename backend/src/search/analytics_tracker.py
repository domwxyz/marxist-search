"""
Analytics tracker for search queries and term tracking.

This module tracks:
- Search terms and their frequency
- Term hit rates (which terms appear in results)
- Author search popularity
- Tag distribution in results
- Synonym matching effectiveness
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger("search")


class AnalyticsTracker:
    """
    Tracks search analytics and term usage.

    Features:
    - Search query tracking
    - Term hit rate tracking
    - Author popularity tracking
    - Tag distribution tracking
    - Synonym matching statistics
    """

    def __init__(self, config_path: str, update_interval: int = 100):
        """
        Initialize analytics tracker.

        Args:
            config_path: Path to analytics_config.json
            update_interval: Number of searches before writing to file
        """
        self.config_path = Path(config_path)
        self.update_interval = update_interval
        self.searches_since_update = 0

        # Load or initialize analytics data
        self.analytics = self._load_analytics()

    def _load_analytics(self) -> Dict:
        """Load analytics from file or create new."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading analytics: {e}")
                return self._create_empty_analytics()
        else:
            return self._create_empty_analytics()

    def _create_empty_analytics(self) -> Dict:
        """Create empty analytics structure."""
        return {
            "tracking": {
                "most_searched_terms": {
                    "people": {},
                    "organizations": {},
                    "concepts": {},
                    "geographic": {},
                    "historical_events": {},
                    "movements": {}
                },
                "most_searched_authors": {},
                "search_volume_by_date": {},
                "popular_tags": {},
                "tag_distribution_in_results": {},
                "avg_results_per_search": 0.0,
                "searches_with_no_results": [],
                "synonym_matching_stats": {
                    "total_synonym_matches": 0,
                    "matches_by_term": {}
                },
                "term_hit_rates": {
                    "people": {},
                    "organizations": {},
                    "concepts": {},
                    "geographic": {},
                    "historical_events": {},
                    "movements": {}
                }
            },
            "metadata": {
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "total_searches_tracked": 0,
                "tracking_start_date": datetime.utcnow().isoformat()[:10]
            }
        }

    def track_search(
        self,
        query: str,
        filters: Dict,
        results: List[Dict],
        result_count: int
    ):
        """
        Track a search query and its results.

        Args:
            query: Search query string
            filters: Applied filters
            results: List of search results
            result_count: Total number of results
        """
        try:
            # Increment total searches
            self.analytics['metadata']['total_searches_tracked'] += 1

            # Track author filter if used
            if filters.get('author'):
                author = filters['author']
                authors = self.analytics['tracking']['most_searched_authors']
                authors[author] = authors.get(author, 0) + 1

            # Track average results per search
            total = self.analytics['metadata']['total_searches_tracked']
            current_avg = self.analytics['tracking']['avg_results_per_search']
            new_avg = ((current_avg * (total - 1)) + result_count) / total
            self.analytics['tracking']['avg_results_per_search'] = new_avg

            # Track no results
            if result_count == 0:
                no_results = self.analytics['tracking']['searches_with_no_results']
                if len(no_results) < 100:  # Keep last 100
                    no_results.append({
                        'query': query,
                        'filters': filters,
                        'timestamp': datetime.utcnow().isoformat() + "Z"
                    })
                else:
                    no_results.pop(0)
                    no_results.append({
                        'query': query,
                        'filters': filters,
                        'timestamp': datetime.utcnow().isoformat() + "Z"
                    })

            # Track term hits in results
            self._track_term_hits(results)

            # Track tag distribution
            self._track_tag_distribution(results)

            # Track search volume by date
            today = datetime.utcnow().isoformat()[:10]
            volume = self.analytics['tracking']['search_volume_by_date']
            volume[today] = volume.get(today, 0) + 1

            # Increment counter and save if needed
            self.searches_since_update += 1
            if self.searches_since_update >= self.update_interval:
                self.save()

        except Exception as e:
            logger.error(f"Error tracking search: {e}")

    def _track_term_hits(self, results: List[Dict]):
        """
        Track which terms appear in search results.

        Args:
            results: List of search results
        """
        term_hits = self.analytics['tracking']['term_hit_rates']

        for result in results:
            terms = result.get('terms', [])
            if isinstance(terms, str):
                try:
                    terms = json.loads(terms)
                except:
                    terms = []

            # Count unique terms in this result
            unique_terms = set(terms) if isinstance(terms, list) else set()

            for term in unique_terms:
                # Try to find which category this term belongs to
                # For simplicity, just track it in a general counter
                # A more sophisticated approach would categorize each term
                for category in term_hits:
                    if term in term_hits[category]:
                        term_hits[category][term] += 1
                        break

    def _track_tag_distribution(self, results: List[Dict]):
        """
        Track tag distribution in search results.

        Args:
            results: List of search results
        """
        tag_dist = self.analytics['tracking']['tag_distribution_in_results']

        for result in results:
            tags = result.get('tags', [])
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except:
                    tags = []

            for tag in tags:
                tag_dist[tag] = tag_dist.get(tag, 0) + 1

    def track_term_mention(self, term: str, category: str):
        """
        Track a special term mention.

        Args:
            term: Term text
            category: Term category (people, organizations, etc.)
        """
        try:
            categories = self.analytics['tracking']['most_searched_terms']
            if category in categories:
                categories[category][term] = categories[category].get(term, 0) + 1

        except Exception as e:
            logger.error(f"Error tracking term mention: {e}")

    def track_synonym_match(self, base_term: str, synonym: str):
        """
        Track synonym matching statistics.

        Args:
            base_term: Base term
            synonym: Matched synonym
        """
        try:
            stats = self.analytics['tracking']['synonym_matching_stats']
            stats['total_synonym_matches'] += 1

            if base_term not in stats['matches_by_term']:
                stats['matches_by_term'][base_term] = {}

            matches = stats['matches_by_term'][base_term]
            matches[synonym] = matches.get(synonym, 0) + 1

        except Exception as e:
            logger.error(f"Error tracking synonym match: {e}")

    def get_top_terms(self, category: str, limit: int = 20) -> List[Dict]:
        """
        Get top searched terms in a category.

        Args:
            category: Term category
            limit: Maximum results

        Returns:
            List of term dictionaries with counts
        """
        categories = self.analytics['tracking']['most_searched_terms']
        if category not in categories:
            return []

        terms = categories[category]
        sorted_terms = sorted(
            terms.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [{'term': term, 'count': count} for term, count in sorted_terms]

    def get_top_authors(self, limit: int = 20) -> List[Dict]:
        """
        Get top searched authors.

        Args:
            limit: Maximum results

        Returns:
            List of author dictionaries with counts
        """
        authors = self.analytics['tracking']['most_searched_authors']
        sorted_authors = sorted(
            authors.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [{'author': author, 'count': count} for author, count in sorted_authors]

    def get_stats(self) -> Dict:
        """
        Get analytics statistics summary.

        Returns:
            Dictionary with analytics stats
        """
        return {
            'total_searches': self.analytics['metadata']['total_searches_tracked'],
            'avg_results_per_search': self.analytics['tracking']['avg_results_per_search'],
            'no_results_count': len(self.analytics['tracking']['searches_with_no_results']),
            'total_synonym_matches': self.analytics['tracking']['synonym_matching_stats']['total_synonym_matches'],
            'last_updated': self.analytics['metadata']['last_updated']
        }

    def save(self):
        """Save analytics to file."""
        try:
            # Update last modified timestamp
            self.analytics['metadata']['last_updated'] = datetime.utcnow().isoformat() + "Z"

            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to file
            with open(self.config_path, 'w') as f:
                json.dump(self.analytics, f, indent=2)

            logger.info(f"Analytics saved to {self.config_path}")
            self.searches_since_update = 0

        except Exception as e:
            logger.error(f"Error saving analytics: {e}")

    def __del__(self):
        """Save analytics on destruction."""
        if self.searches_since_update > 0:
            try:
                self.save()
            except:
                pass
