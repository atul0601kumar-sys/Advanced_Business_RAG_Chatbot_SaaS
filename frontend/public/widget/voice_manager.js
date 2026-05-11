export class WidgetVoiceManager {
  constructor() {
    this.recognition = null;
    this.currentUtterance = null;
    this.speakingMessageId = null;
  }

  supportsInput() {
    return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  supportsOutput() {
    return "speechSynthesis" in window;
  }

  startInput({ onTranscript, onStateChange, onError }) {
    var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      onError(new Error("Voice input is unsupported in this browser."));
      return;
    }
    this.recognition = new Recognition();
    this.recognition.continuous = false;
    this.recognition.interimResults = true;
    this.recognition.lang = "en-US";
    var transcript = "";
    this.recognition.onresult = function (event) {
      var chunks = [];
      for (var index = 0; index < event.results.length; index += 1) {
        if (event.results[index][0] && event.results[index][0].transcript) {
          chunks.push(event.results[index][0].transcript);
        }
      }
      transcript = chunks.join(" ").trim();
    };
    this.recognition.onerror = function () {
      onStateChange({ isRecording: false });
      onError(new Error("Voice recognition failed."));
    };
    this.recognition.onend = function () {
      onStateChange({ isRecording: false });
      if (transcript) {
        onTranscript(transcript);
      }
    };
    onStateChange({ isRecording: true });
    this.recognition.start();
  }

  stopInput() {
    if (this.recognition) {
      this.recognition.stop();
    }
  }

  speak({ messageId, text, voiceStyle, onStart, onEnd, onError }) {
    if (!this.supportsOutput()) {
      onError(new Error("Speech playback is unsupported in this browser."));
      return;
    }
    this.stopSpeaking();
    var utterance = new SpeechSynthesisUtterance(text);
    if (voiceStyle) {
      var voices = window.speechSynthesis.getVoices();
      var matching = voices.find(function (voice) {
        return voice.name.toLowerCase().includes(String(voiceStyle).toLowerCase());
      });
      if (matching) {
        utterance.voice = matching;
      }
    }
    utterance.onstart = () => {
      this.speakingMessageId = messageId;
      onStart();
    };
    utterance.onend = () => {
      this.speakingMessageId = null;
      onEnd();
    };
    utterance.onerror = () => {
      this.speakingMessageId = null;
      onError(new Error("Speech playback failed."));
    };
    this.currentUtterance = utterance;
    window.speechSynthesis.speak(utterance);
  }

  pauseSpeaking() {
    if (this.supportsOutput()) {
      window.speechSynthesis.pause();
    }
  }

  resumeSpeaking() {
    if (this.supportsOutput()) {
      window.speechSynthesis.resume();
    }
  }

  stopSpeaking() {
    if (this.supportsOutput()) {
      window.speechSynthesis.cancel();
    }
    this.currentUtterance = null;
    this.speakingMessageId = null;
  }
}
