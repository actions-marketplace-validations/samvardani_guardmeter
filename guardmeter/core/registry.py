"""Guard registry: register, look up, and enumerate available guards."""

from __future__ import annotations

import importlib.metadata
import logging
from collections.abc import Callable

from guardmeter.core.guard import Guard

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[Guard]] = {}
# Namespaced factories for dynamic guard names like ``nvidia:<preset>``.
_RESOLVERS: dict[str, Callable[..., Guard]] = {}


def register(name: str, cls: type[Guard]) -> None:
    """Register a guard class under the given name."""
    _REGISTRY[name] = cls


def register_resolver(prefix: str, factory: Callable[..., Guard]) -> None:
    """Register a factory for a ``prefix:...`` guard namespace (e.g. ``nvidia``).

    The factory is called as ``factory(full_name, **kwargs)`` and returns a Guard.
    """
    _RESOLVERS[prefix] = factory


def get_guard(name: str, **kwargs: object) -> Guard:
    """Instantiate a registered guard by name, passing kwargs to its constructor.

    Exact names win; otherwise a ``prefix:...`` name is dispatched to a
    registered namespace resolver. Raises KeyError with a helpful message if
    neither matches.
    """
    import_builtin_guards()
    _load_entry_points()
    if name in _REGISTRY:
        return _REGISTRY[name](**kwargs)
    if ":" in name:
        prefix = name.split(":", 1)[0]
        factory = _RESOLVERS.get(prefix)
        if factory is not None:
            return factory(name, **kwargs)
    available = list_guards()
    raise KeyError(
        f"Guard '{name}' not found. Available guards: {available}. "
        "To add a third-party guard, register it in entry_points group 'guardmeter.guards'."
    )


def list_guards() -> list[str]:
    """Return a sorted list of all registered guard names."""
    import_builtin_guards()
    _load_entry_points()
    return sorted(_REGISTRY.keys())


def import_builtin_guards() -> None:
    """Import all built-in guard modules so they self-register by name.

    Optional adapters (openai, anthropic, llamaguard) raise ImportError lazily
    in their constructors, not at import, so importing the modules is safe; the
    loop is wrapped in try/except anyway in case a module-level dependency is
    ever added. This lives here (not in the CLI) so the server and other
    non-click callers can trigger registration too.
    """
    import importlib

    import guardmeter.guards.http_guard
    import guardmeter.guards.injection_heuristic
    import guardmeter.guards.regex_guard  # noqa: F401
    for mod in ("openai_moderation", "openai_guard", "llamaguard", "anthropic_guard",
                "nvidia", "ollama"):
        try:
            importlib.import_module(f"guardmeter.guards.{mod}")
        except ImportError:
            pass  # optional dependency not installed


def _load_entry_points() -> None:
    """Scan Python entry_points group 'guardmeter.guards' for third-party guards."""
    try:
        eps = importlib.metadata.entry_points(group="guardmeter.guards")
        for ep in eps:
            try:
                cls = ep.load()
                if isinstance(cls, type) and issubclass(cls, Guard):
                    register(ep.name, cls)
            except Exception as exc:  # noqa: BLE001 (intentional resilience boundary)
                logger.warning("Failed to load guard entry_point '%s': %s", ep.name, exc)
    except Exception as exc:  # noqa: BLE001 (intentional resilience boundary)
        logger.debug("entry_points scan failed: %s", exc)
