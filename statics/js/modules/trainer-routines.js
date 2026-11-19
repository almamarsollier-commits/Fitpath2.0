import { initializeDrawer } from "./navigation-drawer.js";

initializeDrawer({
  panel: document.querySelector("#fp-sidebar"),
  toggle: document.querySelector("[data-menu-toggle]"),
  close: document.querySelector("[data-menu-close]"),
  overlay: document.querySelector("[data-menu-overlay]")
});

const content = document.querySelector("[data-routine-content]");
const heading = document.querySelector("[data-routine-heading]");
const breadcrumb = document.querySelector("[data-routine-breadcrumb]");
const backLink = document.querySelector("[data-module-back]");
const statusNode = document.querySelector("[data-routine-status]");
const pageUrl = new URL(window.location.href);

const state = {
  csrfToken: null,
  payload: null,
  editingAssignmentId: null,
  addingAssignment: false,
  search: pageUrl.searchParams.get("buscar") || "",
  activity: pageUrl.searchParams.get("estado") || "activas"
};
if (!["activas", "todas", "inactivas"].includes(state.activity)) state.activity = "activas";

const errorMessages = {
  csrf_failed: "La sesión cambió. Recargá la página antes de guardar.",
  permission_denied: "No tenés permiso para gestionar estas rutinas.",
  student_not_authorized: "El alumno ya no está vinculado con tu perfil.",
  objective_not_assigned_to_client: "El objetivo seleccionado no pertenece al alumno.",
  routine_not_found: "La rutina no existe, está inactiva o ya no te pertenece.",
  exercise_not_found: "El ejercicio seleccionado ya no está disponible.",
  routine_exercise_not_found: "La asignación no existe o la rutina ya no admite cambios.",
  exercise_assignment_conflict: "Ese ejercicio u orden entra en conflicto con la rutina actual.",
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

function button(label, className = "fp-button fp-button-outline") {
  const node = element("button", className, label);
  node.type = "button";
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
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
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

function listParameters() {
  const params = new URLSearchParams();
  if (state.search) params.set("buscar", state.search);
  if (state.activity !== "activas") params.set("estado", state.activity);
  return params;
}

function moduleUrl(view = "lista", routineId = null) {
  const params = listParameters();
  if (view !== "lista") params.set("vista", view);
  if (routineId !== null) params.set("rutina", String(routineId));
  const query = params.toString();
  return `/auth/entrenador/rutinas${query ? `?${query}` : ""}`;
}

function syncFilterUrl() {
  const current = new URL(window.location.href);
  current.searchParams.delete("buscar");
  current.searchParams.delete("estado");
  if (state.search) current.searchParams.set("buscar", state.search);
  if (state.activity !== "activas") current.searchParams.set("estado", state.activity);
  window.history.replaceState({}, "", current);
}

function setPageHeading(title, description, crumb = title) {
  const kicker = element("span", "fp-section-kicker", "ENTRENAMIENTO · RUTINAS");
  const pageTitle = element("h1", "", title);
  const copy = element("p", "", description);
  heading.replaceChildren(kicker, pageTitle, copy);
  breadcrumb.textContent = crumb;
}

function routines() {
  return state.payload?.options?.routines || [];
}

function assignmentsFor(routineId) {
  return (state.payload?.options?.routine_exercises || [])
    .filter((item) => item.rutina_id === routineId)
    .sort((first, second) => first.orden - second.orden || first.id - second.id);
}

function objectivesFor(clientId) {
  return (state.payload?.options?.objectives || []).filter(
    (item) => item.cliente_id === Number(clientId)
  );
}

function formatDate(value) {
  if (!value) return "Sin fecha";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("es-AR", { dateStyle: "medium" }).format(parsed);
}

function formatWeight(grams) {
  if (grams === null || grams === undefined) return "Sin carga";
  return `${new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(grams / 1000)} kg`;
}

function statusBadge(active) {
  const badge = element("span", `fp-status ${active ? "fp-status-live" : "fp-status-complete"}`);
  badge.append(element("span"), document.createTextNode(active ? "Activa" : "Inactiva"));
  return badge;
}

function metaItem(term, value) {
  const wrapper = element("div");
  wrapper.append(element("dt", "", term), element("dd", "", value));
  return wrapper;
}

function filteredRoutines() {
  const query = state.search.trim().toLocaleLowerCase("es");
  return routines().filter((routine) => {
    const matchesActivity = state.activity === "todas"
      || (state.activity === "activas" && routine.activa)
      || (state.activity === "inactivas" && !routine.activa);
    const searchable = `${routine.nombre} ${routine.cliente} ${routine.objetivo || ""}`.toLocaleLowerCase("es");
    return matchesActivity && (!query || searchable.includes(query));
  });
}

function routineCard(routine) {
  const card = element("article", "fp-card tr-routine-card");
  const top = element("div", "tr-routine-card-top");
  const title = element("div");
  title.append(element("span", "fp-section-kicker", `RUTINA ${String(routine.id).padStart(2, "0")}`), element("h2", "", routine.nombre));
  top.append(title, statusBadge(routine.activa));

  const metadata = element("dl", "tr-routine-meta");
  metadata.append(
    metaItem("Alumno", routine.cliente),
    metaItem("Objetivo", routine.objetivo || "Sin objetivo asignado"),
    metaItem("Ejercicios", String(routine.ejercicios)),
    metaItem("Creada", formatDate(routine.fecha_creacion_utc))
  );

  const preview = element("p", "tr-routine-preview");
  const exerciseNames = assignmentsFor(routine.id).slice(0, 3).map((item) => item.ejercicio);
  preview.textContent = exerciseNames.length
    ? `${exerciseNames.join(" · ")}${routine.ejercicios > 3 ? " · …" : ""}`
    : "Todavía no agregaste ejercicios a esta rutina.";

  const actions = element("div", "tr-routine-actions");
  actions.append(link("Ver detalle", moduleUrl("detalle", routine.id), "fp-button fp-button-primary"));
  if (routine.activa) {
    actions.append(link("Editar", moduleUrl("editar", routine.id), "fp-button fp-button-outline"));
    const deactivate = button("Eliminar", "fp-button tr-button-danger");
    deactivate.addEventListener("click", () => deactivateRoutine(routine, deactivate));
    actions.append(deactivate);
  }
  card.append(top, metadata, preview, actions);
  return card;
}

function renderList() {
  setPageHeading(
    "Mis rutinas",
    "Gestioná planes persistidos para tus alumnos vinculados sin mezclar formularios con el resumen operativo."
  );
  backLink.href = "/auth/entrenador";
  backLink.textContent = "← Volver al resumen";

  const layout = element("div", "tr-routine-list-layout");
  const toolbar = element("section", "fp-card tr-routine-toolbar");
  const searchField = element("label", "tr-routine-field");
  searchField.append(element("span", "", "Buscar rutina"));
  const search = document.createElement("input");
  search.type = "search";
  search.value = state.search;
  search.placeholder = "Nombre, alumno u objetivo";
  searchField.append(search);

  const stateField = element("label", "tr-routine-field");
  stateField.append(element("span", "", "Estado"));
  const activity = document.createElement("select");
  activity.append(new Option("Activas", "activas"), new Option("Todas", "todas"), new Option("Inactivas", "inactivas"));
  activity.value = state.activity;
  stateField.append(activity);

  const students = state.payload?.options?.students || [];
  const createLink = link("+ Nueva rutina", moduleUrl("crear"), "fp-button fp-button-light");
  if (!students.length) {
    createLink.setAttribute("aria-disabled", "true");
    createLink.classList.add("is-disabled");
    createLink.title = "Necesitás al menos un alumno vinculado";
    createLink.addEventListener("click", (event) => event.preventDefault());
  }
  toolbar.append(searchField, stateField, createLink);

  const resultHeader = element("div", "tr-routine-result-heading");
  const resultTitle = element("h2", "", "Rutinas guardadas");
  const count = element("span", "fp-count-badge");
  resultHeader.append(resultTitle, count);
  const grid = element("div", "tr-routine-grid");

  const updateResults = () => {
    const results = filteredRoutines();
    count.textContent = `${results.length} ${results.length === 1 ? "resultado" : "resultados"}`;
    if (!results.length) {
      const empty = element("section", "fp-card tr-routine-empty");
      empty.append(
        element("strong", "", routines().length ? "No hay coincidencias" : "Todavía no creaste rutinas"),
        element("p", "", routines().length ? "Probá otro texto o cambiá el filtro de estado." : "Cuando tengas un alumno vinculado, podés crear su primera rutina desde este módulo.")
      );
      grid.replaceChildren(empty);
    } else {
      grid.replaceChildren(...results.map(routineCard));
    }
    setStatus(`${results.length} rutinas visibles de ${routines().length} registradas.`, "success");
  };

  search.addEventListener("input", () => {
    state.search = search.value;
    syncFilterUrl();
    updateResults();
  });
  activity.addEventListener("change", () => {
    state.activity = activity.value;
    syncFilterUrl();
    updateResults();
  });

  layout.append(toolbar, resultHeader, grid);
  content.replaceChildren(layout);
  content.setAttribute("aria-busy", "false");
  updateResults();
}

function labeledControl(labelText, control, hint = "") {
  const label = element("label", "tr-routine-field");
  label.append(element("span", "", labelText), control);
  if (hint) label.append(element("small", "", hint));
  return label;
}

function textInput(name, value = "", options = {}) {
  const input = document.createElement("input");
  input.name = name;
  input.type = options.type || "text";
  input.value = value ?? "";
  input.required = Boolean(options.required);
  if (options.maxLength) input.maxLength = options.maxLength;
  if (options.min !== undefined) input.min = String(options.min);
  if (options.max !== undefined) input.max = String(options.max);
  if (options.step !== undefined) input.step = String(options.step);
  return input;
}

function textarea(name, value = "", maxLength = 1000) {
  const control = document.createElement("textarea");
  control.name = name;
  control.value = value || "";
  control.rows = 4;
  control.maxLength = maxLength;
  return control;
}

function routineForm(routine = null) {
  const isEditing = Boolean(routine);
  setPageHeading(
    isEditing ? `Editar ${routine.nombre}` : "Nueva rutina",
    isEditing ? "Actualizá los datos generales. Los ejercicios se administran desde el detalle." : "Elegí un alumno vinculado y definí la base del plan. Luego podrás incorporar sus ejercicios.",
    isEditing ? "Editar rutina" : "Nueva rutina"
  );
  backLink.href = moduleUrl("lista");
  backLink.textContent = "← Volver a mis rutinas";

  const card = element("section", "fp-card tr-routine-editor");
  const form = element("form", "tr-routine-form");
  const grid = element("div", "tr-routine-form-grid");
  const name = textInput("nombre", routine?.nombre, { required: true, maxLength: 120 });
  grid.append(labeledControl("Nombre de la rutina *", name, "Usá un nombre breve y reconocible."));

  let clientSelect = null;
  const clientId = routine?.cliente_id;
  if (isEditing) {
    const readOnly = textInput("cliente", routine.cliente);
    readOnly.readOnly = true;
    grid.append(labeledControl("Alumno", readOnly, "El alumno no cambia durante la edición."));
  } else {
    clientSelect = document.createElement("select");
    clientSelect.name = "cliente_id";
    clientSelect.required = true;
    clientSelect.append(new Option("Seleccioná un alumno", ""));
    for (const student of state.payload?.options?.students || []) {
      clientSelect.append(new Option(`${student.apellido}, ${student.nombre}`, String(student.id)));
    }
    grid.append(labeledControl("Alumno vinculado *", clientSelect));
  }

  const objectiveSelect = document.createElement("select");
  objectiveSelect.name = "objetivo_id";
  const updateObjectives = (selectedClientId, selectedObjective = "") => {
    objectiveSelect.replaceChildren(new Option("Sin objetivo asignado", ""));
    for (const objective of objectivesFor(selectedClientId)) {
      objectiveSelect.append(new Option(`${objective.tipo}: ${objective.nombre}`, String(objective.id)));
    }
    objectiveSelect.value = selectedObjective ? String(selectedObjective) : "";
  };
  grid.append(labeledControl("Objetivo", objectiveSelect, "Solo se muestran objetivos registrados para ese alumno."));
  if (clientSelect) {
    clientSelect.addEventListener("change", () => updateObjectives(clientSelect.value));
    updateObjectives("");
  } else {
    updateObjectives(clientId, routine.objetivo_id);
  }

  const descriptionField = labeledControl("Descripción", textarea("descripcion", routine?.descripcion));
  descriptionField.classList.add("tr-field-wide");
  const notesField = labeledControl("Indicaciones para el alumno", textarea("observaciones", routine?.observaciones));
  notesField.classList.add("tr-field-wide");
  grid.append(descriptionField, notesField);

  const actions = element("div", "tr-form-actions");
  actions.append(link("Cancelar", moduleUrl("lista"), "fp-button fp-button-outline"));
  const submit = element("button", "fp-button fp-button-light", isEditing ? "Guardar cambios" : "Crear rutina");
  submit.type = "submit";
  actions.append(submit);
  form.append(grid, actions);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    submit.disabled = true;
    setStatus(isEditing ? "Guardando cambios…" : "Creando rutina…", "loading");
    const payload = {
      nombre: name.value.trim(),
      descripcion: form.elements.namedItem("descripcion").value.trim(),
      objetivo_id: objectiveSelect.value ? Number(objectiveSelect.value) : null,
      observaciones: form.elements.namedItem("observaciones").value.trim()
    };
    if (!isEditing) payload.cliente_id = Number(clientSelect.value);
    try {
      const result = await requestJson(
        isEditing ? `/api/v1/trainer/routines/${routine.id}` : "/api/v1/trainer/routines",
        { method: isEditing ? "PATCH" : "POST", body: payload }
      );
      const savedId = isEditing ? routine.id : result.routine.id;
      window.location.assign(moduleUrl("detalle", savedId));
    } catch (error) {
      setStatus(requestError(error), "error");
      submit.disabled = false;
    }
  });

  card.append(form);
  content.replaceChildren(card);
  content.setAttribute("aria-busy", "false");
  setStatus(isEditing ? "Editando una rutina activa." : "Completá los campos obligatorios para continuar.", "info");
  name.focus();
}

