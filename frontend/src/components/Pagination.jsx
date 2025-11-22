import React from 'react';

const Pagination = ({ currentPage, totalResults, limit, onPageChange }) => {
  const totalPages = Math.ceil(totalResults / limit);

  if (totalResults === 0) {
    return null;
  }

  const getPageNumbers = () => {
    const pages = [];
    const maxPagesToShow = 7;

    if (totalPages <= maxPagesToShow) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      if (currentPage <= 4) {
        for (let i = 1; i <= 5; i++) {
          pages.push(i);
        }
        pages.push('...');
        pages.push(totalPages);
      } else if (currentPage >= totalPages - 3) {
        pages.push(1);
        pages.push('...');
        for (let i = totalPages - 4; i <= totalPages; i++) {
          pages.push(i);
        }
      } else {
        pages.push(1);
        pages.push('...');
        for (let i = currentPage - 1; i <= currentPage + 1; i++) {
          pages.push(i);
        }
        pages.push('...');
        pages.push(totalPages);
      }
    }

    return pages;
  };

  const handlePrevious = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  const handlePageClick = (page) => {
    if (page !== '...' && page !== currentPage) {
      onPageChange(page);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto mt-8 mb-8 px-2 sm:px-0">
      <div className="flex items-center justify-center gap-2 sm:gap-4">
        {/* Pagination controls */}
        <div className="flex items-center gap-1 sm:gap-2">
          <button
            onClick={handlePrevious}
            disabled={currentPage === 1}
            className="px-2 sm:px-4 py-2 border border-gray-300 rounded-md text-xs sm:text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            ← <span className="hidden sm:inline">Previous</span><span className="sm:hidden">Prev</span>
          </button>

          <div className="flex gap-0.5 sm:gap-1">
            {getPageNumbers().map((page, index) => (
              <button
                key={index}
                onClick={() => handlePageClick(page)}
                disabled={page === '...' || page === currentPage}
                className={`
                  min-w-[32px] sm:min-w-[40px] px-2 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium transition-colors
                  ${page === currentPage
                    ? 'bg-marxist-red text-white'
                    : page === '...'
                    ? 'cursor-default text-gray-400'
                    : 'border border-gray-300 text-gray-700 bg-white hover:bg-gray-50'
                  }
                  ${page === '...' || page === currentPage ? 'cursor-not-allowed' : ''}
                `}
              >
                {page}
              </button>
            ))}
          </div>

          <button
            onClick={handleNext}
            disabled={currentPage === totalPages}
            className="px-2 sm:px-4 py-2 border border-gray-300 rounded-md text-xs sm:text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <span className="hidden sm:inline">Next</span><span className="sm:hidden">Next</span> →
          </button>
        </div>
      </div>

      <div className="text-center mt-4 text-xs sm:text-sm text-gray-600">
        Page {currentPage} of {totalPages}
      </div>
    </div>
  );
};

export default Pagination;
