from __future__ import annotations

from enum import Enum


HIDDEN_WORD = "<hidden>"


class RevealMode(str, Enum):
    NONE = "none"
    CORRECT_ONLY = "correct-only"
    ALL = "all"


def cycle_reveal_mode(mode: RevealMode) -> RevealMode:
    if mode == RevealMode.NONE:
        return RevealMode.CORRECT_ONLY
    if mode == RevealMode.CORRECT_ONLY:
        return RevealMode.ALL
    return RevealMode.NONE


def reveal_status_line(mode: RevealMode) -> str:
    return f"Reveal: {mode.value}"
