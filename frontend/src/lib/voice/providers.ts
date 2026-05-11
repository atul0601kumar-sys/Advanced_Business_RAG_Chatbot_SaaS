"use client";

import { apiBaseUrl, apiFetch, buildApiHeaders } from "@/lib/auth";
import type { VoiceSettings } from "@/lib/settings";
import { mapVoiceError, type PlaybackState, type VoiceError } from "@/lib/voice/utils";

type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

interface BrowserSpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type SpeechRecognitionEventLike = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

export type VoiceTranscription = {
  transcript: string;
  provider: string;
};

export type VoiceRecorderEvents = {
  onTranscript: (value: VoiceTranscription) => void;
  onStateChange: (state: { isRecording: boolean; isProcessing: boolean }) => void;
  onError: (error: VoiceError) => void;
};

export interface SpeechToTextProvider {
  readonly name: string;
  readonly isSupported: boolean;
  start(events: VoiceRecorderEvents): Promise<void>;
  stop(): Promise<void>;
}

export interface TextToSpeechProvider {
  readonly name: string;
  readonly isSupported: boolean;
  speak(options: {
    text: string;
    voiceStyle: string | null;
    onStart: () => void;
    onEnd: () => void;
    onError: (error: VoiceError) => void;
  }): Promise<void>;
  pause(): void;
  resume(): void;
  stop(): void;
  getState(): PlaybackState;
}

async function apiRequest<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await apiFetch(path, {
      ...init,
      headers: buildApiHeaders(init.headers, init.method ?? "GET"),
    });
  } catch (error) {
    throw mapVoiceError(error, "Voice request failed.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Voice request failed." }));
    throw { code: "network_failure", message: payload.detail ?? "Voice request failed." } satisfies VoiceError;
  }
  return response.json() as Promise<T>;
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      const encoded = value.includes(",") ? value.split(",", 2)[1] : value;
      resolve(encoded);
    };
    reader.onerror = () => reject(new Error("Voice recording could not be processed."));
    reader.readAsDataURL(blob);
  });
}

class BrowserSpeechRecognitionProvider implements SpeechToTextProvider {
  readonly name = "browser";
  readonly isSupported = typeof window !== "undefined" && Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  private recognition: BrowserSpeechRecognition | null = null;
  private events: VoiceRecorderEvents | null = null;

  async start(events: VoiceRecorderEvents): Promise<void> {
    if (!this.isSupported) {
      throw new Error("Voice input is unsupported in this browser.");
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      throw new Error("Voice input is unsupported in this browser.");
    }
    this.events = events;
    this.recognition = new Recognition();
    this.recognition.continuous = false;
    this.recognition.interimResults = true;
    this.recognition.lang = "en-US";
    let transcript = "";
    this.recognition.onresult = (event) => {
      const chunks: string[] = [];
      for (const result of Array.from(event.results)) {
        if (result[0]?.transcript) {
          chunks.push(result[0].transcript);
        }
      }
      transcript = chunks.join(" ").trim();
      this.events?.onStateChange({ isRecording: true, isProcessing: false });
    };
    this.recognition.onerror = (event) => {
      this.events?.onError({
        code: event.error === "not-allowed" ? "microphone_denied" : "transcription_failure",
        message: event.error === "not-allowed" ? "Microphone access was denied." : "Voice recognition failed.",
      });
      this.events?.onStateChange({ isRecording: false, isProcessing: false });
    };
    this.recognition.onend = () => {
      this.events?.onStateChange({ isRecording: false, isProcessing: false });
      if (transcript) {
        this.events?.onTranscript({ transcript, provider: this.name });
      }
    };
    this.events.onStateChange({ isRecording: true, isProcessing: false });
    this.recognition.start();
  }

  async stop(): Promise<void> {
    this.recognition?.stop();
  }
}

