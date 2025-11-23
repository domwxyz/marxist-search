import React, { useState } from 'react';

const SearchSyntaxHelper = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  const examples = [
    {
      query: 'capitalism imperialism',
      description: 'Basic search - semantic matching'
    },
    {
      query: '"permanent revolution"',
      description: 'Exact phrase - must match exactly'
    },
    {
      query: 'title:"The Labour Theory"',
      description: 'Search in article titles only'
    },
    {
      query: 'author:"Alan Woods"',
      description: 'Filter by specific author'
    },
    {
      query: 'title:"Theory" author:"Woods" capitalism',
      description: 'Combined - title, author, and semantic search'
    },
    {
      query: '"dialectical materialism" USSR title:"Revolution"',
      description: 'Multiple exact phrases with title search'
    }
  ];

  return (
    <div className="w-full max-w-4xl mx-auto mb-4 px-2 sm:px-0">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm text-gray-600 hover:text-marxist-red transition-colors"
      >
        <svg
          className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span className="font-medium">Advanced Search Syntax</span>
      </button>

      {isExpanded && (
        <div className="mt-3 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">
            Power User Search Syntax
          </h3>
          <div className="space-y-2">
            {examples.map((example, index) => (
              <div key={index} className="bg-white rounded p-2 border border-blue-100">
                <code className="text-xs sm:text-sm text-blue-900 font-mono block mb-1 break-words overflow-wrap-anywhere">
                  {example.query}
                </code>
                <p className="text-xs text-gray-600">{example.description}</p>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-3 border-t border-blue-200">
            <p className="text-xs text-gray-700">
              <strong>Syntax Rules:</strong>
            </p>
            <ul className="text-xs text-gray-600 mt-1 space-y-1 list-disc list-inside">
              <li><code className="bg-white px-1 rounded">"text"</code> - Exact phrase match in content</li>
              <li><code className="bg-white px-1 rounded">title:"text"</code> - Search in article titles only</li>
              <li><code className="bg-white px-1 rounded">author:"Name"</code> - Filter by author</li>
              <li>Combine multiple syntax elements in one query</li>
              <li>Regular words use semantic search (similar meaning)</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchSyntaxHelper;
