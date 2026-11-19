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

function positiveQueryParameter(name) {
  const value = Number(new URLSearchParams(window.location.search).get(name));
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

function routineDetailHref(routineId) {
  return `/templates/cliente/rutina/entrenamiento.html?rutina=${routineId}`;
}

function exerciseDetailHref(routineId, assignmentId) {
  return `/templates/cliente/rutina/ejercicio.html?rutina=${routineId}&asignacion=${assignmentId}`;
}

function classDetailHref(classId) {
  return `/templates/cliente/clases/detalle.html?clase=${classId}`;
}

function nutritionDetailHref(planId) {
  return `/templates/cliente/alimentacion/detalle.html?plan=${planId}`;
}

function exerciseWeight(exercise) {
  return exercise.peso_gramos === null ? "Sin carga" : `${exercise.peso_gramos / 1000} kg`;
}

function exerciseDose(exercise) {
  return `${exercise.series} × ${exercise.repeticiones} · ${exerciseWeight(exercise)} · ${exercise.descanso_segundos}s`;
}

function exerciseListItem(exercise, routineId, detailed = false) {
  const item = element("li");
  const copy = element(detailed ? "div" : "span", "cl-exercise-copy");
  copy.append(
    element("strong", "", exercise.nombre),
    element("small", "", exercise.grupo_muscular || "Grupo muscular no informado"),
    element("small", "", exerciseDose(exercise))
  );
  const link = element("a", "cl-exercise-open", "Ver ejercicio");
  link.href = exerciseDetailHref(routineId, exercise.asignacion_id);
  item.append(
    element(
      "span",
      detailed ? "cl-exercise-number" : "cl-list-date",
      String(exercise.orden).padStart(2, "0")
    ),
    copy,
    link
  );
  return item;
}

function classError(error) {
  const messages = {
    already_enrolled: "Ya estás inscripto en esta clase.",
    active_membership_required: "Necesitás una membresía activa y vigente para inscribirte.",
    class_full: "La clase ya no tiene cupos disponibles.",
    class_unavailable: "La clase ya no admite inscripciones.",
    active_enrollment_not_found: "La inscripción ya no está activa.",
    enrollment_not_cancellable: "La clase ya comenzó y no se puede cancelar.",
    csrf_failed: "La sesión cambió. Recargá la página."
  };
  return messages[error.error] || "No pudimos completar la operación. Volvé a intentar.";
}

function classDuration(item) {
  const start = new Date(item.inicio_utc);
  const end = new Date(item.fin_utc);
  const minutes = Math.round((end - start) / 60000);
  return Number.isFinite(minutes) && minutes > 0 ? `${minutes} minutos` : "No informada";
}

function classEnrollmentButton(item) {
  const button = element(
    "button",
    item.inscripto ? "fp-button fp-button-outline" : "fp-button fp-button-primary",
    item.inscripto ? "Cancelar inscripción" : "Inscribirme"
  );
  button.type = "button";
  button.dataset.classEnrollment = String(item.id);
  button.dataset.action = item.inscripto ? "cancel" : "enroll";
  button.disabled = item.estado !== "programada" || (!item.inscripto && item.cupos_disponibles < 1);
  if (button.disabled) button.title = item.estado !== "programada"
    ? "La clase no admite inscripciones"
    : "No quedan cupos disponibles";
  return button;
}

async function updateClassEnrollment(button, csrfToken) {
  const action = button.dataset.action;
  await api(`/api/v1/client/classes/${button.dataset.classEnrollment}/enrollment`, {
    method: action === "cancel" ? "DELETE" : "POST",
    headers: { "X-CSRF-Token": csrfToken }
  });
  return action;
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
    element("p", "", `${item.direccion} · ${item.entrenador}`),
    element(
      "strong",
      "cl-class-seat",
      `${item.cupos_disponibles} de ${item.cupo_maximo} cupos disponibles`
    )
  );
  const detail = element("a", "cl-text-action", "Ver detalle");
  detail.href = classDetailHref(item.id);
  card.append(detail);
  if (interactive) card.append(classEnrollmentButton(item));
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
      await updateClassEnrollment(button, csrfToken);
      await load();
      setStatus(status, action === "cancel" ? "Inscripción cancelada." : "Inscripción confirmada.");
    } catch (error) {
      setStatus(status, classError(error), true);
      button.disabled = false;
    }
  });
  try { await load(); } catch (_error) { setStatus(status, "No pudimos cargar las clases.", true); }
}

