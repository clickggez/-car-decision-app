/**
 * CarDSS — Main JavaScript
 * Dark mode toggle, form validation, navbar toggle, animations, utilities
 */

// ============================================================
// DARK MODE TOGGLE (DESIGN.md Section 9)
// - data-theme="dark" on <html>
// - localStorage key: "theme"
// - Respects prefers-color-scheme if no stored preference
// ============================================================
(function () {
  var html = document.documentElement;
  var toggle = document.getElementById('themeToggle');
  var stored = localStorage.getItem('theme');

  // Apply saved theme or respect OS preference
  if (stored) {
    html.setAttribute('data-theme', stored);
  } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    html.setAttribute('data-theme', 'dark');
  }

  function updateIcon() {
    if (!toggle) return;
    var icon = toggle.querySelector('i');
    if (html.getAttribute('data-theme') === 'dark') {
      icon.className = 'bi bi-sun-fill';
      toggle.title = 'สลับเป็นธีมสว่าง';
    } else {
      icon.className = 'bi bi-moon-fill';
      toggle.title = 'สลับเป็นธีมดำ';
    }
  }

  updateIcon();

  if (toggle) {
    toggle.addEventListener('click', function () {
      var current = html.getAttribute('data-theme');
      var next = current === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
      updateIcon();
      // แจ้งให้ส่วนที่วาดเองอย่าง Chart.js รู้ว่าธีมเปลี่ยน
      // (Chart อ่านค่าสีจาก CSS variable ตอนสร้างครั้งเดียว ไม่อัปเดตเอง)
      document.dispatchEvent(new CustomEvent('cardss:themechange', { detail: { theme: next } }));
    });
  }
})();

// ============================================================
// RE-SYNC THEME ON BFCACHE RESTORE (browser back/forward)
// ============================================================
window.addEventListener('pageshow', function (e) {
  if (!e.persisted) return;
  var html = document.documentElement;
  var stored = localStorage.getItem('theme');
  if (stored) {
    html.setAttribute('data-theme', stored);
  } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    html.setAttribute('data-theme', 'dark');
  } else {
    html.removeAttribute('data-theme');
  }
  var toggle = document.getElementById('themeToggle');
  if (toggle) {
    var icon = toggle.querySelector('i');
    if (html.getAttribute('data-theme') === 'dark') {
      icon.className = 'bi bi-sun-fill';
    } else {
      icon.className = 'bi bi-moon-fill';
    }
  }
  document.dispatchEvent(new CustomEvent('cardss:themechange', {
    detail: { theme: html.getAttribute('data-theme') || 'light' }
  }));
});

// ============================================================
// NAVBAR MOBILE TOGGLE
// ============================================================
(function () {
  var toggle = document.getElementById('navToggle');
  var nav = document.getElementById('mainNav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      nav.classList.toggle('open');
      var icon = toggle.querySelector('i');
      if (nav.classList.contains('open')) {
        icon.className = 'bi bi-x-lg';
      } else {
        icon.className = 'bi bi-list';
      }
    });

    // Close when clicking a nav link (mobile)
    nav.querySelectorAll('.nav-link').forEach(function (link) {
      link.addEventListener('click', function () {
        nav.classList.remove('open');
        var icon = toggle.querySelector('i');
        icon.className = 'bi bi-list';
      });
    });
  }
})();

// ============================================================
// TOGGLE PASSWORD VISIBILITY
// ============================================================
function togglePassword(inputId, btn) {
  var input = document.getElementById(inputId);
  if (!input) return;
  var icon = btn.querySelector('i');
  if (input.type === 'password') {
    input.type = 'text';
    icon.className = 'bi bi-eye-slash';
  } else {
    input.type = 'password';
    icon.className = 'bi bi-eye';
  }
}

// ============================================================
// LOGIN FORM VALIDATION
// ============================================================
(function () {
  var form = document.getElementById('loginForm');
  if (!form) return;

  form.addEventListener('submit', function (e) {
    var valid = true;

    var username = document.getElementById('username');
    var usernameErr = document.getElementById('username-err');
    if (!username.value.trim()) {
      usernameErr.textContent = 'กรุณากรอกชื่อผู้ใช้';
      usernameErr.style.display = 'block';
      username.style.borderColor = 'var(--brand-primary)';
      valid = false;
    } else {
      usernameErr.style.display = 'none';
      username.style.borderColor = '';
    }

    var password = document.getElementById('password');
    var passwordErr = document.getElementById('password-err');
    if (!password.value) {
      passwordErr.textContent = 'กรุณากรอกรหัสผ่าน';
      passwordErr.style.display = 'block';
      password.style.borderColor = 'var(--brand-primary)';
      valid = false;
    } else {
      passwordErr.style.display = 'none';
      password.style.borderColor = '';
    }

    if (!valid) e.preventDefault();
  });

  // Clear errors on input
  ['username', 'password'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', function () {
        this.style.borderColor = '';
        var errEl = document.getElementById(id + '-err');
        if (errEl) errEl.style.display = 'none';
      });
    }
  });
})();

// ============================================================
// ANIMATE ELEMENTS ON SCROLL (Intersection Observer)
// ============================================================
(function () {
  if (!('IntersectionObserver' in window)) return;

  var elements = document.querySelectorAll('.fade-in');
  if (elements.length === 0) return;

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '';
        entry.target.style.transform = '';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  elements.forEach(function (el) {
    observer.observe(el);
  });
})();

// ============================================================
// AUTO-DISMISS FLASH MESSAGES
// ============================================================
(function () {
  var alerts = document.querySelectorAll('.alert-cardss');
  alerts.forEach(function (alert) {
    // Only auto-dismiss error/success in flash container
    if (!alert.closest('#flash-container')) return;
    setTimeout(function () {
      alert.style.transition = 'opacity 0.4s, transform 0.4s';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-8px)';
      setTimeout(function () { alert.remove(); }, 400);
    }, 6000);
  });
})();

// ============================================================
// SMOOTH SCROLL TO TOP ON FORM ERROR
// ============================================================
function scrollToFirstError() {
  var firstErr = document.querySelector('[style*="border-color: var(--brand-primary)"]');
  if (firstErr) {
    firstErr.scrollIntoView({ behavior: 'smooth', block: 'center' });
    firstErr.focus();
  }
}
