"""The contact pages the hub serves, open to everyone, each in English and German (Patrik, 2026-11-01: Arestemis and the
Empire get pages in the style of Aresium's own, aresium.de/contact):

- the Ares Empire's, www.ares-empire.de/contact and /kontakt: the Empire's general contact (the imprint names it) and
  where people ask for the Ares Empire app;
- Arestemis's, www.ares-empire.de/arestemis/contact and /arestemis/kontakt (Arestemis has no website; its API lives
  under /api/arestemis on the same host).

Each is one form for asking for the iPhone app (`?topic=access`) and for questions, problems and ideas, laid out like
Contact & support in the apps (empire-ios Shared/Support) and in the app's own look. The markup is Aresium's
(aresium src/web/contact-page.ts); the sending (web/shared/forms/contact-form.js) and the layout
(web/shared/forms/contact-form.css) are shared with aresium.de byte for byte; the looks are web/contact/<app>.css on
web/contact/hub.css. The browser posts straight to the account server's open `contact` collection (docs/ACCOUNTS.md →
Website contact form), with the app as `app` and the topic as `kind`. The words address no one: no "you", no "du" or
du-imperatives (Patrik, 2026-10-31).

A page collects personal data, so it is served only while the privacy policy in its language is (webauth/legal.py).
Nothing comes from other hosts, and its Content-Security-Policy (CSP) allows only this server and the account server.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from urllib.parse import urlsplit

from webauth import legal

CONTACT_ENDPOINT = "https://auth.ares-empire.de/api/collections/contact/records"
_ACCOUNT_ORIGIN = "{0.scheme}://{0.netloc}".format(urlsplit(CONTACT_ENDPOINT))

# No inline script or style, nothing from other hosts; the form is sent by script to the account server only.
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
       f"connect-src {_ACCOUNT_ORIGIN}; form-action 'none'; base-uri 'none'; frame-ancestors 'none'")

# Where a message can go when the form cannot send it (the imprint's address).
OWNER_EMAIL = "REDACTED-EMAIL"

# The topics in the order the menu shows them; the values are the collection's `kind`. Asking for the app comes first.
TOPICS = ("access", "question", "problem", "idea", "other")
DEFAULT_TOPIC = "question"
LANGUAGES = ("en", "de")

# The files every contact page loads, besides its app's mark and look (ContactApp).
SHARED_FILES = ("/contact/appearance.js", "/fonts/fonts.css", "/shared/forms/contact-form.css", "/contact/hub.css",
                "/shared/forms/contact-form.js")


@dataclass(frozen=True)
class ContactApp:
    slug: str                    # the contact collection's `app`
    name: str
    paths: dict[str, str]        # language → the page's path
    mark: str                    # the app's bust: the header, the tab's icon
    look: str                    # its stylesheet (web/contact/)
    band: str                    # the name across the width at the end (WordmarkBand)
    home: str | None             # where the name in the header and "Back" lead; None: no page of its own
    images: tuple[str, ...] = () # pictures its look draws (its god's bust in the wall, --bust)


APPS = {
    "empire": ContactApp("empire", "Ares Empire", {"en": "/contact", "de": "/kontakt"}, "/brand/ares-bust-icon.png",
                         "/contact/empire.css", "ARES EMPIRE", "/", ("/brand/head_transparent_real.webp",)),
    "arestemis": ContactApp("arestemis", "Arestemis", {"en": "/arestemis/contact", "de": "/arestemis/kontakt"},
                            "/brand/artemis-icon.png", "/contact/arestemis.css", "ARESTEMIS", None,
                            ("/brand/artemis-profile.webp",)),
}

# path → (app, language)
PAGES = {path: (app, language) for app in APPS.values() for language, path in app.paths.items()}

# What the pages load, all from this server and open without a login (webauth/server.py → OPEN_PATHS).
ASSET_PATHS = frozenset(SHARED_FILES) | {"/fonts/SpaceGrotesk-Variable.ttf", "/fonts/JetBrainsMono-Variable.ttf"} | {
    path for app in APPS.values() for path in (app.mark, app.look, *app.images)}

# The privacy policy each page links and needs (served only while it is published).
POLICY = {"en": "/privacy", "de": "/datenschutz"}
IMPRINT = {"en": "/imprint", "de": "/impressum"}

# English is the source, German its translation. %s in sent_app is the address the visitor gave; %1 and %2 in counter
# are the length and the limit; %e is the owner's email address, written as a mailto link. The words that name an app
# are the app's own (APP_WORDS below).
WORDS = {
    "en": {
        "title": "Contact", "other_language": "Deutsch",
        "topic": "Topic", "message": "Message", "answer_to": "Answer to", "optional": "(optional)",
        "topics": {"access": "Get the app", "question": "Question", "problem": "Problem", "idea": "Idea or wish",
                   "other": "Something else"},
        "placeholders": {"access": "Anything to add? (optional)", "question": "What is the question?",
                         "problem": "What happened, and what should have happened?", "other": "What is it about?"},
        "note_answer": "The answer comes by email, to this address.",
        "email": "Email", "name": "Name (optional)",
        "privacy_lead": "How the data is used:", "privacy": "Privacy policy", "imprint": "Imprint",
        "problems": {
            "empty": "Please write a message.",
            "long": "The message is too long: at most 5,000 characters.",
            "noemail": "An email address is needed for the answer.",
            "email": "This doesn't look like an email address.",
            "many": "Too many messages for now. Please try again later.",
            "offline": "No connection. Please send it again later.",
            "failed": "It didn't go through. Please try again, or write to %e.",
        },
        "send": "Send", "sending": "Sending…", "again": "Send again", "counter": "%1 of %2 characters",
        "noscript": "This form needs JavaScript. Messages by email go to %e.",
        "sent_title": "Thanks, it's arrived.",
        "sent_app": "The install link comes by email, to %s.",
        "sent_answer": "If it needs an answer, it comes by email.",
        "look": "Light appearance",
    },
    "de": {
        "title": "Kontakt", "other_language": "English",
        "topic": "Thema", "message": "Nachricht", "answer_to": "Antwort an", "optional": "(optional)",
        "topics": {"access": "App bekommen", "question": "Frage", "problem": "Problem", "idea": "Idee oder Wunsch",
                   "other": "Sonstiges"},
        "placeholders": {"access": "Noch etwas dazu? (optional)", "question": "Was ist die Frage?",
                         "problem": "Was ist passiert, und was hätte passieren sollen?", "other": "Worum geht es?"},
        "note_answer": "Die Antwort kommt per E-Mail an diese Adresse.",
        "email": "E-Mail", "name": "Name (optional)",
        "privacy_lead": "Wie die Daten verarbeitet werden:", "privacy": "Datenschutzerklärung", "imprint": "Impressum",
        "problems": {
            "empty": "Bitte eine Nachricht schreiben.",
            "long": "Die Nachricht ist zu lang: höchstens 5.000 Zeichen.",
            "noemail": "Für die Antwort fehlt eine E-Mail-Adresse.",
            "email": "Das sieht nicht nach einer E-Mail-Adresse aus.",
            "many": "Zu viele Nachrichten. Bitte später noch mal.",
            "offline": "Keine Verbindung. Bitte später noch mal senden.",
            "failed": "Das hat nicht geklappt. Bitte noch mal versuchen oder an %e schreiben.",
        },
        "send": "Senden", "sending": "Wird gesendet…", "again": "Erneut senden", "counter": "%1 von %2 Zeichen",
        "noscript": "Das Formular braucht JavaScript. Nachrichten per E-Mail gehen an %e.",
        "sent_title": "Danke, ist angekommen.",
        "sent_app": "Der Installationslink kommt per E-Mail an %s.",
        "sent_answer": "Braucht es eine Antwort, kommt sie per E-Mail.",
        "look": "Helle Darstellung",
    },
}

# What each page says about its app. The Empire's page is also the Empire's general contact, so its lead names
# anything else too. Both apps need an Ares account, which the app itself creates (Aresium's does not, so its note
# does not say so).
APP_WORDS = {
    "empire": {
        "en": {
            "page_title": "Contact · Ares Empire",
            "description": "Ask for the Ares Empire iPhone app, or write about a question, a problem, an idea or "
                           "anything else.",
            "lead": "Ask for the iPhone app or write about a question, a problem, an idea or anything else around the "
                    "Ares Empire. Messages go to Patrik Breeck by email.",
            "idea": "What would make the Ares Empire better?",
            "note_app": "The Ares Empire app is for the iPhone (iOS 26 or later) and works with an Ares account, "
                        "created in the app. The install link comes by email, to this address.",
            "back": "Back to Ares Empire",
        },
        "de": {
            "page_title": "Kontakt · Ares Empire",
            "description": "Die iPhone-App von Ares Empire anfragen oder zu einer Frage, einem Problem, einer Idee "
                           "oder etwas anderem schreiben.",
            "lead": "Die iPhone-App anfragen oder zu einer Frage, einem Problem, einer Idee oder etwas anderem rund um "
                    "Ares Empire schreiben. Nachrichten gehen per E-Mail an Patrik Breeck.",
            "idea": "Was würde Ares Empire besser machen?",
            "note_app": "Die App von Ares Empire ist fürs iPhone (ab iOS 26) und nutzt ein Ares-Konto, das in der App "
                        "angelegt wird. Der Installationslink kommt per E-Mail an diese Adresse.",
            "back": "Zurück zu Ares Empire",
        },
    },
    "arestemis": {
        "en": {
            "page_title": "Contact · Arestemis",
            "description": "Ask for the Arestemis iPhone app, or write about a question, a problem or an idea.",
            "lead": "Ask for the iPhone app or write about a question, a problem or an idea. Messages go to Patrik "
                    "Breeck by email.",
            "idea": "What would make Arestemis better?",
            "note_app": "Arestemis is an iPhone app (iOS 26 or later) and works with an Ares account, created in the "
                        "app. The install link comes by email, to this address.",
            "back": None,
        },
        "de": {
            "page_title": "Kontakt · Arestemis",
            "description": "Die iPhone-App von Arestemis anfragen oder zu einer Frage, einem Problem oder einer Idee "
                           "schreiben.",
            "lead": "Die iPhone-App anfragen oder zu einer Frage, einem Problem oder einer Idee schreiben. Nachrichten "
                    "gehen per E-Mail an Patrik Breeck.",
            "idea": "Was würde Arestemis besser machen?",
            "note_app": "Arestemis ist eine iPhone-App (ab iOS 26) und nutzt ein Ares-Konto, das in der App angelegt "
                        "wird. Der Installationslink kommt per E-Mail an diese Adresse.",
            "back": None,
        },
    },
}

# Lucide icons (ISC licence), drawn inline so the page needs no icon script: the topics' as on the iPhone form (a
# bubble with !, ? or …, a light bulb) and Aresium's page, and the look switch's sun and moon.
_BUBBLE = '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>'
ICON_PATHS = {
    "access": '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>',
    "question": _BUBBLE + '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    "problem": _BUBBLE + '<path d="M12 8v4"/><path d="M12 16h.01"/>',
    "idea": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/>'
            '<path d="M9 18h6"/><path d="M10 22h4"/>',
    "other": _BUBBLE + '<path d="M8 12h.01"/><path d="M12 12h.01"/><path d="M16 12h.01"/>',
    "chevrons": '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/>'
           '<path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/>'
           '<path d="m19.07 4.93-1.41 1.41"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
}


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def icon(name: str, attributes: str = "", class_name: str = "icon") -> str:
    return (f'<svg class="{class_name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"{attributes}>'
            f'{ICON_PATHS[name]}</svg>')


def with_email(sentence: str) -> str:
    """A sentence, with the owner's address as a mailto link in place of %e if it has one."""
    if "%e" not in sentence:
        return esc(sentence)
    before, after = sentence.split("%e", 1)
    return f'{esc(before)}<a href="mailto:{OWNER_EMAIL}">{OWNER_EMAIL}</a>{esc(after)}'


