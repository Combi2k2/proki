"""The engine: proki's config, run cycle by cycle.

`Engine(config, ...)` compiles the config (compiler.py) with what the app gives it: where
variables keep their values, and the programs written in code (proki/programs/, made
before the config, which may read their variables). Then `cycle(now)`, every so often:

1. the inputs and signals move on to `now` (`Primitive.run`, from ActivityWatch).
2. the results of slow calls that came since are handed over (`Later.deliver`), answers
   to questions included, on this cycle's values.
3. every program takes its turn (`Program.tick`).

`poll(now)` in between (every few seconds): results again, and the programs in code that
watch what's in focus right now (`Program.poll`).

It knows no UI toolkit: questions and messages go over the bus (core/ask.py, core/ui.py).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from proki.compiler import CONFIG, Compiled, compile_config
from proki.core.later import Later
from proki.core.programs import Program
from proki.core.primitives import Primitive
from proki.core.signals import Variable
from proki.core.signals.variable import VariableStore


class Engine:
    def __init__(
        self,
        config: Path = CONFIG,
        variables: VariableStore | None = None,
        programs: Iterable[Callable[[], Program]] = (),
    ):
        Variable.store = variables
        self.programs = [make() for make in programs]  # programs in code, made before the config, which may read their variables
        self.compiled: Compiled = compile_config(config)

    def cycle(self, now: datetime, context: Any = None) -> None:
        """Everything up to `now`. `context`: for programs in code (`Program.context`), or a
        function that makes it once the signals moved on."""
        Primitive.run(now)
        Later.deliver()
        Program.context = context() if callable(context) else context
        Program.tick(now)

    def poll(self, now: datetime, context: Any = None) -> None:
        """Between cycles, every few seconds: answers, and the programs that watch what's in focus."""
        Later.deliver()
        Program.context = context
        Program.poll_all(now)
