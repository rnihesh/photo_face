import { useEffect, useState } from "react";
import {
  assignFaceToPerson,
  excludeFace,
  getClusterDetail,
  getFaceCropUrl,
  getPhotoImageUrl,
  revealPhotoInFinder,
  setRepresentativeFace,
  updateClusterName,
} from "../services/api";

const ClusterDetail = ({ clusterId, onBack, refreshKey }) => {
  const [cluster, setCluster] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [name, setName] = useState("");
  const [hoveredFace, setHoveredFace] = useState(null);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [assignTargetFace, setAssignTargetFace] = useState(null);
  const [assignPersonName, setAssignPersonName] = useState("");
  const [notice, setNotice] = useState(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    let ignore = false;

    const loadCluster = async () => {
      try {
        setLoading(true);
        const data = await getClusterDetail(clusterId);
        if (ignore) {
          return;
        }
        setCluster(data);
        setName(data.name || "");
        setError(null);
      } catch {
        if (!ignore) {
          setError("Could not load this cluster.");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    };

    loadCluster();

    return () => {
      ignore = true;
    };
  }, [clusterId, refreshKey]);

  useEffect(() => {
    if (!selectedPhoto) {
      return;
    }
    setImageLoading(true);
    setImageError(false);
  }, [selectedPhoto]);

  const refreshCluster = async () => {
    const data = await getClusterDetail(clusterId);
    setCluster(data);
    setName(data.name || "");
    setError(null);
  };

  const handleSaveName = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setIsEditingName(false);
      setName(cluster?.name || "");
      return;
    }

    try {
      await updateClusterName(clusterId, trimmed);
      setCluster((previous) => ({ ...previous, name: trimmed, is_locked: true }));
      setIsEditingName(false);
      setNotice({ tone: "success", text: "Cluster name updated." });
    } catch {
      setNotice({ tone: "error", text: "Could not update the cluster name." });
      setName(cluster?.name || "");
      setIsEditingName(false);
    }
  };

  const handleExcludeFace = async (faceId) => {
    const confirmed = window.confirm(
      "Remove this face from the current person cluster?"
    );
    if (!confirmed) {
      return;
    }

    try {
      await excludeFace(faceId);
      await refreshCluster();
      setNotice({
        tone: "success",
        text: "Face excluded. The next sync will use this correction as a negative signal.",
      });
    } catch {
      setNotice({ tone: "error", text: "Could not exclude this face." });
    }
  };

  const handleSetRepresentative = async (faceId) => {
    try {
      await setRepresentativeFace(clusterId, faceId);
      await refreshCluster();
      setNotice({
        tone: "success",
        text: "Representative face updated.",
      });
    } catch {
      setNotice({ tone: "error", text: "Could not update the cover face." });
    }
  };

  const handleOpenAssign = (face) => {
    setAssignTargetFace(face);
    setAssignPersonName(cluster?.name || "");
  };

  const handleConfirmAssign = async () => {
    if (!assignTargetFace) {
      return;
    }
    if (!assignPersonName.trim()) {
      setNotice({ tone: "error", text: "Enter a name before reassigning." });
      return;
    }

    try {
      await assignFaceToPerson(assignTargetFace.id, assignPersonName.trim(), null);
      setAssignTargetFace(null);
      await refreshCluster();
      setNotice({
        tone: "success",
        text: `Face reassigned to ${assignPersonName.trim()}.`,
      });
    } catch {
      setNotice({ tone: "error", text: "Could not reassign this face." });
    }
  };

  const handleOpenPhotoInBrowser = (photoId) => {
    window.open(getPhotoImageUrl(photoId), "_blank", "noopener,noreferrer");
  };

  const handleRevealPhoto = async (photoId) => {
    try {
      await revealPhotoInFinder(photoId);
      setNotice({
        tone: "success",
        text: "Opened the source file in Finder.",
      });
    } catch {
      setNotice({
        tone: "error",
        text: "Could not reveal this file in Finder.",
      });
    }
  };

  if (loading) {
    return (
      <section className="surface-card rounded-[2rem] p-10 text-center">
        <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-[var(--accent-soft)] border-t-[var(--accent)]" />
        <p className="mt-4 muted-copy">Loading cluster details...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="surface-card rounded-[2rem] p-6">
        <button
          type="button"
          onClick={onBack}
          className="secondary-button px-4 py-2 text-sm font-semibold"
        >
          Back to people
        </button>
        <p className="mt-4 text-lg font-semibold text-[var(--text-primary)]">
          {error}
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[2rem] p-6 sm:p-7">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-4">
            <button
              type="button"
              onClick={onBack}
              className="secondary-button px-4 py-2 text-sm font-semibold"
            >
              Back to people
            </button>

            <div>
              <p className="eyebrow">Cluster detail</p>
              {isEditingName ? (
                <input
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      handleSaveName();
                    }
                    if (event.key === "Escape") {
                      setName(cluster?.name || "");
                      setIsEditingName(false);
                    }
                  }}
                  onBlur={handleSaveName}
                  autoFocus
                  className="field-input mt-3 max-w-xl px-4 py-3 text-lg font-semibold"
                  placeholder="Name this person"
                />
              ) : (
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <h1 className="section-title text-[var(--text-primary)]">
                    {cluster?.name || "Untitled person"}
                  </h1>
                  <button
                    type="button"
                    onClick={() => setIsEditingName(true)}
                    className="secondary-button px-4 py-2 text-sm font-semibold"
                  >
                    Rename
                  </button>
                </div>
              )}

              <p className="mt-3 text-sm muted-copy">
                {cluster?.face_count} faces in cluster #{cluster?.id}
                {cluster?.is_locked ? " • locked by manual naming" : ""}
              </p>
            </div>
          </div>

          <aside className="surface-card rounded-[1.75rem] p-5 xl:max-w-sm">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
              Correction rules
            </p>
            <p className="mt-3 text-sm muted-copy">
              Hover a face to exclude it, move it to another person, or make it
              the representative thumbnail. Click the face to inspect the
              original photo.
            </p>
          </aside>
        </div>

        {notice && (
          <div
            className={`note-banner mt-6 rounded-[1.35rem] p-4 text-sm ${
              notice.tone === "error" ? "border-rose-400/40" : ""
            }`}
          >
            {notice.text}
          </div>
        )}
      </section>

      <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
        {cluster?.faces?.map((face) => (
          <article
            key={face.id}
            className="surface-card group relative cursor-zoom-in overflow-hidden rounded-[1.6rem]"
            onMouseEnter={() => setHoveredFace(face.id)}
            onMouseLeave={() => setHoveredFace(null)}
            onClick={() => setSelectedPhoto(face)}
          >
            <button
              type="button"
              onClick={() => setSelectedPhoto(face)}
              className="block aspect-square w-full overflow-hidden bg-[var(--accent-faint)]"
            >
              <img
                src={getFaceCropUrl(face.id)}
                alt={`Face ${face.id}`}
                className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
                loading="lazy"
              />
            </button>

            <div className="flex items-center justify-between gap-2 p-2.5">
              <div>
                <p className="text-[13px] font-semibold text-[var(--text-primary)]">
                  Face #{face.id}
                </p>
                <p className="mt-1 text-[11px] muted-copy">
                  Match confidence:{" "}
                  {face.cluster_confidence
                    ? `${Math.round(face.cluster_confidence * 100)}%`
                    : "pending"}
                </p>
              </div>
              {cluster?.representative_face_id === face.id && (
                <span className="tag-pill">Cover</span>
              )}
            </div>

            {hoveredFace === face.id && (
              <div
                className="absolute inset-0 flex cursor-zoom-in flex-col justify-end gap-2 bg-black/58 p-3 text-left"
                onClick={() => setSelectedPhoto(face)}
              >
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    setSelectedPhoto(face);
                  }}
                  className="secondary-button w-full border border-white/12 bg-white/12 px-3 py-2 text-sm font-semibold text-white"
                >
                  View photo
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    handleExcludeFace(face.id);
                  }}
                  className="secondary-button w-full border border-white/12 bg-white/12 px-3 py-2 text-sm font-semibold text-white"
                >
                  Not this person
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    handleOpenAssign(face);
                  }}
                  className="secondary-button w-full border border-white/12 bg-white/12 px-3 py-2 text-sm font-semibold text-white"
                >
                  Move to another person
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    handleSetRepresentative(face.id);
                  }}
                  className="primary-button w-full px-3 py-2 text-sm font-semibold"
                >
                  Use as cover face
                </button>
              </div>
            )}
          </article>
        ))}
      </section>

      {assignTargetFace && (
        <div
          className="modal-shell fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={() => setAssignTargetFace(null)}
        >
          <div
            className="surface-card w-full max-w-md rounded-[2rem] p-6"
            onClick={(event) => event.stopPropagation()}
          >
            <p className="eyebrow">Reassign face</p>
            <h3 className="section-title mt-3 text-[var(--text-primary)]">
              Move this face to another identity.
            </h3>
            <p className="mt-3 text-sm muted-copy">
              Use a name that already exists or type a brand-new one to create a
              locked cluster.
            </p>
            <input
              type="text"
              value={assignPersonName}
              onChange={(event) => setAssignPersonName(event.target.value)}
              className="field-input mt-5 px-4 py-3 text-sm"
              placeholder="Person name"
              autoFocus
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  handleConfirmAssign();
                }
              }}
            />
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleConfirmAssign}
                className="primary-button flex-1 px-4 py-3 text-sm font-semibold"
              >
                Save reassignment
              </button>
              <button
                type="button"
                onClick={() => setAssignTargetFace(null)}
                className="secondary-button px-4 py-3 text-sm font-semibold"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedPhoto && (
        <div
          className="modal-shell fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={() => setSelectedPhoto(null)}
        >
          <div
            className="surface-card flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-[2rem]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 border-b border-[var(--border-soft)] p-5">
              <div>
                <p className="eyebrow">Original photo</p>
                <h3 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                  Photo #{selectedPhoto.photo_id}
                </h3>
                <p className="mt-2 text-sm muted-copy">
                  Source: {selectedPhoto.photo_path}
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => handleOpenPhotoInBrowser(selectedPhoto.photo_id)}
                  className="secondary-button px-4 py-2 text-sm font-semibold"
                >
                  Open image
                </button>
                <button
                  type="button"
                  onClick={() => handleRevealPhoto(selectedPhoto.photo_id)}
                  className="secondary-button px-4 py-2 text-sm font-semibold"
                >
                  Show in Finder
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedPhoto(null)}
                  className="secondary-button px-4 py-2 text-sm font-semibold"
                >
                  Close
                </button>
              </div>
            </div>

            <div className="min-h-[320px] flex-1 overflow-auto p-5">
              {imageLoading && (
                <div className="flex h-80 items-center justify-center">
                  <div className="h-12 w-12 animate-spin rounded-full border-4 border-[var(--accent-soft)] border-t-[var(--accent)]" />
                </div>
              )}

              {imageError && (
                <div className="flex h-80 items-center justify-center text-sm muted-copy">
                  The original photo could not be loaded.
                </div>
              )}

              <img
                src={getPhotoImageUrl(selectedPhoto.photo_id)}
                alt={`Photo ${selectedPhoto.photo_id}`}
                className={`mx-auto max-h-[70vh] max-w-full rounded-[1.5rem] ${
                  imageLoading || imageError ? "hidden" : "block"
                }`}
                onLoadStart={() => {
                  setImageLoading(true);
                  setImageError(false);
                }}
                onLoad={() => setImageLoading(false)}
                onError={() => {
                  setImageLoading(false);
                  setImageError(true);
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClusterDetail;
