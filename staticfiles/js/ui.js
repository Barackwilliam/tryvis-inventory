/* Dropdowns, tabs and alerts. ~2 KB in place of Bootstrap's 80 KB bundle. */
(function () {
  "use strict";

  function closeAll(except) {
    document.querySelectorAll(".dropdown-menu.show").forEach(function (menu) {
      if (menu !== except) menu.classList.remove("show");
    });
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-bs-toggle='dropdown']");
    if (trigger) {
      event.preventDefault();
      var menu = trigger.parentElement.querySelector(".dropdown-menu");
      if (menu) {
        var open = menu.classList.contains("show");
        closeAll();
        menu.classList.toggle("show", !open);
        trigger.setAttribute("aria-expanded", String(!open));
      }
      return;
    }

    var tab = event.target.closest("[data-bs-toggle='tab']");
    if (tab) {
      event.preventDefault();
      var target = document.querySelector(tab.dataset.bsTarget);
      if (target) {
        var list = tab.closest(".nav");
        if (list) {
          list.querySelectorAll(".nav-link").forEach(function (link) {
            link.classList.remove("active");
            link.setAttribute("aria-selected", "false");
          });
        }
        tab.classList.add("active");
        tab.setAttribute("aria-selected", "true");
        var panes = target.parentElement.querySelectorAll(".tab-pane");
        panes.forEach(function (pane) { pane.classList.remove("active", "show"); });
        target.classList.add("active", "show");
      }
      return;
    }

    var dismiss = event.target.closest("[data-bs-dismiss='alert']");
    if (dismiss) {
      var alertBox = dismiss.closest(".alert");
      if (alertBox) alertBox.remove();
      return;
    }

    if (!event.target.closest(".dropdown")) closeAll();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeAll();
  });
})();
