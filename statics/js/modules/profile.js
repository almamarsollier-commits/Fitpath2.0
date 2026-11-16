function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function initials(profile) {
  return `${profile.nombre?.[0] || ""}${profile.apellido?.[0] || ""}`.toUpperCase();
}

function updateProfilePresentation(profile) {
  const fullName = `${profile.nombre} ${profile.apellido}`.trim();
  document.querySelectorAll("[data-profile-display-name], .fp-user-chip [data-demo-text='profile.name']")
    .forEach((node) => { node.textContent = fullName; });
  const biography = document.querySelector("[data-profile-display-bio]");
  if (biography) {
    biography.textContent = profile.biografia || "Agregá una biografía breve para personalizar tu espacio.";
  }
  document.querySelectorAll(".fp-avatar:not(.has-profile-image), .fp-client-avatar:not(.has-profile-image), .cl-profile-avatar:not(.has-profile-image)")
    .forEach((avatar) => { avatar.textContent = initials(profile); });
}

function renderObjectives(mount, catalog, selected) {
  if (!mount) return;
  if (!catalog.length) {
    mount.replaceChildren(element("p", "cl-payment-empty", "Todavía no hay objetivos disponibles en el catálogo."));
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const objective of catalog) {
    const label = element("label", "cl-objective-option");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.name = "objetivos";
    checkbox.value = String(objective.id);
    checkbox.checked = selected.has(objective.id);
    const copy = element("span");
    copy.append(
      element("strong", "", objective.nombre),
      element("small", "", objective.descripcion || objective.tipo)
    );
    label.append(checkbox, copy);
    fragment.append(label);
  }
  mount.replaceChildren(fragment);
}

function fillForm(form, profile) {
  for (const field of ["nombre", "apellido", "nombre_usuario", "email", "telefono", "biografia"]) {
    const control = form.elements.namedItem(field);
    if (control) control.value = profile[field] || "";
  }
  form.elements.namedItem("tema").value = profile.preferencias.tema;
  form.elements.namedItem("movimiento_reducido").checked = profile.preferencias.movimiento_reducido;
  form.elements.namedItem("recordatorios_clase").checked = profile.preferencias.recordatorios_clase;
  const count = document.querySelector("[data-bio-count]");
  if (count) count.textContent = String((profile.biografia || "").length);
  renderObjectives(
    document.querySelector("[data-profile-objectives]"),
    profile.catalogo_objetivos || [],
    new Set(profile.objetivos || [])
  );
  const objectiveFieldset = document.querySelector("[data-profile-objective-fieldset]");
  if (objectiveFieldset) objectiveFieldset.hidden = profile.rol !== "Cliente";
}

function clientValidationMessage(form) {
  if (!form.reportValidity()) return "Revisá los campos marcados antes de guardar.";
  const username = form.elements.namedItem("nombre_usuario").value.trim().toLowerCase();
  if (!/^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])$/.test(username)) {
    return "El nombre de usuario no tiene un formato válido.";
  }
  const selectedGoals = form.querySelectorAll("input[name='objetivos']:checked");
  if (selectedGoals.length > 10) return "Podés elegir hasta 10 objetivos.";
  return null;
}

function friendlyError(payload) {
  if (payload.error === "username_unavailable") return "Ese nombre de usuario ya está en uso.";
  if (payload.error === "csrf_failed") return "La sesión cambió. Recargá la página antes de guardar.";
  return payload.message || "No pudimos guardar el perfil. Revisá los datos e intentá nuevamente.";
}

export async function initializeAccountProfile({ csrfToken }) {
  const root = document.querySelector("[data-account-profile-root]");
  const form = root?.querySelector("[data-account-profile-form]");
  if (!root || !form) return;
  const status = form.querySelector("[data-profile-form-status]");
  const submit = form.querySelector("button[type='submit']");
  const biography = form.elements.namedItem("biografia");
  let isClientProfile = false;

  const setStatus = (message, error = false) => {
    status.textContent = message;
    status.dataset.error = error ? "true" : "false";
  };

  biography.addEventListener("input", () => {
    const count = document.querySelector("[data-bio-count]");
    if (count) count.textContent = String(biography.value.length);
  });

  try {
    const response = await fetch("/api/v1/me/profile", {
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" }
    });
    if (!response.ok) throw new Error("profile_load_failed");
    const payload = await response.json();
    isClientProfile = payload.profile.rol === "Cliente";
    fillForm(form, payload.profile);
    updateProfilePresentation(payload.profile);
    setStatus("Perfil cargado. Solo se guardarán los cambios que confirmes.");
  } catch (_error) {
    setStatus("No pudimos cargar tu perfil. Recargá la página.", true);
    submit.disabled = true;
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const validation = clientValidationMessage(form);
    if (validation) {
      setStatus(validation, true);
      return;
    }
    const payload = {
      nombre: form.elements.namedItem("nombre").value,
      apellido: form.elements.namedItem("apellido").value,
      nombre_usuario: form.elements.namedItem("nombre_usuario").value,
      telefono: form.elements.namedItem("telefono").value,
      biografia: biography.value,
      preferencias: {
        tema: form.elements.namedItem("tema").value,
        movimiento_reducido: form.elements.namedItem("movimiento_reducido").checked,
        recordatorios_clase: form.elements.namedItem("recordatorios_clase").checked
      }
    };
    if (isClientProfile) {
      payload.objetivos = [...form.querySelectorAll("input[name='objetivos']:checked")]
        .map((checkbox) => Number(checkbox.value));
    }
    submit.disabled = true;
    setStatus("Guardando cambios…");
    try {
      const response = await fetch("/api/v1/me/profile", {
        method: "PATCH",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken
        },
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw result;
      fillForm(form, result.profile);
      updateProfilePresentation(result.profile);
      setStatus("Perfil actualizado correctamente.");
    } catch (error) {
      setStatus(friendlyError(error || {}), true);
    } finally {
      submit.disabled = false;
    }
  });
}
