"use client";

import { useEffect, useMemo, useState } from "react";

import { ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import { useToast } from "@/components/toast-provider";
import {
  connectIntegration,
  disconnectIntegration,
  fetchIntegrations,
  fetchIntegrationWorkspaceList,
  testIntegration,
  updateIntegration,
  type IntegrationCatalogItem,
  type IntegrationConnectionSummary,
  type IntegrationDeliverySummary,
  type IntegrationListResponse,
} from "@/lib/integrations";
import type { WorkspaceSummary } from "@/lib/settings";

type DraftState = {
  integrationType: IntegrationCatalogItem["integration_type"];
  displayName: string;
  eventTypes: string[];
  configFields: Record<string, string>;
  secretFields: Record<string, string>;
};

const defaultEventTypes = [
  "lead_created",
  "high_priority_lead",
  "chat_started",
  "message_sent",
  "feedback_submitted",
];

export function IntegrationsManager() {
  const { pushToast } = useToast();
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [payload, setPayload] = useState<IntegrationListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<DraftState>({
    integrationType: "slack",
    displayName: "",
    eventTypes: defaultEventTypes,
    configFields: {},
    secretFields: {},
  });

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      setIsLoading(true);
      try {
        const items = await fetchIntegrationWorkspaceList();
        if (!active) return;
        setWorkspaces(items);
        if (items.length) {
          setSelectedWorkspaceId((current) => current || items[0].id);
        }
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load workspaces.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) return;
    let active = true;
    async function loadIntegrations() {
      setIsLoading(true);
      try {
        const response = await fetchIntegrations(selectedWorkspaceId);
        if (!active) return;
        setPayload(response);
        const firstImplemented = response.available_integrations.find((item) => item.implemented) ?? response.available_integrations[0];
        if (firstImplemented) {
          setDraft((current) => ({
            ...current,
            integrationType: firstImplemented.integration_type,
            displayName: current.displayName || firstImplemented.label,
            eventTypes: firstImplemented.supports_events,
          }));
        }
        setError("");
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load integrations.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadIntegrations();
    return () => {
      active = false;
    };
  }, [selectedWorkspaceId]);

  const selectedDefinition = useMemo(() => {
    return payload?.available_integrations.find((item) => item.integration_type === draft.integrationType) ?? null;
  }, [draft.integrationType, payload?.available_integrations]);

  function updateDraftField(kind: "configFields" | "secretFields", key: string, value: string) {
    setDraft((current) => ({
      ...current,
      [kind]: {
        ...current[kind],
        [key]: value,
      },
    }));
  }

  async function reload() {
    if (!selectedWorkspaceId) return;
    const response = await fetchIntegrations(selectedWorkspaceId);
    setPayload(response);
  }

  async function handleConnect() {
    if (!selectedWorkspaceId || !selectedDefinition) return;
    setIsSaving(true);
    try {
      await connectIntegration({
        workspace_id: selectedWorkspaceId,
        integration_type: draft.integrationType,
        display_name: draft.displayName || selectedDefinition.label,
        credentials: draft.secretFields,
        config: {
          ...draft.configFields,
          event_types: draft.eventTypes,
        },
      });
      await reload();
      pushToast({
        title: "Integration connected",
        description: `${selectedDefinition.label} is now active for this workspace.`,
        tone: "success",
      });
      setDraft((current) => ({ ...current, secretFields: {} }));
    } catch (saveError) {
      pushToast({
        title: "Connection failed",
        description: saveError instanceof Error ? saveError.message : "Could not connect integration.",
        tone: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDisconnect(connection: IntegrationConnectionSummary) {
    setIsSaving(true);
    try {
      await disconnectIntegration({
        workspace_id: connection.workspace_id,
        integration_id: connection.id,
      });
      await reload();
      pushToast({
        title: "Integration disconnected",
        description: `${connection.display_name} was set to inactive.`,
        tone: "success",
      });
    } catch (disconnectError) {
      pushToast({
        title: "Disconnect failed",
        description: disconnectError instanceof Error ? disconnectError.message : "Could not disconnect integration.",
        tone: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggleStatus(connection: IntegrationConnectionSummary) {
    setIsSaving(true);
    try {
      await updateIntegration({
        workspace_id: connection.workspace_id,
        integration_id: connection.id,
        status: connection.status === "active" ? "inactive" : "active",
      });
      await reload();
      pushToast({
        title: "Integration updated",
        description: `${connection.display_name} status changed successfully.`,
        tone: "success",
      });
    } catch (updateError) {
      pushToast({
        title: "Status update failed",
        description: updateError instanceof Error ? updateError.message : "Could not update integration.",
        tone: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTest(connection: IntegrationConnectionSummary) {
    setIsSaving(true);
    try {
      await testIntegration({
        workspace_id: connection.workspace_id,
        integration_id: connection.id,
        event_type: connection.event_types[0] || "lead_created",
      });
      await reload();
      pushToast({
        title: "Integration test passed",
        description: `${connection.display_name} accepted a live test event.`,
        tone: "success",
      });
    } catch (testError) {
      pushToast({
        title: "Integration test failed",
        description: testError instanceof Error ? testError.message : "Could not test integration.",
        tone: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading && !payload) {
    return (
      <main className="space-y-6">
        <LoadingGrid rows={2} />
        <LoadingGrid rows={4} />
      </main>
    );
  }

  if (error && !payload) {
    return (
      <ErrorState
        actionLabel="Retry loading"
        description={error}
        onAction={() => window.location.reload()}
        title="Integrations dashboard could not be loaded"
      />
    );
  }

  if (!payload) {
    return null;
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(34,197,94,0.14),transparent_35%),linear-gradient(145deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.35em] text-emerald-200/70">Integration framework</p>
            <h2 className="mt-3 text-4xl font-semibold text-white">Workspace integrations</h2>
            <p className="mt-3 text-slate-300">
              Connect external systems through a pluggable, event-driven delivery layer for leads, notifications, chat sync, and workflow automation.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <select
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none"
              value={selectedWorkspaceId}
              onChange={(event) => setSelectedWorkspaceId(event.target.value)}
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name} - {workspace.role}
                </option>
              ))}
            </select>
            <button
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-200"
              onClick={() => void reload()}
              type="button"
            >
              Refresh
            </button>
          </div>
        </div>
      </section>

      {error ? (
        <section className="rounded-3xl border border-amber-400/20 bg-amber-400/10 px-5 py-4 text-sm text-amber-100">
          {error}
        </section>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1.05fr_1.35fr]">
        <section className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="text-2xl font-semibold text-white">Connect a service</h3>
              <p className="mt-2 text-sm text-slate-400">
                Working examples are ready for Slack, Webhook, and Google Sheets. Other providers are scaffolded for future plugins.
              </p>
            </div>
            <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-100">
              Pluggable
            </span>
          </div>

          <div className="mt-6 grid gap-4">
            <label className="grid gap-2 text-sm text-slate-300">
              <span>Integration type</span>
              <select
                className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-white outline-none"
                value={draft.integrationType}
                onChange={(event) => {
                  const nextType = event.target.value as DraftState["integrationType"];
                  const definition = payload.available_integrations.find((item) => item.integration_type === nextType);
                  setDraft({
                    integrationType: nextType,
                    displayName: definition?.label ?? nextType,
                    eventTypes: definition?.supports_events ?? defaultEventTypes,
                    configFields: {},
                    secretFields: {},
                  });
                }}
              >
                {payload.available_integrations.map((item) => (
                  <option key={item.integration_type} value={item.integration_type}>
                    {item.label} {item.implemented ? "" : "(Scaffolded)"}
                  </option>
                ))}
              </select>
            </label>

            <label className="grid gap-2 text-sm text-slate-300">
              <span>Display name</span>
              <input
                className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-white outline-none"
                value={draft.displayName}
                onChange={(event) => setDraft((current) => ({ ...current, displayName: event.target.value }))}
              />
            </label>

            {selectedDefinition ? (
              <div className="rounded-3xl border border-white/10 bg-slate-950/40 p-4 text-sm text-slate-300">
                <p className="font-medium text-white">{selectedDefinition.label}</p>
                <p className="mt-2 text-slate-400">{selectedDefinition.description}</p>
                <p className="mt-3 text-xs uppercase tracking-[0.25em] text-slate-500">
                  Supported events: {selectedDefinition.supports_events.join(", ")}
                </p>
              </div>
            ) : null}

            {selectedDefinition?.required_config_fields.map((field) => (
              <label key={field} className="grid gap-2 text-sm text-slate-300">
                <span>{field}</span>
                <input
                  className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-white outline-none"
                  value={draft.configFields[field] ?? ""}
                  onChange={(event) => updateDraftField("configFields", field, event.target.value)}
                />
              </label>
            ))}

            {selectedDefinition?.secret_fields.map((field) => (
              <label key={field} className="grid gap-2 text-sm text-slate-300">
                <span>{field}</span>
                <input
                  className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-white outline-none"
                  type="password"
                  value={draft.secretFields[field] ?? ""}
                  onChange={(event) => updateDraftField("secretFields", field, event.target.value)}
                />
              </label>
            ))}

            <div className="grid gap-2 text-sm text-slate-300">
              <span>Event types</span>
              <div className="grid gap-2 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                {defaultEventTypes.map((eventName) => {
                  const selected = draft.eventTypes.includes(eventName);
                  return (
                    <label key={eventName} className="flex items-center gap-3">
                      <input
                        checked={selected}
                        onChange={() =>
                          setDraft((current) => ({
                            ...current,
                            eventTypes: selected
                              ? current.eventTypes.filter((item) => item !== eventName)
                              : [...current.eventTypes, eventName],
                          }))
                        }
                        type="checkbox"
                      />
                      <span>{eventName}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            <button
              className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isSaving || !selectedDefinition?.implemented}
              onClick={() => void handleConnect()}
              type="button"
            >
              {isSaving ? "Saving..." : selectedDefinition?.implemented ? "Connect integration" : "Scaffolded only"}
            </button>
          </div>
        </section>

        <section className="space-y-6">
          <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-2xl font-semibold text-white">Active connections</h3>
                <p className="mt-2 text-sm text-slate-400">
                  Connections stay isolated per workspace, with encrypted credentials and queued event delivery.
                </p>
              </div>
              <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">
                {payload.connections.length} configured
              </span>
            </div>

            <div className="mt-6 grid gap-4">
              {payload.connections.length ? (
                payload.connections.map((connection) => (
                  <article
                    key={connection.id}
                    className="rounded-[1.5rem] border border-white/10 bg-slate-950/35 p-5"
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-3">
                          <h4 className="text-lg font-semibold text-white">{connection.display_name}</h4>
                          <span className={`rounded-full px-3 py-1 text-xs font-medium ${
                            connection.status === "active"
                              ? "border border-emerald-400/20 bg-emerald-400/10 text-emerald-100"
                              : connection.status === "error"
                                ? "border border-rose-400/20 bg-rose-400/10 text-rose-100"
                                : "border border-white/10 bg-white/5 text-slate-300"
                          }`}>
                            {connection.status}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-slate-400">{connection.integration_type}</p>
                        <p className="mt-3 text-xs uppercase tracking-[0.25em] text-slate-500">
                          Events: {connection.event_types.join(", ")}
                        </p>
                        {connection.last_error ? (
                          <p className="mt-3 rounded-2xl border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-100">
                            {connection.last_error}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap gap-3">
                        <button
                          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200"
                          onClick={() => void handleToggleStatus(connection)}
                          type="button"
                        >
                          {connection.status === "active" ? "Pause" : "Activate"}
                        </button>
                        <button
                          className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-4 py-2 text-sm text-cyan-100"
                          onClick={() => void handleTest(connection)}
                          type="button"
                        >
                          Test
                        </button>
                        <button
                          className="rounded-full border border-rose-400/20 bg-rose-400/10 px-4 py-2 text-sm text-rose-100"
                          onClick={() => void handleDisconnect(connection)}
                          type="button"
                        >
                          Disconnect
                        </button>
                      </div>
                    </div>
                  </article>
                ))
              ) : (
                <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/20 px-5 py-10 text-center text-sm text-slate-400">
                  No integrations have been connected for this workspace yet.
                </div>
              )}
            </div>
          </div>

          <RecentDeliveryPanel deliveries={payload.recent_deliveries} />
        </section>
      </div>
    </main>
  );
}

function RecentDeliveryPanel({ deliveries }: { deliveries: IntegrationDeliverySummary[] }) {
  return (
    <section className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
      <h3 className="text-2xl font-semibold text-white">Recent deliveries</h3>
      <p className="mt-2 text-sm text-slate-400">
        Delivery jobs are processed asynchronously with retries and per-integration logging.
      </p>
      <div className="mt-6 space-y-3">
        {deliveries.length ? deliveries.map((delivery) => (
          <div
            key={delivery.id}
            className="rounded-2xl border border-white/10 bg-slate-950/35 px-4 py-3"
          >
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-white">{delivery.event_type}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {new Date(delivery.created_at).toLocaleString()} · retries {delivery.retry_count}
                </p>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs ${
                delivery.status === "success"
                  ? "border border-emerald-400/20 bg-emerald-400/10 text-emerald-100"
                  : delivery.status === "failed"
                    ? "border border-rose-400/20 bg-rose-400/10 text-rose-100"
                    : "border border-white/10 bg-white/5 text-slate-300"
              }`}>
                {delivery.status}
              </span>
            </div>
            {delivery.error_message ? (
              <p className="mt-3 text-sm text-rose-200">{delivery.error_message}</p>
            ) : null}
          </div>
        )) : (
          <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/20 px-5 py-10 text-center text-sm text-slate-400">
            No integration deliveries have been recorded yet.
          </div>
        )}
      </div>
    </section>
  );
}
