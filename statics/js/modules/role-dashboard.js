import { initializeSmartAssistant } from "../assistant/loader.js";
import { initializeDrawer } from "./navigation-drawer.js";

initializeDrawer({
  panel: document.querySelector("#fp-sidebar"),
  toggle: document.querySelector("[data-menu-toggle]"),
  close: document.querySelector("[data-menu-close]"),
  overlay: document.querySelector("[data-menu-overlay]")
});

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function labelText(key) {
  return key.replaceAll("_", " ").replace(/^./, (value) => value.toUpperCase());
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  return String(value);
}

function renderMetrics(mount, metrics) {
  mount.replaceChildren(...metrics.map((metric) => {
    const card = element("article", "fp-card cl-dashboard-metric");
    card.append(
      element("span", "", metric.label),
      element("strong", "", displayValue(metric.value))
    );
    return card;
  }));
}

function renderSection(section) {
  const container = element("section", "fp-card fp-role-section");
  container.append(element("h2", "", section.title));
  if (!section.rows?.length) {
    container.append(element("p", "cl-empty-state", "No hay datos registrados para este módulo."));
    return container;
  }
  const keys = [...new Set(section.rows.flatMap((row) => Object.keys(row)))];
  const wrapper = element("div", "fp-table-scroll");
  const table = element("table", "fp-role-table");
  const header = element("thead");
  const headerRow = element("tr");
  keys.forEach((key) => headerRow.append(element("th", "", labelText(key))));
  header.append(headerRow);
  const body = element("tbody");
  for (const row of section.rows) {
    const tableRow = element("tr");
    keys.forEach((key) => tableRow.append(element("td", "", displayValue(row[key]))));
    body.append(tableRow);
  }
  table.append(header, body);
  wrapper.append(table);
  container.append(wrapper);
  return container;
}

function inputField(config) {
  const label = element("label", "", config.label);
  let control;
  if (config.options) {
    control = document.createElement("select");
    if (!config.required) control.append(new Option("Sin cambio", ""));
    for (const option of config.options) {
      control.append(new Option(option.label, String(option.value)));
    }
  } else if (config.multiline) {
    control = document.createElement("textarea");
    control.rows = config.rows || 3;
  } else {
    control = document.createElement("input");
    control.type = config.type || "text";
    if (config.min !== undefined) control.min = String(config.min);
    if (config.max !== undefined) control.max = String(config.max);
    if (config.step !== undefined) control.step = String(config.step);
  }
  control.name = config.name;
  control.required = Boolean(config.required);
  control.dataset.valueType = config.valueType || "string";
  if (config.placeholder) control.placeholder = config.placeholder;
  label.append(control);
  return label;
}

function formPayload(form) {
  const result = {};
  for (const control of form.elements) {
    if (!control.name || control.type === "submit" || control.value === "") continue;
    if (control.dataset.valueType === "integer") result[control.name] = Number(control.value);
    else if (control.dataset.valueType === "boolean") result[control.name] = control.value === "true";
    else if (control.dataset.valueType === "datetime") {
      result[control.name] = new Date(control.value).toISOString().slice(0, 19) + "Z";
    } else result[control.name] = control.value;
  }
  return result;
}

function actionForm(config, csrfToken, status, refresh) {
  const card = element("section", "fp-card fp-role-action-card");
  card.append(element("h3", "", config.title));
  if (config.note) card.append(element("p", "", config.note));
  const form = element("form", "fp-role-form");
  const fields = element("div", "cl-form-grid");
  config.fields.forEach((field) => fields.append(inputField(field)));
  const button = element("button", "fp-button fp-button-primary", config.button || "Guardar");
  button.type = "submit";
  form.append(fields, button);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    button.disabled = true;
    status(config.pending || "Guardando cambios…");
    const raw = formPayload(form);
    const path = typeof config.path === "function" ? config.path(raw) : config.path;
    const payload = config.transform ? config.transform(raw) : raw;
    try {
      const response = await fetch(path, {
        method: config.method || "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken
        },
        body: JSON.stringify(payload)
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw result;
      form.reset();
      status(config.success || "Cambio guardado correctamente.");
      await refresh();
    } catch (error) {
      const messages = {
        csrf_failed: "La sesión cambió. Recargá la página.",
        student_not_authorized: "El alumno no está autorizado para este entrenador.",
        capacity_below_enrollments: "El cupo no puede ser menor a las inscripciones activas.",
        machine_state_unchanged: "La máquina ya tiene ese estado.",
        cannot_change_own_access: "No podés cambiar tu propio rol o estado.",
        required_admin_permissions: "Los permisos mínimos del Administrador no se pueden quitar.",
        required_role_permissions: "Los permisos mínimos del rol no se pueden quitar.",
        managed_permission_conflict: "Un permiso base no puede asignarse a otro rol.",
        trainer_has_scheduled_classes: "Primero cancelá o reasigná las clases futuras del entrenador."
      };
      status(messages[error.error] || `No se pudo guardar (${error.error || "error"}).`, true);
    } finally {
      button.disabled = false;
    }
  });
  card.append(form);
  return card;
}

