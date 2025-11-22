import React, { useEffect } from 'react';
import SearchBar from './components/SearchBar';
import FilterPanel from './components/FilterPanel';
import ResultsList from './components/ResultsList';
import Pagination from './components/Pagination';
import ResultsPerPageSelector from './components/ResultsPerPageSelector';
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, filters]);

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
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-marxist-red shadow-md">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
          <div className="flex items-center gap-2 sm:gap-4">
            <img
              src="/logo.png"
              alt="Marxist Search Logo"
              className="h-12 w-12 sm:h-16 sm:w-16 object-contain bg-white p-1.5 sm:p-2 rounded-lg shadow-sm flex-shrink-0"
            />
            <div className="min-w-0">
              <h1 className="text-xl sm:text-3xl font-bold text-white">
                Marxist Article Search
              </h1>
              <p className="text-red-100 mt-0.5 sm:mt-1 text-xs sm:text-base">
                <span className="hidden sm:inline">Search publications from across the Revolutionary Communist International</span>
                <span className="sm:hidden">Search RCI publications</span>
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col justify-start pt-[8vh] sm:pt-[12vh] max-w-7xl mx-auto px-3 sm:px-4 py-8 sm:py-12 w-full">
        {/* Stats Display */}
        <div className="mb-8">
          <StatsDisplay />
        </div>

        {/* Search Interface Container */}
        <div className="space-y-6">
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
        </div>

        {/* Results Section */}
        <div className="mt-8">
          {/* Results Per Page Selector at Top */}
          {results.length > 0 && (
            <ResultsPerPageSelector
              limit={filters.limit}
              onLimitChange={handleLimitChange}
              totalResults={total}
              currentPage={page}
              resultsCount={results.length}
            />
          )}

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
            />
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-auto">
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
