import React from 'react';

const ResultCard = ({ result }) => {
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getExcerpt = (text, maxLength = 200) => {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  const highlightMatchedPhrase = (excerpt, matchedPhrase) => {
    if (!excerpt || !matchedPhrase) {
      return <span>{excerpt}</span>;
    }

    // Find the first occurrence (case-insensitive)
    const lowerExcerpt = excerpt.toLowerCase();
    const lowerPhrase = matchedPhrase.toLowerCase();
    const pos = lowerExcerpt.indexOf(lowerPhrase);

    if (pos === -1) {
      return <span>{excerpt}</span>;
    }

    // Split the excerpt and wrap the matched phrase in <strong>
    const before = excerpt.substring(0, pos);
    const matched = excerpt.substring(pos, pos + matchedPhrase.length);
    const after = excerpt.substring(pos + matchedPhrase.length);

    return (
      <span>
        {before}
        <strong className="font-bold">{matched}</strong>
        {after}
      </span>
    );
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 sm:p-5 hover:shadow-md transition-shadow">
      <h3 className="text-lg sm:text-xl font-semibold text-gray-900 mb-2">
        <a
          href={result.url}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-marxist-red transition-colors"
        >
          {result.title}
        </a>
      </h3>

      <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 text-xs sm:text-sm text-gray-600 mb-3">
        <span className="font-medium">{result.source}</span>
        {result.author && (
          <>
            <span>•</span>
            <span className="truncate max-w-[200px]">{result.author}</span>
          </>
        )}
        <span>•</span>
        <span>{formatDate(result.published_date)}</span>
      </div>

      <p className="text-gray-700 mb-3 leading-relaxed text-sm sm:text-base">
        {result.matched_phrase
          ? highlightMatchedPhrase(result.excerpt, result.matched_phrase)
          : <span>{result.excerpt}</span>
        }
      </p>

      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0">
        <div className="flex items-center gap-2 sm:gap-3">
          <a
            href={result.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-marxist-red hover:text-red-700 font-medium text-xs sm:text-sm"
          >
            Read Article →
          </a>
          {result.matched_sections > 1 && (
            <span className="inline-flex items-center px-2 sm:px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
              {result.matched_sections} sections
            </span>
          )}
        </div>
        <div className="text-xs sm:text-sm text-gray-500">
          Score: {result.score.toFixed(2)}
        </div>
      </div>
    </div>
  );
};

export default ResultCard;