function trainerForms(payload, csrfToken, status, refresh) {
  const students = (payload.options?.students || []).map((item) => ({ value: item.id, label: `${item.apellido}, ${item.nombre}` }));
  const sites = (payload.options?.sites || []).map((item) => ({ value: item.id, label: item.nombre }));
  const enrollments = (payload.options?.enrollments || []).map((item) => ({ value: item.id, label: `${item.alumno} · ${item.actividad} · ${item.inicio_utc}` }));
  const routines = (payload.options?.routines || []).map((item) => ({ value: item.id, label: `${item.nombre} · ${item.cliente}` }));
  const exercises = (payload.options?.exercises || []).map((item) => ({ value: item.id, label: item.nombre }));
  return [
    actionForm({ title: "Asignar rutina", path: "/api/v1/trainer/routines", fields: [
      { name: "cliente_id", label: "Alumno autorizado", options: students, valueType: "integer", required: true },
      { name: "nombre", label: "Nombre de rutina", required: true },
      { name: "descripcion", label: "Descripción", multiline: true }
    ], success: "Rutina asignada." }, csrfToken, status, refresh),
    actionForm({ title: "Crear ejercicio", path: "/api/v1/trainer/exercises", fields: [
      { name: "nombre", label: "Ejercicio", required: true },
      { name: "grupo_muscular", label: "Grupo muscular" },
      { name: "descripcion", label: "Descripción", multiline: true }
    ], success: "Ejercicio creado." }, csrfToken, status, refresh),
    actionForm({ title: "Editar rutina", method: "PATCH", path: (raw) => `/api/v1/trainer/routines/${raw.routine_id}`, transform: ({ routine_id, ...rest }) => rest, fields: [
      { name: "routine_id", label: "Rutina", options: routines, valueType: "integer", required: true },
      { name: "nombre", label: "Nuevo nombre" },
      { name: "descripcion", label: "Nueva descripción", multiline: true },
      { name: "observaciones", label: "Indicaciones", multiline: true }
    ], success: "Rutina actualizada." }, csrfToken, status, refresh),
    actionForm({ title: "Editar ejercicio", method: "PATCH", path: (raw) => `/api/v1/trainer/exercises/${raw.exercise_id}`, transform: ({ exercise_id, ...rest }) => rest, fields: [
      { name: "exercise_id", label: "Ejercicio", options: exercises, valueType: "integer", required: true },
      { name: "nombre", label: "Nuevo nombre" },
      { name: "grupo_muscular", label: "Grupo muscular" },
      { name: "descripcion", label: "Descripción", multiline: true }
    ], success: "Ejercicio actualizado." }, csrfToken, status, refresh),
    actionForm({ title: "Agregar ejercicio a rutina", path: (raw) => `/api/v1/trainer/routines/${raw.routine_id}/exercises`, transform: ({ routine_id, ...rest }) => rest, fields: [
      { name: "routine_id", label: "Rutina", options: routines, valueType: "integer", required: true },
      { name: "ejercicio_id", label: "Ejercicio", options: exercises, valueType: "integer", required: true },
      { name: "orden", label: "Orden", type: "number", min: 1, max: 100, valueType: "integer", required: true },
      { name: "series", label: "Series", type: "number", min: 1, max: 100, valueType: "integer", required: true },
      { name: "repeticiones", label: "Repeticiones o segundos", type: "number", min: 1, max: 1000, valueType: "integer", required: true },
      { name: "peso_gramos", label: "Carga (gramos)", type: "number", min: 0, valueType: "integer" },
      { name: "descanso_segundos", label: "Descanso (segundos)", type: "number", min: 0, max: 3600, valueType: "integer", required: true }
    ], success: "Ejercicio agregado a la rutina." }, csrfToken, status, refresh),
    actionForm({ title: "Registrar asistencia", path: "/api/v1/trainer/attendance", fields: [
      { name: "inscripcion_id", label: "Inscripción asignada", options: enrollments, valueType: "integer", required: true },
      { name: "estado", label: "Estado", options: [{ value: "presente", label: "Presente" }, { value: "ausente", label: "Ausente" }], required: true }
    ], success: "Asistencia registrada." }, csrfToken, status, refresh),
    actionForm({ title: "Agregar disponibilidad", path: "/api/v1/trainer/availability", fields: [
      { name: "sede_id", label: "Sede", options: sites, valueType: "integer", required: true },
      { name: "dia_semana", label: "Día (1 lunes - 7 domingo)", type: "number", min: 1, max: 7, valueType: "integer", required: true },
      { name: "hora_inicio", label: "Hora inicio", type: "time", required: true },
      { name: "hora_fin", label: "Hora fin", type: "time", required: true }
    ], success: "Disponibilidad agregada." }, csrfToken, status, refresh)
  ];
}

