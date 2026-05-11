"use client";

type LoadingIndicatorProps = {
  label?: string;
  variant?: "typing" | "skeleton";
};

export function LoadingIndicator({
  label = "Assistant is thinking",
  variant = "typing",
}: LoadingIndicatorProps) {
  if (variant === "skeleton") {
    return (
      <div className="space-y-3" aria-hidden="true">
        <div className="h-4 w-32 animate-pulse rounded-full bg-white/10" />
        <div className="h-4 w-full animate-pulse rounded-full bg-white/10" />
        <div className="h-4 w-4/5 animate-pulse rounded-full bg-white/10" />
      </div>
    );
  }

  return (
    <div className="inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300">
      <span className="sr-only">{label}</span>
      <span className="flex items-center gap-1.5" aria-hidden="true">
        <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-[var(--chat-brand)] [animation-delay:-0.2s]" />
        <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-[var(--chat-brand)] [animation-delay:-0.1s]" />
        <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-[var(--chat-brand)]" />
      </span>
      <span>{label}</span>
    </div>
  );
}
