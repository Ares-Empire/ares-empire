/// <reference path="../pb_data/types.d.ts" />
// Send email through Resend (domain ares-empire.de). The SMTP password is the Resend API key:
// it is entered only in the admin UI (Settings → Mail settings) and is never in git.

migrate((app) => {
  const settings = app.settings();
  settings.smtp.enabled = true;
  settings.smtp.host = "smtp.resend.com";
  settings.smtp.port = 465;
  settings.smtp.tls = true;
  settings.smtp.username = "resend";
  app.save(settings);
}, (app) => {
  const settings = app.settings();
  settings.smtp.enabled = false;
  app.save(settings);
});
