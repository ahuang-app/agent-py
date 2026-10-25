"""Database configuration and session helpers for memory persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from super_ai.project_config import (
    ProjectConfigurationError,
    project_config_section,
    required_str,
)

DEFAULT_MEMORY_DATABASE_URL = "sqlite+aiosqlite:///./var/memory.sqlite3"


@dataclass(frozen=True, slots=True)
class MemoryDatabaseSettings:
    """Runtime database settings for memory persistence."""

    database_url: str = DEFAULT_MEMORY_DATABASE_URL


def load_memory_database_settings(config_path: Path | str | None = None) -> MemoryDatabaseSettings:
    """Load memory database settings from the repository project config."""
    try:
        backend_config = project_config_section("backend", config_path=config_path)
        database_url = required_str(backend_config, "memoryDatabaseUrl")
    except ProjectConfigurationError as exc:
        raise RuntimeError(str(exc)) from exc
    return MemoryDatabaseSettings(database_url=database_url)


def create_memory_engine(
    database_url: str | None = None,
    *,
    echo: bool = False,
    config_path: Path | str | None = None,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine for memory persistence."""
    settings = load_memory_database_settings(config_path) if database_url is None else None
    resolved_url = settings.database_url if settings is not None else database_url
    if resolved_url is None:
        resolved_url = DEFAULT_MEMORY_DATABASE_URL
    connect_args: dict[str, object] = {}
    if resolved_url.startswith("sqlite"):
        # 后台 worker 写任务状态时与读请求竞争数据库锁；加长 busy timeout
        # 让读侧等待写事务提交，而不是立刻抛 "database is locked"（实测表现为瞬时 500）。
        connect_args["timeout"] = 30
    return create_async_engine(resolved_url, echo=echo, connect_args=connect_args)


def create_memory_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for repository implementations."""
    return async_sessionmaker(engine, expire_on_commit=False)
