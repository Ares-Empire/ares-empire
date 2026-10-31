/// <reference path="../pb_data/types.d.ts" />
// Each app's own contact form (2026-10-30, Aresium first: aresium.de/contact and /kontakt): one form for questions,
// problems, ideas and asking for the app. The message now says which app and what about in fields of its own, instead
// of a footer in the text (docs/ACCOUNTS.md → Website contact form). The hub's general form (www.ares-empire.de/contact)
// sends none of them and works as before.
//
// - `app`: the app the message is about, the same values as feedback's `app`. Empty: the general website form.
// - `kind`: what it is about, feedback's kinds plus `access` (asking for the app; Patrik answers with the install link).
// - `app_version` and `system`: for the iPhone apps' Contact & support without a login (as feedback's), so a later
//   build can send them as fields; until then it ends its message with a footer, which pb_hooks/contact.pb.js still
//   reads. `app_version` holds only the characters of a version ("1.0 (12)"), `system` one line ("iOS 27.0 · iPhone").
// - `message` may be empty, but only when asking for the app (an email address is all Patrik needs to send the install
//   link); every other message must have text. pb_hooks/contact.pb.js checks that, since a field cannot depend on
//   another one. A message that is there still needs a character that is not a space.
const APPS = ["empire", "aresium", "arestemis", "aresus", "arestoteles"];
const KINDS = ["access", "question", "problem", "idea", "other"];
const ADDED = ["app", "kind", "app_version", "system"];

migrate((app) => {
  const contact = app.findCollectionByNameOrId("contact");
  contact.fields.add(new SelectField({ name: "app", maxSelect: 1, values: APPS }));
  contact.fields.add(new SelectField({ name: "kind", maxSelect: 1, values: KINDS }));
  contact.fields.add(new TextField({ name: "app_version", max: 40, pattern: "^[0-9A-Za-z .()+_-]*$" }));
  contact.fields.add(new TextField({ name: "system", max: 80, pattern: "^[^\\x00-\\x1f\\x7f]*$" }));
  const message = contact.fields.getByName("message");
  message.required = false;
  message.min = 0;
  app.save(contact);
}, (app) => {
  const contact = app.findCollectionByNameOrId("contact");
  for (const name of ADDED) contact.fields.removeByName(name);
  const message = contact.fields.getByName("message");
  message.required = true;
  message.min = 1;
  app.save(contact);
});