function managerForms(payload, csrfToken, status, refresh) {
  const activities = (payload.options?.activities || []).filter((item) => item.habilitada).map((item) => ({ value: item.id, label: item.nombre }));
  const trainers = (payload.options?.trainers || []).map((item) => ({ value: item.id, label: item.nombre }));
  return [
    actionForm({ title: "Agregar actividad a la sede", path: "/api/v1/manager/activities", fields: [
      { name: "nombre", label: "Nombre", required: true }
    ], success: "Actividad habilitada en la sede." }, csrfToken, status, refresh),
    actionForm({ title: "Programar clase", path: "/api/v1/manager/classes", fields: [
      { name: "actividad_id", label: "Actividad", options: activities, valueType: "integer", required: true },
      { name: "entrenador_id", label: "Entrenador", options: trainers, valueType: "integer", required: true },
      { name: "inicio_utc", label: "Inicio", type: "datetime-local", valueType: "datetime", required: true },
      { name: "fin_utc", label: "Fin", type: "datetime-local", valueType: "datetime", required: true },
      { name: "cupo_maximo", label: "Cupo", type: "number", min: 1, valueType: "integer", required: true }
    ], success: "Clase programada." }, csrfToken, status, refresh),
    actionForm({ title: "Actualizar cupo o estado", method: "PATCH", path: (raw) => `/api/v1/manager/classes/${raw.class_id}`, transform: ({ class_id, ...rest }) => rest, fields: [
      { name: "class_id", label: "ID de clase", type: "number", min: 1, valueType: "integer", required: true },
      { name: "cupo_maximo", label: "Nuevo cupo", type: "number", min: 1, valueType: "integer" },
      { name: "estado", label: "Estado", options: [{ value: "programada", label: "Programada" }, { value: "cancelada", label: "Cancelada" }, { value: "realizada", label: "Realizada" }] }
    ], success: "Clase actualizada." }, csrfToken, status, refresh),
    actionForm({ title: "Gestionar vínculo de Entrenador", method: "PATCH", path: (raw) => `/api/v1/manager/personnel/${raw.user_id}`, transform: ({ user_id, ...rest }) => rest, note: "No se puede desactivar un entrenador con clases futuras programadas en la sede.", fields: [
      { name: "user_id", label: "ID de usuario Entrenador", type: "number", min: 1, valueType: "integer", required: true },
      { name: "activo_en_sede", label: "Vínculo", options: [{ value: "true", label: "Activo" }, { value: "false", label: "Inactivo" }], valueType: "boolean", required: true }
    ], success: "Vínculo del personal actualizado." }, csrfToken, status, refresh)
  ];
}

