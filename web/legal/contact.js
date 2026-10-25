// The contact form on /kontakt and /contact (web/legal/kontakt.html, contact.html), inlined by webauth/legal.py.
// It sends the message to the account server's open `contact` collection (docs/ACCOUNTS.md: Website contact form) and
// shows sending, sent and the problems. The words are in the page, so one script serves both languages.
(function () {
  "use strict";
  var form = document.getElementById("contact-form");
  var sent = document.getElementById("contact-sent");
  if (!form || !sent || !window.fetch) return;   // without it the form posts plainly (and noscript says so)
  var button = form.querySelector("button[type=submit]");
  var label = button.textContent;
  var problems = form.querySelectorAll("[data-problem]");

  function field(name) { return form.elements.namedItem(name); }

  // Shows the problem with this name (empty, email, many, failed), or none.
  function show(name) {
    for (var i = 0; i < problems.length; i++) problems[i].hidden = problems[i].getAttribute("data-problem") !== name;
  }

  function busy(on) {
    form.setAttribute("aria-busy", on ? "true" : "false");
    button.disabled = on;
    button.textContent = on ? button.getAttribute("data-sending") : label;
    ["name", "email", "message"].forEach(function (name) { field(name).readOnly = on; });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var message = field("message").value.trim();
    if (!message) { show("empty"); field("message").focus(); return; }
    show(null);
    busy(true);
    fetch(form.action, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: field("name").value.trim(),
        email: field("email").value.trim(),
        message: message,
        website: field("website").value,
        language: document.documentElement.lang === "de" ? "de" : "en"
      })
    }).then(function (response) {
      if (response.ok) {
        form.hidden = true;
        sent.hidden = false;
        sent.focus();
        return;
      }
      return response.json().catch(function () { return {}; }).then(function (answer) {
        var invalid = (answer && answer.data) || {};
        busy(false);
        if (response.status === 429) {
          show("many");
        } else if (response.status === 400 && invalid.email) {
          show("email");
          field("email").focus();
        } else if (response.status === 400 && invalid.message) {
          show("empty");
          field("message").focus();
        } else {
          show("failed");
        }
      });
    }).catch(function () {
      busy(false);
      show("failed");
    });
  });
})();
