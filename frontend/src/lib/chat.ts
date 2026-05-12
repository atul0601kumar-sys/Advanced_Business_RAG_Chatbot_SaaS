import { apiBaseUrl, apiFetch, buildApiHeaders, fetchCurrentUser as fetchAuthenticatedUser } from "@/lib/auth";

export type WorkspaceMembership = {
  workspace_id: string;
  workspace_name: string;
  workspace_slug: string;
  role: string;
};

export type CurrentUser = {
  id: string;
  full_name: string;
  email: string;
  memberships: WorkspaceMembership[];
};

export type ChatMode = "concise" | "detailed" | "bullet";
export type ConfidenceLabel = "High" | "Medium" | "Low";
export type FeedbackValue = "up" | "down";
export type ChatRetrievalFilters = {
  documentIds?: string[];
};

export type Citation = {
  document_id?: string | null;
  file_name: string | null;
  page_number: number | null;
  url: string | null;
  chunk_preview: string;
};

export type ChatMessageRecord = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[];
  token_usage: {
    confidence?: ConfidenceLabel;
    retrieved_chunks?: number;
    processing_time?: number;
    stopped?: boolean;
    generation_id?: string;
    answer_strategy?: string;
    faq_id?: string | null;
  } | null;
  response_time_ms: number | null;
  created_at: string;
  updated_at: string;
};

export type ChatSessionSummary = {
  id: string;
  workspace_id: string;
  user_id: string | null;
  title: string | null;
  status: string;
  channel: string;
  started_at: string;
  last_message_at: string | null;
  session_summary: string | null;
  needs_human_review: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type LeadCapturePrompt = {
  should_prompt: boolean;
  trigger: string | null;
  message: string | null;
  schedule_call_enabled: boolean;
  high_intent: boolean;
  scheduling_intent_detected: boolean;
};

export type ChatHistoryResponse = {
  session: ChatSessionSummary;
  messages: ChatMessageRecord[];
};

export type ChatAnswerResponse = {
  answer: string;
  citations: Citation[];
  confidence: ConfidenceLabel;
  metadata: {
    retrieved_chunks: number;
    processing_time: number;
    stopped: boolean;
    session_id?: string | null;
    message_id?: string | null;
    generation_id?: string | null;
    lead_capture?: LeadCapturePrompt | null;
    answer_strategy?: string;
    faq_id?: string | null;
  };
};

export type LeadStatus = "new" | "contacted" | "qualified" | "converted" | "closed";
export type LeadPriority = "low" | "medium" | "high";

export type LeadSummary = {
  id: string;
  workspace_id: string;
  chat_session_id: string | null;
  name: string | null;
  email: string | null;
  phone: string | null;
  company: string | null;
  use_case: string | null;
  message: string | null;
  source: string;
  status: LeadStatus;
  priority: LeadPriority;
  tag: "sales" | "support" | "general";
  high_intent: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  metadata_json: Record<string, unknown> | null;
};

export type LeadDetailResponse = {
  lead: LeadSummary;
  conversation: Array<{ id: string; role: string; content: string; created_at: string }>;
  bookings: Array<{
    id: string;
    meeting_type_title: string;
    start_time_utc: string;
    end_time_utc: string;
    status: string;
    meeting_link: string | null;
    assigned_user_id: string | null;
  }>;
};

export type LeadCaptureSettings = {
  workspace_id: string;
  lead_capture_enabled: boolean;
  lead_capture_on_first_message: boolean;
  lead_capture_after_message_count: number;
  lead_capture_on_low_confidence: boolean;
  force_lead_before_chat: boolean;
  required_fields: string[];
  schedule_call_enabled: boolean;
  lead_notifications_enabled: boolean;
  admin_notification_email: string | null;
  notification_webhook_url: string | null;
  auto_response_message: string | null;
};

type StartEventPayload = {
  session_id: string;
  generation_id: string;
  message_id: string;
};

type StreamHandlers = {
  onStart?: (payload: StartEventPayload) => void;
  onToken?: (delta: string) => void;
  onComplete?: (payload: ChatAnswerResponse) => void;
};

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = buildApiHeaders(init.headers, init.method ?? "GET");
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await apiFetch(path, {
      ...init,
      headers,
    });
  } catch {
    throw new Error(
      `Could not reach the backend at ${apiBaseUrl}. Make sure the FastAPI server is running.`,
    );
  }

  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "The request could not be completed." }));
    throw new Error(data.detail ?? "The request could not be completed.");
  }

  return response.json() as Promise<T>;
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  return fetchAuthenticatedUser();
}

