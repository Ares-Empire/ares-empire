"""The legal pages: privacy policy, imprint and the contact form, in German and English, open to everyone (no login).

They are the one exception to "websites stay English" (legal pages in Germany are German). The text lives in
`web/legal/<name>.html` (body only, what Patrik approves); `web/legal/page.html` is the frame in the hub's look.
A page that still holds a draft marker is not served (404), so merging a draft never publishes it; set
LEGAL_PREVIEW=1 to look at drafts locally. The contact form (`/kontakt`, `/contact`) collects personal data, so it is
served only while the privacy policy in its language is (`needs`); its script (`web/legal/contact.js`) is inlined.
"""

from __future__ import annotations

import html
import os
from dataclasses import dataclass
from string import Template

# Placeholders that must be gone before a page goes online (docs/PRIVACY.md).
DRAFT_MARKERS = ("[ADDRESS]", "[lead to confirm]")


@dataclass(frozen=True)
class LegalPage:
    file: str          # in web/legal/
    language: str      # "de" | "en"
    title: str
    other: str         # the same page in the other language
    needs: str | None = None    # a page that must be published for this one to be served
    script: str | None = None   # a script in web/legal/, inlined at the end of the page


PAGES = {
    "/datenschutz": LegalPage("datenschutz.html", "de", "Datenschutzerklärung", "/privacy"),
    "/privacy": LegalPage("privacy.html", "en", "Privacy policy", "/datenschutz"),
    "/impressum": LegalPage("impressum.html", "de", "Impressum", "/imprint"),
    "/imprint": LegalPage("imprint.html", "en", "Imprint", "/impressum"),
    "/kontakt": LegalPage("kontakt.html", "de", "Kontakt", "/contact", needs="/datenschutz", script="contact.js"),
    "/contact": LegalPage("contact.html", "en", "Contact", "/kontakt", needs="/privacy", script="contact.js"),
}

# The footer: the pages in the page's language. The language link names the other language in that language.
NAV = {"de": (("/datenschutz", "Datenschutz"), ("/impressum", "Impressum"), ("/kontakt", "Kontakt")),
       "en": (("/privacy", "Privacy"), ("/imprint", "Imprint"), ("/contact", "Contact"))}
OTHER_LANGUAGE = {"de": ("en", "English"), "en": ("de", "Deutsch")}

# What the frame needs besides the page text: its font (self-hosted, so the pages contact no other host) and licence.
ASSET_PATHS = frozenset({"/fonts/SpaceGrotesk-Variable.ttf", "/fonts/OFL-SpaceGrotesk.txt"})


def is_draft(text: str) -> bool:
    return any(marker in text for marker in DRAFT_MARKERS)


def preview_enabled() -> bool:
    return os.environ.get("LEGAL_PREVIEW") == "1"


def _read(web_root: str, name: str) -> str | None:
    try:
        with open(os.path.join(web_root, "legal", name), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def is_published(path: str, web_root: str) -> bool:
    """Whether the page may go online: its text is there and final, and so is the page it needs."""
    entry = PAGES.get(path)
    if entry is None:
        return False
    content = _read(web_root, entry.file)
    if content is None or is_draft(content):
        return False
    return entry.needs is None or is_published(entry.needs, web_root)


def render(path: str, web_root: str, preview: bool = False) -> tuple[bytes, str] | None:
    """The page for `path` and its language, or None (not a legal page, missing, or not published yet)."""
    entry = PAGES.get(path)
    if entry is None:
        return None
    content = _read(web_root, entry.file)
    frame = _read(web_root, "page.html")
    script = _read(web_root, entry.script) if entry.script else ""
    if content is None or frame is None or script is None:
        return None
    if not preview and not is_published(path, web_root):
        return None
    other_language, other_label = OTHER_LANGUAGE[entry.language]
    links = []
    for href, label in NAV[entry.language]:
        current = ' aria-current="page"' if href == path else ""
        links.append(f'<a href="{href}"{current}>{html.escape(label)}</a>')
    nav = " · ".join(links)
    page = Template(frame).substitute(lang=entry.language, title=html.escape(entry.title), other_href=entry.other,
                                      other_lang=other_language, other_label=other_label, nav=nav, content=content,
                                      script=f"<script>\n{script}</script>" if script else "")
    return page.encode("utf-8"), entry.language
