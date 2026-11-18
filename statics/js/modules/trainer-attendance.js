import { initializeDrawer } from "./navigation-drawer.js";

initializeDrawer({
  panel: document.querySelector("#fp-sidebar"),
  toggle: document.querySelector("[data-menu-toggle]"),
  close: document.querySelector("[data-menu-close]"),
  overlay: document.querySelector("[data-menu-overlay]")
});

const content = document.querySelector("[data-attendance-content]");
const heading = document.querySelector("[data-attendance-heading]");
const breadcrumb = document.querySelector("[data-attendance-breadcrumb]");
const backLink = document.querySelector("[data-attendance-back]");
const statusNode = document.querySelector("[data-attendance-status]");

const state = {
  csrfToken: null,
  payload: null,
  filter: new URL(window.location.href).searchParams.get("estado") || "todas",
  original: new Map(),
  selected: new Map()
};
if (!["todas", "habilitadas", "proximas", "canceladas"].includes(state.filter)) state.filter = "todas";

const errorMessages = {
  csrf_failed: "La sesión cambió. Recargá la página antes de guardar.",
  permission_denied: "No tenés permiso para registrar estas asistencias.",
  enrollment_not_authorized: "La inscripción ya no está activa o no corresponde a una clase asignada.",
  attendance_class_cancelled: "No se puede registrar asistencia en una clase cancelada.",
  attendance_too_early: "La asistencia se habilita cuando comienza la clase.",
  authentication_required: "Tu sesión finalizó. Volvé a iniciar sesión."
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function link(label, href, className = "") {
  const node = element("a", className, label);
  node.href = href;
  return node;
}

function setStatus(message, type = "info") {
  statusNode.textContent = message;
  statusNode.dataset.state = type;
}

function requestError(error) {
  if (error?.error === "invalid_request" && error.field) {
    return `Revisá el campo ${String(error.field).replaceAll("_", " ")}.`;
  }
  return errorMessages[error?.error] || "No se pudo completar la operación. Intentá nuevamente.";
}

async function requestJson(path, options = {}) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  const method = (options.method || "GET").toUpperCase();
  if (!["GET", "HEAD"].includes(method)) headers["X-CSRF-Token"] = state.csrfToken;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    window.location.replace("/auth/login");
    throw payload;
  }
  if (!response.ok) throw payload;
  return payload;
}

function classes() {
  return state.payload?.options?.classes || [];
}

function enrollmentsFor(classId) {
  return (state.payload?.options?.enrollments || []).filter(
    (enrollment) => enrollment.clase_id === classId
  );
}

function classHasStarted(classItem) {
  const start = new Date(classItem.inicio_utc);
  return !Number.isNaN(start.getTime()) && start.getTime() <= Date.now();
}

function classIsEnabled(classItem) {
  return classItem.estado !== "cancelada" && classHasStarted(classItem);
}

function attendanceUrl(classId = null) {
  const params = new URLSearchParams();
  if (state.filter !== "todas") params.set("estado", state.filter);
  if (classId !== null) params.set("clase", String(classId));
  const query = params.toString();
  return `/auth/entrenador/asistencias${query ? `?${query}` : ""}`;
}

function syncFilterUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("estado");
  if (state.filter !== "todas") url.searchParams.set("estado", state.filter);
  window.history.replaceState({}, "", url);
}

function setPageHeading(title, description, crumb = title) {
  heading.replaceChildren(
    element("span", "fp-section-kicker", "ENTRENAMIENTO · ASISTENCIAS"),
    element("h1", "", title),
    element("p", "", description)
  );
  breadcrumb.textContent = crumb;
}

function dateParts(startValue, endValue) {
  const start = new Date(startValue);
  const end = new Date(endValue);
  if (Number.isNaN(start.getTime())) return { date: startValue, time: "Horario no disponible" };
  const date = new Intl.DateTimeFormat("es-AR", { weekday: "short", day: "2-digit", month: "short", year: "numeric" }).format(start);
  const formatter = new Intl.DateTimeFormat("es-AR", { hour: "2-digit", minute: "2-digit" });
  const time = Number.isNaN(end.getTime()) ? formatter.format(start) : `${formatter.format(start)}–${formatter.format(end)}`;
  return { date, time };
}

function classState(classItem) {
  if (classItem.estado === "cancelada") return { label: "Cancelada", className: "tr-state-cancelled" };
  if (!classHasStarted(classItem)) return { label: "Próxima", className: "fp-status-upcoming" };
  if (classItem.estado === "realizada") return { label: "Realizada", className: "fp-status-complete" };
  return { label: "Asistencia habilitada", className: "fp-status-live" };
}

function stateBadge(classItem) {
  const current = classState(classItem);
  const badge = element("span", `fp-status ${current.className}`);
  badge.append(element("span"), document.createTextNode(current.label));
  return badge;
}

