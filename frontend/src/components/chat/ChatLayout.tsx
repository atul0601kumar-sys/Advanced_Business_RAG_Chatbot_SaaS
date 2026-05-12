"use client";

import type { CSSProperties } from "react";
import { startTransition, useEffect, useMemo, useState } from "react";

import { ChatInput } from "@/components/chat/ChatInput";
import { LeadCaptureModal } from "@/components/chat/LeadCaptureModal";
import { BookingScheduler } from "@/components/scheduling/BookingScheduler";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { Sidebar } from "@/components/chat/Sidebar";
import { ExportModal } from "@/components/dashboard/export-modal";
import { useToast } from "@/components/toast-provider";
import {
  captureLead,
  createChatSession,
  downloadResponseAsMarkdown,
  fetchLeadCaptureSettings,
  fetchChatHistory,
  fetchCurrentUser,
  requestHumanHandoff,
  listChatSessions,
  regenerateChatResponse,
  stopChatGeneration,
  streamChatMessage,
  submitChatFeedback,
  type ChatMode,
  type ChatRetrievalFilters,
  type LeadCapturePrompt,
  type LeadCaptureSettings,
  type LeadSummary,
  type ChatSessionSummary,
  type CurrentUser,
  type FeedbackValue,
} from "@/lib/chat";
import {
  CHAT_THEME_STORAGE_KEY,
  defaultChatUiSettings,
  getInitialThemeMode,
  type ChatThemeMode,
} from "@/lib/chat-settings";
import {
  fetchChatbotSettings,
  fetchWorkspaceDocuments,
  type ChatbotSettingsResponse,
  type DocumentSummary,
} from "@/lib/settings";
import type { BookingSummary } from "@/lib/scheduling";
import { useVoiceChat } from "@/lib/voice/use-voice-chat";
import type { UiMessage } from "@/components/chat/MessageBubble";

type ChatLayoutProps = {
  initialView?: "chat" | "history";
};

const HIDDEN_SESSIONS_KEY = "rag_chat_hidden_sessions";
const SESSION_TITLE_OVERRIDES_KEY = "rag_chat_title_overrides";

function normalizeHistoryMessages(historyMessages: Awaited<ReturnType<typeof fetchChatHistory>>["messages"]): UiMessage[] {
  let lastUserContent = "";
  return historyMessages.map((message) => {
    if (message.role === "user") {
      lastUserContent = message.content;
    }
    return {
      id: message.id,
      role: message.role,
      content: message.content,
      citations: message.citations,
      createdAt: message.created_at,
      confidence: message.token_usage?.confidence ?? null,
      relatedQuery: message.role === "assistant" ? lastUserContent : undefined,
      feedback: null,
    };
  });
}

function getStoredJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") {
    return fallback;
  }
  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function persistJson(key: string, value: unknown) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

function applyTitleOverrides(
  sessions: ChatSessionSummary[],
  titleOverrides: Record<string, string>,
  hiddenSessionIds: string[],
) {
  return sessions
    .filter((session) => !hiddenSessionIds.includes(session.id))
    .map((session) => ({
      ...session,
      title: titleOverrides[session.id] ?? session.title,
    }));
}