export async function listChatSessions(workspaceId: string): Promise<ChatSessionSummary[]> {
  return requestJson<ChatSessionSummary[]>(
    `/api/v1/chat/sessions?workspace_id=${encodeURIComponent(workspaceId)}`,
  );
}

export async function createChatSession(workspaceId: string, title?: string): Promise<ChatSessionSummary> {
  return requestJson<ChatSessionSummary>("/api/v1/chat/session", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: workspaceId,
      title: title ?? null,
      channel: "web",
    }),
    headers: { "Content-Type": "application/json" },
  });
}

export async function fetchChatHistory(sessionId: string): Promise<ChatHistoryResponse> {
  return requestJson<ChatHistoryResponse>(`/api/v1/chat/history/${sessionId}`);
}

export async function regenerateChatResponse(
  sessionId: string,
  mode: ChatMode,
  filters?: ChatRetrievalFilters,
): Promise<ChatAnswerResponse> {
  return requestJson<ChatAnswerResponse>("/api/v1/chat/regenerate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      mode,
      filters: serializeChatFilters(filters),
    }),
  });
}

export async function submitChatFeedback(
  sessionId: string,
  messageId: string,
  value: FeedbackValue,
): Promise<void> {
  await requestJson<{ message: string; feedback_id: string }>("/api/v1/chat/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message_id: messageId,
      value,
      category: value === "up" ? "useful" : "not_grounded",
    }),
  });
}

export async function stopChatGeneration(
  sessionId: string,
  generationId: string | null,
): Promise<void> {
  await requestJson<{ message: string }>("/api/v1/chat/stop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      generation_id: generationId,
    }),
  });
}

export async function captureLead(payload: {
  workspaceId: string;
  chatSessionId: string | null;
  name: string;
  email: string;
  phone?: string;
  company?: string;
  useCase?: string;
  message?: string;
  scheduleCallRequested?: boolean;
}): Promise<{ message: string; lead: LeadSummary }> {
  return requestJson("/api/v1/leads/capture", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      workspace_id: payload.workspaceId,
      chat_session_id: payload.chatSessionId,
      name: payload.name,
      email: payload.email,
      phone: payload.phone || null,
      company: payload.company || null,
      use_case: payload.useCase || null,
      message: payload.message || null,
      source: "chatbot",
      schedule_call_requested: payload.scheduleCallRequested ?? false,
    }),
  });
}

export async function requestHumanHandoff(payload: {
  workspaceId: string;
  sessionId: string;
  reason?: string;
  message?: string;
}): Promise<{ message: string; needs_human_review: boolean; lead_prompt: LeadCapturePrompt }> {
  return requestJson("/api/v1/chat/handoff", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      workspace_id: payload.workspaceId,
      session_id: payload.sessionId,
      reason: payload.reason || null,
      message: payload.message || null,
    }),
  });
}

export async function listLeads(params: {
  workspaceId: string;
  status?: string;
  priority?: string;
  search?: string;
  dateFrom?: string;
  dateTo?: string;
}): Promise<{ items: LeadSummary[]; total: number }> {
  const searchParams = new URLSearchParams({ workspace_id: params.workspaceId });
  if (params.status) searchParams.set("status", params.status);
  if (params.priority) searchParams.set("priority", params.priority);
  if (params.search) searchParams.set("search", params.search);
  if (params.dateFrom) searchParams.set("date_from", params.dateFrom);
  if (params.dateTo) searchParams.set("date_to", params.dateTo);
  return requestJson(`/api/v1/leads?${searchParams.toString()}`);
}

