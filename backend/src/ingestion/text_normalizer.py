"""
Text normalization utilities for article content.
"""

import re
import html
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TextNormalizer:
    """Normalizes and cleans article text for indexing."""

    def __init__(self):
        """Initialize text normalizer."""
        # Patterns for cleaning
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.multiple_spaces = re.compile(r'\s+')
        self.multiple_newlines = re.compile(r'\n{3,}')

    def normalize(self, text: str, preserve_paragraphs: bool = True) -> str:
        """
        Normalize article text.

        Args:
            text: Raw text to normalize
            preserve_paragraphs: Whether to preserve paragraph breaks

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Decode HTML entities
        text = html.unescape(text)

        # Remove HTML tags if any remain
        text = self._remove_html_tags(text)

        # Remove URLs (optional - keeping for now as they might be references)
        # text = self.url_pattern.sub('', text)

        # Remove email addresses (privacy)
        text = self.email_pattern.sub('[email]', text)

        # Normalize whitespace
        text = self._normalize_whitespace(text, preserve_paragraphs)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    def normalize_title(self, title: str) -> str:
        """
        Normalize article title.

        Args:
            title: Raw title

        Returns:
            Normalized title
        """
        if not title:
            return ""

        # Decode HTML entities
        title = html.unescape(title)

        # Remove HTML tags
        title = self._remove_html_tags(title)

        # Normalize whitespace
        title = self.multiple_spaces.sub(' ', title)

        # Remove leading/trailing whitespace
        title = title.strip()

        return title

    def normalize_author(self, author: str) -> Optional[str]:
        """
        Normalize author name.

        Args:
            author: Raw author name

        Returns:
            Normalized author name or None if invalid
        """
        if not author:
            return None

        # Decode HTML entities
        author = html.unescape(author)

        # Remove HTML tags
        author = self._remove_html_tags(author)

        # Normalize whitespace
        author = self.multiple_spaces.sub(' ', author)

        # Remove leading/trailing whitespace
        author = author.strip()

        # Filter out common non-author values
        invalid_authors = [
            'admin', 'administrator', 'editor', 'staff', 'unknown',
            'anonymous', 'guest', 'author', 'writer', ''
        ]

        if author.lower() in invalid_authors:
            return None

        # Check for email addresses in author field
        if '@' in author:
            # Extract name before @ if it looks like a name
            parts = author.split('@')
            potential_name = parts[0].strip()
            if len(potential_name) > 2:
                author = potential_name.replace('.', ' ').replace('_', ' ').title()
            else:
                return None

        return author if author else None

    def _remove_html_tags(self, text: str) -> str:
        """
        Remove HTML tags from text.

        Args:
            text: Text potentially containing HTML

        Returns:
            Text without HTML tags
        """
        # Remove script and style elements
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        return text

    def _normalize_whitespace(self, text: str, preserve_paragraphs: bool) -> str:
        """
        Normalize whitespace in text.

        Args:
            text: Text to normalize
            preserve_paragraphs: Whether to preserve paragraph breaks

        Returns:
            Text with normalized whitespace
        """
        if preserve_paragraphs:
            # Preserve double newlines (paragraph breaks)
            # but remove excessive newlines
            text = self.multiple_newlines.sub('\n\n', text)

            # Normalize spaces within lines
            lines = text.split('\n')
            normalized_lines = [self.multiple_spaces.sub(' ', line.strip()) for line in lines]
            text = '\n'.join(normalized_lines)
        else:
            # Replace all whitespace (including newlines) with single spaces
            text = self.multiple_spaces.sub(' ', text)

        return text

    def extract_excerpt(self, text: str, max_length: int = 200) -> str:
        """
        Extract excerpt from text for display.

        Args:
            text: Full text
            max_length: Maximum length of excerpt

        Returns:
            Excerpt with ellipsis if truncated
        """
        if not text:
            return ""

        # Normalize text first
        text = self.normalize(text, preserve_paragraphs=False)

        # Truncate if necessary
        if len(text) <= max_length:
            return text

        # Find last space before max_length to avoid cutting words
        truncated = text[:max_length]
        last_space = truncated.rfind(' ')

        if last_space > 0:
            truncated = truncated[:last_space]

        return truncated + "..."

    def clean_summary(self, summary: str) -> str:
        """
        Clean RSS feed summary text.

        Args:
            summary: Raw summary from RSS

        Returns:
            Cleaned summary
        """
        if not summary:
            return ""

        # Apply standard normalization
        summary = self.normalize(summary, preserve_paragraphs=False)

        # Remove common RSS artifacts
        artifacts = [
            'Continue reading',
            'Read more',
            'Click here',
            'View article',
            'Full story',
        ]

        for artifact in artifacts:
            summary = summary.replace(artifact, '')

        # Clean up resulting whitespace
        summary = self.multiple_spaces.sub(' ', summary).strip()

        return summary


def normalize_article(article: dict) -> dict:
    """
    Normalize all text fields in an article dictionary.

    Args:
        article: Article dictionary with text fields

    Returns:
        Article with normalized text fields
    """
    normalizer = TextNormalizer()

    # Normalize title
    if 'title' in article:
        article['title'] = normalizer.normalize_title(article['title'])

    # Normalize content
    if 'content' in article:
        article['content'] = normalizer.normalize(article['content'], preserve_paragraphs=True)

    # Normalize summary
    if 'summary' in article:
        article['summary'] = normalizer.clean_summary(article['summary'])

    # Normalize author
    if 'author' in article:
        article['author'] = normalizer.normalize_author(article['author'])

    return article


def normalize_articles_batch(articles: list) -> list:
    """
    Normalize a batch of articles.

    Args:
        articles: List of article dictionaries

    Returns:
        List of normalized articles
    """
    return [normalize_article(article) for article in articles]
