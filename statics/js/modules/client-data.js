function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers: { Accept: "application/json", ...(options.headers || {}) }
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw { status: response.status, ...payload };
  return payload;
}

function formatDateTime(value, timeZone = "America/Argentina/Buenos_Aires") {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  try {
    return new Intl.DateTimeFormat("es-AR", {
      timeZone,
      weekday: "short",
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit"
    }).format(date);
  } catch (_error) {
    return new Intl.DateTimeFormat("es-AR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit"
    }).format(date);
  }
}

function setStatus(node, message, error = false) {
  if (!node) return;
  node.textContent = message;
  node.dataset.error = error ? "true" : "false";
}

function classError(error) {
  const messages = {
    already_enrolled: "Ya estás inscripto en esta clase.",
    class_full: "La clase ya no tiene cupos disponibles.",
    class_unavailable: "La clase ya no admite inscripciones.",
    active_enrollment_not_found: "La inscripción ya no está activa.",
    enrollment_not_cancellable: "La clase ya comenzó y no se puede cancelar.",
    csrf_failed: "La sesión cambió. Recargá la página."
  };
  return messages[error.error] || "No pudimos completar la operación. Volvé a intentar.";
}

function classCard(item, interactive = true) {
  const card = element("article", "fp-card cl-class-tile cl-real-data-card");
  const heading = element("div", "cl-card-heading");
  const copy = element("div");
  copy.append(
    element("span", "fp-section-kicker", item.sede),
    element("h2", "", item.actividad)
  );
  heading.append(copy, element("span", "fp-status fp-status-upcoming", item.estado));
  card.append(
    heading,
    element("p", "cl-view-lead", formatDateTime(item.inicio_utc, item.zona_horaria)),
    element("p", "", item.direccion),
    element(
      "strong",
      "cl-class-seat",
      `${item.cupos_disponibles} de ${item.cupo_maximo} cupos disponibles`
    )
  );
  if (interactive && item.estado === "programada") {
    const button = element(
      "button",
      item.inscripto ? "fp-button fp-button-outline" : "fp-button fp-button-primary",
      item.inscripto ? "Cancelar inscripción" : "Inscribirme"
    );
    button.type = "button";
    button.dataset.classEnrollment = String(item.id);
    button.dataset.action = item.inscripto ? "cancel" : "enroll";
    button.disabled = !item.inscripto && item.cupos_disponibles < 1;
    if (button.disabled) button.title = "No quedan cupos disponibles";
    card.append(button);
  }
  return card;
}

async function initializeClasses(csrfToken) {
  const root = document.querySelector("[data-client-classes-root]");
  if (!root) return;
  const mount = root.querySelector("[data-client-classes-list]");
  const status = root.querySelector("[data-client-data-status]");
  const load = async () => {
    setStatus(status, "Cargando próximas clases…");
    const payload = await api("/api/v1/client/classes");
    if (!payload.classes.length) {
      mount.replaceChildren(element("p", "cl-empty-state", "No hay clases próximas disponibles."));
    } else {
      mount.replaceChildren(...payload.classes.map((item) => classCard(item)));
    }
    setStatus(status, `${payload.classes.length} clases próximas encontradas.`);
  };
  root.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-class-enrollment]");
    if (!button) return;
    button.disabled = true;
    const action = button.dataset.action;
    setStatus(status, action === "cancel" ? "Cancelando inscripción…" : "Confirmando inscripción…");
    try {
      await api(`/api/v1/client/classes/${button.dataset.classEnrollment}/enrollment`, {
        method: action === "cancel" ? "DELETE" : "POST",
        headers: { "X-CSRF-Token": csrfToken }
      });
      await load();
      setStatus(status, action === "cancel" ? "Inscripción cancelada." : "Inscripción confirmada.");
    } catch (error) {
      setStatus(status, classError(error), true);
      button.disabled = false;
    }
  });
  try { await load(); } catch (_error) { setStatus(status, "No pudimos cargar las clases.", true); }
}

async function initializeEnrollments() {
  const root = document.querySelector("[data-client-enrollments-root]");
  if (!root) return;
  const mount = root.querySelector("[data-client-enrollments-list]");
  const status = root.querySelector("[data-client-data-status]");
  try {
    const payload = await api("/api/v1/client/enrollments");
    if (!payload.enrollments.length) {
      mount.replaceChildren(element("p", "cl-empty-state", "Todavía no tenés inscripciones registradas."));
    } else {
      mount.replaceChildren(...payload.enrollments.map((item) => {
        const row = element("article", "fp-card cl-history-row");
        const copy = element("div");
        copy.append(
          element("strong", "", item.actividad),
          element("small", "", `${formatDateTime(item.inicio_utc)} · ${item.sede}`)
        );
        const result = item.asistencia ? ` · asistencia ${item.asistencia}` : "";
        row.append(copy, element("span", `fp-payment-status is-${item.estado}`, `${item.estado}${result}`));
        return row;
      }));
    }
    setStatus(status, `${payload.enrollments.length} inscripciones en el historial.`);
  } catch (_error) {
    setStatus(status, "No pudimos cargar tus inscripciones.", true);
  }
}

