"""Retrieval quality benchmark: success@k, MRR, and the HNSW `ef` trade-off.

对已索引的 perf-e2e 语料（120 份运维手册，见 bench_retrieval_e2e.py）计算检索质量：
- 每个查询的相关文档集合 = 文本包含该查询关键短语的文档（多相关黄金集）
- 指标：success@1 / success@5（top-k 内出现任一相关文档）、MRR（首个相关文档排名倒数）
- ef 实验：同一批查询在 HNSW search ef ∈ {16, 64, 128, 256} 下重跑，观察质量-延迟权衡

用法：cd apps/backend && .venv/Scripts/python.exe ../../scripts/bench_retrieval_quality.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import statistics
import sys
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend" / "src"))

_spec = importlib.util.spec_from_file_location(
    "bench_retrieval_e2e", REPO_ROOT / "scripts" / "bench_retrieval_e2e.py"
)
_e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_e2e)  # type: ignore[union-attr]

from super_ai.llm import build_default_llm_provider  # noqa: E402
from super_ai.retrieval import (  # noqa: E402
    KnowledgeRetrievalTool,
    KnowledgeRetrievalToolInput,
)
from super_ai.vector_store import (  # noqa: E402
    MilvusVectorStore,
    load_milvus_vector_store_settings,
)

BASE_URL = "http://127.0.0.1:8000"
DOCUMENT_COUNT = 120
EF_VARIANTS = (16, 64, 128, 256)

# (查询, 相关性判定的关键短语) —— 相关文档 = 生成文本包含该短语的所有文档
GOLDEN: list[tuple[str, str]] = [
    ("支付网关超时的根因是什么", "支付网关超时"),
    ("数据库连接池耗尽如何排查", "数据库连接池耗尽"),
    ("Kafka 消费积压的处理步骤", "Kafka 消费积压"),
    ("Redis 延迟飙升和熔断的关系", "Redis 延迟飙升"),
    ("ES 查询超时应该怎么处理", "ES 查询超时"),
    ("内存泄漏的排查手段", "内存泄漏"),
    ("证书过期会导致什么故障", "证书过期"),
    ("限流误伤的应急动作", "限流误伤"),
    ("线程池打满后如何恢复", "线程池打满"),
    ("磁盘 IO 瓶颈的定位方法", "磁盘 IO 瓶颈"),
]


def relevant_phrase_sets() -> list[tuple[str, set[int]]]:
    """Map each query to the set of document indices whose text contains the key phrase."""
    corpus = [_e2e.build_document(index) for index in range(DOCUMENT_COUNT)]
    pairs: list[tuple[str, set[int]]] = []
    for query, phrase in GOLDEN:
        relevant = {index for index, text in enumerate(corpus) if phrase in text}
        if not relevant:
            raise RuntimeError(f"golden phrase matched no documents: {phrase}")
        pairs.append((query, relevant))
    return pairs


async def login() -> tuple[str, str]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        await client.post(
            "/auth/register",
            json={
                "email": _e2e.EMAIL,
                "displayName": "Perf E2E",
                "password": _e2e.PASSWORD,
            },
        )
        payload = (
            await client.post(
                "/auth/login", json={"email": _e2e.EMAIL, "password": _e2e.PASSWORD}
            )
        ).json()
        if not payload.get("ok"):
            raise RuntimeError(f"login failed: {payload}")
        token = payload["data"]["accessToken"]
        me = (await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})).json()
        return me["data"]["id"], token


def document_index_by_id(token: str) -> dict[str, int]:
    """Map documentId -> corpus index by re-deriving which file each doc is."""
    import json
    import urllib.request

    request = urllib.request.Request(
        f"{BASE_URL}/knowledge-bases/kb_{_user_id[0]}/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        items = json.load(response)["data"]["items"]
    mapping: dict[str, int] = {}
    for item in items:
        name = item["filename"]
        if name.startswith("runbook-"):
            mapping[item["id"]] = int(name.removeprefix("runbook-").removesuffix(".md"))
    return mapping


_user_id: tuple[str, ...] = ()


async def evaluate(
    tool: KnowledgeRetrievalTool,
    owner_user_id: str,
    golden: list[tuple[str, set[int]]],
    doc_index: dict[str, int],
) -> tuple[float, float, float, float]:
    successes_at_1 = 0
    successes_at_5 = 0
    reciprocal_ranks: list[float] = []
    latencies: list[float] = []
    for query, relevant in golden:
        started = perf_counter()
        result = await tool.run(
            KnowledgeRetrievalToolInput(query=query),
            owner_user_id=owner_user_id,
            accessible_knowledge_base_ids=[f"kb_{owner_user_id}"],
        )
        latencies.append(perf_counter() - started)
        ranks = [
            position
            for position, citation in enumerate(result.citations, start=1)
            if doc_index.get(citation.document_id) in relevant
        ]
        if ranks:
            first = min(ranks)
            successes_at_1 += first == 1
            successes_at_5 += first <= 5
            reciprocal_ranks.append(1 / first)
        else:
            reciprocal_ranks.append(0.0)
    count = len(golden)
    return (
        successes_at_1 / count,
        successes_at_5 / count,
        statistics.mean(reciprocal_ranks),
        statistics.median(latencies) * 1000,
    )


async def main() -> None:
    global _user_id
    owner_user_id, token = await login()
    _user_id = (owner_user_id,)
    golden = relevant_phrase_sets()
    doc_index = document_index_by_id(token)
    print(f"语料 {len(doc_index)} 份文档；黄金集 {len(golden)} 个查询（多相关文档判定）\n")

    provider = build_default_llm_provider()
    print(f"{'ef':>4} | {'success@1':>9} | {'success@5':>9} | {'MRR':>6} | {'中位延迟 ms':>10}")
    print("-" * 52)
    for ef in EF_VARIANTS:
        settings = load_milvus_vector_store_settings()
        vector_store = MilvusVectorStore(
            settings=replace(settings, search_params={"ef": ef})
        )
        tool = KnowledgeRetrievalTool(
            embedding_model=provider.create_embedding_model(),
            vector_store=vector_store,
            rerank_model=provider.create_rerank_model(),
            corpus_cache=None,
        )
        at1, at5, mrr, latency = await evaluate(tool, owner_user_id, golden, doc_index)
        print(f"{ef:>4} | {at1:>10.0%} | {at5:>10.0%} | {mrr:>6.3f} | {latency:>10.1f}")


if __name__ == "__main__":
    asyncio.run(main())
