from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import plotly.graph_objects as go


def save_png(
    fig: go.Figure,
    path: Path,
    *,
    width: int = 1600,
    height: int = 650,
    scale: int = 2,
) -> Tuple[bool, Optional[str]]:
    """
    Guarda una figura Plotly a PNG en alta resolución.

    Devuelve (ok, error). Si kaleido no está disponible u ocurre un error,
    ok=False y error contiene un mensaje breve.
    """
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_image(str(path), width=width, height=height, scale=scale)
        return True, None
    except Exception as exc:
        return False, str(exc)

