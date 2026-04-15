"""Extension base class for the plugin system."""

from __future__ import annotations

from typing import Any


class Extension:
    """Base class for all extensions.

    Subclasses must set ``name``, ``label``, and ``description`` at the class
    level and implement ``check_dependencies`` and ``register_routes``.
    """

    name: str = ""
    label: str = ""
    description: str = ""
    version: str = "0.1.0"

    # Actions shown on the article list (frontend renders dynamically)
    article_actions: list[dict[str, Any]] = []

    def check_dependencies(self) -> tuple[bool, str]:
        """Return ``(True, "")`` if all runtime deps are available,
        or ``(False, reason)`` otherwise."""
        return True, ""

    def register_routes(self, app: Any) -> None:  # noqa: ANN401
        """Register FastAPI routes. Only called when deps check passes."""

    # ------ helpers for the registry ------

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "version": self.version,
            "article_actions": self.article_actions,
        }
