"""The legal pages: privacy policy and imprint, in German and English, open to everyone (no login).

They are the one exception to "websites stay English" (legal pages in Germany are German). The text lives in
`web/legal/<name>.html` (body only, what Patrik approves); `web/legal/page.html` is the frame in the hub's look.
A page that still holds a draft marker is not served (404), so merging a draft never publishes it; set
LEGAL_PREVIEW=1 to look at drafts locally.
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


PAGES = {
    "/datenschutz": LegalPage("datenschutz.html", "de", "Datenschutzerklärung", "/privacy"),
    "/privacy": LegalPage("privacy.html", "en", "Privacy policy", "/datenschutz"),
    "/impressum": LegalPage("impressum.html", "de", "Impressum", "/imprint"),
    "/imprint": LegalPage("imprint.html", "en", "Imprint", "/impressum"),
}

# The footer: both pages in the page's language. The language link names the other language in that language.
NAV = {"de": (("/datenschutz", "Datenschutz"), ("/impressum", "Impressum")),
       "en": (("/privacy", "Privacy"), ("/imprint", "Imprint"))}
OTHER_LANGUAGE = {"de": ("en", "English"), "en": ("de", "Deutsch")}

# What the frame needs besides the page text: its font (self-hosted, so the pages contact no other host) and licence.
ASSET_PATHS = frozenset({"/fonts/SpaceGrotesk-Variable.ttf", "/fonts/OFL-SpaceGrotesk.txt"})


def is_draft(text: str) -> bool:
    return any(marker in text for marker in DRAFT_MARKERS)


def preview_enabled() -> bool:
    return os.environ.get("LEGAL_PREVIEW") == "1"


def render(path: str, web_root: str, preview: bool = False) -> tuple[bytes, str] | None:
    """The page for `path` and its language, or None (not a legal page, missing, or still a draft)."""
    entry = PAGES.get(path)
    if entry is None:
        return None
    folder = os.path.join(web_root, "legal")
    try:
        with open(os.path.join(folder, entry.file), encoding="utf-8") as f:
            content = f.read()
        with open(os.path.join(folder, "page.html"), encoding="utf-8") as f:
            frame = Template(f.read())
    except OSError:
        return None
    if is_draft(content) and not preview:
        return None
    other_language, other_label = OTHER_LANGUAGE[entry.language]
    links = []
    for href, label in NAV[entry.language]:
        current = ' aria-current="page"' if href == path else ""
        links.append(f'<a href="{href}"{current}>{html.escape(label)}</a>')
    nav = " · ".join(links)
    page = frame.substitute(lang=entry.language, title=html.escape(entry.title), other_href=entry.other,
                            other_lang=other_language, other_label=other_label, nav=nav, content=content)
    return page.encode("utf-8"), entry.language
