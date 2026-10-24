# 配置与运维

应用只读取本地 `config/project.json` 和可选的 `config/user.project.json`，不读取本机环境变量。两个文件都被 Git 忽略；仓库只保留不含真实凭据的模板。不要为本项目创建 `.env` 文件，也不要提交本地配置。

首次使用时，在仓库根目录执行：

```bash
cp config/project.template.json config/project.json
cp config/user.project.template.json config/user.project.json
```

## 项目交付后的个人配置

在本地 `config/user.project.json` 中填写使用者自己的模型密钥、CLS 凭据和 CLS 日志目标。其他运行参数可在本地 `config/project.json` 中调整：

| 配置字段 | 替换为 |
| --- | --- |
| `llm.apiKey` | 使用者自己的模型服务密钥 |
| `clsMcpServer.secretId` | 使用者自己的 CLS 凭据 ID |
| `clsMcpServer.secretKey` | 使用者自己的 CLS 凭据密钥 |
| `clsLogUpload.region` | 使用者自己的 CLS 地域 |
| `clsLogUpload.logsetId` | 使用者自己的 CLS 日志集 ID |
| `clsLogUpload.topicId` | 使用者自己的 CLS 主题 ID |

模板中的凭据字段必须保持为空。即使仓库是私有仓库，也不要提交真实密钥；已暴露的密钥应在对应云平台立即轮换。

## LLM 用量预算与公网部署

公开部署实例前，建议在本地 `config/project.json` 中配置 `llm.budget` 预算，防止陌生注册用户无限消耗模型额度：

| 配置字段 | 含义 |
| --- | --- |
| `llm.budget.perCallMaxOutputTokens` | 单次对话/诊断调用的输出 token 上限 |
| `llm.budget.perUserDailyTokens` | 每用户每日（UTC 日界）token 预算，超限拒绝并返回 `BUSINESS_LLM_BUDGET_EXCEEDED` |
| `llm.budget.globalMonthlyTokens` | 全平台每月（UTC 月界）token 预算，超限对所有用户拒绝 |
| `backend.corsAllowOrigins` | 允许的跨域前端来源列表；公网前端域名需加入此列表 |

三个预算字段留空（`null`）即不限额；用量记录在 SQLite `llm_usage_events` 台账中（真实 usage 优先，embedding 为估算值并标记）。台账按用户隔离，可按月归档清理。

## 真实日志与本地告警样例

真实 CLS 日志上传和本地 active-alert 演示属于显式运维流程，不是常规应用启动的一部分。请遵循[真实 CLS 日志与告警教程](tutorials/real-log-and-alert.md)，分别执行其中的日志上传脚本和本地告警命令。
