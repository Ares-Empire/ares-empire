/// <reference path="../pb_data/types.d.ts" />
// Emails around sign-up. PocketBase runs each handler in its own scope, so every handler
// is self-contained (no shared helpers at file level).

// Someone signed up through the website → ask the superusers (Patrik) to approve.
onRecordCreateRequest((e) => {
  e.next(); // saves the record; throws on validation errors, so nothing below runs then
  if (e.hasSuperuserAuth()) return; // created by hand in the admin UI

  const app = e.app;
  const meta = app.settings().meta;
  const to = app.findAllRecords("_superusers")
    .map((r) => r.email())
    .filter((m) => m && !m.endsWith("@example.com"))
    .map((m) => ({ address: m }));
  if (to.length === 0) return;

  const email = String(e.record.email()).replace(/[<>&"]/g, "");
  const link = meta.appURL + "/_/#/collections?collection=users&recordId=" + e.record.id;
  try {
    app.newMailClient().send(new MailerMessage({
      from: { address: meta.senderAddress, name: meta.senderName },
      to: to,
      subject: "Approve new Ares Empire account: " + email,
      html: "<p><b>" + email + "</b> created an Ares Empire account.</p>" +
        "<p>To let them in, open <a href=\"" + link + "\">their account</a>, switch on <b>approved</b>, " +
        "pick the <b>services</b> they may use and save. They get an email when you do.</p>" +
        "<p>To decline, delete the account there.</p>",
    }));
  } catch (err) {
    app.logger().error("approval request email failed", "error", String(err));
  }
}, "users");

// A superuser switched `approved` on → tell the person they can log in now.
onRecordUpdateRequest((e) => {
  const wasApproved = e.record.original().getBool("approved");
  e.next();
  if (wasApproved || !e.record.getBool("approved")) return;

  const app = e.app;
  const meta = app.settings().meta;
  try {
    app.newMailClient().send(new MailerMessage({
      from: { address: meta.senderAddress, name: meta.senderName },
      to: [{ address: e.record.email() }],
      subject: "Your Ares Empire account is ready",
      html: "<p>Your Ares Empire account was approved. You can log in now:</p>" +
        "<p><a href=\"https://www.ares-empire.de/login\">www.ares-empire.de</a></p>",
    }));
  } catch (err) {
    app.logger().error("approved email failed", "error", String(err));
  }
}, "users");