class BackendSpeechToTextProvider implements SpeechToTextProvider {
  readonly name = "backend";
  readonly isSupported = typeof window !== "undefined" && typeof MediaRecorder !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
  private mediaRecorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private analyser: AnalyserNode | null = null;
  private audioContext: AudioContext | null = null;
  private silenceCheckTimer: number | null = null;
  private chunks: BlobPart[] = [];
  private events: VoiceRecorderEvents | null = null;
  private workspaceId: string;

  constructor(workspaceId: string) {
    this.workspaceId = workspaceId;
  }

  async start(events: VoiceRecorderEvents): Promise<void> {
    if (!this.isSupported) {
      throw new Error("Voice input is unsupported in this browser.");
    }
    this.events = events;
    this.chunks = [];
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.audioContext = new AudioContext();
    const source = this.audioContext.createMediaStreamSource(this.stream);
    this.analyser = this.audioContext.createAnalyser();
    source.connect(this.analyser);
    this.mediaRecorder = new MediaRecorder(this.stream, { mimeType: "audio/webm" });
    this.mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) {
        this.chunks.push(event.data);
      }
    });
    this.mediaRecorder.addEventListener("stop", () => {
      void this.handleStop();
    });
    this.events.onStateChange({ isRecording: true, isProcessing: false });
    this.mediaRecorder.start();
    this.startSilenceDetection();
  }

  async stop(): Promise<void> {
    this.stopSilenceDetection();
    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      this.mediaRecorder.stop();
    }
  }

  private startSilenceDetection() {
    if (!this.analyser) {
      return;
    }
    const buffer = new Uint8Array(this.analyser.fftSize);
    let silenceStartedAt = Date.now();
    this.silenceCheckTimer = window.setInterval(() => {
      if (!this.analyser || !this.mediaRecorder || this.mediaRecorder.state === "inactive") {
        return;
      }
      this.analyser.getByteTimeDomainData(buffer);
      const silent = buffer.every((sample) => Math.abs(sample - 128) < 6);
      if (silent) {
        if (Date.now() - silenceStartedAt > 1400) {
          void this.stop();
        }
      } else {
        silenceStartedAt = Date.now();
      }
    }, 250);
  }

  private stopSilenceDetection() {
    if (this.silenceCheckTimer !== null) {
      window.clearInterval(this.silenceCheckTimer);
      this.silenceCheckTimer = null;
    }
  }

  private async handleStop() {
    this.events?.onStateChange({ isRecording: false, isProcessing: true });
    try {
      const blob = new Blob(this.chunks, { type: "audio/webm" });
      const audioBase64 = await blobToBase64(blob);
      const payload = await apiRequest<{ transcript: string; provider: string }>("/api/v1/voice/transcribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: this.workspaceId,
          audio_base64: audioBase64,
          mime_type: blob.type || "audio/webm",
        }),
      });
      this.events?.onTranscript(payload);
    } catch (error) {
      this.events?.onError(mapVoiceError(error, "Voice transcription failed."));
    } finally {
      this.events?.onStateChange({ isRecording: false, isProcessing: false });
      this.stream?.getTracks().forEach((track) => track.stop());
      this.audioContext?.close().catch(() => undefined);
      this.stream = null;
      this.audioContext = null;
      this.analyser = null;
    }
  }
}

class BrowserTextToSpeechProvider implements TextToSpeechProvider {
  readonly name = "browser";
  readonly isSupported = typeof window !== "undefined" && "speechSynthesis" in window;
  private state: PlaybackState = "idle";
  private currentUtterance: SpeechSynthesisUtterance | null = null;