function routineCard(routine) {
  const card = element("article", "fp-card cl-routine-real-card");
  card.append(
    element("span", "fp-section-kicker", routine.objetivo || "RUTINA ASIGNADA"),
    element("h2", "", routine.nombre),
    element("p", "cl-view-lead", routine.descripcion || "Sin descripción adicional.")
  );
  if (routine.observaciones_entrenador) {
    card.append(element("p", "cl-routine-note", `Indicaciones: ${routine.observaciones_entrenador}`));
  }
  if (!routine.ejercicios.length) {
    card.append(element("p", "cl-empty-state", "Esta rutina todavía no tiene ejercicios."));
    return card;
  }
  const list = element("ol", "cl-real-exercise-list");
  for (const exercise of routine.ejercicios) {
    const item = element("li");
    const copy = element("span");
    copy.append(
      element("strong", "", exercise.nombre),
      element("small", "", exercise.grupo_muscular || "Grupo muscular no informado")
    );
    const weight = exercise.peso_gramos === null ? "sin carga" : `${exercise.peso_gramos / 1000} kg`;
    item.append(
      element("span", "cl-list-date", String(exercise.orden).padStart(2, "0")),
      copy,
      element("span", "cl-exercise-dose", `${exercise.series} × ${exercise.repeticiones} · ${weight} · ${exercise.descanso_segundos}s`)
    );
    list.append(item);
  }
  card.append(list);
  return card;
}

async function initializeRoutines() {
  const root = document.querySelector("[data-client-routines-root]");
  if (!root) return;
  const mount = root.querySelector("[data-client-routines-list]");
  const status = root.querySelector("[data-client-data-status]");
  try {
    const payload = await api("/api/v1/client/routines");
    mount.replaceChildren(...(
      payload.routines.length
        ? payload.routines.map(routineCard)
        : [element("p", "cl-empty-state", "Todavía no tenés una rutina asignada.")]
    ));
    setStatus(status, `${payload.routines.length} rutinas asignadas.`);
  } catch (_error) {
    setStatus(status, "No pudimos cargar tus rutinas.", true);
  }
}

function progressRow(item) {
  const row = element("article", "fp-card cl-history-row");
  const copy = element("div");
  copy.append(
    element("strong", "", formatDateTime(item.fecha_utc)),
    element("small", "", item.observaciones || item.rendimiento_ejercicios || "Registro sin notas")
  );
  const metrics = [
    item.peso_kg !== null ? `${item.peso_kg} kg` : null,
    item.porcentaje_grasa !== null ? `${item.porcentaje_grasa}% grasa` : null
  ].filter(Boolean).join(" · ");
  row.append(copy, element("span", "cl-exercise-dose", metrics || "Registro cualitativo"));
  return row;
}

async function initializeProgress(csrfToken) {
  const root = document.querySelector("[data-client-progress-root]");
  if (!root) return;
  const form = root.querySelector("[data-client-progress-form]");
  const mount = root.querySelector("[data-client-progress-list]");
  const status = root.querySelector("[data-client-data-status]");
  const submit = form.querySelector("button[type='submit']");
  const load = async () => {
    const payload = await api("/api/v1/client/progress");
    mount.replaceChildren(...(
      payload.progress.length
        ? payload.progress.map(progressRow)
        : [element("p", "cl-empty-state", "Todavía no registraste progreso.")]
    ));
    setStatus(status, `${payload.progress.length} registros de progreso.`);
  };
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const data = new FormData(form);
    const payload = Object.fromEntries(data.entries());
    if (!Object.values(payload).some((value) => String(value).trim())) {
      setStatus(status, "Ingresá al menos una métrica u observación.", true);
      return;
    }
    submit.disabled = true;
    setStatus(status, "Guardando progreso…");
    try {
      await api("/api/v1/client/progress", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify(payload)
      });
      form.reset();
      await load();
      setStatus(status, "Progreso registrado correctamente.");
    } catch (error) {
      setStatus(status, error.error === "csrf_failed" ? "La sesión cambió. Recargá la página." : "No pudimos guardar el progreso.", true);
    } finally {
      submit.disabled = false;
    }
  });
  try { await load(); } catch (_error) { setStatus(status, "No pudimos cargar tu progreso.", true); }
}

async function initializeDashboard() {
  const root = document.querySelector("[data-client-dashboard-root]");
  if (!root) return;
  try {
    const payload = await api("/api/v1/client/dashboard");
    root.querySelectorAll("[data-dashboard-count]").forEach((node) => {
      node.textContent = String(payload.counts[node.dataset.dashboardCount] ?? 0);
    });
    const next = root.querySelector("[data-dashboard-next-class]");
    if (next) {
      next.textContent = payload.next_class
        ? `${payload.next_class.actividad} · ${formatDateTime(payload.next_class.inicio_utc)} · ${payload.next_class.sede}`
        : "No tenés una próxima clase reservada.";
    }
  } catch (_error) {
    const status = root.querySelector("[data-client-data-status]");
    setStatus(status, "No pudimos actualizar el resumen.", true);
  }
}

export async function initializeClientData({ csrfToken }) {
  await Promise.all([
    initializeClasses(csrfToken),
    initializeEnrollments(),
    initializeRoutines(),
    initializeProgress(csrfToken),
    initializeDashboard()
  ]);
}
