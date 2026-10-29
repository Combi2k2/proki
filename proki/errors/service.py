"""Something outside proki failed, or answered what proki can't use.

    ServiceError    a service: down, too slow, a reply that isn't what was asked for
      LlmError      an LLM (services/llm.py): no key, every model failed, not JSON
"""

from __future__ import annotations

from proki.errors.base import ProkiError


class ServiceError(ProkiError):
    pass


class LlmError(ServiceError):
    pass
