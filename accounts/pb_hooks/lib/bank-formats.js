/// <reference path="../../pb_data/types.d.ts" />
// Bank formats shared from Aresium (migration 1793500000_bank_formats.js, hook bank-formats.pb.js): the server's check
// of a shared format, and the email that brings it to Patrik. Loaded by the handlers with
// `require(`${__hooks}/lib/bank-formats.js`)`.
//
// A format is the engine's `CsvLayout` (aresium `src/engine/readers/types.ts`) as `shareableLayout` returns it: no
// `name` or `profile`, and nothing in it that looks like personal data. The app checks that before it sends; this is
// the second check, so a format is refused here even when the app has a bug. It looks at the shape and at every text,
// not at what the format means (Claude reviews that when adding the bank).

const MAX_BYTES = 8192; // the layout as PocketBase stores it (JSON text); the field's maxSize is the same
const MAX_CELLS = 80; // header cells, and the items of any list; column numbers are below it
const MAX_TEXT = 80; // characters in any text of the layout
const MAX_FIELDS = 40; // fields of any object (a CsvLayout has 16, its columns 19)
const MAX_BANK = 100; // the bank field's own limit, which PocketBase checks after this hook
const SEPARATORS = [",", ";", "\t", "|"];

// What personal data would look like in a header cell, a status word or the bank's name. A person's name cannot be
// told from a column's name, so it is not looked for; the limits on the header keep a whole row of data out.
const PERSONAL = [
  /[^\s@]+@[^\s@]+\.[^\s@]+/, // an email address
  /\d{5,}/, // 5+ digits in a row: an account, card, customer or phone number, a date without separators
  /\d(?:[ .\/-]?\d){7,}/, // 8+ digits in groups: "4111 1111 1111 1111", "+49 151 234 567 89"
  /\b\d{1,4}[.\/-]\d{1,2}[.\/-]\d{2,4}\b/, // a date: 27.10.2026, 27.10.26, 2026-10-27, 10/27/2026
  // a date with the month's name: 27 Oct 2026, 27. Okt. 26, 3-Jan-2026
  /\b\d{1,2}\.?[ -]?(?:jan|feb|m[aä]r|apr|ma[iy]|jun|jul|aug|sep|o[ck]t|nov|de[cz])[a-zä]*\.?[ -]?\d{2,4}\b/i,
  /\d[.,]\d{2}(?!\d)/, // an amount: 12,34 · 1.234,56 · -0.99
  /(?:[€$£]|\b(?:EUR|USD|GBP|CHF)\b) ?[-+]?\d|\d ?(?:[€$£]|(?:EUR|USD|GBP|CHF)\b)/i, // an amount with its currency
];

// An IBAN, compact or in groups of four ("DE89 3704 0044 0532 0130 00"): two letters, two check digits, then 11 to 30
// letters or digits, with at least 8 digits in all (so "MT940 Buchungstext" is not one).
const IBAN = /\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}/gi;

function looksPersonal(text) {
  const value = String(text);
  if (PERSONAL.some((pattern) => pattern.test(value))) return true;
  return (value.match(IBAN) || []).some((found) => (found.match(/\d/g) || []).length >= 8);
}

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
 * The first reason to refuse a shared format, or null when it may be kept: {field: "bank" | "layout", code}.
 * `bank` is the name the person typed, `stored` the layout as PocketBase stored it (JSON text). Codes: personal_data,
 * too_big, not_object, name, version, separator, header, columns, shape.
 */
function problem(bank, stored) {
  // A longer name is refused by the field itself; the patterns only ever look at short texts.
  if (String(bank).length <= MAX_BANK && looksPersonal(bank)) return { field: "bank", code: "personal_data" };
  if (utf8Bytes(stored) > MAX_BYTES) return { field: "layout", code: "too_big" };
  let layout = null;
  try {
    layout = JSON.parse(stored);
  } catch (err) {
    layout = null;
  }
  const refuse = (code) => ({ field: "layout", code: code });
  if (!isObject(layout)) return refuse("not_object");
  if (layout.name != null || layout.profile != null) return refuse("name");
  if (layout.version !== 1) return refuse("version");
  if (SEPARATORS.indexOf(layout.separator) < 0) return refuse("separator");
  if (!Array.isArray(layout.header) || layout.header.length > MAX_CELLS ||
    !layout.header.every((cell) => typeof cell === "string" && cell.length <= MAX_TEXT)) return refuse("header");
  const columns = layout.columns;
  if (!isObject(columns) || !Object.keys(columns).every((name) => isColumn(columns[name]) ||
    (Array.isArray(columns[name]) && columns[name].length <= MAX_CELLS && columns[name].every(isColumn)))) {
    return refuse("columns");
  }
  if (!shapeOk(layout, 0)) return refuse("shape");
  if (texts(layout, []).some(looksPersonal)) return refuse("personal_data");
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
  bank: {
    en: "The bank's name looks like personal data (an IBAN, an email address, a date, an amount or a long number). " +
      "Type only the bank's name.",
    de: "Der Name der Bank sieht wie persönliche Daten aus (eine IBAN, eine E-Mail-Adresse, ein Datum, ein Betrag " +
      "oder eine lange Zahl). Gib nur den Namen der Bank ein.",
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

const DETAILS = {
  personal_data: "Something looks like personal data (an IBAN, an email address, a date, an amount or 5+ digits).",
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

/** In the create request `e`: throws a 400 when the format may not be kept (see problem()). */
function refuseUnsafe(e) {
  const found = problem(e.record.getString("bank"), e.record.getString("layout"));
  if (!found) return;
  // A record request event has no `e.request` in hooks; requestInfo() has the headers, lower case with "_" for "-".
  const headers = e.requestInfo().headers || {};
  const language = require(`${__hooks}/lib/accounts.js`).requestLanguage(headers["accept_language"]);
  const kind = found.field === "bank" ? "bank"
    : found.code === "personal_data" ? "personal" : found.code === "too_big" ? "tooBig" : "shape";
  const data = {};
  data[found.field] = new ValidationError(found.code, DETAILS[found.code]);
  throw new BadRequestError(SENTENCES[kind][language], data);
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

module.exports = { MAX_BYTES, problem, looksPersonal, refuseUnsafe, profileId, shellWord, email };
