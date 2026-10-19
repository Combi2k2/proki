"""Building: the programs' specs made into what runs (core/), each name found from its scope.

    Builder(specs).build()   → Built: the inputs, variables, signals, rules and programs

Each spec is made by the method of its kind (`claim_input`, ..., `build_branch`), which
gives nothing back: it puts what it makes where it belongs, in the builder's lists
(`inputs`, ..., `programs`) or in the program or state it's in. A `claim_` one claims its
name in its scope first. A `build_` one makes a part of a program (a state, an action, a
way out), which has no name in a scope.

In order:

    1. the cycle, and the inputs
    2. the global variables, signals and rules
    3. each program: its own variables, signals and rules, then each of its states: its own
       variables (and the ones its asks answer into), signals and rules, its actions, its
       ways out
    4. every spec of a program or a state checked to be in one that's there (`homes`)
    5. every variable's and signal's expression compiled, and no signal reading itself (`check`)

A name is claimed in its scope as it's made (model/scope.py): one defined twice in a scope
is a mistake. What's built is checked by core/ as it's made (an expression's names, a
rule's sides, an action's params), and a mistake says where its spec is (`Spec.inside`).
A program in code isn't built here: its name starts with "@", which a spec's never does.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, ClassVar

from proki.core.programs import Program, State, Branch
from proki.core.signals import Signal, Stream, Variable
from proki.core.actions import Action
from proki.core.actions.var import Update
from proki.core.primitives import Primitive
from proki.core.rules import Rule
from proki.errors import (
    ConfigError,
    ExprError,
    ProgramError
)
from proki.model.scope import Scope
from proki.model.specs import (
    ActionSpec,
    BranchSpec,
    InputSpec,
    ProgramSpec,
    RuleSpec,
    SignalSpec,
    Spec,
    StateSpec,
    VariableSpec
)


@dataclass
class Specs:
    """Every spec, by kind, in order (a state's ways out and actions, in theirs)."""

    ORDER: ClassVar[tuple[str, ...]] = ("inputs", "variables", "signals", "rules", "programs", "states", "branches", "actions")

    cycle       : float              = 10  # seconds between cycles
    inputs      : list[InputSpec]    = field(default_factory=list)
    variables   : list[VariableSpec] = field(default_factory=list)
    signals     : list[SignalSpec]   = field(default_factory=list)
    rules       : list[RuleSpec]     = field(default_factory=list)
    programs    : list[ProgramSpec]  = field(default_factory=list)
    states      : list[StateSpec]    = field(default_factory=list)
    branches    : list[BranchSpec]   = field(default_factory=list)
    actions     : list[ActionSpec]   = field(default_factory=list)

    def copy(self) -> Specs:
        """A copy whose lists can change without changing these (the specs are the same)."""
        return Specs(self.cycle, *(list(getattr(self, kind)) for kind in Specs.ORDER))


@dataclass
class Built:
    """What the specs make, in core/."""

    inputs      : list[Primitive]
    variables   : list[Variable]
    signals     : list[Signal]
    rules       : list[Rule]
    programs    : list[Program]

    @property
    def streams(self) -> list[Stream]:
        return [*self.inputs, *self.variables, *self.signals]


class Builder:
    """Builds `specs` (see above)."""

    def __init__(self, specs: Specs):
        self.scope = Scope()
        self.specs = specs.copy()  # what it declares as it goes (an ask's answer) stays in the build

        # what's made, as it's made
        self.inputs    : list[Primitive]    = []
        self.variables : list[Variable]     = []  # the global ones, then each program's and state's
        self.signals   : list[Signal]       = []  # the same
        self.rules     : list[Rule]         = []  # the global ones (a program's or a state's are its own)
        self.programs  : list[Program]      = []
        self.made      : dict[Stream, Spec] = {}  # every expression, compiled at the end (`check`), and its spec

    # --- the whole ----------------------------------------------------------------------------

    def build(self) -> Built:
        specs = self.specs
        if isinstance(specs.cycle, bool) or not isinstance(specs.cycle, int | float) or specs.cycle <= 0:
            raise ConfigError(f"cycle is in seconds, more than 0 ({specs.cycle!r})")
        Stream.cycle = timedelta(seconds=specs.cycle)

        for spec in specs.inputs:                   self.claim_input(spec)
        for spec in self.owned(specs.variables):    self.claim_variable(spec, self.scope)
        for spec in self.owned(specs.signals):      self.claim_signal(spec, self.scope)
        for spec in self.owned(specs.rules):        self.claim_rule(spec, self.scope)
        for spec in specs.programs:                 self.claim_program(spec)

        self.homes()
        self.check()

        return Built(self.inputs, self.variables, self.signals, self.rules, self.programs)

    def homes(self) -> None:
        """Every state, way out and action is in a program's state that's there, and every
        variable, signal or rule of a program's or a state's scope too."""
        specs    = self.specs
        programs = {p.name for p in specs.programs}
        states   = {(s.program, s.name) for s in specs.states}
        for spec in [*specs.states, *specs.branches, *specs.actions, *specs.variables, *specs.signals, *specs.rules]:
            prog  = getattr(spec, "program", None)
            state = getattr(spec, "state", None)
            local = getattr(spec, "scope", "state" if state else "program") != "global"
            with spec.inside():
                if prog is not None and (local or isinstance(spec, StateSpec)) and prog not in programs:
                    raise ProgramError(f"no program {prog!r}")
                if state is not None and (prog, state) not in states:
                    raise ProgramError(f"{prog} has no state {state!r}")

    def check(self) -> None:
        """The expressions made compiled: every name they read is defined, and no signal
        reads itself."""
        for stream, spec in self.made.items():
            with spec.inside():
                stream.inputs
        if loop := self.loops(self.made):
            raise ExprError(f"{' → '.join(loop)}: a signal can't read itself")

    @staticmethod
    def loops(streams: Iterable[Stream]) -> list[str] | None:
        """The names around a loop of streams reading each other (a → b → a), if there is one."""
        done: set[Stream]  = set()
        path: list[Stream] = []

        def visit(stream: Stream) -> list[str] | None:
            if stream in done:
                return None
            if stream in path:
                return [s.name for s in [*path[path.index(stream):], stream] if s.name]
            path.append(stream)
            for i in stream.inputs:
                if found := visit(i):
                    return found
            path.pop()
            done.add(stream)
            return None

        return next((found for stream in streams if (found := visit(stream))), None)

    # --- what has a name ----------------------------------------------------------------------

    def claim_input(self, spec: InputSpec) -> None:
        with spec.inside():
            if spec.name not in Primitive.kinds:
                raise ConfigError(f"no input is called {spec.name!r} ({', '.join(Primitive.kinds)})")
            window = self.delta(spec.backfill)
            self.scope.claim(spec.name)
            self.inputs.append(Primitive.kinds[spec.name](backfill=window is not None, window=window))

    def claim_variable(self, spec: VariableSpec, scope: Scope, owner: Program | State | None = None) -> None:
        """The variable in `scope`, `owner`'s (None: global, kept across restarts). Its
        starting expression is compiled at the `check`, like a signal's."""
        with spec.inside():
            scope.claim(spec.name)
            variable = Variable(scope.prefix + spec.name, scope.spell(spec.value), desc=spec.desc, persist=owner is None)
        self.variables.append(variable)
        if owner:
            owner.vars.append(variable)
        if variable.start:
            self.made[variable.start] = spec

    def claim_signal(self, spec: SignalSpec, scope: Scope) -> None:
        """The signal in `scope`, compiled at the `check`, once everything is made (it may
        read signals made after it)."""
        with spec.inside():
            scope.claim(spec.name)
            window = self.delta(spec.backfill)
            if spec.persist and window is None:
                raise ConfigError("persist needs a backfill (how many minutes to keep)")
            signal = Signal(
                scope.prefix + spec.name,
                scope.spell(spec.expr),
                backfill = window is not None,
                window   = window,
                persist  = spec.persist,
                desc     = spec.desc,
            )
        self.signals.append(signal)
        self.made[signal] = spec

    def claim_rule(self, spec: RuleSpec, scope: Scope, owner: Program | State | None = None) -> None:
        """The rule in `scope`, `owner`'s (None: global)."""
        with spec.inside():
            scope.claim(spec.name)
            rule = Rule(
                scope.prefix + spec.name,
                scope.spell(spec.lhs),
                spec.cmp,
                scope.spell(spec.rhs),
                softness = spec.softness,
                level    = spec.level,
                desc     = spec.desc,
            )
        (owner.rules if owner else self.rules).append(rule)

    # --- a program, and its states ------------------------------------------------------------

    def claim_program(self, spec: ProgramSpec) -> None:
        """The program, its own variables, signals and rules, then its states."""
        states = [s for s in self.specs.states if s.program == spec.name]
        with spec.inside():
            self.scope.claim(spec.name)
            self.programs.append(program := Program(spec.name, {s.name: State(s.name, desc=s.desc) for s in states}, spec.initial, spec.desc, spec.tags))

        scope = self.scope.inner(spec.name)
        for v in self.owned(self.specs.variables, spec.name):  self.claim_variable(v, scope, program)
        for s in self.owned(self.specs.signals, spec.name):    self.claim_signal(s, scope)
        for r in self.owned(self.specs.rules, spec.name):      self.claim_rule(r, scope, program)
        for state in states:
            self.build_state(state, program, scope.inner(state.name))

    def build_state(self, spec: StateSpec, program: Program, scope: Scope) -> None:
        """Its variables (the ones its asks answer into declared here, if it doesn't), its
        signals, its rules, its actions, `every` and its ways out, in `scope`."""
        state    = program.states[spec.name]
        actions  = [a for a in self.specs.actions if (a.program, a.state) == (spec.program, spec.name)]
        branches = [b for b in self.specs.branches if (b.program, b.state) == (spec.program, spec.name)]

        mine     = {"scope": "state", "program": spec.program, "state": spec.name}
        declared = {v.name for v in self.owned(self.specs.variables, spec.program, spec.name)}
        for name in dict.fromkeys(filter(None, map(self.reply, actions))):
            if name not in declared:
                with spec.inside():
                    self.specs.variables.append(VariableSpec.parse({"name": name, **mine}))

        for v in self.owned(self.specs.variables, spec.program, spec.name):  self.claim_variable(v, scope, state)
        for s in self.owned(self.specs.signals, spec.program, spec.name):    self.claim_signal(s, scope)
        for r in self.owned(self.specs.rules, spec.program, spec.name):      self.claim_rule(r, scope, state)
        for a in actions:                                                    self.build_action(a, scope, state)

        with spec.inside():
            if isinstance(spec.every, bool) or not isinstance(spec.every, int | float) or spec.every < 0:
                raise ProgramError(f"every is in minutes, 0 or more ({spec.every!r})")   # 0: its next at once
        state.every = timedelta(minutes=spec.every)
        for i, b in enumerate(branches):
            self.build_branch(b, i, program, state, scope, branches[:i])
        if not branches:
            state.next.append(Branch(program.initial))

    def build_action(self, spec: ActionSpec, scope: Scope, state: State) -> None:
        """The action, what it reads written out in full for `scope`: the variable a set /
        add / sub changes, its `expr`, the values of a `context`, and the variable an ask
        answers into (the state's own)."""
        params = dict(spec.params)
        if issubclass(Action.kinds.get(spec.kind, Action), Update) and isinstance(params.get("name"), str):
            params["name"] = scope.spell(params["name"])
        if "expr" in params:
            params["expr"] = scope.spell(params["expr"])
        if isinstance(context := params.get("context"), dict) and isinstance(context.get("values"), dict):
            params["context"] = {**context, "values": {k: scope.spell(v) for k, v in context["values"].items()}}
        if (result := self.reply(spec)) is not None:
            params["result"] = scope.prefix + result
        with spec.inside():
            action = Action.parse({spec.kind: params})
        action.id = spec.id
        state.do.append(action)

    def build_branch(self, spec: BranchSpec, i: int, program: Program, state: State, scope: Scope, before: list[BranchSpec]) -> None:
        """Way out `i` of `state`: its rules (found from the state outwards) and its
        conditions (anything else in its `when`, each a hidden signal)."""
        with spec.inside():
            if spec.goto not in program.states:
                raise ProgramError(f"{program.name} has no state {spec.goto!r}")
            if before and not before[-1].when:
                raise ProgramError("it comes after the else, so it's never taken")
            if not all(isinstance(w, str) and w for w in spec.when):
                raise ProgramError(f"when is a list of rules and conditions ({spec.when!r})")

            full  = {w: scope.refer(w) for w in spec.when}
            rules = [Rule.registry[full[w]] for w in spec.when if full[w] in Rule.registry]
            conds = [Signal(f"{scope.prefix}next:{i}:{j}", scope.spell(w))
                     for j, w in enumerate(w for w in spec.when if full[w] not in Rule.registry)]
            for cond in conds:
                cond.inputs  # compiled now: a mistake shows here
            state.next.append(Branch(spec.goto, rules, conds, spec.desc))

    # --- helpers ------------------------------------------------------------------------------

    def owned(self, specs: Iterable[Any], program: str | None = None, state: str | None = None) -> list:
        """The variables, signals or rules of `program`'s scope (or of its `state`'s, None:
        the global scope's), in order."""
        scope = "state" if state else "program" if program else "global"
        return [s for s in specs if s.scope == scope and (scope == "global" or (s.program, s.state) == (program, state))]

    @staticmethod
    def reply(spec: ActionSpec) -> str | None:
        """The name of the variable an ask answers into, as its state says it ("answer")."""
        result = spec.params.get("result") if spec.kind == "ask" else None
        return result if isinstance(result, str) else None

    @staticmethod
    def delta(backfill: Any) -> timedelta | None:
        """A `backfill` in minutes, as a window (None if there's none)."""
        if backfill is None:
            return None
        if isinstance(backfill, bool) or not isinstance(backfill, int | float) or backfill <= 0:
            raise ConfigError(f"backfill is in minutes, more than 0 ({backfill!r})")
        return timedelta(minutes=backfill)
