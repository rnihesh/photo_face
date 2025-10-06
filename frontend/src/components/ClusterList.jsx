import { useState, useEffect } from "react";
import { getClusters } from "../services/api";
import ClusterCard from "./ClusterCard";

const ClusterList = ({ onSelectCluster }) => {
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    minFaces: 1,
    skip: 0,
    limit: 50,
  });

  useEffect(() => {
    const fetchClusters = async () => {
      try {
        setLoading(true);
        const data = await getClusters({
          min_faces: filters.minFaces,
          skip: filters.skip,
          limit: filters.limit,
        });
        setClusters(data);
        setError(null);
      } catch (err) {
        setError("Failed to load face collections");
        console.error("Error fetching clusters:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchClusters();
  }, [filters]);

  const handleLoadMore = () => {
    setFilters((prev) => ({ ...prev, skip: prev.skip + prev.limit }));
  };

  if (loading && clusters.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">
            Loading collections...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
        <p className="text-red-800 dark:text-red-200">{error}</p>
      </div>
    );
  }

  if (clusters.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="text-6xl mb-4">📭</div>
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
          No face collections found
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          Run the clustering script to group detected faces
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Face Collections
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {clusters.length} collection{clusters.length !== 1 ? "s" : ""} found
          </p>
        </div>

        <div className="flex items-center space-x-4">
          <label className="flex items-center space-x-2">
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Min faces:
            </span>
            <select
              value={filters.minFaces}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  minFaces: parseInt(e.target.value),
                  skip: 0,
                }))
              }
              className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
            >
              <option value="1">1+</option>
              <option value="3">3+</option>
              <option value="5">5+</option>
              <option value="10">10+</option>
              <option value="20">20+</option>
            </select>
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {clusters.map((cluster) => (
          <ClusterCard
            key={cluster.id}
            cluster={cluster}
            onClick={() => onSelectCluster(cluster.id)}
          />
        ))}
      </div>

      {clusters.length >= filters.limit && (
        <div className="text-center">
          <button
            onClick={handleLoadMore}
            disabled={loading}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Loading..." : "Load More"}
          </button>
        </div>
      )}
    </div>
  );
};

export default ClusterList;
