import { useState, useEffect } from "react";
import { getStats } from "../services/api";

const StatsCard = ({ title, value, icon, subtitle }) => (
  <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 border border-gray-200 dark:border-gray-700">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
          {title}
        </p>
        <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
          {value}
        </p>
        {subtitle && (
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
            {subtitle}
          </p>
        )}
      </div>
      <div className="text-4xl">{icon}</div>
    </div>
  </div>
);

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const data = await getStats();
        setStats(data);
        setError(null);
      } catch (err) {
        setError(
          "Failed to load statistics. Make sure the API server is running."
        );
        console.error("Error fetching stats:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
    // Refresh stats every 30 seconds
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Dashboard
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Overview of your photo face collection
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatsCard
          title="Total Photos"
          value={stats?.total_photos?.toLocaleString() || 0}
          icon="📸"
          subtitle={`${stats?.processed_photos || 0} processed`}
        />

        <StatsCard
          title="Faces Detected"
          value={stats?.total_faces?.toLocaleString() || 0}
          icon="👤"
          subtitle={`Across all photos`}
        />

        <StatsCard
          title="Face Collections"
          value={stats?.total_clusters?.toLocaleString() || 0}
          icon="👥"
          subtitle={`${stats?.named_clusters || 0} named`}
        />
      </div>

      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-blue-900 dark:text-blue-100 mb-2">
          🎯 Quick Actions
        </h3>
        <ul className="space-y-2 text-blue-800 dark:text-blue-200">
          <li>• Click on &quot;Collections&quot; to browse and name people</li>
          <li>• Each collection groups photos of the same person</li>
          <li>• Click on a collection to see all photos of that person</li>
          <li>• Double-click a collection name to rename it</li>
        </ul>
      </div>
    </div>
  );
};

export default Dashboard;