export async function fetchLeadDetail(workspaceId: string, leadId: string): Promise<LeadDetailResponse> {
  return requestJson(`/api/v1/leads/${leadId}?workspace_id=${encodeURIComponent(workspaceId)}`);
}

export async function updateLead(
  workspaceId: string,
  leadId: string,
  payload: { status?: LeadStatus; priority?: LeadPriority; notes?: string },
): Promise<LeadSummary> {
  return requestJson(`/api/v1/leads/${leadId}?workspace_id=${encodeURIComponent(workspaceId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function exportLeadsCsv(payload: {
  workspaceId: string;
  status?: string;
  priority?: string;
  search?: string;
  dateFrom?: string;
  dateTo?: string;
}): Promise<Blob> {
  const response = await apiFetch("/api/v1/leads/export", {
    method: "POST",
    headers: buildApiHeaders({ "Content-Type": "application/json" }, "POST"),
    body: JSON.stringify({
      workspace_id: payload.workspaceId,
      status: payload.status || null,
      priority: payload.priority || null,
      search: payload.search || null,
      date_from: payload.dateFrom || null,
      date_to: payload.dateTo || null,
    }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: "Export failed." }));
    throw new Error(data.detail ?? "Export failed.");
  }
  return response.blob();
}

export async function fetchLeadCaptureSettings(workspaceId: string): Promise<LeadCaptureSettings> {
  return requestJson(`/api/v1/leads/settings?workspace_id=${encodeURIComponent(workspaceId)}`);
}

export async function updateLeadCaptureSettings(payload: LeadCaptureSettings): Promise<LeadCaptureSettings> {
  return requestJson("/api/v1/leads/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function streamChatMessage(
  payload: {
    sessionId: string;
    message: string;
    mode: ChatMode;
    filters?: ChatRetrievalFilters;
  },
  handlers: StreamHandlers,
): Promise<void> {
  let response: Response;
  try {
    response = await apiFetch("/api/v1/chat/message", {
      method: "POST",
      headers: buildApiHeaders({ "Content-Type": "application/json" }, "POST"),
      body: JSON.stringify({
        session_id: payload.sessionId,
        message: payload.message,
        mode: payload.mode,
        filters: serializeChatFilters(payload.filters),
      }),
    });
  } catch {
    throw new Error(
      `Could not reach the backend at ${apiBaseUrl}. Make sure the FastAPI server is running.`,
    );
  }

  if (!response.ok || !response.body) {
    const data = await response
      .json()
      .catch(() => ({ detail: "Streaming request failed." }));
    throw new Error(data.detail ?? "Streaming request failed.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const parsed = parseSseFrame(frame);
      if (!parsed) {
        continue;
      }
      if (parsed.event === "start") {
        handlers.onStart?.(parsed.data as StartEventPayload);
      } else if (parsed.event === "token") {
        handlers.onToken?.((parsed.data as { delta: string }).delta);
      } else if (parsed.event === "complete") {
        handlers.onComplete?.(parsed.data as ChatAnswerResponse);
      }
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseFrame(buffer);
    if (parsed?.event === "complete") {
      handlers.onComplete?.(parsed.data as ChatAnswerResponse);
    }
  }
}

function serializeChatFilters(filters?: ChatRetrievalFilters): { document_ids: string[] } | undefined {
  const documentIds = filters?.documentIds?.filter(Boolean) ?? [];
  if (!documentIds.length) {
    return undefined;
  }
  return { document_ids: documentIds };
}

function parseSseFrame(frame: string): { event: string; data: unknown } | null {
  const lines = frame
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLine = lines.find((line) => line.startsWith("data:"));
  if (!eventLine || !dataLine) {
    return null;
  }

  const event = eventLine.replace("event:", "").trim();
  const rawData = dataLine.replace("data:", "").trim();
  return { event, data: JSON.parse(rawData) };
}

export function downloadResponseAsMarkdown(title: string, content: string): void {
  const safeTitle = title.trim().replace(/[^a-z0-9]+/gi, "-").replace(/^-+|-+$/g, "") || "chat-response";
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${safeTitle}.md`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function estimateTokens(text: string): number {
  return Math.max(1, Math.ceil(text.length / 4));
}
