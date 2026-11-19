(function (root) {
  "use strict";

  const assistant = root.FitPathAssistant = root.FitPathAssistant || {};
  const knowledge = assistant.knowledge;
  const text = assistant.text;

  function choose(items, index) {
    return items?.length ? items[index % items.length] : "";
  }

  function unavailableMessage(reason) {
    if (reason === "authentication_required") return "Necesitás iniciar sesión en FitPath para consultar información real.";
    if (reason === "permission_denied") return "Tu cuenta no tiene permiso para realizar esa consulta.";
    if (reason === "unsupported_operation") return "Esa operación todavía no está habilitada por el backend de FitPath.";
    if (reason === "active_membership_required") return "Necesitás una membresía activa y vigente antes de inscribirte. Podés revisar tu plan desde Mi perfil.";
    if (reason === "already_enrolled") return "Ya tenés una inscripción activa en esa clase.";
    if (reason === "class_full") return "La clase ya no tiene cupos disponibles.";
    if (reason === "class_unavailable") return "La clase ya no admite nuevas inscripciones.";
    if (reason === "class_not_found") return "No encontré esa clase entre las opciones disponibles.";
    if (reason === "active_enrollment_not_found") return "No encontré una inscripción activa propia para esa clase.";
    if (reason === "enrollment_not_cancellable") return "Esa inscripción ya no se puede cancelar porque la clase comenzó.";
    if (reason === "csrf_failed") return "La sesión cambió. Recargá la página antes de confirmar la operación.";
    return "El backend de FitPath no está disponible. Puedo seguir respondiendo preguntas generales, pero las operaciones reales están temporalmente deshabilitadas.";
  }

  function backendWasReached(reason) {
    return !["backend_unavailable", "authentication_required", "permission_denied", "unsupported_operation"].includes(reason);
  }

  function formatBackendResult(operation, payload) {
    if (payload?.message) return payload.message;
    if (operation === "classes.list" && Array.isArray(payload?.classes)) {
      if (!payload.classes.length) return "No hay clases futuras disponibles para mostrar.";
      const lines = payload.classes.slice(0, 5).map((item) =>
        `${item.id}. ${item.activity} · ${item.starts_at} · ${item.site} · ${item.available_spots} cupos`
      );
      return `Estas son las próximas clases:\n${lines.join("\n")}`;
    }
    if (operation === "routine.get" && payload?.routine) {
      return `Tu rutina actual es “${payload.routine.name}”. Tiene ${payload.routine.exercise_count} ejercicios registrados.`;
    }
    if (operation === "progress.get" && payload?.progress) {
      return `Tu último progreso registrado corresponde a ${payload.progress.recorded_at}.`;
    }
    if (operation === "membership.get" && payload?.membership) {
      return `Tu membresía es ${payload.membership.name} y figura como ${payload.membership.status}.`;
    }
    return "La operación se completó correctamente en FitPath.";
  }

  class ConversationEngine {
    constructor(options) {
      const settings = options || {};
      this.intentEngine = settings.intentEngine || new assistant.IntentEngine();
      this.client = settings.client || new assistant.FitPathClient({ offline: true });
      this.state = { activeTopic: null, pendingAction: null, recent: [] };
      this.responseIndex = 0;
    }

    _remember(role, content) {
      this.state.recent.push({ role, content: String(content).slice(0, 800) });
      this.state.recent = this.state.recent.slice(-8);
    }

    _result(message, extras) {
      this._remember("assistant", message);
      return { message, suggestions: [], actions: [], ...(extras || {}) };
    }

    async _handlePending(normalized) {
      const pending = this.state.pendingAction;
      if (!pending) return null;
      if (/^(no|cancelar confirmacion|descartar|mejor no)$/.test(normalized)) {
        this.state.pendingAction = null;
        return this._result("Entendido. No realicé ningún cambio en FitPath.", { suggestions: ["Ver clases", "Mis reservas"] });
      }
      if (!/^(si|confirmar|confirmo|dale|aceptar)$/.test(normalized)) return null;

      this.state.pendingAction = null;
      const response = await this.client.perform(pending.operation, { id: pending.id });
      if (!response.ok) return this._result(unavailableMessage(response.reason), {
        backendAvailable: backendWasReached(response.reason)
      });
      return this._result(formatBackendResult(pending.operation, response.data), { backendAvailable: true });
    }

    async respond(message) {
      const original = String(message || "").trim();
      const normalized = text.normalizeText(original);
      if (!original) return this._result("Escribí una pregunta para que pueda ayudarte.");
      this._remember("user", original);

      const pendingResult = await this._handlePending(normalized);
      if (pendingResult) return pendingResult;

      const detection = this.intentEngine.detect(original, this.state);
      if (detection.kind === "greeting") {
        return this._result(choose(knowledge.greetings, this.responseIndex++), {
          suggestions: ["Rutina para principiantes", "Nutrición general", "Ver clases"]
        });
      }
      if (detection.kind === "safety") {
        this.state.activeTopic = null;
        return this._result(
          "No puedo diagnosticar ni indicar tratamientos. Si hay dolor agudo, dolor de pecho, desmayo o una lesión, detené la actividad y buscá atención profesional. Puedo ofrecer información general y ayudarte a navegar FitPath."
        );
      }
      if (detection.kind === "ambiguous") {
        const [first, second] = detection.options;
        return this._result(`Tu pregunta puede referirse a ${first.title} o ${second.title}. ¿Cuál de los dos temas querés tratar?`, {
          suggestions: [first.title, second.title]
        });
      }
      if (detection.kind !== "intent") {
        this.state.activeTopic = null;
        return this._result(choose(knowledge.fallbacks, this.responseIndex++), {
          suggestions: ["Entrenamiento", "Nutrición", "Hidratación", "Funciones de FitPath"]
        });
      }

      const intent = detection.intent;
      this.state.activeTopic = intent.id;
      if (intent.category === "navegacion") {
        return this._result(`Podés abrir ${intent.title.toLowerCase()} desde aquí.`, {
          actions: [{ type: "navigate", label: intent.title, href: intent.route }]
        });
      }
      if (intent.category === "fitpath") {
        if (intent.mutation) {
          if (typeof this.client.capabilities === "function") {
            const capabilities = await this.client.capabilities();
            if (!capabilities.ok) {
              return this._result(unavailableMessage(capabilities.reason), {
                suggestions: intent.suggestions || [], backendAvailable: false
              });
            }
            if (capabilities.data?.disabled?.includes(intent.operation)) {
              return this._result(unavailableMessage("unsupported_operation"), {
                suggestions: intent.suggestions || [], backendAvailable: true
              });
            }
          }
          const id = text.extractNumber(original);
          if (!id) {
            return this._result(
              intent.operation === "enrollments.create"
                ? "Para preparar la inscripción necesito el número de la clase. Primero podés pedirme “ver clases”."
                : "Para preparar la cancelación necesito el número de la clase. Consultá tus reservas desde FitPath.",
              { suggestions: intent.suggestions || [] }
            );
          }
          this.state.pendingAction = { operation: intent.operation, id };
          const verb = intent.operation === "enrollments.create" ? "inscribirte en la clase" : "cancelar la inscripción a la clase";
          return this._result(`Voy a solicitar ${verb} ${id}. Escribí “confirmar” para ejecutar la operación real o “mejor no” para descartarla.`, {
            confirmationRequired: true,
            suggestions: ["Confirmar", "Mejor no"]
          });
        }
        const response = await this.client.perform(intent.operation);
        if (!response.ok) return this._result(unavailableMessage(response.reason), {
          suggestions: intent.suggestions || [], backendAvailable: false
        });
        return this._result(formatBackendResult(intent.operation, response.data), {
          suggestions: intent.suggestions || [], backendAvailable: true
        });
      }

      const choiceIndex = this.responseIndex++;
      const base = choose(intent.responses, choiceIndex);
      const followUp = choose(intent.followUps, choiceIndex);
      return this._result(`${base}${followUp ? ` ${followUp}` : ""}`, {
        suggestions: intent.suggestions || [], confidence: detection.confidence, topic: intent.id
      });
    }
  }

  assistant.ConversationEngine = ConversationEngine;
})(typeof window !== "undefined" ? window : globalThis);
