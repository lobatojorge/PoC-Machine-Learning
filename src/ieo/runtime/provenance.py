from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ieo.runtime.run_id import RunId


def _sha256_file(path: Path, *, chunk_bytes: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_bytes)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _safe_stat(path: Path) -> dict[str, Any]:
    try:
        st = path.stat()
        return {"bytes": int(st.st_size), "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


@dataclass(frozen=True, slots=True)
class Provenance:
    """
    Provenance (trazabilidad) de una corrida.

    Explicación práctica
    --------------------
    Este archivo te permite contestar “qué se ejecutó, con qué inputs y con qué versión”.
    Es clave si alguien revisa tu trabajo en un tribunal o en una auditoría.
    """

    run_id: RunId
    created_at_utc: str
    python: str
    platform: str
    inputs: list[dict[str, Any]]
    parameters: dict[str, Any]
    packages: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id.value,
            "created_at_utc": self.created_at_utc,
            "python": self.python,
            "platform": self.platform,
            "inputs": self.inputs,
            "parameters": self.parameters,
            "packages": self.packages,
        }


def build_provenance(
    *,
    run_id: RunId,
    input_files: list[Path],
    parameters: dict[str, Any],
    packages: dict[str, str],
    max_hash_files: int | None = 50,
) -> Provenance:
    """
    Construye provenance de la corrida.

    Si hay muchos ficheros (p. ej. miles de .cnv), solo se hashean los primeros
    ``max_hash_files`` para no bloquear la ingesta horas antes del primer Parquet.
  """
    inputs: list[dict[str, Any]] = []
    n = len(input_files)
    hash_limit = n if max_hash_files is None else min(n, max(0, max_hash_files))

    for i, p in enumerate(input_files):
        if i < hash_limit:
            sha = _sha256_file(p) if p.exists() and p.is_file() else None
        else:
            sha = None
        inputs.append({"path": str(p), "sha256": sha, "stat": _safe_stat(p)})

    if n > hash_limit:
        inputs.append(
            {
                "note": (
                    f"{n - hash_limit} ficheros adicionales sin SHA256 en esta corrida "
                    f"(lote grande; ver stat por ruta o ejecutar hash puntual)."
                )
            }
        )

    params = dict(parameters)
    params.setdefault("n_input_files", n)
    if n > hash_limit:
        params["sha256_computed_for"] = hash_limit

    created = datetime.now(timezone.utc).isoformat()
    return Provenance(
        run_id=run_id,
        created_at_utc=created,
        python=sys.version.replace("\n", " "),
        platform=f"{platform.system()} {platform.release()} ({platform.version()})",
        inputs=inputs,
        parameters=params,
        packages=packages,
    )


def write_provenance_json(path: Path, prov: Provenance) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prov.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