  async speak(options: {
    text: string;
    voiceStyle: string | null;
    onStart: () => void;
    onEnd: () => void;
    onError: (error: VoiceError) => void;
  }): Promise<void> {
    if (!this.isSupported) {
      throw new Error("Speech playback is unsupported in this browser.");
    }
    this.stop();
    const utterance = new SpeechSynthesisUtterance(options.text);
    utterance.onstart = () => {
      this.state = "playing";
      options.onStart();
    };
    utterance.onend = () => {
      this.state = "idle";
      options.onEnd();
    };
    utterance.onerror = () => {
      this.state = "idle";
      options.onError({ code: "tts_failure", message: "Speech playback failed." });
    };
    if (options.voiceStyle) {
      const voices = window.speechSynthesis.getVoices();
      const matchingVoice = voices.find((voice) => voice.name.toLowerCase().includes(options.voiceStyle!.toLowerCase()));
      if (matchingVoice) {
        utterance.voice = matchingVoice;
      }
    }
    this.currentUtterance = utterance;
    window.speechSynthesis.speak(utterance);
  }

  pause(): void {
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.pause();
      this.state = "paused";
    }
  }

  resume(): void {
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      this.state = "playing";
    }
  }

  stop(): void {
    if (!this.isSupported) {
      return;
    }
    window.speechSynthesis.cancel();
    this.currentUtterance = null;
    this.state = "idle";
  }

  getState(): PlaybackState {
    return this.state;
  }
}

class BackendTextToSpeechProvider implements TextToSpeechProvider {
  readonly name = "backend";
  readonly isSupported = true;
  private audio: HTMLAudioElement | null = null;
  private state: PlaybackState = "idle";
  private workspaceId: string;

  constructor(workspaceId: string) {
    this.workspaceId = workspaceId;
  }

  async speak(options: {
    text: string;
    voiceStyle: string | null;
    onStart: () => void;
    onEnd: () => void;
    onError: (error: VoiceError) => void;
  }): Promise<void> {
    this.stop();
    try {
      const payload = await apiRequest<{ audio_base64: string; mime_type: string }>("/api/v1/voice/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: this.workspaceId,
          text: options.text,
          voice_style: options.voiceStyle,
          format: "mp3",
        }),
      });
      const blob = new Blob([Uint8Array.from(atob(payload.audio_base64), (char) => char.charCodeAt(0))], {
        type: payload.mime_type,
      });
      const audio = new Audio(URL.createObjectURL(blob));
      this.audio = audio;
      audio.onplay = () => {
        this.state = "playing";
        options.onStart();
      };
      audio.onended = () => {
        this.state = "idle";
        URL.revokeObjectURL(audio.src);
        options.onEnd();
      };
      audio.onerror = () => {
        this.state = "idle";
        options.onError({ code: "tts_failure", message: "Speech playback failed." });
      };
      await audio.play();
    } catch (error) {
      throw mapVoiceError(error, "Speech playback failed.");
    }
  }

  pause(): void {
    if (this.audio && !this.audio.paused) {
      this.audio.pause();
      this.state = "paused";
    }
  }

  resume(): void {
    if (this.audio && this.audio.paused) {
      void this.audio.play();
      this.state = "playing";
    }
  }

  stop(): void {
    if (!this.audio) {
      return;
    }
    this.audio.pause();
    this.audio.currentTime = 0;
    URL.revokeObjectURL(this.audio.src);
    this.audio = null;
    this.state = "idle";
  }

  getState(): PlaybackState {
    return this.state;
  }
}

export function createSpeechToTextProvider(workspaceId: string): SpeechToTextProvider {
  const browserProvider = new BrowserSpeechRecognitionProvider();
  if (browserProvider.isSupported) {
    return browserProvider;
  }
  return new BackendSpeechToTextProvider(workspaceId);
}

export function createTextToSpeechProvider(workspaceId: string): TextToSpeechProvider {
  const browserProvider = new BrowserTextToSpeechProvider();
  if (browserProvider.isSupported) {
    return browserProvider;
  }
  return new BackendTextToSpeechProvider(workspaceId);
}

export function getVoiceFeatureAvailability(settings: VoiceSettings) {
  return {
    inputEnabled: settings.voice_input_enabled,
    outputEnabled: settings.voice_output_enabled,
    transcriptPreviewEnabled: settings.transcript_preview_enabled,
    autoReadEnabled: settings.auto_read_assistant_responses,
  };
}