function assignmentFields(assignment = null, nextOrder = 1, maxOrder = nextOrder) {
  const grid = element("div", "tr-exercise-form-grid");
  const order = textInput("orden", assignment?.orden ?? nextOrder, { type: "number", required: true, min: 1, max: maxOrder });
  const series = textInput("series", assignment?.series ?? 3, { type: "number", required: true, min: 1, max: 100 });
  const repetitions = textInput("repeticiones", assignment?.repeticiones ?? 10, { type: "number", required: true, min: 1, max: 1000 });
  const weight = textInput("peso_kg", assignment?.peso_gramos === null || assignment?.peso_gramos === undefined ? "" : assignment.peso_gramos / 1000, { type: "number", min: 0, max: 2000, step: 0.25 });
  const rest = textInput("descanso_segundos", assignment?.descanso_segundos ?? 60, { type: "number", required: true, min: 0, max: 3600 });
  grid.append(
    labeledControl("Orden *", order),
    labeledControl("Series *", series),
    labeledControl("Repeticiones o segundos *", repetitions),
    labeledControl("Peso (kg)", weight, "Dejá vacío cuando no corresponda."),
    labeledControl("Descanso (segundos) *", rest)
  );
  return grid;
}

function assignmentPayload(form) {
  const weightValue = form.elements.namedItem("peso_kg").value;
  return {
    orden: Number(form.elements.namedItem("orden").value),
    series: Number(form.elements.namedItem("series").value),
    repeticiones: Number(form.elements.namedItem("repeticiones").value),
    peso_gramos: weightValue === "" ? null : Math.round(Number(weightValue) * 1000),
    descanso_segundos: Number(form.elements.namedItem("descanso_segundos").value)
  };
}

