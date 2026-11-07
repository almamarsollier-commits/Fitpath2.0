import { initializeDrawer } from "./navigation-drawer.js";
import { clienteDemo } from "../data/cliente-demo.js";

const routes = {
  inicio: "/templates/cliente/inicio/resumen.html",
  actividad: "/templates/cliente/inicio/actividad.html",
  proximaClase: "/templates/cliente/inicio/proxima-clase.html",
  clases: "/templates/cliente/clases/index.html",
  detalleClase: "/templates/cliente/clases/detalle.html",
  reservas: "/templates/cliente/clases/reservas.html",
  rutina: "/templates/cliente/rutina/semana.html",
  entrenamiento: "/templates/cliente/rutina/entrenamiento.html",
  ejercicio: "/templates/cliente/rutina/ejercicio.html",
  progreso: "/templates/cliente/progreso/index.html",
  evolucion: "/templates/cliente/progreso/evolucion.html",
  perfil: "/templates/cliente/perfil/index.html",
  membresia: "/templates/cliente/perfil/membresia.html"
};

const sections = [
  { key: "inicio", label: "Inicio", href: routes.inicio, icon: "home" },
  { key: "clases", label: "Clases y reservas", href: routes.clases, icon: "calendar" },
  { key: "rutina", label: "Mi rutina", href: routes.rutina, icon: "routine" },
  { key: "progreso", label: "Progreso", href: routes.progreso, icon: "progress" },
  { key: "perfil", label: "Mi perfil", href: routes.perfil, icon: "profile" }
];

const viewMap = {
  "inicio-resumen": { section: "inicio", title: "Inicio", crumbs: [] },
  "inicio-actividad": { section: "inicio", title: "Resumen de actividad", crumbs: [{ label: "Inicio", href: routes.inicio }] },
  "inicio-proxima-clase": { section: "inicio", title: "Detalle de próxima clase", crumbs: [{ label: "Inicio", href: routes.inicio }] },
  "clases-listado": { section: "clases", title: "Explorar clases", crumbs: [] },
  "clases-detalle": { section: "clases", title: "Detalle de clase", crumbs: [{ label: "Clases", href: routes.clases }] },
  "clases-reservas": { section: "clases", title: "Mis reservas", crumbs: [{ label: "Clases", href: routes.clases }] },
  "rutina-semana": { section: "rutina", title: "Rutina semanal", crumbs: [] },
  "rutina-entrenamiento": { section: "rutina", title: "Entrenamiento del lunes", crumbs: [{ label: "Mi rutina", href: routes.rutina }] },
  "rutina-ejercicio": { section: "rutina", title: "Detalle del ejercicio", crumbs: [{ label: "Mi rutina", href: routes.rutina }, { label: "Entrenamiento del lunes", href: routes.entrenamiento }] },
  "progreso-inicio": { section: "progreso", title: "Progreso", crumbs: [] },
  "progreso-evolucion": { section: "progreso", title: "Evolución y objetivos", crumbs: [{ label: "Progreso", href: routes.progreso }] },
  "perfil-inicio": { section: "perfil", title: "Mi perfil", crumbs: [] },
  "perfil-membresia": { section: "perfil", title: "Detalle de membresía", crumbs: [{ label: "Mi perfil", href: routes.perfil }] }
};

