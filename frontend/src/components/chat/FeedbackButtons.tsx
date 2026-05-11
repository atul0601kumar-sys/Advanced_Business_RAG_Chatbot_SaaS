"use client";

import { memo, useState } from "react";

import type { FeedbackValue } from "@/lib/chat";

type FeedbackButtonsProps = {
  disabled?: boolean;
  initialValue?: FeedbackValue | null;
  onSubmit: (value: FeedbackValue) => Promise<void>;
};

function FeedbackButtonsComponent({
  disabled = false,
  initialValue = null,
  onSubmit,
}: FeedbackButtonsProps) {
  const [selected, setSelected] = useState<FeedbackValue | null>(initialValue);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleClick(value: FeedbackValue) {
    if (disabled || isSubmitting || selected === value) {
      return;
    }
    setIsSubmitting(true);
    try {
      await onSubmit(value);
      setSelected(value);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex items-center gap-2" role="group" aria-label="Response feedback">
      <button
        aria-label="Thumbs up"
        className={`rounded-full border px-3 py-2 text-sm transition ${
          selected === "up"
            ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-100"
            : "border-white/10 bg-white/5 text-slate-300 hover:border-emerald-400/30 hover:text-white"
        }`}
        disabled={disabled || isSubmitting}
        onClick={() => void handleClick("up")}
        type="button"
      >
        👍
      </button>
      <button
        aria-label="Thumbs down"
        className={`rounded-full border px-3 py-2 text-sm transition ${
          selected === "down"
            ? "border-rose-400/40 bg-rose-500/15 text-rose-100"
            : "border-white/10 bg-white/5 text-slate-300 hover:border-rose-400/30 hover:text-white"
        }`}
        disabled={disabled || isSubmitting}
        onClick={() => void handleClick("down")}
        type="button"
      >
        👎
      </button>
    </div>
  );
}

export const FeedbackButtons = memo(FeedbackButtonsComponent);
