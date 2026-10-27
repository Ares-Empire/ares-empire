/// <reference path="../../pb_data/types.d.ts" />
// What looks like personal data in a short text that someone sends from Aresium without an account, and the refusal
// of a bank's name that does. Used by the bank formats (lib/bank-formats.js: the bank's name and every text of the
// layout) and the bank requests (bank-requests.pb.js: the bank's name). Loaded by the handlers with
// `require(`${__hooks}/lib/personal-data.js`)`.
//
// The app checks the same before it sends; this is the second check, so a text is refused here even when the app has
// a bug. A person's name cannot be told from a bank's or a column's name, so it is not looked for.

// An email address, a long number, a date or an amount.
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

/** Whether `text` holds something that looks like an IBAN, an email address, a date, an amount or a long number. */
function looksPersonal(text) {
  const value = String(text);
  if (PERSONAL.some((pattern) => pattern.test(value))) return true;
  return (value.match(IBAN) || []).some((found) => (found.match(/\d/g) || []).length >= 8);
}

// The detail under `data.<field>` of a refusal, for whoever builds the app: in English, like PocketBase's own field
// errors. The person reads the refusal's `message`, in their language.
const DETAIL = "Something looks like personal data (an IBAN, an email address, a date, an amount or 5+ digits).";

// ── The bank's name ──────────────────────────────────────────────────────────

// What the person typed as the bank's name (the `bank` field of bank_formats and bank_requests). The field allows at
// most 100 characters and checks that itself, after this hook; the patterns only ever look at short texts.
const MAX_BANK = 100;

// What a refused bank's name says, in the request's language (docs/LANGUAGES.md).
const BANK_SENTENCE = {
  en: "The bank's name looks like personal data (an IBAN, an email address, a date, an amount or a long number). " +
    "Type only the bank's name.",
  de: "Der Name der Bank sieht wie persönliche Daten aus (eine IBAN, eine E-Mail-Adresse, ein Datum, ein Betrag " +
    "oder eine lange Zahl). Gib nur den Namen der Bank ein.",
};

/**
 * In the create request `e` of a record with a `bank` field: throws a 400 when the bank's name looks like personal
 * data, with the sentence in the request's language and `data.bank.code` "personal_data". Nothing is saved then.
 */
function refuseBankName(e) {
  const bank = String(e.record.getString("bank"));
  if (bank.length > MAX_BANK || !looksPersonal(bank)) return;
  const language = require(`${__hooks}/lib/accounts.js`).recordRequestLanguage(e);
  throw new BadRequestError(BANK_SENTENCE[language], { bank: new ValidationError("personal_data", DETAIL) });
}

module.exports = { looksPersonal, DETAIL, refuseBankName };
