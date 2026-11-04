"""Your suggestions for proki, as tools: each kept until it reaches its developer, sent as soon as
this computer is online.

    suggest(text, contact, pictures)    one kept, and sent now if it can be
    send_suggestions                    the ones kept, sent; how many are still waiting
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import requests

from proki import settings
from proki.tools.base import Tool

# where they're sent: the developer's sheet (scripts/vault.gs), deployed
VAULT    = "https://script.google.com/macros/s/AKfycbzPy-8MeN8T7RRjzxjydw3pmulwjnAjQoC6_JbLnvjU3sTRojJNThs1p-d2eSb6d0lX/exec"
OUTBOX   = settings.DATA_DIR / "suggestions.json"  # the ones not sent yet
LONGEST  = 5000                                    # characters a suggestion can have
PICTURES = 3                                       # pictures a suggestion can have
LARGEST  = 2_000_000                               # bytes a picture can have
PICTURE  = re.compile(r"data:image/(?:png|jpeg|webp|gif);base64,[A-Za-z0-9+/]+=*")
TIMEOUT  = 10                                      # seconds the vault has to answer


def tools(path: Path = OUTBOX, vault: str = VAULT) -> list[Tool]:
    """Making a suggestion and sending the ones waiting, kept at `path` until `vault` has them."""
    return [
        Tool("suggest", "A suggestion for Proki's developer: what could be better, in `text`, and how to reach you "
                        "(`contact`, if you want an answer), with up to three pictures of it (`pictures`, each a PNG, JPEG, "
                        "WebP or GIF of 2 MB at most, as a data URL). Kept, and sent as soon as you're online: "
                        "`waiting`, how many aren't sent yet.",
             {"text":     {"type": "string", "maxLength": LONGEST},
              "contact":  {"type": "string", "maxLength": 200},
              "pictures": {"type": "array", "items": {"type": "string"}, "maxItems": PICTURES}},
             lambda args: suggest(path, vault, args["text"], args.get("contact", ""), args.get("pictures", [])), ("text",)),
        Tool("send_suggestions", "The suggestions waiting, sent if you're online: `waiting`, how many still aren't.", {},
             lambda args: {"waiting": send(path, vault)}),
    ]


def suggest(path: Path, vault: str, text: str, contact: str, pictures: list[str]) -> dict:
    if not (text := text.strip()):
        raise ValueError("a suggestion needs a text")
    if len(text) > LONGEST:
        raise ValueError(f"a suggestion has {LONGEST} characters at most ({len(text)} given)")
    if len(pictures) > PICTURES:
        raise ValueError(f"a suggestion has {PICTURES} pictures at most ({len(pictures)} given)")
    for i, picture in enumerate(pictures, 1):
        if not PICTURE.fullmatch(picture):                         raise ValueError(f"picture {i} isn't a PNG, JPEG, WebP or GIF as a data URL")
        if len(picture.partition(",")[2]) * 3 // 4 > LARGEST:      raise ValueError(f"picture {i} is over {LARGEST // 1_000_000} MB")
    kept = json.loads(path.read_text()) if path.exists() else []
    kept.append({"text": text, "contact": contact.strip(), "pictures": pictures, "at": datetime.now().astimezone().isoformat(timespec="seconds")})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(kept, indent=1))
    return {"waiting": send(path, vault)}


def send(path: Path, vault: str) -> int:
    """How many are still waiting, after sending each in turn until one doesn't go."""
    kept = json.loads(path.read_text()) if path.exists() else []
    while kept and vault:
        try:
            said = requests.post(vault, json=kept[0], timeout=TIMEOUT)
            if not said.ok or said.json().get("ok") is not True:  # the vault's own error is a page, not its answer
                break
        except (requests.RequestException, ValueError):
            break
        kept.pop(0)
        path.write_text(json.dumps(kept, indent=1))
    return len(kept)
