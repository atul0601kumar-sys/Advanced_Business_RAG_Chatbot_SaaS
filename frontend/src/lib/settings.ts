"use client";

import { apiRequest } from "@/lib/auth";

export type ChatbotIdentitySettings = {
  bot_name: string;
  bot_avatar: string | null;
  brand_color_primary: string;
  brand_color_secondary: string;
  logo: string | null;
  tagline: string | null;
  welcome_message: string;
};

export type ChatBehaviorSettings = {
  tone: "professional" | "friendly" | "concise" | "detailed";
  response_style: "paragraph" | "bullet_points" | "mixed";
  max_response_length: number;
  markdown_enabled: boolean;
  citations_enabled: boolean;
  confidence_score_enabled: boolean;
};

export type PromptCustomizationSettings = {
  custom_system_prompt: string | null;
  company_instructions: string | null;
  business_rules: string | null;
};

export type LeadCaptureCustomizationSettings = {
  enabled: boolean;
  force_before_chat: boolean;
  trigger_on_first_message: boolean;
  trigger_on_low_confidence: boolean;
  trigger_after_n_messages: number;
  required_fields: string[];
  custom_form_message: string | null;
  auto_response_message: string | null;
};

export type HumanHandoffSettings = {
  enabled: boolean;
  custom_message: string | null;
  enable_scheduling: boolean;
  escalate_on_low_confidence: boolean;
  escalate_on_repeated_failures: boolean;
};

export type VoiceSettings = {
  voice_input_enabled: boolean;
  voice_output_enabled: boolean;
  voice_style: string | null;
  transcript_preview_enabled: boolean;
  auto_read_assistant_responses: boolean;
};

export type WidgetCustomizationSettings = {
  position: "left" | "right";
  size: "compact" | "comfortable" | "expanded";
  theme: "light" | "dark" | "auto";
  welcome_popup_message: string | null;
  launcher_icon: string | null;
  show_branding: boolean;
  delay_before_appearance_seconds: number;
  allowed_origins: string[];
};

export type AccessControlSettings = {
  restrict_to_logged_in_users: boolean;
  chatbot_mode: "public" | "private";
  allow_guest_access: boolean;
  rate_limit_per_user_per_minute: number;
};

export type KnowledgeBaseSettings = {
  disabled_document_ids: string[];
  disabled_urls: string[];
  prioritized_document_ids: string[];
  prioritized_urls: string[];
  chunk_relevance_threshold: number;
};

export type AnalyticsPreferencesSettings = {
  tracking_enabled: boolean;
  feedback_collection_enabled: boolean;
  anonymize_user_data: boolean;
};

export type NotificationTriggerRule = {
  enabled: boolean;
  channels: string[];
  email_recipients: string[];
  webhook_urls: string[];
};

export type NotificationTemplateOverride = {
  subject: string | null;
  text_body: string | null;
  html_body: string | null;
};

export type NotificationChannelSettings = {
  enabled: boolean;
  notification_types: string[];
  email_recipients: string[];
  webhook_endpoints: string[];
  retry_attempts: number;
  triggers: Record<string, NotificationTriggerRule>;
  template_overrides: Record<string, NotificationTemplateOverride>;
};

export type ChatbotSettingsResponse = {
  workspace_id: string;
  identity: ChatbotIdentitySettings;
  behavior: ChatBehaviorSettings;
  prompt: PromptCustomizationSettings;
  lead_capture: LeadCaptureCustomizationSettings;
  handoff: HumanHandoffSettings;
  voice: VoiceSettings;
  widget: WidgetCustomizationSettings;
  access_control: AccessControlSettings;
  knowledge_base: KnowledgeBaseSettings;
  analytics: AnalyticsPreferencesSettings;
  notifications: NotificationChannelSettings;
  updated_at: string;
};

export type WidgetEmbedMetadata = {
  auth_token: string;
  auth_expires_at: string;
  api_base_url: string;
  script_url: string;
  version: string;
  allowed_origins: string[];
};
export type PublicChatbotSettingsResponse = Omit<
  ChatbotSettingsResponse,
  "prompt" | "knowledge_base" | "notifications" | "updated_at"
> & {
  embed: WidgetEmbedMetadata;
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

export type DocumentSummary = {
  id: string;
  title: string;
  mime_type?: string | null;
  file_size?: number | null;
  ingestion_status?: "pending" | "processing" | "indexed" | "failed";
  metadata_json?: Record<string, unknown> | null;
  summary?: string | null;
  chunk_count: number;
  created_at?: string;
  updated_at?: string;
};

export type WebsiteSourceSummary = {
  id: string;
  document_id: string | null;
  url: string;
  title: string | null;
  domain: string | null;
};

export async function fetchWorkspaceList(): Promise<WorkspaceSummary[]> {
  return apiRequest<WorkspaceSummary[]>("/api/v1/workspaces");
}

export async function fetchChatbotSettings(workspaceId: string): Promise<ChatbotSettingsResponse> {
  return apiRequest<ChatbotSettingsResponse>(`/api/v1/settings?workspace_id=${encodeURIComponent(workspaceId)}`);
}

export async function updateChatbotSettings(payload: ChatbotSettingsResponse): Promise<ChatbotSettingsResponse> {
  return apiRequest<ChatbotSettingsResponse>("/api/v1/settings/update", {
    method: "PUT",
    json: payload,
  });
}

export async function resetChatbotSettings(workspaceId: string): Promise<ChatbotSettingsResponse> {
  return apiRequest<ChatbotSettingsResponse>(`/api/v1/settings/reset-default?workspace_id=${encodeURIComponent(workspaceId)}`, {
    method: "POST",
  });
}

export async function fetchPublicChatbotSettings(workspaceId: string): Promise<PublicChatbotSettingsResponse> {
  return apiRequest<PublicChatbotSettingsResponse>(`/api/v1/settings/public?workspace_id=${encodeURIComponent(workspaceId)}`);
}

export async function fetchWorkspaceDocuments(workspaceId: string): Promise<DocumentSummary[]> {
  return apiRequest<DocumentSummary[]>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/documents`);
}

export async function fetchWorkspaceWebsiteSources(workspaceId: string): Promise<WebsiteSourceSummary[]> {
  return apiRequest<WebsiteSourceSummary[]>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/website-sources`);
}