function editAssignmentForm(routine, assignment) {
  const form = element("form", "tr-inline-exercise-form");
  form.append(assignmentFields(assignment, assignment.orden, assignmentsFor(routine.id).length));
  const actions = element("div", "tr-form-actions");
  const cancel = button("Cancelar");
  const save = element("button", "fp-button fp-button-light", "Guardar ejercicio");
  save.type = "submit";
  cancel.addEventListener("click", () => {
    state.editingAssignmentId = null;
    renderDetail(routine);
  });
  actions.append(cancel, save);
  form.append(actions);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    save.disabled = true;
    setStatus("Guardando parámetros y orden…", "loading");
    try {
      await requestJson(`/api/v1/trainer/routines/${routine.id}/exercises/${assignment.id}`, {
        method: "PATCH",
        body: assignmentPayload(form)
      });
      state.editingAssignmentId = null;
      await refreshData();
      renderDetail(routines().find((item) => item.id === routine.id));
      setStatus("Ejercicio actualizado correctamente.", "success");
    } catch (error) {
      setStatus(requestError(error), "error");
      save.disabled = false;
    }
  });
  return form;
}

function assignmentCard(routine, assignment, index, total) {
  const card = element("article", "tr-assignment-card");
  const header = element("div", "tr-assignment-heading");
  const title = element("div");
  title.append(element("span", "tr-assignment-order", `EJERCICIO ${String(assignment.orden).padStart(2, "0")}`), element("h3", "", assignment.ejercicio));
  header.append(title, element("span", "tr-assignment-dose", `${assignment.series} × ${assignment.repeticiones}`));
  const values = element("dl", "tr-assignment-values");
  values.append(metaItem("Series", String(assignment.series)), metaItem("Repeticiones", String(assignment.repeticiones)), metaItem("Peso", formatWeight(assignment.peso_gramos)), metaItem("Descanso", `${assignment.descanso_segundos} s`));
  const actions = element("div", "tr-assignment-actions");
  const up = button("↑ Subir");
  up.disabled = index === 0;
  up.setAttribute("aria-label", `Subir ${assignment.ejercicio} una posición`);
  up.addEventListener("click", () => moveAssignment(routine, assignment, assignment.orden - 1, up));
  const down = button("↓ Bajar");
  down.disabled = index === total - 1;
  down.setAttribute("aria-label", `Bajar ${assignment.ejercicio} una posición`);
  down.addEventListener("click", () => moveAssignment(routine, assignment, assignment.orden + 1, down));
  const edit = button("Editar");
  edit.addEventListener("click", () => {
    state.editingAssignmentId = assignment.id;
    renderDetail(routine);
  });
  const remove = button("Quitar", "fp-button tr-button-danger");
  remove.addEventListener("click", () => removeAssignment(routine, assignment, remove));
  actions.append(up, down, edit, remove);
  card.append(header, values, actions);
  if (state.editingAssignmentId === assignment.id) card.append(editAssignmentForm(routine, assignment));
  return card;
}