def topic_from(value: str | None) -> str:
    """`?topic=` → the topic to show first; anything else → Question."""
    return value if value in TOPICS else DEFAULT_TOPIC


def words(app: str, language: str) -> dict:
    """The page's words: the shared ones with the app's own."""
    w = {**WORDS[language], **APP_WORDS[app][language]}
    w["placeholders"] = {**WORDS[language]["placeholders"], "idea": APP_WORDS[app][language]["idea"]}
    return w


def is_published(path: str, web_root: str) -> bool:
    """Whether the page may go online: it collects personal data, so only while the privacy policy in its language is."""
    entry = PAGES.get(path)
    return entry is not None and legal.is_published(POLICY[entry[1]], web_root)


def page(app_slug: str, language: str, topic: str = DEFAULT_TOPIC) -> str:
    """The contact page of `app_slug` in `language`, with `topic` chosen (from `?topic=`; the menu can change it)."""
    app = APPS[app_slug]
    w = words(app_slug, language)
    topic = topic_from(topic)
    other = "de" if language == "en" else "en"
    optional = topic == "access"
    options = "\n              ".join(
        f'<option value="{t}"{" selected" if t == topic else ""} data-placeholder="{esc(w["placeholders"][t])}" '
        f'data-note="{esc(w["note_app"] if t == "access" else w["note_answer"])}"'
        f'{" data-optional" if t == "access" else ""}>{esc(w["topics"][t])}</option>' for t in TOPICS)
    icons = "".join(icon(t, f' data-topic-icon="{t}"{"" if t == topic else " hidden"}') for t in TOPICS)
    problems = "\n          ".join(
        f'<p class="problem" data-problem="{name}" hidden>{icon("alert")}<span>{with_email(text)}</span></p>'
        for name, text in w["problems"].items())
    # The band's letters, spread across the width by the stylesheet as the iPhone apps' WordmarkBand; a space between
    # two words is a narrower slot of its own.
    band = "".join('<span class="space"></span>' if letter == " " else f"<span>{esc(letter)}</span>"
                   for letter in app.band)
    mark = f'<img src="{app.mark}" alt="" width="34" height="34" /><span>{esc(app.name)}</span>'
    home = (f'<a class="home" href="{app.home}">{mark}</a>' if app.home
            else f'<span class="home">{mark}</span>')
    back = f'\n        <a class="back" href="{app.home}">{esc(w["back"])}</a>' if app.home and w["back"] else ""
    links = "".join(f'\n<link rel="stylesheet" href="{href}" />'
                    for href in ("/fonts/fonts.css", "/shared/forms/contact-form.css", "/contact/hub.css", app.look))

    return f"""<!doctype html>
<html lang="{language}" data-theme="dark">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<script src="/contact/appearance.js"></script>
<title>{esc(w["page_title"])}</title>
<meta name="description" content="{esc(w["description"])}" />
<link rel="icon" type="image/png" href="{app.mark}" />
<link rel="apple-touch-icon" href="{app.mark}" />
<link rel="alternate" hreflang="{other}" href="{app.paths[other]}" />{links}
<script src="/shared/forms/contact-form.js" defer></script>
</head>
<body>
  <div class="page">
    <header class="top">
      {home}
      <div class="top-end">
        <button class="look" type="button" aria-pressed="false" aria-label="{esc(w["look"])}" title="{esc(w["look"])}" data-look-switch hidden>{icon("sun", "", "icon sun")}{icon("moon", "", "icon moon")}</button>
        <a class="lang" href="{app.paths[other]}?topic={topic}" hreflang="{other}" lang="{other}" data-language-link>{esc(w["other_language"])}</a>
      </div>
    </header>

    <main>
      <section class="compose" id="contact-compose" data-compose>
        <h1>{esc(w["title"])}</h1>
        <p class="lead">{esc(w["lead"])}</p>

        <form class="contact" novalidate data-contact-form data-endpoint="{CONTACT_ENDPOINT}" data-app="{app.slug}"
          data-language="{language}" data-sent="contact-sent" data-max="5000">
          <label class="heading" for="contact-topic">{esc(w["topic"])}</label>
          <div class="glass topic">
            <span class="topic-icon">{icons}</span>
            <select id="contact-topic" name="kind">
              {options}
            </select>
            {icon("chevrons", "", "chevrons")}
          </div>

          <label class="heading" for="contact-message">{esc(w["message"])} <span class="optional" data-optional-mark{"" if optional else " hidden"}>{esc(w["optional"])}</span></label>
          <div class="glass box">
            <textarea id="contact-message" name="message" rows="8" placeholder="{esc(w["placeholders"][topic])}"{"" if optional else " required"}
              aria-describedby="contact-counter contact-problems"></textarea>
          </div>
          <p class="counter" id="contact-counter" data-counter data-words="{esc(w["counter"])}" hidden></p>

          <fieldset class="reply">
            <legend class="heading">{esc(w["answer_to"])}</legend>
            <div class="glass">
              <input id="contact-email" name="email" type="email" inputmode="email" autocomplete="email" autocapitalize="off"
                spellcheck="false" required placeholder="{esc(w["email"])}" aria-label="{esc(w["email"])}"
                aria-describedby="contact-note contact-problems" />
              <hr />
              <input id="contact-name" name="name" type="text" autocomplete="name" maxlength="100"
                placeholder="{esc(w["name"])}" aria-label="{esc(w["name"])}" />
            </div>
          </fieldset>
          <p class="note" id="contact-note" data-topic-note>{esc(w["note_app"] if optional else w["note_answer"])}</p>
          <p class="note">{esc(w["privacy_lead"])} <a href="{POLICY[language]}">{esc(w["privacy"])}</a></p>

          <div class="trap" aria-hidden="true">
            <label for="contact-website">Website</label>
            <input id="contact-website" name="website" type="text" tabindex="-1" autocomplete="off" />
          </div>

          <div class="problems" id="contact-problems" aria-live="assertive">
          {problems}
          </div>
          <button type="submit" data-sending="{esc(w["sending"])}" data-again="{esc(w["again"])}">
            <span class="spinner" aria-hidden="true"></span><span data-label>{esc(w["send"])}</span>
          </button>
          <noscript><p class="note">{with_email(w["noscript"])}</p></noscript>
        </form>
      </section>

      <section class="sent" id="contact-sent" tabindex="-1" aria-labelledby="contact-sent-title" hidden>
        <div class="sent-mark">{icon("check")}</div>
        <h2 id="contact-sent-title">{esc(w["sent_title"])}</h2>
        <p data-sent-line="app" data-words="{esc(w["sent_app"])}" hidden></p>
        <p data-sent-line="answer" hidden>{esc(w["sent_answer"])}</p>{back}
      </section>
    </main>

    <footer class="legal">
      <a href="{POLICY[language]}">{esc(w["privacy"])}</a> · <a href="{IMPRINT[language]}">{esc(w["imprint"])}</a>
    </footer>
  </div>
  <div class="band" aria-hidden="true">{band}</div>
</body>
</html>
"""


def render(path: str, query_topic: str | None, web_root: str, preview: bool = False) -> tuple[bytes, str] | None:
    """The page for `path` and its language, or None (not a contact page, or its privacy policy is not published)."""
    entry = PAGES.get(path)
    if entry is None or (not preview and not is_published(path, web_root)):
        return None
    app, language = entry
    return page(app.slug, language, topic_from(query_topic)).encode("utf-8"), language
