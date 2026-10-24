# 工程日志：2026-10-24 全天工作记录

本文档按时间线完整记录 2026-10-24 在 Agent Py 项目上执行的全部任务、关键决策、遇到的问题与解决方案。所有改动均已通过对应质量门禁并推送到 GitHub（主分支 `main`）。

## 阶段一：项目现状验证与缺陷修复（上午）

### 任务

按"先读文档再动手"原则验证这个本地优先 AIOps 工作台的完整可运行性。

### 完成内容

1. **文档研读**：通读根目录 3 份 md（README、AGENTS.md、OpenSpec 从 0 到 1 提示词），确认仓库是文档所描述系统的完整成品，与用户确认任务范围为"验证并跑通现有系统"而非新建平行系统。
2. **工具链补齐**：本机缺失的 `uv`（pip 安装）与 `openspec` CLI（npm 全局安装）。
3. **依赖安装攻坚**：`uv sync` 在 Windows 失败——锁文件中 `python-snappy` 仅有 cp310 wheel、`lz4==3.1.2` 完全无 wheel（需 MSVC）。解决：`uv sync --python 3.10 --no-install-package lz4`（验证后端运行时不依赖这两个包，仅 fixtures 脚本使用）。
4. **全量门禁执行**：ruff/pyright 0 错误；pytest 发现 4 个失败；contracts 24 通过；前端 82 通过；openspec 42 项通过。

### 修复的真实缺陷（4 项）

| 缺陷 | 修复 |
| --- | --- |
| `.gitignore` 缺少本地配置忽略（真实密钥有入库风险） | 补 `config/project.json`、`config/user.project.json` |
| `config/project.template.json` 含非空 minio 密钥/analytics key | 按脱敏契约清空（确认无代码消费方） |
| Compose 中 Attu 端口 8080 与 README/契约测试的 8001 漂移 | 对齐 8001 |
| `scripts/start-local.bat` 后端端口 8081 漂移（曾导致前端 2 个测试失败） | 对齐 8000 |

另修复本地 `project.json` 的 `apiBaseUrl` 8081→8000（历史上为迁就有缺陷的 .bat 而设）。

### 遗留项（非代码问题）

- `test_posix_launcher_has_valid_shell_syntax` 因 Windows 上 `bash` 命中被未配置的 WSL 劫持而失败——脚本本身经 Git Bash `bash -n` 验证语法正确。
- `test_project_config_declares_real_prometheus_and_alertmanager_sources` 需要用户提供真实 Prometheus 端点。

## 阶段二：基础设施恢复（下午）

- **问题**：Milvus 栈因 minio 基础镜像 `tobi312/minio` 拉取失败而无法启动——本机 8 个 Docker 镜像源全部不可用（2 超时、2 个 429 限流、2 个 403、2 个字节流停滞）。
- **解决**：`hub.rat.dev` 镜像源的后台长跑拉取最终完成，重打本地标签后 `docker compose up` 全栈启动。
- **结果**：`/ready` 四项依赖（SQLite/Milvus/Qwen/MCP）全部绿灯。

## 阶段三：运行时端到端验证

- 后端 `/health`、`/ready` 实测（真实 Qwen 调用成功）。
- 注册→登录→`/auth/me` API 冒烟（Argon2 + opaque token）。
- 浏览器实测：登录工作台 → 发送消息 → **真实 Qwen SSE 流式回答渲染**。

## 阶段四：对话回答 UI 重设计

- `ChatTranscript.vue` 重构为"头像 + 角色标签 + 气泡"三段式：用户消息绿色圆角气泡、助手回答白色卡片；新增流式生成打字点指示器（含 ARIA 与 reduced-motion 兼容）；引用来源/反馈/工具调用区块全面美化。
- `MarkdownContent.vue` 排版补齐（标题层级、列表、代码块圆角、表格、引用块）。
- **约束保持**：`chatLayout.test.ts` 的 4 条源码级 CSS 断言全部满足；AIOps report 模式不受影响。

## 阶段五：字体系统优化

- 引入自托管思源黑体 `@fontsource-variable/noto-sans-sc`（npm，无 CDN），建立 `--font-sans`/`--font-mono` 设计令牌；代码块配套等宽字体栈（Cascadia Code/JetBrains Mono/Consolas）。
- 浏览器确认计算字体族与分片加载（12 个 unicode-range 分片）。

## 阶段六：LaTeX 公式渲染

- 引入 `katex` + `marked-katex-extension`，支持行内 `$...$` 与块级 `$$...$$`。
- 关键决策：KaTeX 以 `output: "html"` 模式只输出 span，与现有 DOMPurify html 白名单完全兼容（无 XSS 面扩大）；`throwOnError: false` 让流式中未完成的公式降级显示而非抛错。
- 新增 3 个测试（含 `$5 和 $10` 非公式误判防护）；浏览器实测渲染通过。

## 阶段七：Skill 测试样例

