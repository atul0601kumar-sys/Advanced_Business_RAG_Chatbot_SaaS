"use client";

import type { PlaybackState } from "@/lib/voice/utils";

type TextToSpeechButtonProps = {
  disabled: boolean;
  supported: boolean;
  isActive: boolean;
  playbackState: PlaybackState;
  onPlay: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
};

export function TextToSpeechButton({
  disabled,
  supported,
  isActive,
  playbackState,
  onPlay,
  onPause,
  onResume,
  onStop,
}: TextToSpeechButtonProps) {
  if (!supported) {
    return null;
  }

  if (!isActive || playbackState === "idle") {
    return (
      <button
        aria-label="Play assistant response"
        className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:text-white"
        disabled={disabled}
        onClick={onPlay}
        type="button"
      >
        Play audio
      </button>
    );
  }

  return (
    <>
      <button
        aria-label={playbackState === "playing" ? "Pause assistant audio" : "Resume assistant audio"}
        className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-100 transition hover:border-cyan-300/40 hover:bg-cyan-400/15"
        disabled={disabled}
        onClick={playbackState === "playing" ? onPause : onResume}
        type="button"
      >
        {playbackState === "playing" ? "Pause audio" : "Resume audio"}
      </button>
      <button
        aria-label="Stop assistant audio"
        className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:text-white"
        disabled={disabled}
        onClick={onStop}
        type="button"
      >
        Stop audio
      </button>
    </>
  );
}
