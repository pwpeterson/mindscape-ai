"""Prompt scanning + token estimation utilities.

Task 21: Prompt management: scan configurable directories + per-file token counts.

Notes:
- Token counting is approximate by default (no tokenizer dependency).
- We avoid reading arbitrarily large files by enforcing size limits.
- This module does not accept client-supplied filesystem paths.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from mindscape_ai.prompts.fs import PromptFileInfo


class PromptsStatsError(RuntimeError):
    """Raised when prompt scanning/stat computation fails."""


@dataclass(frozen=True)
class PromptFileStats:
    relpath: str
    bytes: int
    mtime_ns: int
    is_text: bool
    char_count: int | None
    line_count: int | None
    approx_tokens: int | None


def _looks_binary(sample: bytes) -> bool:
    # Heuristic: NUL byte suggests binary.
    return b"\x00" in sample


def _approx_tokens_for_text(text: str) -> int:
    """Approximate token count.

    Heuristic:
        - Roughly 4 characters per token for English-ish text.
        - Ensure non-empty strings return at least 1.

    This is intentionally simple; a future improvement can add optional tokenizer support.
    """
    n = len(text)
    if n <= 0:
        return 0
    return max(1, int(math.ceil(n / 4)))


def _read_text_limited(path: Path, *, max_bytes: int) -> tuple[bool, str]:
    """Read a file with a hard byte cap.

    Returns:
        (is_text, decoded_text)

    If the file looks binary, returns (False, "").
    """
    try:
        with path.open("rb") as f:
            raw = f.read(max_bytes)
    except OSError as exc:
        raise PromptsStatsError(f"Unable to read file: {path}") from exc

    if _looks_binary(raw):
        return False, ""

    # Decode as UTF-8 with replacement to be robust.
    text = raw.decode("utf-8", errors="replace")
    return True, text


def compute_file_stats(
    base_dir: Path,
    info: PromptFileInfo,
    *,
    max_file_bytes: int,
) -> PromptFileStats:
    """Compute stats for a single prompt file.

    Args:
        base_dir: Directory that the relpath is relative to.
        info: File info (metadata only).
        max_file_bytes: Maximum bytes to read for token estimation.

    Returns:
        PromptFileStats.
    """
    path = (base_dir / info.relpath).resolve()

    # If file is huge, skip deep inspection but still report bytes/mtime.
    if info.bytes > max_file_bytes:
        return PromptFileStats(
            relpath=info.relpath,
            bytes=info.bytes,
            mtime_ns=info.mtime_ns,
            is_text=True,
            char_count=None,
            line_count=None,
            approx_tokens=None,
        )

    is_text, text = _read_text_limited(path, max_bytes=max_file_bytes)
    if not is_text:
        return PromptFileStats(
            relpath=info.relpath,
            bytes=info.bytes,
            mtime_ns=info.mtime_ns,
            is_text=False,
            char_count=None,
            line_count=None,
            approx_tokens=None,
        )

    char_count = len(text)
    line_count = text.count("\n") + (1 if text else 0)
    approx_tokens = _approx_tokens_for_text(text)

    return PromptFileStats(
        relpath=info.relpath,
        bytes=info.bytes,
        mtime_ns=info.mtime_ns,
        is_text=True,
        char_count=char_count,
        line_count=line_count,
        approx_tokens=approx_tokens,
    )
