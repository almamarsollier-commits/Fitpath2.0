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

function renderSection(section, rowAction = null) {
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
  if (rowAction) headerRow.append(element("th", "", "Acciones"));
  header.append(headerRow);
  const body = element("tbody");
  for (const row of section.rows) {
    const tableRow = element("tr");
    keys.forEach((key) => tableRow.append(element("td", "", displayValue(row[key]))));
    if (rowAction) {
      const actionCell = element("td");
      const actionLabel = typeof rowAction.label === "function" ? rowAction.label(row) : rowAction.label;
      const button = element("button", "fp-button fp-button-outline", actionLabel);
      button.type = "button";
      button.setAttribute("aria-label", rowAction.ariaLabel(row));
      button.disabled = Boolean(rowAction.disabled?.(row));
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await rowAction.run(row);
        } finally {
          button.disabled = false;
        }
      });
      actionCell.append(button);
      tableRow.append(actionCell);
    }
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
    control.multiple = Boolean(config.multiple);
    if (config.size !== undefined) control.size = config.size;
    if (!config.required && !config.multiple) control.append(new Option("Sin cambio", ""));
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
  control.dataset.includeEmpty = config.includeEmpty ? "true" : "false";
  if (config.maxLength !== undefined) control.maxLength = config.maxLength;
  if (config.placeholder) control.placeholder = config.placeholder;
  label.append(control);
  return label;
}

function formPayload(form) {
  const result = {};
  for (const control of form.elements) {
    if (!control.name || control.type === "submit") continue;
    if (control.tagName === "SELECT" && control.multiple) {
      result[control.name] = [...control.selectedOptions].map((option) => (
        control.dataset.valueType === "integer" ? Number(option.value) : option.value
      ));
      continue;
    }
    if (control.value === "") {
      if (control.dataset.includeEmpty === "true") result[control.name] = null;
      continue;
    }
    if (control.dataset.valueType === "integer") result[control.name] = Number(control.value);
    else if (control.dataset.valueType === "boolean") result[control.name] = control.value === "true";
    else if (control.dataset.valueType === "datetime") {
      result[control.name] = new Date(control.value).toISOString().slice(0, 19) + "Z";
    } else result[control.name] = control.value;
  }
  return result;
}

function mutationErrorMessage(error) {
  const messages = {
    csrf_failed: "La sesión cambió. Recargá la página.",
    site_conflict: "Los datos de la sede entran en conflicto con la información guardada.",
    site_not_found: "La sede seleccionada ya no está disponible.",
    membership_conflict: "Los datos de la membresía entran en conflicto con el catálogo guardado.",
    membership_not_found: "La membresía seleccionada ya no está disponible.",
    benefit_conflict: "Ya existe un beneficio con esos datos.",
    benefit_not_found: "Uno de los beneficios seleccionados ya no está disponible.",
    membership_benefit_conflict: "No se pudieron actualizar los beneficios de la membresía.",
    availability_conflict: "Esa disponibilidad ya está registrada.",
    availability_not_found: "La disponibilidad ya no existe o no te pertenece.",
    availability_has_scheduled_classes: "No podés eliminar esta disponibilidad porque cubre clases programadas.",
    attendance_class_cancelled: "No se puede registrar asistencia en una clase cancelada.",
    attendance_too_early: "La asistencia se habilita cuando comienza la clase.",
    enrollment_not_authorized: "La inscripción ya no está activa o no corresponde a una clase asignada.",
    activity_already_linked: "La actividad ya pertenece a esta sede.",
    class_not_found: "La clase ya no existe o pertenece a otra sede.",
    class_relationship_conflict: "La actividad o el entrenador no están habilitados en esta sede.",
    site_personnel_not_found: "El entrenador no pertenece a esta sede.",
    trainer_unavailable: "El entrenador no está disponible en ese horario.",
    trainer_schedule_conflict: "El entrenador ya tiene otra clase en ese horario.",
    activity_conflict: "Ya existe una actividad con ese nombre.",
    user_identity_conflict: "El usuario o email ya pertenece a otra cuenta.",
    user_not_found: "El usuario ya no existe.",
    role_not_found: "El rol seleccionado ya no existe.",
    role_profile_conflict: "No se pudo actualizar el perfil asociado al rol.",
    permission_not_found: "Uno de los permisos seleccionados ya no existe.",
    machine_not_authorized: "La máquina no pertenece a tu sede asignada.",
    ticket_not_authorized: "El ticket no corresponde a esa máquina o no está asignado a tu cuenta.",
    ticket_not_found: "El ticket ya no existe, no está asignado a tu cuenta o pertenece a otra sede.",
    ticket_create_failed: "No se pudo registrar la incidencia.",
    machine_update_failed: "No se pudo guardar el estado de la máquina.",
    site_not_authorized: "No tenés autorización para gestionar disponibilidad en esa sede.",
    permission_denied: "No tenés permisos para realizar esta operación.",
    authentication_required: "Tu sesión finalizó. Volvé a iniciar sesión.",
    routine_not_found: "La rutina ya no existe o no te pertenece.",
    routine_exercise_not_found: "El ejercicio asignado ya no existe o no te pertenece.",
    exercise_assignment_conflict: "No se pudo guardar el orden o los parámetros del ejercicio.",
    objective_not_assigned_to_client: "El objetivo seleccionado no pertenece al cliente de la rutina.",
    activity_not_found: "La actividad no pertenece a tu sede o ya no está disponible.",
    student_not_authorized: "El alumno no está autorizado para este entrenador.",
    capacity_below_enrollments: "El cupo no puede ser menor a las inscripciones activas.",
    machine_state_unchanged: "La máquina ya tiene ese estado.",
    machine_conflict: "No se pudo registrar la máquina con los datos indicados.",
    cannot_change_own_access: "No podés cambiar tu propio rol o estado.",
    required_admin_permissions: "Los permisos mínimos del Administrador no se pueden quitar.",
    required_role_permissions: "Los permisos mínimos del rol no se pueden quitar.",
    managed_permission_conflict: "Un permiso base no puede asignarse a otro rol.",
    trainer_has_scheduled_classes: "Primero cancelá o reasigná las clases futuras del entrenador."
  };
  if (error.error === "invalid_request" && error.field) {
    return `Revisá el campo ${labelText(error.field)}.`;
  }
  if (error.error === "invalid_request") return "La solicitud contiene datos inválidos.";
  return messages[error.error] || `No se pudo guardar (${error.error || "error"}).`;
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
      await refresh();
      status(config.success || "Cambio guardado correctamente.");
    } catch (error) {
      status(mutationErrorMessage(error), true);
    } finally {
      button.disabled = false;
    }
  });
  card.append(form);
  return card;
}

