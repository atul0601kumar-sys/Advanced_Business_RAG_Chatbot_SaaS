function buildHeaders(token) {
  var headers = new Headers({
    "Content-Type": "application/json",
    "X-Widget-Request": "1",
  });
  if (token) {
    headers.set("X-Widget-Token", token);
  }
  return headers;
}

async function requestJson(url, options) {
  var response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new Error("Network request failed.");
  }

  if (!response.ok) {
    var detail = "Request failed.";
    try {
      var payload = await response.json();
      detail = payload.detail || payload.message || detail;
    } catch (error) {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function parseFrame(frame) {
  var lines = frame
    .split(/\r?\n/)
    .map(function (line) {
      return line.trim();
    })
    .filter(Boolean);
  var eventLine = lines.find(function (line) {
    return line.indexOf("event:") === 0;
  });
  var dataLine = lines.find(function (line) {
    return line.indexOf("data:") === 0;
  });
  if (!eventLine || !dataLine) {
    return null;
  }
  return {
    event: eventLine.replace("event:", "").trim(),
    data: JSON.parse(dataLine.replace("data:", "").trim()),
  };
}

export class WidgetApiClient {
  constructor(options) {
    this.apiBaseUrl = options.apiBaseUrl.replace(/\/$/, "");
    this.workspaceId = options.workspaceId;
    this.authToken = null;
  }

  setAuthToken(token) {
    this.authToken = token;
  }

  async fetchPublicSettings() {
    var url = this.apiBaseUrl + "/api/v1/settings/public?workspace_id=" + encodeURIComponent(this.workspaceId);
    var response = await requestJson(url, {
      method: "GET",
      headers: new Headers({
        "X-Widget-Request": "1",
      }),
    });
    this.authToken = response.embed.auth_token;
    return response;
  }

  async createSession(title) {
    return requestJson(this.apiBaseUrl + "/api/v1/chat/session", {
      method: "POST",
      headers: buildHeaders(this.authToken),
      body: JSON.stringify({
        workspace_id: this.workspaceId,
        title: title || null,
        channel: "widget",
      }),
    });
  }

  async fetchHistory(sessionId) {
    return requestJson(this.apiBaseUrl + "/api/v1/chat/history/" + encodeURIComponent(sessionId), {
      method: "GET",
      headers: new Headers({
        "X-Widget-Request": "1",
        "X-Widget-Token": this.authToken || "",
      }),
    });
  }

  async regenerate(sessionId, mode) {
    return requestJson(this.apiBaseUrl + "/api/v1/chat/regenerate", {
      method: "POST",
      headers: buildHeaders(this.authToken),
      body: JSON.stringify({
        session_id: sessionId,
        mode: mode || "detailed",
      }),
    });
  }

  async stop(sessionId, generationId) {
    return requestJson(this.apiBaseUrl + "/api/v1/chat/stop", {
      method: "POST",
      headers: buildHeaders(this.authToken),
      body: JSON.stringify({
        session_id: sessionId,
        generation_id: generationId || null,
      }),
    });
  }

  async submitLead(payload) {
    return requestJson(this.apiBaseUrl + "/api/v1/leads/create", {
      method: "POST",
      headers: buildHeaders(this.authToken),
      body: JSON.stringify({
        workspace_id: this.workspaceId,
        chat_session_id: payload.sessionId || null,
        name: payload.name,
        email: payload.email,
        phone: payload.phone || null,
        company: payload.company || null,
        use_case: payload.useCase || null,
        message: payload.message || null,
        source: "widget",
        schedule_call_requested: Boolean(payload.scheduleCallRequested),
      }),
    });
  }

  async submitFeedback(payload) {
    return requestJson(this.apiBaseUrl + "/api/v1/feedback", {
      method: "POST",
      headers: buildHeaders(this.authToken),
      body: JSON.stringify({
        session_id: payload.sessionId,
        message_id: payload.messageId,
        value: payload.value,
        category: payload.category || null,
        comment: payload.comment || null,
      }),
    });
  }

  async trackEvent(eventName, payload) {
    return requestJson(this.apiBaseUrl + "/api/v1/widget/event", {
      method: "POST",
      headers: buildHeaders(this.authToken),
      body: JSON.stringify({
        workspace_id: this.workspaceId,
        session_id: payload && payload.sessionId ? payload.sessionId : null,
        event: eventName,
        metadata: payload && payload.metadata ? payload.metadata : {},
      }),
    });
  }

  async streamMessage(payload, handlers) {
    var response;
    try {
      response = await fetch(this.apiBaseUrl + "/api/v1/chat/message", {
        method: "POST",
        headers: buildHeaders(this.authToken),
        body: JSON.stringify({
          session_id: payload.sessionId,
          message: payload.message,
          mode: payload.mode || "detailed",
        }),
      });
    } catch (error) {
      throw new Error("Network request failed.");
    }

    if (!response.ok || !response.body) {
      var detail = "Streaming request failed.";
      try {
        var data = await response.json();
        detail = data.detail || data.message || detail;
      } catch (error) {
        detail = response.statusText || detail;
      }
      throw new Error(detail);
    }

    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = "";

    while (true) {
      var chunk = await reader.read();
      if (chunk.done) {
        break;
      }
      buffer += decoder.decode(chunk.value, { stream: true });
      var frames = buffer.split("\n\n");
      buffer = frames.pop() || "";
      for (var index = 0; index < frames.length; index += 1) {
        var parsed = parseFrame(frames[index]);
        if (!parsed) {
          continue;
        }
        if (parsed.event === "start" && handlers.onStart) {
          handlers.onStart(parsed.data);
        }
        if (parsed.event === "token" && handlers.onToken) {
          handlers.onToken(parsed.data.delta || "");
        }
        if (parsed.event === "complete" && handlers.onComplete) {
          handlers.onComplete(parsed.data);
        }
      }
    }

    if (buffer.trim()) {
      var trailing = parseFrame(buffer);
      if (trailing && trailing.event === "complete" && handlers.onComplete) {
        handlers.onComplete(trailing.data);
      }
    }
  }
}

