'use strict';

/* Define las claves usadas para guardar los datos de demostración en el navegador. */
const STORAGE_KEYS = {
  users: 'fitpath_users_v2',
  currentUser: 'fitpath_current_user_v2'
};

/* Lee un valor guardado como JSON y devuelve un valor alternativo si no existe o está dañado. */
function readStorage(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch (error) {
    return fallback;
  }
}

/* Guarda un valor en el almacenamiento local y devuelve si la operación tuvo éxito. */
function writeStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    return false;
  }
}

/* Obtiene la lista de cuentas de prueba registradas en este navegador. */
function getUsers() {
  return readStorage(STORAGE_KEYS.users, []);
}

/* Obtiene la cuenta que inició sesión en este navegador. */
function getCurrentUser() {
  return readStorage(STORAGE_KEYS.currentUser, null);
}

/* Muestra un mensaje accesible dentro del formulario indicado. */
function showMessage(element, message, type) {
  if (!element) return;
  element.textContent = message;
  element.classList.remove('message-success', 'message-error');
  if (type) element.classList.add(type === 'success' ? 'message-success' : 'message-error');
}

/* Cambia entre el formulario de inicio de sesión y el formulario de registro. */
function setAuthMode(mode) {
  const loginForm = document.getElementById('login-form');
  const registerForm = document.getElementById('register-form');
  const loginTab = document.getElementById('tab-login');
  const registerTab = document.getElementById('tab-register');
  const title = document.getElementById('auth-title');
  const subtitle = document.getElementById('auth-subtitle');
  const isRegister = mode === 'register';

  if (!loginForm || !registerForm) return;
  loginForm.hidden = isRegister;
  registerForm.hidden = !isRegister;
  loginTab.classList.toggle('is-active', !isRegister);
  registerTab.classList.toggle('is-active', isRegister);
  loginTab.setAttribute('aria-selected', String(!isRegister));
  registerTab.setAttribute('aria-selected', String(isRegister));
  title.textContent = isRegister ? 'Empezá por vos.' : 'Qué bueno verte.';
  subtitle.textContent = isRegister ? 'Creá tu cuenta para entrar a tu espacio.' : 'Ingresá a tu espacio y seguí avanzando.';
  showMessage(document.getElementById('login-message'), '', '');
  showMessage(document.getElementById('register-message'), '', '');
}

/* Registra los eventos de los botones y formularios de acceso. */
function initializeAuthPage() {
  document.querySelectorAll('[data-auth-mode]').forEach(function (button) {
    button.addEventListener('click', function () {
      setAuthMode(button.dataset.authMode);
    });
  });

  const registerForm = document.getElementById('register-form');
  const loginForm = document.getElementById('login-form');

  registerForm.addEventListener('submit', function (event) {
    event.preventDefault();
    const name = document.getElementById('register-name').value.trim();
    const email = document.getElementById('register-email').value.trim().toLowerCase();
    const password = document.getElementById('register-password').value;
    const message = document.getElementById('register-message');

    if (name.length < 2) {
      showMessage(message, 'Ingresá tu nombre para continuar.', 'error');
      return;
    }
    if (password.length < 4) {
      showMessage(message, 'La contraseña debe tener al menos 4 caracteres.', 'error');
      return;
    }

    const users = getUsers();
    if (users.some(function (user) { return user.email === email; })) {
      showMessage(message, 'Ya existe una cuenta con ese correo. Iniciá sesión.', 'error');
      return;
    }

    const user = { name: name, email: email, password: password, goal: 'Bienestar general' };
    users.push(user);
    if (!writeStorage(STORAGE_KEYS.users, users)) {
      showMessage(message, 'No se pudieron guardar los datos en este navegador. Revisá la configuración de almacenamiento.', 'error');
      return;
    }
    writeStorage(STORAGE_KEYS.currentUser, { name: user.name, email: user.email, goal: user.goal });
    window.location.href = 'inicio.html';
  });

  loginForm.addEventListener('submit', function (event) {
    event.preventDefault();
    const email = document.getElementById('login-email').value.trim().toLowerCase();
    const password = document.getElementById('login-password').value;
    const message = document.getElementById('login-message');
    const user = getUsers().find(function (item) {
      return item.email === email && item.password === password;
    });

    if (!user) {
      showMessage(message, 'No encontramos una cuenta con esos datos. Revisá el correo y la contraseña o creá una cuenta.', 'error');
      return;
    }

    writeStorage(STORAGE_KEYS.currentUser, { name: user.name, email: user.email, goal: user.goal || 'Bienestar general' });
    window.location.href = 'inicio.html';
  });
}

/* Protege las páginas internas de la navegación accidental sin sesión y actualiza el saludo. */
function initializeAppPage() {
  const user = getCurrentUser();
  if (!user) {
    window.location.href = 'index.html';
    return;
  }

  document.querySelectorAll('[data-user-name]').forEach(function (element) {
    element.textContent = user.name;
  });
  document.querySelectorAll('[data-first-name]').forEach(function (element) {
    element.textContent = user.name.split(/\s+/)[0];
  });
  document.querySelectorAll('[data-avatar], [data-profile-avatar]').forEach(function (element) {
    element.textContent = (user.name.trim()[0] || 'U').toUpperCase();
  });
  document.querySelectorAll('[data-profile-name]').forEach(function (element) {
    element.textContent = user.name;
  });
  document.querySelectorAll('[data-profile-email]').forEach(function (element) {
    element.textContent = user.email;
  });

  initializeMenu();
  initializeLogout();
  initializeActivitySearch();
  initializeProfileForm(user);
}

