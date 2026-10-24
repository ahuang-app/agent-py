# 简历项目资料：Agent Py —— 本地优先的中文 AIOps 智能工作台

> 本文件是写简历时的完整素材库：项目信息、量化数据、不同侧重的简历条目示例、以及面试问答准备。
> **使用说明**：请按你真实承担的角色取舍与措辞。项目基线是一个已实现的 Monorepo（65 个归档规格），"迭代贡献"部分是 2026-10-24 这轮开发中完成的功能增强、缺陷修复与公网部署，均为可验证的真实改动（对应 GitHub 提交记录与工程日志 `docs/devlog/2026-10-24-full-session-log.md`）。

## 一、项目基本信息

| 项 | 内容 |
| --- | --- |
| 项目名称 | Agent Py（Super AI 工作台） |
| 一句话定位 | 本地优先的中文 AI/AIOps 智能工作台：对话 Agent、RAG 知识库、自动故障诊断一体化 |
| 代码仓库 | github.com/ahuang-app/agent-py（公开） |
| 在线文档站 | ahuang-app.github.io/agent-py |
| 公网演示 | passivism-uptake-gills.ngrok-free.dev（ngrok 免费静态域名 + 隧道） |
| 代码规模 | 约 2.5 万行源码（后端 50 个 Python 模块、前端 60 个 Vue/TS 文件、16 个共享契约文件） |
| 测试规模 | 后端 158 项 + 前端 82 项 + 契约 24 项自动化测试，全部通过 |
| 规格文档 | OpenSpec 规格 42 份、归档变更 65 份、文档站页面 83 页 |
| 核心依赖 | LangChain/LangGraph、FastAPI、Vue 3、Milvus、SQLite、Qwen（OpenAI 兼容） |

## 二、一句话/短简介（按篇幅选用）

**一句话版（20 字内）**：
> 集成 LangChain Agent、RAG 知识库与自动故障诊断的全栈 AIOps 工作台。

**简历项目栏标准版（约 80 字）**：
> 本地优先的中文 AI 运维工作台。Vue 3 + FastAPI 全栈实现：LangChain Agent 流式对话（可引用知识库来源）、Milvus 混合检索 RAG（向量+BM25+RRF+精排四阶段可解释）、LangGraph 自动故障诊断（Plan-Execute-Replan 证据链报告）。OpenAPI/SSE 契约驱动前后端，158+ 自动化测试守门，已公网部署。

**详细版（约 150 字，适合项目经历栏较宽的简历）**：
> 独立完成一个本地优先 AIOps 工作台的开发与公网交付。系统包含：基于 LangChain create_agent 的流式对话（模型自主调用知识检索与 MCP 日志工具，回答附可追溯引用）；Milvus 混合检索 RAG 管线（向量召回 + BM25L 关键词召回 + RRF 融合 + 精排重排，四阶段排名全程可解释）；LangGraph Plan-Execute-Replan 自动故障诊断（证据链持久化、可恢复、自动沉淀案例）。工程上采用共享 TypeScript 契约统一 HTTP/SSE 类型、SQLite durable job 运行时、Argon2 认证与租户级数据隔离，后端 158 项 / 前端 82 项自动化测试全部通过，已通过隧道方案完成公网 HTTPS 部署并配置用量预算防线。

## 三、技术栈清单（面试时按层展开）

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3.5（Composition API + Pinia）、Vite、TypeScript strict（exactOptionalPropertyTypes）、Vitest、marked + DOMPurify + KaTeX、lucide 图标 |
| 后端 | Python 3.10、FastAPI、Pydantic v2、SQLAlchemy 2 async + Alembic、uv、Ruff + strict Pyright |
| AI 编排 | LangChain create_agent（对话 Agent）、LangGraph StateGraph（诊断图）、langchain-openai（Qwen OpenAI 兼容接入）、langchain-mcp-adapters（MCP 工具） |
| 检索 | Milvus（HNSW/COSINE）、rank-bm25（BM25L）、RRF 融合（k=60）、独立 rerank HTTP client |
| 数据 | SQLite（aiosqlite）、Alembic 迁移、durable job 运行时（租约/心跳/重试/取消） |
| 实时通信 | SSE（判别联合事件：content.delta / tool.call / reference.source / complete / error） |
| 基础设施 | Docker Compose（etcd/MinIO/Milvus/Attu/Alertmanager）、cloudflared/ngrok 隧道、GitHub Actions Pages |
| 工程化 | OpenSpec 规格驱动开发、共享 TypeScript 契约包、Conventional Commits、VitePress 文档站 |

## 四、系统架构（口头介绍 1 分钟版）

前后端分离的 Monorepo：**前端** Vue 3 SPA 通过共享 TypeScript 契约包调用 FastAPI 后端（统一成功/错误 envelope + SSE 流事件）；**后端**业务层依赖 Protocol 注入，SQLite 持久化（Alembic 管理），LangChain Agent 在服务端编排工具调用（知识检索工具强制附加用户租户过滤，MCP 工具来自用户自己的连接）；**知识管线**是文档切分 → Qwen embedding → Milvus 写入的后台 durable job，检索时向量与 BM25L 并行召回、RRF 融合后精排；**诊断图**用 LangGraph 实现 Plan-Execute-Replan 循环，全部步骤与证据持久化、可断线恢复；**部署**上基础设施走 Docker Compose，应用本机运行，通过本地同源网关 + 隧道暴露公网，应用层配置了 token 用量预算防线。

