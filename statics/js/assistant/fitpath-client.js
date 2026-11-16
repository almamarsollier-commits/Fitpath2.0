(function (root) {
  "use strict";

  const assistant = root.FitPathAssistant = root.FitPathAssistant || {};

  const operationPaths = Object.freeze({
    "classes.list": { method: "GET", path: "/api/v1/assistant/classes" },
    "routine.get": { method: "GET", path: "/api/v1/assistant/routine" },
    "progress.get": { method: "GET", path: "/api/v1/assistant/progress" },
    "membership.get": { method: "GET", path: "/api/v1/assistant/membership" },
    "enrollments.create": { method: "POST", path: "/api/v1/assistant/enrollments" },
    "enrollments.cancel": { method: "DELETE", path: "/api/v1/assistant/enrollments" }
  });

  class FitPathClient {
    constructor(options) {
      const settings = options || {};
      this.baseUrl = settings.baseUrl || "";
      this.fetch = settings.fetch || root.fetch?.bind(root);
      this.offline = settings.offline ?? (root.location?.protocol === "file:");
      this.timeout = settings.timeout || 2500;
    }

    async _request(path, options) {
      if (this.offline || !this.fetch) return { ok: false, reason: "backend_unavailable" };
      const controller = typeof AbortController === "function" ? new AbortController() : null;
      const timer = controller ? setTimeout(() => controller.abort(), this.timeout) : null;
      try {
        const response = await this.fetch(`${this.baseUrl}${path}`, {
          credentials: "same-origin",
          cache: "no-store",
          ...options,
          headers: { Accept: "application/json", ...(options?.headers || {}) },
          signal: controller?.signal
        });
        let payload = null;
        try { payload = await response.json(); } catch (_error) { payload = null; }
        if (response.ok) return { ok: true, status: response.status, data: payload };
        if (response.status === 401) return { ok: false, reason: "authentication_required", status: 401 };
        if (response.status === 403) return { ok: false, reason: "permission_denied", status: 403 };
        if ([404, 405, 501].includes(response.status)) return { ok: false, reason: "unsupported_operation", status: response.status };
        return { ok: false, reason: payload?.error || "backend_error", status: response.status };
      } catch (_error) {
        return { ok: false, reason: "backend_unavailable" };
      } finally {
        if (timer) clearTimeout(timer);
      }
    }

    async capabilities() {
      return this._request("/api/v1/assistant/capabilities", { method: "GET" });
    }

    async perform(operation, parameters) {
      const target = operationPaths[operation];
      if (!target) return { ok: false, reason: "unsupported_operation" };
      if (target.method === "GET") return this._request(target.path, { method: "GET" });

      const identity = await this._request("/auth/me", { method: "GET" });
      if (!identity.ok) return identity;
      const csrfToken = identity.data?.csrf_token;
      if (!csrfToken) return { ok: false, reason: "authentication_required" };
      const id = parameters?.id;
      const path = target.method === "DELETE" ? `${target.path}/${encodeURIComponent(id)}` : target.path;
      return this._request(path, {
        method: target.method,
        headers: {
          "Content-Type": "application/json;charset=UTF-8",
          "X-CSRF-Token": csrfToken
        },
        body: target.method === "POST" ? JSON.stringify({ clase_id: id }) : undefined
      });
    }
  }

  assistant.FitPathClient = FitPathClient;
})(typeof window !== "undefined" ? window : globalThis);
