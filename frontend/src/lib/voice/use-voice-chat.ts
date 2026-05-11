"use client";

import { useEffect, useRef, useState } from "react";

import type { VoiceSettings } from "@/lib/settings";
import {
  createSpeechToTextProvider,
  createTextToSpeechProvider,
  getVoiceFeatureAvailability,
  type SpeechToTextProvider,
  type TextToSpeechProvider,
} from "@/lib/voice/providers";
import {
  applyTranscriptToInput,
  mapVoiceError,
  resolveVoicePlaybackState,
  type PlaybackState,
  type VoiceError,
} from "@/lib/voice/utils";

export function useVoiceChat(options: {
  workspaceId: string | null;
  settings: VoiceSettings | null;
  composerValue: string;
  setComposerValue: (value: string) => void;
  onVoiceTranscriptReady?: (transcript: string) => void;
}) {
  const { workspaceId, settings, composerValue, setComposerValue, onVoiceTranscriptReady } = options;
  const [voiceError, setVoiceError] = useState<VoiceError | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessingTranscript, setIsProcessingTranscript] = useState(false);
  const [transcriptPreview, setTranscriptPreview] = useState<string | null>(null);
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [playbackState, setPlaybackState] = useState<PlaybackState>("idle");
  const [supportedInput, setSupportedInput] = useState(false);
  const [supportedOutput, setSupportedOutput] = useState(false);

  const sttProviderRef = useRef<SpeechToTextProvider | null>(null);
  const ttsProviderRef = useRef<TextToSpeechProvider | null>(null);

  useEffect(() => {
    if (!workspaceId || !settings) {
      sttProviderRef.current = null;
      ttsProviderRef.current = null;
      setSupportedInput(false);
      setSupportedOutput(false);
      return;
    }
    sttProviderRef.current = createSpeechToTextProvider(workspaceId);
    ttsProviderRef.current = createTextToSpeechProvider(workspaceId);
    setSupportedInput(Boolean(sttProviderRef.current.isSupported));
    setSupportedOutput(Boolean(ttsProviderRef.current.isSupported));
  }, [workspaceId, settings]);

  useEffect(() => {
    return () => {
      ttsProviderRef.current?.stop();
    };
  }, []);

  const availability = settings ? getVoiceFeatureAvailability(settings) : null;

  async function startRecording() {
    if (!settings?.voice_input_enabled || !sttProviderRef.current) {
      return;
    }
    setVoiceError(null);
    try {
      await sttProviderRef.current.start({
        onTranscript: ({ transcript }) => {
          const next = applyTranscriptToInput(
            transcript,
            composerValue,
            settings.transcript_preview_enabled,
          );
          setComposerValue(next.composerValue);
          setTranscriptPreview(next.previewValue);
          onVoiceTranscriptReady?.(transcript);
          setIsProcessingTranscript(false);
        },
        onStateChange: ({ isRecording: nextRecording, isProcessing }) => {
          setIsRecording(nextRecording);
          setIsProcessingTranscript(isProcessing);
        },
        onError: (error) => {
          setVoiceError(error);
          setIsRecording(false);
          setIsProcessingTranscript(false);
        },
      });
    } catch (error) {
      setVoiceError(mapVoiceError(error, "Recording could not be started."));
      setIsRecording(false);
      setIsProcessingTranscript(false);
    }
  }

  async function stopRecording() {
    if (!sttProviderRef.current) {
      return;
    }
    try {
      await sttProviderRef.current.stop();
    } catch (error) {
      setVoiceError(mapVoiceError(error, "Recording could not be stopped."));
    }
  }

  function applyTranscriptPreview() {
    if (!transcriptPreview) {
      return;
    }
    setComposerValue(
      composerValue ? `${composerValue.trimEnd()} ${transcriptPreview}`.trim() : transcriptPreview,
    );
    setTranscriptPreview(null);
  }

  function dismissTranscriptPreview() {
    setTranscriptPreview(null);
  }

  async function speakMessage(messageId: string, text: string) {
    if (!settings?.voice_output_enabled || !ttsProviderRef.current) {
      return;
    }
    setVoiceError(null);
    try {
      await ttsProviderRef.current.speak({
        text,
        voiceStyle: settings.voice_style,
        onStart: () => {
          setSpeakingMessageId(messageId);
          setPlaybackState(resolveVoicePlaybackState("idle", "play"));
        },
        onEnd: () => {
          setSpeakingMessageId((current) => (current === messageId ? null : current));
          setPlaybackState(resolveVoicePlaybackState("playing", "stop"));
        },
        onError: (error) => {
          setVoiceError(error);
          setSpeakingMessageId(null);
          setPlaybackState("idle");
        },
      });
    } catch (error) {
      setVoiceError(mapVoiceError(error, "Speech playback failed."));
      setSpeakingMessageId(null);
      setPlaybackState("idle");
    }
  }

  function pauseSpeaking() {
    ttsProviderRef.current?.pause();
    setPlaybackState((current) => resolveVoicePlaybackState(current, "pause"));
  }

  function resumeSpeaking() {
    ttsProviderRef.current?.resume();
    setPlaybackState((current) => resolveVoicePlaybackState(current, "resume"));
  }

  function stopSpeaking() {
    ttsProviderRef.current?.stop();
    setSpeakingMessageId(null);
    setPlaybackState("idle");
  }

  return {
    availability,
    supportedInput,
    supportedOutput,
    voiceError,
    clearVoiceError: () => setVoiceError(null),
    isRecording,
    isProcessingTranscript,
    transcriptPreview,
    setTranscriptPreview,
    applyTranscriptPreview,
    dismissTranscriptPreview,
    startRecording,
    stopRecording,
    speakingMessageId,
    playbackState,
    speakMessage,
    pauseSpeaking,
    resumeSpeaking,
    stopSpeaking,
  };
}
