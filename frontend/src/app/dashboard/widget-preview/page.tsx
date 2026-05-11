"use client";

import { useEffect, useMemo, useState } from "react";

import { ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import { useToast } from "@/components/toast-provider";
import {
  fetchChatbotSettings,
  fetchPublicChatbotSettings,
  fetchWorkspaceList,
  type ChatbotSettingsResponse,
  type PublicChatbotSettingsResponse,
  type WorkspaceSummary,
} from "@/lib/settings";
import { buildEmbedScript, buildPreviewDocument } from "@/lib/widget-preview";

type PreviewStatus = "idle" | "loading" | "ready" | "error";

export default function WidgetPreviewPage() {
  const { pushToast } = useToast();
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [settings, setSettings] = useState<ChatbotSettingsResponse | null>(null);
  const [publicSettings, setPublicSettings] = useState<PublicChatbotSettingsResponse | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isLoadingPreviewData, setIsLoadingPreviewData] = useState(false);
  const [dataError, setDataError] = useState("");
  const [previewStatus, setPreviewStatus] = useState<PreviewStatus>("idle");
  const [previewError, setPreviewError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      setIsBootstrapping(true);
      try {
        const workspaceList = await fetchWorkspaceList();
        if (!active) {
          return;
        }
        setWorkspaces(workspaceList);
        setSelectedWorkspaceId((current) => current || workspaceList[0]?.id || "");
        setDataError("");
      } catch (error) {
        if (!active) {
          return;
        }
        setDataError(error instanceof Error ? error.message : "Could not load workspaces.");
      } finally {
        if (active) {
          setIsBootstrapping(false);
        }
      }
    }

    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      setSettings(null);
      setPublicSettings(null);
      return;
    }

    let active = true;

    async function loadPreviewData() {
      setIsLoadingPreviewData(true);
      setPreviewStatus("loading");
      setPreviewError("");
      setSettings(null);
      setPublicSettings(null);

      try {
        const [workspaceSettings, workspacePublicSettings] = await Promise.all([
          fetchChatbotSettings(selectedWorkspaceId),
          fetchPublicChatbotSettings(selectedWorkspaceId),
        ]);

        if (!active) {
          return;
        }

        setSettings(workspaceSettings);
        setPublicSettings(workspacePublicSettings);
        setDataError("");
      } catch (error) {
        if (!active) {
          return;
        }

        const message =
          error instanceof Error
            ? error.message
            : "Could not load widget preview settings.";
        setDataError(message);
        setPreviewStatus("error");
        setPreviewError(message);
      } finally {
        if (active) {
          setIsLoadingPreviewData(false);
        }
      }
    }

    void loadPreviewData();
    return () => {
      active = false;
    };
  }, [refreshKey, selectedWorkspaceId]);

  useEffect(() => {
    if (!publicSettings) {
      return;
    }

    const handleMessage = (event: MessageEvent) => {
      const payload = event.data as
        | {
            source?: string;
            workspaceId?: string;
            status?: PreviewStatus;
            error?: string;
          }
        | undefined;

      if (payload?.source !== "widget-preview" || payload.workspaceId !== selectedWorkspaceId) {
        return;
      }

      if (payload.status === "ready") {
        setPreviewStatus("ready");
        setPreviewError("");
        return;
      }

      if (payload.status === "error") {
        setPreviewStatus("error");
        setPreviewError(payload.error || "The live widget preview could not be rendered.");
      }
    };

    window.addEventListener("message", handleMessage);
    return () => {
      window.removeEventListener("message", handleMessage);
    };
  }, [publicSettings, selectedWorkspaceId]);

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null,
    [selectedWorkspaceId, workspaces],
  );

  const embedScript = useMemo(() => {
    if (!publicSettings) {
      return "";
    }
    return buildEmbedScript(publicSettings);
  }, [publicSettings]);

  const previewDocument = useMemo(() => {
    if (!publicSettings) {
      return "";
    }
    return buildPreviewDocument(publicSettings);
  }, [publicSettings]);

  async function handleCopyEmbedScript() {
    if (!embedScript) {
      return;
    }

    try {
      if (!navigator.clipboard) {
        throw new Error("Clipboard API unavailable.");
      }
      await navigator.clipboard.writeText(embedScript);
      pushToast({
        title: "Embed script copied",
        description: "The live widget embed snippet is ready to paste into your site.",
        tone: "success",
      });
    } catch {
      pushToast({
        title: "Copy failed",
        description: "Clipboard access is unavailable in this browser.",
        tone: "error",
      });
    }
  }

  function handleRefresh() {
    if (!selectedWorkspaceId) {
      return;
    }
    setDataError("");
    setPreviewError("");
    setPreviewStatus("loading");
    setRefreshKey((current) => current + 1);
  }

  if (isBootstrapping) {
    return (
      <main className="space-y-6">
        <LoadingGrid rows={2} />
        <LoadingGrid rows={3} />
      </main>
    );
  }

  if (dataError && !workspaces.length) {
    return (
      <ErrorState
        title="Widget preview could not be loaded"
        description={dataError}
        actionLabel="Retry loading"
        onAction={() => window.location.reload()}
      />
    );
  }

  if (!workspaces.length) {
    return (
      <section className="rounded-[2rem] border border-dashed border-white/15 bg-white/[0.03] p-10 text-center">
        <p className="text-sm uppercase tracking-[0.3em] text-cyan-200/70">No workspaces yet</p>
        <h2 className="mt-3 text-2xl font-semibold text-white">A workspace is required for widget preview</h2>
        <p className="mt-3 text-slate-400">
          Create a workspace first, then come back here to generate the live embed snippet and preview.
        </p>
      </section>
    );
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.14),transparent_35%),linear-gradient(145deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.35em] text-sky-200/70">Embeddable experience</p>
            <h1 className="mt-3 text-4xl font-semibold text-white">Live widget preview</h1>
            <p className="mt-3 text-slate-300">
              Pull the current chatbot settings from the backend, generate the real embed script, and verify the
              production widget runtime before publishing.
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
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-200"
              onClick={handleRefresh}
              type="button"
            >
              Refresh preview
            </button>
            <button
              className="rounded-full bg-white px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!embedScript}
              onClick={() => void handleCopyEmbedScript()}
              type="button"
            >
              Copy embed script
            </button>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-3 text-xs text-slate-400">
          <span className="rounded-full border border-white/10 px-3 py-1.5">
            {selectedWorkspace?.name ?? "Workspace"} preview
          </span>
          {settings ? (
            <span className="rounded-full border border-white/10 px-3 py-1.5">
              Updated {new Date(settings.updated_at).toLocaleString()}
            </span>
          ) : null}
          {publicSettings ? (
            <span className="rounded-full border border-white/10 px-3 py-1.5">
              SDK {publicSettings.embed.version}
            </span>
          ) : null}
        </div>
      </section>

      {dataError && settings ? (
        <section className="rounded-3xl border border-rose-400/20 bg-rose-500/10 px-5 py-4 text-sm text-rose-100">
          {dataError}
        </section>
      ) : null}

      {isLoadingPreviewData && !settings ? (
        <div className="space-y-6">
          <LoadingGrid rows={2} />
          <LoadingGrid rows={2} />
        </div>
      ) : null}

      {!isLoadingPreviewData && !settings && dataError ? (
        <ErrorState
          title="Widget preview data is unavailable"
          description={dataError}
          actionLabel="Retry loading"
          onAction={() => setRefreshKey((current) => current + 1)}
        />
      ) : null}

      {settings && publicSettings ? (
        <div className="grid gap-6 xl:grid-cols-[1fr_1.1fr]">
          <section className="space-y-6">
            <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
              <p className="text-xs uppercase tracking-[0.3em] text-sky-200/70">Generated embed</p>
              <h2 className="mt-3 text-2xl font-semibold text-white">Workspace-scoped script</h2>
              <p className="mt-2 text-sm text-slate-400">
                This snippet is built from the backend response for the currently selected workspace.
              </p>

              <div className="mt-6 rounded-[1.5rem] border border-white/10 bg-slate-950/80 p-4">
                <pre className="overflow-x-auto whitespace-pre-wrap break-all text-sm text-slate-200">
                  {embedScript}
                </pre>
              </div>

              <div className="mt-6 grid gap-3 text-sm text-slate-300 md:grid-cols-2">
                <InfoCard label="Bot name" value={settings.identity.bot_name} />
                <InfoCard label="Position" value={settings.widget.position} />
                <InfoCard label="Primary color" value={settings.identity.brand_color_primary} />
                <InfoCard
                  label="Welcome message"
                  value={settings.widget.welcome_popup_message || settings.identity.welcome_message}
                />
                <InfoCard label="Script URL" value={publicSettings.embed.script_url} />
                <InfoCard label="API base URL" value={publicSettings.embed.api_base_url} />
              </div>
            </div>

            <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
              <p className="text-xs uppercase tracking-[0.3em] text-sky-200/70">Brand assets</p>
              <h2 className="mt-3 text-2xl font-semibold text-white">Current widget identity</h2>
              <div className="mt-5 flex items-center gap-4 rounded-[1.5rem] border border-white/10 bg-slate-950/70 p-4">
                <div
                  className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-2xl border border-white/10"
                  style={{ backgroundColor: settings.identity.brand_color_primary }}
                >
                  {settings.identity.logo || settings.identity.bot_avatar ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      alt={settings.identity.bot_name}
                      className="h-full w-full object-cover"
                      src={settings.identity.logo || settings.identity.bot_avatar || ""}
                    />
                  ) : (
                    <span className="text-xl font-semibold text-white">
                      {settings.identity.bot_name.slice(0, 1).toUpperCase()}
                    </span>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-lg font-semibold text-white">{settings.identity.bot_name}</p>
                  <p className="truncate text-sm text-slate-400">
                    {settings.identity.tagline || "Grounded business assistant"}
                  </p>
                  <p className="mt-2 text-sm text-slate-300">
                    {settings.widget.welcome_popup_message || settings.identity.welcome_message}
                  </p>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-sky-200/70">Live runtime preview</p>
                <h2 className="mt-3 text-2xl font-semibold text-white">Production widget renderer</h2>
                <p className="mt-2 text-sm text-slate-400">
                  The iframe below mounts the public widget bundle with the same settings your site embed will use.
                </p>
              </div>
              <span className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300">
                {previewStatus === "ready"
                  ? "Ready"
                  : previewStatus === "error"
                    ? "Preview error"
                    : "Loading"}
              </span>
            </div>

            <div className="mt-6 overflow-hidden rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(8,47,73,0.28),rgba(2,6,23,0.9))]">
              <div className="flex items-center justify-between border-b border-white/10 px-5 py-3 text-xs uppercase tracking-[0.24em] text-slate-400">
                <span>{settings.widget.position} dock</span>
                <span>{settings.widget.theme} theme</span>
              </div>

              <div className="relative min-h-[640px]">
                {previewStatus !== "ready" ? (
                  <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/55 backdrop-blur-sm">
                    <div className="max-w-sm rounded-3xl border border-white/10 bg-slate-950/90 px-5 py-4 text-center">
                      <p className="text-sm font-medium text-white">
                        {previewStatus === "error" ? "Widget preview failed" : "Loading live widget"}
                      </p>
                      <p className="mt-2 text-sm text-slate-400">
                        {previewStatus === "error"
                          ? previewError || "The preview runtime did not finish mounting."
                          : "Fetching settings and mounting the public widget bundle."}
                      </p>
                    </div>
                  </div>
                ) : null}

                <iframe
                  className="h-[640px] w-full bg-transparent"
                  key={`${selectedWorkspaceId}:${settings.updated_at}`}
                  srcDoc={previewDocument}
                  title="Live widget preview"
                />
              </div>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{label}</p>
      <p className="mt-2 break-all text-sm text-slate-200">{value}</p>
    </div>
  );
}
