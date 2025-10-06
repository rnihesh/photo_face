import { useState, useEffect } from "react";
import { getClusterDetail, updateClusterName } from "../services/api";
import { getFaceCropUrl, getPhotoImageUrl } from "../services/api";

const ClusterDetail = ({ clusterId, onBack }) => {
  const [cluster, setCluster] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [name, setName] = useState("");
  const [selectedPhoto, setSelectedPhoto] = useState(null);

  useEffect(() => {
    const fetchClusterDetail = async () => {
      try {
        setLoading(true);
        const data = await getClusterDetail(clusterId);
        setCluster(data);
        setName(data.name || "");
        setError(null);
      } catch (err) {
        setError("Failed to load collection details");
        console.error("Error fetching cluster detail:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchClusterDetail();
  }, [clusterId]);

  const handleSaveName = async () => {
    if (!name.trim()) {
      setIsEditingName(false);
      setName(cluster.name || "");
      return;
    }

    try {
      await updateClusterName(clusterId, name.trim());
      setCluster({ ...cluster, name: name.trim() });
      setIsEditingName(false);
    } catch (err) {
      console.error("Error updating cluster name:", err);
      alert("Failed to update name");
      setName(cluster.name || "");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">
            Loading collection...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <button
          onClick={onBack}
          className="flex items-center space-x-2 text-blue-600 dark:text-blue-400 hover:underline"
        >
          <span>←</span>
          <span>Back to Collections</span>
        </button>
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-red-800 dark:text-red-200">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={onBack}
            className="flex items-center space-x-2 text-blue-600 dark:text-blue-400 hover:underline"
          >
            <span className="text-xl">←</span>
            <span>Back</span>
          </button>

          <div>
            {isEditingName ? (
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveName();
                  if (e.key === "Escape") {
                    setIsEditingName(false);
                    setName(cluster.name || "");
                  }
                }}
                onBlur={handleSaveName}
                autoFocus
                className="text-3xl font-bold px-2 py-1 border border-blue-500 dark:border-blue-400 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                placeholder="Enter name..."
              />
            ) : (
              <div className="flex items-center space-x-3">
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                  {cluster.name || "Unknown Person"}
                </h1>
                <button
                  onClick={() => setIsEditingName(true)}
                  className="text-gray-400 dark:text-gray-500 hover:text-blue-500 dark:hover:text-blue-400"
                  title="Edit name"
                >
                  ✏️
                </button>
              </div>
            )}
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              {cluster.face_count} photo{cluster.face_count !== 1 ? "s" : ""} •
              Collection #{cluster.id}
            </p>
          </div>
        </div>
      </div>

      {/* Photo grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {cluster.faces?.map((face) => (
          <div
            key={face.id}
            onClick={() => setSelectedPhoto(face)}
            className="aspect-square bg-gray-100 dark:bg-gray-700 rounded-lg overflow-hidden cursor-pointer hover:ring-2 hover:ring-blue-500 dark:hover:ring-blue-400 transition-all group"
          >
            <img
              src={getFaceCropUrl(face.id)}
              alt={`Face ${face.id}`}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform"
              loading="lazy"
            />
          </div>
        ))}
      </div>

      {/* Photo modal */}
      {selectedPhoto && (
        <div
          className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
          onClick={() => setSelectedPhoto(null)}
        >
          <div
            className="max-w-4xl max-h-[90vh] bg-white dark:bg-gray-800 rounded-lg overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white">
                  Photo {selectedPhoto.photo_id}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Confidence: {(selectedPhoto.confidence * 100).toFixed(1)}%
                </p>
              </div>
              <button
                onClick={() => setSelectedPhoto(null)}
                className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 text-2xl"
              >
                ×
              </button>
            </div>
            <div className="p-4">
              <img
                src={getPhotoImageUrl(selectedPhoto.photo_id)}
                alt={`Photo ${selectedPhoto.photo_id}`}
                className="max-w-full max-h-[70vh] mx-auto"
              />
            </div>
            <div className="p-4 bg-gray-50 dark:bg-gray-900 text-xs text-gray-500 dark:text-gray-400">
              <p>Path: {selectedPhoto.photo_path}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClusterDetail;
