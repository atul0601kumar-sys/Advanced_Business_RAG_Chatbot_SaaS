import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChatInput } from "@/components/chat/ChatInput";

vi.mock("@/lib/chat", async () => {
  const actual = await vi.importActual<typeof import("@/lib/chat")>("@/lib/chat");
  return {
    ...actual,
    estimateTokens: (text: string) => Math.ceil(text.length / 4),
  };
});

test("supports keyboard submission and stop generation controls", async () => {
  const user = userEvent.setup();
  const onSend = vi.fn();
  const onStop = vi.fn();

  render(
    <ChatInput
      mode="detailed"
      onChange={vi.fn()}
      onModeChange={vi.fn()}
      onSend={onSend}
      onStop={onStop}
      placeholder="Ask grounded questions"
      themeMode="dark"
      value="How did revenue change?"
      isGenerating
    />,
  );

  await user.click(screen.getByLabelText("Chat message input"));
  await user.keyboard("{Enter}");
  expect(onSend).toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Stop generating response" }));
  expect(onStop).toHaveBeenCalled();
});