function addAssignmentForm(routine, assignmentCount) {
  const panel = element("section", "fp-card tr-add-exercise-panel");
  const headingNode = element("div", "tr-panel-heading");
  headingNode.append(element("div", "", ""), button("Cerrar"));
  headingNode.firstElementChild.append(element("span", "fp-section-kicker", "ACCIÓN CONTEXTUAL"), element("h2", "", "Agregar ejercicio"));
  headingNode.lastElementChild.addEventListener("click", () => {
    state.addingAssignment = false;
    renderDetail(routine);
  });
  const form = element("form", "tr-routine-form");
  const exercise = document.createElement("select");
  exercise.name = "ejercicio_id";
  exercise.required = true;
  exercise.append(new Option("Seleccioná un ejercicio", ""));
  const assignedExerciseIds = new Set(assignmentsFor(routine.id).map((item) => item.ejercicio_id));
  for (const item of (state.payload?.options?.exercises || []).filter((candidate) => !assignedExerciseIds.has(candidate.id))) {
    exercise.append(new Option(item.grupo_muscular ? `${item.nombre} · ${item.grupo_muscular}` : item.nombre, String(item.id)));
  }
  const fields = assignmentFields(null, assignmentCount + 1, assignmentCount + 1);
  fields.prepend(labeledControl("Ejercicio del catálogo *", exercise));
  const actions = element("div", "tr-form-actions");
  const submit = element("button", "fp-button fp-button-light", "Agregar a la rutina");
  submit.type = "submit";
  actions.append(submit);
  form.append(fields, actions);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    submit.disabled = true;
    setStatus("Agregando ejercicio…", "loading");
    try {
      await requestJson(`/api/v1/trainer/routines/${routine.id}/exercises`, {
        method: "POST",
        body: { ejercicio_id: Number(exercise.value), ...assignmentPayload(form) }
      });
      state.addingAssignment = false;
      await refreshData();
      renderDetail(routines().find((item) => item.id === routine.id));
      setStatus("Ejercicio agregado a la rutina.", "success");
    } catch (error) {
      setStatus(requestError(error), "error");
      submit.disabled = false;
    }
  });

  const catalog = document.createElement("details");
  catalog.className = "tr-catalog-create";
  catalog.append(element("summary", "", "¿No aparece? Crear ejercicio en el catálogo"));
  const catalogForm = element("form", "tr-catalog-form");
  const catalogName = textInput("nombre", "", { required: true, maxLength: 120 });
  const muscle = textInput("grupo_muscular", "", { maxLength: 120 });
  const description = textarea("descripcion");
  const catalogButton = element("button", "fp-button fp-button-primary", "Crear ejercicio");
  catalogButton.type = "submit";
  catalogForm.append(labeledControl("Nombre *", catalogName), labeledControl("Grupo muscular", muscle), labeledControl("Descripción", description), catalogButton);
  catalogForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!catalogForm.reportValidity()) return;
    catalogButton.disabled = true;
    setStatus("Creando ejercicio en el catálogo…", "loading");
    try {
      await requestJson("/api/v1/trainer/exercises", {
        method: "POST",
        body: { nombre: catalogName.value.trim(), grupo_muscular: muscle.value.trim(), descripcion: description.value.trim() }
      });
      await refreshData();
      state.addingAssignment = true;
      renderDetail(routines().find((item) => item.id === routine.id));
      setStatus("Ejercicio creado. Ya podés seleccionarlo.", "success");
    } catch (error) {
      setStatus(requestError(error), "error");
      catalogButton.disabled = false;
    }
  });
  catalog.append(catalogForm);
  panel.append(headingNode, form, catalog);
  return panel;
}

