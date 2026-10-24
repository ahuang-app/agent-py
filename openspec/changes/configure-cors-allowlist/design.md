# 设计：configure-cors-allowlist

## Context

`create_app` 中 `CORSMiddleware.allow_origins` 硬编码两个本机来源；配置加载已有 `project_config_section` 模式与类型化校验工具（`required_str` 等）。

## Decisions

- **D1**：新增纯函数 `resolve_cors_allow_origins(config_path) -> list[str]`：读取 `backend.corsAllowOrigins`，缺省/空/类型非法时回退内置默认；配置存在但元素非字符串时按校验错误抛出（与配置校验风格一致）。`create_app` 调用它传入中间件。
- **D2**：不引入 `allow_credentials`（认证为 bearer header，无 cookie）；`allow_methods/headers` 维持 `["*"]`。
- **D3**：模板默认携带两个本机来源；公网部署在本地 `user.project.json` 的 `backend.corsAllowOrigins` 追加公网前端来源，不改仓库模板语义。

## Risks / Trade-offs

- 通配 `*` 会被滥用风险由部署者自负；配置即所见，不做来源格式黑名单（URL 合法性由运行时行为兜底）。
