import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { getClusters } from "../services/api";
import ClusterCard from "./ClusterCard";

const PAGE_SIZE = 40;

const ClusterList = ({ onSelectCluster, refreshKey }) => {
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [minFaces, setMinFaces] = useState(1);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const deferredSearch = useDeferredValue(search.trim());
  const querySignature = useMemo(
    () => `${minFaces}:${deferredSearch}:${refreshKey}`,
    [deferredSearch, minFaces, refreshKey]
  );

  useEffect(() => {
    setPage(0);
    setClusters([]);
  }, [querySignature]);

  useEffect(() => {
    let ignore = false;

    const fetchClusters = async () => {
      try {
        if (page === 0) {
          setLoading(true);
        } else {
          setLoadingMore(true);
        }

        const data = await getClusters({
          min_faces: minFaces,
          skip: page * PAGE_SIZE,
          limit: PAGE_SIZE,
          search: deferredSearch || undefined,
        });

        if (ignore) {
          return;
        }

        setClusters((previous) => (page === 0 ? data : [...previous, ...data]));
        setHasMore(data.length === PAGE_SIZE);
        setError(null);
      } catch {
        if (!ignore) {
          setError("Failed to load face clusters.");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    };

    fetchClusters();

    return () => {
      ignore = true;
    };
  }, [page, minFaces, deferredSearch, refreshKey]);

  if (loading && clusters.length === 0) {
    return (
      <section className="surface-card rounded-[2rem] p-10 text-center">
        <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-[var(--accent-soft)] border-t-[var(--accent)]" />
        <p className="mt-4 muted-copy">Loading people clusters...</p>
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
    <div className="space-y-6">
      <section className="surface-card rounded-[2rem] p-6 sm:p-7">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">People browser</p>
            <h2 className="section-title mt-3 text-[var(--text-primary)]">
              Browse clusters, name them, and correct misses quickly.
            </h2>
            <p className="mt-3 text-sm muted-copy">
              {clusters.length} cluster{clusters.length === 1 ? "" : "s"} in
              the current view
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by person name or cluster id"
              className="field-input px-4 py-3 text-sm"
            />

            <select
              value={minFaces}
              onChange={(event) => setMinFaces(Number(event.target.value))}
              className="field-select px-4 py-3 text-sm"
            >
              <option value={1}>1+ faces</option>
              <option value={3}>3+ faces</option>
              <option value={5}>5+ faces</option>
              <option value={10}>10+ faces</option>
              <option value={20}>20+ faces</option>
            </select>
          </div>
        </div>
      </section>

      {clusters.length === 0 ? (
        <section className="surface-card rounded-[2rem] p-10 text-center">
          <p className="section-title text-[var(--text-primary)]">
            No clusters match this view.
          </p>
          <p className="mt-3 muted-copy">
            Try lowering the minimum face count or clearing the search filter.
          </p>
        </section>
      ) : (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          {clusters.map((cluster) => (
            <ClusterCard
              key={cluster.id}
              cluster={cluster}
              onClick={() => onSelectCluster(cluster.id)}
            />
          ))}
        </section>
      )}

      {hasMore && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => setPage((value) => value + 1)}
            disabled={loadingMore}
            className="secondary-button px-5 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loadingMore ? "Loading more clusters" : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
};

export default ClusterList;