export function ChatLayout({ initialView = "chat" }: ChatLayoutProps) {
  const { pushToast } = useToast();
  const [themeMode, setThemeMode] = useState<ChatThemeMode>("dark");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [messagesBySession, setMessagesBySession] = useState<Record<string, UiMessage[]>>({});
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [composerValue, setComposerValue] = useState("");
  const [mode, setMode] = useState<ChatMode>("detailed");
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [currentGenerationId, setCurrentGenerationId] = useState<string | null>(null);
  const [collapsedSidebar, setCollapsedSidebar] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(initialView === "history");
  const [hiddenSessionIds, setHiddenSessionIds] = useState<string[]>([]);
  const [titleOverrides, setTitleOverrides] = useState<Record<string, string>>({});
  const [leadPrompt, setLeadPrompt] = useState<LeadCapturePrompt | null>(null);
  const [leadModalOpen, setLeadModalOpen] = useState(false);
  const [leadSettings, setLeadSettings] = useState<LeadCaptureSettings | null>(null);
  const [hasSubmittedLead, setHasSubmittedLead] = useState(false);
  const [capturedLead, setCapturedLead] = useState<LeadSummary | null>(null);
  const [bookingPanelOpen, setBookingPanelOpen] = useState(false);
  const [confirmedBooking, setConfirmedBooking] = useState<BookingSummary | null>(null);
  const [chatbotSettings, setChatbotSettings] = useState<ChatbotSettingsResponse | null>(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [workspaceDocuments, setWorkspaceDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [documentFilterOpen, setDocumentFilterOpen] = useState(false);

  const settings = chatbotSettings
    ? {
        botName: chatbotSettings.identity.bot_name,
        brandColor: chatbotSettings.identity.brand_color_primary,
        brandColorSecondary: chatbotSettings.identity.brand_color_secondary,
        logoUrl: chatbotSettings.identity.logo,
        avatarUrl: chatbotSettings.identity.bot_avatar,
        tagline: chatbotSettings.identity.tagline,
        welcomeMessage: chatbotSettings.identity.welcome_message,
        inputPlaceholder: `Ask ${chatbotSettings.identity.bot_name} a grounded question...`,
        markdownEnabled: chatbotSettings.behavior.markdown_enabled,
        citationsEnabled: chatbotSettings.behavior.citations_enabled,
        confidenceEnabled: chatbotSettings.behavior.confidence_score_enabled,
        handoffEnabled: chatbotSettings.handoff.enabled,
        handoffMessage: chatbotSettings.handoff.custom_message,
      }
    : defaultChatUiSettings;

  const {
    supportedInput,
    supportedOutput,
    voiceError,
    isRecording,
    isProcessingTranscript,
    transcriptPreview,
    setTranscriptPreview,
    applyTranscriptPreview,
    dismissTranscriptPreview,
    startRecording,
    stopRecording,
    speakingMessageId,
    playbackState,
    speakMessage,
    pauseSpeaking,
    resumeSpeaking,
    stopSpeaking,
  } = useVoiceChat({
    workspaceId,
    settings: chatbotSettings?.voice ?? null,
    composerValue,
    setComposerValue,
  });

  useEffect(() => {
    setThemeMode(getInitialThemeMode());
    setHiddenSessionIds(getStoredJson<string[]>(HIDDEN_SESSIONS_KEY, []));
    setTitleOverrides(getStoredJson<Record<string, string>>(SESSION_TITLE_OVERRIDES_KEY, {}));
  }, []);

  useEffect(() => {
    if (!workspaceId) {
      setWorkspaceDocuments([]);
      setSelectedDocumentIds([]);
      return;
    }

    const currentWorkspaceId = workspaceId;
    let active = true;

    async function loadWorkspaceDocuments() {
      try {
        const documents = await fetchWorkspaceDocuments(currentWorkspaceId);
        if (!active) {
          return;
        }
        setWorkspaceDocuments(documents);
        setSelectedDocumentIds((current) =>
          current.filter((documentId) => documents.some((document) => document.id === documentId)),
        );
      } catch {
        if (!active) {
          return;
        }
        setWorkspaceDocuments([]);
      }
    }

    void loadWorkspaceDocuments();
    return () => {
      active = false;
    };
  }, [workspaceId]);

  useEffect(() => {
    if (!voiceError) {
      return;
    }
    pushToast({
      title: "Voice feature issue",
      description: voiceError.message,
      tone: "error",
    });
  }, [pushToast, voiceError]);

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      setIsBootstrapping(true);
      setPanelError(null);
      try {
        const me = await fetchCurrentUser();
        if (!active) {
          return;
        }
        setUser(me);
        const primaryWorkspace = me.memberships[0];
        if (!primaryWorkspace) {
          throw new Error("No workspace membership was found for this account.");
        }
        setWorkspaceId(primaryWorkspace.workspace_id);
        const [leadCaptureSettings, botSettings] = await Promise.all([
          fetchLeadCaptureSettings(primaryWorkspace.workspace_id),
          fetchChatbotSettings(primaryWorkspace.workspace_id),
        ]);
        if (!active) {
          return;
        }
        setLeadSettings(leadCaptureSettings);
        setChatbotSettings(botSettings);
        setMode(
          botSettings.behavior.response_style === "bullet_points"
            ? "bullet"
            : botSettings.behavior.response_style === "paragraph"
              ? "concise"
              : "detailed",
        );
        const loadedSessions = await listChatSessions(primaryWorkspace.workspace_id);
        if (!active) {
          return;
        }
        setSessions(loadedSessions);
        if (loadedSessions.length) {
          setActiveSessionId((current) => current ?? loadedSessions[0].id);
        }
      } catch (error) {
        if (!active) {
          return;
        }
        setPanelError(error instanceof Error ? error.message : "Chat workspace could not be loaded.");
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
    if (!activeSessionId || messagesBySession[activeSessionId]) {
      return;
    }
    const sessionId: string = activeSessionId;
    let active = true;

    async function loadHistory() {
      setIsLoadingHistory(true);
      setPanelError(null);
      try {
        const history = await fetchChatHistory(sessionId);
        if (!active) {
          return;
        }
        setMessagesBySession((current) => ({
          ...current,
          [sessionId]: normalizeHistoryMessages(history.messages),
        }));
      } catch (error) {
        if (!active) {
          return;
        }
        setPanelError(error instanceof Error ? error.message : "Chat history could not be loaded.");
      } finally {
        if (active) {
          setIsLoadingHistory(false);
        }
      }
    }

    void loadHistory();
    return () => {
      active = false;
    };
  }, [activeSessionId, messagesBySession]);

  const visibleSessions = useMemo(
    () => applyTitleOverrides(sessions, titleOverrides, hiddenSessionIds),
    [hiddenSessionIds, sessions, titleOverrides],
  );
  const activeMessages = activeSessionId ? messagesBySession[activeSessionId] ?? [] : [];
  const activeSession = visibleSessions.find((session) => session.id === activeSessionId) ?? null;
  const selectedDocuments = useMemo(
    () => workspaceDocuments.filter((document) => selectedDocumentIds.includes(document.id)),
    [selectedDocumentIds, workspaceDocuments],
  );
  const activeChatFilters: ChatRetrievalFilters | undefined =
    selectedDocumentIds.length > 0 ? { documentIds: selectedDocumentIds } : undefined;

  function updateTheme(nextTheme: ChatThemeMode) {
    setThemeMode(nextTheme);
    window.localStorage.setItem(CHAT_THEME_STORAGE_KEY, nextTheme);
  }

  function toggleDocumentSelection(documentId: string) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((id) => id !== documentId)
        : [...current, documentId],
    );
  }

  async function refreshSessions(targetSessionId?: string) {
    if (!workspaceId) {
      return;
    }
    const latest = await listChatSessions(workspaceId);
    setSessions(latest);
    if (targetSessionId && latest.some((session) => session.id === targetSessionId)) {
      setActiveSessionId(targetSessionId);
    }
  }

  async function handleNewChat() {
    if (!workspaceId) {
      return;
    }
    try {
      const created = await createChatSession(workspaceId);
      setSessions((current) => [created, ...current]);
      setActiveSessionId(created.id);
      setMessagesBySession((current) => ({ ...current, [created.id]: [] }));
      setComposerValue("");
      setMobileSidebarOpen(false);
      pushToast({
        title: "New chat ready",
        description: "A fresh RAG session has been created for this workspace.",
        tone: "success",
      });
    } catch (error) {
      pushToast({
        title: "New chat could not be created",
        description: error instanceof Error ? error.message : "Please try again.",
        tone: "error",
      });
    }
  }

  async function ensureActiveSession(): Promise<string | null> {
    if (activeSessionId) {
      return activeSessionId;
    }
    if (!workspaceId) {
      return null;
    }
    const created = await createChatSession(workspaceId, composerValue.trim().slice(0, 80));
    setSessions((current) => [created, ...current]);
    setActiveSessionId(created.id);
    setMessagesBySession((current) => ({ ...current, [created.id]: [] }));
    return created.id;
  }

  async function handleSend() {
    const trimmed = composerValue.trim();
    if (!trimmed || isGenerating) {
      return;
    }

    if (!activeSessionId && leadSettings?.force_lead_before_chat && !hasSubmittedLead) {
      setLeadPrompt({
        should_prompt: true,
        trigger: "force_before_chat",
        message:
          leadSettings.auto_response_message ??
          "Before we begin, please share a couple of details so the right teammate can help.",
        schedule_call_enabled: leadSettings.schedule_call_enabled,
        high_intent: false,
        scheduling_intent_detected: false,
      });
      setLeadModalOpen(true);
      return;
    }

    const sessionId = await ensureActiveSession();
    if (!sessionId) {
      return;
    }

    const optimisticUser: UiMessage = {
      id: `local-user-${crypto.randomUUID()}`,
      role: "user",
      content: trimmed,
      citations: [],
      createdAt: new Date().toISOString(),
    };
    const optimisticAssistantId = `local-assistant-${crypto.randomUUID()}`;
    const optimisticAssistant: UiMessage = {
      id: optimisticAssistantId,
      role: "assistant",
      content: "",
      citations: [],
      createdAt: new Date().toISOString(),
      isStreaming: true,
      relatedQuery: trimmed,
    };

    setComposerValue("");
    setIsGenerating(true);
    setIsStopping(false);
    setPanelError(null);
    setMessagesBySession((current) => ({
      ...current,
      [sessionId]: [...(current[sessionId] ?? []), optimisticUser, optimisticAssistant],
    }));

    try {
      await streamChatMessage(
        { sessionId, message: trimmed, mode, filters: activeChatFilters },
        {
          onStart: ({ generation_id, message_id }) => {
            setCurrentGenerationId(generation_id);
          },
          onToken: (delta) => {
            startTransition(() => {
              setMessagesBySession((current) => ({
                ...current,
                [sessionId]: (current[sessionId] ?? []).map((message) =>
                  message.id === optimisticAssistantId
                    ? { ...message, content: `${message.content}${delta}`, isStreaming: true }
                    : message,
                ),
              }));
            });
          },
          onComplete: (result) => {
            setMessagesBySession((current) => ({
              ...current,
              [sessionId]: (current[sessionId] ?? []).map((message) =>
                message.id === optimisticAssistantId
                  ? {
                      ...message,
                      id: result.metadata.message_id ?? message.id,
                      content: result.answer,
                      citations: result.citations,
                      confidence: result.confidence,
                      isStreaming: false,
                      relatedQuery: trimmed,
                    }
                  : message,
              ),
            }));
            if (result.metadata.lead_capture?.should_prompt) {
              setLeadPrompt(result.metadata.lead_capture);
            }
            if (
              chatbotSettings?.voice.voice_output_enabled &&
              chatbotSettings.voice.auto_read_assistant_responses &&
              result.metadata.message_id
            ) {
              void speakMessage(result.metadata.message_id, result.answer);
            }
          },
        },
      );
      await refreshSessions(sessionId);
    } catch (error) {
      const description = error instanceof Error ? error.message : "Streaming failed.";
      setPanelError(description);
      setMessagesBySession((current) => ({
        ...current,
        [sessionId]: (current[sessionId] ?? []).map((message) =>
          message.id === optimisticAssistantId
            ? {
                ...message,
                isStreaming: false,
                isError: true,
                content:
                  message.content ||
                  "The assistant could not complete this response. Please try again or regenerate the answer.",
              }
            : message,
        ),
      }));
      pushToast({
        title: "Streaming interrupted",
        description,
        tone: "error",
      });
    } finally {
      setIsGenerating(false);
      setIsStopping(false);
      setCurrentGenerationId(null);
    }
  }

  async function handleStop() {
    if (!activeSessionId || !isGenerating || isStopping) {
      return;
    }
    setIsStopping(true);
    try {
      await stopChatGeneration(activeSessionId, currentGenerationId);
      pushToast({
        title: "Generation stopping",
        description: "The assistant has been asked to stop after the current token window.",
        tone: "info",
      });
    } catch (error) {
      pushToast({
        title: "Stop request failed",
        description: error instanceof Error ? error.message : "Please try again.",
        tone: "error",
      });
      setIsStopping(false);
    }
  }

  async function handleRegenerate() {
    if (!activeSessionId || isGenerating) {
      return;
    }
    setIsGenerating(true);
    try {
      const result = await regenerateChatResponse(activeSessionId, mode, activeChatFilters);
      setMessagesBySession((current) => {
        const sessionMessages = [...(current[activeSessionId] ?? [])];
        for (let index = sessionMessages.length - 1; index >= 0; index -= 1) {
          if (sessionMessages[index]?.role === "assistant") {
            const lastUser = [...sessionMessages]
              .slice(0, index)
              .reverse()
              .find((message) => message.role === "user");
            sessionMessages[index] = {
              ...sessionMessages[index],
              id: result.metadata.message_id ?? sessionMessages[index].id,
              content: result.answer,
              citations: result.citations,
              confidence: result.confidence,
              relatedQuery: lastUser?.content ?? sessionMessages[index].relatedQuery,
            };
            break;
          }
        }
        return { ...current, [activeSessionId]: sessionMessages };
      });
      if (result.metadata.lead_capture?.should_prompt) {
        setLeadPrompt(result.metadata.lead_capture);
      }
      if (
        chatbotSettings?.voice.voice_output_enabled &&
        chatbotSettings.voice.auto_read_assistant_responses &&
        result.metadata.message_id
      ) {
        void speakMessage(result.metadata.message_id, result.answer);
      }
      pushToast({
        title: "Answer regenerated",
        description: "The last assistant response was refreshed with a new retrieval run.",
        tone: "success",
      });
    } catch (error) {
      pushToast({
        title: "Regeneration failed",
        description: error instanceof Error ? error.message : "Please try again.",
        tone: "error",
      });
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleFeedback(messageId: string, value: FeedbackValue) {
    if (!activeSessionId) {
      return;
    }
    await submitChatFeedback(activeSessionId, messageId, value);
    setMessagesBySession((current) => ({
      ...current,
      [activeSessionId]: (current[activeSessionId] ?? []).map((message) =>
        message.id === messageId ? { ...message, feedback: value } : message,
      ),
    }));
    pushToast({
      title: value === "up" ? "Feedback recorded" : "Feedback captured",
      description:
        value === "up"
          ? "Thanks. This response will count as helpful."
          : "Thanks. This response will be reviewed for grounding quality.",
      tone: "success",
    });
  }

  function handleCopy(message: UiMessage) {
    void navigator.clipboard.writeText(message.content);
    pushToast({
      title: "Response copied",
      description: "The assistant reply is now on your clipboard.",
      tone: "success",
    });
  }

  function handleDownload(message: UiMessage) {
    downloadResponseAsMarkdown(activeSession?.title ?? "chat-response", message.content);
    pushToast({
      title: "Response downloaded",
      description: "The answer has been exported as a markdown file.",
      tone: "success",
    });
  }

  function handleRenameSession(sessionId: string, title: string) {
    const next = { ...titleOverrides, [sessionId]: title };
    setTitleOverrides(next);
    persistJson(SESSION_TITLE_OVERRIDES_KEY, next);
    setSessions((current) =>
      current.map((session) => (session.id === sessionId ? { ...session, title } : session)),
    );
    pushToast({
      title: "Session renamed",
      description: "The new title is stored locally for this dashboard.",
      tone: "success",
    });
  }

  function handleDeleteSession(sessionId: string) {
    const next = [...new Set([...hiddenSessionIds, sessionId])];
    setHiddenSessionIds(next);
    persistJson(HIDDEN_SESSIONS_KEY, next);
    if (activeSessionId === sessionId) {
      const remaining = visibleSessions.filter((session) => session.id !== sessionId);
      setActiveSessionId(remaining[0]?.id ?? null);
    }
    pushToast({
      title: "Session removed from view",
      description: "This is a local UI hide until chat delete APIs are added on the backend.",
      tone: "info",
    });
  }

  function handleClearChat() {
    void handleNewChat();
  }

  async function handleOpenHumanHandoff() {
    if (!workspaceId || !activeSessionId) {
      return;
    }
    try {
      const response = await requestHumanHandoff({
        workspaceId,
        sessionId: activeSessionId,
        reason: "manual_handoff",
        message: activeMessages.filter((message) => message.role === "user").at(-1)?.content,
      });
      setLeadPrompt(response.lead_prompt);
      setLeadModalOpen(true);
      await refreshSessions(activeSessionId);
      pushToast({
        title: "Human handoff started",
        description: response.message,
        tone: "info",
      });
    } catch (error) {
      pushToast({
        title: "Could not request handoff",
        description: error instanceof Error ? error.message : "Please try again.",
        tone: "error",
      });
    }
  }

  async function handleSubmitLead(payload: {
    name: string;
    email: string;
    phone: string;
    company: string;
    useCase: string;
    message: string;
    scheduleCallRequested: boolean;
  }) {
    if (!workspaceId) {
      throw new Error("Workspace is not available.");
    }
    const response = await captureLead({
      workspaceId,
      chatSessionId: activeSessionId,
      name: payload.name,
      email: payload.email,
      phone: payload.phone,
      company: payload.company,
      useCase: payload.useCase,
      message: payload.message,
      scheduleCallRequested: payload.scheduleCallRequested,
    });
    setHasSubmittedLead(true);
    setCapturedLead(response.lead);
    if (payload.scheduleCallRequested || leadPrompt?.scheduling_intent_detected) {
      setBookingPanelOpen(true);
    }
    pushToast({
      title: "Lead captured",
      description:
        response.message ||
        leadSettings?.auto_response_message ||
        "A teammate will follow up without interrupting the rest of your chat.",
      tone: "success",
    });
    if (activeSessionId) {
      await refreshSessions(activeSessionId);
    }
  }

  const rootPanelClass =
    themeMode === "dark"
      ? "border-white/10 bg-[linear-gradient(180deg,rgba(8,14,30,0.94),rgba(2,6,23,0.96))] text-slate-100"
      : "border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.98))] text-slate-950 shadow-[0_28px_90px_rgba(148,163,184,0.18)]";

  return (
    <main
      className="rounded-[2.25rem] border"
      style={{ "--chat-brand": settings.brandColor } as CSSProperties}
    >
      <div className={`grid min-h-[78vh] overflow-hidden rounded-[2.25rem] ${rootPanelClass} md:grid-cols-[auto_1fr]`}>
        <Sidebar
          activeSessionId={activeSessionId}
          botName={settings.botName}
          collapsed={collapsedSidebar}
          mobileOpen={mobileSidebarOpen}
          onCloseMobile={() => setMobileSidebarOpen(false)}
          onDeleteSession={handleDeleteSession}
          onNewChat={() => void handleNewChat()}
          onRenameSession={handleRenameSession}
          onSelectSession={(sessionId) => {
            startTransition(() => {
              setActiveSessionId(sessionId);
              setPanelError(null);
            });
          }}
          onToggleCollapse={() => setCollapsedSidebar((current) => !current)}
          sessions={visibleSessions}
          themeMode={themeMode}
        />

        <section className="flex min-w-0 flex-col">
          <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 px-4 py-4 md:px-6">
            <div className="flex items-center gap-3">
              <button
                aria-label="Open chat history sidebar"
                className="inline-flex rounded-2xl border border-white/10 px-3 py-2 text-slate-300 transition hover:border-white/20 hover:text-white md:hidden"
                onClick={() => setMobileSidebarOpen(true)}
                type="button"
              >
                Menu
              </button>
              <div>
                <p className="text-xs uppercase tracking-[0.35em] text-slate-400">Grounded chat</p>
                <h1 className="text-2xl font-semibold tracking-tight text-inherit">
                  {activeSession?.title ?? "New conversation"}
                </h1>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <button
                  className="inline-flex max-w-[18rem] items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2 text-left text-sm text-slate-300 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
                  onClick={() => setDocumentFilterOpen((current) => !current)}
                  type="button"
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="text-[0.62rem] uppercase tracking-[0.28em] text-slate-500">Chat scope</span>
                    <span className="truncate text-sm text-slate-100">
                      {selectedDocumentIds.length === 0
                        ? "All documents"
                        : selectedDocumentIds.length === 1
                          ? selectedDocuments[0]?.title ?? "1 document"
                          : `${selectedDocumentIds.length} documents selected`}
                    </span>
                  </span>
                  <span
                    aria-hidden="true"
                    className={`text-xs text-slate-400 transition ${documentFilterOpen ? "rotate-180" : ""}`}
                  >
                    v
                  </span>
                </button>
                {documentFilterOpen ? (
                  <div className="absolute left-0 top-full z-20 mt-2 w-[20rem] rounded-3xl border border-white/10 bg-slate-950/95 p-3 shadow-2xl backdrop-blur">
                    <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-3">
                      <p className="text-sm font-medium text-white">Chat scope</p>
                      <button
                        className="text-xs text-cyan-200/80 transition hover:text-white"
                        onClick={() => setSelectedDocumentIds([])}
                        type="button"
                      >
                        Reset
                      </button>
                    </div>
                    <button
                      className={`mt-3 flex w-full items-center justify-between rounded-2xl border px-3 py-2 text-left text-sm transition ${
                        selectedDocumentIds.length === 0
                          ? "border-cyan-300/30 bg-cyan-400/10 text-cyan-50"
                          : "border-white/10 text-slate-200 hover:border-white/20"
                      }`}
                      onClick={() => setSelectedDocumentIds([])}
                      type="button"
                    >
                      <span>All documents</span>
                      {selectedDocumentIds.length === 0 ? (
                        <span className="text-xs uppercase tracking-[0.24em] text-cyan-200/80">Active</span>
                      ) : null}
                    </button>
                    <div className="mt-3 max-h-72 space-y-2 overflow-y-auto">
                      {workspaceDocuments.length ? (
                        workspaceDocuments.map((document) => {
                          const checked = selectedDocumentIds.includes(document.id);
                          return (
                            <label
                              key={document.id}
                              className="flex cursor-pointer items-start gap-3 rounded-2xl border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-white/20"
                            >
                              <input
                                checked={checked}
                                className="mt-1 h-4 w-4 rounded border-white/20 bg-transparent text-cyan-400 focus:ring-cyan-400"
                                onChange={() => toggleDocumentSelection(document.id)}
                                type="checkbox"
                              />
                              <span className="min-w-0">
                                <span className="block break-words">{document.title}</span>
                                <span className="mt-1 block text-xs text-slate-500">
                                  {document.chunk_count} chunks
                                </span>
                              </span>
                            </label>
                          );
                        })
                      ) : (
                        <p className="rounded-2xl border border-white/10 px-3 py-3 text-sm text-slate-400">
                          No indexed documents are available yet.
                        </p>
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
              <button
                className="rounded-full border border-white/10 px-3 py-2 text-sm text-slate-300 transition hover:border-white/20 hover:text-white"
                onClick={handleClearChat}
                type="button"
              >
                Clear chat
              </button>
              {settings.handoffEnabled ? (
                <button
                  className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-3 py-2 text-sm text-cyan-100 transition hover:border-cyan-300/40 hover:bg-cyan-400/15"
                  onClick={() => void handleOpenHumanHandoff()}
                  type="button"
                >
                  Talk to human
                </button>
              ) : null}
              <button
                className="rounded-full border border-white/10 px-3 py-2 text-sm text-slate-300 transition hover:border-white/20 hover:text-white"
                onClick={() => setExportModalOpen(true)}
                type="button"
              >
                Export chats
              </button>
              <button
                className="rounded-full border border-white/10 px-3 py-2 text-sm text-slate-300 transition hover:border-white/20 hover:text-white"
                onClick={() => updateTheme(themeMode === "dark" ? "light" : "dark")}
                type="button"
              >
                {themeMode === "dark" ? "Light mode" : "Dark mode"}
              </button>
              <div className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-300">
                {user?.memberships[0]?.workspace_name ?? "Workspace"}
              </div>
            </div>
          </header>

          <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 md:p-6">
            {isBootstrapping ? (
              <div className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-slate-400">
                Preparing your chat workspace...
              </div>
            ) : null}
            {selectedDocuments.length ? (
              <section className="rounded-[1.6rem] border border-cyan-400/15 bg-cyan-400/10 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-medium uppercase tracking-[0.3em] text-cyan-100/70">
                    Active document filters
                  </span>
                  {selectedDocuments.map((document) => (
                    <button
                      key={document.id}
                      className="inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-400/10 px-3 py-1 text-sm text-cyan-50 transition hover:border-cyan-200/40 hover:bg-cyan-400/15"
                      onClick={() => toggleDocumentSelection(document.id)}
                      type="button"
                    >
                      <span className="max-w-[18rem] truncate">{document.title}</span>
                      <span className="text-cyan-200/70">x</span>
                    </button>
                  ))}
                  <button
                    className="text-sm text-cyan-200/80 transition hover:text-white"
                    onClick={() => setSelectedDocumentIds([])}
                    type="button"
                  >
                    Clear
                  </button>
                </div>
              </section>
            ) : null}
            <>
                <ChatWindow
                  botName={settings.botName}
                  errorMessage={panelError}
                  avatarUrl={settings.avatarUrl}
                  isError={Boolean(panelError && !activeMessages.length && !isGenerating && !isBootstrapping)}
                  isGenerating={isGenerating}
                  isLoadingHistory={isLoadingHistory || isBootstrapping}
                  logoUrl={settings.logoUrl}
                  markdownEnabled={settings.markdownEnabled}
                  messages={activeMessages}
                  onCopy={handleCopy}
                  onDownload={handleDownload}
                  onFeedback={handleFeedback}
                  onPauseSpeech={pauseSpeaking}
                  onRegenerate={() => void handleRegenerate()}
                  onResumeSpeech={resumeSpeaking}
                  onSpeak={(message) => void speakMessage(message.id, message.content)}
                  onStopSpeech={stopSpeaking}
                  playbackState={playbackState}
                  onRetry={() => {
                    if (activeSessionId) {
                      setMessagesBySession((current) => {
                        const next = { ...current };
                        delete next[activeSessionId];
                        return next;
                      });
                    }
                    setPanelError(null);
                  }}
                  showCitations={settings.citationsEnabled}
                  showConfidence={settings.confidenceEnabled}
                  speakingMessageId={speakingMessageId}
                  tagline={settings.tagline}
                  themeMode={themeMode}
                  voiceOutputEnabled={Boolean(chatbotSettings?.voice.voice_output_enabled)}
                  voiceOutputSupported={supportedOutput}
                  welcomeMessage={settings.welcomeMessage}
                />
                {leadPrompt?.should_prompt ? (
                  <section className="rounded-[1.6rem] border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm text-cyan-50">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <div>
                        <p className="font-medium">
                          {leadPrompt.message ?? "Would you like a human expert to contact you?"}
                        </p>
                        <p className="mt-1 text-cyan-100/80">
                          We surface this only when the conversation shows real follow-up intent.
                        </p>
                      </div>
                      <button
                        className="rounded-full bg-white px-4 py-2 font-medium text-slate-950"
                        onClick={() => setLeadModalOpen(true)}
                        type="button"
                      >
                        Share details
                      </button>
                    </div>
                  </section>
                ) : null}
                {bookingPanelOpen && workspaceId ? (
                  <BookingScheduler
                    chatSessionId={activeSessionId}
                    leadId={capturedLead?.id ?? null}
                    title="Schedule a call from chat"
                    visitor={{
                      name: capturedLead?.name ?? "",
                      email: capturedLead?.email ?? "",
                      phone: capturedLead?.phone ?? "",
                    }}
                    workspaceId={workspaceId}
                    onBooked={(booking) => {
                      setConfirmedBooking(booking);
                      setBookingPanelOpen(false);
                      setMessagesBySession((current) => {
                        if (!activeSessionId) {
                          return current;
                        }
                        return {
                          ...current,
                          [activeSessionId]: [
                            ...(current[activeSessionId] ?? []),
                            {
                              id: `booking-${booking.id}`,
                              role: "assistant",
                              content: `Your ${booking.meeting_type_title} is confirmed for ${new Date(booking.start_time_utc).toLocaleString()}.\nMeeting link: ${booking.meeting_link ?? "We will share the meeting details shortly."}`,
                              citations: [],
                              createdAt: new Date().toISOString(),
                            },
                          ],
                        };
                      });
                    }}
                  />
                ) : null}
                {confirmedBooking ? (
                  <section className="rounded-[1.6rem] border border-emerald-300/20 bg-emerald-400/10 p-4 text-sm text-emerald-50">
                    <p className="font-medium">Booking confirmed</p>
                    <p className="mt-2">
                      {confirmedBooking.meeting_type_title} · {new Date(confirmedBooking.start_time_utc).toLocaleString()}
                    </p>
                    <p className="mt-2 break-all text-emerald-100/85">
                      {confirmedBooking.meeting_link ?? "Meeting details will be shared by email."}
                    </p>
                  </section>
                ) : null}
                <ChatInput
                  disabled={!workspaceId || isStopping}
                  isGenerating={isGenerating}
                  isProcessingTranscript={isProcessingTranscript}
                  isRecording={isRecording}
                  mode={mode}
                  onApplyTranscriptPreview={applyTranscriptPreview}
                  onChange={setComposerValue}
                  onDismissTranscriptPreview={dismissTranscriptPreview}
                  onModeChange={setMode}
                  onSend={() => void handleSend()}
                  onStartRecording={() => void startRecording()}
                  onStop={() => void handleStop()}
                  onStopRecording={() => void stopRecording()}
                  onTranscriptPreviewChange={setTranscriptPreview}
                  placeholder={settings.inputPlaceholder}
                  themeMode={themeMode}
                  transcriptPreview={transcriptPreview}
                  value={composerValue}
                  voiceError={voiceError?.message ?? null}
                  voiceInputEnabled={Boolean(chatbotSettings?.voice.voice_input_enabled)}
                  voiceInputSupported={supportedInput}
                />
            </>
          </div>
        </section>
      </div>
      <LeadCaptureModal
        defaultMessage={activeMessages.filter((message) => message.role === "user").at(-1)?.content ?? ""}
        onClose={() => setLeadModalOpen(false)}
        onSubmit={handleSubmitLead}
        open={leadModalOpen}
        requiredFields={leadSettings?.required_fields ?? ["name", "email"]}
        scheduleCallEnabled={leadPrompt?.schedule_call_enabled ?? false}
      />
      <ExportModal
        open={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        exportType="chat"
        workspaceId={workspaceId ?? ""}
        title="Export chat history"
        description="Queue a background export for full chat history, selected sessions, or a filtered workspace slice."
        initialFilters={{
          sessionIds: activeSessionId ? [activeSessionId] : [],
        }}
        sessionOptions={visibleSessions.map((session) => ({
          id: session.id,
          title: session.title,
          startedAt: session.started_at,
        }))}
      />
    </main>
  );
}
