"""Tests for the per-owner MCP tools discovery cache."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

from super_ai.mcp_connections import McpConnectionService
from super_ai.memory.repositories import MemoryRepositories


@dataclass(frozen=True, slots=True)
class _Record:
    id: str
    owner_user_id: str
    name: str
    enabled: bool
    url: str


class _FakeRepository:
    def __init__(self) -> None:
        self.records: dict[str, _Record] = {}

    async def create(self, *, owner_user_id: str, connection_id: str, name: str,
                     transport: str, url: str, enabled: bool, timeout_seconds: int,
                     retries: int) -> _Record:
        record = _Record(id=connection_id, owner_user_id=owner_user_id, name=name,
                         enabled=enabled, url=url)
        self.records[connection_id] = record
        return record

    async def get(self, *, owner_user_id: str, connection_id: str) -> _Record | None:
        record = self.records.get(connection_id)
        return record if record and record.owner_user_id == owner_user_id else None

    async def list(self, *, owner_user_id: str) -> list[_Record]:
        return [r for r in self.records.values() if r.owner_user_id == owner_user_id]

    async def update(self, *, owner_user_id: str, connection_id: str, name: str,
                     transport: str, url: str, enabled: bool, timeout_seconds: int,
                     retries: int) -> _Record | None:
        record = await self.get(owner_user_id=owner_user_id, connection_id=connection_id)
        if record is None:
            return None
        updated = _Record(id=connection_id, owner_user_id=owner_user_id, name=name,
                          enabled=enabled, url=url)
        self.records[connection_id] = updated
        return updated

    async def save_check(self, *, owner_user_id: str, connection_id: str, ok: bool,
                         tools: Sequence[object], error: str | None) -> _Record | None:
        return await self.get(owner_user_id=owner_user_id, connection_id=connection_id)

    async def delete(self, *, owner_user_id: str, connection_id: str) -> bool:
        record = await self.get(owner_user_id=owner_user_id, connection_id=connection_id)
        if record is None:
            return False
        del self.records[connection_id]
        return True


class _CountingClient:
    """LocalMcpClient double counting expensive discovery round trips."""

    def __init__(self) -> None:
        self.discovery_calls = 0

    async def get_langchain_tools(self) -> list[object]:
        self.discovery_calls += 1
        return [f"tool_{self.discovery_calls}"]


def _service(
    repository: _FakeRepository, *, clock: Callable[[], float]
) -> tuple[McpConnectionService, _CountingClient]:
    client = _CountingClient()
    service = McpConnectionService(
        _repositories(repository),
        default_url="http://127.0.0.1:3000/sse",
        default_timeout_seconds=15,
        default_retries=1,
        tools_cache_ttl_seconds=300.0,
        clock=clock,
    )

    async def fake_client_for_user(*, owner_user_id: str) -> _CountingClient:
        return client

    service.client_for_user = fake_client_for_user  # type: ignore[method-assign]
    return service, client


def _repositories(repository: _FakeRepository) -> MemoryRepositories:
    # 只填充 MCP 连接仓储；其余仓储在工具缓存测试中不会被触达。
    return MemoryRepositories(
        chat=cast("object", None),  # type: ignore[arg-type]
        documents=cast("object", None),  # type: ignore[arg-type]
        document_index_tasks=cast("object", None),  # type: ignore[arg-type]
        diagnostics=cast("object", None),  # type: ignore[arg-type]
        mcp_connections=repository,  # type: ignore[arg-type]
    )


async def test_tools_cached_until_invalidated() -> None:
    now = 1000.0
    service, client = _service(_FakeRepository(), clock=lambda: now)

    first = await service.tools_for_user(owner_user_id="user_1")
    second = await service.tools_for_user(owner_user_id="user_1")

    assert first is second
    assert client.discovery_calls == 1


async def test_ttl_expiry_triggers_rediscovery() -> None:
    now = 1000.0

    def clock() -> float:
        return now

    service, client = _service(_FakeRepository(), clock=clock)
    await service.tools_for_user(owner_user_id="user_1")
    now += 301
    await service.tools_for_user(owner_user_id="user_1")
    assert client.discovery_calls == 2


async def test_connection_create_invalidates_cache() -> None:
    repository = _FakeRepository()
    now = 1000.0
    service, client = _service(repository, clock=lambda: now)

    await service.tools_for_user(owner_user_id="user_1")
    await service.create(
        owner_user_id="user_1",
        name="新连接",
        transport="sse",
        url="http://127.0.0.1:4000/sse",
        enabled=True,
        timeout_seconds=15,
        retries=1,
    )
    await service.tools_for_user(owner_user_id="user_1")

    assert client.discovery_calls == 2


async def test_connection_delete_invalidates_cache() -> None:
    repository = _FakeRepository()
    await repository.create(
        owner_user_id="user_1", connection_id="mcp_1", name="cls", transport="sse",
        url="http://127.0.0.1:3000/sse", enabled=True, timeout_seconds=15, retries=1,
    )
    service, client = _service(repository, clock=lambda: 1000.0)

    await service.tools_for_user(owner_user_id="user_1")
    deleted = await service.delete(owner_user_id="user_1", connection_id="mcp_1")
    await service.tools_for_user(owner_user_id="user_1")

    assert deleted
    assert client.discovery_calls == 2


async def test_owners_do_not_share_cache_entries() -> None:
    repository = _FakeRepository()
    service, client = _service(repository, clock=lambda: 1000.0)

    await service.tools_for_user(owner_user_id="user_1")
    await service.tools_for_user(owner_user_id="user_2")

    assert client.discovery_calls == 2
