"""Centralized version info — reads from pyproject.toml + git commit hash."""

from __future__ import annotations

import subprocess
from functools import lru_cache
from importlib.metadata import version as pkg_version


def _get_package_version() -> str:
    """Get version from installed package metadata, fallback to pyproject.toml."""
    try:
        return pkg_version("agent-publisher")
    except Exception:
        pass
    # Fallback: read pyproject.toml directly
    try:
        from pathlib import Path
        import re

        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        text = pyproject.read_text()
        m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "0.0.0"


def _get_git_short_hash() -> str | None:
    """Return the short git commit hash, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


@lru_cache(maxsize=1)
def get_version_info() -> dict:
    """Return version info dict (cached for the lifetime of the process)."""
    ver = _get_package_version()
    commit = _get_git_short_hash()
    display = f"v{ver}"
    if commit:
        display = f"v{ver} ({commit})"
    return {
        "version": ver,
        "commit": commit,
        "display": display,
    }
