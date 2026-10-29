"""proki's services, as tools: the LLM and jev, each set by its provider, its key kept on this
computer, where only you can read it. A change is asked from then on.

    get_settings                               each as it's set, and the providers it can have
    test_connection(service, provider, ...)    whether it answers there, with that key
    list_models(service, provider, ...)        the models there
    set_settings(service, provider, model)     kept, and asked from now on

A key left out is the one kept for that provider.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests

from proki import settings
from proki.services.jev import Jev
from proki.settings import Connection, Settings
from proki.tools.base import Tool

SERVICE  = {"type": "string", "enum": list(settings.PROVIDERS), "description": "llm: the LLM a program's asks go to; jev: the service that answers questions for you"}
PROVIDER = {"type": "string", "description": "its provider's id, or custom (get_settings: each one's)"}
URL      = {"type": "string", "description": "a custom provider's address (…/v1); another's is its own"}
KEY      = {"type": "string", "description": "its key (left out: the one kept; empty: none, as for a local service)"}
MODEL    = {"type": "string", "description": "the model's id"}
TIMEOUT  = 10  # seconds a provider has to answer
QUESTION = {"test": {"type": "noul", "instructions": "Is this a test?",  # what testing jev asks
                     "criteria": {"true": "It's a test", "false": "It isn't"}}}


def tools(config: Settings, path: Path = settings.CONFIG_PATH) -> list[Tool]:
    """Reading the services, trying one, its models, and setting it, asked from then on by `config`'s."""
    found = lambda args: where(args["service"], args["provider"], args.get("url"), args.get("key"))
    given = {"service": SERVICE, "provider": PROVIDER, "url": URL, "key": KEY}
    return [
        Tool("get_settings", "Each service as it's set (provider, url, model; null: not set), and the providers it can "
                             "have: name, url, `key` (whether one is kept), and `models` if it can't list them.", {},
             lambda args: read(path), readonly=True),
        Tool("test_connection", "Whether a service answers at a provider, with its key: ok, else the tool's error says "
                                "why. jev's is asked one question, of `model`.", given | {"model": MODEL},
             lambda args: test(args["service"], args["provider"], *found(args), args.get("model")), ("service", "provider"), readonly=True),
        Tool("list_models", "The models at a provider, by id (none: it can't say, so name one).", given,
             lambda args: {"models": models(args["service"], args["provider"], *found(args))}, ("service", "provider"), readonly=True),
        Tool("set_settings", "A service set: its provider, url, key and model, kept, and asked from now on. The services "
                             "then, as get_settings gives them.", given | {"model": MODEL},
             lambda args: save(config, path, **args), ("service", "provider", "model")),
    ]


def read(path: Path) -> dict[str, Any]:
    """The services set at `path` (None: not set), and each one's providers, with whether a key is kept for each."""
    said = settings.read(path)
    return {
        "services" : {service: asdict(said[service]) if service in said else None for service in settings.PROVIDERS},
        "providers": {service: {provider: {**known, "key": settings.key(service, provider) is not None} for provider, known in providers.items()}
                      for service, providers in settings.PROVIDERS.items()},
    }


def where(service: str, provider: str, url: str | None, given: str | None) -> tuple[str, str | None]:
    """A provider's url (custom: `url`), and the key to send: `given`, else the one kept. ValueError
    for a provider there isn't, or a custom one with no url."""
    if provider not in (providers := settings.PROVIDERS[service]):
        raise ValueError(f"{service} has no provider {provider!r} ({', '.join(providers)})")
    url = providers[provider]["url"] or (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"a custom {service} needs its url, http://… or https://… ({url!r})")
    return url.rstrip("/"), settings.key(service, provider) if given is None else given


def models(service: str, provider: str, url: str, key: str | None) -> list[str]:
    """The models at `url`, by id: the ones its provider has, else the ones it lists (at its own
    address for them, if it has one)."""
    known = settings.PROVIDERS[service][provider]
    if "models" in known:
        return known["models"]
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    if provider == "anthropic":
        headers |= {"x-api-key": key or "", "anthropic-version": "2023-06-01"}
    at = known.get("models_url") or f"{url}/models"
    try:
        response = requests.get(at, headers=headers, params={"limit": 1000} if provider == "anthropic" else None, timeout=TIMEOUT)
    except requests.RequestException:
        raise ValueError(f"can't reach {at}") from None
    if response.status_code != 200:
        raise ValueError(refused(at, response))
    try:
        answer = response.json()
    except ValueError:
        raise ValueError(f"{at} doesn't answer JSON") from None
    return sorted({m["id"].removeprefix("models/") for m in answer.get("data", []) if isinstance(m, dict) and m.get("id")})


def test(service: str, provider: str, url: str, key: str | None, model: str | None) -> dict:
    """{"ok": true} if `service` answers at `url` with `key`. ValueError, saying why, if not."""
    if service == "llm":
        return {"ok": True, "models": len(models(service, provider, url, key))}
    model = model or next(iter(models(service, provider, url, key)), None)  # its provider's, else the ones it lists
    if not model:
        raise ValueError("pick a model first (step 3): this provider asks one by name")
    try:
        Jev(url, key, model, timeout=TIMEOUT).ask("a test", QUESTION)
    except requests.HTTPError as e:
        raise ValueError(refused(url, e.response)) from None
    except requests.RequestException:
        raise ValueError(f"can't reach {url}") from None
    except (KeyError, ValueError):
        raise ValueError(f"{url} doesn't answer as jev does") from None
    return {"ok": True}


def save(config: Settings, path: Path, service: str, provider: str, model: str, url: str | None = None, key: str | None = None) -> dict:
    """`service` at `provider` with `model`, kept at `path` (its key kept apart, if given), and
    asked by `config`'s from now on. ValueError for a provider there isn't, or no model."""
    url, _ = where(service, provider, url, "")
    if not model.strip():
        raise ValueError(f"{service} needs a model")
    if key is not None:
        settings.keep(service, provider, key)
    connection = Connection(provider, url, model.strip())
    settings.write(path, settings.read(path) | {service: connection})
    settings.connect(getattr(config, service), connection, settings.key(service, provider))
    return read(path)


def refused(url: str, response: requests.Response) -> str:
    """Why `url` said no, as it says it."""
    status = response.status_code
    try:
        said = response.json().get("error", {})
        said = said.get("message") if isinstance(said, dict) else said
    except (ValueError, AttributeError):
        said = response.text.strip().splitlines()[0] if response.text.strip() else ""
    return (f"the key isn't accepted (HTTP {status})" if status in (401, 403) else f"{url}: HTTP {status}") + (f": {str(said)[:200]}" if said else "")
