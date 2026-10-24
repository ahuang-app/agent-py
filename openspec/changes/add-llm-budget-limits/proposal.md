# 提案：add-llm-budget-limits（应用侧 LLM 预算限额）

## Why

平台当前所有 Qwen 调用（对话、AIOps 诊断、记忆压缩、索引 embedding、检索 embedding）都不计量、不限额。一旦部署到公开环境，任何注册用户都能无限消耗账号的 API 额度。需要一个应用侧的用量记账与预算控制层，作为平台限额（账号级限流/资源包）之外的兜底防线。

## What Changes

- 新增 SQLite 用量台账表 `llm_usage_events`（owner、kind、input/output/total tokens、是否估算、时间），配套 Alembic 迁移与 owner-scoped Repository。
- 新增 `LlmBudgetService`：调用前校验"每用户每日预算"与"全局每月预算"，调用后记录实际/估算用量；超限抛出专用异常并映射为统一错误码 `BUSINESS_LLM_BUDGET_EXCEEDED`（HTTP 429，SSE 复用同一错误结构）。
- 配置新增 `llm.budget` 节：`perCallMaxOutputTokens`（每次调用输出上限，写入 chat 模型 `max_tokens`）、`perUserDailyTokens`、`globalMonthlyTokens`；三者均可为空表示不限额。模板、加载校验同步。
- 记账接线：chat 流式最终消息的真实 usage（开启 `stream_usage`）；AIOps 与记忆压缩 `ainvoke` 响应的真实 usage；embedding 用 LangChain `count_tokens_approximately` 估算（EmbeddingModel 协议不返回 usage）。rerank 本提案只记录输入 token 估算。
- 强制点：chat 发送前、AIOps 诊断每个 LLM 节点前、记忆压缩前。超限调用被明确拒绝，不产生半截回答。
- 共享契约 `errors.ts` 新增 `BUSINESS_LLM_BUDGET_EXCEEDED`；前端无需新页面，超限错误经现有统一反馈与 SSE error 事件展示。

## Capabilities

### New Capabilities

- `llm-usage-budgets`：LLM 用量记账与预算限制（per-call 上限、每用户每日预算、全局每月预算、超限拒绝语义、用量台账 owner 隔离）。

### Modified Capabilities

- 无（不修改既有主规格的行为边界；chat/AIOps 既有 SSE 契约不变，仅新增一种 error code 取值）。

## Impact

- 后端：`llm/`（配置、模型创建）、`chat/streaming.py`、`chat/memory.py`、`aiops/diagnostics.py`、`api/app.py`（embedding 记账 + 服务装配）、`memory/`（新 Repository）、`error_catalog.py`、Alembic 迁移。
- 共享契约：`packages/api-contracts/src/errors.ts` 及错误目录测试。
- 前端：无结构性改动；复用现有错误展示。
- 配置：`config/project.template.json`、`config/user.project.template.json`、`llm/config.py` 校验、`docs/operations-and-monitoring.md` 运维说明。
