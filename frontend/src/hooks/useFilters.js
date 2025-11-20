import { useState, useCallback } from 'react';

export const useFilters = () => {
  const [filters, setFilters] = useState({
    source: '',
    author: '',
    dateRange: '',
    customStartDate: '',
    customEndDate: '',
    limit: 10,
    offset: 0,
  });

  const updateFilter = useCallback((key, value) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
      // Reset offset when changing filters
      offset: key !== 'offset' && key !== 'limit' ? 0 : prev.offset,
    }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({
      source: '',
      author: '',
      dateRange: '',
      customStartDate: '',
      customEndDate: '',
      limit: 10,
      offset: 0,
    });
  }, []);

  const buildApiFilters = useCallback(() => {
    const apiFilters = {
      limit: filters.limit,
      offset: filters.offset,
    };

    if (filters.source) {
      apiFilters.source = filters.source;
    }

    if (filters.author) {
      apiFilters.author = filters.author;
    }

    if (filters.dateRange) {
      apiFilters.date_range = filters.dateRange;
    }

    if (filters.customStartDate && filters.customEndDate) {
      apiFilters.custom_start = filters.customStartDate;
      apiFilters.custom_end = filters.customEndDate;
    }

    return apiFilters;
  }, [filters]);

  return {
    filters,
    updateFilter,
    clearFilters,
    buildApiFilters,
  };
};
