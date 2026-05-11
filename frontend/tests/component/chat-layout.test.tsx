import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ToastProvider } from "@/components/toast-provider";
import { ChatLayout } from "@/components/chat/ChatLayout";

const { streamChatMessage } = vi.hoisted(() => ({
  streamChatMessage: vi.fn(async (_payload, handlers) => {
    handlers.onStart?.({ session_id: "session-1", generation_id: "gen-1", message_id: "msg-1" });
    handlers.onToken?.("Revenue ");
    handlers.onToken?.("grew 18 percent.");
    handlers.onComplete?.({
      answer: "Revenue grew 18 percent.",
      citations: [
        {
          file_name: "report.pdf",
          page_number: 2,
          url: null,
          chunk_preview: "Revenue grew 18 percent year over year.",
        },
      ],
      confidence: "High",
      metadata: {
        retrieved_chunks: 2,
        processing_time: 18,
        stopped: false,
        message_id: "msg-1",
        generation_id: "gen-1",
        lead_capture: {
          should_prompt: false,
          trigger: null,
          message: null,
          schedule_call_enabled: false,
          high_intent: false,
        },
      },
    });
  }),
}));

vi.mock("@/lib/chat", () => ({
  fetchCurrentUser: vi.fn().mockResolvedValue({
    id: "user-1",
    full_name: "Owner",
    email: "owner@example.com",
    memberships: [{ workspace_id: "workspace-1", workspace_name: "Alpha Workspace", workspace_slug: "alpha", role: "admin" }],
  }),
  fetchLeadCaptureSettings: vi.fn().mockResolvedValue({
    workspace_id: "workspace-1",
    lead_capture_enabled: true,
    lead_capture_on_first_message: true,
    lead_capture_after_message_count: 2,
    lead_capture_on_low_confidence: true,
    force_lead_before_chat: false,
    required_fields: ["name", "email"],
    schedule_call_enabled: true,
    lead_notifications_enabled: false,
    admin_notification_email: null,
    notification_webhook_url: null,
    auto_response_message: "Thanks, we'll follow up.",
  }),
  listChatSessions: vi.fn().mockResolvedValue([
    {
      id: "session-1",
      workspace_id: "workspace-1",
      user_id: "user-1",
      title: "Quarterly Review",
      status: "active",
      channel: "web",
      started_at: "2026-01-01T00:00:00Z",
      last_message_at: "2026-01-01T00:00:00Z",
      session_summary: null,
      needs_human_review: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      message_count: 0,
    },
  ]),
  fetchChatHistory: vi.fn().mockResolvedValue({
    session: {
      id: "session-1",
      workspace_id: "workspace-1",
      user_id: "user-1",
      title: "Quarterly Review",
      status: "active",
      channel: "web",
      started_at: "2026-01-01T00:00:00Z",
      last_message_at: "2026-01-01T00:00:00Z",
      session_summary: null,
      needs_human_review: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      message_count: 0,
    },
    messages: [],
  }),
  createChatSession: vi.fn().mockResolvedValue({
    id: "session-1",
    workspace_id: "workspace-1",
    user_id: "user-1",
    title: "Quarterly Review",
    status: "active",
    channel: "web",
    started_at: "2026-01-01T00:00:00Z",
    last_message_at: "2026-01-01T00:00:00Z",
    session_summary: null,
    needs_human_review: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    message_count: 0,
  }),
  streamChatMessage,
  regenerateChatResponse: vi.fn(),
  stopChatGeneration: vi.fn(),
  submitChatFeedback: vi.fn().mockResolvedValue(undefined),
  captureLead: vi.fn(),
  requestHumanHandoff: vi.fn(),
  downloadResponseAsMarkdown: vi.fn(),
  estimateTokens: (text: string) => Math.max(1, Math.ceil(text.length / 4)),
}));

vi.mock("@/lib/settings", () => ({
  fetchChatbotSettings: vi.fn().mockResolvedValue({
    identity: {
      bot_name: "Atlas",
      bot_avatar: null,
      brand_color_primary: "#0ea5e9",
      brand_color_secondary: "#0284c7",
      logo: null,
      tagline: "Revenue intelligence",
      welcome_message: "Ask grounded questions.",
    },
    behavior: {
      tone: "professional",
      response_style: "mixed",
      max_response_length: 600,
      markdown_enabled: true,
      citations_enabled: true,
      confidence_score_enabled: true,
    },
    handoff: { enabled: true, custom_message: "Talk to a human", enable_scheduling: true, escalate_on_low_confidence: true, escalate_on_repeated_failures: true },
    voice: {
      voice_input_enabled: false,
      voice_output_enabled: false,
      voice_style: null,
      transcript_preview_enabled: true,
      auto_read_assistant_responses: false,
    },
  }),
}));

vi.mock("@/lib/voice/use-voice-chat", () => ({
  useVoiceChat: () => ({
    supportedInput: false,
    supportedOutput: false,
    voiceError: null,
    isRecording: false,
    isProcessingTranscript: false,
    transcriptPreview: null,
    setTranscriptPreview: vi.fn(),
    applyTranscriptPreview: vi.fn(),
    dismissTranscriptPreview: vi.fn(),
    startRecording: vi.fn(),
    stopRecording: vi.fn(),
    speakingMessageId: null,
    playbackState: "idle",
    speakMessage: vi.fn(),
    pauseSpeaking: vi.fn(),
    resumeSpeaking: vi.fn(),
    stopSpeaking: vi.fn(),
  }),
}));

vi.mock("@/components/chat/Sidebar", () => ({
  Sidebar: ({ sessions, onSelectSession }: any) => (
    <div>
      <button type="button" onClick={() => onSelectSession(sessions[0].id)}>
        Open session
      </button>
    </div>
  ),
}));

vi.mock("@/components/dashboard/export-modal", () => ({
  ExportModal: () => null,
}));

test("sends messages, renders streaming updates, and shows citations", async () => {
  const user = userEvent.setup();
  render(
    <ToastProvider>
      <ChatLayout />
    </ToastProvider>,
  );

  await screen.findByText("Quarterly Review");
  const input = screen.getByLabelText("Chat message input");
  await user.type(input, "How did revenue change?");
  await user.click(screen.getByRole("button", { name: "Send message" }));

  await waitFor(() => expect(streamChatMessage).toHaveBeenCalled());
  await screen.findByText("Revenue grew 18 percent.");
  expect(screen.getByText("report.pdf")).toBeInTheDocument();
});
