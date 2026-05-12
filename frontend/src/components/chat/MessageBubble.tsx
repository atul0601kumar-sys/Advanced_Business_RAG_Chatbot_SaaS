"use client";

import { memo } from "react";

import { CitationCard } from "@/components/chat/CitationCard";
import { FeedbackButtons } from "@/components/chat/FeedbackButtons";
import { LoadingIndicator } from "@/components/chat/LoadingIndicator";
import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";
import { TextToSpeechButton } from "@/components/chat/TextToSpeechButton";
import type { Citation, ConfidenceLabel, FeedbackValue } from "@/lib/chat";
import type { PlaybackState } from "@/lib/voice/utils";

type UiMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[];
  createdAt: string;
  confidence?: ConfidenceLabel | null;
  isStreaming?: boolean;
  isError?: boolean;
  relatedQuery?: string;
  feedback?: FeedbackValue | null;
  isSpeaking?: boolean;
};

type MessageBubbleProps = {
  message: UiMessage;
  botName: string;
  logoUrl: string | null;
  avatarUrl: string | null;
  themeMode: "dark" | "light";
  markdownEnabled: boolean;
  showCitations: boolean;
  showConfidence: boolean;
  onCopy: (message: UiMessage) => void;
  onDownload: (message: UiMessage) => void;
  onRegenerate: () => void;
  onFeedback: (messageId: string, value: FeedbackValue) => Promise<void>;
  canRegenerate: boolean;
  voiceOutputEnabled: boolean;
  voiceOutputSupported: boolean;
  speakingMessageId: string | null;
  playbackState: PlaybackState;
  onSpeak: (message: UiMessage) => void;
  onPauseSpeech: () => void;
  onResumeSpeech: () => void;
  onStopSpeech: () => void;
};

const confidenceStyles: Record<ConfidenceLabel, string> = {
  High: "border-emerald-400/35 bg-emerald-500/15 text-emerald-100",
  Medium: "border-amber-400/35 bg-amber-500/15 text-amber-100",
  Low: "border-rose-400/35 bg-rose-500/15 text-rose-100",
};

function formatTime(timestamp: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

function MessageBubbleComponent({
  message,
  botName,
  logoUrl,
  avatarUrl,
  themeMode,
  markdownEnabled,
  showCitations,
  showConfidence,
  onCopy,
  onDownload,
  onRegenerate,
  onFeedback,
  canRegenerate,
  voiceOutputEnabled,
  voiceOutputSupported,
  speakingMessageId,
  playbackState,
  onSpeak,
  onPauseSpeech,
  onResumeSpeech,
  onStopSpeech,
}: MessageBubbleProps) {
  const isAssistant = message.role === "assistant";
  const isSpeaking = speakingMessageId === message.id;
  const bubbleBase =
    themeMode === "dark"
      ? isAssistant
        ? "border-white/10 bg-white/[0.045] text-slate-100"
        : "border-[var(--chat-brand)]/20 bg-[var(--chat-brand)]/12 text-white"
      : isAssistant
        ? "border-slate-200 bg-white text-slate-900 shadow-sm"
        : "border-[var(--chat-brand)]/15 bg-[var(--chat-brand)]/10 text-slate-950";

  return (
    <article
      className={`group flex gap-4 ${isAssistant ? "items-start" : "flex-row-reverse items-start"}`}
      aria-live={message.isStreaming ? "polite" : undefined}
    >
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border ${
          isAssistant
            ? "border-white/10 bg-slate-950/70 text-white"
            : "border-[var(--chat-brand)]/25 bg-[var(--chat-brand)] text-white"
        }`}
      >
        {isAssistant && (avatarUrl || logoUrl) ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img alt={`${botName} logo`} className="h-8 w-8 rounded-xl object-cover" src={avatarUrl || logoUrl || ""} />
        ) : (
          <span className="text-sm font-semibold">
            {isAssistant ? botName.slice(0, 1).toUpperCase() : "You".slice(0, 1)}
          </span>
        )}
      </div>

      <div className={`max-w-[min(100%,52rem)] space-y-3 ${isAssistant ? "" : "items-end"}`}>
        <div
          className={`rounded-[1.75rem] border px-5 py-4 transition-all duration-300 ${bubbleBase} ${
            message.isError ? "border-rose-400/30 bg-rose-500/10" : ""
          } ${isSpeaking ? "ring-2 ring-cyan-400/40" : ""}`}
        >
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <span className="font-medium uppercase tracking-[0.28em] text-slate-400/90">
              {isAssistant ? botName : "You"}
            </span>
            <span>{formatTime(message.createdAt)}</span>
            {showConfidence && message.confidence ? (
              <span className={`rounded-full border px-2 py-1 ${confidenceStyles[message.confidence]}`}>
                {message.confidence}
              </span>
            ) : null}
          </div>

          {message.isStreaming && !message.content ? (
            <LoadingIndicator />
          ) : (
            markdownEnabled ? (
              <MarkdownRenderer content={message.content || " "} />
            ) : (
              <div className="whitespace-pre-wrap text-sm leading-7">{message.content || " "}</div>
            )
          )}
        </div>

        {isAssistant && showCitations && message.citations.length ? (
          <div className="space-y-1.5">
            <p className="text-[0.68rem] font-medium uppercase tracking-[0.28em] text-slate-500">
              References
            </p>
            <div className="space-y-1.5">
            {message.citations.map((citation, index) => (
              <CitationCard
                key={`${message.id}-${citation.file_name ?? "source"}-${index}`}
                citation={citation}
                highlightQuery={message.relatedQuery}
                index={index}
              />
            ))}
            </div>
          </div>
        ) : null}

        {isAssistant ? (
          <div className="flex flex-wrap items-center gap-2">
            <button
              className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:text-white"
              onClick={() => onCopy(message)}
              type="button"
            >
              Copy
            </button>
            <button
              className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:text-white"
              onClick={() => onDownload(message)}
              type="button"
            >
              Download
            </button>
            {canRegenerate ? (
              <button
                className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:text-white"
                onClick={onRegenerate}
                type="button"
              >
                Regenerate
              </button>
            ) : null}
            {voiceOutputEnabled ? (
              <TextToSpeechButton
                disabled={Boolean(message.isStreaming)}
                isActive={isSpeaking}
                onPause={onPauseSpeech}
                onPlay={() => onSpeak(message)}
                onResume={onResumeSpeech}
                onStop={onStopSpeech}
                playbackState={playbackState}
                supported={voiceOutputSupported}
              />
            ) : null}
            <FeedbackButtons
              initialValue={message.feedback ?? null}
              onSubmit={(value) => onFeedback(message.id, value)}
            />
          </div>
        ) : null}
      </div>
    </article>
  );
}

export const MessageBubble = memo(MessageBubbleComponent);
export type { UiMessage };
