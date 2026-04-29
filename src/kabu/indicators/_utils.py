"""Shared helpers for the indicator package.

Internal: not part of the public API.
"""

from __future__ import annotations

from collections.abc import Sequence


def require_window(window: int) -> None:
    if window <= 0:
        raise TypeError("window must be a positive integer")


def require_floats(values: Sequence[float]) -> None:
    for i, v in enumerate(values):
        if v is None:
            raise ValueError(f"values[{i}] is None")
        if not isinstance(v, (int, float)):
            raise TypeError(
                f"values[{i}] must be int or float, got {type(v).__name__}"
            )