/* Abre y cierra el menú lateral en pantallas pequeñas. */
function initializeMenu() {
  const sidebar = document.getElementById('sidebar');
  const toggle = document.querySelector('[data-menu-toggle]');
  const overlay = document.querySelector('[data-close-menu]');
  if (!sidebar || !toggle || !overlay) return;

  toggle.addEventListener('click', function () {
    sidebar.classList.toggle('is-open');
    overlay.classList.toggle('is-visible');
  });
  overlay.addEventListener('click', function () {
    sidebar.classList.remove('is-open');
    overlay.classList.remove('is-visible');
  });
}

/* Cierra la sesión local y devuelve al usuario a la pantalla de acceso. */
function initializeLogout() {
  document.querySelectorAll('[data-logout]').forEach(function (button) {
    button.addEventListener('click', function () {
      localStorage.removeItem(STORAGE_KEYS.currentUser);
      window.location.href = 'index.html';
    });
  });
}

/* Filtra las actividades por nombre y categoría y actualiza el contador de resultados. */
function initializeActivitySearch() {
  const searchInput = document.getElementById('activity-search');
  const typeSelect = document.getElementById('activity-type');
  const clearButton = document.getElementById('clear-filters');
  const cards = Array.from(document.querySelectorAll('.activity-card'));
  const count = document.getElementById('results-count');
  const emptyState = document.getElementById('empty-results');

  if (!searchInput || !typeSelect) return;

  function filterCards() {
    const query = searchInput.value.trim().toLocaleLowerCase('es');
    const type = typeSelect.value;
    let visible = 0;

    cards.forEach(function (card) {
      const matchesName = card.dataset.name.toLocaleLowerCase('es').includes(query);
      const matchesType = type === 'all' || card.dataset.type === type;
      const show = matchesName && matchesType;
      card.hidden = !show;
      if (show) visible += 1;
    });

    if (count) count.textContent = visible + (visible === 1 ? ' opción' : ' opciones');
    if (emptyState) emptyState.hidden = visible !== 0;
  }

  searchInput.addEventListener('input', filterCards);
  typeSelect.addEventListener('change', filterCards);
  if (clearButton) {
    clearButton.addEventListener('click', function () {
      searchInput.value = '';
      typeSelect.value = 'all';
      filterCards();
    });
  }

  document.querySelectorAll('.save-activity').forEach(function (button) {
    button.addEventListener('click', function () {
      const isSaved = button.getAttribute('aria-pressed') === 'true';
      button.setAttribute('aria-pressed', String(!isSaved));
      button.textContent = isSaved ? '♡' : '♥';
      button.classList.toggle('is-saved', !isSaved);
    });
  });
}

/* Carga los datos del perfil y permite guardar los cambios en la cuenta local. */
function initializeProfileForm(user) {
  const form = document.getElementById('profile-form');
  if (!form) return;

  const nameInput = document.getElementById('profile-name');
  const emailInput = document.getElementById('profile-email');
  const goalInput = document.getElementById('profile-goal');
  const message = document.getElementById('profile-message');

  nameInput.value = user.name || '';
  emailInput.value = user.email || '';
  goalInput.value = user.goal || 'Bienestar general';

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const newName = nameInput.value.trim();
    const newEmail = emailInput.value.trim().toLowerCase();
    const newGoal = goalInput.value;

    if (newName.length < 2) {
      showMessage(message, 'El nombre debe tener al menos 2 caracteres.', 'error');
      return;
    }

    const users = getUsers();
    const duplicate = users.some(function (item) {
      return item.email === newEmail && item.email !== user.email;
    });
    if (duplicate) {
      showMessage(message, 'Ese correo ya está asociado a otra cuenta.', 'error');
      return;
    }

    const storedUser = users.find(function (item) { return item.email === user.email; });
    if (storedUser) {
      storedUser.name = newName;
      storedUser.email = newEmail;
      storedUser.goal = newGoal;
    }

    const updatedUser = { name: newName, email: newEmail, goal: newGoal };
    if (!writeStorage(STORAGE_KEYS.users, users) || !writeStorage(STORAGE_KEYS.currentUser, updatedUser)) {
      showMessage(message, 'No se pudieron guardar los cambios en este navegador.', 'error');
      return;
    }

    showMessage(message, 'Tus cambios se guardaron correctamente.', 'success');
    document.querySelectorAll('[data-user-name], [data-profile-name]').forEach(function (element) {
      element.textContent = newName;
    });
    document.querySelectorAll('[data-profile-email]').forEach(function (element) {
      element.textContent = newEmail;
    });
    document.querySelectorAll('[data-avatar], [data-profile-avatar]').forEach(function (element) {
      element.textContent = newName[0].toUpperCase();
    });
  });
}

/* Inicializa solo las funciones correspondientes a la página HTML actual. */
document.addEventListener('DOMContentLoaded', function () {
  const page = document.body.dataset.page;
  if (page === 'auth') initializeAuthPage();
  if (page === 'app') initializeAppPage();
});