function renderDetail(routine) {
  setPageHeading(routine.nombre, "Consultá la asignación completa y administrá los ejercicios desde un único lugar.", "Detalle de rutina");
  backLink.href = moduleUrl("lista");
  backLink.textContent = "← Volver a mis rutinas";

  const page = element("div", "tr-routine-detail-layout");
  const summary = element("section", "fp-card tr-routine-summary");
  const summaryTop = element("div", "tr-routine-card-top");
  const summaryTitle = element("div");
  summaryTitle.append(element("span", "fp-section-kicker", "RESUMEN DEL PLAN"), element("h2", "", routine.nombre));
  summaryTop.append(summaryTitle, statusBadge(routine.activa));
  const metadata = element("dl", "tr-routine-meta");
  metadata.append(metaItem("Alumno", routine.cliente), metaItem("Objetivo", routine.objetivo || "Sin objetivo asignado"), metaItem("Creada", formatDate(routine.fecha_creacion_utc)), metaItem("Ejercicios", String(routine.ejercicios)));
  summary.append(summaryTop, metadata);
  if (routine.descripcion) summary.append(element("p", "tr-routine-description", routine.descripcion));
  if (routine.observaciones) {
    const note = element("div", "tr-routine-note");
    note.append(element("strong", "", "Indicaciones"), element("p", "", routine.observaciones));
    summary.append(note);
  }
  if (!routine.activa) summary.append(element("p", "tr-inactive-note", "Esta rutina conserva su historial y puede consultarse, pero ya no admite cambios."));
  const summaryActions = element("div", "tr-routine-actions");
  if (routine.activa) {
    summaryActions.append(link("Editar datos", moduleUrl("editar", routine.id), "fp-button fp-button-outline"));
    const deactivate = button("Eliminar rutina", "fp-button tr-button-danger");
    deactivate.addEventListener("click", () => deactivateRoutine(routine, deactivate));
    summaryActions.append(deactivate);
  }
  summary.append(summaryActions);

  const assignmentSection = element("section", "tr-assignment-section");
  const sectionHeading = element("div", "tr-routine-result-heading");
  const assignmentTitle = element("div");
  assignmentTitle.append(element("span", "fp-section-kicker", "SECUENCIA DE ENTRENAMIENTO"), element("h2", "", "Ejercicios"));
  const assignmentRows = assignmentsFor(routine.id);
  const actionSlot = element("div", "tr-heading-actions");
  actionSlot.append(element("span", "fp-count-badge", `${assignmentRows.length} ${assignmentRows.length === 1 ? "ejercicio" : "ejercicios"}`));
  if (routine.activa && !state.addingAssignment) {
    const add = button("+ Agregar ejercicio", "fp-button fp-button-light");
    add.addEventListener("click", () => {
      state.addingAssignment = true;
      renderDetail(routine);
    });
    actionSlot.append(add);
  }
  sectionHeading.append(assignmentTitle, actionSlot);
  const list = element("div", "tr-assignment-list");
  if (!assignmentRows.length) {
    const empty = element("div", "fp-card tr-routine-empty");
    empty.append(element("strong", "", "La rutina todavía no tiene ejercicios"), element("p", "", routine.activa ? "Agregá el primer ejercicio y definí sus series, repeticiones, peso y descanso." : "La rutina quedó inactiva sin ejercicios registrados."));
    list.append(empty);
  } else if (routine.activa) {
    list.append(...assignmentRows.map((assignment, index) => assignmentCard(routine, assignment, index, assignmentRows.length)));
  } else {
    list.append(...assignmentRows.map((assignment) => {
      const card = element("article", "tr-assignment-card");
      const title = element("div", "tr-assignment-heading");
      title.append(element("h3", "", `${assignment.orden}. ${assignment.ejercicio}`), element("span", "tr-assignment-dose", `${assignment.series} × ${assignment.repeticiones}`));
      const values = element("dl", "tr-assignment-values");
      values.append(metaItem("Peso", formatWeight(assignment.peso_gramos)), metaItem("Descanso", `${assignment.descanso_segundos} s`));
      card.append(title, values);
      return card;
    }));
  }
  assignmentSection.append(sectionHeading, list);
  page.append(summary);
  if (routine.activa && state.addingAssignment) page.append(addAssignmentForm(routine, assignmentRows.length));
  page.append(assignmentSection);
  content.replaceChildren(page);
  content.setAttribute("aria-busy", "false");
  setStatus(routine.activa ? "Rutina activa lista para gestionar." : "Vista de historial: la rutina está inactiva.", routine.activa ? "success" : "info");
}

