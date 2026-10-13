"""The programs' model: what you write for each node of the programs (a spec), and the
operations that change them, each checked by building it aside before it's kept.

    specs.py      one dataclass per kind of node (input, variable, signal, rule, program,
                  state, branch, action): its fields, their types, and their JSON Schema
    scope.py      Scope: where a name is written, so it's found from the inside out
    build.py      Builder: the specs made into what runs (core/)
    model.py      Model: add, update, remove (and several together), each change checked
    defaults.py   Defaults: the JSON files proki ships, made into specs

A spec is checked twice: its shape when it's made (`parse`: the fields it takes and their
types), and whether it makes sense when it's built, by core/'s own constructors (a rule's
sides, an action's params, an expression's names) and Scope (a name defined twice, or
hiding another).
"""

from proki.model.build import Builder, Built, Specs
from proki.model.model import Model
from proki.model.specs import Spec
from proki.model.defaults import Defaults

__all__ = ["Builder", "Built", "Defaults", "Model", "Spec", "Specs"]
