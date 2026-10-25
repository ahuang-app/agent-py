"""Benchmark: per-query cost of BM25 keyword recall, before vs after corpus caching.

对比两种每查询路径的真实耗时（不含 Milvus 拉取与 embedding 网络调用）：
- baseline（优化前）：每次查询全量重新分词 + 重建 BM25L 评分器
- cached（优化后）：语料分词与评分器在缓存填充时一次性构建，每查询直接 get_scores

用法：python scripts/bench_retrieval_bm25.py
仅依赖后端既有依赖（rank_bm25），在仓库根目录或任意位置运行均可。
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "backend" / "src"))

from super_ai.retrieval.hybrid import (  # noqa: E402
    build_bm25_scorer,
    rank_bm25_documents,
    rank_bm25_tokenized,
    tokenize_hybrid_text,
)

QUERIES = [
    "支付网关超时的根因是什么",
    "Milvus 向量检索与 BM25 的区别",
    "数据库连接池耗尽如何排查",
    "Kafka consumer lag 过高的处理步骤",
    "ES timeout 与熔断的关系",
]


def synthetic_corpus(chunks: int, chars: int) -> list[str]:
    documents = []
    for index in range(chunks):
        body = (
            f"{index} 号服务的运行手册：支付网关超时通常由上游依赖抖动引起，"
            "需要检查数据库连接池、Redis 延迟、Kafka consumer lag 与 ES 超时；"
            "处理步骤包括熔断降级、扩容与回滚，验证指标恢复后解除告警。"
        )
        documents.append((body * (chars // len(body) + 1))[:chars])
    return documents


def bench_baseline(documents: list[str], rounds: int) -> list[float]:
    timings = []
    for index in range(rounds):
        query = QUERIES[index % len(QUERIES)]
        started = perf_counter()
        rank_bm25_documents(query=query, documents=documents)
        timings.append(perf_counter() - started)
    return timings


def bench_cached(documents: list[str], rounds: int) -> list[float]:
    corpus_tokens = [tuple(tokenize_hybrid_text(document)) for document in documents]
    scorer = build_bm25_scorer(corpus_tokens)
    timings = []
    for index in range(rounds):
        query = QUERIES[index % len(QUERIES)]
        started = perf_counter()
        rank_bm25_tokenized(
            query=query,
            corpus_tokens=corpus_tokens,
            documents=documents,
            scorer=scorer,
        )
        timings.append(perf_counter() - started)
    return timings


def median_ms(values: list[float]) -> float:
    return round(statistics.median(values) * 1000, 2)


def main() -> None:
    rounds = 5
    print(f"每档 {rounds} 次查询取中位数（语料：中文混排运维文本，约 320 字/条）\n")
    print(f"{'语料规模':>8} | {'优化前 ms/查询':>14} | {'优化后 ms/查询':>14} | {'加速比':>6}")
    print("-" * 52)
    for count in (100, 500, 1000):
        documents = synthetic_corpus(count, 320)
        baseline = bench_baseline(documents, rounds)
        cached = bench_cached(documents, rounds)
        before, after = median_ms(baseline), median_ms(cached)
        speedup = round(before / after, 1) if after > 0 else float("inf")
        print(f"{count:>10} | {before:>14} | {after:>14} | {speedup:>5}x")
    print(
        "\n说明：baseline 即优化前每次查询的固定成本（全量分词 + BM25L 重建）；"
        "cached 将该成本移到缓存填充时一次性支付。另需叠加每查询一次的 Milvus 全量拉取"
        "（缓存同样消除，规模相关，未含在本表）。"
    )


if __name__ == "__main__":
    main()
