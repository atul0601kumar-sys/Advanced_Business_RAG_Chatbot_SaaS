"use client";

import { useEffect, useMemo, useState } from "react";

import { ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import { useToast } from "@/components/toast-provider";
import { apiRequest } from "@/lib/auth";

type Workspace = {
  id: string;
  name: string;
  role: string;
};

type WebsiteSource = {
  id: string;
  workspace_id: string;
  document_id: string | null;
  url: string;
  domain: string | null;
  page_title: string | null;
  title: string | null;
  crawl_status: "pending" | "crawling" | "indexed" | "failed";
  crawl_date: string | null;
  last_crawled_at: string | null;
  checksum: string | null;
  chunk_count: number;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

type WebsiteSourceActionResponse = {
  message: string;
  source: WebsiteSource | null;
};

const statusStyles: Record<WebsiteSource["crawl_status"], string> = {
  pending: "border-amber-400/25 bg-amber-500/10 text-amber-100",
  crawling: "border-sky-400/25 bg-sky-500/10 text-sky-100",
  indexed: "border-emerald-400/25 bg-emerald-500/10 text-emerald-100",
  failed: "border-rose-400/25 bg-rose-500/10 text-rose-100",
};

function formatDate(value: string | null) {
  if (!value) {
    return "Not available yet";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function WebsiteSourcesManager() {
  const { pushToast } = useToast();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [sources, setSources] = useState<WebsiteSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [url, setUrl] = useState("");
  const [domainRoot, setDomainRoot] = useState("");
  const [maxDepth, setMaxDepth] = useState("1");
  const [maxPages, setMaxPages] = useState("10");

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null,
    [selectedWorkspaceId, workspaces],
  );
  const canManageSources = selectedWorkspace?.role !== "viewer";

  useEffect(() => {
    let active = true;

    async function loadWorkspaces() {
      setIsLoading(true);
      setError("");
      try {
        const workspaceList = await apiRequest<Workspace[]>("/api/v1/workspaces");
        if (!active) {
          return;
        }
        setWorkspaces(workspaceList);
        if (workspaceList.length) {
          setSelectedWorkspaceId((current) => current || workspaceList[0].id);
        }
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load workspaces.");
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    void loadWorkspaces();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      setSources([]);
      return;
    }

    let active = true;
    async function loadSources() {
      setIsLoading(true);
      setError("");
      try {
        const sourceList = await apiRequest<WebsiteSource[]>(
          `/api/v1/workspaces/${selectedWorkspaceId}/website-sources`,
        );
        if (!active) {
          return;
        }
        setSources(sourceList);
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load website sources.");
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    void loadSources();

    return () => {
      active = false;
    };
  }, [selectedWorkspaceId]);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      return;
    }
    const hasActiveCrawl = sources.some((source) =>
      ["pending", "crawling"].includes(source.crawl_status),
    );
    if (!hasActiveCrawl) {
      return;
    }

    const interval = window.setInterval(() => {
      void refreshSources();
    }, 2500);
    return () => window.clearInterval(interval);
  }, [selectedWorkspaceId, sources]);

  async function refreshSources() {
    if (!selectedWorkspaceId) {
      return;
    }
    const sourceList = await apiRequest<WebsiteSource[]>(
      `/api/v1/workspaces/${selectedWorkspaceId}/website-sources`,
    );
    setSources(sourceList);
  }

  function countFor(status: WebsiteSource["crawl_status"]) {
    return sources.filter((source) => source.crawl_status === status).length;
  }

  async function handleAddSource() {
    if (!selectedWorkspaceId) {
      return;
    }
    if (!canManageSources) {
      pushToast({
        title: "Read-only workspace",
        description: "Viewer access can review crawl status but cannot add, refresh, or delete sources.",
        tone: "error",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await apiRequest<WebsiteSourceActionResponse>(
        `/api/v1/workspaces/${selectedWorkspaceId}/website-sources`,
        {
          method: "POST",
          json: {
            url,
            domain_root: domainRoot || undefined,
            max_depth: Number(maxDepth),
            max_pages: Number(maxPages),
          },
        },
      );
      setUrl("");
      setDomainRoot("");
      await refreshSources();
      pushToast({
        title: "Website source queued",
        description: response.message,
        tone: "info",
      });
    } catch (submitError) {
      pushToast({
        title: "Could not add source",
        description: submitError instanceof Error ? submitError.message : "Request failed.",
        tone: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRefreshSource(sourceId: string, label: string) {
    try {
      const response = await apiRequest<WebsiteSourceActionResponse>(
        `/api/v1/workspaces/${selectedWorkspaceId}/website-sources/${sourceId}/reindex`,
        { method: "POST" },
      );
      await refreshSources();
      pushToast({
        title: `${label} refresh queued`,
        description: response.message,
        tone: "info",
      });
    } catch (refreshError) {
      pushToast({
        title: "Refresh failed",
        description: refreshError instanceof Error ? refreshError.message : "Could not re-crawl this source.",
        tone: "error",
      });
    }
  }

  async function handleDeleteSource(sourceId: string, label: string) {
    try {
      await apiRequest(`/api/v1/workspaces/${selectedWorkspaceId}/website-sources/${sourceId}`, {
        method: "DELETE",
      });
      setSources((current) => current.filter((source) => source.id !== sourceId));
      pushToast({
        title: `${label} deleted`,
        description: "The website source, linked chunks, and indexed vectors were removed.",
        tone: "success",
      });
    } catch (deleteError) {
      pushToast({
        title: "Delete failed",
        description: deleteError instanceof Error ? deleteError.message : "Could not delete this source.",
        tone: "error",
      });
    }
  }

  if (isLoading && !workspaces.length && !sources.length) {
    return (
      <main className="space-y-6">
        <LoadingGrid rows={2} />
        <LoadingGrid rows={4} />
      </main>
    );
  }

  if (error) {
    return (
      <ErrorState
        actionLabel="Retry loading"
        description={error}
        onAction={() => window.location.reload()}
        title="Website source workspace could not be loaded"
      />
    );
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.14),transparent_35%),linear-gradient(145deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.35em] text-emerald-200/70">Web ingestion</p>
            <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">Website Source Radar</h2>
            <p className="mt-4 text-slate-300">
              Track pending, crawling, indexed, and failed URLs, then refresh stale pages without duplicating chunks or vectors.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <select
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none"
              onChange={(event) => setSelectedWorkspaceId(event.target.value)}
              value={selectedWorkspaceId}
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name} - {workspace.role}
                </option>
              ))}
            </select>
            <button
              className="rounded-full border border-white/10 bg-white/5 px-5 py-2.5 text-sm text-slate-200"
              onClick={() => void refreshSources()}
              type="button"
            >
              Refresh list
            </button>
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-4">
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">Pending</p>
            <p className="mt-3 text-2xl font-semibold text-white">{countFor("pending")}</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">Crawling</p>
            <p className="mt-3 text-2xl font-semibold text-white">{countFor("crawling")}</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">Indexed</p>
            <p className="mt-3 text-2xl font-semibold text-white">{countFor("indexed")}</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">Failed</p>
            <p className="mt-3 text-2xl font-semibold text-white">{countFor("failed")}</p>
          </div>
        </div>
      </section>

      <section className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-8">
        <div className="grid gap-4 lg:grid-cols-[1.6fr_1.2fr_0.7fr_0.7fr_auto]">
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500"
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com/pricing"
            value={url}
          />
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500"
            onChange={(event) => setDomainRoot(event.target.value)}
            placeholder="Optional domain root"
            value={domainRoot}
          />
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none"
            min="0"
            onChange={(event) => setMaxDepth(event.target.value)}
            type="number"
            value={maxDepth}
          />
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none"
            min="1"
            onChange={(event) => setMaxPages(event.target.value)}
            type="number"
            value={maxPages}
          />
          <button
            className="rounded-2xl bg-white px-5 py-3 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!url.trim() || isSubmitting || !canManageSources}
            onClick={() => void handleAddSource()}
            type="button"
          >
            Add URL
          </button>
        </div>
        <p className="mt-3 text-sm text-slate-400">
          Respectful crawling is enabled server-side with robots.txt checks, duplicate detection, per-request delays, and workspace isolation.
        </p>
      </section>

      {!sources.length ? (
        <section className="rounded-[2rem] border border-dashed border-white/15 bg-white/[0.03] p-10 text-center">
          <p className="text-sm uppercase tracking-[0.3em] text-emerald-200/70">Empty state</p>
          <h3 className="mt-3 text-2xl font-semibold text-white">No website sources connected yet</h3>
          <p className="mt-3 text-slate-400">
            Add a public URL to begin safe crawling, content extraction, and background indexing for this workspace.
          </p>
        </section>
      ) : (
        <section className="grid gap-4">
          {sources.map((source) => {
            const metadata = source.metadata_json ?? {};
            const failureReason = typeof metadata.failure_reason === "string" ? metadata.failure_reason : null;
            const processingError = typeof metadata.processing_error === "string" ? metadata.processing_error : null;
            const pageCount = typeof metadata.page_count === "number" ? metadata.page_count : null;
            const blockedUrls = Array.isArray(metadata.blocked_urls) ? metadata.blocked_urls.length : 0;

            return (
              <article
                key={source.id}
                className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6"
              >
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="max-w-3xl">
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="text-xl font-semibold text-white">
                        {source.page_title ?? source.title ?? source.domain ?? source.url}
                      </h3>
                      <span
                        className={`rounded-full border px-3 py-1 text-xs font-medium ${statusStyles[source.crawl_status]}`}
                      >
                        {source.crawl_status}
                      </span>
                    </div>
                    <a
                      className="mt-3 block break-all text-sm text-cyan-200 transition hover:text-cyan-100"
                      href={source.url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      {source.url}
                    </a>
                    <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500">
                      <span>{source.domain ?? "Unknown domain"}</span>
                      <span>{pageCount ? `${pageCount} pages indexed` : "Awaiting crawl"}</span>
                      <span>{source.chunk_count} indexed chunks</span>
                      <span>{blockedUrls} blocked or skipped URLs</span>
                      <span>Last crawl: {formatDate(source.last_crawled_at)}</span>
                    </div>
                    {failureReason || processingError ? (
                      <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-500/10 p-4 text-sm text-rose-100">
                        <p className="font-medium">Failure reason: {failureReason ?? "crawl_failed"}</p>
                        <p className="mt-2 text-rose-100/80">{processingError ?? "No additional details."}</p>
                      </div>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <button
                      className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!canManageSources}
                      onClick={() =>
                        void handleRefreshSource(source.id, source.page_title ?? source.domain ?? "Source")
                      }
                      type="button"
                    >
                      Re-crawl
                    </button>
                    <button
                      className="rounded-full border border-rose-400/20 bg-rose-500/10 px-4 py-2 text-sm text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!canManageSources}
                      onClick={() =>
                        void handleDeleteSource(source.id, source.page_title ?? source.domain ?? "Source")
                      }
                      type="button"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}
