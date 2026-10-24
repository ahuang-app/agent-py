@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

where docker >nul 2>nul || (echo 缺少必需命令：docker & exit /b 1)
where npm >nul 2>nul || (echo 缺少必需命令：npm & exit /b 1)
where uv >nul 2>nul || (echo 缺少必需命令：uv & exit /b 1)
where cls-mcp-server >nul 2>nul || (echo 缺少必需命令：cls-mcp-server & exit /b 1)

for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "function Merge-Config($base,$override){ foreach($p in $override.PSObject.Properties){ if($null -ne $base.($p.Name) -and $base.($p.Name) -is [pscustomobject] -and $p.Value -is [pscustomobject]){ Merge-Config $base.($p.Name) $p.Value } else { Add-Member -InputObject $base -NotePropertyName $p.Name -NotePropertyValue $p.Value -Force } }; $base }; $config = ConvertFrom-Json (Get-Content -Raw 'config/project.json'); if(Test-Path 'config/user.project.json'){ $user = ConvertFrom-Json (Get-Content -Raw 'config/user.project.json'); $config = Merge-Config $config $user }; Write-Output ('TRANSPORT=' + $config.clsMcpServer.transport); Write-Output ('PORT=' + $config.clsMcpServer.port); Write-Output ('TENCENTCLOUD_SECRET_ID=' + $config.clsMcpServer.secretId); Write-Output ('TENCENTCLOUD_SECRET_KEY=' + $config.clsMcpServer.secretKey); Write-Output ('TZ=' + $config.clsMcpServer.timezone)"`) do set "%%A"

docker compose -f infra/compose.yaml up -d etcd minio milvus attu alertmanager

pushd apps\backend
if not exist var mkdir var

uv sync
if errorlevel 1 exit /b 1

uv run alembic upgrade head
if errorlevel 1 exit /b 1

start "Agent Py CLS MCP" /D "%CD%" cmd /k "cls-mcp-server"
start "Agent Py Backend" /D "%CD%" cmd /k "uv run uvicorn super_ai.api.app:create_app --factory --host 127.0.0.1 --port 8000"

popd

pushd apps\frontend

if not exist node_modules npm install
if errorlevel 1 exit /b 1

start "Agent Py Frontend" /D "%CD%" cmd /k "npm run dev -- --host 127.0.0.1"

popd

echo.
echo ==========================================
echo Agent Py local environment started
echo ==========================================
echo Frontend: http://127.0.0.1:5173
echo Backend:  http://127.0.0.1:8000
echo MCP SSE:  http://127.0.0.1:%PORT%/sse
echo Attu:     http://127.0.0.1:8001
echo MinIO:    http://127.0.0.1:9001
echo Alert:    http://127.0.0.1:9093
echo ==========================================
echo.
