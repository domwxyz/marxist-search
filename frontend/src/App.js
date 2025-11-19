import React, { useEffect } from 'react';
import SearchBar from './components/SearchBar';
import FilterPanel from './components/FilterPanel';
import ResultsList from './components/ResultsList';
import Pagination from './components/Pagination';
import StatsDisplay from './components/StatsDisplay';
import { useSearch } from './hooks/useSearch';
import { useFilters } from './hooks/useFilters';

function App() {
  const {
    query,
    setQuery,
    results,
    total,
    loading,
    error,
    queryTime,
    page,
    debouncedSearch,
  } = useSearch();

  const { filters, updateFilter, clearFilters, buildApiFilters } = useFilters();

  // Perform search when query or filters change
  useEffect(() => {
    if (query.trim()) {
      const apiFilters = buildApiFilters();
      debouncedSearch(query, apiFilters);
    }
  }, [query, filters, buildApiFilters, debouncedSearch]);

  const handleSearch = () => {
    if (query.trim()) {
      const apiFilters = buildApiFilters();
      debouncedSearch(query, apiFilters, true); // Immediate search
    }
  };

  const handlePageChange = (newPage) => {
    const newOffset = (newPage - 1) * filters.limit;
    updateFilter('offset', newOffset);
  };

  const handleLimitChange = (newLimit) => {
    updateFilter('limit', newLimit);
    updateFilter('offset', 0); // Reset to first page
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">
            Marxist Article Search
          </h1>
          <p className="text-gray-600 mt-1">
            Search across 16,000+ articles from revolutionary communist publications
          </p>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Stats Display */}
        <StatsDisplay />

        {/* Search Bar */}
        <SearchBar
          query={query}
          onQueryChange={setQuery}
          onSearch={handleSearch}
        />

        {/* Filter Panel */}
        <FilterPanel
          filters={filters}
          onFilterChange={updateFilter}
          onClearFilters={clearFilters}
        />

        {/* Results List */}
        <ResultsList
          results={results}
          total={total}
          queryTime={queryTime}
          loading={loading}
          error={error}
        />

        {/* Pagination */}
        {results.length > 0 && (
          <Pagination
            currentPage={page}
            totalResults={total}
            limit={filters.limit}
            onPageChange={handlePageChange}
            onLimitChange={handleLimitChange}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <p className="text-center text-gray-600 text-sm">
            Marxist Article Search Engine - Search across decades of revolutionary theory and analysis
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
