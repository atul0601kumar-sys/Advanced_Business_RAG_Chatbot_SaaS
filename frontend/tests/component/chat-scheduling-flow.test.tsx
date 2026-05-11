import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ToastProvider } from "@/components/toast-provider";
import { ChatLayout } from "@/components/chat/ChatLayout";

const {
  captureLead,
  requestHumanHandoff,
  listMeetingTypes,
  fetchBookingSlots,
} = vi.hoisted(() => ({
  captureLead: vi.fn(),
  requestHumanHandoff: vi.fn(),
  listMeetingTypes: vi.fn(),
  fetchBookingSlots: vi.fn(),
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
  streamChatMessage: vi.fn(),
  regenerateChatResponse: vi.fn(),
  stopChatGeneration: vi.fn(),
  submitChatFeedback: vi.fn().mockResolvedValue(undefined),
  captureLead,
  requestHumanHandoff,
  downloadResponseAsMarkdown: vi.fn(),
  estimateTokens: (text: string) => Math.max(1, Math.ceil(text.length / 4)),
}));

vi.mock("@/lib/scheduling", () => ({
  listMeetingTypes,
  fetchBookingSlots,
  createBooking: vi.fn(),
  rescheduleBooking: vi.fn(),
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

test("opens the booking scheduler after lead capture requests a scheduled call", async () => {
  captureLead.mockResolvedValue({
    message: "Lead captured",
    lead: {
      id: "lead-1",
      name: "Jordan Buyer",
      email: "jordan@example.com",
      phone: "+15555550101",
    },
  });
  requestHumanHandoff.mockResolvedValue({
    message: "A teammate can take over from here.",
    lead_prompt: {
      should_prompt: true,
      message: "Share your details for a callback.",
      schedule_call_enabled: true,
      scheduling_intent_detected: true,
    },
  });
  listMeetingTypes.mockResolvedValue({
    items: [
      {
        id: "meeting-1",
        workspace_id: "workspace-1",
        title: "Sales Demo",
        slug: "sales-demo",
        description: "Walk through the platform.",
        duration_minutes: 30,
        location_type: "manual",
        assigned_user_id: "user-1",
        assignment_mode: "specific",
        provider_preference: "external_link",
        external_location_url: null,
        manual_location_text: "https://meet.example.com/demo",
        booking_link: "http://localhost:3000/book/alpha?meeting=sales-demo",
        availability_rules: null,
        metadata: null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ],
  });
  fetchBookingSlots.mockResolvedValue({
    workspace_id: "workspace-1",
    meeting_type_id: "meeting-1",
    timezone: "UTC",
    slots: [
      {
        start_time_utc: "2026-06-01T09:00:00Z",
        end_time_utc: "2026-06-01T09:30:00Z",
        display_time: "Mon, Jun 1 at 9:00 AM",
        timezone: "UTC",
        provider: "external_link",
        assigned_user_id: "user-1",
      },
    ],
  });

  const user = userEvent.setup();
  render(
    <ToastProvider>
      <ChatLayout />
    </ToastProvider>,
  );

  await screen.findByText("Quarterly Review");
  await user.click(screen.getByRole("button", { name: "Talk to human" }));
  await screen.findByRole("button", { name: "Submit details" });

  await user.type(screen.getByPlaceholderText("Name *"), "Jordan Buyer");
  await user.type(screen.getByPlaceholderText("Email *"), "jordan@example.com");
  await user.click(screen.getByRole("button", { name: "Submit details" }));

  await waitFor(() => expect(captureLead).toHaveBeenCalled());
  await screen.findByText("Schedule a call from chat");
  expect(screen.getByText("Available slots")).toBeInTheDocument();
  expect(screen.getByDisplayValue("Jordan Buyer")).toBeInTheDocument();
  expect(screen.getByDisplayValue("jordan@example.com")).toBeInTheDocument();
});