function descriptionRow(label, value) {
  const row = element("div");
  row.append(element("dt", "", label), element("dd", "", value));
  return row;
}

function renderClassDetail(root, item) {
  root.querySelector("[data-class-title]").textContent = item.actividad;
  root.querySelector("[data-class-lead]").textContent = `${item.sede} · ${item.direccion}`;
  const information = element("article", "fp-card cl-list-card");
  const list = element("dl", "cl-description-list");
  list.append(
    descriptionRow("Horario", formatDateTime(item.inicio_utc, item.zona_horaria)),
    descriptionRow("Duración", classDuration(item)),
    descriptionRow("Sede", `${item.sede} · ${item.direccion}`),
    descriptionRow("Entrenador", `${item.entrenador} · ${item.entrenador_especialidad}`),
    descriptionRow("Estado", item.estado),
    descriptionRow("Cupos", `${item.cupos_disponibles} disponibles de ${item.cupo_maximo}`)
  );
  information.append(
    element("span", "fp-section-kicker", "INFORMACIÓN DE LA CLASE"),
    element("h2", "", "Datos confirmados"),
    list
  );
  const action = element("aside", "fp-card cl-action-card");
  action.append(
    element("span", "fp-section-kicker", "INSCRIPCIÓN"),
    element("h2", "", item.inscripto ? "Tu lugar está reservado" : "Gestioná tu lugar"),
    element(
      "p",
      "",
      item.inscripto
        ? "Podés cancelar mientras la clase todavía no haya comenzado."
        : "La confirmación se guarda en tu historial de FitPath."
    ),
    classEnrollmentButton(item)
  );
  const reservations = element("a", "cl-text-action", "Consultar mis reservas");
  reservations.href = "/templates/cliente/clases/reservas.html";
  action.append(reservations);
  const grid = element("section", "cl-detail-grid");
  grid.append(information, action);
  root.querySelector("[data-class-detail]").replaceChildren(grid);
}

async function initializeClassDetailPage(root, csrfToken, selectClass, emptyMessage) {
  const status = root.querySelector("[data-client-data-status]");
  const mount = root.querySelector("[data-class-detail]");
  const load = async () => {
    setStatus(status, "Cargando información de la clase…");
    const payload = await api("/api/v1/client/classes");
    const item = selectClass(payload.classes);
    if (!item) {
      root.querySelector("[data-class-title]").textContent = "Clase no disponible";
      root.querySelector("[data-class-lead]").textContent = emptyMessage;
      mount.replaceChildren(element("p", "cl-empty-state", emptyMessage));
      setStatus(status, emptyMessage, true);
      return;
    }
    renderClassDetail(root, item);
    setStatus(status, `Clase ${item.estado}; ${item.cupos_disponibles} cupos disponibles.`);
  };
  root.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-class-enrollment]");
    if (!button) return;
    button.disabled = true;
    const action = button.dataset.action;
    setStatus(status, action === "cancel" ? "Cancelando inscripción…" : "Confirmando inscripción…");
    try {
      await updateClassEnrollment(button, csrfToken);
      await load();
      setStatus(status, action === "cancel" ? "Inscripción cancelada." : "Inscripción confirmada.");
    } catch (error) {
      setStatus(status, classError(error), true);
      button.disabled = false;
    }
  });
  try {
    await load();
  } catch (_error) {
    mount.replaceChildren(element("p", "cl-empty-state", "La información no está disponible temporalmente."));
    setStatus(status, "No pudimos cargar la clase.", true);
  }
}

