function createElement(tag, className, text) {
  var element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (typeof text === "string") {
    element.textContent = text;
  }
  return element;
}

function formatTimestamp(value) {
  if (!value) {
    return "";
  }
  try {
    return new Date(value).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch (error) {
    return "";
  }
}

function initials(text) {
  return (text || "AI")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(function (part) {
      return part.charAt(0).toUpperCase();
    })
    .join("");
}

export class WidgetRenderer {
  constructor(shadowRoot, callbacks) {
    this.shadowRoot = shadowRoot;
    this.callbacks = callbacks;
    this.state = null;
    this.isFocused = false;
    this.elements = {};
    this._build();
  }

  _build() {
    var root = createElement("div", "abrag-root");
    var launcherBadge = createElement("div", "abrag-launcher-badge");
    launcherBadge.setAttribute("aria-hidden", "true");

    var launcher = createElement("button", "abrag-launcher");
    launcher.type = "button";
    launcher.setAttribute("aria-label", "Open chat assistant");
    launcher.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 10h10M7 14h7m-8 6 2.1-3.15c.24-.36.36-.54.52-.67.14-.12.31-.21.48-.27.2-.07.41-.07.85-.07H18a3 3 0 0 0 3-3V7a3 3 0 0 0-3-3H6A3 3 0 0 0 3 7v6a3 3 0 0 0 3 3v4Z" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    launcher.addEventListener("click", this.callbacks.onToggle);

    var panel = createElement("section", "abrag-panel");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "false");
    panel.setAttribute("aria-label", "Chat assistant");

    var header = createElement("div", "abrag-header");
    var brand = createElement("div", "abrag-brand");
    var avatar = createElement("div", "abrag-avatar");
    var avatarImage = document.createElement("img");
    avatarImage.alt = "";
    avatarImage.hidden = true;
    avatar.appendChild(avatarImage);
    var brandText = createElement("div");
    var title = createElement("p", "abrag-title");
    var subtitle = createElement("p", "abrag-subtitle");
    brandText.appendChild(title);
    brandText.appendChild(subtitle);
    brand.appendChild(avatar);
    brand.appendChild(brandText);
    var closeButton = createElement("button", "abrag-close", "✕");
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", "Close chat");
    closeButton.addEventListener("click", this.callbacks.onToggle);
    header.appendChild(brand);
    header.appendChild(closeButton);

    var offlineBanner = createElement("div", "abrag-banner");
    offlineBanner.textContent = "You are offline";
    offlineBanner.hidden = true;

    var errorBanner = createElement("div", "abrag-error");
    errorBanner.hidden = true;

    var messages = createElement("div", "abrag-messages");
    messages.setAttribute("role", "log");
    messages.setAttribute("aria-live", "polite");

    var footer = createElement("div", "abrag-footer");
    var inputShell = createElement("div", "abrag-input-shell");
    var composer = document.createElement("textarea");
    composer.className = "abrag-input abrag-composer";
    composer.placeholder = "Ask a grounded question...";
    composer.setAttribute("aria-label", "Message");
    composer.rows = 1;
    composer.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        this.callbacks.onSubmitMessage();
      }
      if (event.key === "Escape" && this.state && this.state.isOpen) {
        this.callbacks.onToggle();
      }
    });
    var sendButton = createElement("button", "abrag-primary-btn", "Send");
    sendButton.type = "button";
    sendButton.addEventListener("click", this.callbacks.onSubmitMessage);
    var voiceButton = createElement("button", "abrag-secondary-btn", "Voice");
    voiceButton.type = "button";
    voiceButton.addEventListener("click", this.callbacks.onToggleVoiceInput);
    inputShell.appendChild(composer);
    inputShell.appendChild(voiceButton);
    inputShell.appendChild(sendButton);

    var actionRow = createElement("div", "abrag-row");
    var utilityRow = createElement("div");
    var stopButton = createElement("button", "abrag-secondary-btn", "Stop");
    stopButton.type = "button";
    stopButton.addEventListener("click", this.callbacks.onStop);
    var leadButton = createElement("button", "abrag-secondary-btn", "Contact team");
    leadButton.type = "button";
    leadButton.addEventListener("click", this.callbacks.onOpenLeadForm);
    utilityRow.appendChild(stopButton);
    utilityRow.appendChild(leadButton);
    var branding = createElement("div", "abrag-branding", "Powered by Advanced Business RAG");
    actionRow.appendChild(utilityRow);
    actionRow.appendChild(branding);

    footer.appendChild(inputShell);
    footer.appendChild(actionRow);

    panel.appendChild(header);
    panel.appendChild(offlineBanner);
    panel.appendChild(errorBanner);
    panel.appendChild(messages);
    panel.appendChild(footer);

    root.appendChild(launcherBadge);
    root.appendChild(panel);
    root.appendChild(launcher);
    this.shadowRoot.appendChild(root);

    this.elements = {
      root: root,
      launcher: launcher,
      launcherBadge: launcherBadge,
      panel: panel,
      title: title,
      subtitle: subtitle,
      avatar: avatar,
      avatarImage: avatarImage,
      messages: messages,
      offlineBanner: offlineBanner,
      errorBanner: errorBanner,
      composer: composer,
      sendButton: sendButton,
      voiceButton: voiceButton,
      stopButton: stopButton,
      leadButton: leadButton,
      branding: branding,
    };
  }

  focusComposer() {
    this.elements.composer.focus();
  }

  setComposerValue(value) {
    this.elements.composer.value = value;
  }

  getComposerValue() {
    return this.elements.composer.value;
  }

  clearComposer() {
    this.elements.composer.value = "";
  }

  render(state) {
    this.state = state;
    this.elements.panel.dataset.open = state.isOpen ? "true" : "false";
    this.elements.launcherBadge.dataset.visible = !state.isOpen && state.showLauncherBadge ? "true" : "false";
    this.elements.launcherBadge.textContent = state.launcherBadgeText || "";
    this.elements.offlineBanner.hidden = !state.isOffline;
    this.elements.errorBanner.hidden = !state.error;
    this.elements.errorBanner.textContent = state.error || "";
    this.elements.title.textContent = state.botName;
    this.elements.subtitle.textContent = state.tagline || "Grounded answers from your business knowledge";
    this.elements.branding.hidden = !state.showBranding;
    this.elements.leadButton.hidden = !state.leadEnabled;
    this.elements.stopButton.hidden = !state.isStreaming;
    this.elements.sendButton.disabled = state.isStreaming || state.isOffline;
    this.elements.composer.disabled = state.isStreaming || state.isOffline;
    this.elements.voiceButton.hidden = !state.voiceInputEnabled;
    this.elements.voiceButton.disabled = state.isOffline;
    this.elements.voiceButton.textContent = state.isRecording ? "Stop voice" : "Voice";
    this.elements.launcher.disabled = !state.isReady;
    this.elements.leadButton.disabled = state.isStreaming;
    this.elements.stopButton.disabled = !state.isStreaming;
    if (state.avatarUrl) {
      this.elements.avatarImage.src = state.avatarUrl;
      this.elements.avatarImage.hidden = false;
      this.elements.avatar.textContent = "";
    } else {
      this.elements.avatarImage.hidden = true;
      this.elements.avatar.textContent = initials(state.botName);
    }
    this._renderMessages(state);
  }

  _renderMessages(state) {
    var container = this.elements.messages;
    container.innerHTML = "";

    if (!state.messages.length) {
      var welcome = createElement("div", "abrag-message");
      welcome.dataset.role = "assistant";
      welcome.textContent = state.welcomeMessage;
      container.appendChild(welcome);
    }

    for (var index = 0; index < state.messages.length; index += 1) {
      var message = state.messages[index];
      var bubble = createElement("div", "abrag-message");
      bubble.dataset.role = message.role;
      if (message.isTyping) {
        var dots = createElement("div", "abrag-dot-typing");
        dots.innerHTML = "<span></span><span></span><span></span>";
        bubble.appendChild(dots);
      } else {
        bubble.textContent = message.content || "";
      }

      if (message.citations && message.citations.length) {
        var citations = createElement("div", "abrag-citations");
        for (var citationIndex = 0; citationIndex < message.citations.length; citationIndex += 1) {
          var citation = message.citations[citationIndex];
          var citationCard = createElement("div", "abrag-citation");
          var label = [];
          if (citation.file_name) {
            label.push(citation.file_name);
          }
          if (citation.page_number) {
            label.push("p. " + citation.page_number);
          }
          if (citation.url) {
            label.push(citation.url);
          }
          citationCard.textContent = (label.join(" • ") || "Source") + ": " + (citation.chunk_preview || "");
          citations.appendChild(citationCard);
        }
        bubble.appendChild(citations);
      }

      var meta = createElement("div", "abrag-meta");
      if (message.created_at) {
        meta.appendChild(createElement("span", "", formatTimestamp(message.created_at)));
      }
      if (message.confidence) {
        meta.appendChild(createElement("span", "", "Confidence: " + message.confidence));
      }
      bubble.appendChild(meta);

      if (message.role === "assistant" && message.id && !message.isTyping) {
        var actions = createElement("div", "abrag-actions");
        var upButton = createElement("button", "abrag-chip", "Helpful");
        upButton.type = "button";
        upButton.dataset.active = message.feedback === "up" ? "true" : "false";
        upButton.addEventListener("click", this.callbacks.onFeedback.bind(null, message.id, "up"));
        var downButton = createElement("button", "abrag-chip", "Needs work");
        downButton.type = "button";
        downButton.dataset.active = message.feedback === "down" ? "true" : "false";
        downButton.addEventListener("click", this.callbacks.onFeedback.bind(null, message.id, "down"));
        actions.appendChild(upButton);
        actions.appendChild(downButton);

        if (index === state.messages.length - 1) {
          var regenerateButton = createElement("button", "abrag-chip", "Regenerate");
          regenerateButton.type = "button";
          regenerateButton.addEventListener("click", this.callbacks.onRegenerate);
          actions.appendChild(regenerateButton);
        }
        if (state.voiceOutputEnabled) {
          var voiceAction = createElement(
            "button",
            "abrag-chip",
            state.speakingMessageId === message.id ? "Stop audio" : "Play audio",
          );
          voiceAction.type = "button";
          voiceAction.addEventListener(
            "click",
            state.speakingMessageId === message.id
              ? this.callbacks.onStopSpeaking
              : this.callbacks.onSpeakMessage.bind(null, message.id, message.content),
          );
          actions.appendChild(voiceAction);
        }
        bubble.appendChild(actions);
      }

      container.appendChild(bubble);
    }

    if (state.showLeadForm) {
      container.appendChild(this._buildLeadForm(state));
    }

    requestAnimationFrame(function () {
      container.scrollTop = container.scrollHeight;
    });
  }

  _buildLeadForm(state) {
    var card = createElement("div", "abrag-lead-card");
    card.appendChild(createElement("strong", "", state.leadPromptTitle || "Talk to our team"));
    if (state.leadPromptMessage) {
      card.appendChild(createElement("p", "", state.leadPromptMessage));
    }

    var grid = createElement("div", "abrag-lead-grid");
    var fields = state.leadFields || ["name", "email"];
    var leadValues = state.leadValues || {};

    var definitions = [
      { key: "name", label: "Name", type: "text", full: false },
      { key: "email", label: "Email", type: "email", full: false },
      { key: "phone", label: "Phone", type: "tel", full: false },
      { key: "company", label: "Company", type: "text", full: false },
      { key: "useCase", label: "Use case", type: "text", full: false },
      { key: "message", label: "Message", type: "textarea", full: true },
    ];

    for (var index = 0; index < definitions.length; index += 1) {
      var field = definitions[index];
      if (fields.indexOf(field.key) === -1 && field.key !== "message") {
        continue;
      }
      var shell = createElement("label", "abrag-field" + (field.full ? " abrag-field--full" : ""));
      shell.appendChild(createElement("span", "abrag-label", field.label));
      var control;
      if (field.type === "textarea") {
        control = document.createElement("textarea");
        control.className = "abrag-textarea";
      } else {
        control = document.createElement("input");
        control.className = "abrag-input";
        control.type = field.type;
      }
      control.value = leadValues[field.key] || "";
      control.addEventListener("input", this.callbacks.onLeadFieldChange.bind(null, field.key));
      shell.appendChild(control);
      grid.appendChild(shell);
    }

    card.appendChild(grid);

    var row = createElement("div", "abrag-row");
    var submit = createElement("button", "abrag-primary-btn", state.isSubmittingLead ? "Sending..." : "Submit");
    submit.type = "button";
    submit.disabled = state.isSubmittingLead;
    submit.addEventListener("click", this.callbacks.onLeadSubmit);
    var cancel = createElement("button", "abrag-secondary-btn", "Later");
    cancel.type = "button";
    cancel.disabled = state.isSubmittingLead;
    cancel.addEventListener("click", this.callbacks.onCloseLeadForm);
    row.appendChild(submit);
    row.appendChild(cancel);
    card.appendChild(row);
    return card;
  }
}
