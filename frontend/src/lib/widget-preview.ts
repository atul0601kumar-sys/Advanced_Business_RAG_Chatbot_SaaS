import type { PublicChatbotSettingsResponse } from "@/lib/settings";

export function buildEmbedScript(settings: PublicChatbotSettingsResponse): string {
  const lines = [
    "<script",
    `  src="${settings.embed.script_url}"`,
    `  data-workspace-id="${settings.workspace_id}"`,
    `  data-api-base-url="${settings.embed.api_base_url}"`,
    `  data-position="${settings.widget.position}"`,
    `  data-theme="${settings.widget.theme}"`,
    `  data-color="${settings.identity.brand_color_primary}"`,
    `  data-welcome-message="${escapeAttribute(settings.widget.welcome_popup_message || settings.identity.welcome_message)}"`,
    "></script>",
  ];

  return lines.join("\n");
}

export function buildPreviewDocument(settings: PublicChatbotSettingsResponse): string {
  const welcomeMessage = settings.widget.welcome_popup_message || settings.identity.welcome_message;
  const scriptAttributes = [
    `src="${escapeAttribute(settings.embed.script_url)}"`,
    `data-workspace-id="${escapeAttribute(settings.workspace_id)}"`,
    `data-api-base-url="${escapeAttribute(settings.embed.api_base_url)}"`,
    `data-position="${escapeAttribute(settings.widget.position)}"`,
    `data-theme="${escapeAttribute(settings.widget.theme)}"`,
    `data-color="${escapeAttribute(settings.identity.brand_color_primary)}"`,
    `data-welcome-message="${escapeAttribute(welcomeMessage)}"`,
  ].join("\n        ");

  const workspaceIdJson = JSON.stringify(settings.workspace_id);
  const brandColor = escapeHtml(settings.identity.brand_color_primary);
  const botName = escapeHtml(settings.identity.bot_name);
  const position = escapeHtml(settings.widget.position);

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      :root {
        color-scheme: dark;
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        min-height: 100vh;
        overflow: hidden;
        background:
          radial-gradient(circle at top left, rgba(14, 165, 233, 0.14), transparent 28%),
          linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 1));
        font-family: Arial, sans-serif;
      }

      .preview-shell {
        position: relative;
        min-height: 100vh;
        padding: 24px;
      }

      .preview-card {
        width: min(380px, calc(100vw - 48px));
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 24px;
        background: rgba(15, 23, 42, 0.78);
        color: rgba(226, 232, 240, 0.9);
        padding: 18px;
        backdrop-filter: blur(14px);
      }

      .preview-card strong {
        display: block;
        color: white;
        font-size: 16px;
        margin-bottom: 6px;
      }

      .preview-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 8px 12px;
        font-size: 11px;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: rgba(226, 232, 240, 0.72);
      }

      .preview-dot {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: ${brandColor};
      }

      .preview-placement {
        position: absolute;
        bottom: 22px;
        ${position === "left" ? "left: 22px;" : "right: 22px;"}
      }
    </style>
  </head>
  <body>
    <div class="preview-shell">
      <div class="preview-card">
        <span class="preview-badge"><span class="preview-dot"></span>${botName}</span>
        <strong>Live widget mount</strong>
        <span>The preview opens the real widget bundle and docks it on the ${position} side.</span>
      </div>
      <div class="preview-placement"></div>
      <script
        ${scriptAttributes}
      ><\/script>
      <script>
        (function () {
          var workspaceId = ${workspaceIdJson};
          var opened = false;
          var attempts = 0;

          function notify(status, error) {
            window.parent.postMessage(
              {
                source: "widget-preview",
                workspaceId: workspaceId,
                status: status,
                error: error || "",
              },
              "*",
            );
          }

          function tryOpenWidget() {
            attempts += 1;
            var host = document.querySelector("advanced-rag-widget");
            var root = host && host.shadowRoot;
            var launcher = root && root.querySelector(".abrag-launcher");

            if (launcher) {
              if (!opened) {
                opened = true;
                launcher.click();
              }
              notify("ready");
              return;
            }

            if (attempts > 120) {
              notify("error", "The widget loader timed out before the preview became interactive.");
              return;
            }

            window.setTimeout(tryOpenWidget, 100);
          }

          window.addEventListener("error", function (event) {
            notify("error", event.message || "The live widget preview crashed.");
          });

          window.setTimeout(tryOpenWidget, 100);
        })();
      <\/script>
    </div>
  </body>
</html>`;
}

function escapeAttribute(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
