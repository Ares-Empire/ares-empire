"""The shared, machine-local owner file. Never log its contents."""

import argparse
from functools import lru_cache
import html
import json
import os
from pathlib import Path
import re
import tempfile

KEYS = frozenset(("name", "street", "city", "email"))


def owner_path():
    if "ARES_OWNER_FILE" in os.environ:
        return Path(os.environ["ARES_OWNER_FILE"])
    return Path.home() / ".config/ares-empire/owner.json"


def load_owner():
    path = owner_path()

    def fail(problem):
        raise ValueError(f"Owner file {path}: {problem}") from None

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail("duplicate JSON key")
            result[key] = value
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=object_pairs)
    except OSError as exc:
        fail(exc.strerror or "cannot read file")
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        fail("invalid UTF-8 JSON")
    if not isinstance(data, dict) or data.keys() != KEYS:
        fail("expected an object with exactly name, street, city and email")
    for key in sorted(KEYS):
        if not isinstance(data[key], str) or not data[key].strip():
            fail(f"{key} must be a non-empty string")
    return data


@lru_cache(maxsize=1)
def get_owner():
    """Read once per process; the web server calls this before opening its socket."""
    return load_owner()


def fill(text):
    details = get_owner()
    return re.sub(r"\{\{OWNER_(NAME|STREET|CITY|EMAIL)\}\}",
                  lambda match: html.escape(details[match[1].lower()], quote=True), text)


def write_accounts_environment(destination):
    """A root-only systemd EnvironmentFile, containing only the support email."""
    email = load_owner()["email"]
    if "\0" in email:
        raise ValueError(f"Owner file {owner_path()}: email cannot contain NUL in a service environment")
    # systemd EnvironmentFile double quotes preserve whitespace, including literal newlines.
    escaped = email.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    destination = Path(destination)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write('ARES_OWNER_EMAIL="' + escaped + '"\n')
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounts-environment", required=True)
    args = parser.parse_args()
    try:
        write_accounts_environment(args.accounts_environment)
    except ValueError as exc:
        parser.exit(1, str(exc) + "\n")