function filteredClasses() {
  return classes().filter((classItem) => {
    if (state.filter === "habilitadas") return classIsEnabled(classItem);
    if (state.filter === "proximas") return classItem.estado !== "cancelada" && !classHasStarted(classItem);
    if (state.filter === "canceladas") return classItem.estado === "cancelada";
    return true;
  });
}

function classCard(classItem) {
  const card = element("article", "fp-card tr-class-card");
  const top = element("div", "tr-class-card-top");
  const title = element("div");
  title.append(element("span", "fp-section-kicker", `CLASE ${String(classItem.id).padStart(2, "0")}`), element("h2", "", classItem.actividad));
  top.append(title, stateBadge(classItem));
  const date = dateParts(classItem.inicio_utc, classItem.fin_utc);
  const metadata = element("dl", "tr-class-meta");
  metadata.append(
    metaItem("Fecha", date.date),
    metaItem("Horario", date.time),
    metaItem("Sede", classItem.sede),
    metaItem("Inscriptos", `${classItem.inscriptos} / ${classItem.cupo_maximo}`)
  );
  const action = link(
    classIsEnabled(classItem) ? "Tomar asistencia" : "Ver inscriptos",
    attendanceUrl(classItem.id),
    classIsEnabled(classItem) ? "fp-button fp-button-light" : "fp-button fp-button-outline"
  );
  card.append(top, metadata, action);
  return card;
}

function metaItem(term, value) {
  const wrapper = element("div");
  wrapper.append(element("dt", "", term), element("dd", "", value));
  return wrapper;
}

function renderClassList() {
  setPageHeading("Asistencias", "Elegí una de tus clases asignadas para consultar su nómina y registrar estados.");
  backLink.href = "/auth/entrenador";
  backLink.textContent = "← Volver al resumen";

  const page = element("div", "tr-attendance-list-layout");
  const toolbar = element("section", "fp-card tr-attendance-toolbar");
  const filterLabel = element("label", "tr-module-field");
  filterLabel.append(element("span", "", "Mostrar clases"));
  const filter = document.createElement("select");
  filter.append(
    new Option("Todas las asignadas", "todas"),
    new Option("Con asistencia habilitada", "habilitadas"),
    new Option("Próximas", "proximas"),
    new Option("Canceladas", "canceladas")
  );
  filter.value = state.filter;
  filterLabel.append(filter);
  const guidance = element("p", "tr-toolbar-note", "Las clases futuras y canceladas se muestran en modo consulta; el backend impide registrar asistencia.");
  toolbar.append(filterLabel, guidance);

  const resultHeader = element("div", "tr-module-result-heading");
  resultHeader.append(element("h2", "", "Clases asignadas"), element("span", "fp-count-badge"));
  const grid = element("div", "tr-class-grid");

  const update = () => {
    const results = filteredClasses();
    resultHeader.lastElementChild.textContent = `${results.length} ${results.length === 1 ? "clase" : "clases"}`;
    if (!results.length) {
      const empty = element("section", "fp-card tr-module-empty");
      empty.append(element("strong", "", classes().length ? "No hay clases con ese estado" : "No tenés clases asignadas"), element("p", "", classes().length ? "Elegí otro filtro para continuar." : "Cuando una sede te asigne una clase, aparecerá en este listado."));
      grid.replaceChildren(empty);
    } else {
      grid.replaceChildren(...results.map(classCard));
    }
    setStatus(`${results.length} clases visibles de ${classes().length} asignadas.`, "success");
  };

  filter.addEventListener("change", () => {
    state.filter = filter.value;
    syncFilterUrl();
    update();
  });
  page.append(toolbar, resultHeader, grid);
  content.replaceChildren(page);
  content.setAttribute("aria-busy", "false");
  update();
}

function attendanceStatus(value) {
  const labels = { presente: "Presente", ausente: "Ausente", sin_registrar: "Pendiente" };
  const classNames = { presente: "tr-attendance-present", ausente: "tr-attendance-absent", sin_registrar: "tr-attendance-pending" };
  return element("span", `tr-attendance-badge ${classNames[value] || classNames.sin_registrar}`, labels[value] || labels.sin_registrar);
}

function dirtyEnrollments(enrollments) {
  return enrollments.filter((item) => {
    const selected = state.selected.get(item.id) || "sin_registrar";
    return selected !== state.original.get(item.id) && selected !== "sin_registrar";
  });
}