## 五、核心功能模块（按模块准备一句话说明）

1. **认证与隔离**：Argon2 密码哈希、opaque bearer token（只存哈希）、全业务数据按用户租户隔离、越权统一 403。
2. **流式对话 Agent**：LangChain create_agent，模型自主决定调用知识检索/时间/MCP 工具；回答按 Unicode 字符流式下发；Prompt 与渐进式 Skill（load_skill 按需加载正文）；会话级记忆压缩（每 30 轮/70% 上下文/手动三种模式）。
3. **知识库 RAG**：Markdown/PDF 上传、三种切分策略、durable 索引任务（排队/执行/重试/取消）、混合检索四阶段全程可解释引用、空结果诚实返回。
4. **智能诊断**：真实告警入口（Prometheus/Alertmanager）、LangGraph 诊断图、证据链持久化、中文结构化报告、成功自动沉淀为知识案例。
5. **MCP 工具治理**：用户级连接管理（SSE/Streamable HTTP）、超时/重试/同名冲突保护、调用审计（工具名+参数键+耗时，不落敏感值）。
6. **Durable 任务运行时**：SQLite 任务/事件/租约/心跳，进程重启恢复、指数退避、协作式取消。
7. **可观测性**：request id 透传、结构化日志、敏感字段递归脱敏、/health 与 /ready 分层探针、/metrics。
8. **LLM 预算防线**（本轮新增）：用量台账 + 每用户每日/全局每月预算 + per-call 输出上限，超限返回统一错误码。

## 六、工程实践亮点（面试加分点）

1. **规格驱动开发**：每个功能先写 OpenSpec change（proposal/design/delta spec/tasks）再实现，65 份归档变更全程可追溯；文档站用 include 直接引用规格原文，永不与代码脱节。
2. **契约先行**：前后端共享 TypeScript 契约包统一 HTTP envelope、错误码目录与 SSE 事件联合类型，前端不复制私有类型，契约测试锁死两端一致性。
3. **可解释 RAG**：检索不是黑盒——每条引用保留向量/BM25/RRF/精排四阶段排名与分数，未命中显式标注"未命中"，空结果不编造。
4. **安全边界**：Argon2、token 只存哈希、租户过滤在 Repository 层强制、日志对密码/token/key 递归脱敏、KaTeX 输出过 DOMPurify 白名单。
5. **测试文化**：158+82+24 项自动化测试覆盖权限边界、SSE 事件顺序、任务恢复/重试/取消、检索算法边界（如 RRF 平局确定性、预算日界切换）；不用无条件 skip 放水。
6. **诚实交付**：无真实凭据的 smoke 明确标注"未执行"；失败显式化而非伪造成功（如报告生成的 fallback 标注来源）。

## 七、迭代贡献（2026-10-24 开发批次，简历可引用）

> 以下均为本轮真实完成的改动（GitHub 提交可查：`fc8f66f`→`657602b`），按"你独立完成了什么"组织：

1. **全系统可运行性验证与 4 项缺陷修复**：发现并修复 .gitignore 密钥泄露风险、配置模板脱敏违约、两处端口漂移（曾导致前端测试失败）；定位 Windows 依赖安装的 cp310 wheel 边界问题。
2. **对话回答 UI 重设计**：头像+气泡布局、流式打字指示器、引用/反馈/工具调用区块美化；Markdown 排版体系（代码块/表格/标题层级）。
3. **中文排版与公式能力**：自托管思源黑体可变字体（设计令牌化）；KaTeX 公式渲染（$...$/$$...$$，与 DOMPurify 安全白名单兼容）。
4. **LLM 用量预算系统**（OpenSpec 规格驱动）：用量台账、每用户每日/全局每月预算、per-call 上限、统一 429 错误码，覆盖对话/诊断/记忆/索引四条调用链。
5. **公网部署交付**：CORS 白名单配置化、单网址同源网关（含 SSE 流式反代）、ngrok 固定域名上线、部署文档化；GitHub 公开仓库 + Actions 自动发布文档站。
6. **文档资产**：功能测试指南（RAG/诊断/MCP/Skill 含概念解释）、公网部署指南、运维文档增补、全天工程日志。

## 八、简历条目示例（挑贴合目标岗位的用）

**偏全栈/后端：**
> - 设计并实现基于 FastAPI + LangChain 的 Agent 服务端：SSE 流式对话、工具自主调用审计、SQLite durable 任务运行时（租约/心跳/断线恢复），前后端通过共享 TypeScript 契约统一 HTTP/SSE 类型，核心链路自动化测试 240+ 项全绿。
> - 实现 LLM 用量预算系统：SQLite 用量台账 + 每用户每日/全局每月两级预算 + per-call token 上限，四条 AI 调用链（对话/诊断/记忆压缩/索引向量化）统一计量，超限返回统一错误码，为公网多租户部署提供成本防线。

