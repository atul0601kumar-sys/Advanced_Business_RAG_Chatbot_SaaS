function safeStorage() {
  try {
    return window.localStorage;
  } catch (error) {
    return null;
  }
}

export class SessionManager {
  constructor(workspaceId) {
    this.key = "advanced-rag-widget:" + workspaceId + ":session";
    this.storage = safeStorage();
  }

  getSessionId() {
    if (!this.storage) {
      return null;
    }
    return this.storage.getItem(this.key);
  }

  setSessionId(sessionId) {
    if (!this.storage) {
      return;
    }
    this.storage.setItem(this.key, sessionId);
  }

  clearSessionId() {
    if (!this.storage) {
      return;
    }
    this.storage.removeItem(this.key);
  }
}