function adminForms(payload, csrfToken, status, refresh) {
  const roles = (payload.options?.roles || []).map((item) => ({ value: item.id, label: item.nombre }));
  const sites = (payload.options?.sites || []).map((item) => ({ value: item.id, label: item.nombre }));
  const permissionHelp = (payload.options?.permissions || []).map((item) => `${item.id}: ${item.clave}`).join(" · ");
  return [
    actionForm({ title: "Crear usuario local", path: "/api/v1/admin/users", note: "Entrenador requiere especialidad y sede; Jefe o Técnico requieren sede. Google se vincula por separado.", fields: [
      { name: "nombre", label: "Nombre", required: true }, { name: "apellido", label: "Apellido", required: true },
      { name: "nombre_usuario", label: "Usuario", required: true }, { name: "email", label: "Email", type: "email", required: true },
      { name: "rol_id", label: "Rol", options: roles, valueType: "integer", required: true },
      { name: "especialidad", label: "Especialidad (Entrenador)" },
      { name: "sede_id", label: "Sede del rol", options: sites, valueType: "integer" }
    ], success: "Usuario creado sin credenciales locales." }, csrfToken, status, refresh),
    actionForm({ title: "Actualizar acceso de usuario", method: "PATCH", path: (raw) => `/api/v1/admin/users/${raw.user_id}`, transform: ({ user_id, ...rest }) => rest, fields: [
      { name: "user_id", label: "ID de usuario", type: "number", min: 1, valueType: "integer", required: true },
      { name: "rol_id", label: "Nuevo rol", options: roles, valueType: "integer" },
      { name: "especialidad", label: "Especialidad (si cambia a Entrenador)" },
      { name: "sede_id", label: "Sede del nuevo rol", options: sites, valueType: "integer" },
      { name: "activo", label: "Estado", options: [{ value: "true", label: "Activo" }, { value: "false", label: "Inactivo" }], valueType: "boolean" }
    ], success: "Acceso actualizado." }, csrfToken, status, refresh),
    actionForm({ title: "Crear sede", path: "/api/v1/admin/sites", fields: [
      { name: "nombre", label: "Nombre", required: true }, { name: "direccion", label: "Dirección", required: true },
      { name: "zona_horaria", label: "Zona horaria IANA", placeholder: "America/Argentina/Buenos_Aires", required: true }
    ], success: "Sede creada." }, csrfToken, status, refresh),
    actionForm({ title: "Crear actividad", path: "/api/v1/admin/activities", fields: [
      { name: "nombre", label: "Nombre", required: true }
    ], success: "Actividad creada." }, csrfToken, status, refresh),
    actionForm({ title: "Crear membresía", path: "/api/v1/admin/memberships", fields: [
      { name: "nombre", label: "Nombre", required: true },
      { name: "precio_unidades_menores", label: "Precio en centavos", type: "number", min: 0, valueType: "integer", required: true },
      { name: "moneda", label: "Moneda", placeholder: "ARS", required: true },
      { name: "descripcion", label: "Descripción", multiline: true }
    ], success: "Membresía creada." }, csrfToken, status, refresh),
    actionForm({ title: "Configurar permisos del rol", method: "PUT", path: (raw) => `/api/v1/admin/roles/${raw.role_id}/permissions`, transform: ({ role_id, permission_ids }) => ({ permission_ids: String(permission_ids).split(",").map((value) => Number(value.trim())).filter(Number.isInteger) }), note: `Ingresá IDs separados por coma. Los permisos base son obligatorios y exclusivos. ${permissionHelp}`, fields: [
      { name: "role_id", label: "Rol", options: roles, valueType: "integer", required: true },
      { name: "permission_ids", label: "IDs de permisos", placeholder: "1, 2", required: true }
    ], success: "Permisos del rol actualizados." }, csrfToken, status, refresh)
  ];
}

