"""The programs' model: what you write for each part of the programs (a spec), and the
changes made to them, each kept only if it builds.

    specs       a dataclass for each kind (input, variable, signal, rule, program, state,
                branch, action): its fields, their types, and their JSON Schema
    scope       where a name is written, so it's found from the inside out
    build       the specs made into what runs
    model       add, update, remove (and several together), each change checked
    defaults    the files proki ships, made into specs

A spec is checked twice: its shape when it's made (`parse`: the fields it takes and their
types), and whether it makes sense when it's built, by what runs, as it's made (a rule's
sides, an action's params, an expression's names) and the scopes (a name defined twice, or
hiding another).
"""

from proki.model.build import Builder, Specs
from proki.model.defaults import Defaults
from proki.model.model import Model
from proki.model.specs import Spec

__all__ = ["Builder", "Defaults", "Model", "Spec", "Specs"]
