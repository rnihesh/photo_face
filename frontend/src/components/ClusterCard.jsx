import { useState } from "react";
import { updateClusterName } from "../services/api";
import { getFaceCropUrl } from "../services/api";

const ClusterCard = ({ cluster, onClick }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(cluster.name || "");
  const [saving, setSaving] = useState(false);

  const handleSaveName = async (e) => {
    e.stopPropagation();
    if (!name.trim()) {
      setIsEditing(false);
      setName(cluster.name || "");
      return;
    }

    try {
      setSaving(true);
      await updateClusterName(cluster.id, name.trim());
      setIsEditing(false);
    } catch (err) {
      console.error("Error updating cluster name:", err);
      alert("Failed to update name");
      setName(cluster.name || "");
    } finally {
      setSaving(false);
    }
  };

  const handleDoubleClick = (e) => {
    e.stopPropagation();
    setIsEditing(true);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") {
      handleSaveName(e);
    } else if (e.key === "Escape") {
      setIsEditing(false);
      setName(cluster.name || "");
    }
  };

  return (
    <div
      onClick={() => {
        console.log("ClusterCard clicked:", cluster.id, cluster);
        onClick();
      }}
      className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden border border-gray-200 dark:border-gray-700 hover:shadow-lg dark:hover:shadow-gray-900/50 transition-all cursor-pointer group"
    >
      {/* Thumbnail */}
      <div className="aspect-square bg-gray-100 dark:bg-gray-700 relative overflow-hidden">
        {cluster.representative_face_id ? (
          <img
            src={getFaceCropUrl(cluster.representative_face_id)}
            alt={cluster.name || "Unknown"}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-6xl">
            👤
          </div>
        )}

        {/* Face count badge */}
        <div className="absolute top-2 right-2 bg-black/70 text-white px-2 py-1 rounded-full text-xs font-semibold">
          {cluster.face_count} {cluster.face_count === 1 ? "photo" : "photos"}
        </div>
      </div>

      {/* Name section */}
      <div className="p-4">
        {isEditing ? (
          <div onClick={(e) => e.stopPropagation()}>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyPress}
              onBlur={handleSaveName}
              disabled={saving}
              autoFocus
              className="w-full px-2 py-1 border border-blue-500 dark:border-blue-400 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
              placeholder="Enter name..."
            />
          </div>
        ) : (
          <div
            onDoubleClick={handleDoubleClick}
            className="flex items-center justify-between"
          >
            <h3 className="font-semibold text-gray-900 dark:text-white truncate">
              {cluster.name || "Unknown Person"}
            </h3>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsEditing(true);
              }}
              className="text-gray-400 dark:text-gray-500 hover:text-blue-500 dark:hover:text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity"
              title="Edit name"
            >
              ✏️
            </button>
          </div>
        )}
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          ID: {cluster.id}
        </p>
      </div>
    </div>
  );
};

export default ClusterCard;
