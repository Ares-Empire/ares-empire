"""Hub API sentences in both languages; the login website stays English."""

TEXTS = {
    "Issue: ": {"en": "Issue: ", "de": "Problem: "},
    "This account has no access to Ares Empire.": {
        "en": "This account has no access to Ares Empire.",
        "de": "Dieses Konto hat keinen Zugang zu Ares Empire.",
    },
    "Login service unavailable, try again in a minute.": {
        "en": "Login service unavailable, try again in a minute.",
        "de": "Anmeldedienst nicht erreichbar, versuch es in einer Minute noch einmal.",
    },
    "Hub data unavailable, try again in a minute.": {
        "en": "Hub data unavailable, try again in a minute.",
        "de": "Hub-Daten nicht erreichbar, versuch es in einer Minute noch einmal.",
    },
    "Invalid account request.": {
        "en": "Invalid account request.",
        "de": "Ungültige Kontoanfrage.",
    },
    "Forbidden.": {"en": "Forbidden.", "de": "Kein Zugang."},
    "Account not found.": {"en": "Account not found.", "de": "Konto nicht gefunden."},
    "Account service unavailable, try again in a minute.": {
        "en": "Account service unavailable, try again in a minute.",
        "de": "Kontodienst nicht erreichbar, versuch es in einer Minute noch einmal.",
    },
    "Account service returned an unreadable response.": {
        "en": "Account service returned an unreadable response.",
        "de": "Die Antwort des Kontodienstes ist nicht lesbar.",
    },
    "Administrator access required.": {
        "en": "Administrator access required.",
        "de": "Dafür brauchst du Administratorrechte.",
    },
}


def text(message: str, language: str) -> str:
    return TEXTS.get(message, {}).get(language, message)
