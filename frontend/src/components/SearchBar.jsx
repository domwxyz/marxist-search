import React from 'react';

const SearchBar = ({ query, onQueryChange, onSearch }) => {
  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch();
  };

  return (
    <div className="w-full max-w-4xl mx-auto mb-6 px-2 sm:px-0">
      <form onSubmit={handleSubmit}>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search 16,000+ articles..."
            className="flex-1 px-3 sm:px-4 py-2 sm:py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-marxist-red focus:border-transparent text-base sm:text-lg"
          />
          <button
            type="submit"
            className="px-4 sm:px-6 py-2 sm:py-3 bg-marxist-red text-white rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-marxist-red focus:ring-offset-2 transition-colors font-semibold text-sm sm:text-base"
          >
            Search
          </button>
        </div>
      </form>
    </div>
  );
};

export default SearchBar;
