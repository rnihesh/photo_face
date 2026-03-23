import { useEffect, useState } from "react";
import { getFaceCropUrl, updateClusterName } from "../services/api";

const ClusterCard = ({ cluster, onClick }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(cluster.name || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setName(cluster.name || "");
  }, [cluster.id, cluster.name]);

  const handleSaveName = async (event) => {
    event?.stopPropagation?.();
    const trimmed = name.trim();

    if (!trimmed) {
      setIsEditing(false);
      setName(cluster.name || "");
      return;
    }

    try {
      setSaving(true);
      await updateClusterName(cluster.id, trimmed);
      setIsEditing(false);
    } catch {
      setName(cluster.name || "");
      setIsEditing(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <article
      onClick={onClick}
      className="surface-card card-hover group cursor-pointer overflow-hidden rounded-[1.45rem]"
    >
      <div className="relative aspect-[4/4.9] overflow-hidden bg-[var(--accent-faint)]">
        {cluster.representative_face_id ? (
          <img
            src={getFaceCropUrl(cluster.representative_face_id)}
            alt={cluster.name || "Unnamed cluster"}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-6xl text-[var(--text-muted)]">
            ◌
          </div>
        )}

        <div className="cover-image absolute inset-0" />

        <div className="absolute left-3 top-3 flex flex-wrap gap-2">
          <span className="tag-pill bg-black/40 text-white backdrop-blur-md">
            {cluster.face_count} faces
          </span>
          {cluster.is_locked && (
            <span className="tag-pill bg-black/40 text-white backdrop-blur-md">
              Locked
            </span>
          )}
        </div>

        <div className="absolute bottom-3 left-3 right-3">
          {isEditing ? (
            <div onClick={(event) => event.stopPropagation()}>
              <input
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    handleSaveName(event);
                  }
                  if (event.key === "Escape") {
                    setIsEditing(false);
                    setName(cluster.name || "");
                  }
                }}
                onBlur={handleSaveName}
                disabled={saving}
                autoFocus
                className="field-input px-3 py-2 text-sm"
                placeholder="Name this person"
              />
            </div>
          ) : (
            <div className="rounded-[1.15rem] bg-black/50 p-2.5 text-white backdrop-blur-md">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-base font-semibold">
                    {cluster.name || "Untitled person"}
                  </h3>
                  <p className="mt-1 text-[11px] uppercase tracking-[0.18em] text-white/70">
                    Cluster #{cluster.id}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    setIsEditing(true);
                  }}
                  className="secondary-button h-9 w-9 border border-white/20 bg-white/10 text-sm text-white"
                  title="Rename cluster"
                >
                  ✎
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </article>
  );
};

export default ClusterCard;
