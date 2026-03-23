import { useEffect, useState } from "react";
import { getStats } from "../services/api";

const StatCard = ({ title, value, caption, tone }) => (
  <article className="metric-card rounded-[1.75rem] p-5">
    <p className="soft-copy text-sm uppercase tracking-[0.18em]">{title}</p>
    <p
      className={`mt-3 text-4xl font-semibold tracking-tight ${
        tone === "accent"
          ? "text-[var(--accent-strong)] dark:text-[var(--accent-strong)]"
          : tone === "success"
          ? "text-[var(--success)]"
          : "text-[var(--text-primary)]"
      }`}
    >
      {value}
    </p>
    <p className="mt-2 text-sm muted-copy">{caption}</p>
  </article>
);

const Dashboard = ({
  apiStatus,
  syncStatus,
  onOpenCollections,
  onSync,
  refreshKey,
}) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (apiStatus !== "connected") {
      setLoading(false);
      return;
    }

    let ignore = false;

    const fetchStats = async () => {
      try {
        setLoading(true);
        const data = await getStats();
        if (ignore) {
          return;
        }
        setStats(data);
        setError(null);
      } catch {
        if (ignore) {
          return;
        }
        setError("Could not load dashboard stats.");
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    };

    fetchStats();
    const interval = window.setInterval(fetchStats, 30000);

    return () => {
      ignore = true;
      window.clearInterval(interval);
    };
  }, [apiStatus, refreshKey]);

  if (apiStatus !== "connected") {
    return null;
  }

  const reviewCount =
    (stats?.pending_cluster_faces || 0) + (stats?.unclustered_faces || 0);

  if (loading && !stats) {
    return (
      <section className="surface-card rounded-[2rem] p-10 text-center">
        <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-[var(--accent-soft)] border-t-[var(--accent)]" />
        <p className="mt-4 muted-copy">Loading your library overview...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="surface-card rounded-[2rem] p-6 text-center">
        <p className="text-lg font-semibold text-[var(--text-primary)]">{error}</p>
      </section>
    );
  }

  return (
    <div className="space-y-8">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Photos indexed"
          value={stats?.total_photos?.toLocaleString() || "0"}
          caption={`${stats?.processed_photos?.toLocaleString() || 0} already processed`}
          tone="accent"
        />
        <StatCard
          title="Faces detected"
          value={stats?.total_faces?.toLocaleString() || "0"}
          caption="Raw detections available for clustering"
        />
        <StatCard
          title="People groups"
          value={stats?.total_clusters?.toLocaleString() || "0"}
          caption={`${stats?.named_clusters?.toLocaleString() || 0} clusters already named`}
          tone="success"
        />
        <StatCard
          title="Needs review"
          value={reviewCount.toLocaleString()}
          caption={`${stats?.unclustered_faces || 0} faces are still unclustered`}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <article className="surface-card rounded-[2rem] p-6 sm:p-7">
          <p className="eyebrow">What changed</p>
          <h2 className="section-title mt-3 text-[var(--text-primary)]">
            The backend now behaves like an always-on librarian.
          </h2>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-[1.5rem] bg-[var(--accent-faint)] p-4">
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                New-photo detection
              </p>
              <p className="mt-2 text-sm muted-copy">
                Only new or modified files are reprocessed when the drive is
                connected and the backend starts.
              </p>
            </div>
            <div className="rounded-[1.5rem] bg-[var(--accent-faint)] p-4">
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                Stable clustering
              </p>
              <p className="mt-2 text-sm muted-copy">
                Existing clusters keep their identities instead of reusing raw
                DBSCAN labels every run.
              </p>
            </div>
            <div className="rounded-[1.5rem] bg-[var(--accent-faint)] p-4">
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                Learned corrections
              </p>
              <p className="mt-2 text-sm muted-copy">
                Manual exclusions and assignments become seeds for later syncs.
              </p>
            </div>
          </div>
        </article>

        <article className="surface-card rounded-[2rem] p-6 sm:p-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Sync briefing</p>
              <h2 className="section-title mt-3 text-[var(--text-primary)]">
                Current library pulse
              </h2>
            </div>
            <span className="tag-pill">{syncStatus.status}</span>
          </div>

          <div className="mt-5 space-y-3 text-sm muted-copy">
            <p>{syncStatus.message}</p>
            <p>Path: {syncStatus.path || "Waiting for your configured photo drive"}</p>
            <p>Cache backend: {stats?.cache_backend || syncStatus.cache_backend}</p>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onOpenCollections}
              className="primary-button px-5 py-3 text-sm font-semibold"
            >
              Browse people clusters
            </button>
            <button
              type="button"
              onClick={() => onSync({ forceRescan: false, forceRecluster: false })}
              className="secondary-button px-5 py-3 text-sm font-semibold"
            >
              Run incremental sync
            </button>
            <button
              type="button"
              onClick={() => onSync({ forceRescan: false, forceRecluster: true })}
              className="ghost-button px-5 py-3 text-sm font-semibold"
            >
              Rebuild clustering
            </button>
          </div>
        </article>
      </section>
    </div>
  );
};

export default Dashboard;
