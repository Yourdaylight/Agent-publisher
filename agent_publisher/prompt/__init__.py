"""Prompt loading utilities.

Reads base_prompt.md once and caches it for the process lifetime.
The file lives alongside this __init__.py so it's always found relative
to the package, regardless of the working directory.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def load_base_prompt() -> str:
    """Load and cache the base prompt from ``base_prompt.md``.

    Returns an empty string if the file is missing or empty so that
    callers never crash.
    """
    path = _PROMPT_DIR / "base_prompt.md"
    if not path.exists():
        logger.warning("base_prompt.md not found at %s", path)
        return ""
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        logger.warning("base_prompt.md is empty")
        return ""
    logger.info("Loaded base prompt (%d chars) from %s", len(content), path)
    return content
