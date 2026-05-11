"use client";

import { apiFetch, apiRequest } from "@/lib/auth";

export type AnalyticsFilters = {
  workspace_id: string;
  date_from: string | null;
  date_to: string | null;
  user_id: string | null;
  document_id: string | null;
  source: string | null;
};

export type MetricCard = {
  label: string;
  value: number;
  display_value: string;
  hint: string | null;
};

export type TimeSeriesPoint = {
  bucket: string;
  value: number;
  label: string | null;
  secondary_value: number | null;
};

export type BreakdownItem = {
  label: string;
  value: number;
  hint: string | null;
  extra: Record<string, unknown> | null;
};

export type InsightItem = {
  title: string;
  description: string;
  severity: "info" | "warning" | "critical";
};

export type QueryInsightItem = {
  query: string;
  count: number;
  share: number | null;
  last_seen_at: string | null;
};

export type KeywordInsightItem = {
  keyword: string;
  count: number;
};

export type TopicClusterItem = {
  topic: string;
  count: number;
  sample_queries: string[];
};

export type DislikedResponseItem = {
  message_id: string | null;
  session_id: string | null;
  response_excerpt: string;
  feedback_count: number;
  confidence: string | null;
  latest_feedback_at: string | null;
};

export type OverviewMetrics = {
  total_chats: number;
  total_users: number;
  total_messages: number;
  total_documents: number;
  total_website_sources: number;
  total_leads: number;
  conversion_rate: number;
  average_response_time_ms: number;
  average_confidence_score: number;
};

export type AnalyticsOverviewResponse = {
  generated_at: string;
  filters: AnalyticsFilters;
  metrics: OverviewMetrics;
  metric_cards: MetricCard[];
  daily_chat_volume: TimeSeriesPoint[];
  daily_lead_volume: TimeSeriesPoint[];
  source_distribution: BreakdownItem[];
  confidence_distribution: BreakdownItem[];
  top_knowledge_sources: BreakdownItem[];
  alerts: InsightItem[];
  insights: InsightItem[];
};

export type ChatAnalyticsResponse = {
  generated_at: string;
  filters: AnalyticsFilters;
  daily_chat_volume: TimeSeriesPoint[];
  messages_per_session: number;
  average_session_duration_minutes: number;
  peak_usage_times: BreakdownItem[];
  active_users_over_time: TimeSeriesPoint[];
  message_mix: BreakdownItem[];
  session_length_distribution: BreakdownItem[];
};

export type LeadAnalyticsResponse = {
  generated_at: string;
  filters: AnalyticsFilters;
  conversion_rate: number;
  leads_per_day: TimeSeriesPoint[];
  leads_per_week: TimeSeriesPoint[];
  leads_per_month: TimeSeriesPoint[];
  lead_sources: BreakdownItem[];
  lead_priority_distribution: BreakdownItem[];
  funnel: BreakdownItem[];
  insights: InsightItem[];
};

export type PerformanceAnalyticsResponse = {
  generated_at: string;
  filters: AnalyticsFilters;
  confidence_distribution: BreakdownItem[];
  unanswered_queries: number;
  failed_queries: QueryInsightItem[];
  response_quality: BreakdownItem[];
  retrieval_success_rate: number;
  average_response_time_ms: number;
  average_confidence_score: number;
  feedback_confidence_correlation: BreakdownItem[];
  alerts: InsightItem[];
};

export type QueryAnalyticsResponse = {
  generated_at: string;
  filters: AnalyticsFilters;
  most_asked_questions: QueryInsightItem[];
  search_trends: TimeSeriesPoint[];
  repeated_queries: QueryInsightItem[];
  keywords: KeywordInsightItem[];
  topics: TopicClusterItem[];
  most_used_documents: BreakdownItem[];
  most_used_urls: BreakdownItem[];
  chunk_usage_frequency: BreakdownItem[];
  top_knowledge_sources: BreakdownItem[];
  insights: InsightItem[];
};

export type FeedbackAnalyticsResponse = {
  generated_at: string;
  filters: AnalyticsFilters;
  positive_vs_negative: BreakdownItem[];
  feedback_trends: TimeSeriesPoint[];
  most_disliked_responses: DislikedResponseItem[];
  confidence_correlation: BreakdownItem[];
  response_quality_over_time: TimeSeriesPoint[];
};

