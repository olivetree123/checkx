# CheckX · 设计审阅

面向设计师与审阅者的轻量协作工具。以 **项目 → 页面 → 设计图 → 审阅记录** 组织工作；支持多人同时使用同一个账号，没有群组或成员系统。

## 已实现

- 邮箱注册、登录和退出；无需邮箱验证；独立登录会话，不互相踢下线。
- 项目和页面的创建、编辑、列表及统计。
- 每个页面上传多张 PNG / JPEG / WebP 图片，逐张设置名称和备注；拖拽、多选、预览、失败项重试。
- 原图查看、缩放、按状态筛选和搜索；原图访问也有账号鉴权。
- 设计图审阅：填写意见和审阅人署名，选择「需修改 / 已通过」；保留完整历史，最新审阅决定当前状态。
- 设计图名称/备注修改，设计图及其审阅记录删除（前端二次确认）。
- 瀑布流大图卡片完整展示备注及最新 3 条审阅记录，可直接通过或展开输入修改意见；点击图片进入详情页。
- 列表与详情页的每条审阅记录提供删除图标，确认后删除并更新状态、历史和统计；保留图片本身。
- MCP 访问令牌创建、到期和撤销；Codex 可列出/创建项目和页面、上传本地图片（同页同文件名覆盖）、按 ID 更新图片并自动递增版本、删除设计图及审阅历史、按版本读取审阅结果。
- 简洁项目首页；项目详情为左侧页面列表、右侧设计图内容，支持收起页面列表。
- 顶部头像菜单进入设置：修改名称、邮箱、密码，管理 MCP 令牌。
- 响应式中文 React 界面，覆盖桌面和手机。
- 白天/夜间主题：头像菜单或登录页右上角切换；首次打开参考系统主题，手动选择保存在当前浏览器，多标签页同步，设计图片保持原色。

## 技术与目录

```text
checkx/
├── checkx-backend/
│   ├── app/
│   │   ├── main.py          # 生命周期、请求体限制、统一异常处理
│   │   ├── api.py           # REST 路由，Pydantic 输入/输出
│   │   ├── models.py        # Tortoise ORM 模型
│   │   ├── schemas.py       # Pydantic DTO 与 Envelope[T]
│   │   ├── security.py      # Argon2、独立会话、访问令牌
│   │   ├── services.py      # 归属校验、图片存储、审阅事务
│   │   ├── config.py        # 环境变量配置
│   │   └── migrations/     # 初始与图片版本数据库迁移
│   ├── mcp_server.py        # 独立 stdio MCP 服务，调用同一套 REST API
│   ├── tests/              # API、并发、权限及 MCP 协议测试
│   ├── .venv/              # 本机已创建 Python 3.14 虚拟环境（不提交）
│   ├── pyproject.toml
│   ├── uv.lock
│   └── Dockerfile
├── checkx-frontend/
│   ├── src/                # React 19 + TypeScript + Vite + React Query
│   ├── e2e/                # 桌面和手机 Playwright 完整流程
│   ├── package-lock.json
│   ├── nginx.conf
│   └── Dockerfile
├── compose.yaml            # 可选数据库/应用编排
└── docs/
    ├── architecture.md     # 领域模型、认证、存储、接口设计
    ├── mcp.md              # Codex MCP 接入示例
    └── verification.md     # 已执行的验证与边界
```

后端使用 **Python 3.14 + FastAPI + PostgreSQL + Tortoise ORM + Pydantic 2**。这里将需求中的 “pedantic” 按 Pydantic 实现。图片保存到可配置的本地目录，不保存到数据库。

## 本机直接启动

当前工作区已经创建 `checkx-backend/.venv`、安装依赖、生成锁文件，并在你已有的 `postgres` 容器中创建了 `checkx` 与 `checkx_test`。本地 `checkx-backend/.env` 已配置现有容器连接，真实凭据不会写入示例或提交文件。**不需要再启动数据库容器，也不要重复复制 `.env.example` 覆盖已有 `.env`。**

### 后端

```bash
cd checkx-backend
source .venv/bin/activate
# 首次克隆到另一台机器时执行：uv sync --frozen
# 首次配置时复制 .env.example 为 .env，并按实际容器修改 DATABASE_URL

tortoise migrate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

如果需要重新创建虚拟环境：

```bash
uv venv --python 3.14 .venv
uv sync --frozen
```

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json
- 健康检查: http://127.0.0.1:8000/api/health

### 前端（另一个终端）

```bash
cd checkx-frontend
npm ci
npm run dev
```

打开 **http://127.0.0.1:5173**，直接注册自己的账号。默认没有预置账号或演示业务数据。Vite 把 `/api` 转发到 `http://127.0.0.1:8000`，浏览器始终使用同源 HttpOnly Cookie。

