export function initializeDrawer({ panel, toggle, close, overlay, breakpoint = "(max-width: 860px)" }) {
  if (!panel || !toggle || !close || !overlay) return;

  const viewport = window.matchMedia(breakpoint);
  const focusableItems = () =>
    [...panel.querySelectorAll('a[href], button:not([disabled])')].filter(
      (item) => !item.hasAttribute("aria-disabled") && !item.closest("[inert]")
    );

  const setOpen = (isOpen, restoreFocus = false) => {
    const shouldOpen = viewport.matches && isOpen;

    panel.classList.toggle("is-open", shouldOpen);
    panel.inert = !shouldOpen && viewport.matches;
    panel.setAttribute("aria-hidden", String(!shouldOpen && viewport.matches));
    toggle.setAttribute("aria-expanded", String(shouldOpen));
    overlay.hidden = !shouldOpen;
    document.body.classList.toggle("fp-drawer-open", shouldOpen);

    if (shouldOpen) {
      requestAnimationFrame(() => close.focus());
    } else if (restoreFocus && viewport.matches) {
      toggle.focus();
    }
  };

  const syncViewport = () => {
    const isMobile = viewport.matches;
    panel.classList.remove("is-open");
    panel.inert = isMobile;
    panel.setAttribute("aria-hidden", String(isMobile));
    toggle.setAttribute("aria-expanded", "false");
    overlay.hidden = true;
    document.body.classList.remove("fp-drawer-open");
  };

  toggle.addEventListener("click", () => {
    setOpen(toggle.getAttribute("aria-expanded") !== "true");
  });
  close.addEventListener("click", () => setOpen(false, true));
  overlay.addEventListener("click", () => setOpen(false, true));
  panel.querySelectorAll("a[href]").forEach((link) => {
    link.addEventListener("click", () => setOpen(false, true));
  });

  document.addEventListener("keydown", (event) => {
    if (!viewport.matches || toggle.getAttribute("aria-expanded") !== "true") return;

    if (event.key === "Escape") {
      setOpen(false, true);
      return;
    }

    if (event.key !== "Tab") return;
    const items = focusableItems();
    const firstItem = items[0];
    const lastItem = items[items.length - 1];

    if (event.shiftKey && document.activeElement === firstItem) {
      event.preventDefault();
      lastItem?.focus();
    } else if (!event.shiftKey && document.activeElement === lastItem) {
      event.preventDefault();
      firstItem?.focus();
    }
  });

  viewport.addEventListener("change", syncViewport);
  syncViewport();
}
