/// <reference path="../pb_data/types.d.ts" />
// Contact & support from the apps (migration 1793100000_feedback.js): every new feedback record is mailed to Patrik,
// with Reply-To the account's email so he can answer straight from his inbox. A failed email is logged and the record
// stays (he still finds it in the admin UI); it never fails the create.

onRecordAfterCreateSuccess((e) => {
  e.next();

  // Where support messages go: the one place to change it. (PocketBase runs each handler in its own scope, so the
  // handler cannot see names declared outside it; this is the top of the only handler in this file.)
  const TO = "REDACTED-EMAIL";
  const APPS = {
    empire: "Ares Empire", aresium: "Aresium", arestemis: "Arestemis", aresus: "Aresus", arestoteles: "Arestoteles",
  };
  const KINDS = { problem: "Problem", idea: "Idea", question: "Question", other: "Other" };

  const app = e.app;
  const record = e.record;
  try {
    const meta = app.settings().meta;
    const account = app.findRecordById("users", record.getString("user"));
    const email = String(account.email() || "");
    const appName = APPS[record.getString("app")] || record.getString("app");
    const kind = KINDS[record.getString("kind")] || record.getString("kind");
    const message = record.getString("message");

    // The subject's summary: the message's first words on one line (whole words, at most 60 characters).
    const flat = message.replace(/\s+/g, " ").trim();
    let summary = "";
    for (const word of flat.split(" ")) {
      const longer = summary ? summary + " " + word : word;
      if (longer.length > 60) break;
      summary = longer;
    }
    if (!summary) summary = flat.slice(0, 60);          // one very long word
    if (summary.length < flat.length) summary += "…";

    const line = (label, value) => (label + ":").padEnd(10) + (value || "–");
    const text = [
      kind + " from the " + appName + " app",
      "",
      line("Kind", kind),
      line("App", appName),
      line("Version", record.getString("app_version")),
      line("System", record.getString("system")),
      line("Language", record.getString("language")),
      line("Account", email),
      "",
      message,
      "",
      "--",
      "Reply to this email to answer: it goes to " + (email || "the account") + ".",
      "In the admin UI: " + meta.appURL + "/_/#/collections?collection=feedback&recordId=" + record.id,
    ].join("\n");

    const mail = {
      from: { address: meta.senderAddress, name: meta.senderName },
      to: [{ address: TO }],
      subject: "[" + appName + "] " + kind + ": " + summary,
      text: text,
    };
    if (email) mail.headers = { "Reply-To": email };
    app.newMailClient().send(new MailerMessage(mail));
  } catch (err) {
    app.logger().error("feedback email failed", "feedback", record.id, "error", String(err));
  }
}, "feedback");
