import { WidgetApiClient } from "./api_client.js";
import { SessionManager } from "./session_manager.js";
import { createStyleElement } from "./style_manager.js";
import { WidgetRenderer } from "./ui_renderer.js";
import { WidgetVoiceManager } from "./voice_manager.js";

function normalizeTheme(theme) {
  if (theme === "auto") {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return theme || "light";
}

function mergeSettings(settings, overrides) {
  var theme = overrides.theme || settings.widget.theme;
  var primaryColor = overrides.color || settings.identity.brand_color_primary;
  var welcomeMessage = overrides.welcomeMessage || settings.identity.welcome_message;
  var launcherBadgeText = overrides.welcomeMessage || settings.widget.welcome_popup_message || welcomeMessage;
  return {
    theme: normalizeTheme(theme),
    position: overrides.position || settings.widget.position,
    primaryColor: primaryColor,
    secondaryColor: settings.identity.brand_color_secondary,
    welcomeMessage: welcomeMessage,
    launcherBadgeText: launcherBadgeText,
  };
}

function toWidgetMessage(message) {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    citations: message.citations || [],
    created_at: message.created_at,
    confidence: message.token_usage ? message.token_usage.confidence : null,
    feedback: null,
    isTyping: false,
  };
}

function maybeIdle(callback) {
  if (window.requestIdleCallback) {
    window.requestIdleCallback(callback, { timeout: 1000 });
    return;
  }
  window.setTimeout(callback, 0);
}

export class WidgetCore {
  constructor(scriptElement, config) {
    this.scriptElement = scriptElement;
    this.config = config;
    this.api = new WidgetApiClient({
      apiBaseUrl: config.apiBaseUrl,
      workspaceId: config.workspaceId,
    });
    this.sessionManager = new SessionManager(config.workspaceId);
    this.voiceManager = new WidgetVoiceManager();
    this.state = {
      isReady: false,
      isOpen: false,
      isOffline: !navigator.onLine,
      isStreaming: false,
      showLauncherBadge: false,
      launcherBadgeText: "",
      botName: "Assistant",
      tagline: "",
      avatarUrl: null,
      welcomeMessage: "Ask a question to get started.",
      showBranding: true,
      messages: [],
      error: "",
      currentSessionId: this.sessionManager.getSessionId(),
      currentGenerationId: null,
      leadEnabled: false,
      showLeadForm: false,
      leadPromptTitle: "Talk to our team",
      leadPromptMessage: "",
      leadFields: ["name", "email"],
      leadValues: {
        name: "",
        email: "",
        phone: "",
        company: "",
        useCase: "",
        message: "",
      },
      isSubmittingLead: false,
      openTracked: false,
      voiceInputEnabled: false,
      voiceOutputEnabled: false,
      isRecording: false,
      speakingMessageId: null,
    };
    this.shadowHost = null;
    this.shadowRoot = null;
    this.renderer = null;
    this.publicSettings = null;
  }

  async mount() {
    this._createShadowRoot();
    this._bindWindowEvents();
    this.renderer = new WidgetRenderer(this.shadowRoot, {
      onToggle: this.toggle.bind(this),
      onSubmitMessage: this.sendMessage.bind(this),
      onStop: this.stopGeneration.bind(this),
      onRegenerate: this.regenerateLastAnswer.bind(this),
      onFeedback: this.submitFeedback.bind(this),
      onOpenLeadForm: this.openLeadForm.bind(this),
      onCloseLeadForm: this.closeLeadForm.bind(this),
      onLeadFieldChange: this.updateLeadField.bind(this),
      onLeadSubmit: this.submitLead.bind(this),
      onToggleVoiceInput: this.toggleVoiceInput.bind(this),
      onSpeakMessage: this.speakMessage.bind(this),
      onStopSpeaking: this.stopSpeaking.bind(this),
    });
    this.renderer.render(this.state);

    maybeIdle(async () => {
      try {
        await this._initialize();
      } catch (error) {
        this._setError(error.message || "Widget failed to initialize.");
      }
    });
  }

