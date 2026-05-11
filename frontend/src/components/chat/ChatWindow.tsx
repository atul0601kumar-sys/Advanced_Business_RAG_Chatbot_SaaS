"use client";

import { memo, useEffect, useRef } from "react";

import { LoadingIndicator } from "@/components/chat/LoadingIndicator";
import { MessageBubble, type UiMessage } from "@/components/chat/MessageBubble";
import type { FeedbackValue } from "@/lib/chat";
import type { PlaybackState } from "@/lib/voice/utils";

type ChatWindowProps = {
  messages: UiMessage[];
  isLoadingHistory: boolean;
  isGenerating: boolean;
  isError: boolean;
  errorMessage: string | null;
  welcomeMessage: string;
  botName: string;
  logoUrl: string | null;
  avatarUrl: string | null;
  tagline: string | null;
  themeMode: "dark" | "light";
  markdownEnabled: boolean;
  showCitations: boolean;
  showConfidence: boolean;
  onRetry: () => void;
  onCopy: (message: UiMessage) => void;
  onDownload: (message: UiMessage) => void;
  onRegenerate: () => void;
  onFeedback: (messageId: string, value: FeedbackValue) => Promise<void>;
  voiceOutputEnabled: boolean;
  voiceOutputSupported: boolean;
  speakingMessageId: string | null;
  playbackState: PlaybackState;
  onSpeak: (message: UiMessage) => void;
  onPauseSpeech: () => void;
  onResumeSpeech: () => void;
  onStopSpeech: () => void;
};

function ChatWindowComponent({
  messages,
  isLoadingHistory,
  isGenerating,
  isError,
  errorMessage,
  welcomeMessage,
  botName,
  logoUrl,
  avatarUrl,
  tagline,
  themeMode,
  markdownEnabled,
  showCitations,
  showConfidence,
  onRetry,
  onCopy,
  onDownload,
  onRegenerate,
  onFeedback,
  voiceOutputEnabled,
  voiceOutputSupported,
  speakingMessageId,
  playbackState,
  onSpeak,
  onPauseSpeech,
  onResumeSpeech,
  onStopSpeech,
}: ChatWindowProps) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isGenerating]);

  if (isLoadingHistory) {
    return (
      <section className="flex flex-1 flex-col gap-6 overflow-y-auto rounded-[2rem] border border-white/10 bg-white/[0.04] p-6">
        <LoadingIndicator variant="skeleton" />
        <LoadingIndicator variant="skeleton" />
        <LoadingIndicator variant="skeleton" />
      </section>
    );
  }

  if (isError) {
    return (
      <section className="flex flex-1 items-center justify-center rounded-[2rem] border border-rose-400/20 bg-rose-500/10 p-6">
        <div className="max-w-lg text-center">
          <p className="text-xs uppercase tracking-[0.35em] text-rose-200/80">Chat unavailable</p>
          <h2 className="mt-3 text-3xl font-semibold text-white">The conversation could not be loaded</h2>
          <p className="mt-3 text-sm text-slate-300">
            {errorMessage ?? "The assistant could not reach the backend or load the selected session."}
          </p>
          <button
            className="mt-6 rounded-full bg-[var(--chat-brand)] px-5 py-3 text-sm font-semibold text-white"
            onClick={onRetry}
            type="button"
          >
            Retry
          </button>
        </div>
      </section>
    );
  }

  if (!messages.length) {
    return (
      <section
        className={`flex flex-1 items-center justify-center rounded-[2rem] border p-8 ${
          themeMode === "dark"
            ? "border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.14),transparent_34%),linear-gradient(160deg,rgba(15,23,42,0.92),rgba(2,6,23,0.95))]"
            : "border-slate-200 bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.09),transparent_34%),linear-gradient(160deg,rgba(255,255,255,0.95),rgba(248,250,252,0.98))]"
        }`}
      >
        <div className="max-w-2xl space-y-4 text-center">
          <p className="text-xs uppercase tracking-[0.35em] text-slate-400">Grounded assistant</p>
          <h2 className={`text-4xl font-semibold tracking-tight ${themeMode === "dark" ? "text-white" : "text-slate-950"}`}>
            {botName}
          </h2>
          {tagline ? (
            <p className={`text-sm uppercase tracking-[0.28em] ${themeMode === "dark" ? "text-cyan-200/75" : "text-sky-700/80"}`}>
              {tagline}
            </p>
          ) : null}
          <p className={`text-base leading-7 ${themeMode === "dark" ? "text-slate-300" : "text-slate-600"}`}>
            {welcomeMessage}
          </p>
          <div className="grid gap-3 pt-4 text-left md:grid-cols-3">
            {[
              "Summarize the latest revenue signals with citations.",
              "What changed in customer onboarding this quarter?",
              "Which documents mention churn reduction programs?",
            ].map((prompt) => (
              <div
                key={prompt}
                className={`rounded-3xl border p-4 text-sm ${
                  themeMode === "dark"
                    ? "border-white/10 bg-white/[0.04] text-slate-200"
                    : "border-slate-200 bg-white text-slate-700 shadow-sm"
                }`}
              >
                {prompt}
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section
      aria-label="Chat messages"
      className={`flex flex-1 flex-col overflow-y-auto rounded-[2rem] border border-white/10 p-4 md:p-6 ${
        themeMode === "dark" ? "bg-white/[0.04]" : "bg-white/80"
      }`}
    >
      <div className="space-y-6">
        {messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            botName={botName}
            canRegenerate={message.role === "assistant" && index === messages.length - 1}
            logoUrl={logoUrl}
            avatarUrl={avatarUrl}
            markdownEnabled={markdownEnabled}
            message={message}
            onCopy={onCopy}
            onDownload={onDownload}
            onFeedback={onFeedback}
            onRegenerate={onRegenerate}
            onPauseSpeech={onPauseSpeech}
            onResumeSpeech={onResumeSpeech}
            onSpeak={onSpeak}
            onStopSpeech={onStopSpeech}
            playbackState={playbackState}
            showCitations={showCitations}
            showConfidence={showConfidence}
            speakingMessageId={speakingMessageId}
            themeMode={themeMode}
            voiceOutputEnabled={voiceOutputEnabled}
            voiceOutputSupported={voiceOutputSupported}
          />
        ))}
        {isGenerating ? <LoadingIndicator /> : null}
        <div ref={endRef} />
      </div>
    </section>
  );
}

export const ChatWindow = memo(ChatWindowComponent);
