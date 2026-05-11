"use client";

import { apiRequest } from "@/lib/auth";
import type { WorkspaceSummary } from "@/lib/settings";

export type IntegrationCatalogItem = {
  integration_type:
    | "google_sheets"
    | "zapier"
    | "make"
    | "hubspot"
    | "salesforce"
    | "slack"
    | "discord"
    | "whatsapp"
    | "telegram"
    | "webhook";
  label: string;
  description: string;
  implemented: boolean;
  supports_events: string[];
  required_config_fields: string[];
  secret_fields: string[];
};

export type IntegrationConnectionSummary = {
  id: string;
  workspace_id: string;
  integration_type: IntegrationCatalogItem["integration_type"];
  display_name: string;
  status: string;
  config: Record<string, unknown>;
  event_types: string[];
  last_error: string | null;
  last_tested_at: string | null;
  created_at: string;
  updated_at: string;
};

export type IntegrationDeliverySummary = {
  id: string;
  integration_id: string;
  event_type: string;
  status: string;
  retry_count: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
};

export type IntegrationListResponse = {
  available_integrations: IntegrationCatalogItem[];
  connections: IntegrationConnectionSummary[];
  recent_deliveries: IntegrationDeliverySummary[];
};

export type IntegrationConnectPayload = {
  workspace_id: string;
  integration_type: IntegrationCatalogItem["integration_type"];
  display_name: string;
  credentials: Record<string, string>;
  config: Record<string, unknown>;
};

export type IntegrationUpdatePayload = {
  workspace_id: string;
  integration_id: string;
  display_name?: string;
  credentials?: Record<string, string>;
  config?: Record<string, unknown>;
  status?: string;
};

export type IntegrationDisconnectPayload = {
  workspace_id: string;
  integration_id: string;
};

export type IntegrationTestPayload = {
  workspace_id: string;
  integration_id: string;
  event_type: string;
};

export async function fetchIntegrationWorkspaceList(): Promise<WorkspaceSummary[]> {
  return apiRequest<WorkspaceSummary[]>("/api/v1/workspaces");
}

export async function fetchIntegrations(workspaceId: string): Promise<IntegrationListResponse> {
  return apiRequest<IntegrationListResponse>(`/api/v1/integrations/list?workspace_id=${encodeURIComponent(workspaceId)}`);
}

export async function connectIntegration(payload: IntegrationConnectPayload) {
  return apiRequest<{ message: string; connection: IntegrationConnectionSummary }>("/api/v1/integrations/connect", {
    method: "POST",
    json: payload,
  });
}

export async function updateIntegration(payload: IntegrationUpdatePayload) {
  return apiRequest<{ message: string; connection: IntegrationConnectionSummary }>("/api/v1/integrations/update", {
    method: "PUT",
    json: payload,
  });
}

export async function disconnectIntegration(payload: IntegrationDisconnectPayload) {
  return apiRequest<{ message: string; connection: IntegrationConnectionSummary | null }>("/api/v1/integrations/disconnect", {
    method: "DELETE",
    json: payload,
  });
}

export async function testIntegration(payload: IntegrationTestPayload) {
  return apiRequest<{ message: string; status: string; connection: IntegrationConnectionSummary }>("/api/v1/integrations/test", {
    method: "POST",
    json: payload,
  });
}
