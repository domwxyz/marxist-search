const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

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
  const response = await fetch(`${BASE_URL}/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      filters,
    }),
  });

  return handleResponse(response);
};

export const getTopAuthors = async (minArticles = 10) => {
  const url = new URL(`${BASE_URL}/top-authors`);
  if (minArticles) {
    url.searchParams.append('min_articles', minArticles);
  }

  const response = await fetch(url.toString());
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