async function moveAssignment(routine, assignment, order, control) {
  control.disabled = true;
  setStatus("Actualizando el orden de forma transaccional…", "loading");
  try {
    await requestJson(`/api/v1/trainer/routines/${routine.id}/exercises/${assignment.id}`, { method: "PATCH", body: { orden: order } });
    await refreshData();
    renderDetail(routines().find((item) => item.id === routine.id));
    setStatus("Orden actualizado correctamente.", "success");
  } catch (error) {
    setStatus(requestError(error), "error");
    control.disabled = false;
  }
}

async function removeAssignment(routine, assignment, control) {
  if (!window.confirm(`¿Quitar ${assignment.ejercicio} de ${routine.nombre}? La rutina seguirá guardada.`)) return;
  control.disabled = true;
  setStatus("Quitando ejercicio…", "loading");
  try {
    await requestJson(`/api/v1/trainer/routines/${routine.id}/exercises/${assignment.id}`, { method: "DELETE" });
    await refreshData();
    renderDetail(routines().find((item) => item.id === routine.id));
    setStatus("Ejercicio quitado; el orden restante fue normalizado.", "success");
  } catch (error) {
    setStatus(requestError(error), "error");
    control.disabled = false;
  }
}

async function deactivateRoutine(routine, control) {
  const confirmed = window.confirm(`¿Eliminar la rutina “${routine.nombre}”? Se desactivará y conservará su historial.`);
  if (!confirmed) return;
  control.disabled = true;
  setStatus("Desactivando rutina…", "loading");
  try {
    await requestJson(`/api/v1/trainer/routines/${routine.id}`, { method: "DELETE" });
    await refreshData();
    state.activity = "activas";
    window.history.replaceState({}, "", moduleUrl("lista"));
    renderList();
    setStatus("Rutina desactivada. Su historial permanece disponible en el filtro Inactivas.", "success");
  } catch (error) {
    setStatus(requestError(error), "error");
    control.disabled = false;
  }
}

