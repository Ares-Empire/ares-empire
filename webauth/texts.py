"""Hub API sentences in both languages; the login website stays English."""

TEXTS = {
    "Too many requests. Please try again shortly.": {
        "en": "Too many requests. Please try again shortly.",
        "de": "Zu viele Anfragen. Bitte versuch es in Kürze noch einmal.",
    },
    "Request timed out.": {"en": "Request timed out.", "de": "Zeit für die Anfrage abgelaufen."},
    "Incomplete request body.": {"en": "Incomplete request body.", "de": "Unvollständiger Anfrageinhalt."},
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
    "Please log in again.": {"en": "Please log in again.", "de": "Bitte melde dich erneut an."},
    "Say which app to ask for.": {
        "en": "Say which app to ask for.",
        "de": "Gib an, welche App du anfragen möchtest.",
    },
    "This app is not open to requests.": {
        "en": "This app is not open to requests.",
        "de": "Diese App kann nicht angefragt werden.",
    },
    "This app is coming soon and cannot be requested yet.": {
        "en": "This app is coming soon and cannot be requested yet.",
        "de": "Diese App kommt bald und kann noch nicht angefragt werden.",
    },
    "This account already has this app.": {
        "en": "This account already has this app.",
        "de": "Dieses Konto hat diese App schon.",
    },
    "Invalid account id.": {"en": "Invalid account id.", "de": "Ungültige Konto-ID."},
    "Send approve: true or decline: true.": {
        "en": "Send approve: true or decline: true.",
        "de": "Schick approve: true oder decline: true.",
    },
    "requested must be a list of apps.": {
        "en": "requested must be a list of apps.",
        "de": "requested muss eine Liste von Apps sein.",
    },
    "Unknown API route.": {"en": "Unknown API route.", "de": "Unbekannte API-Route."},
    "Invalid content length.": {"en": "Invalid content length.", "de": "Ungültige Inhaltslänge."},
    "Request too large.": {"en": "Request too large.", "de": "Die Anfrage ist zu groß."},
    "A JSON object is required.": {"en": "A JSON object is required.", "de": "Erwartet wird ein JSON-Objekt."},
    "Invalid JSON.": {"en": "Invalid JSON.", "de": "Ungültiges JSON."},
    "Something went wrong on the server. Try again later.": {
        "en": "Something went wrong on the server. Try again later.",
        "de": "Auf dem Server ist etwas schiefgegangen. Versuch es später noch einmal.",
    },
}


def text(message: str, language: str) -> str:
    return TEXTS.get(message, {}).get(language, message)
