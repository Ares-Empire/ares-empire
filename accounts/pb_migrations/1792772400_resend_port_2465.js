/// <reference path="../pb_data/types.d.ts" />
// The hosting provider blocks outgoing ports 25/465/587 (tested 2026-10-23), so use Resend's
// alternative TLS port 2465.

migrate((app) => {
  const settings = app.settings();
  settings.smtp.port = 2465;
  settings.smtp.tls = true;
  app.save(settings);
}, (app) => {
  const settings = app.settings();
  settings.smtp.port = 465;
  app.save(settings);
});
