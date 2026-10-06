"""What proki raises on purpose, one root (base.py: `ProkiError`, with where it happened):
mistakes in the config or definitions (config.py), services that failed (service.py), an
unsupported computer (platform.py). Catch `ProkiError` for all of them, or one group."""

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