如端口冲突，先停止已有开发服务；变更前端源地址时同步修改后端 `CORS_ORIGINS`。后端地址变更可通过 `API_PROXY_TARGET` 配置 Vite。

## PostgreSQL：仅使用容器

开发使用你提供的 `postgres:18-bookworm` 容器，不在宿主系统安装 PostgreSQL。数据库不存在时可执行：

```bash
docker exec postgres createdb -U postgres checkx
docker exec postgres createdb -U postgres checkx_test
```

上述命令只适合首次创建；数据库已经存在时无需重复执行。之后在后端 `.env` 设置：

```dotenv
DATABASE_URL=postgres://postgres:你的容器密码@127.0.0.1:5432/checkx
```

URL 中密码含特殊字符时需要进行 URL 编码。

**另一台机器上没有现有容器时**，可选用本项目的 Compose 数据库：

```bash
cp .env.example .env
# 修改根目录 .env 的 POSTGRES_PASSWORD
# 同步修改 checkx-backend/.env 的 DATABASE_URL（用户默认是 checkx）
docker compose up -d db
```

不要在现有容器占用 5432 时再运行这条命令。Compose 默认只启动数据库，前后端在 `app` profile 下；PostgreSQL 18 数据卷挂载到 `/var/lib/postgresql`。

## 配置

配置从后端工作目录的 `.env` 和进程环境读取，环境变量优先。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | 示例 PostgreSQL URL | 开发/部署均使用 PostgreSQL |
| `STORAGE_DIR` | `./data/uploads` | 图片目录；相对路径相对于后端进程工作目录，部署建议使用绝对路径 |
| `CORS_ORIGINS` | localhost:5173 / 127.0.0.1:5173 / localhost:8080 | JSON 数组，同时用于浏览器写请求的 Origin 校验 |
| `COOKIE_SECURE` | `false` | 本地 HTTP 开发使用 false；HTTPS 部署使用 true |
| `SESSION_DAYS` | `7` | 浏览器会话有效期，退出只撤销当前会话 |
| `MAX_UPLOAD_MB` | `20` | 后端单文件上限，整个请求允许额外 1 MiB 表单开销 |
| `MAX_IMAGE_PIXELS` | `40000000` | 单图最大像素数 |
| `AUTO_CREATE_SCHEMA` | `false` | 仅测试/临时开发可开启，正常启动使用迁移 |

前端上传组件默认限制 20 MiB；MCP 也默认 20 MiB，可配置 `CHECKX_MAX_UPLOAD_MB`。若修改服务端上传上限，应同步修改前端校验和 Nginx 的 `client_max_body_size`。

## 接口约定

所有业务 JSON 成功/失败响应统一：

```json
{"code": 0, "data": {}, "message": "ok"}
```

成功 `code=0`；错误 `code` 等于 HTTP 状态码。HTTP 状态码也保持真实语义，例如 201、401、404、409、413、422、429、500。参数错误的 `data` 包含字段路径及错误消息，不返回密码或令牌输入。

例外是成功的原图下载（图片二进制）、OpenAPI/Swagger 文档和 MCP 自身协议包；它们不能包装为业务 JSON。原图的错误仍使用统一 JSON。

