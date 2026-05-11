"use client";

type VoiceRecorderProps = {
  disabled: boolean;
  supported: boolean;
  isRecording: boolean;
  isProcessing: boolean;
  onStart: () => void;
  onStop: () => void;
  errorMessage?: string | null;
};

export function VoiceRecorder({
  disabled,
  supported,
  isRecording,
  isProcessing,
  onStart,
  onStop,
  errorMessage,
}: VoiceRecorderProps) {
  return (
    <div className="flex flex-col gap-2">
      <button
        aria-label={
          !supported
            ? "Voice input is not supported in this browser"
            : isRecording
              ? "Stop voice recording"
              : "Start voice recording"
        }
        className={`inline-flex h-12 items-center justify-center rounded-2xl border px-4 text-sm font-medium transition ${
          !supported
            ? "cursor-not-allowed border-slate-700/60 bg-slate-900/50 text-slate-500"
            : isRecording
              ? "border-rose-400/40 bg-rose-500/14 text-rose-100"
              : "border-white/10 bg-white/[0.04] text-slate-200 hover:border-white/20 hover:text-white"
        }`}
        disabled={disabled || !supported || isProcessing}
        onClick={isRecording ? onStop : onStart}
        type="button"
      >
        <span className={`mr-2 inline-flex h-2.5 w-2.5 rounded-full ${isRecording ? "animate-pulse bg-rose-300" : "bg-[var(--chat-brand)]"}`} />
        {isProcessing ? "Transcribing..." : isRecording ? "Recording" : "Voice"}
      </button>
      {!supported ? (
        <p className="text-xs text-amber-300">Voice input is not supported in this browser.</p>
      ) : null}
      {errorMessage ? <p className="text-xs text-rose-300">{errorMessage}</p> : null}
    </div>
  );
}
