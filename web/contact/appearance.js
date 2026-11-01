/* The look of the hub's contact pages (/contact and /arestemis/contact, each also in German; webauth/contact.py):
   dark until switched with the header's button, then the last choice, remembered in this browser for both pages (the
   apps' light and dark, Settings → Appearance; the websites open dark, Patrik 2026-10-26). Loaded first in <head>, so
   the page opens in its look without a flash of the other one. The storage can be missing or blocked (private
   windows): the page is then dark and still switches, it only forgets. */
(function () {
  "use strict";
  var KEY = "ares-empire-appearance";
  var root = document.documentElement;

  // "light" or "dark"; anything else, or no storage, is dark.
  function load() {
    try { return window.localStorage.getItem(KEY) === "light" ? "light" : "dark"; } catch (e) { return "dark"; }
  }

  function save(look) {
    try {
      if (look === "light") window.localStorage.setItem(KEY, "light");
      else window.localStorage.removeItem(KEY);
    } catch (e) { /* not remembered; the page still switches */ }
  }

  root.setAttribute("data-theme", load());

  // The header's button ([data-look-switch], hidden until here: without this script it would do nothing) is pressed
  // while the page is light; its icon follows the look (the stylesheet).
  function wire() {
    var button = document.querySelector("[data-look-switch]");
    if (!button) return;
    var show = function () {
      button.setAttribute("aria-pressed", root.getAttribute("data-theme") === "light" ? "true" : "false");
    };
    show();
    button.hidden = false;
    button.addEventListener("click", function () {
      var look = root.getAttribute("data-theme") === "light" ? "dark" : "light";
      root.setAttribute("data-theme", look);
      save(look);
      show();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();

  window.EmpireAppearance = { load: load, save: save };
})();
