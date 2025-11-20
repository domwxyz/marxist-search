import React from 'react';

const ResultsPerPageSelector = ({ limit, onLimitChange, totalResults, currentPage, resultsCount }) => {
  if (totalResults === 0) {
    return null;
  }

  // Calculate the range of results being shown
  const startResult = ((currentPage - 1) * limit) + 1;
  const endResult = Math.min(currentPage * limit, totalResults);

  return (
    <div className="w-full max-w-4xl mx-auto mb-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <label htmlFor="limit-top" className="text-sm text-gray-700 font-medium">
            Results per page:
          </label>
          <select
            id="limit-top"
            value={limit}
            onChange={(e) => onLimitChange(Number(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-marxist-red focus:border-transparent bg-white shadow-sm"
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
        <div className="text-sm text-gray-600">
          Showing {startResult}-{endResult} of {totalResults.toLocaleString()} results
        </div>
      </div>
    </div>
  );
};

export default ResultsPerPageSelector;
