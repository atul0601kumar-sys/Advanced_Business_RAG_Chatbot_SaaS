import type { VoiceSettings } from "@/lib/settings";

export type VoiceErrorCode =
  | "unsupported_browser"
  | "microphone_denied"
  | "no_microphone"
  | "network_failure"
  | "transcription_failure"
  | "tts_failure"
  | "recording_failed"
  | "unknown";

export type VoiceError = {
  code: VoiceErrorCode;
  message: string;
};

export type TranscriptResult = {
  composerValue: string;
  previewValue: string | null;
};

export type PlaybackState = "idle" | "playing" | "paused";

export function mapVoiceError(error: unknown, fallback: string): VoiceError {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError" || error.name === "SecurityError") {
      return { code: "microphone_denied", message: "Microphone access was denied." };
    }
    if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
      return { code: "no_microphone", message: "No microphone was found on this device." };
    }
  }
  if (error instanceof Error) {
    const message = error.message.toLowerCase();
    if (message.includes("unsupported")) {
      return { code: "unsupported_browser", message: "Voice is not supported in this browser." };
    }
    if (message.includes("network")) {
      return { code: "network_failure", message: "A network issue interrupted the voice request." };
    }
    if (message.includes("transcription")) {
      return { code: "transcription_failure", message: error.message };
    }
    if (message.includes("speech") || message.includes("audio")) {
      return { code: "tts_failure", message: error.message };
    }
    return { code: "unknown", message: error.message || fallback };
  }
  return { code: "unknown", message: fallback };
}

export function applyTranscriptToInput(
  transcript: string,
  currentComposerValue: string,
  transcriptPreviewEnabled: boolean,
): TranscriptResult {
  const normalized = transcript.trim();
  if (!normalized) {
    return { composerValue: currentComposerValue, previewValue: null };
  }
  if (transcriptPreviewEnabled) {
    return { composerValue: currentComposerValue, previewValue: normalized };
  }
  return {
    composerValue: currentComposerValue ? `${currentComposerValue.trimEnd()} ${normalized}`.trim() : normalized,
    previewValue: null,
  };
}

export function resolveVoicePlaybackState(
  currentState: PlaybackState,
  action: "play" | "pause" | "resume" | "stop",
): PlaybackState {
  if (action === "play") {
    return "playing";
  }
  if (action === "pause" && currentState === "playing") {
    return "paused";
  }
  if (action === "resume" && currentState === "paused") {
    return "playing";
  }
  if (action === "stop") {
    return "idle";
  }
  return currentState;
}

export function isVoiceInputAvailable(settings: VoiceSettings): boolean {
  return settings.voice_input_enabled;
}

export function isVoiceOutputAvailable(settings: VoiceSettings): boolean {
  return settings.voice_output_enabled;
}