async function initializeClassDetail(csrfToken) {
  const root = document.querySelector("[data-client-class-detail-root]");
  if (!root) return;
  const classId = positiveQueryParameter("clase");
  if (!classId) {
    root.querySelector("[data-class-title]").textContent = "Clase no seleccionada";
    root.querySelector("[data-class-lead]").textContent = "Abrí el detalle desde Clases disponibles.";
    root.querySelector("[data-class-detail]").replaceChildren(
      element("p", "cl-empty-state", "Falta identificar una clase válida.")
    );
    setStatus(root.querySelector("[data-client-data-status]"), "No se recibió una clase válida.", true);
    return;
  }
  await initializeClassDetailPage(
    root,
    csrfToken,
    (classes) => classes.find((item) => item.id === classId),
    "La clase no existe o ya no está disponible."
  );
}

async function initializeNextClass(csrfToken) {
  const root = document.querySelector("[data-client-next-class-root]");
  if (!root) return;
  await initializeClassDetailPage(
    root,
    csrfToken,
    (classes) => classes.find((item) => item.inscripto && item.estado === "programada"),
    "No tenés una próxima clase reservada."
  );
}

function calendarQueryMessage() {
  const state = new URLSearchParams(window.location.search).get("calendar");
  const messages = {
    connected: ["Google Calendar quedó conectado.", false],
    authorization_denied: ["No autorizaste Google Calendar. No se creó ningún evento.", true],
    account_mismatch: ["La cuenta elegida no coincide con tu identidad Google de FitPath.", true],
    identity_required: ["Tu usuario FitPath no tiene una identidad Google vinculada.", true],
    configuration_required: ["Google Calendar todavía no está configurado en FitPath.", true],
    provider_unavailable: ["Google no está disponible temporalmente. Volvé a intentar.", true],
    authorization_error: ["No pudimos completar la autorización de Google Calendar.", true]
  };
  return messages[state] || null;
}

function calendarEventLink(url) {
  if (!url) return element("span", "fp-payment-status is-realizado", "Añadida a Calendar");
  const link = element("a", "cl-text-action", "Abrir en Google Calendar");
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function calendarErrorMessage(error) {
  const messages = {
    csrf_failed: "La sesión cambió. Recargá la página.",
    calendar_not_configured: "Google Calendar todavía no está configurado.",
    calendar_authorization_required: "Primero autorizá Google Calendar.",
    calendar_authorization_expired: "La autorización venció. Volvé a conectar Google Calendar.",
    enrollment_not_available: "La inscripción ya no está activa o la clase no está programada.",
    calendar_provider_unavailable: "Google Calendar no está disponible temporalmente."
  };
  return messages[error.error] || "No pudimos añadir la clase a Google Calendar.";
}

async function initializeEnrollments(csrfToken) {
  const root = document.querySelector("[data-client-enrollments-root]");
  if (!root) return;
  const mount = root.querySelector("[data-client-enrollments-list]");
  const status = root.querySelector("[data-client-data-status]");
  const calendarRoot = root.querySelector("[data-client-calendar-root]");
  const connectionStatus = calendarRoot.querySelector("[data-calendar-connection-status]");
  const connectLink = calendarRoot.querySelector("[data-calendar-connect]");
  let calendarState = { configured: false, connected: false, state: "configuration_required" };

  const renderConnection = (queryMessage = null) => {
    connectLink.hidden = !calendarState.configured || calendarState.connected;
    if (queryMessage) {
      setStatus(connectionStatus, queryMessage[0], queryMessage[1]);
      return;
    }
    if (!calendarState.configured) {
      setStatus(connectionStatus, "Configuración pendiente: la integración todavía no está disponible.", true);
    } else if (!calendarState.connected) {
      setStatus(connectionStatus, "Google Calendar no está autorizado para tu usuario.");
    } else {
      setStatus(connectionStatus, "Google Calendar conectado. Elegí una clase activa para añadirla.");
    }
  };

  const enrollmentRow = (item) => {
    const row = element("article", "fp-card cl-history-row");
    const copy = element("div");
    copy.append(
      element("strong", "", item.actividad),
      element("small", "", `${formatDateTime(item.inicio_utc, item.zona_horaria)} · ${item.sede}`)
    );
    const result = item.asistencia ? ` · asistencia ${item.asistencia}` : "";
    const actions = element("div", "cl-inline-links");
    actions.append(element("span", `fp-payment-status is-${item.estado}`, `${item.estado}${result}`));
    if (item.calendar_event_added) {
      actions.append(calendarEventLink(item.calendar_event_url));
    } else if (calendarState.connected && item.estado === "activa" && item.clase_estado === "programada") {
      const button = element("button", "fp-button fp-button-outline", "Añadir a Google Calendar");
      button.type = "button";
      button.dataset.calendarEnrollment = String(item.id);
      button.dataset.calendarActivity = item.actividad;
      actions.append(button);
    }
    row.append(copy, actions);
    return row;
  };

  root.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-calendar-enrollment]");
    if (!button) return;
    const confirmed = window.confirm(
      `¿Añadir ${button.dataset.calendarActivity} a tu Google Calendar?`
    );
    if (!confirmed) return;
    button.disabled = true;
    setStatus(connectionStatus, "Añadiendo la clase a Google Calendar…");
    try {
      const payload = await api(
        `/api/v1/client/calendar/enrollments/${button.dataset.calendarEnrollment}/event`,
        { method: "POST", headers: { "X-CSRF-Token": csrfToken } }
      );
      button.replaceWith(calendarEventLink(payload.event.event_url));
      setStatus(
        connectionStatus,
        payload.event.created
          ? "Clase añadida correctamente a Google Calendar."
          : "La clase ya estaba añadida a Google Calendar."
      );
    } catch (error) {
      if (error.error === "calendar_authorization_expired") {
        calendarState.connected = false;
        connectLink.hidden = false;
      }
      setStatus(connectionStatus, calendarErrorMessage(error), true);
      button.disabled = false;
    }
  });

  try {
    const [calendarPayload, payload] = await Promise.all([
      api("/api/v1/client/calendar/status"),
      api("/api/v1/client/enrollments")
    ]);
    calendarState = calendarPayload;
    renderConnection(calendarQueryMessage());
    if (!payload.enrollments.length) {
      mount.replaceChildren(element("p", "cl-empty-state", "Todavía no tenés inscripciones registradas."));
    } else {
      mount.replaceChildren(...payload.enrollments.map(enrollmentRow));
    }
    setStatus(status, `${payload.enrollments.length} inscripciones en el historial.`);
  } catch (_error) {
    renderConnection(calendarQueryMessage());
    setStatus(status, "No pudimos cargar tus inscripciones.", true);
  }
}

function shortDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("es-AR", { day: "2-digit", month: "short" }).format(date);
}

function activityListItem(item) {
  const row = element("li");
  const copy = element("span");
  copy.append(element("strong", "", item.title), element("small", "", item.description));
  const link = element("a", "", item.linkLabel);
  link.href = item.href;
  row.append(element("span", "cl-list-date", shortDate(item.date)), copy, link);
  return row;
}

async function initializeActivity() {
  const root = document.querySelector("[data-client-activity-root]");
  if (!root) return;
  const status = root.querySelector("[data-client-data-status]");
  const mount = root.querySelector("[data-client-activity-list]");
  try {
    const [enrollmentsPayload, routinesPayload, progressPayload] = await Promise.all([
      api("/api/v1/client/enrollments"),
      api("/api/v1/client/routines"),
      api("/api/v1/client/progress")
    ]);
    const counts = {
      enrollments: enrollmentsPayload.enrollments.length,
      attendance: enrollmentsPayload.enrollments.filter((item) => item.asistencia === "presente").length,
      routines: routinesPayload.routines.filter((item) => item.activa).length,
      progress: progressPayload.progress.length
    };
    root.querySelectorAll("[data-activity-count]").forEach((node) => {
      node.textContent = String(counts[node.dataset.activityCount] ?? 0);
    });
    const entries = [
      ...enrollmentsPayload.enrollments.map((item) => ({
        date: item.inicio_utc,
        title: item.actividad,
        description: `${item.sede} · inscripción ${item.estado}${item.asistencia ? ` · asistencia ${item.asistencia}` : ""}`,
        href: "/templates/cliente/clases/reservas.html",
        linkLabel: "Ver inscripción"
      })),
      ...routinesPayload.routines.map((item) => ({
        date: item.fecha_creacion_utc,
        title: item.nombre,
        description: `${item.activa ? "Rutina activa" : "Rutina histórica"} · ${item.objetivo || "sin objetivo asociado"}`,
        href: routineDetailHref(item.id),
        linkLabel: "Ver rutina"
      })),
      ...progressPayload.progress.map((item) => ({
        date: item.fecha_utc,
        title: "Registro de progreso",
        description: item.observaciones || item.rendimiento_ejercicios || "Medición personal",
        href: "/templates/cliente/progreso/evolucion.html",
        linkLabel: "Ver evolución"
      }))
    ].sort((left, right) => new Date(right.date) - new Date(left.date)).slice(0, 8);
    mount.replaceChildren(...(
      entries.length
        ? entries.map(activityListItem)
        : [element("li", "cl-empty-state", "Todavía no hay actividad registrada en tu perfil.")]
    ));
    setStatus(status, `${entries.length} movimientos recientes encontrados.`);
  } catch (_error) {
    mount.replaceChildren(element("li", "cl-empty-state", "La actividad no está disponible temporalmente."));
    setStatus(status, "No pudimos cargar tu actividad.", true);
  }
}

