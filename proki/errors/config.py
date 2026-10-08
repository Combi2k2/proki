"""Mistakes in what proki is told to run: the config (and its program files), or a signal,
rule or program defined in code. Each is also a `ValueError`: a value proki can't use.

    ConfigError         the config itself: an unknown section or field, a name defined twice, ...
      ExprError         an expression that can't be read, names nothing, or reads itself
      SignalError       a signal or primitive (its window, backfill, ...)
      VariableError     a variable (its name, its starting value)
      RuleError         a rule (its sides, compare operator, softness)
      ProgramError      a program and its states (an unknown state, a state without an exit, ...)
      ActionError       an action (an unknown kind, its params, an expression with a window)
"""

from __future__ import annotations

from proki.errors.base import ProkiError


class ConfigError(ProkiError, ValueError):
    pass


class ExprError(ConfigError):
    pass


class SignalError(ConfigError):
    pass


class VariableError(ConfigError):
    pass


class RuleError(ConfigError):
    pass


class ProgramError(ConfigError):
    pass


class ActionError(ConfigError):
    pass
