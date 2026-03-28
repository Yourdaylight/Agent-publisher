"""Extension registry — auto-discovers extensions under extensions/*/extension.py."""
from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from agent_publisher.extensions._base import Extension

logger = logging.getLogger(__name__)

__all__ = ["Extension", "registry"]


class ExtensionRegistry:
    """Singleton that discovers, validates and registers extensions."""

    def __init__(self) -> None:
        self._extensions: list[Extension] = []

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_and_load(self) -> None:
        """Scan ``extensions/*/extension.py`` and safely import each one.

        Safe to call multiple times — already-loaded extension names are skipped.
        """
        loaded_names = {e.name for e in self._extensions}
        ext_root = Path(__file__).parent
        for candidate in sorted(ext_root.iterdir()):
            if not candidate.is_dir() or candidate.name.startswith("_"):
                continue
            module_path = candidate / "extension.py"
            if not module_path.exists():
                continue
            dotted = f"agent_publisher.extensions.{candidate.name}.extension"
            try:
                mod = importlib.import_module(dotted)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to import extension '%s': %s", candidate.name, exc)
                continue

            # Expect a module-level ``extension`` instance or an ``Extension`` subclass
            ext_obj: Extension | None = getattr(mod, "extension", None)
            if ext_obj is None:
                # Try to find a subclass and instantiate it
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, Extension)
                        and attr is not Extension
                    ):
                        ext_obj = attr()
                        break

            if ext_obj is None:
                logger.warning("Extension module '%s' has no Extension instance", candidate.name)
                continue

            # Skip if already loaded (safe for multiple calls)
            if ext_obj.name in loaded_names:
                continue

            ok, reason = ext_obj.check_dependencies()
            if not ok:
                logger.warning(
                    "Extension '%s' disabled: %s", ext_obj.name or candidate.name, reason
                )
                continue

            self._extensions.append(ext_obj)
            logger.info("Extension '%s' v%s loaded", ext_obj.name, ext_obj.version)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_all(self, app: Any) -> None:  # noqa: ANN401
        """Call ``register_routes`` on every loaded extension."""
        for ext in self._extensions:
            try:
                ext.register_routes(app)
                logger.info("Extension '%s' routes registered", ext.name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to register routes for '%s': %s", ext.name, exc)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_metadata(self) -> list[dict[str, Any]]:
        return [ext.metadata() for ext in self._extensions]

    def __len__(self) -> int:
        return len(self._extensions)


registry = ExtensionRegistry()
