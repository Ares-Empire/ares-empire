#!/usr/bin/env python3
"""Generate AUTH_PASSWORD_HASH (+ a fresh AUTH_SESSION_SECRET if missing) for the Ares
Empire web login gate. Prints .env lines; does NOT write them (secrets stay out of git).

Usage:  python3 webauth/gen_password.py 'the-password'
Scrypt params match webauth/server.py. (Ported from arestoteles/webauth.)
"""

import hashlib
import os
import secrets
import sys

N, R, P, DKLEN, MAXMEM = 16384, 8, 1, 32, 64 * 1024 * 1024


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=DKLEN, maxmem=MAXMEM)
    # ":" separator (not "$") so the value survives docker-compose env_file interpolation
    return f"scrypt:{salt.hex()}:{dk.hex()}"


if __name__ == "__main__":
    # accept the password from argv OR the AUTH_PASSWORD env var (keeps it out of argv/history)
    pw = sys.argv[1] if len(sys.argv) == 2 else os.environ.get("AUTH_PASSWORD")
    if not pw:
        sys.exit("usage: python3 webauth/gen_password.py 'the-password'   (or set AUTH_PASSWORD)")
    print(f"AUTH_PASSWORD_HASH={hash_password(pw)}")
    if not os.environ.get("AUTH_SESSION_SECRET"):
        print(f"AUTH_SESSION_SECRET={secrets.token_urlsafe(48)}")
