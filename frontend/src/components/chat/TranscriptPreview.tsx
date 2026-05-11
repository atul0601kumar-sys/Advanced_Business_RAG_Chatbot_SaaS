"use client";

type TranscriptPreviewProps = {
  transcript: string | null;
  onChange: (value: string) => void;
  onApply: () => void;
  onDismiss: () => void;
};

export function TranscriptPreview({
  transcript,
  onChange,
  onApply,
  onDismiss,
}: TranscriptPreviewProps) {
  if (!transcript) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs uppercase tracking-[0.28em] text-cyan-100/80">Transcript preview</p>
        <p className="text-xs text-cyan-50/80">Edit before sending</p>
      </div>
      <textarea
        aria-label="Transcript preview"
        className="mt-3 min-h-[96px] w-full rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-white outline-none"
        onChange={(event) => onChange(event.target.value)}
        value={transcript}
      />
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          className="rounded-full bg-[var(--chat-brand)] px-4 py-2 text-sm font-medium text-white"
          onClick={onApply}
          type="button"
        >
          Use transcript
        </button>
        <button
          className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200"
          onClick={onDismiss}
          type="button"
        >
          Discard
        </button>
      </div>
    </div>
  );
}
