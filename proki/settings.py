"""proki's settings: where its files are, and the two services it asks, each set in the app.

    llm    the LLM a program's asks go to
    jev    the service that answers questions for you

Each is a provider, its address, its key and the model asked there. The keys are kept in a file
only you can read, the rest in the config file. Everything else runs on this machine, as proki
starts it.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import (
    user_config_path,
    user_data_path,
    user_log_path
)

from proki.services.jev import Jev
from proki.services.llm import Llm

ROOT_DIR     = Path(__file__).resolve().parent.parent
BACKEND_DIR  = ROOT_DIR / "proki"
FRONTEND_DIR = ROOT_DIR / "ui"                           # the app

CONFIG_DIR   = user_config_path("proki")
CONFIG_PATH  = CONFIG_DIR / "config.toml"
PROGRAMS_DIR = CONFIG_DIR / "programs"                   # your programs as files, before proki.db kept them (read once)
TOOLS_TOKEN  = CONFIG_DIR / "tools-token"                # what a client of the tools sends, made the first time
KEYS         = CONFIG_DIR / "keys.json"                  # every key, by "service.provider": readable by you only

DATA_DIR     = user_data_path("proki")
DB_PATH      = DATA_DIR / "proki.db"
MEDIA_DIR    = DATA_DIR / "media"                        # the media library's pictures and sounds, each a copy
LOG_DIR      = user_log_path("proki")

SHIPPED_DIR  = BACKEND_DIR / "programs" / "config"       # the programs proki ships
ASSETS_DIR   = BACKEND_DIR / "assets"                    # what proki ships: the media library's, and the providers

HOST         = "127.0.0.1"                               # where ActivityWatch, the message bus and the tools are
AW_PORT      = 5600
NATS_PORT    = 4222
TOOLS_PORT   = 9144

PROVIDERS = {  # each service's, by id: its name, its url (custom: yours), and its models if it can't list them, or where it does
    "llm": json.loads((ASSETS_DIR / "llms.json").read_text()),
    "jev": json.loads((ASSETS_DIR / "jevs.json").read_text()),
}


@dataclass
class Connection:
    """A service as it's set: who provides it, where it is, and the model asked there."""

    provider : str = ""
    url      : str = ""
    model    : str = ""


@dataclass
class Settings:
    """The services proki asks, as they're set: one not set fails every ask."""

    llm : Llm = field(default_factory=lambda: Llm("", None, ""))
    jev : Jev = field(default_factory=lambda: Jev(""))


def load(path: Path = CONFIG_PATH) -> Settings:
    """The services as set at `path`, each with its key (not set if it says nothing, or if it's missing)."""
    made = Settings()
    for service, connection in read(path).items():
        connect(getattr(made, service), connection, key(service, connection.provider))
    return made


def connect(client: Llm | Jev, connection: Connection, key: str | None) -> None:
    """`client` asking `connection` from now on, with `key`."""
    client.api_url = connection.url.rstrip("/")
    client.api_key = key or None
    client.model   = connection.model or (None if isinstance(client, Jev) else "")


def read(path: Path) -> dict[str, Connection]:
    """The services set at `path`, by name (none if it's missing). One whose provider isn't
    known isn't set."""
    said  = tomllib.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    shown = lambda service: Connection(**{k: str(v) for k, v in said[service].items() if k in Connection.__dataclass_fields__})
    return {service: made for service in PROVIDERS
            if isinstance(said.get(service), dict) and (made := shown(service)).provider in PROVIDERS[service]}


def write(path: Path, connections: dict[str, Connection]) -> None:
    """`connections` kept at `path`, the only thing there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"[{service}]\n" + "".join(f"{k} = {json.dumps(v)}\n" for k, v in asdict(connection).items())
                              for service, connection in connections.items()))


def key(service: str, provider: str) -> str | None:
    """The key kept for `service` at `provider` (None: none)."""
    return keys().get(f"{service}.{provider}")


def keys() -> dict[str, str]:
    """Every key kept, by "service.provider" (none: none, or none readable)."""
    try:
        return json.loads(KEYS.read_text())
    except (OSError, ValueError):
        return {}


def keep(service: str, provider: str, given: str) -> None:
    """`given` kept as the key for `service` at `provider` (empty: none kept), where only you can
    read it. ValueError if it can't be written."""
    named = f"{service}.{provider}"
    if not given and named not in keys():
        return
    changed = {k: v for k, v in keys().items() if k != named} | ({named: given} if given else {})
    try:
        KEYS.parent.mkdir(parents=True, exist_ok=True)
        KEYS.touch(mode=0o600)  # yours only before a key's in it
        KEYS.chmod(0o600)
        KEYS.write_text(json.dumps(changed, indent=2))
    except OSError as e:
        raise ValueError(f"the key can't be kept: {e}") from None