- 新增 `samples/skills/` 四个 `SKILL.md`（latex-writing / code-review / sql-troubleshooting / incident-brief）+ 使用说明 README，用于验证渐进式加载语义。

## 阶段八：GitHub 发布与文档站

- 仓库公开发布：`github.com/ahuang-app/agent-py`（824 文件，提交前做了三重密钥扫描：sk-/AKID/高熵键值模式零命中，真实凭据靠 .gitignore 隔离）。
- VitePress 文档站发布到 GitHub Pages：`ahuang-app.github.io/agent-py`。
  - `.github/workflows/deploy-docs.yml` 自动发布；`DOCS_BASE` 环境变量驱动子路径 `/agent-py/`。
  - 修复 `docs/openspec` 退化为文本文件的符号链接（git index 恢复 120000 模式）。
  - 排障记录：Pages 开通需 `gh api` 手动（workflow token 权限不足）；Git Bash 的 MSYS 路径转换会破坏 `/agent-py/` 环境值（需 `MSYS_NO_PATHCONV=1`）。

## 阶段九：LLM 用量预算 + CORS 配置化（OpenSpec 双 change）

按仓库规范创建并实现两个 OpenSpec change（proposal/spec/design/tasks 全套 + 全部任务勾选）：

### add-llm-budget-limits

- 新增 `llm_usage_events` 台账（Alembic `202610240001`）与 owner-scoped Repository。
- `LlmBudgetService`：每用户每日预算（UTC 日界）+ 全局每月预算 + per-call 输出上限。
- 五个调用点接线：chat（端点层预检 + runner finally 记账，`stream_usage` 捕获真实 usage）、AIOps（planner/report）、记忆压缩、索引 embedding 与检索 embedding（`count_tokens_approximately` 估算并标记）。
- 新错误码 `BUSINESS_LLM_BUDGET_EXCEEDED`（429，HTTP/SSE 统一，前端中文提示映射）。
- 配置 `llm.budget` 三字段严格校验（非法值拒绝启动）。

### configure-cors-allowlist

- `backend.corsAllowOrigins` 配置化（缺省回退本机 5173 默认值；非法元素拒绝启动）。
- 排障记录：初版误把字段路径设计为 `app.backend.*`，与配置实际结构不符导致预检 400，已统一对齐顶层 `backend` 节并同步规格文档与测试。

### 门禁结果

后端 ruff/pyright 0 错误 + pytest 156 通过（仅剩 2 个已知环境/待配置项）；契约 24、前端 82、openspec 44 全部通过。

## 阶段十：公网部署演进（三次迭代）

1. **双快速隧道**：前端/后端各一条 trycloudflare 隧道 + CORS 白名单——验证通过但 URL 临时且需两条。
2. **单网址网关架构**：新增 `scripts/local_gateway.py`（零依赖 stdlib 实现）：精确 SPA 路由与静态文件走 dist，其余路径反代后端，SSE 逐块流式转发；前端改为同源相对调用（`apiBaseUrl=""`）。浏览器实测公网登录、对话、SSE 全通过。
3. **ngrok 固定域名**：用户提供免费静态域名 + authtoken，`ngrok http 4173 --domain=passivism-uptake-gills.ngrok-free.dev` 上线固定网址；浏览器验证登录、对话、KaTeX 渲染全链路。临时隧道已拆除。

## 阶段十一：文档交付

- `docs/tutorials/testing-guide.md`：知识库 RAG / 智能诊断 / MCP / Skill 三大测试问题整合指南（含概念补充解释、验收点表格、常见失败对照）。
- `docs/tutorials/public-deployment.md`：公网部署三路线对比与命名隧道完整步骤。
- `docs/operations-and-monitoring.md` 增补预算与 CORS 运维说明。
- 本文件与 `docs/resume-project.md`。

## 当前运行状态（截至本文写作）

| 项 | 状态 |
| --- | --- |
| 公网入口 | https://passivism-uptake-gills.ngrok-free.dev（ngrok 固定域名） |
| 后端 | 127.0.0.1:8000（含预算限额与 CORS 配置化） |
| 网关 | 127.0.0.1:4173（单网址同源架构） |
| CLS MCP | 127.0.0.1:3000 |
| Milvus 栈 | Docker Compose 五容器健康 |
| 预算 | 4096/每用户每日 200k/全平台每月 2M tokens |
| 测试 | 后端 158 / 前端 82 / 契约 24 / OpenSpec 44 项门禁 |

## 本日经验沉淀

- Windows 环境：`uv` 需匹配锁文件的 cp310 wheel；`uv run` 要 `--no-sync`；WSL bash 劫持 `bash -n`；TaskStop 杀不净 node 子进程需 `taskkill //F`；Git Bash MSYS 会改写以 `/` 开头的环境变量值。
- 网络：Docker 镜像源与 GitHub 连接均不稳定，关键操作要有重试与本地提交兜底。
- 安全：提交前三重密钥扫描；用户贴入聊天的 API key 建议立即轮换。
