import { startTransition, useEffect, useRef, useState } from "react";
import Dashboard from "./components/Dashboard";
import ClusterList from "./components/ClusterList";
import ClusterDetail from "./components/ClusterDetail";
import { getSyncStatus, healthCheck, triggerSync } from "./services/api";
import "./App.css";

const RUNNING_SYNC_STATES = new Set(["discovering", "processing", "clustering"]);
const DEFAULT_ROUTE = { view: "dashboard", clusterId: null, path: "/" };

const getRouteState = (pathname) => {
  const normalizedPath = pathname === "/" ? "/" : pathname.replace(/\/+$/, "");

  if (normalizedPath === "/" || normalizedPath === "/overview") {
    return DEFAULT_ROUTE;
  }

  if (normalizedPath === "/people") {
    return { view: "collections", clusterId: null, path: "/people" };
  }

  const detailMatch = normalizedPath.match(/^\/people\/(\d+)$/);
  if (detailMatch) {
    const clusterId = Number(detailMatch[1]);
    return {
      view: "detail",
      clusterId,
      path: `/people/${clusterId}`,
    };
  }

  return DEFAULT_ROUTE;
};

const SyncBadge = ({ status }) => {
  const palette =
    status === "completed"
      ? "bg-emerald-500"
      : RUNNING_SYNC_STATES.has(status)
        ? "bg-amber-400"
        : status === "error"
          ? "bg-rose-500"
          : status === "waiting"
            ? "bg-slate-400"
            : "bg-slate-300";

  const label =
    status === "completed"
      ? "Ready"
      : RUNNING_SYNC_STATES.has(status)
        ? "Syncing"
        : status === "error"
          ? "Issue"
          : status === "waiting"
            ? "Waiting"
            : "Idle";

  return (
    <span className="status-pill">
      <span className={`h-2.5 w-2.5 rounded-full ${palette}`} />
      {label}
    </span>
  );
};

