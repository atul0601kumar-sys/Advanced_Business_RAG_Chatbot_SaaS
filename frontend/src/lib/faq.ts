"use client";

import { apiFetch, buildApiHeaders, apiRequest } from "@/lib/auth";

export type FAQStatus = "draft" | "approved" | "rejected";
export type FAQBulkAction = "approve" | "reject";
export type FAQExportFormat = "csv" | "json";

export type FAQCitation = {
  document_id?: string | null;
  file_name?: string | null;
  page_number?: number | null;
  url?: string | null;
  chunk_preview: string;
};

export type FAQSummary = {
  id: string;
  workspace_id: string;
  question: string;
  answer: string;
  category: string;
  source: string;
  status: FAQStatus;
  confidence_score: number;
  created_at: string;
  updated_at: string;
  source_type?: string | null;
  source_id?: string | null;
  citations: FAQCitation[];
};

export type FAQGenerationState = {
  status: string;
  message: string;
  started_at?: string | null;
  completed_at?: string | null;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  rejected_count: number;
};

export type FAQListResponse = {
  items: FAQSummary[];
  total: number;
  page: number;
  page_size: number;
  categories: string[];
  generation?: FAQGenerationState | null;
};

export type WorkspaceSummary = {
  id: string;
  name: string;
  role: string;
};

export async function fetchFaqWorkspaces(): Promise<WorkspaceSummary[]> {
  return apiRequest<WorkspaceSummary[]>("/api/v1/workspaces");
}

export async function listFaqs(params: {
  workspaceId: string;
  category?: string;
  status?: FAQStatus | "";
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<FAQListResponse> {
  const searchParams = new URLSearchParams({
    workspace_id: params.workspaceId,
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 10),
  });
  if (params.category) searchParams.set("category", params.category);
  if (params.status) searchParams.set("status", params.status);
  if (params.search) searchParams.set("search", params.search);
  return apiRequest<FAQListResponse>(`/api/v1/faq/list?${searchParams.toString()}`);
}

export async function generateFaqs(payload: {
  workspaceId: string;
  force?: boolean;
  maxFaqsPerSource?: number;
}): Promise<{ message: string; generation: FAQGenerationState }> {
  return apiRequest<{ message: string; generation: FAQGenerationState }>("/api/v1/faq/generate", {
    method: "POST",
    json: {
      workspace_id: payload.workspaceId,
      force: payload.force ?? false,
      max_faqs_per_source: payload.maxFaqsPerSource ?? 5,
    },
  });
}

export async function updateFaq(payload: {
  workspaceId: string;
  faqId: string;
  question: string;
  answer: string;
  category: string;
  status?: FAQStatus;
}): Promise<FAQSummary> {
  return apiRequest<FAQSummary>("/api/v1/faq/update", {
    method: "PUT",
    json: {
      workspace_id: payload.workspaceId,
      faq_id: payload.faqId,
      question: payload.question,
      answer: payload.answer,
      category: payload.category,
      status: payload.status,
    },
  });
}

export async function bulkReviewFaqs(payload: {
  workspaceId: string;
  faqIds: string[];
  action: FAQBulkAction;
}): Promise<{ message: string; updated_ids: string[] }> {
  return apiRequest<{ message: string; updated_ids: string[] }>("/api/v1/faq/approve", {
    method: "POST",
    json: {
      workspace_id: payload.workspaceId,
      faq_ids: payload.faqIds,
      action: payload.action,
    },
  });
}

export async function deleteFaqs(payload: {
  workspaceId: string;
  faqIds: string[];
}): Promise<{ message: string; updated_ids: string[] }> {
  const searchParams = new URLSearchParams({
    workspace_id: payload.workspaceId,
    faq_ids: payload.faqIds.join(","),
  });
  return apiRequest<{ message: string; updated_ids: string[] }>(`/api/v1/faq/delete?${searchParams.toString()}`, {
    method: "DELETE",
  });
}

export async function exportFaqs(payload: {
  workspaceId: string;
  format: FAQExportFormat;
  status?: FAQStatus;
}): Promise<Blob> {
  const response = await apiFetch("/api/v1/faq/export", {
    method: "POST",
    headers: buildApiHeaders({ "Content-Type": "application/json" }, "POST"),
    body: JSON.stringify({
      workspace_id: payload.workspaceId,
      format: payload.format,
      status: payload.status ?? "approved",
    }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: "Export failed." }));
    throw new Error(data.detail ?? "Export failed.");
  }
  return response.blob();
}
