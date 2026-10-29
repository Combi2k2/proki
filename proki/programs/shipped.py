"""The programs proki ships, your copy of them, and the defaults you set yourself.

    Shipped(folder, kv).update(model)           new defaults in, the ones you never changed
                                                brought to their default now
    Shipped(folder, kv).default(name)           a program's default, as specs (None: none)
    Shipped(folder, kv).revert(model, name)     a program back to its default
    Shipped(folder, kv).pin(model, name)        a program as it is now, set as its default
    Shipped(folder, kv).unpin(name)             back to the one proki ships

A program is found by its name, and None is the global scope (main.json).

Each default proki ships is recorded as it was last taken (`KEY_SHIPPED`: each file's
JSON). A program still the same as its record is one you never changed: it follows its
default when proki ships a new one. One you changed stays yours. One you removed doesn't
come back: its record says it was taken.

A default you set (`KEY_PINNED`: each program's JSON) is the one it goes back to, in place
of proki's, and a program of your own can have one too. A program with one is yours: what
proki ships next leaves it as it is.
"""

from __future__ import annotations

from pathlib import Path

from proki.errors import ConfigError
from proki.model import Defaults, Model, Specs
from proki.storage import StateDB


class Shipped:
    KEY_SHIPPED = "programs_shipped"   # {file: its JSON, as last taken}
    KEY_PINNED  = "programs_pinned"    # {name (main.json: the global scope): its JSON, as you set it}

    def __init__(self, folder: Path, kv: StateDB):
        """The defaults in `folder` (main.json and a file per program), recorded in `kv`."""
        self.defaults = Defaults(folder)
        self.kv = kv

    def default(self, name: str | None) -> Specs | None:
        """Program `name`'s default, as specs: the one you set, else proki's (None: neither)."""
        pinned = self.pinned().get(self.key(name))
        return self.part(name, pinned) if pinned is not None else self.shipped(name)

    def revert(self, model: Model, name: str | None) -> None:
        """Program `name` back to its default. ValueError if it has none."""
        default = self.default(name)
        if default is None:  raise ValueError(f"{name or 'the global scope'} has no default")

        model.swap(name, default)
        if self.key(name) not in self.pinned():
            self.kv.set(self.KEY_SHIPPED, {**self.taken(), self.file(name): Defaults.dump(default, name)})

    def pin(self, model: Model, name: str | None) -> None:
        """Program `name` as it is now, set as its default. KeyError for one that isn't there."""
        if name is not None and all(p.name != name for p in model.specs.programs):
            raise KeyError(name)
        self.kv.set(self.KEY_PINNED, {**self.pinned(), self.key(name): Defaults.dump(model.specs, name)})

    def unpin(self, name: str | None) -> None:
        """Program `name`'s default, proki's again (none, for one of your own)."""
        self.kv.set(self.KEY_PINNED, {k: v for k, v in self.pinned().items() if k != self.key(name)})

    def update(self, model: Model) -> None:
        """Each default you never had, in, and each one you never changed, brought to its
        default as it is now. Yours, and the ones you removed, stay so."""
        taken, pinned = self.taken(), self.pinned()
        due = []  # (file, name, its default now): the ones to take
        for file in self.files():
            name    = self.name(file)
            now     = Defaults.dump(self.shipped(name), name)
            have    = name is None or any(p.name == name for p in model.specs.programs)
            mine    = Defaults.dump(model.specs, name) if have else None

            new     = not have and file not in taken
            behind  = have and file in taken and mine == taken[file] and taken[file] != now and self.key(name) not in pinned
            if new or behind:               due.append((file, name, now))
            elif not have or mine != now:   taken.setdefault(file, now)  # yours, or removed: it stays so
            else:                           taken[file] = now            # yours is the default

        try:  # together: one may read what another brings (a signal moved from main.json to a program)
            model.swap([name for _, name, _ in due], [self.shipped(name) for _, name, _ in due])
            taken.update({file: now for file, _, now in due})
        except ConfigError:
            for file, name, now in due:  # one at a time: the ones that go with what you have
                try:
                    model.swap(name, self.shipped(name))
                    taken[file] = now
                except ConfigError as e:  # it doesn't go with what you have: yours stays
                    print(f"the default {file} wasn't taken: {e}", flush=True)
        self.kv.set(self.KEY_SHIPPED, taken)

    # --- helpers ------------------------------------------------------------------------------

    def shipped(self, name: str | None) -> Specs | None:
        """Program `name`'s default as proki ships it (None: it ships none)."""
        path = self.defaults.folder / self.file(name)
        return self.part(name, self.defaults.read(path)) if path.exists() else None

    def files(self) -> list[str]:
        """main.json, then each program's file."""
        return [Defaults.MAIN, *sorted(p.name for p in self.defaults.folder.glob("*.json") if p.name != Defaults.MAIN)]

    def taken(self) -> dict:
        """Each default proki ships, as it was last taken, by file."""
        return self.kv.get(self.KEY_SHIPPED, {})

    def pinned(self) -> dict:
        """Each default you set, by name."""
        return self.kv.get(self.KEY_PINNED, {})

    @staticmethod
    def part(name: str | None, data: dict) -> Specs:
        """A file's JSON, as program `name`'s specs."""
        return Defaults.parse(data, {}) if name is None else Defaults.parse({}, {name: data})

    @staticmethod
    def file(name: str | None) -> str:
        """Program `name`'s file."""
        return Defaults.MAIN if name is None else f"{name}.json"

    @staticmethod
    def name(file: str) -> str | None:
        """The name of the program a file is."""
        return None if file == Defaults.MAIN else Path(file).stem

    @staticmethod
    def key(name: str | None) -> str:
        """Program `name`'s key among the pinned (main.json: the global scope, never a program's name)."""
        return name or Defaults.MAIN
