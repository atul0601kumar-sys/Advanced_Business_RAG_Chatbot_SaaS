"use client";

import { useEffect, useMemo, useState } from "react";

import { useToast } from "@/components/toast-provider";
import {
  downloadExportJob,
  fetchExportJobStatus,
  requestAnalyticsExportJob,
  requestChatExportJob,
  requestFaqExportJob,
  requestLeadExportJob,
  type ExportFilters,
  type ExportFormat,
  type ExportJob,
  type ExportType,
} from "@/lib/exports";

type SessionOption = {
  id: string;
  title: string | null;
  startedAt: string;
};

type ExportModalProps = {
  open: boolean;
  onClose: () => void;
  exportType: ExportType;
  workspaceId: string;
  title: string;
  description: string;
  defaultFormat?: ExportFormat;
  initialFilters?: ExportFilters;
  sessionOptions?: SessionOption[];
};

const labels: Record<ExportType, string> = {
  chat: "chat history",
  lead: "leads",
  analytics: "analytics report",
  faq: "FAQ dataset",
};

export function ExportModal(props: ExportModalProps) {
  const { pushToast } = useToast();
  const [format, setFormat] = useState<ExportFormat>(props.defaultFormat ?? "csv");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [category, setCategory] = useState("");
  const [selectedSessionIds, setSelectedSessionIds] = useState<string[]>([]);
  const [job, setJob] = useState<ExportJob | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    if (!props.open) {
      return;
    }
    setFormat(props.defaultFormat ?? "csv");
    setDateFrom(props.initialFilters?.dateFrom ?? "");
    setDateTo(props.initialFilters?.dateTo ?? "");
    setSource(props.initialFilters?.source ?? "");
    setStatus(props.initialFilters?.status ?? (props.exportType === "faq" ? "approved" : ""));
    setPriority(props.initialFilters?.priority ?? "");
    setCategory(props.initialFilters?.category ?? "");
    setSelectedSessionIds(props.initialFilters?.sessionIds ?? []);
    setJob(null);
  }, [props.defaultFormat, props.exportType, props.open]);

  useEffect(() => {
    if (!props.open || !job || !["pending", "processing"].includes(job.status)) {
      return;
    }
    const interval = window.setInterval(() => {
      void fetchExportJobStatus(job.job_id)
        .then((nextJob) => {
          setJob(nextJob);
          if (nextJob.status === "completed") {
            pushToast({
              title: "Export ready",
              description: `Your ${labels[props.exportType]} is ready to download.`,
              tone: "success",
            });
          }
        })
        .catch((error) => {
          pushToast({
            title: "Status refresh failed",
            description: error instanceof Error ? error.message : "Could not refresh export progress.",
            tone: "error",
          });
        });
    }, 2500);
    return () => window.clearInterval(interval);
  }, [job, props.exportType, props.open, pushToast]);

  const allowedFormats = useMemo<ExportFormat[]>(
    () => (props.exportType === "analytics" ? ["pdf", "csv", "json"] : ["csv", "json", "pdf"]),
    [props.exportType],
  );

  if (!props.open) {
    return null;
  }

  function toggleSession(sessionId: string) {
    setSelectedSessionIds((current) =>
      current.includes(sessionId) ? current.filter((value) => value !== sessionId) : [...current, sessionId],
    );
  }

  async function handleSubmit() {
    if (!props.workspaceId) {
      return;
    }
    setIsSubmitting(true);
    try {
      let created: ExportJob;
      if (props.exportType === "chat") {
        created = await requestChatExportJob({
          workspaceId: props.workspaceId,
          format,
          dateFrom: dateFrom || undefined,
          dateTo: dateTo || undefined,
          source: source || undefined,
          sessionIds: selectedSessionIds,
        });
      } else if (props.exportType === "lead") {
        created = await requestLeadExportJob({
          workspaceId: props.workspaceId,
          format,
          dateFrom: dateFrom || undefined,
          dateTo: dateTo || undefined,
          source: source || undefined,
          status: status || undefined,
          priority: priority || undefined,
        });
      } else if (props.exportType === "analytics") {
        created = await requestAnalyticsExportJob({
          workspaceId: props.workspaceId,
          format,
          dateFrom: dateFrom || undefined,
          dateTo: dateTo || undefined,
          source: source || undefined,
          userId: props.initialFilters?.userId,
          documentId: props.initialFilters?.documentId,
        });
      } else {
        created = await requestFaqExportJob({
          workspaceId: props.workspaceId,
          format,
          dateFrom: dateFrom || undefined,
          dateTo: dateTo || undefined,
          source: source || undefined,
          status: status || undefined,
          category: category || undefined,
        });
      }
      setJob(created);
      pushToast({
        title: "Export queued",
        description: "The export job is running in the background.",
        tone: "info",
      });
    } catch (error) {
      pushToast({
        title: "Export failed to start",
        description: error instanceof Error ? error.message : "Please try again.",
        tone: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDownload() {
    if (!job) {
      return;
    }
    setIsDownloading(true);
    try {
      await downloadExportJob(job.job_id, job.file_name ?? `${props.exportType}-export.${job.format}`);
      pushToast({
        title: "Download started",
        description: "The export file has been downloaded.",
        tone: "success",
      });
    } catch (error) {
      pushToast({
        title: "Download failed",
        description: error instanceof Error ? error.message : "Could not download the export.",
        tone: "error",
      });
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="w-full max-w-3xl rounded-[2rem] border border-white/10 bg-slate-950 p-6 shadow-2xl shadow-slate-950/50">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-sky-200/75">Export Center</p>
            <h3 className="mt-2 text-2xl font-semibold text-white">{props.title}</h3>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">{props.description}</p>
          </div>
          <button
            className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-sm text-white transition hover:bg-white/10"
            onClick={props.onClose}
            type="button"
          >
            Close
          </button>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Format</span>
            <select
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
              value={format}
              onChange={(event) => setFormat(event.target.value as ExportFormat)}
            >
              {allowedFormats.map((item) => (
                <option key={item} value={item}>
                  {item.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Workspace</span>
            <input
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-400 outline-none"
              readOnly
              value={props.workspaceId}
            />
          </label>
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Date From</span>
            <input
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </label>
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Date To</span>
            <input
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
              type="date"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </label>
          <label className="space-y-2 md:col-span-2">
            <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Source</span>
            <input
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500"
              placeholder="Optional source filter"
              value={source}
              onChange={(event) => setSource(event.target.value)}
            />
          </label>
          {props.exportType === "lead" ? (
            <>
              <label className="space-y-2">
                <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Status</span>
                <select
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  <option value="">All statuses</option>
                  <option value="new">New</option>
                  <option value="contacted">Contacted</option>
                  <option value="qualified">Qualified</option>
                  <option value="converted">Converted</option>
                  <option value="closed">Closed</option>
                </select>
              </label>
              <label className="space-y-2">
                <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Priority</span>
                <select
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
                  value={priority}
                  onChange={(event) => setPriority(event.target.value)}
                >
                  <option value="">All priorities</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
            </>
          ) : null}
          {props.exportType === "faq" ? (
            <>
              <label className="space-y-2">
                <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Status</span>
                <select
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  <option value="approved">Approved</option>
                  <option value="draft">Draft</option>
                  <option value="rejected">Rejected</option>
                </select>
              </label>
              <label className="space-y-2">
                <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Category</span>
                <input
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500"
                  placeholder="Optional category"
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                />
              </label>
            </>
          ) : null}
        </div>

        {props.exportType === "chat" && props.sessionOptions?.length ? (
          <div className="mt-6 rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-white">Selected sessions</p>
                <p className="mt-1 text-xs text-slate-400">
                  Leave all unchecked to export every session that matches the filters.
                </p>
              </div>
              {selectedSessionIds.length ? (
                <button
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white transition hover:bg-white/10"
                  onClick={() => setSelectedSessionIds([])}
                  type="button"
                >
                  Clear selection
                </button>
              ) : null}
            </div>
            <div className="mt-4 max-h-52 space-y-2 overflow-y-auto">
              {props.sessionOptions.map((session) => (
                <label
                  key={session.id}
                  className="flex items-start gap-3 rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm text-slate-200"
                >
                  <input
                    checked={selectedSessionIds.includes(session.id)}
                    onChange={() => toggleSession(session.id)}
                    type="checkbox"
                  />
                  <span>
                    <span className="block text-white">{session.title ?? "Untitled session"}</span>
                    <span className="mt-1 block text-xs text-slate-500">
                      {new Date(session.startedAt).toLocaleString()}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </div>
        ) : null}

        {job ? (
          <div className="mt-6 rounded-[1.5rem] border border-cyan-400/20 bg-cyan-400/10 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-white">
                {job.status.toUpperCase()}
              </span>
              <span className="text-sm text-cyan-50">Job ID: {job.job_id}</span>
            </div>
            <p className="mt-3 text-sm text-cyan-50/90">
              {job.status === "completed"
                ? "The export finished successfully and is ready to download."
                : job.status === "failed"
                  ? job.error_message || "The export job failed."
                  : "The export is being generated in the background. You can keep working while it runs."}
            </p>
            {job.row_count !== null ? (
              <p className="mt-2 text-xs text-cyan-100/80">Rows included: {job.row_count}</p>
            ) : null}
            {job.status === "completed" ? (
              <button
                className="mt-4 rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-60"
                disabled={isDownloading}
                onClick={() => void handleDownload()}
                type="button"
              >
                {isDownloading ? "Preparing download..." : "Download export"}
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button
            className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/10"
            onClick={props.onClose}
            type="button"
          >
            Cancel
          </button>
          <button
            className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-4 py-2.5 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isSubmitting || Boolean(job && ["pending", "processing"].includes(job.status))}
            onClick={() => void handleSubmit()}
            type="button"
          >
            {isSubmitting ? "Queueing export..." : "Start export"}
          </button>
        </div>
      </div>
    </div>
  );
}
