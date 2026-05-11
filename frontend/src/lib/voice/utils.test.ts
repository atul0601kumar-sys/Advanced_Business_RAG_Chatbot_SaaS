import test from "node:test";
import assert from "node:assert/strict";

import {
  applyTranscriptToInput,
  isVoiceInputAvailable,
  isVoiceOutputAvailable,
  mapVoiceError,
  resolveVoicePlaybackState,
} from "./utils";

test("maps microphone permission errors clearly", () => {
  const error = mapVoiceError(new DOMException("Permission denied", "NotAllowedError"), "fallback");
  assert.equal(error.code, "microphone_denied");
});

test("keeps transcript in preview when preview is enabled", () => {
  const result = applyTranscriptToInput("hello world", "", true);
  assert.equal(result.previewValue, "hello world");
  assert.equal(result.composerValue, "");
});

test("sends transcript directly into the composer when preview is disabled", () => {
  const result = applyTranscriptToInput("hello world", "Current", false);
  assert.equal(result.previewValue, null);
  assert.equal(result.composerValue, "Current hello world");
});

test("tracks TTS playback state transitions", () => {
  assert.equal(resolveVoicePlaybackState("idle", "play"), "playing");
  assert.equal(resolveVoicePlaybackState("playing", "pause"), "paused");
  assert.equal(resolveVoicePlaybackState("paused", "resume"), "playing");
  assert.equal(resolveVoicePlaybackState("playing", "stop"), "idle");
});

test("respects disabled voice settings", () => {
  assert.equal(
    isVoiceInputAvailable({
      voice_input_enabled: false,
      voice_output_enabled: true,
      voice_style: null,
      transcript_preview_enabled: true,
      auto_read_assistant_responses: false,
    }),
    false,
  );
  assert.equal(
    isVoiceOutputAvailable({
      voice_input_enabled: true,
      voice_output_enabled: false,
      voice_style: null,
      transcript_preview_enabled: true,
      auto_read_assistant_responses: false,
    }),
    false,
  );
});
