"""The media library, as tools: its pictures and sounds, the pools a popup draws from, and
each poke's and question's picks, by its action's id."""

from __future__ import annotations

from pathlib import Path

from proki.engine import Engine
from proki.services.media import Library
from proki.tools.base import Tool

KEYS = {"type": "array", "items": {"type": "string"}}
ID   = {"type": "string"}


def tools(library: Library, engine: Engine) -> list[Tool]:
    """Reading the library, adding to it, renaming and removing from it, then its pools and picks."""
    return [
        Tool("get_media", "What's in the media library, and how many in all (`total`): of a kind, the "
                          "ones of `keys` (in their order), else yours first, the newest first. A page of it: "
                          "from `offset`, `limit` of them. Each picture or sound's key, name, kind, file and "
                          "added_by (dev or you).",
             {"kind": {"type": "string", "enum": ["image", "sound"]}, "keys": KEYS,
              "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 200}},
             lambda args: dict(zip(("media", "total"), library.get(args.get("kind"), args.get("keys"), args.get("offset", 0), args.get("limit")))),
             readonly=True),
        Tool("add_media", "A picture (gif, png, jpg, webp) or a sound (mp3, wav, ogg) of yours in the library: "
                          "a copy of the file at `path`. Its key.", {"path": {"type": "string"}},
             lambda args: {"key": library.add(Path(args["path"]).expanduser())}, ("path",)),
        Tool("rename_media", "A picture's or a sound's name, what you see: its key, what picks and pools "
                             "know it by, stays.", {"key": ID, "name": {"type": "string"}},
             lambda args: library.rename(args["key"], args["name"]), ("key", "name")),
        Tool("remove_media", "Pictures or sounds deleted: out of the library, and gone for good a week later. "
                             "Not one a poke, a question or a pool still uses: those are `kept`, each with why.",
             {"keys": KEYS}, lambda args: remove(library, engine, args["keys"]), ("keys",), undoable=True),
        Tool("list_pools", "The pools a popup draws a picture from: \"questions\" for every question to you, "
                           "along with its own. Each a list of media (key, name, kind, file, added_by).", {},
             lambda args: {name: library.get(keys=keys)[0] for name, keys in library.pools().items()}, readonly=True),
        Tool("set_pool", "A pool as these keys (in the library).", {"name": {"type": "string"}, "keys": KEYS},
             lambda args: library.set_pool(args["name"], args["keys"]), ("name", "keys")),
        Tool("get_picks", "What a poke or a question draws from as it's shown (one picture and one sound): "
                          "its picks, by its action's `id`: `media`, each picture or sound (key, name, kind, file, added_by).",
             {"id": ID}, lambda args: {"media": library.get(keys=library.get_picks(args["id"]))[0]}, ("id",), readonly=True),
        Tool("set_picks", "A poke's or a question's picks as these keys (in the library), pictures and "
                          "sounds together.", {"id": ID, "keys": KEYS},
             lambda args: pick(library, engine, args["id"], args["keys"]), ("id", "keys")),
    ]


def pick(library: Library, engine: Engine, id: str, keys: list[str]) -> None:
    if id not in popups(engine):
        raise ValueError(f"no poke or question has id {id!r}")
    library.set_picks(id, keys)


def remove(library: Library, engine: Engine, keys: list[str]) -> dict:
    used = {key for id in popups(engine) for key in library.get_picks(id)} | {key for pool in library.pools().values() for key in pool}
    removed, kept = [], {}
    for key in keys:
        try:
            library.remove(key, used)
            removed.append(key)
        except ValueError as e:
            kept[key] = str(e)
    return {"removed": removed, "kept": kept}


def popups(engine: Engine) -> set[str]:
    return {a.id for a in engine.model.specs.actions if a.kind in ("poke", "ask_usr")}
