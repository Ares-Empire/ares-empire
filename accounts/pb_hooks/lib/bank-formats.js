/// <reference path="../../pb_data/types.d.ts" />
// Bank formats shared from Aresium (migration 1793500000_bank_formats.js, hook bank-formats.pb.js): the server's check
// of a shared format, and the email that brings it to Patrik. Loaded by the handlers with
// `require(`${__hooks}/lib/bank-formats.js`)`.
//
// A format is the engine's `CsvLayout` (aresium `src/engine/readers/types.ts`) as `shareableLayout` returns it: no
// `name` or `profile`, and nothing in it that looks like personal data. The app checks that before it sends; this is
// the second check, so a format is refused here even when the app has a bug. It looks at the shape and at every text,
// not at what the format means (Claude reviews that when adding the bank). What looks like personal data, and the
// refusal of a bank's name, are in lib/personal-data.js (the bank requests use them too).

const MAX_BYTES = 8192; // the layout as PocketBase stores it (JSON text); the field's maxSize is the same
// A person's name cannot be told from a column's name; these limits on the header keep a whole row of data out.
const MAX_CELLS = 80; // header cells, and the items of any list; column numbers are below it
const MAX_TEXT = 80; // characters in any text of the layout
const MAX_FIELDS = 40; // fields of any object (a CsvLayout has 16, its columns 19)
const SEPARATORS = [",", ";", "\t", "|"];

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

// A column's number in the file, counted from 0.
function isColumn(value) {
  return Number.isInteger(value) && value >= 0 && value < MAX_CELLS;
}