const iconPaths = {
  close: ["m6 6 12 12", "M18 6 6 18"],
  home: ["M3 10.8 12 3l9 7.8", "M5.5 9.5V21h13V9.5", "M9 21v-7h6v7"],
  calendar: ["M4 5h16v16H4z", "M8 3v4", "M16 3v4", "M4 10h16"],
  routine: ["M4 9v6", "M8 5v14", "M16 5v14", "M20 9v6", "M8 12h8"],
  progress: ["M4 19V5", "M4 19h16", "m7 15 4-4 3 2 5-6", "M16 7h3v3"],
  profile: ["M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z", "M4 21a8 8 0 0 1 16 0"]
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function makeIcon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  for (const d of iconPaths[name] ?? []) {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}

function renderSidebar(activeSection) {
  const sidebar = document.querySelector("#fp-sidebar");
  if (!sidebar) return;

  const brandRow = element("div", "fp-sidebar-brand");
  const brand = element("a", "fp-brand");
  brand.href = routes.inicio;
  brand.setAttribute("aria-label", "FitPath 2.0, ir al inicio del espacio Cliente");
  brand.append(element("span", "fp-brand-mark", "F"));
  const word = element("span", "fp-brand-word");
  word.append(document.createTextNode("FIT"), element("span", "", "PATH"));
  brand.append(word, element("span", "fp-brand-version", "2.0"));
  brandRow.append(brand);

  const close = element("button", "fp-icon-button fp-sidebar-close");
  close.type = "button";
  close.setAttribute("aria-label", "Cerrar menú");
  close.dataset.menuClose = "";
  close.append(makeIcon("close"));
  brandRow.append(close);

  const user = element("div", "fp-client-side-heading");
  user.append(element("span", "fp-client-avatar", clienteDemo.profile.initials));
  const userText = element("span");
  userText.append(element("strong", "", "Espacio Cliente"), element("small", "", "Perfil ficticio"));
  user.append(userText);

  const nav = element("nav", "fp-primary-nav fp-client-nav");
  nav.setAttribute("aria-label", "Secciones de mi espacio");
  nav.append(element("p", "fp-nav-heading", "MI ESPACIO"));
  for (const section of sections) {
    const link = element("a", "fp-nav-link");
    link.href = section.href;
    link.append(makeIcon(section.icon), element("span", "", section.label));
    if (section.key === activeSection) {
      link.classList.add("is-current");
      link.setAttribute("aria-current", "page");
    }
    nav.append(link);
  }

  const bottom = element("div", "fp-sidebar-bottom");
  const tip = element("div", "fp-client-side-tip");
  tip.append(element("span", "", "✳"), element("p", "", "Un paso a la vez. Tu constancia también cuenta."));
  bottom.append(tip);
  const version = element("p", "fp-sidebar-version", "FITPATH 2.0 · DEMO CLIENTE");
  bottom.append(version);
  sidebar.replaceChildren(brandRow, user, nav, bottom);
}

function renderBreadcrumbs(view) {
  const nav = document.querySelector("#client-breadcrumb-mount");
  if (!nav) return;
  const parts = [...view.crumbs, { label: view.title, current: true }];
  parts.forEach((part, index) => {
    if (index) nav.append(element("span", "fp-breadcrumb-divider", "/"));
    if (part.current) {
      const current = element("strong", "", part.label);
      current.setAttribute("aria-current", "page");
      nav.append(current);
    } else {
      const link = element("a", "", part.label);
      link.href = part.href;
      nav.append(link);
    }
  });
}

function getDemoValue(key, query) {
  if (key === "exercise.name" || key.startsWith("exercise.")) {
    const slug = query.get("ejercicio") || "press-mancuernas";
    return clienteDemo.exercises[slug]?.[key.slice("exercise.".length)];
  }
  return key.split(".").reduce((value, part) => value?.[part], clienteDemo);
}

function hydrateDemoContent() {
  const query = new URLSearchParams(window.location.search);
  document.querySelectorAll("[data-demo-text]").forEach((node) => {
    const value = getDemoValue(node.dataset.demoText, query);
    if (typeof value === "string") node.textContent = value;
  });
}

const view = viewMap[document.body.dataset.clientView] ?? viewMap["inicio-resumen"];
renderSidebar(view.section);
renderBreadcrumbs(view);
hydrateDemoContent();

initializeDrawer({
  panel: document.querySelector("#fp-sidebar"),
  toggle: document.querySelector("[data-menu-toggle]"),
  close: document.querySelector("[data-menu-close]"),
  overlay: document.querySelector("[data-menu-overlay]")
});
