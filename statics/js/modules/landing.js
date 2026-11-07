import { initializeDrawer } from "./navigation-drawer.js";

initializeDrawer({
  panel: document.querySelector("#pub-navigation"),
  toggle: document.querySelector("[data-menu-toggle]"),
  close: document.querySelector("[data-menu-close]"),
  overlay: document.querySelector("[data-menu-overlay]"),
  breakpoint: "(max-width: 900px)",
});
