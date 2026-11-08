#!/bin/bash
# Sets the Ares (pab) account picture to the Ares bust (brand/ares-avatar.jpg, found from this
# script's own folder), then checks whether avatarsd / iCloud reverts it.
# Run from the repo root with: sudo bash tools/set-avatar.sh
set -u
ACCT=pab
IMG="$(cd "$(dirname "$0")/.." && pwd)/brand/ares-avatar.jpg"

if [ "$(id -u)" -ne 0 ]; then echo "Please run with sudo: sudo bash $0"; exit 1; fi
if [ ! -f "$IMG" ]; then echo "Avatar image not found: $IMG"; exit 1; fi

echo "=== BEFORE ==="
dscl . -read /Users/$ACCT Picture 2>/dev/null
echo -n "JPEGPhoto bytes (before): "; dscl . -read /Users/$ACCT JPEGPhoto 2>/dev/null | wc -c

# 1) clear existing picture attributes
dscl . -delete /Users/$ACCT JPEGPhoto 2>/dev/null
dscl . -delete /Users/$ACCT Picture   2>/dev/null

# 2) set the file path
dscl . -create /Users/$ACCT Picture "$IMG"

# 3) embed the binary photo (what the login/lock screen actually renders)
TMP="$(mktemp /tmp/avatar.XXXXXX.dsimport)"
printf '0x0A 0x5C 0x3A 0x2C dsRecTypeStandard:Users 2 dsAttrTypeStandard:RecordName externalbinary:dsAttrTypeStandard:JPEGPhoto\n%s:%s\n' "$ACCT" "$IMG" > "$TMP"
dsimport "$TMP" /Local/Default M
rm -f "$TMP"

echo "=== JUST AFTER SETTING ==="
dscl . -read /Users/$ACCT Picture 2>/dev/null
echo -n "JPEGPhoto bytes (after set): "; dscl . -read /Users/$ACCT JPEGPhoto 2>/dev/null | wc -c

echo "=== waiting 15s to see if avatarsd reverts it ==="
sleep 15

echo "=== AFTER WAIT ==="
dscl . -read /Users/$ACCT Picture 2>/dev/null
echo -n "JPEGPhoto bytes (after wait): "; dscl . -read /Users/$ACCT JPEGPhoto 2>/dev/null | wc -c
echo
echo "If 'after wait' still shows ares-avatar.jpg and a small-ish JPEGPhoto byte count,"
echo "it stuck. If it jumped back to ~1588283 bytes / Whiterose, iCloud reverted it."
