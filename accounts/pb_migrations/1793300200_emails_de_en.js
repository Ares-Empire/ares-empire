/// <reference path="../pb_data/types.d.ts" />
// PocketBase's own emails to an account (confirm the email address, reset the password) in English and German in one
// message (2026-10-25): an account can be created in any app, and these templates are fixed (they cannot follow the
// account's `language`). The links open PocketBase's own pages, as before. Down: PocketBase's default templates again.

const VERIFICATION = {
  subject: "Confirm your Ares account · Bestätige dein Ares-Konto",
  body: `<p>Hello,</p>
<p>please confirm that this email address belongs to your Ares account:</p>
<p><a class="btn" href="{APP_URL}/_/#/auth/confirm-verification/{TOKEN}" target="_blank" rel="noopener">Confirm email address</a></p>
<p>Then Patrik approves the account, and you get an email as soon as it is ready. If you didn't create an Ares account, ignore this email.</p>
<hr>
<p>Hallo,</p>
<p>bitte bestätige, dass diese E-Mail-Adresse zu deinem Ares-Konto gehört:</p>
<p><a class="btn" href="{APP_URL}/_/#/auth/confirm-verification/{TOKEN}" target="_blank" rel="noopener">E-Mail-Adresse bestätigen</a></p>
<p>Danach gibt Patrik das Konto frei, und du bekommst eine E-Mail, sobald es bereit ist. Wenn du kein Ares-Konto angelegt hast, ignoriere diese E-Mail.</p>
<p>Ares Empire</p>`,
};

const RESET = {
  subject: "Reset your Ares password · Setze dein Ares-Passwort zurück",
  body: `<p>Hello,</p>
<p>to choose a new password for your Ares account, open this link:</p>
<p><a class="btn" href="{APP_URL}/_/#/auth/confirm-password-reset/{TOKEN}" target="_blank" rel="noopener">Choose a new password</a></p>
<p>The new password is the one for every Ares app; the apps ask you to log in again. If you didn't ask for this, ignore this email: your password stays as it is.</p>
<hr>
<p>Hallo,</p>
<p>um ein neues Passwort für dein Ares-Konto zu wählen, öffne diesen Link:</p>
<p><a class="btn" href="{APP_URL}/_/#/auth/confirm-password-reset/{TOKEN}" target="_blank" rel="noopener">Neues Passwort wählen</a></p>
<p>Das neue Passwort gilt für alle Ares-Apps; die Apps bitten dich, dich neu anzumelden. Wenn du das nicht angefordert hast, ignoriere diese E-Mail: Dein Passwort bleibt, wie es ist.</p>
<p>Ares Empire</p>`,
};

migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  users.verificationTemplate.subject = VERIFICATION.subject;
  users.verificationTemplate.body = VERIFICATION.body;
  users.resetPasswordTemplate.subject = RESET.subject;
  users.resetPasswordTemplate.body = RESET.body;
  app.save(users);
}, (app) => {
  const users = app.findCollectionByNameOrId("users");
  const defaults = new Collection({ type: "auth", name: "defaults" }); // never saved: only its default templates
  users.verificationTemplate.subject = defaults.verificationTemplate.subject;
  users.verificationTemplate.body = defaults.verificationTemplate.body;
  users.resetPasswordTemplate.subject = defaults.resetPasswordTemplate.subject;
  users.resetPasswordTemplate.body = defaults.resetPasswordTemplate.body;
  app.save(users);
});
