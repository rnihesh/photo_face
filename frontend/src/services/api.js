import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const getStats = async () => {
  const response = await api.get("/stats");
  return response.data;
};

export const getSyncStatus = async () => {
  const response = await api.get("/sync/status");
  return response.data;
};

export const triggerSync = async ({
  forceRescan = false,
  forceRecluster = false,
} = {}) => {
  const response = await api.post("/sync/run", null, {
    params: {
      force_rescan: forceRescan,
      force_recluster: forceRecluster,
    },
  });
  return response.data;
};

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

export const getClustersByName = async (name) => {
  const response = await api.get(`/clusters/by-name/${name}`);
  return response.data;
};

export const setRepresentativeFace = async (clusterId, faceId) => {
  const response = await api.put(
    `/clusters/${clusterId}/representative/${faceId}`
  );
  return response.data;
};

export const getPhotoInfo = async (photoId) => {
  const response = await api.get(`/photos/${photoId}`);
  return response.data;
};

export const getPhotoImageUrl = (photoId) => {
  return `${API_BASE_URL}/photos/${photoId}/image`;
};

export const revealPhotoInFinder = async (photoId) => {
  const response = await api.post(`/photos/${photoId}/reveal`);
  return response.data;
};

export const getFaceInfo = async (faceId) => {
  const response = await api.get(`/faces/${faceId}`);
  return response.data;
};

export const getFaceCropUrl = (faceId) => {
  return `${API_BASE_URL}/faces/${faceId}/crop`;
};

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

export const healthCheck = async () => {
  const response = await api.get("/health");
  return response.data;
};

export default api;
