import React, { useState, useEffect } from 'react';
import { getSources, getTopAuthors } from '../utils/api';

const FilterPanel = ({ filters, onFilterChange, onClearFilters }) => {
  const [sources, setSources] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [showCustomDate, setShowCustomDate] = useState(false);

  useEffect(() => {
    const loadFilters = async () => {
      try {
        const [sourcesData, authorsData] = await Promise.all([
          getSources(),
          getTopAuthors(10),
        ]);
        setSources(sourcesData.sources || []);
        setAuthors(authorsData.authors || []);
      } catch (error) {
        console.error('Failed to load filter options:', error);
      }
    };

    loadFilters();
  }, []);

  const dateRanges = [
    { value: '', label: 'Any Time' },
    { value: 'past_week', label: 'Past Week' },
    { value: 'past_month', label: 'Past Month' },
    { value: 'past_3months', label: 'Past 3 Months' },
    { value: 'past_year', label: 'Past Year' },
    { value: '2020s', label: '2020-2025 (2020s)' },
    { value: '2010s', label: '2010-2019 (2010s)' },
    { value: '2000s', label: '2000-2009 (2000s)' },
    { value: '1990s', label: '1990-1999 (1990s)' },
    { value: 'custom', label: 'Custom range...' },
  ];

  const handleDateRangeChange = (value) => {
    if (value === 'custom') {
      setShowCustomDate(true);
      onFilterChange('dateRange', '');
    } else {
      setShowCustomDate(false);
      onFilterChange('dateRange', value);
      // Clear custom date fields when switching to preset ranges
      onFilterChange('customStartDate', '');
      onFilterChange('customEndDate', '');
    }
  };

  const hasActiveFilters = filters.source || filters.author || filters.dateRange;

  return (
    <div className="w-full max-w-4xl mx-auto mb-6 px-2 sm:px-0">
      <div className="bg-white border border-gray-200 rounded-lg p-3 sm:p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4">
          {/* Source Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Source
            </label>
            <select
              value={filters.source}
              onChange={(e) => onFilterChange('source', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-marxist-red focus:border-transparent"
            >
              <option value="">All Sources</option>
              {sources.map((source) => (
                <option key={source.name} value={source.name}>
                  {source.name} ({source.article_count})
                </option>
              ))}
            </select>
          </div>

          {/* Author Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Author
            </label>
            <select
              value={filters.author}
              onChange={(e) => onFilterChange('author', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-marxist-red focus:border-transparent"
            >
              <option value="">All Authors</option>
              {authors.map((author) => (
                <option key={author.name} value={author.name}>
                  {author.name} ({author.article_count})
                </option>
              ))}
            </select>
          </div>

          {/* Date Range Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Date Range
            </label>
            <select
              value={showCustomDate ? 'custom' : filters.dateRange}
              onChange={(e) => handleDateRangeChange(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-marxist-red focus:border-transparent"
            >
              {dateRanges.map((range) => (
                <option key={range.value} value={range.value}>
                  {range.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Custom Date Range */}
        {showCustomDate && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Start Date
              </label>
              <input
                type="date"
                value={filters.customStartDate}
                onChange={(e) => onFilterChange('customStartDate', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-marxist-red focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                End Date
              </label>
              <input
                type="date"
                value={filters.customEndDate}
                onChange={(e) => onFilterChange('customEndDate', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-marxist-red focus:border-transparent"
              />
            </div>
          </div>
        )}

        {/* Clear Filters Button */}
        {hasActiveFilters && (
          <div className="mt-4">
            <button
              onClick={onClearFilters}
              className="text-sm text-marxist-red hover:text-red-700 font-medium"
            >
              Clear all filters
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default FilterPanel;
