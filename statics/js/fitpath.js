'use strict';

function showMessage(element, message, type) {
  if (!element) return;
  element.textContent = message;
  element.classList.remove('message-success', 'message-error');
  if (type) element.classList.add(type === 'success' ? 'message-success' : 'message-error');
}

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

function initializeAuthPage() {
  document.querySelectorAll('[data-auth-mode]').forEach(function (button) {
    button.addEventListener('click', function () {
      setAuthMode(button.dataset.authMode);
    });
  });

  const registerForm = document.getElementById('register-form');
  const loginForm = document.getElementById('login-form');

  registerForm.addEventListener('submit', async function (event) {
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

    try {
      const response = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password, goal: 'Bienestar general' })
      });
      const data = await response.json();

      if (!response.ok) {
        showMessage(message, data.error || 'No se pudo registrar la cuenta.', 'error');
        return;
      }

      sessionStorage.setItem('fitpath_current_user', JSON.stringify(data.user));
      window.location.href = 'inicio.html';
    } catch (err) {
      showMessage(message, 'Error de conexión con el servidor.', 'error');
    }
  });

  loginForm.addEventListener('submit', async function (event) {
    event.preventDefault();
    const email = document.getElementById('login-email').value.trim().toLowerCase();
    const password = document.getElementById('login-password').value;
    const message = document.getElementById('login-message');

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await response.json();

      if (!response.ok) {
        showMessage(message, data.error || 'Correo o contraseña incorrectos.', 'error');
        return;
      }

      sessionStorage.setItem('fitpath_current_user', JSON.stringify(data.user));
      window.location.href = 'inicio.html';
    } catch (err) {
      showMessage(message, 'Error de conexión con el servidor.', 'error');
    }
  });
}

function initializeAppPage() {
  const userJson = sessionStorage.getItem('fitpath_current_user');
  if (!userJson) {
    window.location.href = 'index.html';
    return;
  }
  const user = JSON.parse(userJson);

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

function initializeLogout() {
  document.querySelectorAll('[data-logout]').forEach(function (button) {
    button.addEventListener('click', function () {
      sessionStorage.removeItem('fitpath_current_user');
      window.location.href = 'index.html';
    });
  });
}

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

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    const newName = nameInput.value.trim();
    const newEmail = emailInput.value.trim().toLowerCase();
    const newGoal = goalInput.value;

    if (newName.length < 2) {
      showMessage(message, 'El nombre debe tener al menos 2 caracteres.', 'error');
      return;
    }

    try {
      const response = await fetch('/api/perfil', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ oldEmail: user.email, name: newName, email: newEmail, goal: newGoal })
      });
      const data = await response.json();

      if (!response.ok) {
        showMessage(message, data.error || 'No se pudieron guardar los cambios.', 'error');
        return;
      }

      sessionStorage.setItem('fitpath_current_user', JSON.stringify(data.user));
      showMessage(message, 'Tus cambios se guardaron correctamente en la base de datos.', 'success');
      
      document.querySelectorAll('[data-user-name], [data-profile-name]').forEach(element => element.textContent = newName);
      document.querySelectorAll('[data-profile-email]').forEach(element => element.textContent = newEmail);
      document.querySelectorAll('[data-avatar], [data-profile-avatar]').forEach(element => element.textContent = newName[0].toUpperCase());
    } catch (err) {
      showMessage(message, 'Error de conexión con el servidor.', 'error');
    }
  });
}

document.addEventListener('DOMContentLoaded', function () {
  const page = document.body.dataset.page;
  if (page === 'auth') initializeAuthPage();
  if (page === 'app') initializeAppPage();
});