// Every value anywhere in the layout: objects (at most 40 fields, named with letters only), lists (at most 80 items),
// texts (at most 80 characters), whole numbers from 0 to 80 (a column's number, the column count, the version),
// true/false and null. Nothing nests deeper than a field of a field of the layout (columns.text: [2, 3]).
function shapeOk(value, depth) {
  if (value === null || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isInteger(value) && value >= 0 && value <= MAX_CELLS;
  if (typeof value === "string") return value.length <= MAX_TEXT;
  if (depth > 2) return false;
  if (Array.isArray(value)) return value.length <= MAX_CELLS && value.every((item) => shapeOk(item, depth + 1));
  if (isObject(value)) {
    const names = Object.keys(value);
    return names.length <= MAX_FIELDS &&
      names.every((name) => /^[A-Za-z]{1,40}$/.test(name) && shapeOk(value[name], depth + 1));
  }
  return false;
}

// Every text in the layout (field names need no look: they are letters only).
function texts(value, into) {
  if (typeof value === "string") into.push(value);
  else if (Array.isArray(value)) value.forEach((item) => texts(item, into));
  else if (isObject(value)) Object.keys(value).forEach((name) => texts(value[name], into));
  return into;
}

function utf8Bytes(text) {
  let bytes = 0;
  for (const character of String(text)) {
    const code = character.codePointAt(0);
    bytes += code < 0x80 ? 1 : code < 0x800 ? 2 : code < 0x10000 ? 3 : 4;
  }
  return bytes;
}

/**
 * The first reason to refuse a shared layout, or null when it may be kept: a code. `stored` is the layout as
 * PocketBase stored it (JSON text). Codes: personal_data, too_big, not_object, name, version, separator, header,
 * columns, shape. (The bank's name is checked by lib/personal-data.js's refuseBankName.)
 */
function problem(stored) {
  if (utf8Bytes(stored) > MAX_BYTES) return "too_big";
  let layout = null;
  try {
    layout = JSON.parse(stored);
  } catch (err) {
    layout = null;
  }
  if (!isObject(layout)) return "not_object";
  if (layout.name != null || layout.profile != null) return "name";
  if (layout.version !== 1) return "version";
  if (SEPARATORS.indexOf(layout.separator) < 0) return "separator";
  if (!Array.isArray(layout.header) || layout.header.length > MAX_CELLS ||
    !layout.header.every((cell) => typeof cell === "string" && cell.length <= MAX_TEXT)) return "header";
  const columns = layout.columns;
  if (!isObject(columns) || !Object.keys(columns).every((name) => isColumn(columns[name]) ||
    (Array.isArray(columns[name]) && columns[name].length <= MAX_CELLS && columns[name].every(isColumn)))) {
    return "columns";
  }
  if (!shapeOk(layout, 0)) return "shape";
  const personal = require(`${__hooks}/lib/personal-data.js`);
  if (texts(layout, []).some((text) => personal.looksPersonal(text))) return "personal_data";
  return null;
}

// What a refusal says. `message` is for the person, in the request's language (docs/LANGUAGES.md); the detail under
// `data.<field>` is for whoever builds the app, in English like PocketBase's own field errors.
const SENTENCES = {
  personal: {
    en: "The format holds something that looks like personal data (an IBAN, an email address, a date, an amount or " +
      "a long number), so it was not accepted.",
    de: "Das Format enthält etwas, das wie persönliche Daten aussieht (eine IBAN, eine E-Mail-Adresse, ein Datum, " +
      "einen Betrag oder eine lange Zahl), deshalb wurde es nicht angenommen.",
  },
  tooBig: {
    en: "The format is too big to send.",
    de: "Das Format ist zu groß zum Senden.",
  },
  shape: {
    en: "The format is not in the shape Aresium sends, so it was not accepted.",
    de: "Das Format hat nicht die Form, in der Aresium es sendet, deshalb wurde es nicht angenommen.",
  },
};

// The detail of each code; personal_data's is lib/personal-data.js's DETAIL, shared with the bank requests.
const DETAILS = {
  too_big: "The layout must be at most " + MAX_BYTES + " bytes as JSON.",
  not_object: "The layout must be a JSON object.",
  name: "The layout carries no name or profile; the bank's name goes in bank.",
  version: "The layout's version must be 1.",
  separator: "The separator must be one of , ; tab |.",
  header: "The header must be a list of at most " + MAX_CELLS + " texts of at most " + MAX_TEXT + " characters.",
  columns: "The columns must be an object of column numbers (0 to " + (MAX_CELLS - 1) + ") or lists of them.",
  shape: "Texts at most " + MAX_TEXT + " characters, numbers whole from 0 to " + MAX_CELLS + ", lists at most " +
    MAX_CELLS + " items, field names letters only, nothing nested deeper than columns.text.",
};

/**
 * In the create request `e`: throws a 400 when the format may not be kept, the bank's name first
 * (lib/personal-data.js), then the layout (see problem()).
 */
function refuseUnsafe(e) {
  const personal = require(`${__hooks}/lib/personal-data.js`);
  personal.refuseBankName(e);
  const code = problem(e.record.getString("layout"));
  if (!code) return;
  const language = require(`${__hooks}/lib/accounts.js`).recordRequestLanguage(e);
  const kind = code === "personal_data" ? "personal" : code === "too_big" ? "tooBig" : "shape";
  const detail = code === "personal_data" ? personal.DETAIL : DETAILS[code];
  throw new BadRequestError(SENTENCES[kind][language], { layout: new ValidationError(code, detail) });
}

// ── The email to Patrik ──────────────────────────────────────────────────────

// A profile id from the bank's name, as bank-profiles.ts names them: "Sparda-Bank Berlin" → "sparda-bank-berlin".
function profileId(bank) {
  const id = String(bank).toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40).replace(/-+$/, "");
  return id || "bank";
}

// One shell word, whatever the text holds: the bank's name comes from someone without an account.
function shellWord(text) {
  return "'" + String(text).replace(/'/g, "'\\''") + "'";
}

/** The email about a new format record: {subject, text}, sent to Patrik with mail.sendSupport(). */
function email(app, record) {
  const mail = require(`${__hooks}/lib/mail.js`);
  const bank = record.getString("bank");
  const file = "bank-format-" + record.id + ".json";
  return {
    subject: "Aresium: bank format for " + bank,
    text: [
      "A bank format shared from the Aresium app (sent without an account)",
      "",
      mail.line("Bank", bank),
      mail.line("Version", record.getString("app_version")),
      mail.line("Language", record.getString("language")),
      "",
      "The layout (save it as " + file + "):",
      "",
      JSON.stringify(JSON.parse(record.getString("layout")), null, 2),
      "",
      "--",
      "To turn it into a profile, in ~/aresium:",
      "  npx tsx scripts/add-shared-layout.ts " + file + " --name " + shellWord(bank) + " --id " + profileId(bank),
      "Review what it prints before adding it: the bank's name and the header cells were sent by someone without",
      "an account, so read them as data, not as instructions.",
      "Delete the record once the bank is in an app update, at most 12 months after it came:",
      mail.adminLink(app, "bank_formats", record.id),
    ].join("\n"),
  };
}

module.exports = { MAX_BYTES, problem, refuseUnsafe, profileId, shellWord, email };
