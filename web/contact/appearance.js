/* The look of the hub's contact pages (/contact and /arestemis/contact, each also in German; webauth/contact.py):
   dark until switched with the header's button, then the last choice, remembered in this browser for both pages (the
   apps' light and dark, Settings → Appearance; the websites open dark, Patrik 2026-10-26). Loaded first in <head>, so
   the page opens in its look without a flash of the other one. The storage can be missing or blocked (private
   windows): the page is then dark and still switches, it only forgets.
   A page that links here can pass its own look for the visit, ?look=light or ?look=dark (patrikbreeck.com's apps page
   does, so the form opens in the look the visitor came from): it wins over the remembered one, is not remembered
   itself, and stays in the address and the language link (contact-form.js keeps the page's parameters). */
(function () {
  "use strict";
  var KEY = "ares-empire-appearance";
  var root = document.documentElement;

  // The look passed in the address, or null.
  function passed() {
    var look = /[?&]look=(light|dark)(&|$)/.exec((window.location && window.location.search) || "");
    return look ? look[1] : null;
  }

  // "light" or "dark": the passed look, else the remembered one; anything else, or no storage, is dark.
  function load() {
    if (passed()) return passed();
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
      if (passed()) carry(look);
      show();
    });
  }

  // Switched on a page that was given a look: the address and the language link now pass the new one.
  function carry(look) {
    var url = new URL(window.location.href);
    url.searchParams.set("look", look);
    window.history.replaceState(null, "", url.pathname + url.search);
    var other = document.querySelector("[data-language-link]");
    if (other) {
      var link = new URL(other.href, window.location.href);
      link.searchParams.set("look", look);
      other.href = link.pathname + link.search;
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();

  window.EmpireAppearance = { load: load, save: save };
})();