  async _initialize() {
    this.publicSettings = await this.api.fetchPublicSettings();
    var merged = mergeSettings(this.publicSettings, this.config.overrides);

    this.shadowRoot.innerHTML = "";
    this.shadowRoot.appendChild(
      createStyleElement({
        theme: merged.theme,
        position: merged.position,
        primaryColor: merged.primaryColor,
        secondaryColor: merged.secondaryColor,
      }),
    );
    this.renderer = new WidgetRenderer(this.shadowRoot, {
      onToggle: this.toggle.bind(this),
      onSubmitMessage: this.sendMessage.bind(this),
      onStop: this.stopGeneration.bind(this),
      onRegenerate: this.regenerateLastAnswer.bind(this),
      onFeedback: this.submitFeedback.bind(this),
      onOpenLeadForm: this.openLeadForm.bind(this),
      onCloseLeadForm: this.closeLeadForm.bind(this),
      onLeadFieldChange: this.updateLeadField.bind(this),
      onLeadSubmit: this.submitLead.bind(this),
      onToggleVoiceInput: this.toggleVoiceInput.bind(this),
      onSpeakMessage: this.speakMessage.bind(this),
      onStopSpeaking: this.stopSpeaking.bind(this),
    });

    this.state = Object.assign({}, this.state, {
      isReady: true,
      botName: this.publicSettings.identity.bot_name,
      tagline: this.publicSettings.identity.tagline || "",
      avatarUrl: this.publicSettings.identity.bot_avatar || this.publicSettings.identity.logo || null,
      welcomeMessage: merged.welcomeMessage,
      launcherBadgeText: merged.launcherBadgeText,
      showBranding: this.publicSettings.widget.show_branding,
      leadEnabled: Boolean(this.publicSettings.lead_capture.enabled || this.publicSettings.handoff.enabled),
      leadFields: (this.publicSettings.lead_capture.required_fields || ["name", "email"]).map(function (field) {
        if (field === "use_case") {
          return "useCase";
        }
        return field;
      }),
      showLeadForm: Boolean(this.publicSettings.lead_capture.force_before_chat),
      voiceInputEnabled: Boolean(this.publicSettings.voice.voice_input_enabled && this.voiceManager.supportsInput()),
      voiceOutputEnabled: Boolean(this.publicSettings.voice.voice_output_enabled && this.voiceManager.supportsOutput()),
    });

    this.renderer.render(this.state);
    this._scheduleLauncherBadge(this.publicSettings.widget.delay_before_appearance_seconds || 0);

    if (this.state.currentSessionId) {
      await this._hydrateExistingSession();
    }
  }

  _createShadowRoot() {
    this.shadowHost = document.createElement("advanced-rag-widget");
    this.shadowRoot = this.shadowHost.attachShadow({ mode: "open" });
    document.body.appendChild(this.shadowHost);
  }

  _bindWindowEvents() {
    window.addEventListener("online", () => {
      this.state.isOffline = false;
      this._setError("");
      this._render();
    });
    window.addEventListener("offline", () => {
      this.state.isOffline = true;
      this._render();
    });
  }

  _scheduleLauncherBadge(delaySeconds) {
    var delay = Math.max(0, Number(delaySeconds || 0)) * 1000;
    window.setTimeout(() => {
      if (!this.state.isOpen) {
        this.state.showLauncherBadge = true;
        this._render();
      }
    }, delay);
  }

  async _hydrateExistingSession() {
    try {
      var history = await this.api.fetchHistory(this.state.currentSessionId);
      this.state.messages = history.messages.map(toWidgetMessage);
      this._render();
    } catch (error) {
      this.sessionManager.clearSessionId();
      this.state.currentSessionId = null;
      this.state.messages = [];
      this._setError("Previous session could not be restored.");
    }
  }

  _render() {
    if (this.renderer) {
      this.renderer.render(this.state);
    }
  }

  _setError(message) {
    this.state.error = message || "";
    this._render();
  }

  async toggle() {
    if (!this.state.isReady) {
      return;
    }
    this.state.isOpen = !this.state.isOpen;
    if (this.state.isOpen) {
      this.state.showLauncherBadge = false;
      if (!this.state.openTracked) {
        this.state.openTracked = true;
        this.api.trackEvent("widget_opened", {
          sessionId: this.state.currentSessionId,
          metadata: {
            url: window.location.href,
          },
        }).catch(function () {
          return null;
        });
      }
      requestAnimationFrame(() => {
        this.renderer.focusComposer();
      });
    }
    this._render();
  }