function renderMissing(message) {
  setPageHeading("Rutina no disponible", "La selección no puede abrirse desde tu perfil.", "Rutina no disponible");
  backLink.href = moduleUrl("lista");
  backLink.textContent = "← Volver a mis rutinas";
  const card = element("section", "fp-card tr-routine-empty");
  card.append(element("strong", "", "No encontramos esa rutina"), element("p", "", message), link("Ir al listado", moduleUrl("lista"), "fp-button fp-button-primary"));
  content.replaceChildren(card);
  content.setAttribute("aria-busy", "false");
  setStatus("No se modificó ningún dato.", "error");
}

async function refreshData() {
  state.payload = await requestJson("/api/v1/trainer/dashboard");
}

function renderCurrentView() {
  const params = new URL(window.location.href).searchParams;
  const view = params.get("vista") || "lista";
  const routineId = Number(params.get("rutina"));
  if (view === "lista") {
    renderList();
    return;
  }
  if (view === "crear") {
    if (!(state.payload?.options?.students || []).length) {
      renderMissing("Necesitás al menos un alumno vinculado antes de crear una rutina.");
      return;
    }
    routineForm();
    return;
  }
  const routine = routines().find((item) => item.id === routineId);
  if (!routine) {
    renderMissing("Puede que ya no exista o que corresponda a otro entrenador.");
    return;
  }
  if (view === "editar") {
    if (!routine.activa) {
      renderMissing("Las rutinas inactivas son de solo lectura y no pueden editarse.");
      return;
    }
    routineForm(routine);
    return;
  }
  if (view === "detalle") {
    renderDetail(routine);
    return;
  }
  renderMissing("La vista solicitada no está disponible.");
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
    const retry = button("Reintentar", "fp-button fp-button-primary");
    retry.addEventListener("click", () => window.location.reload());
    const card = element("section", "fp-card tr-routine-empty");
    card.append(element("strong", "", "No pudimos cargar las rutinas"), element("p", "", "Verificá tu sesión o intentá nuevamente."), retry);
    content.replaceChildren(card);
  }
}

initialize();
