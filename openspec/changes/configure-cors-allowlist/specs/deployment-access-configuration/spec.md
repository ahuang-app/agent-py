# Delta Spec: deployment-access-configuration

## ADDED Requirements

### Requirement: CORS 来源白名单可配置

系统 SHALL 从本地合并配置的 `backend.corsAllowOrigins`（字符串数组）读取 CORS 允许来源；字段缺省或为空时 SHALL 回退到内置默认（`http://127.0.0.1:5173`、`http://localhost:5173`）。

#### Scenario: 配置的来源被允许

- **WHEN** 配置声明了额外来源且该来源的前端页面调用 API
- **THEN** 浏览器跨域预检通过，请求正常处理

#### Scenario: 缺省回退本机默认

- **WHEN** 配置未声明 `corsAllowOrigins`
- **THEN** 行为与配置化之前完全一致（仅允许本机 5173 来源）
