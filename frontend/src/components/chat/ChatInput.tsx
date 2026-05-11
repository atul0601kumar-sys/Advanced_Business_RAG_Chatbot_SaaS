"use client";

import { memo, useEffect, useRef } from "react";

import { TranscriptPreview } from "@/components/chat/TranscriptPreview";
import { VoiceRecorder } from "@/components/chat/VoiceRecorder";
import { estimateTokens, type ChatMode } from "@/lib/chat";

type ChatInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  disabled?: boolean;
  isGenerating?: boolean;
  mode: ChatMode;
  onModeChange: (mode: ChatMode) => void;
  placeholder: string;
  themeMode: "dark" | "light";
  voiceInputEnabled?: boolean;
  voiceInputSupported?: boolean;
  isRecording?: boolean;
  isProcessingTranscript?: boolean;
  transcriptPreview?: string | null;
  voiceError?: string | null;
  onStartRecording?: () => void;
  onStopRecording?: () => void;
  onTranscriptPreviewChange?: (value: string) => void;
  onApplyTranscriptPreview?: () => void;
  onDismissTranscriptPreview?: () => void;
};

const modeLabels: Array<{ value: ChatMode; label: string }> = [
  { value: "concise", label: "Concise" },
  { value: "detailed", label: "Detailed" },
  { value: "bullet", label: "Bullet points" },
];

function ChatInputComponent({
  value,
  onChange,
  onSend,
  onStop,
  disabled = false,
  isGenerating = false,
  mode,
  onModeChange,
  placeholder,
  themeMode,
  voiceInputEnabled = false,
  voiceInputSupported = false,
  isRecording = false,
  isProcessingTranscript = false,
  transcriptPreview = null,
  voiceError = null,
  onStartRecording,
  onStopRecording,
  onTranscriptPreviewChange,
  onApplyTranscriptPreview,
  onDismissTranscriptPreview,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const characterCount = value.length;
  const tokenEstimate = estimateTokens(value);
  const showWarning = characterCount > 6500 || tokenEstimate > 1600;

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 240)}px`;
  }, [value]);

  return (
    <div className="rounded-[1.75rem] border border-white/10 bg-white/[0.045] p-4 shadow-[0_24px_80px_rgba(2,6,23,0.32)]">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Answer mode">
          {modeLabels.map((item) => (
            <button
              key={item.value}
              className={`rounded-full border px-3 py-1.5 text-xs transition ${
                mode === item.value
                  ? "border-[var(--chat-brand)]/30 bg-[var(--chat-brand)]/14 text-white"
                  : "border-white/10 bg-white/[0.04] text-slate-300 hover:border-white/20 hover:text-white"
              }`}
              disabled={disabled}
              onClick={() => onModeChange(item.value)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className={`text-xs ${showWarning ? "text-amber-300" : "text-slate-400"}`}>
          {characterCount}/8000 chars · ~{tokenEstimate} tokens
        </div>
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-end">
        <textarea
          ref={textareaRef}
          aria-label="Chat message input"
          className={`min-h-[72px] w-full resize-none rounded-2xl border px-4 py-3 text-[15px] outline-none transition focus:border-[var(--chat-brand)]/40 focus:ring-2 focus:ring-[var(--chat-brand)]/20 disabled:cursor-not-allowed disabled:opacity-60 ${
            themeMode === "dark"
              ? "border-white/10 bg-slate-950/50 text-white placeholder:text-slate-500"
              : "border-slate-200 bg-white text-slate-950 placeholder:text-slate-400"
          }`}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (value.trim()) {
                onSend();
              }
            }
          }}
          placeholder={placeholder}
          rows={1}
          value={value}
        />

        <div className="flex items-center gap-2 md:self-stretch">
          {voiceInputEnabled ? (
            <VoiceRecorder
              disabled={disabled}
              errorMessage={voiceError}
              isProcessing={isProcessingTranscript}
              isRecording={isRecording}
              onStart={() => onStartRecording?.()}
              onStop={() => onStopRecording?.()}
              supported={voiceInputSupported}
            />
          ) : null}
          {isGenerating ? (
            <button
              aria-label="Stop generating response"
              className="h-full rounded-2xl border border-rose-400/30 bg-rose-500/12 px-4 py-3 text-sm font-medium text-rose-100 transition hover:border-rose-400/40 hover:bg-rose-500/18"
              onClick={onStop}
              type="button"
            >
              Stop
            </button>
          ) : null}
          <button
            aria-label="Send message"
            className="h-full rounded-2xl bg-[var(--chat-brand)] px-5 py-3 text-sm font-semibold text-white shadow-[0_18px_40px_color-mix(in_srgb,var(--chat-brand)_35%,transparent)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={disabled || !value.trim()}
            onClick={onSend}
            type="button"
          >
            Send
          </button>
        </div>
      </div>
      <div className="mt-3">
        <TranscriptPreview
          onApply={() => onApplyTranscriptPreview?.()}
          onChange={(nextValue) => onTranscriptPreviewChange?.(nextValue)}
          onDismiss={() => onDismissTranscriptPreview?.()}
          transcript={transcriptPreview}
        />
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Press Enter to send. Press Shift+Enter for a newline.
      </p>
    </div>
  );
}

export const ChatInput = memo(ChatInputComponent);
