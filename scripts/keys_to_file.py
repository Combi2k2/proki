"""Your keys out of the keychain, once: the item proki kept them all in, moved into the file only
you can read (settings.KEYS), so the keychain never asks again.

    uv run --with keyring python scripts/keys_to_file.py

Run it with proki's own Python, the one that kept them: the keychain gives them to it without
asking. The keys are read back from the file before the item is deleted. Refused while proki
runs, and once done.
"""

import json
import sys

import keyring

from proki import settings
from proki.services.nats import NatsBus

KEYCHAIN = ("proki", "keys")  # where they were

if __name__ == "__main__":
    if NatsBus.is_up(settings.HOST, settings.TOOLS_PORT):
        sys.exit("proki is running: quit it first. Nothing was changed.")
    found = json.loads(keyring.get_password(*KEYCHAIN) or "{}")
    if not found:
        sys.exit("no keys in the keychain: done already. Nothing was changed.")
    for named, given in found.items():
        settings.keep(*named.split(".", 1), given)
    if any(settings.keys().get(named) != given for named, given in found.items()):
        sys.exit("the keys read back aren't the ones kept: they're still in the keychain.")
    keyring.delete_password(*KEYCHAIN)
    print(f"done: {', '.join(found)} in {settings.KEYS}")
