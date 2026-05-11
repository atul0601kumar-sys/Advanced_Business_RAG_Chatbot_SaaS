function hexToRgb(color) {
  var normalized = (color || "#0ea5e9").replace("#", "");
  if (normalized.length === 3) {
    normalized = normalized
      .split("")
      .map(function (part) {
        return part + part;
      })
      .join("");
  }
  var value = parseInt(normalized, 16);
  return {
    r: (value >> 16) & 255,
    g: (value >> 8) & 255,
    b: value & 255,
  };
}

export function createStyleElement(config) {
  var style = document.createElement("style");
  var primary = hexToRgb(config.primaryColor);
  var isDark = config.theme === "dark";
  style.textContent = `
    :host {
      all: initial;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color-scheme: ${isDark ? "dark" : "light"};
      --abrag-primary: ${config.primaryColor};
      --abrag-primary-rgb: ${primary.r}, ${primary.g}, ${primary.b};
      --abrag-secondary: ${config.secondaryColor};
      --abrag-surface: ${isDark ? "#07111f" : "#ffffff"};
      --abrag-surface-muted: ${isDark ? "rgba(148, 163, 184, 0.12)" : "#f8fafc"};
      --abrag-border: ${isDark ? "rgba(148, 163, 184, 0.18)" : "rgba(15, 23, 42, 0.12)"};
      --abrag-text: ${isDark ? "#e2e8f0" : "#0f172a"};
      --abrag-subtle: ${isDark ? "#94a3b8" : "#475569"};
      --abrag-shadow: 0 24px 80px rgba(15, 23, 42, 0.28);
      position: fixed;
      z-index: 2147483647;
      ${config.position === "left" ? "left: 20px;" : "right: 20px;"}
      bottom: 20px;
      line-height: 1.4;
    }

    *, *::before, *::after {
      box-sizing: border-box;
      font-family: inherit;
    }

    button, input, textarea {
      font: inherit;
    }

    .abrag-root {
      position: relative;
    }

    .abrag-launcher {
      width: 64px;
      height: 64px;
      border-radius: 999px;
      border: 0;
      background: linear-gradient(135deg, var(--abrag-primary), var(--abrag-secondary));
      color: white;
      cursor: pointer;
      box-shadow: var(--abrag-shadow);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: transform 180ms ease, box-shadow 180ms ease, opacity 180ms ease;
      opacity: 1;
    }

    .abrag-launcher:hover,
    .abrag-launcher:focus-visible {
      transform: translateY(-1px) scale(1.02);
      outline: none;
    }

    .abrag-launcher-badge {
      position: absolute;
      bottom: 78px;
      ${config.position === "left" ? "left: 0;" : "right: 0;"}
      max-width: 280px;
      padding: 12px 14px;
      border-radius: 18px;
      background: var(--abrag-surface);
      border: 1px solid var(--abrag-border);
      color: var(--abrag-text);
      box-shadow: var(--abrag-shadow);
      opacity: 0;
      pointer-events: none;
      transform: translateY(10px);
      transition: opacity 180ms ease, transform 180ms ease;
    }

    .abrag-launcher-badge[data-visible="true"] {
      opacity: 1;
      transform: translateY(0);
    }

    .abrag-panel {
      position: absolute;
      bottom: 82px;
      ${config.position === "left" ? "left: 0;" : "right: 0;"}
      width: min(420px, calc(100vw - 24px));
      height: min(720px, calc(100vh - 112px));
      border-radius: 28px;
      background: var(--abrag-surface);
      color: var(--abrag-text);
      border: 1px solid var(--abrag-border);
      box-shadow: var(--abrag-shadow);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      opacity: 0;
      pointer-events: none;
      transform: translateY(12px) scale(0.98);
      transition: opacity 220ms ease, transform 220ms ease;
    }

    .abrag-panel[data-open="true"] {
      opacity: 1;
      pointer-events: auto;
      transform: translateY(0) scale(1);
    }

    .abrag-header {
      padding: 18px 18px 16px;
      background: linear-gradient(135deg, rgba(var(--abrag-primary-rgb), 0.16), rgba(var(--abrag-primary-rgb), 0.04));
      border-bottom: 1px solid var(--abrag-border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .abrag-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .abrag-avatar {
      width: 42px;
      height: 42px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(var(--abrag-primary-rgb), 0.18);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: var(--abrag-primary);
      font-weight: 700;
      flex-shrink: 0;
    }

    .abrag-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    .abrag-title {
      font-size: 15px;
      font-weight: 700;
      color: var(--abrag-text);
      margin: 0;
    }

    .abrag-subtitle {
      margin: 2px 0 0;
      font-size: 12px;
      color: var(--abrag-subtle);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .abrag-close {
      border: 0;
      background: transparent;
      color: var(--abrag-subtle);
      width: 36px;
      height: 36px;
      border-radius: 999px;
      cursor: pointer;
    }

    .abrag-banner,
    .abrag-error {
      margin: 10px 16px 0;
      padding: 10px 12px;
      border-radius: 14px;
      font-size: 12px;
      border: 1px solid var(--abrag-border);
    }

    .abrag-banner {
      background: rgba(245, 158, 11, 0.12);
      color: ${isDark ? "#fcd34d" : "#92400e"};
    }

    .abrag-error {
      background: rgba(239, 68, 68, 0.12);
      color: ${isDark ? "#fca5a5" : "#991b1b"};
    }

    .abrag-messages {
      flex: 1;
      overflow: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background:
        radial-gradient(circle at top, rgba(var(--abrag-primary-rgb), 0.08), transparent 38%),
        var(--abrag-surface);
    }

    .abrag-message {
      max-width: 88%;
      padding: 12px 14px;
      border-radius: 18px;
      font-size: 14px;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .abrag-message[data-role="assistant"] {
      align-self: flex-start;
      background: var(--abrag-surface-muted);
      border-bottom-left-radius: 8px;
    }

    .abrag-message[data-role="user"] {
      align-self: flex-end;
      background: linear-gradient(135deg, var(--abrag-primary), var(--abrag-secondary));
      color: white;
      border-bottom-right-radius: 8px;
    }

    .abrag-meta {
      margin-top: 8px;
      font-size: 11px;
      color: var(--abrag-subtle);
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .abrag-citations {
      margin-top: 8px;
      display: grid;
      gap: 6px;
    }

    .abrag-citation {
      padding: 8px 10px;
      border-radius: 12px;
      font-size: 12px;
      background: rgba(var(--abrag-primary-rgb), 0.08);
      border: 1px solid rgba(var(--abrag-primary-rgb), 0.12);
    }

    .abrag-actions {
      display: flex;
      gap: 8px;
      margin-top: 8px;
      flex-wrap: wrap;
    }

    .abrag-chip {
      border: 1px solid var(--abrag-border);
      background: transparent;
      color: var(--abrag-subtle);
      padding: 6px 10px;
      border-radius: 999px;
      cursor: pointer;
      font-size: 12px;
    }

    .abrag-chip[data-active="true"] {
      color: var(--abrag-primary);
      border-color: rgba(var(--abrag-primary-rgb), 0.28);
      background: rgba(var(--abrag-primary-rgb), 0.08);
    }

    .abrag-lead-card {
      border: 1px solid var(--abrag-border);
      background: var(--abrag-surface-muted);
      border-radius: 22px;
      padding: 14px;
      display: grid;
      gap: 10px;
    }

    .abrag-lead-grid {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .abrag-lead-grid .abrag-field--full {
      grid-column: 1 / -1;
    }

    .abrag-field {
      display: grid;
      gap: 6px;
    }

    .abrag-label {
      font-size: 12px;
      color: var(--abrag-subtle);
    }

    .abrag-input,
    .abrag-textarea {
      width: 100%;
      border: 1px solid var(--abrag-border);
      background: ${isDark ? "rgba(15, 23, 42, 0.7)" : "white"};
      color: var(--abrag-text);
      border-radius: 14px;
      padding: 10px 12px;
    }

    .abrag-textarea {
      min-height: 92px;
      resize: vertical;
    }

    .abrag-footer {
      border-top: 1px solid var(--abrag-border);
      padding: 14px 16px 16px;
      display: grid;
      gap: 10px;
      background: var(--abrag-surface);
    }

    .abrag-input-shell {
      display: flex;
      gap: 10px;
      align-items: flex-end;
    }

    .abrag-composer {
      flex: 1;
      min-height: 48px;
      max-height: 140px;
    }

    .abrag-primary-btn,
    .abrag-secondary-btn {
      border-radius: 14px;
      padding: 12px 14px;
      cursor: pointer;
      border: 0;
      transition: transform 160ms ease, opacity 160ms ease;
    }

    .abrag-primary-btn {
      background: linear-gradient(135deg, var(--abrag-primary), var(--abrag-secondary));
      color: white;
      min-width: 92px;
    }

    .abrag-secondary-btn {
      background: var(--abrag-surface-muted);
      color: var(--abrag-subtle);
      border: 1px solid var(--abrag-border);
    }

    .abrag-primary-btn:disabled,
    .abrag-secondary-btn:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }

    .abrag-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
    }

    .abrag-branding {
      font-size: 11px;
      color: var(--abrag-subtle);
    }

    .abrag-dot-typing {
      display: inline-flex;
      gap: 4px;
      align-items: center;
      min-height: 18px;
    }

    .abrag-dot-typing span {
      width: 7px;
      height: 7px;
      border-radius: 999px;
      background: var(--abrag-subtle);
      animation: abragPulse 1.1s infinite ease-in-out;
    }

    .abrag-dot-typing span:nth-child(2) {
      animation-delay: 0.15s;
    }

    .abrag-dot-typing span:nth-child(3) {
      animation-delay: 0.3s;
    }

    @keyframes abragPulse {
      0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
      40% { opacity: 1; transform: translateY(-2px); }
    }

    @media (max-width: 640px) {
      :host {
        left: 12px !important;
        right: 12px !important;
        bottom: 12px;
      }

      .abrag-launcher {
        width: 58px;
        height: 58px;
      }

      .abrag-panel {
        width: calc(100vw - 24px);
        height: min(78vh, 680px);
        ${config.position === "left" ? "left: 0;" : "right: 0;"}
      }

      .abrag-lead-grid {
        grid-template-columns: 1fr;
      }
    }
  `;
  return style;
}

