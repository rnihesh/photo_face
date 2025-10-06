import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Statistics
export const getStats = async () => {
  const response = await api.get("/stats");
  return response.data;
};

// Clusters
export const getClusters = async (params = {}) => {
  const response = await api.get("/clusters", { params });
  return response.data;
};

export const getClusterDetail = async (clusterId) => {
  const response = await api.get(`/clusters/${clusterId}`);
  return response.data;
};

export const updateClusterName = async (clusterId, name) => {
  const response = await api.put(`/clusters/${clusterId}/name`, null, {
    params: { name },
  });
  return response.data;
};

// Photos
export const getPhotoInfo = async (photoId) => {
  const response = await api.get(`/photos/${photoId}`);
  return response.data;
};

export const getPhotoImageUrl = (photoId) => {
  return `${API_BASE_URL}/photos/${photoId}/image`;
};

// Faces
export const getFaceInfo = async (faceId) => {
  const response = await api.get(`/faces/${faceId}`);
  return response.data;
};

export const getFaceCropUrl = (faceId) => {
  return `${API_BASE_URL}/faces/${faceId}/crop`;
};

// Health check
export const healthCheck = async () => {
  const response = await api.get("/health");
  return response.data;
};

export default api;