function studentRow(enrollment, editable, onChange) {
  const row = element("article", "tr-student-row");
  const identity = element("div", "tr-student-identity");
  const initials = enrollment.alumno.split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase();
  identity.append(element("span", "tr-student-avatar", initials), element("strong", "", enrollment.alumno));

  const current = element("div", "tr-student-current");
  current.append(element("small", "", "Estado registrado"), attendanceStatus(enrollment.asistencia));

  const choices = element("fieldset", "tr-attendance-choices");
  choices.disabled = !editable;
  choices.append(element("legend", "fp-sr-only", `Asistencia de ${enrollment.alumno}`));
  for (const option of [
    { value: "presente", label: "Presente", className: "is-present" },
    { value: "ausente", label: "Ausente", className: "is-absent" }
  ]) {
    const label = element("label", `tr-attendance-choice ${option.className}`);
    const input = document.createElement("input");
    input.type = "radio";
    input.name = `attendance-${enrollment.id}`;
    input.value = option.value;
    input.checked = state.selected.get(enrollment.id) === option.value;
    input.addEventListener("change", () => {
      state.selected.set(enrollment.id, option.value);
      onChange();
    });
    label.append(input, element("span", "", option.label));
    choices.append(label);
  }
  row.append(identity, current, choices);
  return row;
}

function lockedReason(classItem) {
  if (classItem.estado === "cancelada") return "La clase está cancelada. La nómina permanece visible, pero no admite registros.";
  if (!classHasStarted(classItem)) return "La asistencia se habilitará cuando comience la clase.";
  return "La asistencia no está disponible para esta clase.";
}

function renderAttendance(classItem, successMessage = "") {
  const date = dateParts(classItem.inicio_utc, classItem.fin_utc);
  setPageHeading(classItem.actividad, `${date.date} · ${date.time} · ${classItem.sede}`, "Detalle de asistencia");
  backLink.href = attendanceUrl();
  backLink.textContent = "← Volver a clases";
  const enrollments = enrollmentsFor(classItem.id);
  const editable = classIsEnabled(classItem);

  state.original = new Map(enrollments.map((item) => [item.id, item.asistencia]));
  state.selected = new Map(enrollments.map((item) => [item.id, item.asistencia]));

  const page = element("div", "tr-attendance-detail-layout");
  const summary = element("section", "fp-card tr-attendance-summary");
  const summaryTop = element("div", "tr-class-card-top");
  const summaryTitle = element("div");
  summaryTitle.append(element("span", "fp-section-kicker", "CLASE SELECCIONADA"), element("h2", "", classItem.actividad));
  summaryTop.append(summaryTitle, stateBadge(classItem));
  const metadata = element("dl", "tr-class-meta");
  metadata.append(metaItem("Fecha", date.date), metaItem("Horario", date.time), metaItem("Sede", classItem.sede), metaItem("Cupo", `${classItem.inscriptos} inscriptos de ${classItem.cupo_maximo}`));
  summary.append(summaryTop, metadata);
  if (!editable) summary.append(element("p", "tr-attendance-locked", lockedReason(classItem)));

  const roster = element("section", "tr-roster-section");
  const rosterHeader = element("div", "tr-module-result-heading");
  const rosterTitle = element("div");
  rosterTitle.append(element("span", "fp-section-kicker", "NÓMINA REAL"), element("h2", "", "Alumnos inscriptos"));
  rosterHeader.append(rosterTitle, element("span", "fp-count-badge", `${enrollments.length} ${enrollments.length === 1 ? "alumno" : "alumnos"}`));
  const list = element("div", "tr-student-list");
  const actions = element("div", "fp-card tr-attendance-savebar");
  const pendingCopy = element("p", "", editable ? "No hay cambios pendientes." : lockedReason(classItem));
  const actionButtons = element("div", "tr-attendance-save-actions");
  const reset = element("button", "fp-button fp-button-outline", "Descartar cambios");
  reset.type = "button";
  reset.disabled = true;
  const save = element("button", "fp-button fp-button-light", "Guardar cambios");
  save.type = "button";
  save.disabled = true;

  const updateDirtyState = () => {
    const dirty = dirtyEnrollments(enrollments);
    save.disabled = !editable || !dirty.length;
    reset.disabled = !editable || !dirty.length;
    save.textContent = dirty.length ? `Guardar cambios (${dirty.length})` : "Guardar cambios";
    pendingCopy.textContent = dirty.length
      ? `${dirty.length} ${dirty.length === 1 ? "asistencia pendiente" : "asistencias pendientes"} de guardar.`
      : (editable ? "No hay cambios pendientes." : lockedReason(classItem));
  };

  reset.addEventListener("click", () => {
    renderAttendance(classItem);
    setStatus("Cambios descartados; no se modificó la asistencia guardada.", "info");
  });

  if (!enrollments.length) {
    const empty = element("div", "fp-card tr-module-empty");
    empty.append(element("strong", "", "No hay alumnos inscriptos"), element("p", "", "Solo aparecen inscripciones activas pertenecientes a esta clase."));
    list.append(empty);
  } else {
    list.append(...enrollments.map((item) => studentRow(item, editable && item.puede_registrar, updateDirtyState)));
  }

  save.addEventListener("click", async () => {
    const changes = dirtyEnrollments(enrollments);
    if (!changes.length) return;
    save.disabled = true;
    setStatus(`Guardando ${changes.length} ${changes.length === 1 ? "asistencia" : "asistencias"}…`, "loading");
    let saved = 0;
    try {
      for (const enrollment of changes) {
        await requestJson("/api/v1/trainer/attendance", {
          method: "POST",
          body: { inscripcion_id: enrollment.id, estado: state.selected.get(enrollment.id) }
        });
        saved += 1;
      }
      await refreshData();
      const refreshedClass = classes().find((item) => item.id === classItem.id);
      if (refreshedClass) {
        renderAttendance(refreshedClass, `${saved} ${saved === 1 ? "asistencia guardada" : "asistencias guardadas"} correctamente.`);
      } else {
        renderMissing();
      }
    } catch (error) {
      try {
        await refreshData();
        const refreshedClass = classes().find((item) => item.id === classItem.id);
        if (refreshedClass) renderAttendance(refreshedClass);
        else renderMissing();
      } catch (_refreshError) {
        save.disabled = false;
      }
      setStatus(`${saved ? `${saved} cambios se guardaron. ` : ""}${requestError(error)}`, "error");
    }
  });

  actionButtons.append(reset, save);
  actions.append(pendingCopy, actionButtons);
  roster.append(rosterHeader, list);
  if (enrollments.length) roster.append(actions);
  page.append(summary, roster);
  content.replaceChildren(page);
  content.setAttribute("aria-busy", "false");
  updateDirtyState();
  setStatus(successMessage || (editable ? "Seleccioná Presente o Ausente y guardá los cambios." : lockedReason(classItem)), successMessage ? "success" : "info");
}

