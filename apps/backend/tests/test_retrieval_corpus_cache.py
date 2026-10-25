"""Tests for the BM25 corpus cache and tokenized ranking path."""

from dataclasses import dataclass
from typing import cast

import pytest

from super_ai.retrieval.corpus_cache import Bm25CorpusCache
from super_ai.retrieval.hybrid import rank_bm25_documents, rank_bm25_tokenized, tokenize_hybrid_text
from super_ai.vector_store import StoredVectorChunk


@dataclass(frozen=True, slots=True)
class _Chunk:
    """Minimal StoredVectorChunk stand-in for cache tests."""

    chunk_id: str
    content: str


class _FakeLoader:
    def __init__(self, chunks: list[_Chunk]) -> None:
        self._chunks = chunks
        self.calls = 0

    def __call__(self) -> list[StoredVectorChunk]:
        self.calls += 1
        return cast("list[StoredVectorChunk]", list(self._chunks))


def _chunks(count: int) -> list[_Chunk]:
    return [
        _Chunk(
            chunk_id=f"chunk_{index}",
            content=(
                f"文档 {index}：Milvus 向量检索与 BM25 关键词召回的组合测试语料，编号 {index}。"
            ),
        )
        for index in range(count)
    ]


def test_get_ranking_context_caches_loader_result() -> None:
    loader = _FakeLoader(_chunks(3))
    cache = Bm25CorpusCache(ttl_seconds=60, clock=lambda: 1000.0)

    first = cache.get_ranking_context(
        owner_user_id="user_1", knowledge_base_ids=["kb_1"], loader=loader
    )
    second = cache.get_ranking_context(
        owner_user_id="user_1", knowledge_base_ids=["kb_1"], loader=loader
    )

    assert loader.calls == 1
    assert first is second
    assert len(second.chunks) == 3


def test_ttl_expiry_triggers_reload() -> None:
    loader = _FakeLoader(_chunks(2))
    now = 1000.0
    cache = Bm25CorpusCache(ttl_seconds=10, clock=lambda: now)

    cache.get_ranking_context(owner_user_id="user_1", knowledge_base_ids=["kb_1"], loader=loader)
    now += 11
    cache.get_ranking_context(owner_user_id="user_1", knowledge_base_ids=["kb_1"], loader=loader)

    assert loader.calls == 2


def test_invalidate_scopes_by_owner_and_knowledge_base() -> None:
    loader = _FakeLoader(_chunks(2))
    cache = Bm25CorpusCache(ttl_seconds=60, clock=lambda: 1000.0)

    cache.get_ranking_context(owner_user_id="user_1", knowledge_base_ids=["kb_1"], loader=loader)
    cache.get_ranking_context(owner_user_id="user_2", knowledge_base_ids=["kb_1"], loader=loader)
    cache.invalidate(owner_user_id="user_1", knowledge_base_ids=["kb_1"])
    cache.get_ranking_context(owner_user_id="user_1", knowledge_base_ids=["kb_1"], loader=loader)
    cache.get_ranking_context(owner_user_id="user_2", knowledge_base_ids=["kb_1"], loader=loader)

    # user_1 失效后重载（+1），user_2 未失效仍命中
    assert loader.calls == 3

    cache.invalidate(owner_user_id="user_1")
    cache.get_ranking_context(owner_user_id="user_1", knowledge_base_ids=["kb_2"], loader=loader)
    # user_1 的全部条目已被清除，kb_2 是新键 → 必然重新加载
    assert loader.calls == 4

    cache.get_ranking_context(owner_user_id="user_2", knowledge_base_ids=["kb_1"], loader=loader)
    assert loader.calls == 4  # user_2 未被失效，命中缓存


def test_rank_bm25_tokenized_matches_plain_ranking() -> None:
    documents = [chunk.content for chunk in _chunks(5)]
    query = "Milvus 向量检索"

    plain = rank_bm25_documents(query=query, documents=documents)
    tokenized = rank_bm25_tokenized(
        query=query,
        corpus_tokens=[tuple(tokenize_hybrid_text(document)) for document in documents],
        documents=documents,
    )

    assert [(rank.index, rank.score) for rank in plain] == [
        (rank.index, rank.score) for rank in tokenized
    ]


def test_rank_bm25_tokenized_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        rank_bm25_tokenized(query="q", corpus_tokens=[("a",), ("b",)], documents=["only-one"])
