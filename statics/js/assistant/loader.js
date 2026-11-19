const assistantScripts = [
  "/statics/js/assistant/text-utils.js",
  "/statics/js/assistant/knowledge-base.js",
  "/statics/js/assistant/intent-engine.js",
  "/statics/js/assistant/fitpath-client.js",
  "/statics/js/assistant/conversation-engine.js",
  "/statics/js/assistant/widget.js"
];

function loadClassicScript(source) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-assistant-source="${source}"]`);
    if (existing?.dataset.loaded === "true") {
      resolve();
      return;
    }
    const script = existing || document.createElement("script");
    script.src = source;
    script.defer = true;
    script.dataset.assistantSource = source;
    script.addEventListener("load", () => {
      script.dataset.loaded = "true";
      resolve();
    }, { once: true });
    script.addEventListener("error", () => reject(new Error("assistant_script_failed")), { once: true });
    if (!existing) document.head.append(script);
  });
}

export async function initializeSmartAssistant(options = {}) {
  for (const source of assistantScripts) await loadClassicScript(source);
  return window.FitPathAssistant.mountWidget(options);
}
