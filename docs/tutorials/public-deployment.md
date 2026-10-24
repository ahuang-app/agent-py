# 公网部署指南：从临时隧道到固定域名

本平台是"本地优先"架构：后端、数据库、向量库都跑在你自己的电脑上。让别人访问有三个阶段，**成本与稳定性递增**，可按需升级。

## 三条路线对比

| 路线 | 域名 | 在线时长 | 成本 | 适合 |
| --- | --- | --- | --- | --- |
| 快速隧道（当前方案） | 临时 `*.trycloudflare.com`，重启即变 | 电脑开机期间 | 0 元，无需注册 | 朋友试用 |
| **命名隧道（本指南）** | 你自己的固定域名 | 电脑开机期间（可配开机自启） | 域名费（约几十元/年起）+ 免费云账号 | 长期给团队/朋友用 |
| 云服务器部署 | 固定域名 | **真正的 24×7** | 服务器租金 | 生产使用 |

> **重要认知**：Cloudflare 隧道解决的是"**固定域名**"和"**加密免公网暴露端口**"，它**不能**让你的电脑在关机后继续提供服务。"24 小时在线"只有两条路：① 这台电脑不关机（配好开机自启后可接受）；② 把整套服务搬到云服务器（迁移指引见文末）。

## 前置条件（一次性）

1. **一个域名**：在任意注册商购买（Cloudflare 自家 Registrar 成本价、无加价；或在阿里云/腾讯云购买后接入）。域名总身价几十元/年。
2. **域名托管到 Cloudflare（免费套餐）**：注册 Cloudflare 账号 → Add site → 按提示到注册商处把 Nameserver 改成 Cloudflare 给的两个地址 → 等待生效（几分钟到几小时）。
3. 本机服务在运行：后端 `:8000`、前端静态服务 `:4173`（`npx serve apps/frontend/dist -s -l 4173`，注意 dist 需以公网 API 地址构建，见第 3 步）。

## 第 1 步：登录 cloudflared（浏览器授权一次）

```bash
cloudflared tunnel login
```

浏览器会打开 Cloudflare 授权页，选择你的域名，授权后本机 `~/.cloudflared/cert.pem` 生成。

## 第 2 步：创建命名隧道并绑定两个子域

```bash
cloudflared tunnel create agent-py
cloudflared tunnel route dns agent-py chat.你的域名.com
cloudflared tunnel route dns agent-py api.你的域名.com
```

## 第 3 步：写隧道配置文件

创建 `~/.cloudflared/config.yml`：

```yaml
tunnel: agent-py
credentials-file: C:\Users\<你的用户名>\.cloudflared\<隧道ID>.json
ingress:
  - hostname: chat.你的域名.com
    service: http://localhost:4173
  - hostname: api.你的域名.com
    service: http://localhost:8000
  - service: 404
```

## 第 4 步：让应用认识新域名（两处）

1. **前端以新 API 地址重新构建**：把 `config/project.json` 的 `frontend.apiBaseUrl` 改为 `https://api.你的域名.com`，然后：

   ```bash
   cd apps/frontend
   npm run build
   ```

2. **后端 CORS 白名单**：`config/project.json` 的 `backend.corsAllowOrigins` 加入 `https://chat.你的域名.com`，重启后端。

## 第 5 步：启动并（可选）注册为 Windows 服务

```bash
cloudflared tunnel run agent-py          # 前台运行，验证通过后执行下一行
cloudflared service install              # 注册为 Windows 服务，开机自启
```

验证：浏览器打开 `https://chat.你的域名.com`，注册并进入工作台即成功。

## 24 小时在线的两个额外保障

1. **开机自启应用**：用 Windows 任务计划程序在"登录时"启动后端 uvicorn、静态前端服务和（若未注册服务）cloudflared。需要我配置时说一声。
2. **断电/重启自愈**：Milvus 等 Docker 容器在 compose 里已配置 `restart: unless-stopped`，Docker Desktop 随登录启动即可。

## 升级到云服务器（真 24×7）

把上述整套（Docker 基础设施 + 后端 + 前端静态 + cloudflared 或 Caddy）搬到一台 2C4G+ 云主机即可，域名指向改为服务器。需要迁移时提供服务器 SSH 访问，我负责部署脚本、HTTPS 反代与数据迁移方案。迁移前记得为线上实例单独申请一把有限额的模型服务密钥。

## 安全清单（公开实例必读）

- `llm.budget` 预算已配置（当前 4096/每用户每日 200k/全平台每月 2M），防止额度被刷。
- 模型服务密钥是平台级资产：所有注册用户共享同一把 key 的额度，预算是唯一闸门。
- 不要把真实密钥写进仓库；`config/project.json` 永远只在目标机器本地存在。
