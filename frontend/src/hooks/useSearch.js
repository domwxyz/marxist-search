import { useState, useCallback, useRef, useEffect } from 'react';
import { searchArticles } from '../utils/api';

export const useSearch = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [queryTime, setQueryTime] = useState(0);
  const [page, setPage] = useState(1);

  const debounceTimer = useRef(null);
  const abortController = useRef(null);

  const performSearch = useCallback(async (searchQuery, filters) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setTotal(0);
      setQueryTime(0);
      return;
    }

    // Cancel previous request if still pending
    if (abortController.current) {
      abortController.current.abort();
    }

    abortController.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const data = await searchArticles(searchQuery, filters);
      setResults(data.results || []);
      setTotal(data.total || 0);
      setQueryTime(data.query_time_ms || 0);
      setPage(Math.floor(filters.offset / filters.limit) + 1);
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Search failed');
        setResults([]);
        setTotal(0);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const debouncedSearch = useCallback((searchQuery, filters, immediate = false) => {
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    if (immediate) {
      performSearch(searchQuery, filters);
    } else {
      debounceTimer.current = setTimeout(() => {
        performSearch(searchQuery, filters);
      }, 300);
    }
  }, [performSearch]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
      if (abortController.current) {
        abortController.current.abort();
      }
    };
  }, []);

  return {
    query,
    setQuery,
    results,
    total,
    loading,
    error,
    queryTime,
    page,
    performSearch,
    debouncedSearch,
  };
};