function routineCard(routine) {
  const card = element("article", "fp-card cl-routine-real-card");
  const kicker = routine.activa
    ? (routine.objetivo || "RUTINA ASIGNADA")
    : `RUTINA HISTÓRICA${routine.objetivo ? ` · ${routine.objetivo}` : ""}`;
  card.append(
    element("span", "fp-section-kicker", kicker),
    element("h2", "", routine.nombre),
    element("p", "cl-view-lead", routine.descripcion || "Sin descripción adicional.")
  );
  if (routine.observaciones_entrenador) {
    card.append(element("p", "cl-routine-note", `Indicaciones: ${routine.observaciones_entrenador}`));
  }
  const detailLink = element(
    "a",
    "fp-button fp-button-primary",
    routine.activa ? "Abrir rutina" : "Consultar historial"
  );
  detailLink.href = routineDetailHref(routine.id);
  if (!routine.ejercicios.length) {
    card.append(
      element("p", "cl-empty-state", "Esta rutina todavía no tiene ejercicios."),
      detailLink
    );
    return card;
  }
  const list = element("ol", "cl-real-exercise-list");
  for (const exercise of routine.ejercicios) {
    list.append(exerciseListItem(exercise, routine.id));
  }
  card.append(list, detailLink);
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

function nutritionPlanDetails(plan) {
  const details = element("dl", "cl-description-list");
  details.append(
    descriptionRow("Objetivo", `${plan.objetivo.tipo}: ${plan.objetivo.nombre}`),
    descriptionRow("Descripción", plan.descripcion || "Sin descripción adicional."),
    descriptionRow("Indicaciones", plan.indicaciones || "Sin indicaciones adicionales."),
    descriptionRow("Creado", formatDateTime(plan.fecha_creacion_utc)),
    descriptionRow("Actualizado", formatDateTime(plan.fecha_actualizacion_utc))
  );
  return details;
}

function nutritionPlanCard(plan) {
  const card = element("article", "fp-card cl-routine-real-card");
  card.append(
    element("span", "fp-section-kicker", plan.objetivo.tipo.toUpperCase()),
    element("h2", "", plan.nombre),
    nutritionPlanDetails(plan)
  );
  const link = element("a", "fp-button fp-button-primary", "Consultar detalle");
  link.href = nutritionDetailHref(plan.id);
  card.append(link);
  return card;
}

async function initializeNutritionPlans() {
  const root = document.querySelector("[data-client-nutrition-root]");
  if (!root) return;
  const mount = root.querySelector("[data-client-nutrition-list]");
  const status = root.querySelector("[data-client-data-status]");
  try {
    const payload = await api("/api/v1/client/nutrition-plans");
    mount.replaceChildren(...(
      payload.nutrition_plans.length
        ? payload.nutrition_plans.map(nutritionPlanCard)
        : [element("p", "cl-empty-state", "Todavía no tenés planes de alimentación asignados.")]
    ));
    setStatus(
      status,
      payload.nutrition_plans.length
        ? `${payload.nutrition_plans.length} planes asignados.`
        : "No hay planes asignados a tu perfil."
    );
  } catch (_error) {
    mount.replaceChildren(element("p", "cl-empty-state", "La información no está disponible temporalmente."));
    setStatus(status, "No pudimos cargar tus planes de alimentación.", true);
  }
}

async function initializeNutritionDetail() {
  const root = document.querySelector("[data-client-nutrition-detail-root]");
  if (!root) return;
  const title = root.querySelector("[data-nutrition-title]");
  const lead = root.querySelector("[data-nutrition-lead]");
  const mount = root.querySelector("[data-client-nutrition-detail]");
  const status = root.querySelector("[data-client-data-status]");
  const planId = positiveQueryParameter("plan");
  if (!planId) {
    title.textContent = "Plan no seleccionado";
    lead.textContent = "Volvé a Mi alimentación y elegí un plan asignado.";
    mount.replaceChildren(element("p", "cl-empty-state", "Falta identificar el plan."));
    setStatus(status, "No se recibió un plan válido.", true);
    return;
  }
  try {
    const payload = await api(`/api/v1/client/nutrition-plans/${planId}`);
    const plan = payload.nutrition_plan;
    title.textContent = plan.nombre;
    lead.textContent = `${plan.objetivo.tipo}: ${plan.objetivo.nombre}`;
    const information = element("article", "fp-card cl-routine-real-card");
    information.append(
      element("span", "fp-section-kicker", "PLAN ASIGNADO"),
      element("h2", "", "Información registrada"),
      nutritionPlanDetails(plan)
    );
    mount.replaceChildren(information);
    setStatus(status, "Plan cargado desde tu perfil protegido.");
  } catch (error) {
    title.textContent = "Plan no disponible";
    lead.textContent = error.status === 404
      ? "El plan no existe o no pertenece a tu perfil."
      : "Recargá la página para volver a intentar.";
    mount.replaceChildren(element("p", "cl-empty-state", "No hay información autorizada para mostrar."));
    setStatus(status, "No pudimos cargar el plan de alimentación.", true);
  }
}

async function initializeTrainingDetail() {
  const root = document.querySelector("[data-client-training-root]");
  if (!root) return;
  const status = root.querySelector("[data-client-data-status]");
  const title = root.querySelector("[data-training-title]");
  const description = root.querySelector("[data-training-description]");
  const summary = root.querySelector("[data-training-summary]");
  const exercises = root.querySelector("[data-training-exercises]");
  const routineId = positiveQueryParameter("rutina");
  if (!routineId) {
    title.textContent = "Rutina no seleccionada";
    description.textContent = "Volvé a Mis rutinas y elegí un plan asignado.";
    summary.replaceChildren();
    exercises.replaceChildren(element("p", "cl-empty-state", "Falta identificar la rutina."));
    setStatus(status, "No se recibió una rutina válida.", true);
    return;
  }
  try {
    const payload = await api("/api/v1/client/routines");
    const routine = payload.routines.find((item) => item.id === routineId);
    if (!routine) {
      title.textContent = "Rutina no disponible";
      description.textContent = "La rutina no existe o no pertenece a tu perfil.";
      summary.replaceChildren();
      exercises.replaceChildren(element("p", "cl-empty-state", "No hay datos autorizados para mostrar."));
      setStatus(status, "No pudimos encontrar esa rutina entre tus asignaciones.", true);
      return;
    }
    title.textContent = routine.nombre;
    description.textContent = routine.descripcion || "Sin descripción adicional.";
    summary.replaceChildren(
      element("span", "fp-section-kicker", routine.activa ? "RUTINA ACTIVA" : "RUTINA HISTÓRICA"),
      element("h2", "", routine.objetivo || "Sin objetivo asociado"),
      element("p", "", `Asignada el ${formatDateTime(routine.fecha_creacion_utc)}.`),
      element("p", "cl-routine-note", routine.observaciones_entrenador || "Sin indicaciones adicionales.")
    );
    if (!routine.ejercicios.length) {
      exercises.replaceChildren(element("p", "cl-empty-state", "Esta rutina todavía no tiene ejercicios."));
    } else {
      const list = element("ol", "cl-exercise-detail-list");
      routine.ejercicios.forEach((exercise) => {
        list.append(exerciseListItem(exercise, routine.id, true));
      });
      exercises.replaceChildren(list);
    }
    setStatus(status, `${routine.ejercicios.length} ejercicios cargados desde FitPath.`);
  } catch (_error) {
    title.textContent = "No pudimos cargar la rutina";
    description.textContent = "Recargá la página para volver a intentar.";
    summary.replaceChildren();
    exercises.replaceChildren(element("p", "cl-empty-state", "La información no está disponible temporalmente."));
    setStatus(status, "Ocurrió un error al consultar la rutina.", true);
  }
}

async function initializeExerciseDetail() {
  const root = document.querySelector("[data-client-exercise-root]");
  if (!root) return;
  const status = root.querySelector("[data-client-data-status]");
  const title = root.querySelector("[data-exercise-title]");
  const lead = root.querySelector("[data-exercise-lead]");
  const detail = root.querySelector("[data-exercise-detail]");
  const back = root.querySelector("[data-exercise-back]");
  const routineId = positiveQueryParameter("rutina");
  const assignmentId = positiveQueryParameter("asignacion");
  if (!routineId || !assignmentId) {
    title.textContent = "Ejercicio no seleccionado";
    lead.textContent = "Abrí el ejercicio desde una rutina asignada.";
    detail.replaceChildren(element("p", "cl-empty-state", "Faltan datos para identificar el ejercicio."));
    setStatus(status, "No se recibió un ejercicio válido.", true);
    return;
  }
  try {
    const payload = await api("/api/v1/client/routines");
    const routine = payload.routines.find((item) => item.id === routineId);
    const exercise = routine?.ejercicios.find((item) => item.asignacion_id === assignmentId);
    if (!routine || !exercise) {
      title.textContent = "Ejercicio no disponible";
      lead.textContent = "El ejercicio no existe o no pertenece a una rutina de tu perfil.";
      detail.replaceChildren(element("p", "cl-empty-state", "No hay datos autorizados para mostrar."));
      setStatus(status, "No pudimos encontrar ese ejercicio entre tus asignaciones.", true);
      return;
    }
    if (back) back.href = routineDetailHref(routine.id);
    title.textContent = exercise.nombre;
    lead.textContent = exercise.grupo_muscular || "Grupo muscular no informado";
    const feature = element("section", "cl-exercise-feature");
    const featureCopy = element("div");
    featureCopy.append(
      element("span", "fp-section-kicker", routine.activa ? "EJERCICIO ASIGNADO" : "EJERCICIO HISTÓRICO"),
      element("h2", "", routine.nombre),
      element("p", "", exercise.descripcion || "Sin descripción adicional.")
    );
    feature.append(element("div", "cl-exercise-mark", String(exercise.orden)), featureCopy);
    const stats = element("section", "cl-stat-grid cl-exercise-stats");
    for (const [label, value] of [
      ["Series", exercise.series],
      ["Repeticiones", exercise.repeticiones],
      ["Peso", exerciseWeight(exercise)],
      ["Descanso", `${exercise.descanso_segundos} segundos`]
    ]) {
      const card = element("article", "fp-card cl-stat-card");
      card.append(element("span", "", label), element("strong", "", String(value)));
      stats.append(card);
    }
    const context = element("article", "fp-card cl-routine-real-card");
    context.append(
      element("span", "fp-section-kicker", "CONTEXTO DE LA RUTINA"),
      element("h2", "", routine.objetivo || "Sin objetivo asociado"),
      element("p", "", routine.observaciones_entrenador || "Sin indicaciones adicionales.")
    );
    detail.replaceChildren(feature, stats, context);
    setStatus(status, "Ejercicio cargado desde tu rutina asignada.");
  } catch (_error) {
    title.textContent = "No pudimos cargar el ejercicio";
    lead.textContent = "Recargá la página para volver a intentar.";
    detail.replaceChildren(element("p", "cl-empty-state", "La información no está disponible temporalmente."));
    setStatus(status, "Ocurrió un error al consultar el ejercicio.", true);
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

function progressMetric(records, field) {
  return records.filter((item) => typeof item[field] === "number");
}

function signedMetric(value, unit) {
  if (value === null) return "—";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)} ${unit}`;
}

function progressChart(records, field, title, unit) {
  const card = element("article", "fp-card cl-evolution-card");
  card.append(element("span", "fp-section-kicker", title.toUpperCase()), element("h2", "", title));
  const values = progressMetric(records, field).slice(0, 12).reverse();
  if (!values.length) {
    card.append(element("p", "cl-empty-state", `No hay mediciones de ${title.toLowerCase()} para graficar.`));
    return card;
  }
  const numbers = values.map((item) => item[field]);
  const minimum = Math.min(...numbers);
  const maximum = Math.max(...numbers);
  const range = maximum - minimum;
  const chart = element("div", "cl-chart");
  chart.setAttribute("role", "img");
  chart.setAttribute(
    "aria-label",
    `${title}: ${values.map((item) => `${shortDate(item.fecha_utc)}, ${item[field]} ${unit}`).join("; ")}`
  );
  values.forEach((item) => {
    const column = element("span");
    const bar = element("i");
    const height = range === 0 ? 65 : 20 + ((item[field] - minimum) / range) * 80;
    bar.style.setProperty("--chart-height", `${height}%`);
    bar.title = `${item[field]} ${unit}`;
    column.append(bar, element("strong", "cl-chart-value", `${item[field]}`), element("small", "", shortDate(item.fecha_utc)));
    chart.append(column);
  });
  card.append(chart, element("p", "cl-note", `Últimas ${values.length} mediciones con ${unit}.`));
  return card;
}

async function initializeEvolution() {
  const root = document.querySelector("[data-client-evolution-root]");
  if (!root) return;
  const status = root.querySelector("[data-client-data-status]");
  const charts = root.querySelector("[data-evolution-charts]");
  try {
    const payload = await api("/api/v1/client/progress");
    const records = payload.progress;
    const weights = progressMetric(records, "peso_kg");
    const fat = progressMetric(records, "porcentaje_grasa");
    const stats = {
      records: String(records.length),
      weight: weights.length ? `${weights[0].peso_kg} kg` : "—",
      weightChange: weights.length > 1
        ? signedMetric(weights[0].peso_kg - weights[weights.length - 1].peso_kg, "kg")
        : "—",
      fat: fat.length ? `${fat[0].porcentaje_grasa}%` : "—"
    };
    root.querySelectorAll("[data-evolution-stat]").forEach((node) => {
      node.textContent = stats[node.dataset.evolutionStat] ?? "—";
    });
    charts.replaceChildren(
      progressChart(records, "peso_kg", "Evolución del peso", "kg"),
      progressChart(records, "porcentaje_grasa", "Grasa corporal", "%")
    );
    setStatus(
      status,
      records.length
        ? `${records.length} registros propios analizados.`
        : "Todavía no hay registros; podés comenzar desde Progreso."
    );
  } catch (_error) {
    charts.replaceChildren(element("p", "cl-empty-state", "La evolución no está disponible temporalmente."));
    setStatus(status, "No pudimos cargar tu evolución.", true);
  }
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
    const nextLink = root.querySelector("[data-dashboard-next-class-link]");
    if (next) {
      next.textContent = payload.next_class
        ? `${payload.next_class.actividad} · ${formatDateTime(payload.next_class.inicio_utc)} · ${payload.next_class.sede}`
        : "No tenés una próxima clase reservada.";
    }
    if (nextLink) {
      nextLink.href = payload.next_class
        ? "/templates/cliente/inicio/proxima-clase.html"
        : "/templates/cliente/clases/index.html";
      nextLink.firstChild.textContent = payload.next_class ? "Ver próxima clase " : "Explorar clases ";
    }
  } catch (_error) {
    const status = root.querySelector("[data-client-data-status]");
    setStatus(status, "No pudimos actualizar el resumen.", true);
  }
}

export async function initializeClientData({ csrfToken }) {
  await Promise.all([
    initializeClasses(csrfToken),
    initializeClassDetail(csrfToken),
    initializeNextClass(csrfToken),
    initializeEnrollments(csrfToken),
    initializeActivity(),
    initializeRoutines(),
    initializeNutritionPlans(),
    initializeNutritionDetail(),
    initializeTrainingDetail(),
    initializeExerciseDetail(),
    initializeProgress(csrfToken),
    initializeEvolution(),
    initializeDashboard()
  ]);
}
