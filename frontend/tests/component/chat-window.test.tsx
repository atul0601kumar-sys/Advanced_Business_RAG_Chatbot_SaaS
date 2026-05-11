import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChatWindow } from "@/components/chat/ChatWindow";

const baseProps = {
  messages: [],
  isLoadingHistory: false,
  isGenerating: false,
  isError: false,
  errorMessage: null,
  welcomeMessage: "Ask grounded questions about your workspace documents.",
  botName: "Atlas",
  logoUrl: null,
  avatarUrl: null,
  tagline: "Revenue intelligence",
  themeMode: "dark" as const,
  markdownEnabled: true,
  showCitations: true,
  showConfidence: true,
  onRetry: vi.fn(),
  onCopy: vi.fn(),
  onDownload: vi.fn(),
  onRegenerate: vi.fn(),
  onFeedback: vi.fn().mockResolvedValue(undefined),
  voiceOutputEnabled: false,
  voiceOutputSupported: false,
  speakingMessageId: null,
  playbackState: "idle" as const,
  onSpeak: vi.fn(),
  onPauseSpeech: vi.fn(),
  onResumeSpeech: vi.fn(),
  onStopSpeech: vi.fn(),
};

test("renders loading, empty, and error states clearly", async () => {
  const user = userEvent.setup();
  const { rerender } = render(<ChatWindow {...baseProps} isLoadingHistory />);
  expect(document.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0);

  rerender(<ChatWindow {...baseProps} />);
  expect(screen.getByText("Grounded assistant")).toBeInTheDocument();
  expect(screen.getByText("Ask grounded questions about your workspace documents.")).toBeInTheDocument();

  rerender(<ChatWindow {...baseProps} isError errorMessage="Backend is unavailable." />);
  expect(screen.getByText("The conversation could not be loaded")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Retry" }));
  expect(baseProps.onRetry).toHaveBeenCalled();
});
