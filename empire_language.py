"""Request language shared by the independently deployed hub and push service."""

import re


def request_language(header: str | None) -> str:
    """Highest quality English/German tag wins; first wins ties, English is the fallback."""
    best, quality = "en", 0.0
    for item in (header or "").split(","):
        parts = item.strip().lower().split(";")
        tag = parts[0].strip()
        if not re.fullmatch(r"(?:de|en)(?:-[a-z0-9]{1,8})*", tag):
            continue
        q = 1.0
        if len(parts) > 1:
            if len(parts) != 2 or not re.fullmatch(r"\s*q\s*=\s*(?:0(?:\.\d{0,3})?|1(?:\.0{0,3})?)\s*", parts[1]):
                continue
            q = float(parts[1].split("=")[1])
        if q > quality:
            best, quality = tag.split("-")[0], q
    return best
