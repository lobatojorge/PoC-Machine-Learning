from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ieo.runtime.run_id import RunId


@dataclass(frozen=True, slots=True)
class RunPaths:
    """
    Rutas estables de una corrida.

    Explicación práctica
    --------------------
    En vez de escribir archivos "sueltos" por el proyecto, todo cae dentro de
    `outputs/runs/<run_id>/`. Si algo falla, tienes el contexto completo.
    """

    project_root: Path
    run_id: RunId

    @property
    def run_root(self) -> Path:
        return self.project_root / "outputs" / "runs" / self.run_id.value

    @property
    def checkpoints_dir(self) -> Path:
        return self.run_root / "checkpoints"

    @property
    def data_dir(self) -> Path:
        return self.run_root / "data"

    @property
    def staging_dir(self) -> Path:
        # Artefactos temporales pero reproducibles (p.ej. CSV normalizado)
        return self.run_root / "staging"

    def ensure(self) -> None:
        for p in (self.run_root, self.checkpoints_dir, self.data_dir, self.staging_dir):
            p.mkdir(parents=True, exist_ok=True)

