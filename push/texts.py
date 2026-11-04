"""App-facing push API messages. Codes and developer validation messages stay unchanged."""

TEXTS = {
    "Too many requests. Please try again shortly.": {
        "en": "Too many requests. Please try again shortly.",
        "de": "Zu viele Anfragen. Bitte versuch es in Kürze noch einmal.",
    },
    "This account's access changed. Please try again.": {
        "en": "This account's access changed. Please try again.",
        "de": "Der Zugang dieses Kontos hat sich geändert. Bitte versuch es noch einmal.",
    },
    "Request timed out.": {"en": "Request timed out.", "de": "Zeit für die Anfrage abgelaufen."},
    "This account has no access to this app.": {
        "en": "This account has no access to this app.",
        "de": "Dieses Konto hat keinen Zugang zu dieser App.",
    },
    "This account is not active.": {
        "en": "This account is not active.",
        "de": "Dieses Konto ist nicht aktiv.",
    },
    "Login service unavailable, try again in a minute.": {
        "en": "Login service unavailable, try again in a minute.",
        "de": "Anmeldedienst nicht erreichbar, versuch es in einer Minute noch einmal.",
    },
    "The account server returned an unreadable answer.": {
        "en": "The account server returned an unreadable answer.",
        "de": "Die Antwort des Anmeldedienstes ist nicht lesbar.",
    },
    "Internal error.": {
        "en": "Internal error.",
        "de": "Interner Fehler.",
    },
}


def text(message: str, language: str) -> str:
    return TEXTS.get(message, {}).get(language, message)
