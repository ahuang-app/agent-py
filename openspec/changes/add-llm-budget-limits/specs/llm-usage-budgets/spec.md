# Delta Spec: llm-usage-budgets

## ADDED Requirements

### Requirement: LLM 用量记账

系统 SHALL 在每次 LLM 调用完成后，将用量事件持久化到 owner-scoped 台账，事件至少包含：当前用户、调用类别（chat / aiops / memory / embedding / rerank）、输入 token 数、输出 token 数、总 token 数、是否为估算值、发生时间。

#### Scenario: 对话回答记录真实用量

- **WHEN** 一次流式对话回答正常完成且模型返回了 usage
- **THEN** 台账新增一条 `kind=chat` 的用量事件，token 数取自模型返回的真实 usage，`estimated` 为 false

#### Scenario: embedding 用量以估算方式记录

- **WHEN** 文档索引或检索查询产生 embedding 调用
- **THEN** 台账新增 `kind=embedding` 事件，token 数按确定性估算器计算并标记 `estimated=true`，同一输入的估算值不变

#### Scenario: 台账按用户隔离

- **WHEN** 用户查询或聚合自己的用量
- **THEN** 结果只包含当前 owner 的台账记录，跨用户访问返回空且不泄露他人用量

### Requirement: 每用户每日预算

配置了 `perUserDailyTokens` 时，系统 SHALL 在发起 LLM 调用前校验：当前用户当日（UTC 日界）已记录的总 token 数与本次调用的预估成本之和不得超过该预算；超出时拒绝调用并返回 `BUSINESS_LLM_BUDGET_EXCEEDED`（HTTP 429）。

#### Scenario: 未超限调用正常放行

- **WHEN** 用户当日用量低于预算且单次预估成本可控
- **THEN** 调用正常执行，行为与本需求生效前一致

#### Scenario: 达到每日预算后明确拒绝

- **WHEN** 用户当日累计用量达到预算，再次发送对话消息
- **THEN** 请求被拒绝，响应为统一错误 envelope（HTTP 与 SSE error 一致），错误码为 `BUSINESS_LLM_BUDGET_EXCEEDED`，消息为安全中文提示，不产生半条助手消息，不写入该条消息

#### Scenario: 次日预算自动恢复

- **WHEN** UTC 日期变更后用户再次调用
- **THEN** 当日计数从零开始，调用放行

### Requirement: 全局每月预算

配置了 `globalMonthlyTokens` 时，系统 SHALL 校验全平台当月（UTC 月界）累计用量；超出时对所有用户拒绝 LLM 调用并返回同一错误码，消息须能让用户区分"全局额度"与"个人额度"两种超限。

#### Scenario: 全局超限影响所有用户且语义可区分

- **WHEN** 全平台当月用量达到全局预算，任一用户发起对话
- **THEN** 拒绝错误中明确标识为全局月度额度超限

### Requirement: 单次调用输出上限

配置了 `perCallMaxOutputTokens` 时，系统 SHALL 将该值作为对话与 AIOps 类 LLM 调用的输出 token 上限传递给模型提供方。

#### Scenario: 输出上限对对话生效

- **WHEN** 配置了 `perCallMaxOutputTokens` 且用户发起对话
- **THEN** 底层模型调用携带该上限，单次回答不会超过该 token 数

### Requirement: 预算配置与降级语义

预算三项均为可选；未配置或为空时系统 SHALL 保持现有限额行为（不限额）。配置值必须为正整数，非法配置 SHALL 在配置校验中明确报错，不静默忽略。

#### Scenario: 未配置预算时行为不变

- **WHEN** `llm.budget` 节缺省或字段为空
- **THEN** 所有 LLM 调用放行，台账记录仍然生效

#### Scenario: 非法预算配置被拒绝

- **WHEN** 预算字段为 0 或负数或非整数
- **THEN** 配置加载/校验给出明确错误，应用拒绝以错误配置启动
