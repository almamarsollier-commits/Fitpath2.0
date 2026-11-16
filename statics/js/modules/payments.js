const statusLabels = {
  creado: "Preparando checkout",
  pendiente: "Pendiente",
  aprobado: "Aprobado",
  rechazado: "Rechazado",
  cancelado: "Cancelado",
  error: "No disponible",
  pagada: "Pagada",
  anulada: "Anulada",
  activa: "Activa",
  vencida: "Vencida",
  cancelada: "Cancelada"
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatMoney(amountMinor, currency, decimals = 2) {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(amountMinor / (10 ** decimals));
}

function statusBadge(status) {
  return element(
    "span",
    `fp-payment-status is-${status}`,
    statusLabels[status] || status
  );
}

function renderMembership(root, membership) {
  const name = root.querySelector("[data-payment-membership-name]");
  const state = root.querySelector("[data-payment-membership-state]");
  const dates = root.querySelector("[data-payment-membership-dates]");
  if (!membership) {
    if (name) name.textContent = "Sin membresía registrada";
    if (state) state.replaceChildren(statusBadge("vencida"));
    if (dates) dates.textContent = "No hay una suscripción asociada a tu cuenta.";
    return;
  }
  if (name) name.textContent = membership.nombre;
  if (state) state.replaceChildren(statusBadge(membership.estado));
  if (dates) {
    dates.textContent = membership.fecha_fin
      ? `Desde ${membership.fecha_inicio} hasta ${membership.fecha_fin}`
      : `Desde ${membership.fecha_inicio}, sin fecha de finalización`;
  }
}

function renderDebts(root, debts, checkoutAvailable) {
  const mount = root.querySelector("[data-payment-debts]");
  if (!mount) return;
  if (!debts.length) {
    mount.replaceChildren(element("p", "cl-payment-empty", "No tenés deudas registradas."));
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const debt of debts) {
    const card = element("article", "fp-card cl-debt-card");
    const heading = element("div", "cl-debt-heading");
    const title = element("div");
    title.append(
      element("span", "fp-section-kicker", `VENCE ${debt.due_on}`),
      element("h3", "", debt.concept)
    );
    heading.append(title, statusBadge(debt.status));
    const amount = element(
      "strong",
      "cl-debt-amount",
      formatMoney(debt.outstanding_minor, debt.currency, debt.currency_decimals)
    );
    const detail = element(
      "p",
      "",
      debt.status === "pagada"
        ? "Obligación confirmada como pagada."
        : `Importe original ${formatMoney(debt.amount_minor, debt.currency, debt.currency_decimals)}.`
    );
    card.append(heading, amount, detail);
    if (debt.status === "pendiente" && debt.outstanding_minor > 0) {
      const button = element(
        "button",
        "fp-button fp-button-primary",
        checkoutAvailable ? "Pagar con Mercado Pago" : "Pago de prueba no configurado"
      );
      button.type = "button";
      button.dataset.payDebt = String(debt.id);
      button.disabled = !checkoutAvailable;
      card.append(button);
    }
    fragment.append(card);
  }
  mount.replaceChildren(fragment);
}

function renderHistory(root, history) {
  const mount = root.querySelector("[data-payment-history]");
  if (!mount) return;
  if (!history.length) {
    mount.replaceChildren(element("p", "cl-payment-empty", "Todavía no hay intentos de pago."));
    return;
  }
  const list = element("ul", "cl-payment-history-list");
  for (const item of history) {
    const row = element("li");
    const copy = element("span");
    copy.append(
      element("strong", "", item.concept),
      element(
        "small",
        "",
        `${formatMoney(item.amount_minor, item.currency, item.currency_decimals)} · ${item.updated_at}`
      )
    );
    row.append(copy, statusBadge(item.status));
    list.append(row);
  }
  mount.replaceChildren(list);
}

export async function initializePayments({ csrfToken }) {
  const root = document.querySelector("[data-payments-root]");
  if (!root) return;
  const status = root.querySelector("[data-payment-status]");
  const setStatus = (message, isError = false) => {
    if (!status) return;
    status.textContent = message;
    status.dataset.error = isError ? "true" : "false";
  };

  const loadSummary = async () => {
    const response = await fetch("/api/v1/client/payments", {
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" }
    });
    if (!response.ok) throw new Error("summary_failed");
    const payload = await response.json();
    renderMembership(root, payload.membership);
    renderDebts(root, payload.debts, payload.checkout_available);
    renderHistory(root, payload.history);
    if (!payload.checkout_available) {
      setStatus("Checkout Pro está implementado, pero faltan credenciales de prueba y una URL HTTPS pública.", true);
    } else {
      setStatus("Checkout Pro disponible en modo de prueba.");
    }
  };

  const params = new URLSearchParams(window.location.search);
  const returnedPaymentId = params.get("payment_id") || params.get("collection_id");
  if (returnedPaymentId) {
    setStatus("Confirmando el resultado con Mercado Pago…");
    try {
      const response = await fetch("/api/v1/client/payment-intents/confirm", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken
        },
        body: JSON.stringify({ payment_id: returnedPaymentId })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "confirmation_failed");
      setStatus(`Pago ${statusLabels[payload.payment.status] || payload.payment.status}.`);
    } catch (_error) {
      setStatus("No pudimos confirmar todavía el resultado. El Webhook puede actualizarlo luego.", true);
    }
  }

  root.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-pay-debt]");
    if (!button) return;
    button.disabled = true;
    setStatus("Preparando el checkout seguro de prueba…");
    try {
      const response = await fetch("/api/v1/client/payment-intents", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken
        },
        body: JSON.stringify({ debt_id: Number(button.dataset.payDebt) })
      });
      const payload = await response.json();
      if (!response.ok || !payload.intent?.checkout_url) {
        throw new Error(payload.error || "checkout_failed");
      }
      window.location.assign(payload.intent.checkout_url);
    } catch (error) {
      button.disabled = false;
      const message = error.message === "payments_not_configured"
        ? "Faltan las credenciales de prueba o la URL HTTPS pública."
        : "No pudimos iniciar el pago. Volvé a intentar.";
      setStatus(message, true);
    }
  });

  try {
    await loadSummary();
  } catch (_error) {
    setStatus("No pudimos cargar tus pagos y deudas.", true);
  }
}
