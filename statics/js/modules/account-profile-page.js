import { initializeDrawer } from "./navigation-drawer.js";
import { initializeAccountProfile } from "./profile.js";
import { initializeProfileImage } from "./profile-image.js";

initializeDrawer({
  panel: document.querySelector("#fp-sidebar"),
  toggle: document.querySelector("[data-menu-toggle]"),
  close: document.querySelector("[data-menu-close]"),
  overlay: document.querySelector("[data-menu-overlay]")
});

function showPageStatus(message) {
  const status = document.querySelector("[data-profile-form-status]");
  if (status) {
    status.textContent = message;
    status.dataset.error = "true";
  }
}

async function initializePage() {
  const response = await fetch("/auth/me", {
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: "application/json" }
  });
  if (response.status === 401) {
    window.location.replace("/auth/login");
    return;
  }
  if (!response.ok) throw new Error("session_check_failed");
  const identity = await response.json();
  const fullName = `${identity.user.nombre} ${identity.user.apellido}`.trim();
  const form = document.querySelector("[data-profile-logout]");
  const csrf = form?.elements.namedItem("csrf_token");
  const button = form?.querySelector("button[type='submit']");
  if (csrf) csrf.value = identity.csrf_token;
  if (button) button.disabled = false;
  document.querySelectorAll("[data-demo-text='profile.name']").forEach((node) => {
    node.textContent = fullName;
  });

  await initializeAccountProfile({ csrfToken: identity.csrf_token });
  await initializeProfileImage({ identity, fullName });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (button) button.disabled = true;
    const logout = await fetch("/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
      body: new URLSearchParams({ csrf_token: identity.csrf_token })
    });
    if (logout.ok) window.location.assign("/auth/login?logout=1");
    else {
      if (button) button.disabled = false;
      showPageStatus("No pudimos cerrar la sesión.");
    }
  });
}

initializePage().catch(() => showPageStatus("No pudimos comprobar la sesión FitPath."));
