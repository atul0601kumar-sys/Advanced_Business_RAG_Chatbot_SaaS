"use client";

import type { Dispatch, ReactNode, SetStateAction } from "react";
import { useEffect, useMemo, useState } from "react";

import { ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import { VoiceSettingsPanel } from "@/components/chat/VoiceSettingsPanel";
import { useToast } from "@/components/toast-provider";
import {
  fetchChatbotSettings,
  fetchPublicChatbotSettings,
  fetchWorkspaceDocuments,
  fetchWorkspaceList,
  fetchWorkspaceWebsiteSources,
  resetChatbotSettings,
  updateChatbotSettings,
  type ChatbotSettingsResponse,
  type DocumentSummary,
  type PublicChatbotSettingsResponse,
  type WebsiteSourceSummary,
  type WorkspaceSummary,
} from "@/lib/settings";
import { buildEmbedScript, buildPreviewDocument } from "@/lib/widget-preview";

const notificationEventOptions = [
  "new_lead",
  "high_priority_lead",
  "handoff_requested",
  "negative_feedback",
];

type PreviewStatus = "idle" | "loading" | "ready" | "error";

export function SettingsManager() {
  const { pushToast } = useToast();
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [websiteSources, setWebsiteSources] = useState<WebsiteSourceSummary[]>([]);
  const [savedSettings, setSavedSettings] = useState<ChatbotSettingsResponse | null>(null);
  const [draftSettings, setDraftSettings] = useState<ChatbotSettingsResponse | null>(null);
  const [publicSettings, setPublicSettings] = useState<PublicChatbotSettingsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [isLoadingWidgetPreview, setIsLoadingWidgetPreview] = useState(false);
  const [widgetPreviewError, setWidgetPreviewError] = useState("");
  const [previewStatus, setPreviewStatus] = useState<PreviewStatus>("idle");

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      setIsLoading(true);
      try {
        const workspaceList = await fetchWorkspaceList();
        if (!active) return;
        setWorkspaces(workspaceList);
        if (workspaceList.length) {
          setSelectedWorkspaceId((current) => current || workspaceList[0].id);
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
    async function loadWorkspaceSettings() {
      setIsLoading(true);
      setIsLoadingWidgetPreview(true);
      setWidgetPreviewError("");
      setPreviewStatus("loading");
      setPublicSettings(null);
      try {
        const [settings, workspaceDocuments, workspaceSources, workspacePublicSettings] = await Promise.all([
          fetchChatbotSettings(selectedWorkspaceId),
          fetchWorkspaceDocuments(selectedWorkspaceId),
          fetchWorkspaceWebsiteSources(selectedWorkspaceId),
          fetchPublicChatbotSettings(selectedWorkspaceId),
        ]);
        if (!active) return;
        setSavedSettings(settings);
        setDraftSettings(settings);
        setDocuments(workspaceDocuments);
        setWebsiteSources(workspaceSources);
        setPublicSettings(workspacePublicSettings);
        setError("");
      } catch (loadError) {
        if (!active) return;
        const message = loadError instanceof Error ? loadError.message : "Could not load chatbot settings.";
        setError(message);
        setPublicSettings(null);
        setWidgetPreviewError(message);
        setPreviewStatus("error");
      } finally {
        if (active) {
          setIsLoading(false);
          setIsLoadingWidgetPreview(false);
        }
      }
    }
    void loadWorkspaceSettings();
    return () => {
      active = false;
    };
  }, [selectedWorkspaceId]);

  const dirty = useMemo(() => {
    if (!savedSettings || !draftSettings) return false;
    return JSON.stringify(savedSettings) !== JSON.stringify(draftSettings);
  }, [draftSettings, savedSettings]);

  const embedScript = useMemo(() => {
    if (!publicSettings) return "";
    return buildEmbedScript(publicSettings);
  }, [publicSettings]);

  const previewDocument = useMemo(() => {
    if (!publicSettings) return "";
    return buildPreviewDocument(publicSettings);
  }, [publicSettings]);

  useEffect(() => {
    if (!publicSettings || !selectedWorkspaceId) {
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
        setWidgetPreviewError("");
        return;
      }

      if (payload.status === "error") {
        setPreviewStatus("error");
        setWidgetPreviewError(payload.error || "The live widget preview could not be rendered.");
      }
    };

    window.addEventListener("message", handleMessage);
    return () => {
      window.removeEventListener("message", handleMessage);
    };
  }, [publicSettings, selectedWorkspaceId]);

  async function handleSave() {
    if (!draftSettings) return;
    setIsSaving(true);
    try {
      const normalized = normalizeNotificationTriggers(draftSettings);
      const updated = await updateChatbotSettings(normalized);
      const refreshedPublicSettings = await fetchPublicChatbotSettings(updated.workspace_id);
      setSavedSettings(updated);
      setDraftSettings(updated);
      setPublicSettings(refreshedPublicSettings);
      setPreviewStatus("loading");
      setWidgetPreviewError("");
      pushToast({
        title: "Settings saved",
        description: "Chatbot customization was updated for this workspace.",
        tone: "success",
      });
    } catch (saveError) {
      pushToast({
        title: "Settings could not be saved",
        description: saveError instanceof Error ? saveError.message : "Please review the form and try again.",
        tone: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReset() {
    if (!selectedWorkspaceId) return;
    setIsSaving(true);
    try {
      const reset = await resetChatbotSettings(selectedWorkspaceId);
      const refreshedPublicSettings = await fetchPublicChatbotSettings(selectedWorkspaceId);
      setSavedSettings(reset);
      setDraftSettings(reset);
      setPublicSettings(refreshedPublicSettings);
      setPreviewStatus("loading");
      setWidgetPreviewError("");
      pushToast({
        title: "Defaults restored",
        description: "Safe default chatbot settings have been restored.",
        tone: "success",
      });
    } catch (resetError) {
      pushToast({
        title: "Reset failed",
        description: resetError instanceof Error ? resetError.message : "Please try again.",
        tone: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleImageUpload(
    file: File | undefined,
    apply: (value: string | null) => void,
  ) {
    if (!file) return;
    const value = await readFileAsDataUrl(file);
    apply(value);
  }

  async function handleCopyEmbedScript() {
    if (!embedScript) return;

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

  if (isLoading && !draftSettings) {
    return (
      <main className="space-y-6">
        <LoadingGrid rows={2} />
        <LoadingGrid rows={5} />
      </main>
    );
  }

  if (error && !draftSettings) {
    return (
      <ErrorState
        actionLabel="Retry loading"
        description={error}
        onAction={() => window.location.reload()}
        title="Settings dashboard could not be loaded"
      />
    );
  }

  if (!draftSettings) {
    return null;
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.14),transparent_35%),linear-gradient(145deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.35em] text-sky-200/70">Control plane</p>
            <h2 className="mt-3 text-4xl font-semibold text-white">Workspace chatbot settings</h2>
            <p className="mt-3 text-slate-300">
              Configure branding, behavior, lead capture, handoff, widget delivery, safety, and advanced prompt instructions from one workspace-scoped control surface.
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
              disabled={!dirty || isSaving}
              onClick={() => setDraftSettings(savedSettings)}
              type="button"
            >
              Discard draft
            </button>
            <button
              className="rounded-full border border-amber-400/20 bg-amber-400/10 px-4 py-2.5 text-sm text-amber-100"
              disabled={isSaving}
              onClick={() => void handleReset()}
              type="button"
            >
              Reset defaults
            </button>
            <button
              className="rounded-full bg-white px-4 py-2.5 text-sm font-semibold text-slate-950"
              disabled={isSaving}
              onClick={() => void handleSave()}
              type="button"
            >
              {isSaving ? "Saving..." : "Save settings"}
            </button>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-3 text-xs text-slate-400">
          <span className="rounded-full border border-white/10 px-3 py-1.5">
            {dirty ? "Unsaved changes" : "All changes saved"}
          </span>
          <span className="rounded-full border border-white/10 px-3 py-1.5">
            Updated {new Date(draftSettings.updated_at).toLocaleString()}
          </span>
        </div>
      </section>

      {error ? (
        <section className="rounded-3xl border border-amber-400/20 bg-amber-400/10 px-5 py-4 text-sm text-amber-100">
          {error}
        </section>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.9fr]">
        <div className="space-y-6">
          <SettingsSection title="General" description="Identity, welcome copy, colors, and assets.">
            <div className="grid gap-4 md:grid-cols-2">
              <TextField label="Bot name" value={draftSettings.identity.bot_name} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.identity.bot_name = value; })} />
              <TextField label="Tagline" value={draftSettings.identity.tagline ?? ""} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.identity.tagline = value || null; })} />
              <ColorField label="Primary brand color" value={draftSettings.identity.brand_color_primary} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.identity.brand_color_primary = value; })} />
              <ColorField label="Secondary brand color" value={draftSettings.identity.brand_color_secondary} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.identity.brand_color_secondary = value; })} />
              <FileField label="Bot avatar" onChange={(file) => void handleImageUpload(file, (value) => updateDraft(setDraftSettings, (draft) => { draft.identity.bot_avatar = value; }))} />
              <FileField label="Logo" onChange={(file) => void handleImageUpload(file, (value) => updateDraft(setDraftSettings, (draft) => { draft.identity.logo = value; }))} />
              <TextAreaField className="md:col-span-2" label="Welcome message" rows={4} value={draftSettings.identity.welcome_message} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.identity.welcome_message = value; })} />
            </div>
          </SettingsSection>

          <SettingsSection title="Chat behavior" description="Tone, response style, markdown, citations, and confidence display.">
            <div className="grid gap-4 md:grid-cols-2">
              <SelectField label="Tone" value={draftSettings.behavior.tone} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.behavior.tone = value as ChatbotSettingsResponse["behavior"]["tone"]; })} options={["professional", "friendly", "concise", "detailed"]} />
              <SelectField label="Response style" value={draftSettings.behavior.response_style} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.behavior.response_style = value as ChatbotSettingsResponse["behavior"]["response_style"]; })} options={["paragraph", "bullet_points", "mixed"]} />
              <NumberField label="Max response length" value={draftSettings.behavior.max_response_length} min={120} max={4000} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.behavior.max_response_length = value; })} />
              <div className="grid gap-3">
                <ToggleField label="Enable markdown formatting" checked={draftSettings.behavior.markdown_enabled} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.behavior.markdown_enabled = checked; })} />
                <ToggleField label="Show citations" checked={draftSettings.behavior.citations_enabled} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.behavior.citations_enabled = checked; })} />
                <ToggleField label="Show confidence score" checked={draftSettings.behavior.confidence_score_enabled} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.behavior.confidence_score_enabled = checked; })} />
              </div>
            </div>
          </SettingsSection>

          <SettingsSection title="Lead capture" description="Capture preferences, required fields, prompt text, and follow-up copy.">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-3">
                <ToggleField label="Enable lead capture" checked={draftSettings.lead_capture.enabled} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.lead_capture.enabled = checked; })} />
                <ToggleField label="Trigger on first message" checked={draftSettings.lead_capture.trigger_on_first_message} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.lead_capture.trigger_on_first_message = checked; })} />
                <ToggleField label="Trigger on low confidence" checked={draftSettings.lead_capture.trigger_on_low_confidence} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.lead_capture.trigger_on_low_confidence = checked; })} />
              </div>
              <div className="grid gap-4">
                <NumberField label="Trigger after N messages" value={draftSettings.lead_capture.trigger_after_n_messages} min={1} max={20} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.lead_capture.trigger_after_n_messages = value; })} />
                <ChecklistField
                  label="Required fields"
                  options={["name", "email", "phone", "company"]}
                  selected={draftSettings.lead_capture.required_fields}
                  onToggle={(field) =>
                    updateDraft(setDraftSettings, (draft) => {
                      const next = new Set(draft.lead_capture.required_fields);
                      if (next.has(field)) next.delete(field);
                      else next.add(field);
                      draft.lead_capture.required_fields = [...next];
                    })
                  }
                />
              </div>
              <TextAreaField className="md:col-span-2" label="Lead form message" rows={3} value={draftSettings.lead_capture.custom_form_message ?? ""} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.lead_capture.custom_form_message = value || null; })} />
              <TextAreaField className="md:col-span-2" label="Auto-response after submission" rows={3} value={draftSettings.lead_capture.auto_response_message ?? ""} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.lead_capture.auto_response_message = value || null; })} />
            </div>
          </SettingsSection>

          <SettingsSection title="Handoff" description="Escalation behavior and human fallback messaging.">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-3">
                <ToggleField label="Enable human handoff" checked={draftSettings.handoff.enabled} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.handoff.enabled = checked; })} />
                <ToggleField label="Enable scheduling option" checked={draftSettings.handoff.enable_scheduling} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.handoff.enable_scheduling = checked; })} />
                <ToggleField label="Escalate on low confidence" checked={draftSettings.handoff.escalate_on_low_confidence} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.handoff.escalate_on_low_confidence = checked; })} />
                <ToggleField label="Escalate on repeated failures" checked={draftSettings.handoff.escalate_on_repeated_failures} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.handoff.escalate_on_repeated_failures = checked; })} />
              </div>
              <TextAreaField label="Handoff message" rows={5} value={draftSettings.handoff.custom_message ?? ""} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.handoff.custom_message = value || null; })} />
            </div>
          </SettingsSection>

          <SettingsSection title="Widget" description="Launcher placement, popup messaging, branding, and appearance timing.">
            <div className="grid gap-4 md:grid-cols-2">
              <SelectField label="Position" value={draftSettings.widget.position} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.widget.position = value as ChatbotSettingsResponse["widget"]["position"]; })} options={["left", "right"]} />
              <SelectField label="Size" value={draftSettings.widget.size} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.widget.size = value as ChatbotSettingsResponse["widget"]["size"]; })} options={["compact", "comfortable", "expanded"]} />
              <SelectField label="Theme" value={draftSettings.widget.theme} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.widget.theme = value as ChatbotSettingsResponse["widget"]["theme"]; })} options={["light", "dark", "auto"]} />
              <NumberField label="Delay before widget appears (seconds)" value={draftSettings.widget.delay_before_appearance_seconds} min={0} max={120} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.widget.delay_before_appearance_seconds = value; })} />
              <ToggleField label="Show branding" checked={draftSettings.widget.show_branding} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.widget.show_branding = checked; })} />
              <FileField label="Launcher icon" onChange={(file) => void handleImageUpload(file, (value) => updateDraft(setDraftSettings, (draft) => { draft.widget.launcher_icon = value; }))} />
              <TextAreaField className="md:col-span-2" label="Welcome popup message" rows={3} value={draftSettings.widget.welcome_popup_message ?? ""} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.widget.welcome_popup_message = value || null; })} />
            </div>
          </SettingsSection>

          <SettingsSection title="Voice" description="Voice feature toggles and transcript preview preferences.">
            <VoiceSettingsPanel draftSettings={draftSettings} setDraftSettings={setDraftSettings} />
          </SettingsSection>

          <SettingsSection title="Notifications" description="Workspace alert recipients, webhook endpoints, and event coverage.">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-3">
                <ToggleField label="Enable notifications" checked={draftSettings.notifications.enabled} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.notifications.enabled = checked; })} />
                <NumberField label="Retry attempts" value={draftSettings.notifications.retry_attempts} min={1} max={10} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.notifications.retry_attempts = value; })} />
              </div>
              <ChecklistField
                label="Notification event types"
                options={notificationEventOptions}
                selected={draftSettings.notifications.notification_types}
                onToggle={(item) =>
                  updateDraft(setDraftSettings, (draft) => {
                    const next = new Set(draft.notifications.notification_types);
                    if (next.has(item)) next.delete(item);
                    else next.add(item);
                    draft.notifications.notification_types = [...next];
                  })
                }
              />
              <TextAreaField className="md:col-span-2" label="Email recipients (comma separated)" rows={2} value={draftSettings.notifications.email_recipients.join(", ")} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.notifications.email_recipients = splitCommaValues(value); })} />
              <TextAreaField className="md:col-span-2" label="Webhook endpoints (comma separated)" rows={3} value={draftSettings.notifications.webhook_endpoints.join(", ")} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.notifications.webhook_endpoints = splitCommaValues(value); })} />
            </div>
          </SettingsSection>

          <SettingsSection title="Access and knowledge" description="Public/private mode, rate limits, and source prioritization.">
            <div className="grid gap-4 md:grid-cols-2">
              <SelectField label="Chatbot mode" value={draftSettings.access_control.chatbot_mode} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.access_control.chatbot_mode = value as ChatbotSettingsResponse["access_control"]["chatbot_mode"]; })} options={["public", "private"]} />
              <NumberField label="Rate limit per user per minute" value={draftSettings.access_control.rate_limit_per_user_per_minute} min={1} max={1000} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.access_control.rate_limit_per_user_per_minute = value; })} />
              <div className="grid gap-3">
                <ToggleField label="Restrict to logged-in users" checked={draftSettings.access_control.restrict_to_logged_in_users} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.access_control.restrict_to_logged_in_users = checked; })} />
                <ToggleField label="Allow guest access" checked={draftSettings.access_control.allow_guest_access} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.access_control.allow_guest_access = checked; })} />
              </div>
              <NumberField label="Chunk relevance threshold" value={draftSettings.knowledge_base.chunk_relevance_threshold} min={0} max={1} step={0.05} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.knowledge_base.chunk_relevance_threshold = value; })} />
              <ChecklistField
                className="md:col-span-2"
                label="Enabled documents"
                options={documents.map((item) => item.title)}
                selected={documents.filter((item) => !draftSettings.knowledge_base.disabled_document_ids.includes(item.id)).map((item) => item.title)}
                onToggle={(title) =>
                  updateDraft(setDraftSettings, (draft) => {
                    const document = documents.find((item) => item.title === title);
                    if (!document) return;
                    const disabled = new Set(draft.knowledge_base.disabled_document_ids);
                    if (disabled.has(document.id)) disabled.delete(document.id);
                    else disabled.add(document.id);
                    draft.knowledge_base.disabled_document_ids = [...disabled];
                  })
                }
              />
              <ChecklistField
                className="md:col-span-2"
                label="Prioritized documents"
                options={documents.map((item) => item.title)}
                selected={documents.filter((item) => draftSettings.knowledge_base.prioritized_document_ids.includes(item.id)).map((item) => item.title)}
                onToggle={(title) =>
                  updateDraft(setDraftSettings, (draft) => {
                    const document = documents.find((item) => item.title === title);
                    if (!document) return;
                    const prioritized = new Set(draft.knowledge_base.prioritized_document_ids);
                    if (prioritized.has(document.id)) prioritized.delete(document.id);
                    else prioritized.add(document.id);
                    draft.knowledge_base.prioritized_document_ids = [...prioritized];
                  })
                }
              />
              <ChecklistField
                className="md:col-span-2"
                label="Enabled URLs"
                options={websiteSources.map((item) => item.url)}
                selected={websiteSources.filter((item) => !draftSettings.knowledge_base.disabled_urls.includes(item.url)).map((item) => item.url)}
                onToggle={(url) =>
                  updateDraft(setDraftSettings, (draft) => {
                    const disabled = new Set(draft.knowledge_base.disabled_urls);
                    if (disabled.has(url)) disabled.delete(url);
                    else disabled.add(url);
                    draft.knowledge_base.disabled_urls = [...disabled];
                  })
                }
              />
              <ChecklistField
                className="md:col-span-2"
                label="Prioritized URLs"
                options={websiteSources.map((item) => item.url)}
                selected={draftSettings.knowledge_base.prioritized_urls}
                onToggle={(url) =>
                  updateDraft(setDraftSettings, (draft) => {
                    const prioritized = new Set(draft.knowledge_base.prioritized_urls);
                    if (prioritized.has(url)) prioritized.delete(url);
                    else prioritized.add(url);
                    draft.knowledge_base.prioritized_urls = [...prioritized];
                  })
                }
              />
            </div>
          </SettingsSection>

          <SettingsSection title="Analytics and advanced" description="Tracking preferences and safe prompt customization.">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-3">
                <ToggleField label="Enable analytics tracking" checked={draftSettings.analytics.tracking_enabled} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.analytics.tracking_enabled = checked; })} />
                <ToggleField label="Enable feedback collection" checked={draftSettings.analytics.feedback_collection_enabled} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.analytics.feedback_collection_enabled = checked; })} />
                <ToggleField label="Anonymize user data" checked={draftSettings.analytics.anonymize_user_data} onChange={(checked) => updateDraft(setDraftSettings, (draft) => { draft.analytics.anonymize_user_data = checked; })} />
              </div>
              <div className="rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm text-cyan-50">
                Core anti-hallucination and secret-protection rules stay enforced even when prompt customization changes.
              </div>
              <TextAreaField className="md:col-span-2" label="Company instructions" rows={4} value={draftSettings.prompt.company_instructions ?? ""} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.prompt.company_instructions = value || null; })} />
              <TextAreaField className="md:col-span-2" label="Business rules" rows={4} value={draftSettings.prompt.business_rules ?? ""} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.prompt.business_rules = value || null; })} />
              <TextAreaField className="md:col-span-2" label="Custom system prompt" rows={8} value={draftSettings.prompt.custom_system_prompt ?? ""} onChange={(value) => updateDraft(setDraftSettings, (draft) => { draft.prompt.custom_system_prompt = value || null; })} />
            </div>
          </SettingsSection>
        </div>

        <div className="space-y-6">
          <section className="sticky top-24 space-y-6">
            <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
              <p className="text-xs uppercase tracking-[0.3em] text-sky-200/70">Live preview</p>
              <h3 className="mt-3 text-2xl font-semibold text-white">Chatbot experience</h3>
              <p className="mt-2 text-sm text-slate-400">
                Preview updates instantly while you edit. Save only when the experience feels right.
              </p>
              <div className="mt-6 rounded-[1.9rem] border border-white/10 bg-slate-950/80 p-5" style={{ borderColor: `${draftSettings.identity.brand_color_primary}33` }}>
                <div className="flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-2xl border border-white/10" style={{ backgroundColor: draftSettings.identity.brand_color_primary }}>
                    {draftSettings.identity.bot_avatar || draftSettings.identity.logo ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img className="h-full w-full object-cover" src={draftSettings.identity.bot_avatar || draftSettings.identity.logo || ""} alt={draftSettings.identity.bot_name} />
                    ) : (
                      <span className="text-lg font-semibold text-white">{draftSettings.identity.bot_name.slice(0, 1).toUpperCase()}</span>
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{draftSettings.identity.bot_name}</p>
                    <p className="text-xs text-slate-400">{draftSettings.identity.tagline || "Grounded business assistant"}</p>
                  </div>
                </div>
                <div className="mt-5 rounded-3xl border border-white/10 bg-white/[0.04] p-4 text-sm text-slate-200">
                  {draftSettings.identity.welcome_message}
                </div>
                <div className="mt-4 rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                  <div className="rounded-2xl px-4 py-3 text-sm text-white" style={{ backgroundColor: draftSettings.identity.brand_color_primary }}>
                    {draftSettings.behavior.response_style === "bullet_points"
                      ? "• Grounded answer\n• Safe prompt rules stay active\n• Citations can be shown below"
                      : draftSettings.behavior.response_style === "mixed"
                        ? "Here is a short grounded answer summary.\n\n• It follows your chosen tone\n• It respects your safety rules\n• It can still cite sources"
                        : "Here is a grounded paragraph response that follows your configured tone, response length, and safety protections."}
                  </div>
                  {draftSettings.behavior.confidence_score_enabled ? (
                    <div className="mt-3 inline-flex rounded-full border border-emerald-400/30 bg-emerald-500/15 px-3 py-1 text-xs text-emerald-100">
                      High confidence
                    </div>
                  ) : null}
                  {draftSettings.behavior.citations_enabled ? (
                    <div className="mt-3 rounded-2xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                      Citation preview: pricing.pdf | page 2
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
              <p className="text-xs uppercase tracking-[0.3em] text-sky-200/70">Widget preview</p>
              <h3 className="mt-3 text-2xl font-semibold text-white">Live embed runtime</h3>
              <p className="mt-2 text-sm text-slate-400">
                This panel fetches the current saved settings from the backend, generates the real embed snippet, and mounts the public widget bundle.
              </p>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  className="rounded-full bg-white px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={!embedScript}
                  onClick={() => void handleCopyEmbedScript()}
                  type="button"
                >
                  Copy embed script
                </button>
                <span className="rounded-full border border-white/10 px-3 py-2 text-xs text-slate-300">
                  {previewStatus === "ready" ? "Preview ready" : previewStatus === "error" ? "Preview error" : "Loading preview"}
                </span>
              </div>

              {widgetPreviewError ? (
                <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                  {widgetPreviewError}
                </div>
              ) : null}

              <div className="mt-5 grid gap-3 text-sm text-slate-300">
                <InfoCard label="Bot name" value={publicSettings?.identity.bot_name || savedSettings?.identity.bot_name || "Unavailable"} />
                <InfoCard label="Primary color" value={publicSettings?.identity.brand_color_primary || savedSettings?.identity.brand_color_primary || "Unavailable"} />
                <InfoCard label="Welcome message" value={publicSettings?.widget.welcome_popup_message || publicSettings?.identity.welcome_message || savedSettings?.widget.welcome_popup_message || savedSettings?.identity.welcome_message || "Unavailable"} />
                <InfoCard label="Position" value={publicSettings?.widget.position || savedSettings?.widget.position || "Unavailable"} />
              </div>

              <div className="mt-5 rounded-[1.5rem] border border-white/10 bg-slate-950/80 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Generated embed</p>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-all text-sm text-slate-200">
                  {embedScript || (isLoadingWidgetPreview ? "Loading embed script..." : "Embed script unavailable.")}
                </pre>
              </div>

              <div className="mt-5 overflow-hidden rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(8,47,73,0.28),rgba(2,6,23,0.9))]">
                <div className="flex items-center justify-between border-b border-white/10 px-5 py-3 text-xs uppercase tracking-[0.24em] text-slate-400">
                  <span>{publicSettings?.widget.position || savedSettings?.widget.position || draftSettings.widget.position} dock</span>
                  <span>{publicSettings?.widget.theme || savedSettings?.widget.theme || draftSettings.widget.theme} theme</span>
                </div>
                <div className="relative min-h-[520px]">
                  {previewStatus !== "ready" ? (
                    <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/55 backdrop-blur-sm">
                      <div className="max-w-sm rounded-3xl border border-white/10 bg-slate-950/90 px-5 py-4 text-center">
                        <p className="text-sm font-medium text-white">
                          {previewStatus === "error" ? "Widget preview failed" : "Loading live widget"}
                        </p>
                        <p className="mt-2 text-sm text-slate-400">
                          {previewStatus === "error"
                            ? widgetPreviewError || "The preview runtime did not finish mounting."
                            : "Fetching settings and mounting the public widget bundle."}
                        </p>
                      </div>
                    </div>
                  ) : null}

                  {publicSettings ? (
                    <iframe
                      className="h-[520px] w-full bg-transparent"
                      key={`${selectedWorkspaceId}:${savedSettings?.updated_at || draftSettings.updated_at}`}
                      srcDoc={previewDocument}
                      title="Live widget preview"
                    />
                  ) : (
                    <div className="flex h-[520px] items-center justify-center px-6 text-center text-sm text-slate-400">
                      {isLoadingWidgetPreview ? "Loading live widget preview..." : "The widget preview is unavailable for this workspace."}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

function SettingsSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
      <div>
        <h3 className="text-2xl font-semibold text-white">{title}</h3>
        <p className="mt-2 text-sm text-slate-400">{description}</p>
      </div>
      <div className="mt-6">{children}</div>
    </section>
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

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      <span>{label}</span>
      <input className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-white outline-none" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      <span>{label}</span>
      <input className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-white outline-none" type="number" value={value} min={min} max={max} step={step ?? 1} onChange={(event) => onChange(Number(event.target.value) || min)} />
    </label>
  );
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      <span>{label}</span>
      <select className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-white outline-none" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function TextAreaField({
  label,
  value,
  rows,
  onChange,
  className,
}: {
  label: string;
  value: string;
  rows: number;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <label className={`grid gap-2 text-sm text-slate-300 ${className ?? ""}`}>
      <span>{label}</span>
      <textarea className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-white outline-none" rows={rows} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function ToggleField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-center gap-3 text-sm text-slate-300">
      <input checked={checked} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
      <span>{label}</span>
    </label>
  );
}

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      <span>{label}</span>
      <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3">
        <input className="h-10 w-12 rounded border-0 bg-transparent p-0" type="color" value={value} onChange={(event) => onChange(event.target.value)} />
        <input className="w-full bg-transparent text-white outline-none" value={value} onChange={(event) => onChange(event.target.value)} />
      </div>
    </label>
  );
}

