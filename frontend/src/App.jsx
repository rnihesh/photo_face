import { useState, useEffect } from "react";
import Dashboard from "./components/Dashboard";
import ClusterList from "./components/ClusterList";
import ClusterDetail from "./components/ClusterDetail";
import { healthCheck } from "./services/api";

function App() {
  const [currentView, setCurrentView] = useState("dashboard");
  const [selectedClusterId, setSelectedClusterId] = useState(null);
  const [darkMode, setDarkMode] = useState(true);
  const [apiStatus, setApiStatus] = useState("checking");

  // Check API health on mount
  useEffect(() => {
    const checkAPI = async () => {
      try {
        await healthCheck();
        setApiStatus("connected");
      } catch (err) {
        setApiStatus("disconnected");
      }
    };
    checkAPI();
  }, []);

  // Apply dark mode
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [darkMode]);

  const handleSelectCluster = (clusterId) => {
    setSelectedClusterId(clusterId);
    setCurrentView("detail");
  };

  const handleBackToList = () => {
    setCurrentView("collections");
    setSelectedClusterId(null);
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      {/* Navigation Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo and Title */}
            <div className="flex items-center space-x-3">
              <div className="text-3xl">📸</div>
              <div>
                <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                  Photo Face Detection
                </h1>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Powered by Apple Silicon M4 Pro
                </p>
              </div>
            </div>

            {/* Navigation */}
            <nav className="flex items-center space-x-6">
              <button
                onClick={() => setCurrentView("dashboard")}
                className={`text-sm font-medium transition-colors ${
                  currentView === "dashboard"
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                }`}
              >
                Dashboard
              </button>
              <button
                onClick={() => setCurrentView("collections")}
                className={`text-sm font-medium transition-colors ${
                  currentView === "collections" || currentView === "detail"
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                }`}
              >
                Collections
              </button>

              {/* Dark mode toggle */}
              <button
                onClick={() => setDarkMode(!darkMode)}
                className="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                title={darkMode ? "Light mode" : "Dark mode"}
              >
                {darkMode ? "☀️" : "🌙"}
              </button>

              {/* API Status */}
              <div className="flex items-center space-x-2">
                <div
                  className={`w-2 h-2 rounded-full ${
                    apiStatus === "connected"
                      ? "bg-green-500"
                      : apiStatus === "disconnected"
                      ? "bg-red-500"
                      : "bg-yellow-500"
                  }`}
                />
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {apiStatus === "connected"
                    ? "Connected"
                    : apiStatus === "disconnected"
                    ? "Disconnected"
                    : "Checking..."}
                </span>
              </div>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {apiStatus === "disconnected" && (
          <div className="mb-6 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <p className="text-yellow-800 dark:text-yellow-200">
              ⚠️ Cannot connect to API server. Make sure it&apos;s running on{" "}
              <code className="bg-yellow-100 dark:bg-yellow-900 px-1 py-0.5 rounded">
                http://localhost:8000
              </code>
            </p>
            <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-2">
              Run:{" "}
              <code className="bg-yellow-100 dark:bg-yellow-900 px-1 py-0.5 rounded">
                cd backend && python api.py
              </code>
            </p>
          </div>
        )}

        {currentView === "dashboard" && <Dashboard />}
        {currentView === "collections" && (
          <ClusterList onSelectCluster={handleSelectCluster} />
        )}
        {currentView === "detail" && selectedClusterId && (
          <ClusterDetail
            clusterId={selectedClusterId}
            onBack={handleBackToList}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-gray-500 dark:text-gray-400">
            Built with React, FastAPI, and optimized for Apple Silicon
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
