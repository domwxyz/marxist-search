import React from 'react';
import ResultCard from './ResultCard';

const ResultsList = ({ results, total, queryTime, loading, error }) => {
  if (loading) {
    return (
      <div className="w-full max-w-4xl mx-auto px-2 sm:px-0">
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-600">Searching...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full max-w-4xl mx-auto px-2 sm:px-0">
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 sm:p-4">
          <p className="text-red-800 text-sm sm:text-base">
            <strong>Error:</strong> {error}
          </p>
        </div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="w-full max-w-4xl mx-auto px-2 sm:px-0">
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 sm:p-8 text-center">
          <p className="text-gray-600 text-sm sm:text-base">
            No articles found. Try a different search query or adjust your filters.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mx-auto px-2 sm:px-0">
      <div className="mb-4 flex flex-row items-center justify-between">
        <p className="text-gray-700 text-xs sm:text-base">
          <span className="font-semibold">{total.toLocaleString()}</span> <span className="hidden sm:inline">articles found</span><span className="sm:hidden">found</span>
        </p>
        <p className="text-xs sm:text-sm text-gray-500">
          <span className="hidden sm:inline">Query time: {queryTime}ms</span>
          <span className="sm:hidden">{queryTime}ms</span>
        </p>
      </div>

      <div className="space-y-3 sm:space-y-4">
        {results.map((result) => (
          <ResultCard key={result.id} result={result} />
        ))}
      </div>
    </div>
  );
};

export default ResultsList;