function technicianForms(payload, csrfToken, status, refresh) {
  const machines = (payload.options?.machines || []).map((item) => ({ value: item.id, label: `${item.tipo} · ${item.estado}` }));
  const tickets = (payload.options?.tickets || []).map((item) => ({ value: item.id, label: `#${item.id} · ${item.maquina}` }));
  const machineStates = [{ value: "operativa", label: "Operativa" }, { value: "en_reparacion", label: "En reparación" }, { value: "fuera_de_servicio", label: "Fuera de servicio" }];
  return [
    actionForm({ title: "Registrar incidencia", path: "/api/v1/technician/tickets", fields: [
      { name: "maquina_id", label: "Máquina", options: machines, valueType: "integer", required: true },
      { name: "descripcion", label: "Descripción", multiline: true, required: true }
    ], success: "Incidencia registrada." }, csrfToken, status, refresh),
    actionForm({ title: "Actualizar ticket", method: "PATCH", path: (raw) => `/api/v1/technician/tickets/${raw.ticket_id}`, transform: ({ ticket_id, ...rest }) => rest, fields: [
      { name: "ticket_id", label: "Ticket", options: tickets, valueType: "integer", required: true },
      { name: "estado", label: "Estado", options: [{ value: "abierto", label: "Abierto" }, { value: "en_proceso", label: "En proceso" }, { value: "resuelto", label: "Resuelto" }, { value: "cancelado", label: "Cancelado" }], required: true }
    ], success: "Ticket actualizado." }, csrfToken, status, refresh),
    actionForm({ title: "Cambiar estado de máquina", method: "PATCH", path: (raw) => `/api/v1/technician/machines/${raw.machine_id}`, transform: ({ machine_id, ...rest }) => rest, fields: [
      { name: "machine_id", label: "Máquina", options: machines, valueType: "integer", required: true },
      { name: "estado", label: "Nuevo estado", options: machineStates, required: true },
      { name: "ticket_id", label: "Ticket relacionado", options: tickets, valueType: "integer" },
      { name: "descripcion", label: "Detalle del cambio", multiline: true }
    ], success: "Estado e historial actualizados." }, csrfToken, status, refresh)
  ];
}

const root = document.body;
const role = root.dataset.roleDashboard;
const expectedRole = root.dataset.roleName;
const statusNode = document.querySelector("[data-role-status]");
const metricsMount = document.querySelector("[data-role-metrics]");
const sectionsMount = document.querySelector("[data-role-sections]");
let csrfToken = null;

const showStatus = (message, error = false) => {
  statusNode.textContent = message;
  statusNode.dataset.error = error ? "true" : "false";
};

async function loadDashboard() {
  const response = await fetch(`/api/v1/${role}/dashboard`, {
    credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" }
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw payload;
  renderMetrics(metricsMount, payload.metrics || []);
  const sections = (payload.sections || []).map(renderSection);
  const actions = element("section", "fp-role-actions");
  actions.append(element("h2", "", "Acciones autorizadas"));
  const factory = { trainer: trainerForms, manager: managerForms, admin: adminForms, technician: technicianForms }[role];
  factory?.(payload, csrfToken, showStatus, loadDashboard).forEach((form) => actions.append(form));
  sectionsMount.replaceChildren(actions, ...sections);
  showStatus("Información actualizada desde FitPath.");
}

async function initialize() {
  try {
    const response = await fetch("/auth/me", { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } });
    if (response.status === 401) { window.location.replace("/auth/login"); return; }
    if (!response.ok) throw new Error("session_failed");
    const identity = await response.json();
    if (identity.user?.rol !== expectedRole || !identity.csrf_token) { window.location.replace("/auth/login"); return; }
    csrfToken = identity.csrf_token;
    const fullName = `${identity.user.nombre} ${identity.user.apellido}`.trim();
    document.querySelectorAll("[data-role-user-name]").forEach((node) => { node.textContent = fullName; });
    document.querySelectorAll("[data-role-user]").forEach((node) => { node.textContent = fullName; });
    document.querySelectorAll(".fp-avatar, .fp-client-avatar").forEach((node) => {
      node.textContent = `${identity.user.nombre[0] || ""}${identity.user.apellido[0] || ""}`.toUpperCase();
    });
    const logout = document.querySelector("[data-role-logout]");
    const csrf = logout.elements.namedItem("csrf_token");
    const button = logout.querySelector("button");
    csrf.value = csrfToken;
    button.disabled = false;
    logout.addEventListener("submit", async (event) => {
      event.preventDefault();
      button.disabled = true;
      const result = await fetch("/auth/logout", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
        body: new URLSearchParams({ csrf_token: csrfToken })
      });
      if (result.ok) window.location.assign("/auth/login?logout=1");
      else { button.disabled = false; showStatus("No pudimos cerrar la sesión.", true); }
    });
    await loadDashboard();
  } catch (_error) {
    showStatus("No pudimos cargar el panel autorizado.", true);
  }
}

initialize();
initializeSmartAssistant().catch(() => {});
