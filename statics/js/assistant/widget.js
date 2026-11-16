(function (root) {
  "use strict";

  const assistant = root.FitPathAssistant = root.FitPathAssistant || {};

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function mountWidget(options) {
    if (document.querySelector("[data-smart-assistant]")) return null;
    const settings = options || {};
    const client = settings.client || new assistant.FitPathClient({ offline: settings.offline });
    const engine = settings.engine || new assistant.ConversationEngine({ client });
    const host = element("section", "fp-assistant");
    host.dataset.smartAssistant = "";

    const launcher = element("button", "fp-assistant-launcher");
    launcher.type = "button";
    launcher.setAttribute("aria-label", "Abrir Asistente de IA");
    launcher.setAttribute("aria-expanded", "false");
    launcher.innerHTML = '<span aria-hidden="true">✦</span><span>Asistente de IA</span>';

    const panel = element("div", "fp-assistant-panel");
    panel.hidden = !settings.expanded;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Asistente de IA de FitPath");

    const header = element("header", "fp-assistant-header");
    const heading = element("div", "fp-assistant-heading");
    heading.append(element("span", "fp-assistant-mark", "✦"));
    const title = element("span");
    title.append(element("strong", "", "Asistente de IA"), element("small", "", "Orientación general y acceso a FitPath"));
    heading.append(title);
    const close = element("button", "fp-assistant-close", "×");
    close.type = "button";
    close.setAttribute("aria-label", "Cerrar asistente");
    header.append(heading, close);

    const status = element("p", `fp-assistant-status ${client.offline ? "is-offline" : ""}`);
    status.append(element("span", "", ""), document.createTextNode(
      client.offline ? "Modo informativo · backend desconectado" : "Modo FitPath · operaciones verificadas por backend"
    ));

    const messages = element("div", "fp-assistant-messages");
    messages.setAttribute("role", "log");
    messages.setAttribute("aria-live", "polite");
    messages.setAttribute("aria-relevant", "additions");

    const suggestions = element("div", "fp-assistant-suggestions");
    suggestions.setAttribute("aria-label", "Sugerencias");

    const form = element("form", "fp-assistant-form");
    const label = element("label", "fp-sr-only", "Escribí tu consulta");
    const input = element("textarea", "fp-assistant-input");
    input.rows = 1;
    input.maxLength = 500;
    input.placeholder = "Preguntá sobre entrenamiento o FitPath…";
    label.htmlFor = "fitpath-assistant-input";
    input.id = "fitpath-assistant-input";
    const submit = element("button", "fp-assistant-send", "Enviar");
    submit.type = "submit";
    form.append(label, input, submit);

    const disclaimer = element("p", "fp-assistant-disclaimer", "Información general. No reemplaza asesoramiento médico o nutricional profesional.");
    panel.append(header, status, messages, suggestions, form, disclaimer);
    host.append(launcher, panel);
    (settings.container || document.body).append(host);

    function setExpanded(expanded) {
      panel.hidden = !expanded;
      launcher.setAttribute("aria-expanded", String(expanded));
      if (expanded) input.focus();
    }

    function addMessage(role, content) {
      const row = element("div", `fp-assistant-message is-${role}`);
      const bubble = element("p", "", content);
      row.append(bubble);
      messages.append(row);
      messages.scrollTop = messages.scrollHeight;
      return row;
    }

    function renderSuggestions(items) {
      suggestions.replaceChildren();
      (items || []).slice(0, 4).forEach((suggestion) => {
        const button = element("button", "fp-assistant-suggestion", suggestion);
        button.type = "button";
        button.addEventListener("click", () => sendMessage(suggestion));
        suggestions.append(button);
      });
    }

    function renderActions(actions) {
      (actions || []).forEach((action) => {
        const button = element("button", "fp-assistant-action", action.label);
        button.type = "button";
        button.addEventListener("click", () => {
          if (root.location?.protocol === "file:") {
            addMessage("assistant", "La navegación real se habilita al ejecutar FitPath con Flask. Esta demo sigue disponible en modo informativo.");
            return;
          }
          root.location.assign(action.href);
        });
        messages.append(button);
      });
    }

    async function sendMessage(value) {
      const message = String(value || input.value || "").trim();
      if (!message) return;
      addMessage("user", message);
      input.value = "";
      submit.disabled = true;
      renderSuggestions([]);
      const indicator = addMessage("thinking", "Analizando tu consulta…");
      try {
        const response = await engine.respond(message);
        indicator.remove();
        addMessage("assistant", response.message);
        renderActions(response.actions);
        renderSuggestions(response.suggestions);
        if (response.backendAvailable === false) {
          status.classList.add("is-offline");
          status.lastChild.textContent = " Operaciones reales temporalmente deshabilitadas";
        }
      } catch (_error) {
        indicator.remove();
        addMessage("assistant", "No pude procesar la consulta. Probá reformularla en una frase breve.");
      } finally {
        submit.disabled = false;
        input.focus();
      }
    }

    launcher.addEventListener("click", () => setExpanded(panel.hidden));
    close.addEventListener("click", () => setExpanded(false));
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      sendMessage();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });

    addMessage("assistant", "¡Hola! Puedo ayudarte con entrenamiento, nutrición general y funciones de FitPath. ¿Qué querés consultar?");
    renderSuggestions(["Rutina para principiantes", "¿Cómo ganar fuerza?", "Nutrición general", "Ver clases"]);
    if (settings.expanded) launcher.setAttribute("aria-expanded", "true");
    return { engine, client, sendMessage, setExpanded };
  }

  assistant.mountWidget = mountWidget;
})(typeof window !== "undefined" ? window : globalThis);
