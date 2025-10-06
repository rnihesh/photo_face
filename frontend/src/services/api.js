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
  console.log(
    "api.getClusterDetail called with:",
    clusterId,
    "type:",
    typeof clusterId
  );
  const url = `/clusters/${clusterId}`;
  console.log("Fetching URL:", url);
  const response = await api.get(url);
  console.log("Response received:", response.status, response.data);
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

// Face corrections (learning)
export const excludeFace = async (faceId) => {
  const response = await api.post(`/faces/${faceId}/exclude`);
  return response.data;
};

export const assignFaceToPerson = async (
  faceId,
  personName,
  targetClusterId
) => {
  const response = await api.post(`/faces/${faceId}/assign`, null, {
    params: {
      person_name: personName,
      target_cluster_id: targetClusterId,
    },
  });
  return response.data;
};

export const removeCorrection = async (faceId) => {
  const response = await api.delete(`/faces/${faceId}/correction`);
  return response.data;
};

// Cluster management
export const setRepresentativeFace = async (clusterId, faceId) => {
  const response = await api.put(
    `/clusters/${clusterId}/representative/${faceId}`
  );
  return response.data;
};

export const getClustersByName = async (name) => {
  const response = await api.get(`/clusters/by-name/${name}`);
  return response.data;
};

// Health check
export const healthCheck = async () => {
  const response = await api.get("/health");
  return response.data;
};

export default api;