  async ensureSession() {
    if (this.state.currentSessionId) {
      return this.state.currentSessionId;
    }
    var session = await this.api.createSession(this.publicSettings.identity.bot_name + " widget");
    this.state.currentSessionId = session.id;
    this.sessionManager.setSessionId(session.id);
    return session.id;
  }

  async sendMessage() {
    var text = this.renderer.getComposerValue().trim();
    if (!text || this.state.isStreaming || this.state.isOffline) {
      return;
    }
    if (this.state.showLeadForm && this.publicSettings.lead_capture.force_before_chat) {
      this._setError("Please share your contact details before starting the chat.");
      return;
    }

    this._setError("");
    await this.ensureSession();
    this.state.messages.push({
      id: "local-user-" + Date.now(),
      role: "user",
      content: text,
      citations: [],
      created_at: new Date().toISOString(),
      confidence: null,
      feedback: null,
      isTyping: false,
    });
    this.state.messages.push({
      id: "streaming-assistant",
      role: "assistant",
      content: "",
      citations: [],
      created_at: new Date().toISOString(),
      confidence: null,
      feedback: null,
      isTyping: true,
    });
    this.state.isStreaming = true;
    this.renderer.clearComposer();
    this._render();

    this.api.trackEvent("message_sent", {
      sessionId: this.state.currentSessionId,
      metadata: {
        url: window.location.href,
      },
    }).catch(function () {
      return null;
    });

    try {
      await this.api.streamMessage(
        {
          sessionId: this.state.currentSessionId,
          message: text,
          mode: "detailed",
        },
        {
          onStart: (payload) => {
            this.state.currentGenerationId = payload.generation_id;
          },
          onToken: (delta) => {
            var current = this.state.messages[this.state.messages.length - 1];
            if (!current || current.id !== "streaming-assistant") {
              return;
            }
            current.isTyping = false;
            current.content += delta;
            this._render();
          },
          onComplete: (payload) => {
            var current = this.state.messages[this.state.messages.length - 1];
            if (current && current.id === "streaming-assistant") {
              current.id = payload.metadata.message_id || "assistant-" + Date.now();
              current.content = payload.answer;
              current.citations = payload.citations || [];
              current.confidence = payload.confidence || null;
              current.isTyping = false;
              current.created_at = new Date().toISOString();
            }
            this.state.isStreaming = false;
            this.state.currentGenerationId = payload.metadata.generation_id || null;
            this._applyLeadPrompt(payload.metadata.lead_capture || null);
            if (this.publicSettings.voice.voice_output_enabled && this.publicSettings.voice.auto_read_assistant_responses) {
              this.speakMessage(current.id, current.content);
            }
            this._render();
          },
        },
      );
    } catch (error) {
      this.state.isStreaming = false;
      this.state.currentGenerationId = null;
      this.state.messages = this.state.messages.filter(function (message) {
        return message.id !== "streaming-assistant";
      });
      this._setError(error.message || "Message could not be sent.");
    }
  }

  _applyLeadPrompt(leadPrompt) {
    if (!leadPrompt || !leadPrompt.should_prompt) {
      return;
    }
    this.state.showLeadForm = true;
    this.state.leadPromptTitle = leadPrompt.high_intent ? "Talk to a human expert" : "Share your details";
    this.state.leadPromptMessage = leadPrompt.message || "Leave your contact details and our team will follow up.";
  }

  async stopGeneration() {
    if (!this.state.currentSessionId || !this.state.isStreaming) {
      return;
    }
    try {
      await this.api.stop(this.state.currentSessionId, this.state.currentGenerationId);
      this.state.isStreaming = false;
      this.state.currentGenerationId = null;
      var current = this.state.messages[this.state.messages.length - 1];
      if (current && current.id === "streaming-assistant") {
        current.isTyping = false;
      }
      this._render();
    } catch (error) {
      this._setError(error.message || "Stop request failed.");
    }
  }

