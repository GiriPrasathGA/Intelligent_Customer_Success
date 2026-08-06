/**
 * NovaCart AI — Shared Application Utilities (app.js)
 * Auth state management, API client, routing, toast notifications
 */

const API_BASE = (typeof window !== 'undefined' && window.location.protocol.startsWith('http'))
  ? window.location.origin
  : 'http://localhost:8000';

// ── Auth State ──────────────────────────────────────────────────────────────

const Auth = {
  getToken() {
    return localStorage.getItem('novacart_token') || sessionStorage.getItem('novacart_token');
  },

  setToken(token, persistent = false) {
    localStorage.removeItem('novacart_token');
    sessionStorage.removeItem('novacart_token');
    if (persistent) {
      localStorage.setItem('novacart_token', token);
    } else {
      sessionStorage.setItem('novacart_token', token);
    }
  },

  getUser() {
    try {
      const raw = localStorage.getItem('novacart_user') || sessionStorage.getItem('novacart_user');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },

  setUser(user) {
    const storage = localStorage.getItem('novacart_token') ? localStorage : sessionStorage;
    storage.setItem('novacart_user', JSON.stringify(user));
  },

  logout() {
    localStorage.removeItem('novacart_token');
    localStorage.removeItem('novacart_user');
    sessionStorage.removeItem('novacart_token');
    sessionStorage.removeItem('novacart_user');
    const path = window.location.pathname;
    const isIndex = path === '/' || path.endsWith('/index.html') || path === '';
    if (!isIndex) {
      window.location.href = 'index.html';
    } else {
      this.ensureGuestSession();
    }
  },

  isAuthenticated() {
    return !!this.getToken();
  },

  /** No longer redirects — always returns true. Call ensureGuestSession() on page load. */
  requireAuth() {
    return true;
  },

  redirectIfAuthenticated() {
    return false;
  },

  /** Auto-create a guest session if no token exists. */
  async ensureGuestSession(forceRefresh = false) {
    if (!forceRefresh && this.isAuthenticated()) return;
    try {
      localStorage.removeItem('novacart_token');
      sessionStorage.removeItem('novacart_token');
      localStorage.removeItem('novacart_user');
      sessionStorage.removeItem('novacart_user');
      const res = await fetch(`${API_BASE}/api/auth/guest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error('Guest login failed');
      const data = await res.json();
      this.setToken(data.access_token, true);
      this.setUser(data.user);
    } catch (err) {
      console.error('Failed to create guest session:', err);
      const fallbackUser = { id: 'guest', name: 'Guest User', email: 'guest@novacart.ai', is_guest: true };
      sessionStorage.setItem('novacart_user', JSON.stringify(fallbackUser));
    }
  },
};

// ── API Client ──────────────────────────────────────────────────────────────

const API = {
  async request(method, path, body = null, requireAuth = true) {
    if (requireAuth && !Auth.getToken()) {
      await Auth.ensureGuestSession();
    }

    const headers = { 'Content-Type': 'application/json' };

    let token = Auth.getToken();
    if (requireAuth && token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    let res = await fetch(`${API_BASE}${path}`, options);

    if (res.status === 401 && requireAuth) {
      // Clear token and auto-renew guest session once
      await Auth.ensureGuestSession(true);
      token = Auth.getToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
        res = await fetch(`${API_BASE}${path}`, { method, headers, body: body ? JSON.stringify(body) : null });
      }
    }

    if (!res.ok) {
      let detail = 'Request failed';
      try {
        const err = await res.json();
        detail = err.detail || JSON.stringify(err);
      } catch {}
      throw new Error(detail);
    }

    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) return res.json();
    return res;
  },

  get(path, requireAuth = true) {
    return this.request('GET', path, null, requireAuth);
  },

  post(path, body, requireAuth = true) {
    return this.request('POST', path, body, requireAuth);
  },

  patch(path, body, requireAuth = true) {
    return this.request('PATCH', path, body, requireAuth);
  },

  delete(path, requireAuth = true) {
    return this.request('DELETE', path, null, requireAuth);
  },
};

// ── Toast Notifications ─────────────────────────────────────────────────────

const Toast = {
  container: null,

  init() {
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
  },

  show(message, type = 'info', duration = 4000) {
    this.init();

    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    const colors = {
      success: '#10b981',
      error:   '#ef4444',
      warning: '#f59e0b',
      info:    '#6C63FF',
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <div style="width:20px;height:20px;border-radius:50%;background:${colors[type] || colors.info};
        display:flex;align-items:center;justify-content:center;color:white;font-size:0.7rem;
        font-weight:700;flex-shrink:0">${icons[type] || icons.info}</div>
      <span style="flex:1;font-size:0.875rem;color:var(--text-primary)">${message}</span>
      <button onclick="this.closest('.toast').remove()"
        style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1rem;padding:0;line-height:1">×</button>
    `;

    this.container.appendChild(toast);

    if (duration > 0) {
      setTimeout(() => {
        toast.style.animation = 'slide-out 300ms ease forwards';
        setTimeout(() => toast.remove(), 300);
      }, duration);
    }

    return toast;
  },

  success(msg, duration) { return this.show(msg, 'success', duration); },
  error(msg, duration)   { return this.show(msg, 'error', duration); },
  warning(msg, duration) { return this.show(msg, 'warning', duration); },
  info(msg, duration)    { return this.show(msg, 'info', duration); },
};

// ── Avatar Initials Helper ───────────────────────────────────────────────────

function getInitials(name = '') {
  return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase() || 'U';
}

// ── Format Date ──────────────────────────────────────────────────────────────

function formatDate(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatTime(isoString) {
  const d = isoString ? new Date(isoString) : new Date();
  let hours = d.getHours();
  const minutes = d.getMinutes().toString().padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12;
  hours = hours ? hours : 12;
  const strHours = hours.toString().padStart(2, '0');
  return `${strHours}:${minutes} ${ampm}`;
}

function formatRelative(isoString) {
  if (!isoString) return '';
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return formatDate(isoString);
}

// ── Debounce ─────────────────────────────────────────────────────────────────

function debounce(fn, ms = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// ── Copy to Clipboard ────────────────────────────────────────────────────────

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    return true;
  }
}

// ── Auto-resize Textarea ─────────────────────────────────────────────────────

function autoResizeTextarea(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

// ── CSS slide-out keyframe (injected dynamically) ────────────────────────────
(function injectStyles() {
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slide-out {
      from { transform: translateX(0); opacity: 1; }
      to   { transform: translateX(110%); opacity: 0; }
    }
  `;
  document.head.appendChild(style);
})();

// Export for module-less HTML pages
window.Auth = Auth;
window.API = API;
window.Toast = Toast;
window.getInitials = getInitials;
window.formatDate = formatDate;
window.formatTime = formatTime;
window.formatRelative = formatRelative;
window.debounce = debounce;
window.copyToClipboard = copyToClipboard;
window.autoResizeTextarea = autoResizeTextarea;
