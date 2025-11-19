import React, { useState, useEffect } from 'react';
import { getStats } from '../utils/api';

const StatsDisplay = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const data = await getStats();
        setStats(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadStats();
  }, []);

  if (loading) {
    return (
      <div className="w-full max-w-4xl mx-auto mb-6">
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <p className="text-gray-600">Loading statistics...</p>
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return null;
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="w-full max-w-4xl mx-auto mb-6">
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-gray-600">Total Articles</p>
            <p className="text-2xl font-bold text-gray-900">
              {stats.total_articles?.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Sources</p>
            <p className="text-2xl font-bold text-gray-900">
              {stats.sources_count}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Earliest Article</p>
            <p className="text-lg font-semibold text-gray-900">
              {stats.date_range?.earliest ? formatDate(stats.date_range.earliest) : 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Latest Article</p>
            <p className="text-lg font-semibold text-gray-900">
              {stats.date_range?.latest ? formatDate(stats.date_range.latest) : 'N/A'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StatsDisplay;