function trainerNutritionViewer(studentRows) {
  const card = element("section", "fp-card fp-role-action-card");
  card.append(
    element("h3", "", "Consultar alimentación"),
    element("p", "", "Información asignada de solo lectura. No permite crear, editar ni asignar planes.")
  );
  const form = element("form", "fp-role-form");
  const fields = element("div", "cl-form-grid");
  const label = element("label", "", "Cliente vinculado");
  const select = document.createElement("select");
  select.name = "cliente_id";
  select.required = true;
  select.append(new Option(
    studentRows.length ? "Seleccioná un cliente" : "No hay clientes vinculados",
    ""
  ));
  studentRows.forEach((student) => {
    select.append(new Option(`${student.apellido}, ${student.nombre}`, String(student.id)));
  });
  label.append(select);
  fields.append(label);
  const button = element("button", "fp-button fp-button-primary", "Consultar planes");
  button.type = "submit";
  button.disabled = !studentRows.length;
  const localStatus = element(
    "p",
    "cl-payment-page-status",
    studentRows.length
      ? "Seleccioná un cliente autorizado."
      : "No hay clientes vinculados para consultar."
  );
  localStatus.setAttribute("role", "status");
  localStatus.setAttribute("aria-live", "polite");
  const results = element("div", "cl-history-list");
  results.append(element("p", "cl-empty-state", "La consulta todavía no fue realizada."));
  form.append(fields, button);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    button.disabled = true;
    localStatus.textContent = "Cargando planes de alimentación…";
    localStatus.dataset.error = "false";
    try {
      const response = await fetch(
        `/api/v1/trainer/clients/${select.value}/nutrition-plans`,
        { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } }
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw payload;
      if (!payload.nutrition_plans.length) {
        results.replaceChildren(element("p", "cl-empty-state", "El cliente no tiene planes asignados."));
      } else {
        results.replaceChildren(...payload.nutrition_plans.map((plan) => {
          const item = element("article", "fp-card cl-history-row");
          const copy = element("div");
          copy.append(
            element("strong", "", plan.nombre),
            element("small", "", `Objetivo: ${plan.objetivo.tipo} · ${plan.objetivo.nombre}`),
            element("small", "", `Descripción: ${plan.descripcion || "Sin descripción adicional."}`),
            element("small", "", `Indicaciones: ${plan.indicaciones || "Sin indicaciones adicionales."}`),
            element("small", "", `Creado: ${plan.fecha_creacion_utc} · Actualizado: ${plan.fecha_actualizacion_utc}`)
          );
          item.append(copy);
          return item;
        }));
      }
      localStatus.textContent = `${payload.nutrition_plans.length} planes autorizados encontrados.`;
    } catch (error) {
      results.replaceChildren(element("p", "cl-empty-state", "No hay información disponible para mostrar."));
      localStatus.textContent = error.error === "student_not_authorized"
        ? "El cliente ya no está vinculado a tu perfil."
        : "No pudimos consultar los planes de alimentación.";
      localStatus.dataset.error = "true";
    } finally {
      button.disabled = false;
    }
  });
  card.append(form, localStatus, results);
  return card;
}

function trainerRoutineModuleCard(payload) {
  const rows = payload.options?.routines || [];
  const active = rows.filter((item) => item.activa).length;
  const card = element("section", "fp-card fp-role-action-card tr-dashboard-module-card");
  card.append(
    element("span", "fp-section-kicker", "MÓDULO INDEPENDIENTE"),
    element("h3", "", "Mis rutinas"),
    element("p", "", `${active} activas de ${rows.length} rutinas guardadas. Creá planes y administrá sus ejercicios en una vista enfocada.`)
  );
  const open = element("a", "fp-button fp-button-light", "Abrir gestión de rutinas");
  open.href = "/auth/entrenador/rutinas";
  card.append(open);
  return card;
}

function trainerAttendanceModuleCard(payload) {
  const rows = payload.options?.classes || [];
  const now = Date.now();
  const enabled = rows.filter((item) => (
    item.estado !== "cancelada" && new Date(item.inicio_utc).getTime() <= now
  )).length;
  const card = element("section", "fp-card fp-role-action-card tr-dashboard-module-card");
  card.append(
    element("span", "fp-section-kicker", "MÓDULO INDEPENDIENTE"),
    element("h3", "", "Asistencias"),
    element("p", "", `${enabled} de ${rows.length} clases asignadas tienen la asistencia habilitada.`)
  );
  const open = element("a", "fp-button fp-button-light", "Abrir asistencias");
  open.href = "/auth/entrenador/asistencias";
  card.append(open);
  return card;
}

function trainerForms(payload, csrfToken, status, refresh) {
  const studentRows = payload.options?.students || [];
  const sites = (payload.options?.sites || []).map((item) => ({ value: item.id, label: item.nombre }));
  return [
    trainerRoutineModuleCard(payload),
    trainerAttendanceModuleCard(payload),
    trainerNutritionViewer(studentRows),
    actionForm({ title: "Agregar disponibilidad", path: "/api/v1/trainer/availability", fields: [
      { name: "sede_id", label: "Sede", options: sites, valueType: "integer", required: true },
      { name: "dia_semana", label: "Día (1 lunes - 7 domingo)", type: "number", min: 1, max: 7, valueType: "integer", required: true },
      { name: "hora_inicio", label: "Hora inicio", type: "time", required: true },
      { name: "hora_fin", label: "Hora fin", type: "time", required: true }
    ], success: "Disponibilidad agregada." }, csrfToken, status, refresh)
  ];
}

