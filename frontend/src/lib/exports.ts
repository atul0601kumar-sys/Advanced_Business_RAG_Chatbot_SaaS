"use client";

import { apiFetch, buildApiHeaders } from "@/lib/auth";

export type ExportType = "chat" | "lead" | "analytics" | "faq";
export type ExportFormat = "csv" | "json" | "pdf";
export type ExportStatus = "pending" | "processing" | "completed" | "failed";

export type ExportJob = {
  job_id: string;
  workspace_id: string;
  type: ExportType;
  format: ExportFormat;
  status: ExportStatus;
  file_url: string | null;
  file_name: string | null;
  content_type: string | null;
  row_count: number | null;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
};

export type ExportFilters = {
  dateFrom?: string;
  dateTo?: string;
  source?: string;
  status?: string;
  priority?: string;
  category?: string;
  sessionIds?: string[];
  userId?: string;
  documentId?: string;
};

async function postExport<T>(path: string, payload: unknown): Promise<T> {
  const response = await apiFetch(path, {
    method: "POST",
    headers: buildApiHeaders({ "Content-Type": "application/json" }, "POST"),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: "Export request failed." }));
    throw new Error(data.detail ?? "Export request failed.");
  }
  return response.json() as Promise<T>;
}

export async function requestChatExportJob(payload: {
  workspaceId: string;
  format: ExportFormat;
  dateFrom?: string;
  dateTo?: string;
  source?: string;
  sessionIds?: string[];
  userId?: string;
}): Promise<ExportJob> {
  return postExport("/api/v1/export/chat", {
    workspace_id: payload.workspaceId,
    format: payload.format,
    date_from: payload.dateFrom || null,
    date_to: payload.dateTo || null,
    source: payload.source || null,
    session_ids: payload.sessionIds ?? [],
    user_id: payload.userId || null,
  });
}

export async function requestLeadExportJob(payload: {
  workspaceId: string;
  format: ExportFormat;
  dateFrom?: string;
  dateTo?: string;
  source?: string;
  status?: string;
  priority?: string;
}): Promise<ExportJob> {
  return postExport("/api/v1/export/leads", {
    workspace_id: payload.workspaceId,
    format: payload.format,
    date_from: payload.dateFrom || null,
    date_to: payload.dateTo || null,
    source: payload.source || null,
    status: payload.status || null,
    priority: payload.priority || null,
  });
}

export async function requestAnalyticsExportJob(payload: {
  workspaceId: string;
  format: ExportFormat;
  dateFrom?: string;
  dateTo?: string;
  source?: string;
  userId?: string;
  documentId?: string;
}): Promise<ExportJob> {
  return postExport("/api/v1/export/analytics", {
    workspace_id: payload.workspaceId,
    format: payload.format,
    date_from: payload.dateFrom || null,
    date_to: payload.dateTo || null,
    source: payload.source || null,
    user_id: payload.userId || null,
    document_id: payload.documentId || null,
  });
}

export async function requestFaqExportJob(payload: {
  workspaceId: string;
  format: ExportFormat;
  dateFrom?: string;
  dateTo?: string;
  source?: string;
  status?: string;
  category?: string;
}): Promise<ExportJob> {
  return postExport("/api/v1/export/faq", {
    workspace_id: payload.workspaceId,
    format: payload.format,
    date_from: payload.dateFrom || null,
    date_to: payload.dateTo || null,
    source: payload.source || null,
    status: payload.status || "approved",
    category: payload.category || null,
  });
}

export async function fetchExportJobStatus(jobId: string): Promise<ExportJob> {
  const response = await apiFetch(`/api/v1/export/status/${jobId}`, { method: "GET" });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: "Could not load export status." }));
    throw new Error(data.detail ?? "Could not load export status.");
  }
  return response.json() as Promise<ExportJob>;
}

export async function downloadExportJob(jobId: string, fallbackName: string): Promise<void> {
  const response = await apiFetch(`/api/v1/export/download/${jobId}`, { method: "GET" });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: "Download failed." }));
    throw new Error(data.detail ?? "Download failed.");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fallbackName;
  anchor.click();
  URL.revokeObjectURL(url);
}
