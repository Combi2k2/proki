"""The computer proki runs on: `PlatformError`, an OS proki has no support for."""

from __future__ import annotations

from proki.errors.base import ProkiError


class PlatformError(ProkiError, RuntimeError):
    pass
