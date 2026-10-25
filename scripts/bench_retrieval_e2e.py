"""End-to-end retrieval benchmark with a real corpus through the real pipeline.

流程：
1. 注册/登录专用测试账号（perf-e2e@example.com）
2. 生成 N 份多样化中文运维 Markdown 文档
3. 通过真实 HTTP API 上传并创建索引任务，轮询至全部终态（真实 Qwen embedding + Milvus 写入）
4. 用真实 embedding / Milvus / rerank 构建两把检索工具做 A/B：
   - no-cache：优化前路径（每查询全量拉取 + 重分词 + 重建 BM25L）
   - cached：优化后路径（缓存命中，含一次冷启动）
5. 报告每查询墙钟时间（中位数）与分解

用法：cd apps/backend && python scripts/../../scripts/bench_retrieval_e2e.py
（需在 backend venv 中运行；依赖本机 127.0.0.1:8000 后端与基础设施）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from urllib.parse import quote

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "backend" / "src"))

from super_ai.llm import build_default_llm_provider  # noqa: E402
from super_ai.retrieval import Bm25CorpusCache, KnowledgeRetrievalTool  # noqa: E402
from super_ai.vector_store import build_default_milvus_vector_store  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"
EMAIL = "perf-e2e@example.com"
PASSWORD = "PerfE2E#2026x"

SERVICES = [
    "payment-service", "inventory-service", "order-service", "cart-service",
    "api-gateway", "promotion-service", "auth-service", "search-service",
    "fulfillment-service", "notification-service",
]
FAULTS = [
    "支付网关超时", "库存锁等待", "数据库连接池耗尽", "Redis 延迟飙升", "熔断触发",
    "CPU 饱和", "Kafka 消费积压", "ES 查询超时", "JWK 刷新失败", "上游供应商 503",
    "内存泄漏", "线程池打满", "磁盘 IO 瓶颈", "证书过期", "限流误伤",
]
ACTIONS = [
    "检查上游依赖健康状态并执行降级", "扩容实例并观察 P99 延迟", "回滚最近一次发布",
    "重启进程并确认连接池回收", "清理积压队列后恢复消费", "切换备用节点并验证数据一致性",
    "调高熔断阈值并加强监控告警", "重建索引并核对分片状态",
]

QUERIES = [
    "支付网关超时的根因是什么",
    "数据库连接池耗尽如何排查",
    "Kafka 消费积压的处理步骤",
    "Redis 延迟飙升和熔断的关系",
    "ES 查询超时应该怎么处理",
    "内存泄漏的排查手段",
    "证书过期会导致什么故障",
    "限流误伤的应急动作",
]


def build_document(index: int) -> str:
    service = SERVICES[index % len(SERVICES)]
    fault = FAULTS[(index * 3) % len(FAULTS)]
    action = ACTIONS[(index * 5) % len(ACTIONS)]
    related = SERVICES[(index * 7) % len(SERVICES)]
    other_fault = FAULTS[(index * 11) % len(FAULTS)]
    return (
        f"# {service} {fault} 处理手册\n\n"
        f"## 现象\n{service} 出现{fault}，告警级别 P{'一二'[index % 2]}，"
        f"影响范围包括下游 {related}。\n\n"
        f"## 排查步骤\n1. 检查 {service} 的 QPS 与错误率曲线；\n"
        f"2. 确认是否由{other_fault}引发；\n"
        f"3. 查看日志中的 traceId 并关联 {related} 的调用链。\n\n"
        f"## 处理动作\n{action}。完成后验证 {fault} 是否复现，"
        f"并持续观察 30 分钟的核心指标。\n"
    )


async def ensure_login(client: httpx.AsyncClient) -> str:
    registered = await client.post(
        "/auth/register",
        json={"email": EMAIL, "displayName": "Perf E2E", "password": PASSWORD},
    )
    if registered.status_code not in (200, 201, 409):
        raise RuntimeError(f"register failed: {registered.text}")
    response = await client.post(
        "/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"login failed: {payload}")
    return payload["data"]["accessToken"]


async def upload_and_index(client: httpx.AsyncClient, token: str, count: int) -> None:
    me = (await client.get("/auth/me", headers=_auth(token))).json()["data"]
    kb_id = f"kb_{me['id']}"
    listed = (
        await client.get(f"/knowledge-bases/{kb_id}/documents", headers=_auth(token))
    ).json()["data"]["items"]
    existing_by_name = {item["filename"]: item["id"] for item in listed}
    if len(existing_by_name) >= count:
        print(f"[e2e] 库中已有 {len(existing_by_name)} 份文档，等待既有索引任务收敛")
        while True:
            items = (
                await client.get(
                    f"/knowledge-bases/{kb_id}/documents", headers=_auth(token)
                )
            ).json()["data"]["items"]
            pending_docs = [
                item for item in items if item["indexStatus"] not in {"indexed", "failed"}
            ]
            if not pending_docs:
                failed = [item for item in items if item["indexStatus"] == "failed"]
                if failed:
                    raise RuntimeError(f"{len(failed)} 份文档索引失败")
                break
            await asyncio.sleep(5)
        print("[e2e] 全部文档已索引")
        return

    task_ids: list[tuple[str, str]] = []
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for index in range(count):
            name = f"runbook-{index:04d}.md"
            path = folder / name
            path.write_text(build_document(index), encoding="utf-8")
            with path.open("rb") as handle:
                uploaded = await client.post(
                    f"/knowledge-bases/{kb_id}/documents",
                    headers=_auth(token),
                    files={"file": (name, handle, "text/markdown")},
                    data={"overwrite": "false", "chunking": ""},
                )
            if uploaded.status_code in (200, 201):
                document_id = uploaded.json()["data"]["document"]["id"]
            elif uploaded.status_code == 409:
                # 幂等重入：同名同哈希文档已存在（上次中断的运行），复用并重建索引
                document_id = existing_by_name.get(name)
                if document_id is None:
                    listed = (
                        await client.get(
                            f"/knowledge-bases/{kb_id}/documents", headers=_auth(token)
                        )
                    ).json()["data"]["items"]
                    document_id = next(
                        (item["id"] for item in listed if item["filename"] == name), None
                    )
                if document_id is None:
                    raise RuntimeError(f"duplicate without existing doc for {name}")
                print(f"[e2e] {name} 已存在，复用文档重建索引")
            else:
                raise RuntimeError(f"upload {name} failed: {uploaded.text}")
            _, task_id = await _create_index_task(client, token, kb_id, document_id)
            task_ids.append((document_id, task_id))
        print(f"[e2e] 已排队 {len(task_ids)} 份文档的索引任务")
        await _wait_for_tasks(client, token, kb_id, task_ids)


async def _create_index_task(
    client: httpx.AsyncClient, token: str, kb_id: str, document_id: str
) -> tuple[str, str]:
    task = await client.post(
        f"/knowledge-bases/{kb_id}/documents/{document_id}/index-tasks",
        headers=_auth(token),
    )
    if task.status_code not in (200, 202):
        raise RuntimeError(f"index task failed: {task.text}")
    payload = task.json()["data"]["task"]
    return document_id, payload["id"]


async def _wait_for_tasks(
    client: httpx.AsyncClient,
    token: str,
    kb_id: str,
    task_ids: list[tuple[str, str]],
) -> None:
    pending = set(task_ids)
    deadline = asyncio.get_event_loop().time() + 1800
    while pending:
        if asyncio.get_event_loop().time() > deadline:
            raise RuntimeError(f"index wait timeout with {len(pending)} pending")
        await asyncio.sleep(3)
        still: set[tuple[str, str]] = set()
        for document_id, task_id in pending:
            response = await client.get(
                f"/knowledge-bases/{kb_id}/documents/{document_id}"
                f"/index-tasks/{task_id}",
                headers=_auth(token),
            )
            if response.status_code != 200:
                # 瞬时 500：后台 worker 写任务状态时 SQLite 写锁竞争，稍后重试
                still.add((document_id, task_id))
                continue
            status = response.json()["data"]["status"]
            if status in {"succeeded", "failed", "cancelled"}:
                if status != "succeeded":
                    raise RuntimeError(f"index task {task_id} -> {status}")
            else:
                still.add((document_id, task_id))
        pending = still
        if pending and len(pending) % 20 == 0:
            print(f"[e2e] 剩余索引任务 {len(pending)}")
    print("[e2e] 全部索引任务完成")


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def run_benchmark(owner_user_id: str, rounds: int) -> None:
    from super_ai.retrieval import KnowledgeRetrievalToolInput

    provider = build_default_llm_provider()
    vector_store = build_default_milvus_vector_store()
    kb_ids = [f"kb_{owner_user_id}"]

    no_cache_tool = KnowledgeRetrievalTool(
        embedding_model=provider.create_embedding_model(),
        vector_store=vector_store,
        rerank_model=provider.create_rerank_model(),
    )
    cached_tool = KnowledgeRetrievalTool(
        embedding_model=provider.create_embedding_model(),
        vector_store=vector_store,
        rerank_model=provider.create_rerank_model(),
        corpus_cache=Bm25CorpusCache(ttl_seconds=600),
    )

    async def measure(tool: KnowledgeRetrievalTool, label: str) -> list[float]:
        timings: list[float] = []
        for index in range(rounds):
            query = QUERIES[index % len(QUERIES)]
            started = perf_counter()
            result = await tool.run(
                KnowledgeRetrievalToolInput(query=query),
                owner_user_id=owner_user_id,
                accessible_knowledge_base_ids=kb_ids,
            )
            timings.append(perf_counter() - started)
            assert result.results, f"{label}: query returned no results"
        return timings

    print(f"\n端到端检索 A/B（{rounds} 次查询取中位数，真实 embedding+Milvus+rerank）")
    baseline = await measure(no_cache_tool, "no-cache")
    cold_start = None
    cached_timings: list[float] = []
    for index in range(rounds):
        query = QUERIES[index % len(QUERIES)]
        started = perf_counter()
        await cached_tool.run(
            KnowledgeRetrievalToolInput(query=query),
            owner_user_id=owner_user_id,
            accessible_knowledge_base_ids=kb_ids,
        )
        elapsed = perf_counter() - started
        if index == 0:
            cold_start = elapsed
        else:
            cached_timings.append(elapsed)

    base_ms = statistics.median(baseline) * 1000
    warm_ms = statistics.median(cached_timings) * 1000
    print(f"  no-cache  中位数 {base_ms:8.1f} ms/查询")
    print(f"  cached    冷启动 {(cold_start or 0) * 1000:8.1f} ms（含缓存填充，仅首次）")
    print(f"  cached    热查询 {warm_ms:8.1f} ms/查询")
    print(f"  每查询节省 {base_ms - warm_ms:8.1f} ms（{(base_ms - warm_ms) / base_ms * 100:.0f}%）")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=int, default=120, help="语料文档数量")
    parser.add_argument("--rounds", type=int, default=8, help="每臂查询次数")
    args = parser.parse_args()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
        token = await ensure_login(client)
        await upload_and_index(client, token, args.documents)
        me = (await client.get("/auth/me", headers=_auth(token))).json()["data"]
        await run_benchmark(me["id"], args.rounds)


if __name__ == "__main__":
    asyncio.run(main())
