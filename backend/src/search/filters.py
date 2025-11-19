"""
Filter builder for txtai WHERE clauses.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SearchFilters:
    """Builds SQL WHERE clauses for txtai search filtering."""

    @staticmethod
    def build_where_clause(filters: Dict[str, Any]) -> Optional[str]:
        """
        Build a txtai WHERE clause from filter parameters.

        Args:
            filters: Dictionary with filter parameters
                - source: Filter by article source
                - author: Filter by article author
                - date_range: Date range preset or custom range
                - start_date: Custom start date (YYYY-MM-DD)
                - end_date: Custom end date (YYYY-MM-DD)
                - published_year: Filter by specific year
                - min_word_count: Minimum word count

        Returns:
            SQL WHERE clause string or None if no filters
        """
        conditions = []

        # Source filter
        if filters.get('source'):
            source = filters['source'].replace("'", "''")  # Escape single quotes
            conditions.append(f"source = '{source}'")

        # Author filter
        if filters.get('author'):
            author = filters['author'].replace("'", "''")
            conditions.append(f"author = '{author}'")

        # Date range filters
        date_condition = SearchFilters._build_date_filter(filters)
        if date_condition:
            conditions.append(date_condition)

        # Year filter
        if filters.get('published_year'):
            year = int(filters['published_year'])
            conditions.append(f"published_year = {year}")

        # Word count filter
        if filters.get('min_word_count'):
            min_words = int(filters['min_word_count'])
            conditions.append(f"word_count >= {min_words}")

        # Combine all conditions
        if not conditions:
            return None

        where_clause = " AND ".join(conditions)
        logger.debug(f"Built WHERE clause: {where_clause}")

        return where_clause

    @staticmethod
    def _build_date_filter(filters: Dict[str, Any]) -> Optional[str]:
        """
        Build date filter condition.

        Supports:
        - Date range presets: "past_week", "past_month", "past_3months", "past_year"
        - Decade ranges: "2020s", "2010s", "2000s", "1990s"
        - Custom ranges: start_date + end_date
        """
        # Check for date range preset
        date_range = filters.get('date_range', '').lower()

        if date_range == 'past_week':
            cutoff_date = datetime.now() - timedelta(days=7)
            return f"published_date >= '{cutoff_date.strftime('%Y-%m-%d')}'"

        elif date_range == 'past_month':
            cutoff_date = datetime.now() - timedelta(days=30)
            return f"published_date >= '{cutoff_date.strftime('%Y-%m-%d')}'"

        elif date_range == 'past_3months':
            cutoff_date = datetime.now() - timedelta(days=90)
            return f"published_date >= '{cutoff_date.strftime('%Y-%m-%d')}'"

        elif date_range == 'past_year':
            cutoff_date = datetime.now() - timedelta(days=365)
            return f"published_date >= '{cutoff_date.strftime('%Y-%m-%d')}'"

        elif date_range == '2020s':
            return "published_year >= 2020 AND published_year <= 2029"

        elif date_range == '2010s':
            return "published_year >= 2010 AND published_year <= 2019"

        elif date_range == '2000s':
            return "published_year >= 2000 AND published_year <= 2009"

        elif date_range == '1990s':
            return "published_year >= 1990 AND published_year <= 1999"

        # Custom date range
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')

        if start_date and end_date:
            # Validate date format
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
                return f"published_date BETWEEN '{start_date}' AND '{end_date}'"
            except ValueError:
                logger.warning(f"Invalid date format: {start_date} or {end_date}")
                return None

        elif start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                return f"published_date >= '{start_date}'"
            except ValueError:
                logger.warning(f"Invalid start date format: {start_date}")
                return None

        elif end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
                return f"published_date <= '{end_date}'"
            except ValueError:
                logger.warning(f"Invalid end date format: {end_date}")
                return None

        return None

    @staticmethod
    def calculate_recency_boost(published_date: datetime) -> float:
        """
        Calculate recency boost score based on article age.

        Args:
            published_date: Article publication date

        Returns:
            Boost score (0.0 to 0.1)
        """
        if not published_date:
            return 0.0

        now = datetime.now()
        age_days = (now - published_date).days

        if age_days < 30:
            return 0.05
        elif age_days < 90:
            return 0.02
        elif age_days < 365:
            return 0.01
        else:
            return 0.0
