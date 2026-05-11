import React from "react";
import { render, screen } from "@testing-library/react";

import { MessageBubble } from "@/components/chat/MessageBubble";

const assistantMessage = {
  id: "msg-1",
  role: "assistant" as const,
  content: "Revenue grew 18 percent year over year.",
  citations: [
    {
      file_name: "quarterly.txt",
      page_number: 1,
      url: null,
      chunk_preview: "Revenue grew 18 percent year over year.",
    },
  ],
  createdAt: "2026-01-01T00:00:00Z",
  confidence: "High" as const,
  feedback: null,
  relatedQuery: "revenue growth",
};

test("renders accessible assistant controls and matches the bubble snapshot", () => {
  const { asFragment } = render(
    <MessageBubble
      avatarUrl={null}
      botName="Atlas"
      canRegenerate
      logoUrl={null}
      markdownEnabled={false}
      message={assistantMessage}
      onCopy={vi.fn()}
      onDownload={vi.fn()}
      onFeedback={vi.fn().mockResolvedValue(undefined)}
      onPauseSpeech={vi.fn()}
      onRegenerate={vi.fn()}
      onResumeSpeech={vi.fn()}
      onSpeak={vi.fn()}
      onStopSpeech={vi.fn()}
      playbackState="idle"
      showCitations
      showConfidence
      speakingMessageId={null}
      themeMode="dark"
      voiceOutputEnabled={false}
      voiceOutputSupported={false}
    />,
  );

  expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Regenerate" })).toBeInTheDocument();
  expect(screen.getByText("quarterly.txt")).toBeInTheDocument();
  expect(asFragment()).toMatchSnapshot();
});
