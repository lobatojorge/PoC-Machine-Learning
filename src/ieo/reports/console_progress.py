"""Barras de progreso y mensajes compactos en consola (stderr)."""

from __future__ import annotations

import sys
from typing import TextIO


def _bar(pct: float, width: int = 30) -> str:
    filled = int(width * max(0.0, min(1.0, pct)))
    return "#" * filled + "-" * (width - filled)


class ProgressBar:
    """Progreso en una línea si hay TTY; si no, hitos cada ~4%."""

    def __init__(self, *, stream: TextIO | None = None, enabled: bool | None = None) -> None:
        self._stream = stream if stream is not None else sys.stderr
        if enabled is None:
            try:
                enabled = self._stream.isatty()
            except Exception:
                enabled = False
        self._tty = bool(enabled)
        self._active = False

    def update(self, current: int, total: int, label: str) -> None:
        if total <= 0:
            return
        pct = current / total
        pct_i = int(pct * 100)
        if self._tty:
            line = (
                f"\r[ieo] {label} [{_bar(pct)}] {current}/{total} ({pct_i}%)   "
            )
            self._stream.write(line)
            self._stream.flush()
            self._active = True
            return
        step = max(1, total // 25)
        if current == 1 or current == total or current % step == 0:
            self._line(f"[ieo] {label}: {current}/{total} ({pct_i}%)")

    def finish(self, label: str, *, detail: str = "") -> None:
        if self._tty and self._active:
            self._stream.write("\n")
            self._stream.flush()
            self._active = False
        msg = f"[ieo] {label}"
        if detail:
            msg = f"{msg} · {detail}"
        self._line(msg)

    def message(self, msg: str) -> None:
        if self._tty and self._active:
            self._stream.write("\n")
            self._stream.flush()
            self._active = False
        self._line(msg)

    def _line(self, msg: str) -> None:
        self._stream.write(msg + "\n")
        self._stream.flush()