function bindDependentOptions(card, sourceName, targetName, optionsForValue, emptyLabel) {
  const form = card.querySelector("form");
  const source = form.elements.namedItem(sourceName);
  const target = form.elements.namedItem(targetName);
  const update = () => {
    target.replaceChildren(new Option(emptyLabel, ""));
    for (const option of optionsForValue(source.value)) {
      target.append(new Option(option.label, String(option.value)));
    }
  };
  source.addEventListener("change", update);
  update();
}

function routineExerciseEditForm(assignments, csrfToken, status, refresh) {
  const byId = new Map(assignments.map((assignment) => [assignment.id, assignment]));
  const card = actionForm({
    title: "Editar ejercicio asignado",
    method: "PATCH",
    path: (raw) => `/api/v1/trainer/routines/${byId.get(raw.assignment_id).rutina_id}/exercises/${raw.assignment_id}`,
    transform: ({ assignment_id, ...values }) => values,
    fields: [
      { name: "assignment_id", label: "Ejercicio de rutina", options: assignments.map((item) => ({ value: item.id, label: `${item.rutina} · ${item.ejercicio}` })), valueType: "integer", required: true },
      { name: "orden", label: "Orden", type: "number", min: 1, max: 100, valueType: "integer", required: true },
      { name: "series", label: "Series", type: "number", min: 1, max: 100, valueType: "integer", required: true },
      { name: "repeticiones", label: "Repeticiones", type: "number", min: 1, max: 1000, valueType: "integer", required: true },
      { name: "peso_gramos", label: "Carga (gramos)", type: "number", min: 0, valueType: "integer", includeEmpty: true },
      { name: "descanso_segundos", label: "Descanso (segundos)", type: "number", min: 0, max: 3600, valueType: "integer", required: true }
    ],
    button: "Guardar parámetros",
    success: "Ejercicio y orden actualizados."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const selector = form.elements.namedItem("assignment_id");
  const fill = (assignment) => {
    if (!assignment) return;
    for (const field of ["orden", "series", "repeticiones", "descanso_segundos"]) {
      form.elements.namedItem(field).value = String(assignment[field]);
    }
    form.elements.namedItem("peso_gramos").value = assignment.peso_gramos ?? "";
  };
  selector.addEventListener("change", () => fill(byId.get(Number(selector.value))));
  fill(assignments[0]);
  return card;
}

function localDateTimeValue(utcValue) {
  const date = new Date(utcValue);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function managerClassEditForm(classes, csrfToken, status, refresh, registerEditor) {
  const byId = new Map(classes.map((item) => [item.id, item]));
  const card = actionForm({
    title: "Editar horario, cupo o estado",
    method: "PATCH",
    path: (raw) => `/api/v1/manager/classes/${raw.class_id}`,
    transform: ({ class_id, ...values }) => {
      const current = byId.get(class_id);
      return Object.fromEntries(Object.entries(values).filter(([key, value]) => value !== current?.[key]));
    },
    fields: [
      { name: "class_id", label: "Clase", options: classes.map((item) => ({ value: item.id, label: `${item.actividad} · ${item.inicio_utc} · ${item.entrenador}` })), valueType: "integer", required: true },
      { name: "inicio_utc", label: "Inicio", type: "datetime-local", valueType: "datetime", required: true },
      { name: "fin_utc", label: "Fin", type: "datetime-local", valueType: "datetime", required: true },
      { name: "cupo_maximo", label: "Cupo", type: "number", min: 1, max: 10000, valueType: "integer", required: true },
      { name: "estado", label: "Estado", options: [{ value: "programada", label: "Programada" }, { value: "cancelada", label: "Cancelada" }, { value: "realizada", label: "Realizada" }], required: true }
    ],
    success: "Clase actualizada."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const selector = form.elements.namedItem("class_id");
  const fill = (item) => {
    if (!item) return;
    selector.value = String(item.id);
    form.elements.namedItem("inicio_utc").value = localDateTimeValue(item.inicio_utc);
    form.elements.namedItem("fin_utc").value = localDateTimeValue(item.fin_utc);
    form.elements.namedItem("cupo_maximo").value = String(item.cupo_maximo);
    form.elements.namedItem("estado").value = item.estado;
  };
  selector.addEventListener("change", () => fill(byId.get(Number(selector.value))));
  registerEditor((item) => {
    fill(byId.get(item.id));
    status(`Editando clase ${item.actividad} del ${item.inicio_utc}.`);
    card.scrollIntoView({ block: "center" });
    form.elements.namedItem("inicio_utc").focus({ preventScroll: true });
  });
  fill(classes[0]);
  return card;
}

function managerPersonnelForm(personnel, csrfToken, status, refresh) {
  const byId = new Map(personnel.map((item) => [item.id, item]));
  const card = actionForm({
    title: "Gestionar vínculo de Entrenador",
    method: "PATCH",
    path: (raw) => `/api/v1/manager/personnel/${raw.user_id}`,
    transform: ({ user_id, ...values }) => values,
    note: "No se puede desactivar un entrenador con clases futuras programadas en la sede.",
    fields: [
      { name: "user_id", label: "Entrenador", options: personnel.map((item) => ({ value: item.id, label: `${item.apellido}, ${item.nombre}` })), valueType: "integer", required: true },
      { name: "activo_en_sede", label: "Vínculo", options: [{ value: "true", label: "Activo" }, { value: "false", label: "Inactivo" }], valueType: "boolean", required: true }
    ],
    success: "Vínculo del personal actualizado."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const selector = form.elements.namedItem("user_id");
  const fill = (item) => {
    if (!item) return;
    form.elements.namedItem("activo_en_sede").value = String(item.vinculo_activo);
  };
  selector.addEventListener("change", () => fill(byId.get(Number(selector.value))));
  fill(personnel[0]);
  return card;
}

function managerForms(payload, csrfToken, status, refresh, context = {}) {
  const activities = (payload.options?.activities || []).filter((item) => item.habilitada).map((item) => ({ value: item.id, label: item.nombre }));
  const trainers = (payload.options?.trainers || []).map((item) => ({ value: item.id, label: item.nombre }));
  const classes = payload.options?.classes || [];
  const personnel = (payload.options?.personnel || []).filter((item) => item.rol === "Entrenador");
  const forms = [
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
  ];
  if (classes.length) forms.push(managerClassEditForm(
    classes,
    csrfToken,
    status,
    refresh,
    context.registerClassEditor || (() => {})
  ));
  if (personnel.length) forms.push(managerPersonnelForm(personnel, csrfToken, status, refresh));
  return forms;
}

function managerActivityToggle(csrfToken, status, refresh) {
  return async (activity) => {
    const enabled = !activity.habilitada;
    status(`${enabled ? "Habilitando" : "Deshabilitando"} ${activity.nombre}…`);
    try {
      const response = await fetch(`/api/v1/manager/activities/${activity.id}`, {
        method: "PATCH",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken
        },
        body: JSON.stringify({ habilitada: enabled })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw result;
      await refresh();
      status(`Actividad ${enabled ? "habilitada" : "deshabilitada"} correctamente.`);
    } catch (error) {
      status(mutationErrorMessage(error), true);
    }
  };
}

function trainerAvailabilityDelete(csrfToken, status, refresh) {
  return async (availability) => {
    const confirmed = window.confirm(
      `¿Eliminar la disponibilidad del día ${availability.dia_semana}, de ${availability.hora_inicio} a ${availability.hora_fin}, en ${availability.sede}?`
    );
    if (!confirmed) return;
    status("Eliminando disponibilidad…");
    try {
      const response = await fetch(`/api/v1/trainer/availability/${availability.id}`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-CSRF-Token": csrfToken }
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw result;
      await refresh();
      status("Disponibilidad eliminada correctamente.");
    } catch (error) {
      status(mutationErrorMessage(error), true);
    }
  };
}

function trainerRoutineDeactivate(csrfToken, status, refresh) {
  return async (routine) => {
    if (!window.confirm(`¿Desactivar la rutina ${routine.nombre}? El Cliente seguirá viendo su historial.`)) return;
    status("Desactivando rutina…");
    try {
      const response = await fetch(`/api/v1/trainer/routines/${routine.id}`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-CSRF-Token": csrfToken }
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw result;
      await refresh();
      status("Rutina desactivada; el historial permanece disponible.");
    } catch (error) {
      status(mutationErrorMessage(error), true);
    }
  };
}

function trainerRoutineExerciseDelete(csrfToken, status, refresh) {
  return async (assignment) => {
    if (!window.confirm(`¿Quitar ${assignment.ejercicio} de ${assignment.rutina}?`)) return;
    status("Quitando ejercicio…");
    try {
      const response = await fetch(`/api/v1/trainer/routines/${assignment.rutina_id}/exercises/${assignment.id}`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-CSRF-Token": csrfToken }
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw result;
      await refresh();
      status("Ejercicio retirado de la rutina.");
    } catch (error) {
      status(mutationErrorMessage(error), true);
    }
  };
}

function siteEditForm(sites, csrfToken, status, refresh, registerEditor) {
  const byId = new Map(sites.map((site) => [site.id, site]));
  const card = actionForm({
    title: "Editar sede",
    method: "PATCH",
    path: (raw) => `/api/v1/admin/sites/${raw.site_id}`,
    transform: ({ site_id, ...values }) => Object.fromEntries(
      Object.entries(values).map(([key, value]) => [key, value.trim()])
    ),
    fields: [
      { name: "site_id", label: "Sede", options: sites.map((site) => ({ value: site.id, label: site.nombre })), valueType: "integer", required: true },
      { name: "nombre", label: "Nombre", maxLength: 160, required: true },
      { name: "direccion", label: "Dirección", maxLength: 160, required: true },
      { name: "zona_horaria", label: "Zona horaria IANA", maxLength: 160, required: true }
    ],
    button: "Guardar cambios",
    pending: "Actualizando sede…",
    success: "Sede actualizada correctamente."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const siteSelect = form.elements.namedItem("site_id");
  const fill = (site) => {
    if (!site) return;
    siteSelect.value = String(site.id);
    form.elements.namedItem("nombre").value = site.nombre;
    form.elements.namedItem("direccion").value = site.direccion;
    form.elements.namedItem("zona_horaria").value = site.zona_horaria;
  };
  siteSelect.addEventListener("change", () => fill(byId.get(Number(siteSelect.value))));
  registerEditor((site) => {
    fill(byId.get(site.id));
    status(`Editando ${site.nombre}.`);
    card.scrollIntoView({ block: "center" });
    form.elements.namedItem("nombre").focus({ preventScroll: true });
  });
  fill(sites[0]);
  return card;
}

function membershipEditForm(memberships, csrfToken, status, refresh, registerEditor) {
  const byId = new Map(memberships.map((membership) => [membership.id, membership]));
  const card = actionForm({
    title: "Editar membresía",
    method: "PATCH",
    path: (raw) => `/api/v1/admin/memberships/${raw.membership_id}`,
    transform: ({ membership_id, ...values }) => ({
      ...values,
      nombre: values.nombre.trim(),
      moneda: values.moneda.trim().toUpperCase(),
      descripcion: values.descripcion === null ? null : values.descripcion.trim()
    }),
    fields: [
      { name: "membership_id", label: "Membresía", options: memberships.map((item) => ({ value: item.id, label: item.nombre })), valueType: "integer", required: true },
      { name: "nombre", label: "Nombre", maxLength: 120, required: true },
      { name: "precio_unidades_menores", label: "Precio en unidades menores", type: "number", min: 0, max: 1000000000, valueType: "integer", required: true },
      { name: "moneda", label: "Moneda", maxLength: 3, required: true },
      { name: "descripcion", label: "Descripción", maxLength: 1000, multiline: true, includeEmpty: true },
      { name: "activa", label: "Estado", options: [{ value: "true", label: "Activa" }, { value: "false", label: "Inactiva" }], valueType: "boolean", required: true }
    ],
    button: "Guardar membresía",
    pending: "Actualizando membresía…",
    success: "Membresía actualizada correctamente."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const selector = form.elements.namedItem("membership_id");
  const fill = (membership) => {
    if (!membership) return;
    selector.value = String(membership.id);
    form.elements.namedItem("nombre").value = membership.nombre;
    form.elements.namedItem("precio_unidades_menores").value = String(membership.precio_unidades_menores);
    form.elements.namedItem("moneda").value = membership.moneda;
    form.elements.namedItem("descripcion").value = membership.descripcion || "";
    form.elements.namedItem("activa").value = String(Boolean(membership.activa));
  };
  selector.addEventListener("change", () => fill(byId.get(Number(selector.value))));
  registerEditor((membership) => {
    fill(byId.get(membership.id));
    status(`Editando membresía ${membership.nombre}.`);
    card.scrollIntoView({ block: "center" });
    form.elements.namedItem("nombre").focus({ preventScroll: true });
  });
  fill(memberships[0]);
  return card;
}

function benefitEditForm(benefits, csrfToken, status, refresh, registerEditor) {
  const byId = new Map(benefits.map((benefit) => [benefit.id, benefit]));
  const card = actionForm({
    title: "Editar beneficio",
    method: "PATCH",
    path: (raw) => `/api/v1/admin/benefits/${raw.benefit_id}`,
    transform: ({ benefit_id, ...values }) => ({
      ...values,
      nombre: values.nombre.trim(),
      descripcion: values.descripcion === null ? null : values.descripcion.trim()
    }),
    fields: [
      { name: "benefit_id", label: "Beneficio", options: benefits.map((item) => ({ value: item.id, label: item.nombre })), valueType: "integer", required: true },
      { name: "nombre", label: "Nombre", maxLength: 120, required: true },
      { name: "descripcion", label: "Descripción", maxLength: 1000, multiline: true, includeEmpty: true }
    ],
    button: "Guardar beneficio",
    pending: "Actualizando beneficio…",
    success: "Beneficio actualizado correctamente."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const selector = form.elements.namedItem("benefit_id");
  const fill = (benefit) => {
    if (!benefit) return;
    selector.value = String(benefit.id);
    form.elements.namedItem("nombre").value = benefit.nombre;
    form.elements.namedItem("descripcion").value = benefit.descripcion || "";
  };
  selector.addEventListener("change", () => fill(byId.get(Number(selector.value))));
  registerEditor((benefit) => {
    fill(byId.get(benefit.id));
    status(`Editando beneficio ${benefit.nombre}.`);
    card.scrollIntoView({ block: "center" });
    form.elements.namedItem("nombre").focus({ preventScroll: true });
  });
  fill(benefits[0]);
  return card;
}

function membershipBenefitsForm(memberships, benefits, csrfToken, status, refresh) {
  const byId = new Map(memberships.map((membership) => [membership.id, membership]));
  const card = actionForm({
    title: "Configurar beneficios",
    note: "Seleccioná los beneficios que pertenecen al plan. Esta relación no define elegibilidad para clases.",
    method: "PUT",
    path: (raw) => `/api/v1/admin/memberships/${raw.membership_id}/benefits`,
    transform: ({ membership_id, benefit_ids = [] }) => ({ benefit_ids }),
    fields: [
      { name: "membership_id", label: "Membresía", options: memberships.map((item) => ({ value: item.id, label: item.nombre })), valueType: "integer", required: true },
      { name: "benefit_ids", label: "Beneficios", options: benefits.map((item) => ({ value: item.id, label: item.nombre })), valueType: "integer", multiple: true, size: Math.min(Math.max(benefits.length, 2), 6) }
    ],
    button: "Guardar beneficios",
    pending: "Actualizando beneficios…",
    success: "Beneficios de la membresía actualizados."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const membershipSelect = form.elements.namedItem("membership_id");
  const benefitSelect = form.elements.namedItem("benefit_ids");
  const fill = (membership) => {
    const selected = new Set(membership?.beneficio_ids || []);
    for (const option of benefitSelect.options) {
      option.selected = selected.has(Number(option.value));
    }
  };
  membershipSelect.addEventListener("change", () => fill(byId.get(Number(membershipSelect.value))));
  fill(memberships[0]);
  return card;
}

function activityEditForm(activities, csrfToken, status, refresh, registerEditor) {
  const byId = new Map(activities.map((item) => [item.id, item]));
  const card = actionForm({
    title: "Editar actividad",
    method: "PATCH",
    path: (raw) => `/api/v1/admin/activities/${raw.activity_id}`,
    transform: ({ activity_id, ...values }) => ({ nombre: values.nombre.trim() }),
    fields: [
      { name: "activity_id", label: "Actividad", options: activities.map((item) => ({ value: item.id, label: item.nombre })), valueType: "integer", required: true },
      { name: "nombre", label: "Nombre", maxLength: 120, required: true }
    ],
    success: "Actividad actualizada."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const selector = form.elements.namedItem("activity_id");
  const fill = (item) => {
    if (!item) return;
    selector.value = String(item.id);
    form.elements.namedItem("nombre").value = item.nombre;
  };
  selector.addEventListener("change", () => fill(byId.get(Number(selector.value))));
  registerEditor((item) => {
    fill(byId.get(item.id));
    status(`Editando actividad ${item.nombre}.`);
    card.scrollIntoView({ block: "center" });
    form.elements.namedItem("nombre").focus({ preventScroll: true });
  });
  fill(activities[0]);
  return card;
}

function userAccessForm(users, roles, sites, csrfToken, status, refresh, registerEditor) {
  const byId = new Map(users.map((item) => [item.id, item]));
  const rolesById = new Map(roles.map((item) => [item.id, item]));
  const card = actionForm({
    title: "Actualizar acceso de usuario",
    method: "PATCH",
    path: (raw) => `/api/v1/admin/users/${raw.user_id}`,
    transform: ({ user_id, rol_id, activo, especialidad, sede_id }) => {
      const current = byId.get(user_id);
      const role = rolesById.get(rol_id);
      const values = {};
      const specialtyValue = especialidad || "";
      const siteValue = sede_id ?? null;
      const profileChanged = rol_id !== current?.rol_id
        || specialtyValue !== (current?.especialidad || "")
        || siteValue !== (current?.sede_id ?? null);
      if (profileChanged) {
        values.rol_id = rol_id;
        if (role?.nombre === "Entrenador") {
          values.especialidad = specialtyValue;
          values.sede_id = sede_id;
        } else if (["Jefe de sede", "Técnico de mantenimiento"].includes(role?.nombre)) {
          values.sede_id = sede_id;
        }
      }
      if (activo !== current?.activo) values.activo = activo;
      return values;
    },
    fields: [
      { name: "user_id", label: "Usuario", options: users.map((item) => ({ value: item.id, label: `${item.apellido}, ${item.nombre} · ${item.rol}` })), valueType: "integer", required: true },
      { name: "rol_id", label: "Rol", options: roles.map((item) => ({ value: item.id, label: item.nombre })), valueType: "integer", required: true },
      { name: "especialidad", label: "Especialidad (Entrenador)", maxLength: 120 },
      { name: "sede_id", label: "Sede del rol", options: sites, valueType: "integer" },
      { name: "activo", label: "Estado", options: [{ value: "true", label: "Activo" }, { value: "false", label: "Inactivo" }], valueType: "boolean", required: true }
    ],
    success: "Acceso actualizado."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const userSelect = form.elements.namedItem("user_id");
  const roleSelect = form.elements.namedItem("rol_id");
  const specialty = form.elements.namedItem("especialidad");
  const site = form.elements.namedItem("sede_id");
  const syncRequirements = () => {
    const roleName = rolesById.get(Number(roleSelect.value))?.nombre;
    specialty.required = roleName === "Entrenador";
    site.required = ["Entrenador", "Jefe de sede", "Técnico de mantenimiento"].includes(roleName);
  };
  const fill = (item) => {
    if (!item) return;
    userSelect.value = String(item.id);
    roleSelect.value = String(item.rol_id);
    specialty.value = item.especialidad || "";
    site.value = item.sede_id === null ? "" : String(item.sede_id);
    form.elements.namedItem("activo").value = String(Boolean(item.activo));
    syncRequirements();
  };
  userSelect.addEventListener("change", () => fill(byId.get(Number(userSelect.value))));
  roleSelect.addEventListener("change", syncRequirements);
  registerEditor((item) => {
    fill(byId.get(item.id));
    status(`Editando acceso de ${item.nombre} ${item.apellido}.`);
    card.scrollIntoView({ block: "center" });
    roleSelect.focus({ preventScroll: true });
  });
  fill(users[0]);
  return card;
}

function rolePermissionsForm(roles, permissions, csrfToken, status, refresh) {
  const byId = new Map(roles.map((item) => [item.id, item]));
  const card = actionForm({
    title: "Configurar permisos del rol",
    note: "Los permisos base de cada rol son obligatorios y no pueden asignarse a otro rol.",
    method: "PUT",
    path: (raw) => `/api/v1/admin/roles/${raw.role_id}/permissions`,
    transform: ({ role_id, permission_ids = [] }) => ({ permission_ids }),
    fields: [
      { name: "role_id", label: "Rol", options: roles.map((item) => ({ value: item.id, label: item.nombre })), valueType: "integer", required: true },
      { name: "permission_ids", label: "Permisos", options: permissions.map((item) => ({ value: item.id, label: `${item.clave} · ${item.descripcion || "Sin descripción"}` })), valueType: "integer", multiple: true, size: Math.min(Math.max(permissions.length, 4), 10) }
    ],
    success: "Permisos del rol actualizados."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const roleSelect = form.elements.namedItem("role_id");
  const permissionSelect = form.elements.namedItem("permission_ids");
  const fill = (role) => {
    const selected = new Set(role?.permission_ids || []);
    for (const option of permissionSelect.options) option.selected = selected.has(Number(option.value));
  };
  roleSelect.addEventListener("change", () => fill(byId.get(Number(roleSelect.value))));
  fill(roles[0]);
  return card;
}

function adminForms(payload, csrfToken, status, refresh, context = {}) {
  const roleRows = payload.options?.roles || [];
  const roles = roleRows.map((item) => ({ value: item.id, label: item.nombre }));
  const userRows = payload.options?.users || [];
  const siteRows = payload.options?.sites || [];
  const sites = siteRows.map((item) => ({ value: item.id, label: item.nombre }));
  const activityRows = payload.options?.activities || [];
  const membershipRows = payload.options?.memberships || [];
  const benefitRows = payload.options?.benefits || [];
  const permissionRows = payload.options?.permissions || [];
  const forms = [
    actionForm({ title: "Crear usuario local", path: "/api/v1/admin/users", note: "Entrenador requiere especialidad y sede; Jefe o Técnico requieren sede. Google se vincula por separado.", fields: [
      { name: "nombre", label: "Nombre", required: true }, { name: "apellido", label: "Apellido", required: true },
      { name: "nombre_usuario", label: "Usuario", required: true }, { name: "email", label: "Email", type: "email", required: true },
      { name: "rol_id", label: "Rol", options: roles, valueType: "integer", required: true },
      { name: "especialidad", label: "Especialidad (Entrenador)" },
      { name: "sede_id", label: "Sede del rol", options: sites, valueType: "integer" }
    ], success: "Usuario creado sin credenciales locales." }, csrfToken, status, refresh),
    actionForm({ title: "Crear sede", path: "/api/v1/admin/sites", fields: [
      { name: "nombre", label: "Nombre", maxLength: 160, required: true }, { name: "direccion", label: "Dirección", maxLength: 160, required: true },
      { name: "zona_horaria", label: "Zona horaria IANA", maxLength: 160, placeholder: "America/Argentina/Buenos_Aires", required: true }
    ], success: "Sede creada." }, csrfToken, status, refresh),
    actionForm({ title: "Crear actividad", path: "/api/v1/admin/activities", fields: [
      { name: "nombre", label: "Nombre", required: true }
    ], success: "Actividad creada." }, csrfToken, status, refresh),
    actionForm({ title: "Crear membresía", path: "/api/v1/admin/memberships", fields: [
      { name: "nombre", label: "Nombre", maxLength: 120, required: true },
      { name: "precio_unidades_menores", label: "Precio en unidades menores", type: "number", min: 0, max: 1000000000, valueType: "integer", required: true },
      { name: "moneda", label: "Moneda", maxLength: 3, placeholder: "ARS", required: true },
      { name: "descripcion", label: "Descripción", maxLength: 1000, multiline: true }
    ], success: "Membresía creada." }, csrfToken, status, refresh),
  ];
  if (userRows.length) forms.splice(1, 0, userAccessForm(
    userRows,
    roleRows,
    sites,
    csrfToken,
    status,
    refresh,
    context.registerUserEditor || (() => {})
  ));
  if (siteRows.length) {
    forms.splice(3, 0, siteEditForm(
      siteRows,
      csrfToken,
      status,
      refresh,
      context.registerSiteEditor || (() => {})
    ));
    forms.push(actionForm({ title: "Registrar máquina", path: "/api/v1/admin/machines", fields: [
      { name: "sede_id", label: "Sede", options: sites, valueType: "integer", required: true },
      { name: "tipo", label: "Tipo de máquina", maxLength: 120, required: true },
      { name: "estado", label: "Estado inicial", options: [
        { value: "operativa", label: "Operativa" },
        { value: "en_reparacion", label: "En reparación" },
        { value: "fuera_de_servicio", label: "Fuera de servicio" }
      ], required: true }
    ], success: "Máquina registrada en la sede." }, csrfToken, status, refresh));
  }
  if (activityRows.length) forms.push(activityEditForm(
    activityRows,
    csrfToken,
    status,
    refresh,
    context.registerActivityEditor || (() => {})
  ));
  if (membershipRows.length) {
    forms.push(membershipEditForm(
      membershipRows,
      csrfToken,
      status,
      refresh,
      context.registerMembershipEditor || (() => {})
    ));
  }
  forms.push(actionForm({ title: "Crear beneficio", path: "/api/v1/admin/benefits", fields: [
    { name: "nombre", label: "Nombre", maxLength: 120, required: true },
    { name: "descripcion", label: "Descripción", maxLength: 1000, multiline: true }
  ], success: "Beneficio creado correctamente." }, csrfToken, status, refresh));
  if (benefitRows.length) {
    forms.push(benefitEditForm(
      benefitRows,
      csrfToken,
      status,
      refresh,
      context.registerBenefitEditor || (() => {})
    ));
  }
  if (membershipRows.length) {
    forms.push(membershipBenefitsForm(
      membershipRows,
      benefitRows,
      csrfToken,
      status,
      refresh
    ));
  }
  if (roleRows.length) forms.push(rolePermissionsForm(
    roleRows,
    permissionRows,
    csrfToken,
    status,
    refresh
  ));
  return forms;
}

function technicianTicketForm(tickets, csrfToken, status, refresh, registerEditor) {
  const byId = new Map(tickets.map((item) => [item.id, item]));
  const card = actionForm({
    title: "Actualizar ticket",
    method: "PATCH",
    path: (raw) => `/api/v1/technician/tickets/${raw.ticket_id}`,
    transform: ({ ticket_id, ...values }) => values,
    fields: [
      { name: "ticket_id", label: "Ticket", options: tickets.map((item) => ({ value: item.id, label: `#${item.id} · ${item.maquina} · ${item.descripcion}` })), valueType: "integer", required: true },
      { name: "estado", label: "Estado", options: [{ value: "abierto", label: "Abierto" }, { value: "en_proceso", label: "En proceso" }, { value: "resuelto", label: "Resuelto" }, { value: "cancelado", label: "Cancelado" }], required: true }
    ],
    success: "Ticket actualizado."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const selector = form.elements.namedItem("ticket_id");
  const fill = (item) => {
    if (!item) return;
    selector.value = String(item.id);
    form.elements.namedItem("estado").value = item.estado;
  };
  selector.addEventListener("change", () => fill(byId.get(Number(selector.value))));
  registerEditor((item) => {
    fill(byId.get(item.id));
    status(`Editando ticket #${item.id}.`);
    card.scrollIntoView({ block: "center" });
    form.elements.namedItem("estado").focus({ preventScroll: true });
  });
  fill(tickets[0]);
  return card;
}

function technicianMachineForm(machines, tickets, csrfToken, status, refresh, registerEditor) {
  const byId = new Map(machines.map((item) => [item.id, item]));
  const machineStates = [{ value: "operativa", label: "Operativa" }, { value: "en_reparacion", label: "En reparación" }, { value: "fuera_de_servicio", label: "Fuera de servicio" }];
  const card = actionForm({
    title: "Cambiar estado de máquina",
    method: "PATCH",
    path: (raw) => `/api/v1/technician/machines/${raw.machine_id}`,
    transform: ({ machine_id, ...values }) => values,
    fields: [
      { name: "machine_id", label: "Máquina", options: machines.map((item) => ({ value: item.id, label: `${item.tipo} · ${item.estado}` })), valueType: "integer", required: true },
      { name: "estado", label: "Nuevo estado", options: machineStates, required: true },
      { name: "ticket_id", label: "Ticket relacionado", options: [], valueType: "integer" },
      { name: "descripcion", label: "Detalle del cambio", multiline: true }
    ],
    success: "Estado e historial actualizados."
  }, csrfToken, status, refresh);
  const form = card.querySelector("form");
  const machineSelect = form.elements.namedItem("machine_id");
  const ticketSelect = form.elements.namedItem("ticket_id");
  const fill = (item) => {
    if (!item) return;
    machineSelect.value = String(item.id);
    form.elements.namedItem("estado").value = item.estado;
    ticketSelect.replaceChildren(new Option("Sin ticket relacionado", ""));
    for (const ticket of tickets.filter((candidate) => candidate.maquina_id === item.id)) {
      ticketSelect.append(new Option(`#${ticket.id} · ${ticket.estado} · ${ticket.descripcion}`, String(ticket.id)));
    }
  };
  machineSelect.addEventListener("change", () => fill(byId.get(Number(machineSelect.value))));
  registerEditor((item) => {
    fill(byId.get(item.id));
    status(`Editando estado de ${item.tipo}.`);
    card.scrollIntoView({ block: "center" });
    form.elements.namedItem("estado").focus({ preventScroll: true });
  });
  fill(machines[0]);
  return card;
}

function technicianForms(payload, csrfToken, status, refresh, context = {}) {
  const machineRows = payload.options?.machines || [];
  const ticketRows = payload.options?.tickets || [];
  const machines = machineRows.map((item) => ({ value: item.id, label: `${item.tipo} · ${item.estado}` }));
  const forms = [];
  if (machineRows.length) forms.push(
    actionForm({ title: "Registrar incidencia", path: "/api/v1/technician/tickets", fields: [
      { name: "maquina_id", label: "Máquina", options: machines, valueType: "integer", required: true },
      { name: "descripcion", label: "Descripción", multiline: true, required: true }
    ], success: "Incidencia registrada." }, csrfToken, status, refresh)
  );
  if (ticketRows.length) forms.push(technicianTicketForm(
    ticketRows,
    csrfToken,
    status,
    refresh,
    context.registerTicketEditor || (() => {})
  ));
  if (machineRows.length) forms.push(technicianMachineForm(
    machineRows,
    ticketRows,
    csrfToken,
    status,
    refresh,
    context.registerMachineEditor || (() => {})
  ));
  return forms;
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
  const actions = element("section", "fp-role-actions");
  actions.append(element("h2", "", "Acciones autorizadas"));
  const factory = { trainer: trainerForms, manager: managerForms, admin: adminForms, technician: technicianForms }[role];
  let editSite = null;
  let editMembership = null;
  let editBenefit = null;
  let editClass = null;
  let editUser = null;
  let editActivity = null;
  let editTicket = null;
  let editMachine = null;
  const context = {
    registerSiteEditor: (editor) => { editSite = editor; },
    registerMembershipEditor: (editor) => { editMembership = editor; },
    registerBenefitEditor: (editor) => { editBenefit = editor; },
    registerClassEditor: (editor) => { editClass = editor; },
    registerUserEditor: (editor) => { editUser = editor; },
    registerActivityEditor: (editor) => { editActivity = editor; },
    registerTicketEditor: (editor) => { editTicket = editor; },
    registerMachineEditor: (editor) => { editMachine = editor; }
  };
  factory?.(payload, csrfToken, showStatus, loadDashboard, context).forEach((form) => actions.append(form));
  const toggleActivity = role === "manager"
    ? managerActivityToggle(csrfToken, showStatus, loadDashboard)
    : null;
  const deleteAvailability = role === "trainer"
    ? trainerAvailabilityDelete(csrfToken, showStatus, loadDashboard)
    : null;
  const deactivateRoutine = role === "trainer"
    ? trainerRoutineDeactivate(csrfToken, showStatus, loadDashboard)
    : null;
  const deleteRoutineExercise = role === "trainer"
    ? trainerRoutineExerciseDelete(csrfToken, showStatus, loadDashboard)
    : null;
  const rowActions = {};
  if (role === "admin") {
    if (editUser) rowActions.Usuarios = {
      label: "Editar acceso",
      ariaLabel: (user) => `Editar acceso de ${user.nombre} ${user.apellido}`,
      run: editUser
    };
    if (editSite) rowActions.Sedes = {
      label: "Editar",
      ariaLabel: (site) => `Editar sede ${site.nombre}`,
      run: editSite
    };
    if (editMembership) rowActions["Membresías"] = {
      label: "Editar",
      ariaLabel: (membership) => `Editar membresía ${membership.nombre}`,
      run: editMembership
    };
    if (editBenefit) rowActions.Beneficios = {
      label: "Editar",
      ariaLabel: (benefit) => `Editar beneficio ${benefit.nombre}`,
      run: editBenefit
    };
    if (editActivity) rowActions.Actividades = {
      label: "Editar",
      ariaLabel: (activity) => `Editar actividad ${activity.nombre}`,
      run: editActivity
    };
  }
  if (role === "manager" && toggleActivity) rowActions.Actividades = {
    label: (activity) => activity.habilitada ? "Deshabilitar" : "Habilitar",
    ariaLabel: (activity) => `${activity.habilitada ? "Deshabilitar" : "Habilitar"} actividad ${activity.nombre}`,
    run: toggleActivity
  };
  if (role === "manager" && editClass) rowActions["Horarios y cupos"] = {
    label: "Editar",
    ariaLabel: (item) => `Editar clase ${item.actividad} del ${item.inicio_utc}`,
    run: editClass
  };
  if (role === "technician" && editMachine) rowActions["Máquinas de la sede"] = {
    label: "Cambiar estado",
    ariaLabel: (machine) => `Cambiar estado de ${machine.tipo}`,
    run: editMachine
  };
  if (role === "technician" && editTicket) rowActions["Incidencias asignadas"] = {
    label: "Actualizar",
    ariaLabel: (ticket) => `Actualizar ticket ${ticket.id} de ${ticket.maquina}`,
    run: editTicket
  };
  if (role === "trainer" && deleteAvailability) rowActions.Disponibilidad = {
    label: "Eliminar",
    ariaLabel: (availability) => `Eliminar disponibilidad del día ${availability.dia_semana}, de ${availability.hora_inicio} a ${availability.hora_fin}`,
    run: deleteAvailability
  };
  if (role === "trainer" && deactivateRoutine) rowActions.Rutinas = {
    label: "Desactivar",
    ariaLabel: (routine) => `Desactivar rutina ${routine.nombre}`,
    disabled: (routine) => !routine.activa,
    run: deactivateRoutine
  };
  if (role === "trainer" && deleteRoutineExercise) rowActions["Ejercicios de rutinas"] = {
    label: "Quitar",
    ariaLabel: (assignment) => `Quitar ${assignment.ejercicio} de ${assignment.rutina}`,
    disabled: (assignment) => !assignment.rutina_activa,
    run: deleteRoutineExercise
  };
  const trainerIndependentSections = new Set(["Rutinas", "Ejercicios de rutinas", "Ejercicios", "Asistencias"]);
  const visibleSections = role === "trainer"
    ? (payload.sections || []).filter((section) => !trainerIndependentSections.has(section.title))
    : (payload.sections || []);
  const sections = visibleSections.map(
    (section) => renderSection(section, rowActions[section.title] || null)
  );
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
if (!["trainer", "manager", "admin", "technician"].includes(role)) initializeSmartAssistant().catch(() => {});
