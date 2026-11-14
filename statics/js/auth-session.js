"use strict";

(() => {
  const loginLink = document.getElementById("google-login-link");
  const sessionSection = document.getElementById("authenticated-session");
  const sessionSummary = document.getElementById("session-summary");
  const logoutForm = document.getElementById("logout-form");
  const logoutButton = document.getElementById("logout-button");
  const result = document.getElementById("auth-session-result");

  if (!loginLink || !sessionSection || !sessionSummary || !logoutForm || !logoutButton || !result) {
    return;
  }

  let csrfToken = null;
  const csrfField = logoutForm.elements.namedItem("csrf_token");

  const showStatus = (message, state) => {
    result.textContent = message;
    result.className = state ? `form-message message-${state}` : "form-message";
  };

  const showSignedOut = () => {
    csrfToken = null;
    if (csrfField) {
      csrfField.value = "";
    }
    sessionSummary.textContent = "";
    sessionSection.hidden = true;
    loginLink.hidden = false;
  };

  const loadSession = async () => {
    try {
      const response = await fetch("/auth/me", {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });

      if (response.status === 401) {
        showSignedOut();
        return;
      }
      if (!response.ok) {
        throw new Error("session_check_failed");
      }

      const identity = await response.json();
      if (!identity.authenticated || !identity.csrf_token || !identity.user) {
        throw new Error("session_payload_invalid");
      }

      csrfToken = identity.csrf_token;
      if (csrfField) {
        csrfField.value = csrfToken;
      }
      sessionSummary.textContent = `Sesión iniciada como ${identity.user.nombre} ${identity.user.apellido} · ${identity.user.rol} (ID FitPath ${identity.user.id}).`;
      loginLink.hidden = true;
      sessionSection.hidden = false;
    } catch (_error) {
      showStatus("No pudimos comprobar la sesión. Recargá la página e intentá de nuevo.", "error");
    }
  };

  logoutForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    csrfToken = csrfField?.value || csrfToken;
    if (!csrfToken) {
      showStatus("No se pudo validar la sesión. Recargá la página e intentá de nuevo.", "error");
      return;
    }

    logoutButton.disabled = true;
    showStatus("Cerrando sesión…", "");

    try {
      const response = await fetch("/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "text/html",
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        },
        body: new URLSearchParams({ csrf_token: csrfToken }),
      });

      if (!response.ok) {
        throw new Error("logout_failed");
      }

      const verification = await fetch("/auth/me", {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (verification.status !== 401) {
        throw new Error("session_still_active");
      }

      showSignedOut();
      showStatus("Sesión cerrada correctamente. /auth/me confirma que ya no está activa.", "success");
    } catch (_error) {
      logoutButton.disabled = false;
      showStatus("No pudimos cerrar la sesión. Recargá la página e intentá de nuevo.", "error");
    }
  });

  loadSession();
})();
