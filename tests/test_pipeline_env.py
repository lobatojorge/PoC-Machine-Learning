"""Resolución del alcance del pipeline (IEO_PIPELINE_RADIAL)."""

from __future__ import annotations

import pytest

from ieo.pipeline_env import (
    PIPELINE_RADIAL_ENV,
    resolve_pipeline_scope,
)


@pytest.fixture
def clear_pipeline_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        PIPELINE_RADIAL_ENV,
        "IEO_ONLY_CUDILLERO",
        "IEO_ALL_RADIALS",
    ):
        monkeypatch.delenv(k, raising=False)


def test_resolve_default_all(clear_pipeline_env: None) -> None:
    scope, warns, err = resolve_pipeline_scope()
    assert scope is None
    assert err is None
    assert isinstance(warns, list)


def test_resolve_pipeline_radial_gijon(clear_pipeline_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PIPELINE_RADIAL_ENV, "gijon")
    scope, warns, err = resolve_pipeline_scope()
    assert scope == "gijon"
    assert err is None


def test_resolve_invalid_radial(clear_pipeline_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PIPELINE_RADIAL_ENV, "marsella")
    scope, warns, err = resolve_pipeline_scope()
    assert scope is None
    assert err is not None
    assert "marsella" in err


def test_legacy_only_cudillero(clear_pipeline_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IEO_ONLY_CUDILLERO", "1")
    scope, warns, err = resolve_pipeline_scope()
    assert scope == "cudillero"
    assert err is None


def test_pipeline_radial_wins_over_legacy_only_other(
    clear_pipeline_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PIPELINE_RADIAL_ENV, "santander")
    monkeypatch.setenv("IEO_ONLY_CUDILLERO", "1")
    scope, warns, err = resolve_pipeline_scope()
    assert scope == "santander"
    assert err is None
    assert any("IEO_ONLY_CUDILLERO" in w for w in warns)


def test_resolve_all_radials_redundant_legacy_flag(
    clear_pipeline_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IEO_ALL_RADIALS", "1")
    scope, warns, err = resolve_pipeline_scope()
    assert scope is None
    assert err is None
    assert any("IEO_ALL_RADIALS" in w for w in warns)
