import { WidgetCore } from "./widget_core.js";

function readScriptConfig(scriptElement) {
  var dataset = scriptElement.dataset || {};
  var workspaceId = dataset.workspaceId;
  if (!workspaceId) {
    throw new Error("The widget script requires data-workspace-id.");
  }

  return {
    workspaceId: workspaceId,
    apiBaseUrl: dataset.apiBaseUrl || new URL(scriptElement.src).origin,
    overrides: {
      position: dataset.position || null,
      theme: dataset.theme || null,
      color: dataset.color || null,
      welcomeMessage: dataset.welcomeMessage || null,
    },
  };
}

export function bootstrap(scriptElement) {
  if (!scriptElement || scriptElement.__advancedRagWidgetMounted) {
    return;
  }
  scriptElement.__advancedRagWidgetMounted = true;
  var config = readScriptConfig(scriptElement);
  var widget = new WidgetCore(scriptElement, config);
  widget.mount().catch(function (error) {
    console.error("Advanced Business RAG widget failed to mount.", error);
  });
}

