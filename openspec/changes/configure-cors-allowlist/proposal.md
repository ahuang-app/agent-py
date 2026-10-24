# 提案：configure-cors-allowlist（CORS 来源白名单配置化）

## Why

后端 CORS 允许来源硬编码为本机 5173 端口，公网部署时前端（任意 https 来源）调用 API 会被浏览器拦截。部署需要一个无需改代码即可声明允许来源的配置面。

## What Changes

- `backend.corsAllowOrigins`（字符串数组）新增配置字段：后端启动时读取合并配置作为 `CORSMiddleware.allow_origins`。
- 未配置时默认保持现行为（`http://127.0.0.1:5173`、`http://localhost:5173`）。
- 配置模板同步该字段（携带默认本机来源，非敏感可提交）。
- 不改变认证机制（bearer token，非 cookie），不引入 `allow_credentials`。

## Capabilities

### New Capabilities

- `deployment-access-configuration`：公网部署相关的访问配置（CORS 来源白名单；后续部署字段归入同一能力）。

### Modified Capabilities

- 无。

## Impact

- 后端 `api/app.py`（CORS 读取）、`config/project.template.json`、`config/user.project.template.json`。
- 测试：来源解析与默认回退的单测。
