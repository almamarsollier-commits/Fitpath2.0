function showProfileImage(url, fullName) {
  if (!url) return;
  document.querySelectorAll(".fp-avatar, .fp-client-avatar, .cl-profile-avatar").forEach((avatar) => {
    const image = document.createElement("img");
    image.src = url;
    image.alt = avatar.classList.contains("cl-profile-avatar") ? `Foto de perfil de ${fullName}` : "";
    image.referrerPolicy = "no-referrer";
    avatar.replaceChildren(image);
    avatar.classList.add("has-profile-image");
  });
}

function setStatus(node, message, isError = false) {
  if (!node) return;
  node.textContent = message;
  node.dataset.error = isError ? "true" : "false";
}

export async function initializeProfileImage({ identity, fullName }) {
  const form = document.querySelector("[data-profile-image-form]");
  const input = form?.elements.namedItem("image");
  const button = form?.querySelector("button[type='submit']");
  const status = document.querySelector("[data-profile-image-status]");
  let previewUrl = null;

  input?.addEventListener("change", () => {
    const file = input.files?.[0];
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    if (!file) return;
    if (!file.type.match(/^image\/(jpeg|png|webp)$/) || file.size > 5 * 1024 * 1024) {
      setStatus(status, "Elegí una imagen JPEG, PNG o WebP de hasta 5 MiB.", true);
      return;
    }
    previewUrl = URL.createObjectURL(file);
    showProfileImage(previewUrl, fullName);
    setStatus(status, "Previsualización lista. Confirmá con Guardar foto.");
  });

  try {
    const response = await fetch("/api/v1/me/profile-image", {
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" }
    });
    if (response.ok) {
      const payload = await response.json();
      if (payload.image?.url) showProfileImage(payload.image.url, fullName);
    } else if (response.status === 503) {
      setStatus(status, "La carga de fotos requiere configurar el bucket privado.", true);
    }
  } catch (_error) {
    setStatus(status, "No pudimos consultar tu foto de perfil.", true);
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = input?.files?.[0];
    if (!file || !file.type.match(/^image\/(jpeg|png|webp)$/) || file.size > 5 * 1024 * 1024) {
      setStatus(status, "Elegí una imagen JPEG, PNG o WebP de hasta 5 MiB.", true);
      return;
    }
    if (button) button.disabled = true;
    setStatus(status, "Subiendo tu foto…");
    const body = new FormData();
    body.append("image", file);
    try {
      const response = await fetch("/api/v1/me/profile-image", {
        method: "POST",
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-CSRF-Token": identity.csrf_token },
        body
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw payload;
      if (payload.image?.url) showProfileImage(payload.image.url, fullName);
      form.reset();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = null;
      setStatus(status, "Tu foto se guardó de forma privada.");
    } catch (error) {
      const message = error.error === "storage_not_configured"
        ? "El almacenamiento S3 todavía no está configurado."
        : "No pudimos guardar la imagen. Revisá el formato e intentá nuevamente.";
      setStatus(status, message, true);
    } finally {
      if (button) button.disabled = false;
    }
  });
}
