# 任务：configure-cors-allowlist

- [x] 1.1 实现 `resolve_cors_allow_origins` 并接入 `create_app` 的 CORSMiddleware，缺省回退默认来源
- [x] 1.2 两个配置模板新增 `app.backend.corsAllowOrigins`（默认本机来源）
- [x] 1.3 单测：配置来源生效、缺省回退、非法元素报配置错误
- [x] 1.4 门禁：后端 ruff/pyright/pytest 通过；`openspec validate --all` 通过
