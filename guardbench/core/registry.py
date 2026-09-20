"""Guard registry: register, look up, and enumerate available guards."""

from __future__ import annotations

import importlib.metadata
import logging

from guardbench.core.guard import Guard

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[Guard]] = {}


def register(name: str, cls: type[Guard]) -> None:
    """Register a guard class under the given name."""
    _REGISTRY[name] = cls


def get_guard(name: str, **kwargs: object) -> Guard:
    """Instantiate a registered guard by name, passing kwargs to its constructor.

    Raises KeyError with a helpful message if the name is not registered.
    """
    _load_entry_points()
    if name not in _REGISTRY:
        available = list_guards()
        raise KeyError(
            f"Guard '{name}' not found. Available guards: {available}. "
            "To add a third-party guard, register it in entry_points group 'guardbench.guards'."
        )
    return _REGISTRY[name](**kwargs)


def list_guards() -> list[str]:
    """Return a sorted list of all registered guard names."""
    _load_entry_points()
    return sorted(_REGISTRY.keys())


def _load_entry_points() -> None:
    """Scan Python entry_points group 'guardbench.guards' for third-party guards."""
    try:
        eps = importlib.metadata.entry_points(group="guardbench.guards")
        for ep in eps:
            try:
                cls = ep.load()
                if isinstance(cls, type) and issubclass(cls, Guard):
                    register(ep.name, cls)
            except Exception as exc:  # noqa: BLE001 (intentional resilience boundary)
                logger.warning("Failed to load guard entry_point '%s': %s", ep.name, exc)
    except Exception as exc:  # noqa: BLE001 (intentional resilience boundary)
        logger.debug("entry_points scan failed: %s", exc)
