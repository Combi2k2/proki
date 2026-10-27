"""Building: the programs' specs made into what runs, each name found from its scope.

    Builder(specs).build()   → Built: the inputs, variables, signals, rules and programs

Each spec is made by its kind's method (`claim_input`, ..., `build_branch`): a `claim_` one
claims its name in its scope first, a `build_` one makes a part of a program that has none
(a state, an action, a way out). Each puts what it makes where it belongs: in what's built,
or in its program or state.

In order:

    1. the cycle, and the inputs
    2. the global variables, signals and rules
    3. each program: its own variables, signals and rules, then each of its states: its own
       variables (and the ones its asks answer into), signals and rules, its actions, its
       ways out
    4. every spec of a program or a state in one that's there (`homes`)
    5. every expression compiled, no signal reading itself (`check`)
    6. what each action sets, of its variable's type (`typecheck`)

A name defined twice in a scope is a mistake, and so is anything else wrong as it's made (an
expression's names, a rule's sides, an action's params): each says where its spec is. A
program in code isn't built here: its name starts with "@", which a spec's never does.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from types import UnionType
from typing import Any, ClassVar, Union, get_args, get_origin, get_type_hints, is_typeddict

from proki.core.actions import Action, Context, LValue
from proki.core.primitives import Primitive
from proki.core.programs import Branch, Program, State
from proki.core.rules import Rule
from proki.core.signals import Expr, Signal, Stream, Variable
from proki.core.signals.stream import settle
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
from proki.types import schema
from proki.utils import span


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
    """What the specs make."""

    inputs      : list[Primitive]
    variables   : list[Variable]
    signals     : list[Signal]
    rules       : list[Rule]
    programs    : list[Program]

    @property
    def streams(self) -> list[Stream]:
        """Every stream made: the inputs, variables and signals."""
        return [*self.inputs, *self.variables, *self.signals]


class Builder:
    """Builds `specs` (see above)."""

    def __init__(self, specs: Specs):
        self.scope = Scope()
        self.specs = specs.copy()  # what it declares as it goes (an ask's answer) stays in the build

        # what's made, as it's made
        self.inputs    : list[Primitive]           = []
        self.variables : list[Variable]            = []  # the global ones, then each program's and state's
        self.signals   : list[Signal]              = []  # the same
        self.rules     : list[Rule]                = []  # the global ones (a program's or a state's are its own)
        self.programs  : list[Program]             = []
        self.made      : dict[Stream, Spec]        = {}  # every expression, compiled at the end (`check`), and its spec
        self.acted     : list[tuple[Action, Spec]] = []  # every action, what it sets type checked at the end (`typecheck`)

    # --- the whole ----------------------------------------------------------------------------

    def build(self) -> Built:
        """What the specs make. ConfigError, or one of its kinds, for a mistake, said where it is."""
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
        self.typecheck()

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

    def typecheck(self) -> None:
        """Every type worked out, once all is made, and what each action sets of a type its
        variable takes."""
        settle(list(Stream.registry.values()), again=True)
        for action, spec in self.acted:
            with spec.inside():
                action.typecheck()

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
        """The input, by its name."""
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
            variable = Variable(scope.prefix + spec.name, scope.spell(spec.value), desc=spec.desc, persist=owner is None,
                                type=typed(spec.type))
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
                type     = typed(spec.type),
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
            made    = {s.name: State(s.name, desc=s.desc) for s in states}
            program = Program(spec.name, made, spec.initial, spec.desc, spec.tags, spec.title, spec.icon)
        self.programs.append(program)

        scope = self.scope.inner(spec.name)
        for v in self.owned(self.specs.variables, spec.name):  self.claim_variable(v, scope, program)
        for s in self.owned(self.specs.signals, spec.name):    self.claim_signal(s, scope)
        for r in self.owned(self.specs.rules, spec.name):      self.claim_rule(r, scope, program)
        for state in states:
            self.build_state(state, program, scope.inner(state.name))

    def build_state(self, spec: StateSpec, program: Program, scope: Scope) -> None:
        """Its variables, signals, actions (and the variables they declare, in order: each sees
        those before it), rules, `every` and ways out, in `scope`."""
        state    = program.states[spec.name]
        actions  = [a for a in self.specs.actions if (a.program, a.state) == (spec.program, spec.name)]
        branches = [b for b in self.specs.branches if (b.program, b.state) == (spec.program, spec.name)]

        for v in self.owned(self.specs.variables, spec.program, spec.name):  self.claim_variable(v, scope, state)
        for s in self.owned(self.specs.signals, spec.program, spec.name):    self.claim_signal(s, scope)
        for a in actions:                                                    self.build_action(a, scope, state)
        for r in self.owned(self.specs.rules, spec.program, spec.name):      self.claim_rule(r, scope, state)

        with spec.inside():
            try:
                state.every = span(spec.every)   # 0: its next at once
            except ValueError:
                raise ProgramError(f"every is minutes, 0 or more, or a time: 6s, 5min, 1h ({spec.every!r})") from None
        for i, b in enumerate(branches):
            self.build_branch(b, i, program, state, scope, branches[:i])
        if not branches:
            state.next.append(Branch(program.initial))

    def build_action(self, spec: ActionSpec, scope: Scope, state: State) -> None:
        """The action, the names in its params written out in full for `scope`: a name it sets
        that's nobody's is its state's own, declared as it's made."""
        params = named(spec, lambda kind, name: spell(scope, name) if kind is LValue else scope.spell(name))
        before = set(Stream.registry)
        with spec.inside():
            action = Action.parse({spec.kind: params})
            for name in [n for n in Stream.registry if n not in before and type(Stream.registry[n]) is Variable]:
                if not (name.startswith(scope.prefix) and alone(bare := name.removeprefix(scope.prefix))):
                    raise ProgramError(f"no variable is called {name!r}")
                scope.claim(bare)
                self.variables.append(variable := Stream.registry[name])
                state.vars.append(variable)
        action.id = spec.id
        state.do.append(action)
        self.acted.append((action, spec))

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
    def delta(backfill: Any) -> timedelta | None:
        """A `backfill` (minutes, or a time: "1d"), as a window (None if there's none)."""
        if backfill is None:
            return None
        try:
            window = span(backfill)
        except ValueError:
            window = timedelta(0)
        if window <= timedelta(0):
            raise ConfigError(f"backfill is minutes, more than 0, or a time: 1d, 12h ({backfill!r})")
        return window


def typed(type: Any) -> Any:
    """A spec's type, checked: ConfigError for one there isn't."""
    try:
        schema(type)
    except ValueError as e:
        raise ConfigError(str(e)) from None
    return type


def spell(scope: Scope, name: str) -> str:
    """The full name of a variable an action sets or answers into: the one it means, else, a
    name alone that's nobody's, its state's own."""
    if alone(name) and scope.spell(name) == name and name not in Stream.registry:
        return scope.refer(name) or scope.prefix + name
    return scope.spell(name)


def alone(name: str) -> bool:
    """Whether it's a name alone, not a place in a variable (xs[0].status): one a state can own."""
    return name.isidentifier()


def named(spec: ActionSpec, do: Callable[[type, str], Any]) -> dict:
    """An action's params, each name in them replaced by `do(what it names, name)`: an RValue it
    reads, or an LValue it sets, as its kind's params' types say."""
    made = Action.kinds.get(spec.kind)
    if made is None or not isinstance(spec.params, dict):
        return dict(spec.params) if isinstance(spec.params, dict) else spec.params
    hints = get_type_hints(made.__init__)
    return {k: walked(v, hints.get(k), do) for k, v in spec.params.items()}


def walked(value: Any, hint: Any, do: Callable[[type, str], Any]) -> Any:
    """`value` as `hint` says, its names given to `do` (see `named`)."""
    if isinstance(hint, type) and issubclass(hint, Expr):
        return do(hint, value) if isinstance(value, str) else value
    if hint is Context:
        if isinstance(value, dict) and isinstance(values := value.get("values"), dict):
            return {**value, "values": {k: walked(v, Expr, do) for k, v in values.items()}}
        return value
    if get_origin(hint) in (Union, UnionType):
        return next((walked(value, h, do) for h in get_args(hint) if fits(value, h)), value)
    if is_typeddict(hint) and isinstance(value, dict):
        inner = get_type_hints(hint)
        return {k: walked(v, inner.get(k), do) for k, v in value.items()}
    if get_origin(hint) is dict and isinstance(value, dict):
        return {k: walked(v, get_args(hint)[1], do) for k, v in value.items()}
    if get_origin(hint) is list and isinstance(value, list):
        return [walked(v, get_args(hint)[0], do) for v in value]
    return value


def fits(value: Any, hint: Any) -> bool:
    """Whether `value` is written as `hint` says (the first of a union's that it fits is it)."""
    if isinstance(hint, type) and issubclass(hint, Expr):   return isinstance(value, str)
    if hint is Context:                                     return isinstance(value, str | dict)
    if is_typeddict(hint):                                  return isinstance(value, dict)
    origin = get_origin(hint) or hint
    return isinstance(origin, type) and isinstance(value, origin)
