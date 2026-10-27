"""The engine: your programs, built from their specs and run cycle by cycle.

    Engine(specs, variables, programs, switches, keep, reads)
        specs       the programs' specs, or a folder of their JSON files
        variables   where variables keep their values
        programs    the programs in code
        switches    where the programs switched off are kept
        keep        where the specs are kept when they change
        reads       the names the app reads, each of its type (ConfigError if not)

    engine.cycle(now)           the inputs and signals up to `now`, then the programs due
    engine.close()              proki quitting: until it's back, nothing's known
    engine.model                the specs to change: a change that doesn't build is refused
    engine.switch(name, on)     a program off or on, kept so across builds
    engine.reload()             what runs, built again from the specs

Specs that change run as at a start: every program at its initial state, every signal
from its past. Global variables keep their values.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from proki.core.primitives import Primitive
from proki.core.programs import Program
from proki.core.rules import Rule
from proki.core.signals import Stream, Variable
from proki.core.signals.variable import VariableStore
from proki.errors import ConfigError
from proki.model.build import Builder, Built, Specs
from proki.model.defaults import Defaults
from proki.model.model import Model
from proki.types import Type, accept, typename

REGISTRIES = (Stream.registry, Rule.registry, Program.registry)  # what a build fills


class Switches(Protocol):
    """Where the programs switched off are kept, by name."""

    def load(self) -> set[str]: ...
    def save(self, off: set[str]) -> None: ...


class Engine:
    """Your programs, built from their specs and run (see above)."""

    def __init__(
        self,
        specs    : Specs | Path,
        variables: VariableStore | None = None,
        programs : Iterable[Callable[[], Program]] = (),
        switches : Switches | None = None,
        keep     : Callable[[Specs], None] | None = None,
        reads    : dict[str, Type] | None = None,
    ):
        Variable.store = variables
        self.makers    = list(programs)
        self.reads     = reads or {}
        self.switches  = switches
        self.keep      = keep
        self.off       = switches.load() if switches else set()

        specs          = Defaults(specs).specs() if isinstance(specs, Path) else specs
        self.compiled  = self.build(specs)
        self.model     = Model(specs, check=self.check, changed=self.changed)

    async def cycle(self, now: datetime) -> None:
        """The inputs and signals up to `now`, then the programs whose wait is over."""
        Primitive.run(now)
        Program.tick(now)

    def close(self) -> None:
        """proki quitting: until it's back, nothing's known."""
        for stream in Stream.registry.values():
            stream.close()

    def switch(self, name: str, on: bool) -> None:
        """Program `name` on or off, and kept so. KeyError for one that isn't there."""
        Program.registry[name].switch(on)
        self.off = self.off - {name} if on else self.off | {name}
        if self.switches:
            self.switches.save(self.off)

    def reload(self) -> None:
        """What runs, built again from the specs."""
        self.check(self.model.specs)
        self.run(self.model.specs)

    # --- building -----------------------------------------------------------------------------

    def build(self, specs: Specs) -> Built:
        """What runs, the switched off left off. ConfigError if a name the app reads is wrong."""
        for make in self.makers:
            make()
        built = Builder(specs).build()
        for name, wanted in self.reads.items():
            if (found := Stream.registry.get(name)) is None:    raise ConfigError(f"the app reads {name}: there's none")
            if not accept(wanted, found.type):                  raise ConfigError(f"the app reads {name}, of type {typename(wanted)}: it's of type {typename(found.type)}")
        for name in self.off & set(Program.registry):
            Program.registry[name].switch(False)
        return built

    def check(self, specs: Specs) -> None:
        """ConfigError if `specs` have a mistake. What runs isn't touched."""
        saved, cycle = [dict(registry) for registry in REGISTRIES], Stream.cycle
        clear()
        try:
            self.build(specs)
        finally:
            for registry, kept in zip(REGISTRIES, saved):
                registry.clear()
                registry.update(kept)
            Stream.cycle = cycle

    def changed(self, specs: Specs) -> None:
        """`specs`, checked: kept, and run."""
        if self.keep:
            self.keep(specs)
        self.run(specs)

    def run(self, specs: Specs) -> None:
        """`specs` run in place of what runs, as at a start."""
        Program.stop()
        clear()
        Stream.now = Stream.live = None  # the next cycle starts over, as far back as the longest table
        self.compiled = self.build(specs)


def clear() -> None:
    for registry in REGISTRIES:
        registry.clear()
