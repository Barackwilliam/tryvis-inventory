/* TRYVIS INVENTORY — shell behaviour. No framework, no build step. */
(function () {
  "use strict";

  var app = document.getElementById("app");
  if (!app) return;

  /* ---------------------------------------------------------- theme ---- */
  var THEME_KEY = "tryvis-theme";

  function applyTheme(choice) {
    var resolved = choice;
    if (choice === "system" || !choice) {
      resolved = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    document.documentElement.setAttribute("data-theme", resolved);
    document.querySelectorAll("[data-theme-choice]").forEach(function (el) {
      el.classList.toggle("active", el.dataset.themeChoice === (choice || "system"));
    });
  }

  try { applyTheme(localStorage.getItem(THEME_KEY) || "system"); } catch (e) { applyTheme("light"); }

  document.querySelectorAll("[data-theme-choice]").forEach(function (el) {
    el.addEventListener("click", function (event) {
      event.preventDefault();
      var choice = el.dataset.themeChoice;
      try { localStorage.setItem(THEME_KEY, choice); } catch (e) {}
      applyTheme(choice);
    });
  });

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
    var stored = null;
    try { stored = localStorage.getItem(THEME_KEY); } catch (e) {}
    if (!stored || stored === "system") applyTheme("system");
  });

  /* -------------------------------------------------------- sidebar ---- */
  var COLLAPSE_KEY = "tryvis-sidebar-collapsed";
  try {
    if (localStorage.getItem(COLLAPSE_KEY) === "1") app.classList.add("is-collapsed");
  } catch (e) {}

  function isMobile() { return window.matchMedia("(max-width: 991.98px)").matches; }

  var toggle = document.getElementById("sidebarToggle");

  function closeDrawer() {
    app.classList.remove("is-drawer-open");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      if (isMobile()) {
        var open = app.classList.toggle("is-drawer-open");
        toggle.setAttribute("aria-expanded", String(open));
      } else {
        app.classList.toggle("is-collapsed");
        try {
          localStorage.setItem(COLLAPSE_KEY, app.classList.contains("is-collapsed") ? "1" : "0");
        } catch (e) {}
      }
    });
  }

  var drawerClose = document.getElementById("drawerClose");
  if (drawerClose) drawerClose.addEventListener("click", closeDrawer);

  // Escape closes the drawer; resizing back to desktop clears the state.
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && app.classList.contains("is-drawer-open")) closeDrawer();
  });
  window.addEventListener("resize", function () {
    if (!isMobile()) closeDrawer();
  });

  document.querySelectorAll(".sidebar__nav a").forEach(function (link) {
    link.addEventListener("click", function () {
      if (isMobile()) closeDrawer();
    });
  });

  var scrim = document.getElementById("scrim");
  if (scrim) scrim.addEventListener("click", closeDrawer);

  /* --------------------------------------------------------- search ---- */
  var input = document.getElementById("globalSearch");
  var panel = document.getElementById("searchResults");

  if (input && panel) {
    var timer = null;
    var cursor = -1;

    function hits() { return panel.querySelectorAll(".search__hit"); }

    function close() { panel.classList.remove("is-open"); cursor = -1; }

    function run(term) {
      fetch(panel.dataset.url + "?q=" + encodeURIComponent(term), {
        headers: { "X-Requested-With": "XMLHttpRequest" }
      })
        .then(function (response) {
          if (!response.ok) throw new Error(response.status);
          return response.json();
        })
        .then(function (data) { render(data, term); })
        .catch(function () {
          panel.innerHTML = '<div class="search__empty">Search is not available right now.</div>';
          panel.classList.add("is-open");
        });
    }

    function safe(text) {
      // Item and customer names are typed by people. They go into the page as
      // text, never as markup.
      return String(text == null ? "" : text)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

    function render(data, term) {
      var html = "";
      (data.groups || []).forEach(function (group) {
        if (!group.items.length) return;
        html += '<div class="search__group">' + safe(group.label) + "</div>";
        group.items.forEach(function (row) {
          html += '<a class="search__hit" href="' + safe(row.url) + '">' +
            "<span>" + safe(row.title) + "</span>" +
            (row.meta ? "<small>" + safe(row.meta) + "</small>" : "") + "</a>";
        });
      });
      if (!html) {
        html = '<div class="search__empty">Nothing found for &ldquo;' +
          safe(term) + "&rdquo;</div>";
      }
      panel.innerHTML = html;
      panel.classList.add("is-open");
      cursor = -1;
    }

    input.addEventListener("input", function () {
      var term = input.value.trim();
      clearTimeout(timer);
      if (term.length < 2) { close(); return; }
      timer = setTimeout(function () { run(term); }, 180);
    });

    input.addEventListener("keydown", function (event) {
      var rows = hits();
      if (event.key === "Escape") { close(); input.blur(); return; }
      if (!rows.length) return;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        cursor += event.key === "ArrowDown" ? 1 : -1;
        if (cursor < 0) cursor = rows.length - 1;
        if (cursor >= rows.length) cursor = 0;
        rows.forEach(function (row, index) { row.classList.toggle("is-cursor", index === cursor); });
        rows[cursor].scrollIntoView({ block: "nearest" });
      } else if (event.key === "Enter" && cursor > -1) {
        event.preventDefault();
        window.location.href = rows[cursor].getAttribute("href");
      }
    });

    document.addEventListener("click", function (event) {
      if (!panel.contains(event.target) && event.target !== input) close();
    });

    document.addEventListener("keydown", function (event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        input.focus();
        input.select();
      }
    });
  }

  /* --------------------------------------------------------- toasts ---- */
  document.querySelectorAll(".toast-x").forEach(function (toast) {
    var close = toast.querySelector("button");
    if (close) close.addEventListener("click", function () { toast.remove(); });
    setTimeout(function () {
      toast.style.transition = "opacity .25s, transform .25s";
      toast.style.opacity = "0";
      toast.style.transform = "translateY(6px)";
      setTimeout(function () { toast.remove(); }, 260);
    }, 6000);
  });

  /* ------------------------------------------- confirm dangerous acts -- */
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (event) {
      if (!window.confirm(el.dataset.confirm)) event.preventDefault();
    });
  });
})();
