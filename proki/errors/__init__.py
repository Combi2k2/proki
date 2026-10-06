"""The errors proki raises on purpose, all under one root, `ProkiError`:

    ProkiError                 any of them (base.py). Its message says where it happened
      ConfigError              a mistake in the config or a definition (config.py)
        ExprError, SignalError, VariableError, RuleError, ProgramError, ActionError
      ServiceError             a service outside proki failed (service.py)
        LlmError
      PlatformError            an operating system proki doesn't support (platform.py)

Catch `ProkiError` for all of them, or one group.
"""

from proki.errors.base import ProkiError
from proki.errors.config import (
    ActionError,
    ConfigError,
    ExprError,
    ProgramError,
    RuleError,
    SignalError,
    VariableError,
)
from proki.errors.platform import PlatformError
from proki.errors.service import LlmError, ServiceError

__all__ = [
    "ProkiError",
    "ConfigError", "ExprError", "SignalError", "VariableError", "RuleError", "ProgramError", "ActionError",
    "ServiceError", "LlmError",
    "PlatformError",
]
