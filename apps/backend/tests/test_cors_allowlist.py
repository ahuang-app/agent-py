"""Tests for the configurable CORS allowlist resolution."""

import json
from pathlib import Path

import pytest

from super_ai.api.app import resolve_cors_allow_origins
from super_ai.project_config import ProjectConfigurationError

_VALID_BACKEND: dict[str, object] = {
    "host": "127.0.0.1",
    "port": 8000,
    "memoryDatabaseUrl": "sqlite+aiosqlite:///./var/memory.sqlite3",
}


def _write_config(tmp_path: Path, backend: dict[str, object]) -> Path:
    config_path = tmp_path / "project.json"
    config_path.write_text(
        json.dumps({"backend": backend}, ensure_ascii=False),
        encoding="utf-8",
    )
    return config_path


def test_missing_backend_section_falls_back_to_local_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "project.json"
    config_path.write_text(json.dumps({}), encoding="utf-8")

    origins = resolve_cors_allow_origins(config_path)

    assert origins == ["http://127.0.0.1:5173", "http://localhost:5173"]


def test_configured_origins_are_returned(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {
            **_VALID_BACKEND,
            "corsAllowOrigins": ["https://chat.example.com", "http://127.0.0.1:5173"],
        },
    )

    origins = resolve_cors_allow_origins(config_path)

    assert origins == ["https://chat.example.com", "http://127.0.0.1:5173"]


def test_invalid_origin_entries_raise_configuration_error(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {**_VALID_BACKEND, "corsAllowOrigins": ["https://ok.example.com", 42]},
    )

    with pytest.raises(ProjectConfigurationError):
        resolve_cors_allow_origins(config_path)


def test_blank_origin_entries_raise_configuration_error(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {**_VALID_BACKEND, "corsAllowOrigins": ["   "]},
    )

    with pytest.raises(ProjectConfigurationError):
        resolve_cors_allow_origins(config_path)