function App() {
  const [route, setRoute] = useState(() => getRouteState(window.location.pathname));
  const [darkMode, setDarkMode] = useState(() => {
    const stored = window.localStorage.getItem("photo-face-theme");
    return stored ? stored === "dark" : false;
  });
  const [apiStatus, setApiStatus] = useState("checking");
  const [syncStatus, setSyncStatus] = useState({
    status: "idle",
    message: "Waiting for the next sync.",
  });
  const [syncRequested, setSyncRequested] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const previousSyncState = useRef("idle");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
    window.localStorage.setItem("photo-face-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    const canonicalRoute = getRouteState(window.location.pathname);
    if (window.location.pathname !== canonicalRoute.path) {
      window.history.replaceState({}, "", canonicalRoute.path);
    }
    setRoute(canonicalRoute);

    const handlePopState = () => {
      setRoute(getRouteState(window.location.pathname));
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    let ignore = false;

    const readBackendState = async () => {
      try {
        await healthCheck();
        const sync = await getSyncStatus();
        if (ignore) {
          return;
        }
        setApiStatus("connected");
        setSyncStatus(sync);
      } catch {
        if (ignore) {
          return;
        }
        setApiStatus("disconnected");
      }
    };

    readBackendState();
    const interval = window.setInterval(readBackendState, 5000);

    return () => {
      ignore = true;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const previous = previousSyncState.current;
    const current = syncStatus.status;

    if (RUNNING_SYNC_STATES.has(previous) && !RUNNING_SYNC_STATES.has(current)) {
      setRefreshKey((value) => value + 1);
      setSyncRequested(false);
    }

    previousSyncState.current = current;
  }, [syncStatus.status]);

  const navigateTo = (path) => {
    const nextRoute = getRouteState(path);
    if (window.location.pathname !== nextRoute.path) {
      window.history.pushState({}, "", nextRoute.path);
    }
    setRoute(nextRoute);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleSelectCluster = (clusterId) => {
    startTransition(() => {
      navigateTo(`/people/${clusterId}`);
    });
  };

  const handleBackToList = () => {
    startTransition(() => {
      navigateTo("/people");
    });
  };

  const handleRunSync = async (options = {}) => {
    try {
      setSyncRequested(true);
      const response = await triggerSync(options);
      if (response?.status) {
        setSyncStatus(response.status);
      }
      setApiStatus("connected");
    } catch {
      setApiStatus("disconnected");
      setSyncRequested(false);
    }
  };

  const syncMeta =
    syncStatus.status === "completed"
      ? `${syncStatus.processed_photos || 0} processed, ${
          syncStatus.faces_detected || 0
        } faces detected`
      : syncStatus.message;

  return (
    <div className="app-shell min-h-screen">
      <div className="content-layer min-h-screen">
        <header className="sticky top-0 z-40 pb-4 pt-4">
          <div className="page-shell px-4 sm:px-6 lg:px-8">
            <div className="flex w-full flex-col gap-4 rounded-[2rem] glass-panel px-5 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--accent-soft)] text-2xl shadow-sm">
                  ◐
                </div>
                <div>
                  <p className="eyebrow">Face Library</p>
                  <h1 className="section-title text-[var(--text-primary)]">
                    Photo Atlas
                  </h1>
                  <p className="muted-copy text-sm">
                    Incremental face learning for your external photo drive
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-3 lg:items-end">
                <nav className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => navigateTo("/")}
                    className={`nav-button px-4 py-2 text-sm font-semibold ${
                      route.view === "dashboard" ? "is-active" : ""
                    }`}
                  >
                    Overview
                  </button>
                  <button
                    type="button"
                    onClick={() => navigateTo("/people")}
                    className={`nav-button px-4 py-2 text-sm font-semibold ${
                      route.view === "collections" || route.view === "detail"
                        ? "is-active"
                        : ""
                    }`}
                  >
                    People
                  </button>
                  <button
                    type="button"
                    onClick={() => setDarkMode((value) => !value)}
                    className="secondary-button px-4 py-2 text-sm font-semibold"
                    title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
                  >
                    {darkMode ? "Light" : "Dark"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleRunSync()}
                    disabled={
                      apiStatus !== "connected" ||
                      RUNNING_SYNC_STATES.has(syncStatus.status) ||
                      syncRequested
                    }
                    className="primary-button px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {RUNNING_SYNC_STATES.has(syncStatus.status) || syncRequested
                      ? "Syncing library"
                      : "Sync library"}
                  </button>
                </nav>

                <div className="flex flex-wrap items-center gap-2">
                  <SyncBadge status={syncStatus.status} />
                  <span className="status-pill">
                    API {apiStatus === "connected" ? "online" : "offline"}
                  </span>
                  <span className="tag-pill">
                    Cache {syncStatus.cache_backend || "memory"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </header>

        <main className="page-shell flex w-full flex-col gap-8 px-4 pb-10 sm:px-6 lg:px-8">
          {apiStatus === "disconnected" ? (
            <section className="rounded-[2rem] glass-panel p-6 note-banner">
              <p className="text-lg font-semibold text-[var(--text-primary)]">
                Backend is unreachable
              </p>
              <p className="mt-2 text-sm">
                Start the API on <code>http://localhost:8000</code> and this UI
                will reconnect automatically.
              </p>
              <p className="mt-2 text-sm">
                Command: <code>cd /Users/nihesh/Nihesh/photo_face && source .venv/bin/activate && python backend/api.py</code>
              </p>
            </section>
          ) : (
            <section className="hero-panel rounded-[2rem] glass-panel mosaic px-6 py-6 sm:px-8">
              <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
                <div className="space-y-4">
                  <p className="eyebrow">Live library status</p>
                  <div>
                    <h2 className="page-title text-[var(--text-primary)]">
                      Your drive is treated like a living library, not a batch
                      export.
                    </h2>
                    <p className="mt-4 max-w-3xl muted-copy text-base sm:text-lg">
                      The backend now scans for changes, processes only new or
                      updated photos, and reclusters only when the dataset
                      actually moved.
                    </p>
                  </div>
                </div>

                <div className="surface-card rounded-[1.75rem] p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="soft-copy text-sm uppercase tracking-[0.18em]">
                        Sync pulse
                      </p>
                      <p className="mt-2 text-lg font-semibold text-[var(--text-primary)]">
                        {syncMeta}
                      </p>
                    </div>
                    <SyncBadge status={syncStatus.status} />
                  </div>
                  <div className="mt-4 grid gap-2 text-sm muted-copy">
                    <p>Path: {syncStatus.path || "Waiting for PHOTOS_PATH"}</p>
                    <p>Last update: {syncStatus.updated_at || "Not available yet"}</p>
                  </div>
                </div>
              </div>
            </section>
          )}

          {route.view === "dashboard" && (
            <Dashboard
              apiStatus={apiStatus}
              syncStatus={syncStatus}
              onOpenCollections={() => navigateTo("/people")}
              onSync={handleRunSync}
              refreshKey={refreshKey}
            />
          )}

          {route.view === "collections" && (
            <ClusterList
              onSelectCluster={handleSelectCluster}
              refreshKey={refreshKey}
            />
          )}

          {route.view === "detail" && route.clusterId !== null && (
            <ClusterDetail
              clusterId={route.clusterId}
              onBack={handleBackToList}
              refreshKey={refreshKey}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