function renderMissing() {
  setPageHeading("Clase no disponible", "La clase solicitada no pertenece a tu agenda asignada.", "Clase no disponible");
  backLink.href = attendanceUrl();
  backLink.textContent = "← Volver a clases";
  const card = element("section", "fp-card tr-module-empty");
  card.append(element("strong", "", "No encontramos esa clase"), element("p", "", "Puede que ya no exista o que corresponda a otro entrenador."), link("Ir a clases", attendanceUrl(), "fp-button fp-button-primary"));
  content.replaceChildren(card);
  content.setAttribute("aria-busy", "false");
  setStatus("No se modificó ninguna asistencia.", "error");
}

async function refreshData() {
  state.payload = await requestJson("/api/v1/trainer/dashboard");
}

function renderCurrentView() {
  const classId = Number(new URL(window.location.href).searchParams.get("clase"));
  if (!classId) {
    renderClassList();
    return;
  }
  const classItem = classes().find((item) => item.id === classId);
  if (!classItem) {
    renderMissing();
    return;
  }
  renderAttendance(classItem);
}

function configureIdentity(identity) {
  state.csrfToken = identity.csrf_token;
  const fullName = `${identity.user.nombre} ${identity.user.apellido}`.trim();
  const initials = `${identity.user.nombre[0] || ""}${identity.user.apellido[0] || ""}`.toUpperCase();
  document.querySelectorAll("[data-role-user-name], [data-role-user]").forEach((node) => { node.textContent = fullName; });
  document.querySelectorAll(".fp-avatar, .fp-client-avatar").forEach((node) => { node.textContent = initials; });
  const logout = document.querySelector("[data-role-logout]");
  const csrf = logout.elements.namedItem("csrf_token");
  const logoutButton = logout.querySelector("button");
  csrf.value = state.csrfToken;
  logoutButton.disabled = false;
  logout.addEventListener("submit", async (event) => {
    event.preventDefault();
    logoutButton.disabled = true;
    const response = await fetch("/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
      body: new URLSearchParams({ csrf_token: state.csrfToken })
    });
    if (response.ok) window.location.assign("/auth/login?logout=1");
    else {
      logoutButton.disabled = false;
      setStatus("No pudimos cerrar la sesión.", "error");
    }
  });
}

async function initialize() {
  try {
    const identity = await requestJson("/auth/me");
    if (identity.user?.rol !== "Entrenador" || !identity.csrf_token) {
      window.location.replace("/auth/login");
      return;
    }
    configureIdentity(identity);
    await refreshData();
    renderCurrentView();
  } catch (error) {
    content.setAttribute("aria-busy", "false");
    setStatus(requestError(error), "error");
    const retry = element("button", "fp-button fp-button-primary", "Reintentar");
    retry.type = "button";
    retry.addEventListener("click", () => window.location.reload());
    const card = element("section", "fp-card tr-module-empty");
    card.append(element("strong", "", "No pudimos cargar las asistencias"), element("p", "", "Verificá tu sesión o intentá nuevamente."), retry);
    content.replaceChildren(card);
  }
}

initialize();
