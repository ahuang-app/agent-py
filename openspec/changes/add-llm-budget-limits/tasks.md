# 任务：add-llm-budget-limits

## 1. 持久化与配置

- [x] 1.1 新增 Alembic revision：创建 `llm_usage_events` 表及两个索引，`alembic upgrade head` 可从全新库执行
- [x] 1.2 新增 `LlmUsageEvent` ORM 模型与 owner-scoped Repository（append、owner 日聚合、全局月聚合、按 owner 删除），查询显式 owner scope
- [x] 1.3 `llm/config.py` 增加 `LlmBudgetConfig`（三字段 `int | None`）与非法值校验（≤0 或非整数报 `LlmConfigurationError`），接入 `load_llm_provider_config` 与 project_config 深合并链路
- [x] 1.4 更新 `config/project.template.json` 与 `user.project.template.json` 增加 `llm.budget` 节（三值留空），`/config/check` 脱敏诊断包含预算节

## 2. 预算服务与错误目录

- [x] 2.1 `error_catalog.py` 新增 `BUSINESS_LLM_BUDGET_EXCEEDED`（business/429/安全中文消息）；共享契约 `packages/api-contracts/src/errors.ts` 同步并补错误目录测试
- [x] 2.2 实现 `llm/budget.py`：`LlmBudgetExceededError`、`LlmBudgetService.ensure_within_budget / record_usage`（每日按 owner、每月全局，`now` 显式参数，超限消息区分个人/全局额度），单测覆盖边界（预算内、恰好达到、跨 UTC 日/月恢复、未配置放行、owner 隔离、估算与真实混合记账）

## 3. 接线

- [x] 3.1 `_create_chat_openai_model` 开启 `stream_usage` 并应用 `perCallMaxOutputTokens`；chat 流在发送前校验预算、最终消息持久化处记账（真实 usage 优先、缺失时估算并标 `estimated`），SSE error 与 HTTP 同码
- [x] 3.2 AIOps 诊断 LLM 节点（planner/report）调用前校验、响应后记账；超限作为任务失败原因安全持久化，补 worker 失败路径测试
- [x] 3.3 记忆压缩 `ainvoke` 前校验、后记账，补压缩被拒时的回滚/无副作用测试
- [x] 3.4 索引与检索 embedding 记账（`count_tokens_approximately` 估算、`estimated=true`），不阻断执行，补记账断言测试
- [x] 3.5 API 装配：服务注入 FastAPI 依赖链，确保所有调用点经依赖提供者获取

## 4. 验证与文档

- [x] 4.1 后端门禁：`uv run ruff check .`、`uv run pyright`、`uv run pytest` 全绿；`alembic upgrade head` 从全新库验证
- [x] 4.2 契约门禁：`npm run contracts:typecheck` 与契约测试全绿（新错误码）
- [x] 4.3 前端门禁：`npm run frontend:typecheck`、`frontend:test`、`frontend:build` 全绿（超限错误经现有反馈组件展示）
- [x] 4.4 `openspec validate --all` 通过
- [x] 4.5 `docs/operations-and-monitoring.md` 补充预算配置说明与运维调整方式；README 配置说明同步 `llm.budget`
