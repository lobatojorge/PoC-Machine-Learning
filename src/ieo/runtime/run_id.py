from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from secrets import token_hex


@dataclass(frozen=True, slots=True)
class RunId:
    """
    Identificador de corrida (run) para agrupar outputs.

    Explicación práctica
    --------------------
    Cada vez que ejecutes el pipeline se crea un `run_id` único.
    Así puedes comparar ejecuciones sin mezclar archivos.
    """

    value: str


def new_run_id(*, prefix: str = "run") -> RunId:
    """
    Crea un id único, legible y ordenable por tiempo.

    Formato:
        <prefix>-YYYYmmddTHHMMSSZ-<random>
    """

    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rnd = token_hex(4)
    return RunId(f"{prefix}-{now}-{rnd}")