  async regenerateLastAnswer() {
    if (!this.state.currentSessionId || this.state.isStreaming || this.state.isOffline) {
      return;
    }
    this._setError("");
    this.state.isStreaming = true;
    this._render();
    try {
      var payload = await this.api.regenerate(this.state.currentSessionId, "detailed");
      for (var index = this.state.messages.length - 1; index >= 0; index -= 1) {
        if (this.state.messages[index].role === "assistant") {
          this.state.messages[index] = {
            id: payload.metadata.message_id || this.state.messages[index].id,
            role: "assistant",
            content: payload.answer,
            citations: payload.citations || [],
            created_at: new Date().toISOString(),
            confidence: payload.confidence || null,
            feedback: null,
            isTyping: false,
          };
          break;
        }
      }
      this.state.isStreaming = false;
      this._applyLeadPrompt(payload.metadata.lead_capture || null);
      this._render();
    } catch (error) {
      this.state.isStreaming = false;
      this._setError(error.message || "Could not regenerate the answer.");
    }
  }

  async submitFeedback(messageId, value) {
    if (!this.state.currentSessionId) {
      return;
    }
    try {
      await this.api.submitFeedback({
        sessionId: this.state.currentSessionId,
        messageId: messageId,
        value: value,
        category: value === "up" ? "useful" : "not_grounded",
      });
      this.state.messages = this.state.messages.map(function (message) {
        if (message.id === messageId) {
          message.feedback = value;
        }
        return message;
      });
      this._render();
    } catch (error) {
      this._setError(error.message || "Feedback could not be submitted.");
    }
  }

  openLeadForm() {
    this.state.showLeadForm = true;
    this.state.leadPromptTitle = "Talk to our team";
    this.state.leadPromptMessage =
      this.state.leadPromptMessage ||
      this.publicSettings.lead_capture.custom_form_message ||
      "Share your details and our team will follow up.";
    this._render();
  }

  closeLeadForm() {
    if (this.publicSettings.lead_capture.force_before_chat && !this.state.messages.length) {
      return;
    }
    this.state.showLeadForm = false;
    this._render();
  }

  updateLeadField(key, event) {
    this.state.leadValues[key] = event.target.value;
  }

  async submitLead() {
    if (this.state.isSubmittingLead) {
      return;
    }
    this.state.isSubmittingLead = true;
    this._render();
    try {
      await this.api.submitLead({
        sessionId: this.state.currentSessionId,
        name: this.state.leadValues.name,
        email: this.state.leadValues.email,
        phone: this.state.leadValues.phone,
        company: this.state.leadValues.company,
        useCase: this.state.leadValues.useCase,
        message: this.state.leadValues.message,
        scheduleCallRequested: false,
      });
      this.api.trackEvent("lead_submitted", {
        sessionId: this.state.currentSessionId,
        metadata: {
          source: "widget",
        },
      }).catch(function () {
        return null;
      });
      this.state.isSubmittingLead = false;
      this.state.showLeadForm = false;
      this.state.messages.push({
        id: "lead-confirmation-" + Date.now(),
        role: "assistant",
        content:
          this.publicSettings.lead_capture.auto_response_message ||
          "Thanks, our team will reach out soon.",
        citations: [],
        created_at: new Date().toISOString(),
        confidence: null,
        feedback: null,
        isTyping: false,
      });
      this._render();
    } catch (error) {
      this.state.isSubmittingLead = false;
      this._setError(error.message || "Lead form could not be submitted.");
    }
  }

  toggleVoiceInput() {
    if (!this.state.voiceInputEnabled) {
      return;
    }
    if (this.state.isRecording) {
      this.voiceManager.stopInput();
      return;
    }
    this._setError("");
    this.voiceManager.startInput({
      onTranscript: (transcript) => {
        this.renderer.setComposerValue(transcript);
      },
      onStateChange: ({ isRecording }) => {
        this.state.isRecording = Boolean(isRecording);
        this._render();
      },
      onError: (error) => {
        this.state.isRecording = false;
        this._setError(error.message || "Voice recording failed.");
      },
    });
  }

  speakMessage(messageId, text) {
    if (!this.state.voiceOutputEnabled || !text) {
      return;
    }
    this.voiceManager.speak({
      messageId,
      text,
      voiceStyle: this.publicSettings.voice.voice_style,
      onStart: () => {
        this.state.speakingMessageId = messageId;
        this._render();
      },
      onEnd: () => {
        this.state.speakingMessageId = null;
        this._render();
      },
      onError: (error) => {
        this.state.speakingMessageId = null;
        this._setError(error.message || "Speech playback failed.");
      },
    });
  }

  stopSpeaking() {
    this.voiceManager.stopSpeaking();
    this.state.speakingMessageId = null;
    this._render();
  }
}