export type WorkspaceSummary = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  status: string;
  role: string;
  created_at: string;
};

export type WorkspaceMemberSummary = {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  role: string;
};

export type DocumentSummary = {
  id: string;
  title: string;
};

export type AnalyticsView =
  | "overview"
  | "chats"
  | "leads"
  | "performance"
  | "queries";

export async function fetchWorkspaces(): Promise<WorkspaceSummary[]> {
  return apiRequest<WorkspaceSummary[]>("/api/v1/workspaces");
}

export async function fetchWorkspaceMembers(workspaceId: string): Promise<WorkspaceMemberSummary[]> {
  return apiRequest<WorkspaceMemberSummary[]>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members`);
}

export async function fetchWorkspaceDocuments(workspaceId: string): Promise<DocumentSummary[]> {
  return apiRequest<DocumentSummary[]>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/documents`);
}

function buildQuery(params: {
  workspaceId: string;
  dateFrom?: string;
  dateTo?: string;
  userId?: string;
  documentId?: string;
  source?: string;
}) {
  const query = new URLSearchParams({ workspace_id: params.workspaceId });
  if (params.dateFrom) query.set("date_from", params.dateFrom);
  if (params.dateTo) query.set("date_to", params.dateTo);
  if (params.userId) query.set("user_id", params.userId);
  if (params.documentId) query.set("document_id", params.documentId);
  if (params.source) query.set("source", params.source);
  return query.toString();
}

export async function fetchAnalyticsOverview(params: {
  workspaceId: string;
  dateFrom?: string;
  dateTo?: string;
  userId?: string;
  documentId?: string;
  source?: string;
}): Promise<AnalyticsOverviewResponse> {
  return apiRequest<AnalyticsOverviewResponse>(`/api/v1/analytics/overview?${buildQuery(params)}`);
}

export async function fetchChatAnalytics(params: {
  workspaceId: string;
  dateFrom?: string;
  dateTo?: string;
  userId?: string;
  documentId?: string;
  source?: string;
}): Promise<ChatAnalyticsResponse> {
  return apiRequest<ChatAnalyticsResponse>(`/api/v1/analytics/chats?${buildQuery(params)}`);
}

export async function fetchLeadAnalytics(params: {
  workspaceId: string;
  dateFrom?: string;
  dateTo?: string;
  userId?: string;
  documentId?: string;
  source?: string;
}): Promise<LeadAnalyticsResponse> {
  return apiRequest<LeadAnalyticsResponse>(`/api/v1/analytics/leads?${buildQuery(params)}`);
}

export async function fetchPerformanceAnalytics(params: {
  workspaceId: string;
  dateFrom?: string;
  dateTo?: string;
  userId?: string;
  documentId?: string;
  source?: string;
}): Promise<PerformanceAnalyticsResponse> {
  return apiRequest<PerformanceAnalyticsResponse>(`/api/v1/analytics/performance?${buildQuery(params)}`);
}

export async function fetchQueryAnalytics(params: {
  workspaceId: string;
  dateFrom?: string;
  dateTo?: string;
  userId?: string;
  documentId?: string;
  source?: string;
}): Promise<QueryAnalyticsResponse> {
  return apiRequest<QueryAnalyticsResponse>(`/api/v1/analytics/queries?${buildQuery(params)}`);
}

export async function fetchFeedbackAnalytics(params: {
  workspaceId: string;
  dateFrom?: string;
  dateTo?: string;
  userId?: string;
  documentId?: string;
  source?: string;
}): Promise<FeedbackAnalyticsResponse> {
  return apiRequest<FeedbackAnalyticsResponse>(`/api/v1/analytics/feedback?${buildQuery(params)}`);
}

export async function exportAnalyticsCsv(
  view: AnalyticsView | "feedback",
  params: {
    workspaceId: string;
    dateFrom?: string;
    dateTo?: string;
    userId?: string;
    documentId?: string;
    source?: string;
  },
): Promise<Blob> {
  const response = await apiFetch(
    `/api/v1/analytics/${view}?${buildQuery(params)}&export=csv`,
    { method: "GET" },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: "Export failed." }));
    throw new Error(data.detail ?? "Export failed.");
  }
  return response.blob();
}