主要接口：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` | 注册、登录、退出 |
| GET / PUT | `/api/auth/me` | 当前账号、更新名称和邮箱 |
| PUT | `/api/auth/password` | 确认当前密码并修改密码，撤销其他浏览器会话 |
| GET / POST | `/api/projects` | 项目列表、创建 |
| GET / PUT | `/api/projects/{id}` | 项目详情、更新 |
| GET / POST | `/api/projects/{id}/pages` | 页面列表、创建 |
| PUT | `/api/pages/{id}` | 更新页面 |
| GET / POST | `/api/pages/{id}/designs` | 设计图列表、上传 |
| GET / PUT / DELETE | `/api/designs/{id}` | 设计图详情、编辑、删除 |
| GET | `/api/designs/{id}/image` | 经过鉴权的最新原图 |
| PUT | `/api/designs/{id}/image` | 按 ID 更新图片，保留旧文件并递增版本 |
| GET / POST | `/api/designs/{id}/reviews` | 审阅结果和历史、提交审阅 |
| DELETE | `/api/designs/{id}/reviews/{review_id}` | 删除单条审阅记录，返回更新后的设计图 |
| GET / POST | `/api/tokens` | 列出有效访问令牌、创建令牌 |
| DELETE | `/api/tokens/{id}` | 撤销令牌 |

列表支持 `offset` / `limit`，上限 100；设计图列表支持 `status=pending|changes_requested|approved`。审阅结果的 `reviews` 也分页，最新在前，支持 `version` 筛选；设计图与审阅记录均返回 `version`。上传新图为 V1，按 ID 更新或同名覆盖都会递增版本、保留旧图片并重置为待审阅；页面只显示最新图片。更新图片和提交审阅支持 `expected_version`，版本不匹配返回 409。前端自动读取全部页，项目/页面每 15 秒刷新、审阅每 10 秒刷新。

上传接口使用 `multipart/form-data`：`file`、`name`、`notes`（可选）。每次请求上传一张；前端多图队列逐张调用，以便显示每张图片的结果并重试失败项。

## MCP

完整配置与工具列表见 [docs/mcp.md](docs/mcp.md)。在网页右上角头像 →「设置」→「MCP」创建令牌，在本地 MCP 进程设置 `CHECKX_API_TOKEN`，由 Codex 启动 `mcp_server.py`。令牌只显示一次，数据库仅存 SHA-256 摘要，可随时撤销。

## 数据库迁移

已经提供初始迁移 `app/migrations/0001_initial.py` 和图片版本迁移 `0002_image_versions.py`，使用 Tortoise 内置迁移，不需要 Aerich。版本迁移会将现有设计图及审阅统一归入 V1；以前已被删除的旧图片无法恢复，后续更新保留旧文件。

```bash
cd checkx-backend
source .venv/bin/activate
tortoise migrate
# 修改 models.py 后：
tortoise makemigrations --name describe_your_change
# 审查生成的迁移文件后再应用：
tortoise migrate
```

## 验证

```bash
cd checkx-backend
uv sync --frozen
.venv/bin/ruff check app mcp_server.py tests
.venv/bin/pytest -q
```

默认 API 和 MCP 自动测试使用隔离的临时 SQLite 数据库，MCP 测试会启动临时 HTTP/stdio 子进程。

对 PostgreSQL 重跑相同 API 测试：

```bash
# 必须使用专用 checkx_test，测试会清理其中的账号与关联业务数据
TEST_DATABASE_URL='postgres://postgres:容器密码@127.0.0.1:5432/checkx_test' \
  .venv/bin/pytest -q tests/test_api.py
```

```bash
cd checkx-frontend
npm ci
npm run build
npm run format:check
npx playwright install chromium
npm run test:e2e
```

Playwright 自动启动 8001 / 5174 的独立测试服务，用临时库和临时图片目录，不操作开发数据。支持设置 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 使用已有 Chromium。截图和失败 trace 位于 `test-results/`。

## Dockerfile 与部署

已提供两个 Dockerfile、Nginx 配置和可选 Compose 编排。**本次没有构建前后端镜像。**

- 后端：Python 3.14、锁定 uv/依赖、非 root 用户、启动前执行迁移、本地存储卷。
- 前端：Node 构建阶段 + 非 root Nginx 静态服务，转发 `/api`，支持 SPA 深链接。
- Compose：数据库默认可启动，应用需要显式启用 `app` profile。这是全新独立部署示例，不自动接管你已有的 `postgres` 容器。
- 正式部署使用 HTTPS，配置真实源地址并启用 `COOKIE_SECURE=true`；持久化并同时备份 PostgreSQL 与图片目录。
- 当前注册/登录限流为每个进程、每 IP 每分钟 20 次；多实例部署时在可信网关增加共享限流。

## 当前范围

没有群组/成员权限、邮箱验证、密码找回、邮件通知、图上定位批注、自动 AI 审阅和版本分支。共享账号的署名是自由文本，不能用于验证真实个人身份。网页上传创建独立设计图；MCP 上传按同页原始文件名覆盖，保留旧图片与分版本审阅历史并重置为待审阅。MCP 也支持按设计图 ID 更新图片；网页只显示最新图片，暂不提供历史图片预览与恢复。项目和页面提供创建/编辑，暂不提供级联删除项目/页面。
