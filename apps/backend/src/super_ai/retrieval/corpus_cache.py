"""Tenant-scoped cache for the keyword-recall BM25 corpus.

每次检索都会从 Milvus 拉取该租户的全量 chunk，并重新分词、重建 BM25L 评分器，
三者都是 O(语料) 的每查询成本。此缓存按 (owner, knowledge_base_ids) 维度缓存
chunk 列表、分词结果与评分器，并在向量写入/删除时由调用方显式失效；TTL 只作
为遗漏失效路径的兜底，不是主要失效机制。
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol

from super_ai.retrieval.hybrid import build_bm25_scorer, tokenize_hybrid_text
from super_ai.vector_store import StoredVectorChunk


class StoredChunkLoader(Protocol):
    """Synchronous loader that lists all stored chunks for a prepared tenant scope."""

    def __call__(self) -> list[StoredVectorChunk]: ...


@dataclass(frozen=True, slots=True)
class CorpusRankingContext:
    """Immutable ranking context for one (owner, knowledge base set) key."""

    chunks: tuple[StoredVectorChunk, ...]
    tokenized: tuple[tuple[str, ...], ...]
    # BM25L 评分器来自未标注类型的 rank_bm25 库，随语料一次性构建后只读共享。
    scorer: Any
    created_at: float


class Bm25CorpusCache:
    """Thread-safe corpus cache; loaders run in the caller's worker thread."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 60.0,
        max_entries: int = 64,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must not be negative")
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[tuple[str, tuple[str, ...]], CorpusRankingContext] = {}

    def get_ranking_context(
        self,
        *,
        owner_user_id: str,
        knowledge_base_ids: Sequence[str],
        loader: StoredChunkLoader,
    ) -> CorpusRankingContext:
        key = (owner_user_id, tuple(sorted(knowledge_base_ids)))
        with self._lock:
            entry = self._entries.get(key)
            now = self._clock()
            if entry is not None and now - entry.created_at <= self._ttl_seconds:
                return entry
        chunks = loader()
        tokenized = tuple(tuple(tokenize_hybrid_text(chunk.content)) for chunk in chunks)
        scorer = build_bm25_scorer(tokenized) if chunks else None
        entry = CorpusRankingContext(
            chunks=tuple(chunks), tokenized=tokenized, scorer=scorer, created_at=self._clock()
        )
        with self._lock:
            self._entries[key] = entry
            self._evict_overflow()
        return entry

    def invalidate(
        self,
        *,
        owner_user_id: str,
        knowledge_base_ids: Sequence[str] | None = None,
    ) -> None:
        """Drop cache entries; without knowledge_base_ids every entry of the owner is dropped."""
        with self._lock:
            if knowledge_base_ids is None:
                keys = [key for key in self._entries if key[0] == owner_user_id]
            else:
                keys = [(owner_user_id, tuple(sorted(knowledge_base_ids)))]
            for key in keys:
                self._entries.pop(key, None)

    def _evict_overflow(self) -> None:
        if len(self._entries) <= self._max_entries:
            return
        oldest = sorted(self._entries.items(), key=lambda item: item[1].created_at)
        for key, _ in oldest[: len(self._entries) - self._max_entries]:
            self._entries.pop(key, None)