function FileField({ label, onChange }: { label: string; onChange: (file: File | undefined) => void }) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      <span>{label}</span>
      <input className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-white outline-none file:mr-4 file:rounded-full file:border-0 file:bg-white file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-950" type="file" accept="image/*" onChange={(event) => onChange(event.target.files?.[0])} />
    </label>
  );
}

function ChecklistField({
  label,
  options,
  selected,
  onToggle,
  className,
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
  className?: string;
}) {
  const selectedSet = new Set(selected);
  return (
    <div className={`grid gap-2 text-sm text-slate-300 ${className ?? ""}`}>
      <span>{label}</span>
      <div className="grid gap-2 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
        {options.length ? options.map((option) => (
          <label key={option} className="flex items-center gap-3">
            <input checked={selectedSet.has(option)} onChange={() => onToggle(option)} type="checkbox" />
            <span className="break-all">{option}</span>
          </label>
        )) : <span className="text-slate-500">No options available for this workspace yet.</span>}
      </div>
    </div>
  );
}

function updateDraft(
  setDraft: Dispatch<SetStateAction<ChatbotSettingsResponse | null>>,
  mutator: (draft: ChatbotSettingsResponse) => void,
) {
  setDraft((current) => {
    if (!current) return current;
    const next = structuredClone(current);
    mutator(next);
    return next;
  });
}

function splitCommaValues(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeNotificationTriggers(payload: ChatbotSettingsResponse): ChatbotSettingsResponse {
  const next = structuredClone(payload);
  const defaultChannels = ["email", "webhook"];
  const generatedTriggers: Record<string, { enabled: boolean; channels: string[]; email_recipients: string[]; webhook_urls: string[] }> = {};
  for (const eventName of next.notifications.notification_types) {
    generatedTriggers[eventName] = next.notifications.triggers[eventName] ?? {
      enabled: true,
      channels: defaultChannels,
      email_recipients: next.notifications.email_recipients,
      webhook_urls: next.notifications.webhook_endpoints,
    };
  }
  next.notifications.triggers = generatedTriggers;
  return next;
}

async function readFileAsDataUrl(file: File): Promise<string> {
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Could not read image file."));
    reader.readAsDataURL(file);
  });
}
