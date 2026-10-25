/// <reference path="../pb_data/types.d.ts" />
// Contact & support from the apps (migration 1793100000_feedback.js): every new feedback record is mailed to Patrik
// (lib/mail.js), with Reply-To the account's email so he can answer straight from his inbox. A failed email is logged and
// the record stays (he still finds it in the admin UI); it never fails the create.

onRecordAfterCreateSuccess((e) => {
  e.next();

  const APPS = {
    empire: "Ares Empire", aresium: "Aresium", arestemis: "Arestemis", aresus: "Aresus", arestoteles: "Arestoteles",
  };
  const KINDS = { problem: "Problem", idea: "Idea", question: "Question", other: "Other" };

  const app = e.app;
  const record = e.record;
  try {
    const mail = require(`${__hooks}/lib/mail.js`);
    const account = app.findRecordById("users", record.getString("user"));
    const email = String(account.email() || "");
    const appName = APPS[record.getString("app")] || record.getString("app");
    const kind = KINDS[record.getString("kind")] || record.getString("kind");
    const message = record.getString("message");

    const text = [
      kind + " from the " + appName + " app",
      "",
      mail.line("Kind", kind),
      mail.line("App", appName),
      mail.line("Version", record.getString("app_version")),
      mail.line("System", record.getString("system")),
      mail.line("Language", record.getString("language")),
      mail.line("Account", email),
      "",
      message,
      "",
      "--",
      "Reply to this email to answer: it goes to " + (email || "the account") + ".",
      "In the admin UI: " + mail.adminLink(app, "feedback", record.id),
    ].join("\n");

    mail.sendSupport(app, "[" + appName + "] " + kind + ": " + mail.summary(message), text, email);
  } catch (err) {
    app.logger().error("feedback email failed", "feedback", record.id, "error", String(err));
  }
}, "feedback");
