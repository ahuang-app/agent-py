# 设计：add-llm-budget-limits

## Context

- 当前 Qwen 调用点：chat 流式 Agent（`chat/streaming.py`，`create_chat_model()` 传入 LangChain agent）、AIOps 诊断节点（`aiops/diagnostics.py` 两处 `ainvoke`）、记忆压缩（`chat/memory.py` 一处 `ainvoke`）、embedding（索引与检索，经 `create_embedding_model()`）、rerank（独立 HTTP client）。
- 代码库无任何 usage 记账；错误统一走 `error_catalog.py` 的 `ERROR_DEFINITIONS`（code → category/httpStatus/中文默认消息）；配置经 `llm/config.py` 的 `LlmProviderConfig` 强类型加载与校验；持久化遵循 Repository 边界 + Alembic 迁移。
- 项目已有 LangChain `count_tokens_approximately` 纯函数（chat 记忆模块在用），可复用为 embedding 的确定性估算器。

## Goals / Non-Goals

- Goals：调用前预算校验（每用户每日、全局每月）、调用后记账（真实 usage 优先、embedding 估算）、per-call 输出上限、统一错误码与安全中文提示、台账 owner 隔离。
- Non-Goals：不做计费金额换算（只记 token）；不做请求级 rate limit（QPS 由部署侧反代承担）；不改动 SSE 事件结构（仅新增一种 error code 取值）；不给 rerank 记录精确 usage（协议不返回，只记输入估算）。

## Decisions

- **D1 记账与校验集中在 `LlmBudgetService`**（`llm/budget.py`）：`ensure_within_budget(owner_user_id, kind, now=...)` 在调用前抛 `LlmBudgetExceededError`；`record_usage(owner_user_id, kind, input_tokens, output_tokens, *, estimated, now=...)` 调用后记账。`now` 作为显式参数（默认 `_utc_now()`），与 P09 的时钟约定一致，阈值测试不依赖真实时间。
- **D2 台账表**：`llm_usage_events(id, owner_user_id, kind, input_tokens, output_tokens, total_tokens, estimated, created_at)`，`(owner_user_id, created_at)` 与 `(created_at)` 建索引分别支撑每日/每月聚合；Repository 所有查询显式 owner scope，全局月度聚合是唯一跨 owner 查询（仅返回 SUM）。删除用户数据时按现有级联约定同步清理。
- **D3 流式对话的真实 usage**：`_create_chat_openai_model` 开启 `stream_usage`（DashScope 兼容端点支持 `include_usage`）；chat 流在最终 assistant 消息持久化处从最终 AI 消息读取 `usage_metadata` 记账；provider 未返回 usage 时以 `count_tokens_approximately` 估算并标 `estimated=true`。校验时机在 agent 创建前，超限直接抛错，由现有"失败不落半条消息"语义承接。
- **D4 AIOps 与记忆压缩**：两处 `ainvoke` 改经 budget service 的 `ensure + record` 包装；诊断超限作为该次任务失败原因安全持久化（不伪造成功）；owner 取自任务归属。
- **D5 embedding 估算记账**：索引批处理与检索查询处，对送入 embedding 的文本用 `count_tokens_approximately` 估算 input tokens 记账（`estimated=true`），不在校验路径阻断（预算超限时 embedding 仍执行，避免索引任务中途产生半态；预算仅由 chat/aiops/memory 强制）。
- **D6 per-call 上限**：`perCallMaxOutputTokens` 映射为 ChatOpenAI 的 `max_tokens`，对 chat 与 AIOps 的 chat 模型创建统一生效。
- **D7 错误映射**：`error_catalog.py` 新增 `BUSINESS_LLM_BUDGET_EXCEEDED = ("business", 429, "今日模型用量已达到限额，请明天再试或联系管理员调整预算。")`；全局超限时服务层给出可区分的中文消息（错误 envelope 的 message 允许按来源细分，code 不变）；SSE error 复用 HTTP 错误结构（现有机制）。
- **D8 配置**：`LlmProviderConfig` 新增嵌套 `LlmBudgetConfig(per_call_max_output_tokens, per_user_daily_tokens, global_monthly_tokens)`，全部 `int | None`；模板三值留空；加载校验非正整数直接报 `LlmConfigurationError`。同步 `config/check` 的脱敏诊断输出（预算非敏感，可原样展示）。

## Risks / Trade-offs

- 流式 usage 依赖端点支持 `include_usage`；不支持时退化为估算记账（明确标注），不影响预算判断的正确性量级。
- 全局月度聚合查询随数据量增长变慢：按月界做 SUM 且只在该查询用 `(created_at)` 索引，量级（本地/中小部署）可接受；不为过早优化引入汇总表。
- 台账增长：无清理任务（与审计表同等生命周期）；本地优先场景量级可控，运维文档注明可按月归档。

## Open Questions

- 无（预算粒度 UTC 日/月界、三种配置字段、拒绝语义已在提案中确定）。
