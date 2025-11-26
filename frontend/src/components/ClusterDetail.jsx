import { useState, useEffect } from "react";
import {
  getClusterDetail,
  updateClusterName,
  excludeFace,
  assignFaceToPerson,
  setRepresentativeFace,
  getClusters,
} from "../services/api";
import { getFaceCropUrl, getPhotoImageUrl } from "../services/api";

const ClusterDetail = ({ clusterId, onBack }) => {
  const [cluster, setCluster] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [name, setName] = useState("");
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [hoveredFace, setHoveredFace] = useState(null);
  const [showAssignModal, setShowAssignModal] = useState(null);
  const [assignPersonName, setAssignPersonName] = useState("");
  const [allClusters, setAllClusters] = useState([]);

  // Reset image states when photo changes
  useEffect(() => {
    if (selectedPhoto) {
      setImageLoading(true);
      setImageError(false);
    }
  }, [selectedPhoto]);

  useEffect(() => {
    const fetchClusterDetail = async () => {
      try {
        setLoading(true);
        const data = await getClusterDetail(clusterId);
        setCluster(data);
        setName(data.name || "");
        setError(null);
      } catch (err) {
        console.error("Error fetching cluster detail:", err);
        setError("Failed to load collection details");
      } finally {
        setLoading(false);
      }
    };

    const fetchAllClusters = async () => {
      try {
        const clusters = await getClusters({ limit: 1000 });
        setAllClusters(clusters);
      } catch (err) {
        console.error("Error fetching clusters:", err);
      }
    };

    fetchClusterDetail();
    fetchAllClusters();
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

  const handleExcludeFace = async (faceId) => {
    if (
      !confirm(
        "Mark this face as 'not this person'? This will help the system learn."
      )
    ) {
      return;
    }

    try {
      await excludeFace(faceId);
      // Reload cluster data
      const data = await getClusterDetail(clusterId);
      setCluster(data);
      alert("Face excluded! Re-run clustering to apply this learning.");
    } catch (err) {
      console.error("Error excluding face:", err);
      alert("Failed to exclude face");
    }
  };

  const handleSetRepresentative = async (faceId) => {
    try {
      await setRepresentativeFace(clusterId, faceId);
      setCluster({ ...cluster, representative_face_id: faceId });
      alert("Key photo set!");
    } catch (err) {
      console.error("Error setting representative:", err);
      alert("Failed to set key photo");
    }
  };

  const handleAssignFace = async (face) => {
    setShowAssignModal(face);
    setAssignPersonName(cluster.name || "");
  };

  const handleConfirmAssign = async () => {
    if (!assignPersonName.trim()) {
      alert("Please enter a person's name");
      return;
    }

    try {
      await assignFaceToPerson(
        showAssignModal.id,
        assignPersonName.trim(),
        clusterId
      );
      setShowAssignModal(null);
      // Reload cluster
      const data = await getClusterDetail(clusterId);
      setCluster(data);
      alert(
        `Assigned to "${assignPersonName.trim()}"! Re-run clustering to apply this learning.`
      );
    } catch (err) {
      console.error("Error assigning face:", err);
      alert("Failed to assign face");
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
            className="relative aspect-square bg-gray-100 dark:bg-gray-700 rounded-lg overflow-hidden group"
            onMouseEnter={() => setHoveredFace(face.id)}
            onMouseLeave={() => setHoveredFace(null)}
            onClick={() => setSelectedPhoto(face)}
          >
            <img
              src={getFaceCropUrl(face.id)}
              alt={`Face ${face.id}`}
              className="w-full h-full object-cover cursor-pointer"
              loading="lazy"
            />

            {/* Action buttons on hover */}
            {hoveredFace === face.id && (
              <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center gap-2 p-2 pointer-events-none">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleExcludeFace(face.id);
                  }}
                  className="w-full px-2 py-1 bg-red-500 hover:bg-red-600 text-white text-xs rounded pointer-events-auto"
                  title="Mark as 'not this person'"
                >
                  ✖ Not this person
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleAssignFace(face);
                  }}
                  className="w-full px-2 py-1 bg-blue-500 hover:bg-blue-600 text-white text-xs rounded pointer-events-auto"
                  title="Assign to different person"
                >
                  ↔ Reassign
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSetRepresentative(face.id);
                  }}
                  className="w-full px-2 py-1 bg-green-500 hover:bg-green-600 text-white text-xs rounded pointer-events-auto"
                  title="Set as key photo for this cluster"
                >
                  ⭐ Set as key
                </button>
              </div>
            )}

            {/* Key photo indicator */}
            {cluster.representative_face_id === face.id && (
              <div className="absolute top-1 right-1 bg-yellow-400 text-yellow-900 px-1 rounded text-xs font-bold">
                ⭐
              </div>
            )}
          </div>
        ))}
      </div>{" "}
      {/* Assign modal */}
      {showAssignModal && (
        <div
          className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
          onClick={() => setShowAssignModal(null)}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Assign Face to Person
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Enter the person's name. The system will learn from this and apply
              it when you re-cluster.
            </p>
            <input
              type="text"
              value={assignPersonName}
              onChange={(e) => setAssignPersonName(e.target.value)}
              placeholder="Person's name..."
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white mb-4"
              autoFocus
              onKeyPress={(e) => e.key === "Enter" && handleConfirmAssign()}
            />
            <div className="flex gap-2">
              <button
                onClick={handleConfirmAssign}
                className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium"
              >
                Assign
              </button>
              <button
                onClick={() => setShowAssignModal(null)}
                className="flex-1 px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-900 dark:text-white rounded-md font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
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
              {imageLoading && (
                <div className="flex items-center justify-center h-64">
                  <div className="text-gray-400">Loading image...</div>
                </div>
              )}
              {imageError && (
                <div className="flex flex-col items-center justify-center h-64 text-red-500">
                  <div>Failed to load image</div>
                  <div className="text-sm mt-2">
                    Photo ID: {selectedPhoto.photo_id}
                  </div>
                  <div className="text-xs mt-1 text-gray-400">
                    URL: {getPhotoImageUrl(selectedPhoto.photo_id)}
                  </div>
                </div>
              )}
              <img
                src={getPhotoImageUrl(selectedPhoto.photo_id)}
                alt={`Photo ${selectedPhoto.photo_id}`}
                className={`max-w-full max-h-[70vh] mx-auto ${
                  imageLoading || imageError ? "hidden" : ""
                }`}
                onLoadStart={() => {
                  setImageLoading(true);
                  setImageError(false);
                }}
                onLoad={() => setImageLoading(false)}
                onError={(e) => {
                  console.error("Image load error:", {
                    photo_id: selectedPhoto.photo_id,
                    url: e.target.src,
                    error: e,
                  });
                  setImageLoading(false);
                  setImageError(true);
                }}
              />
            </div>
            <div className="p-4 bg-gray-50 dark:bg-gray-900 text-xs text-gray-500 dark:text-gray-400">
              <p>Photo ID: {selectedPhoto.photo_id}</p>
              <p>Path: {selectedPhoto.photo_path}</p>
              <p className="mt-1 text-gray-600 dark:text-gray-500">
                Confidence: {(selectedPhoto.confidence * 100).toFixed(1)}%
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClusterDetail;
