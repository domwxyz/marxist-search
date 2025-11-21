// Use relative URL in production (nginx proxies /api/ to backend)
// Falls back to localhost for local development
const BASE_URL = process.env.REACT_APP_API_URL || (
  process.env.NODE_ENV === 'production'
    ? '/api/v1'
    : 'http://localhost:8000/api/v1'
);

class ApiError extends Error {
  constructor(message, code, details) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.details = details;
  }
}

const handleResponse = async (response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      errorData.error || `HTTP ${response.status}: ${response.statusText}`,
      errorData.code || 'REQUEST_FAILED',
      errorData.details || {}
    );
  }
  return response.json();
};

export const searchArticles = async (query, filters = {}) => {
  // Extract limit and offset from filters as they should be at the root level
  const { limit = 10, offset = 0, ...apiFilters } = filters;

  const response = await fetch(`${BASE_URL}/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      filters: apiFilters,  // Filters without limit/offset
      limit,                 // limit at root level
      offset,                // offset at root level
    }),
  });

  return handleResponse(response);
};

export const getTopAuthors = async (minArticles = 10) => {
  // Build URL with query parameters manually to support relative URLs
  // (URL constructor requires absolute URLs and fails with relative paths like /api/v1)
  let url = `${BASE_URL}/top-authors`;
  if (minArticles) {
    url += `?min_articles=${minArticles}`;
  }

  const response = await fetch(url);
  return handleResponse(response);
};

export const getSources = async () => {
  const response = await fetch(`${BASE_URL}/sources`);
  return handleResponse(response);
};

export const getStats = async () => {
  const response = await fetch(`${BASE_URL}/stats`);
  return handleResponse(response);
};

export const checkHealth = async () => {
  const response = await fetch(`${BASE_URL}/health`);
  return handleResponse(response);
};