**偏 AI/算法：**
> - 构建 Milvus 混合检索 RAG 管线：向量召回与 BM25L 并行、RRF(k=60) 确定性融合、rerank 精排，四阶段 rank/score 全程可解释并随引用透出；空结果诚实返回、未命中阶段显式标注，测试覆盖中英分词、小语料 IDF、平局稳定性等算法边界。
> - 用 LangGraph 实现 Plan-Execute-Replan 自动故障诊断：Planner 检索 SOP 后有界规划，Executor 真实调用 MCP 日志工具取证，证据链与检查点持久化，报告结论可追溯到证据，成功案例自动回流知识库。

**偏运维/DevOps：**
> - 完成系统的公网交付：Docker Compose 编排 Milvus/etcd/MinIO/Alertmanager 栈、本地同源网关（含 SSE 流式反代）合并前后端为单 URL、隧道方案固定公网域名（HTTPS），并建立 LLM token 预算防线与就绪探针/结构化日志/脱敏的可观测性基线。

## 九、面试问答准备

**Q1：为什么混合检索？只用向量不行吗？**
向量懂语义但对精确标识符（类名、traceId、错误码）不敏感；BM25L 补关键词匹配；两者用 RRF（1/(k+rank)，k=60）融合让互不偏科，最后 rerank 精排。每条引用保留四阶段排名，检索可解释、可审计。

**Q2：SSE 怎么保证回答的打字机效果和事件顺序？**
后端把最终正文按 Unicode 字符拆成有序 `content.delta` 事件，工具调用/引用/错误不拆字符；事件 id/sequence 稳定，complete 只出现一次；前端每字符约 28ms 节流渲染。流失败不留半条助手消息（assistant 消息只在成功完成后一次性持久化）。

**Q3：Agent 怎么决定调用哪些工具？会不会乱调？**
LangChain create_agent 让模型自主决策，但工具边界被服务端强制：知识检索工具绑定当前用户租户过滤（模型传参不能扩大权限）、MCP 工具只来自该用户启用且检查通过的连接、每次调用落审计记录。未启用/不相关时模型就不调。

**Q4：后台任务为什么不用 asyncio.create_task？**
对话断了任务不能死。durable runtime 把任务/事件/租约写 SQLite：worker 原子领取、心跳续租、崩溃后过期租约回收、指数退避重试、超时与协作式取消；SSE 断开只影响观看不影响执行，重连从持久事件恢复。

**Q5：怎么防公开部署后额度被刷？**
三层：应用层 token 预算（每用户每日 + 全局每月 + per-call 上限，SQLite 台账记账，超限 429）；模型服务平台侧限流与预付费资源包；部署侧反代限速。应用层是唯一能精确到"每人每天"的层级。

**Q6：LLM 输出的内容直接渲染安全吗？**
不直接。Markdown 先经 marked 解析（自定义 renderer 丢弃原生 HTML），再过 DOMPurify 白名单；KaTeX 用 output:"html" 模式只产出 span，被同一白名单覆盖；引用来源点击只打开用户自己的文档。

**Q7：数据隔离怎么做的？**
当前用户 id 即租户 id。所有 Repository 方法显式要求 owner_user_id，向量检索的 Milvus filter 由服务端从认证上下文生成（tenantId + 允许的知识库列表），客户端传来的 owner 字段一律不可信；越权访问统一返回 403 且不泄露资源存在性。有专门的双用户交叉测试。

**Q8：RAG 的引用为什么显示"未命中"而不是给个 0 分？**
伪造分数比没有分数更危险——它让人以为检索发生过。四阶段各自可能未命中，诚实的空标注让使用者能判断这条引用的可信度来源。

**Q9：遇到过的最难的环境问题？**
Windows 依赖链：锁文件里 python-snappy 只有 cp310 wheel、lz4 无 wheel 需 MSVC——用 uv 的 `--python 3.10 --no-install-package` 精确绕开（先验证运行时不导入这两个包）；Docker 镜像源全挂时用备用镜像站长跑拉取。方法论：先确认真实依赖边界，再选最小侵入的绕行，并把问题写进文档。

**Q10：如果流量涨 10 倍，哪里先崩？**
SQLite 写入与单机 Milvus。演进路径：Repository 边界已隔离存储细节，可平迁 PostgreSQL；Milvus 换集群版；网关/隧道换 Nginx + 固定服务器。这也是本地优先架构预留的替换边界。

## 十、量化数据汇总（更新于 2026-10-24）

| 指标 | 数值 |
| --- | --- |
| 源码规模 | ~24,900 行（不含生成物与依赖） |
| 自动化测试 | 后端 158 + 前端 82 + 契约 24 = **264 项** |
| OpenSpec 规格 | 42 份主规格，65 份归档变更 |
| 文档站页面 | 83 页（含 2 份教程指南） |
| 公网交付 | 固定域名 HTTPS（ngrok 隧道）、单网址同源网关 |
| 安全机制 | Argon2 / token 哈希存储 / 租户隔离 / 递归脱敏 / DOMPurify / 用量预算 |
