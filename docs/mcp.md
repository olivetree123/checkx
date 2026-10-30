# CheckX 远程 MCP

服务器直接提供 Streamable HTTP MCP，默认路径 `/mcp/`。Codex 无需本地 Python，使用设置页创建的 API 令牌连接。服务器数据库与本地账号独立。

## 远程配置

当前服务器个人 Codex 配置示例（修改已有同名配置，不要重复添加）：

```toml
[mcp_servers.checkx]
url = "http://192.168.124.9:8080/mcp/"
http_headers = { Authorization = "Bearer 替换为服务器创建的令牌" }
tool_timeout_sec = 120
```

重连 MCP 后可请求“使用 CheckX 列出我的项目”。也可用 `bearer_token_env_var = "CHECKX_API_TOKEN"` 替代 `http_headers`，前提是启动 Codex 的环境确实包含该变量。个人配置含秘密，勿提交 Git。当前局域网部署使用 HTTP，未加密；需要加密时配置 HTTPS 反向代理，并同步修改 `MCP_PUBLIC_URL`、`CORS_ORIGINS` 和客户端 URL，HTTPS 网页同时启用 `COOKIE_SECURE=true`。

请求必须带 Bearer API 令牌，网页 Cookie 不足以连接 MCP。每次请求以及执行上传时都会验证令牌的到期/撤销状态，数据隔离规则与网页相同。

## 上传本地图片

远程服务提供同样 9 个工具，其中 `upload_design` 和 `update_design_image` 改为准备上传：不接收 `file_path`，返回短期上传凭证。其他 7 个工具参数不变。

1. 调用 `upload_design(page_id, name, notes="")`，或 `update_design_image(design_id, name=None, notes=None, expected_version=None)`。
2. 使用结果 `data.upload_url` 和 `data.headers`，在图片所在电脑执行：

```bash
curl --fail-with-body -X POST '工具返回的上传地址' \
  -H 'X-Upload-Token: 工具返回的临时凭证' \
  -F 'file=@/本地图片绝对路径.png'
```

3. HTTP 成功响应的 `data` 为设计图（含 `id`、`version`、状态）。还可调用 `list_designs` 或 `get_review_results` 确认。

无需把完整图片编码为工具参数，文件由 curl 直接传输；不要手动设置 multipart 的 Content-Type。临时凭证不等同于账号令牌，绑定创建时的页面/设计图/名称/备注，5 分钟有效，成功使用一次后失效；持有者能执行该项上传，因此不要公开。图片验证失败可以在有效期内重试；成功响应丢失时先查询设计图，避免再次更新产生多余版本。

同名覆盖、版本递增、旧文件保留、重置待审阅、版本筛选及删除规则见下方业务说明。更新时的 `expected_version` 在准备凭证和实际写入时都验证，阻止两者之间的并发覆盖。

## 运行与部署

远程 MCP 与 FastAPI 在同一容器进程运行，不需要单独端口或共享的账号令牌。Nginx 将 `/mcp/` 转发到后端，并关闭响应缓冲。`MCP_PUBLIC_URL` 是上传地址的外部源地址（如 `http://192.168.124.9:8080`），不使用客户端传入的 Host 或转发头拼接上传地址。将外部访问源加入 `CORS_ORIGINS`，MCP 同时检查 Host/Origin。

临时上传凭证保存在内存中，单进程最多 128 个，重启即失效。当前部署保持单 worker；多 worker/多副本需要先将凭证迁移到共享存储。请求体和图片大小仍受现有后端及 Nginx 限制。图片和数据库保存在既有 Docker 卷中，升级不清空数据。

---

# 兼容：本地 stdio MCP

CheckX 提供标准 **stdio MCP 服务**，由 Codex 在本地启动。后端 REST API 需要先运行；服务不会自动启动后端，也不会把 HTTP API 当成 MCP 端点。

## 1. 创建令牌

登录 CheckX，在右上角头像菜单 →「设置」→「MCP」创建一个访问令牌，选择 30 / 90 / 365 天有效期。完整令牌只显示一次，请保存到本地私密配置或环境变量中。不要提交到 Git。

令牌拥有当前账号项目的数据访问能力。与浏览器登录分开，到期/撤销后立即失效。

## 2. 配置 Codex

以下配置使用当前工作区绝对路径。复制到个人 `~/.codex/config.toml`，或可信项目的 `.codex/config.toml`，注意不要覆盖已有配置：

```toml
[mcp_servers.checkx]
command = "/Users/gao/code/checkx/checkx-backend/.venv/bin/python"
args = ["/Users/gao/code/checkx/checkx-backend/mcp_server.py"]
env_vars = ["CHECKX_API_TOKEN"]
startup_timeout_sec = 15
tool_timeout_sec = 120

[mcp_servers.checkx.env]
CHECKX_API_URL = "http://127.0.0.1:8000"
# 可选：只允许上传这个目录下的文件，符号链接也会先解析再校验
# CHECKX_UPLOAD_ROOT = "/Users/gao/Designs"
# CHECKX_MAX_UPLOAD_MB = "20"
```

确保启动 Codex 的环境包含 `CHECKX_API_TOKEN`。`env_vars` 只转发变量，不会从任意 shell 或 `.env` 自动读取。通过桌面启动的应用不一定继承终端环境；这时可以在个人配置的 `[mcp_servers.checkx.env]` 中设置 `CHECKX_API_TOKEN = "你的令牌"`，并限制该配置文件的访问权限。**不要把实际令牌放进可提交的项目配置。**

本项目不会自动修改你的 Codex 配置。将目录复制到其他机器后需替换两个绝对路径。

配置字段依据 [OpenAI 官方 MCP 文档](https://developers.openai.com/codex/mcp/)：`command/args` 启动进程、`env` 设置环境、`env_vars` 转发环境。配置后重载 MCP 连接，可用 `codex mcp list` 检查注册状态。

## 3. 工具

| 工具 | 主要参数 | 作用 |
| --- | --- | --- |
| `list_projects` | `offset`, `limit` | 列出当前账号项目和统计 |
| `create_project` | `name`, `description` | 创建项目 |
| `list_pages` | `project_id`, `offset`, `limit` | 列出项目页面 |
| `create_page` | `project_id`, `name`, `description` | 创建页面 |
| `list_designs` | `page_id`, `offset`, `limit` | 列出图片、备注与状态 |
| `upload_design` | `page_id`, `file_path`, `name`, `notes` | 上传本地图片；同一页面原始文件名相同则覆盖 |
| `update_design_image` | `design_id`, `file_path`, `name?`, `notes?`, `expected_version?` | 按 ID 更新图片，版本号递增，保留旧文件 |
| `delete_design` | `design_id` | 永久删除设计图、所有版本图片及其全部审阅历史 |
| `get_review_results` | `design_id`, `offset`, `limit`, `version?` | 读取当前版本与状态，可筛选指定版本的审阅历史 |

列表和审阅查询工具显式标注只读；创建工具标注非破坏性写操作；上传（可能覆盖）、按 ID 更新和删除工具标注 `destructiveHint=true`。没有暴露审阅写入或账号管理工具。

成功的工具业务结果同样包含 `code/data/message`；失败通过 MCP 的标准 `isError` 工具结果返回，包含 HTTP 错误说明。

`file_path` 必须是 MCP 进程所在机器的绝对路径，不是后端服务器的目录，也不是任意公网 URL。一次工具调用上传一张图，多张图可多次调用。远程 API 强制使用 HTTPS，本机 loopback 允许 HTTP。`CHECKX_MAX_UPLOAD_MB` 是客户端预检查，最终仍受后端上限约束。

### 上传与同名覆盖

`upload_design(page_id, file_path, name, notes="")` 默认启用同名覆盖，无需额外参数。

- 匹配范围仅限指定 `page_id`。匹配键是本地路径的文件名（`original_name`，包含扩展名、区分大小写），不是展示名称 `name`。例如来自不同目录的 `home.png` 会在同一页面互相覆盖，`home.jpg` 或另一个页面的 `home.png` 则独立创建。
- 没有匹配项时创建 V1 新设计图；只有一个匹配项时版本号加一，保留设计图 `id`、创建时间与历史审阅记录，替换图片、展示名称和备注，更新修改时间，状态重置为 `pending`（待审阅）。省略 `notes` 会将备注设为空字符串。
- 历史审阅意见保留作修改参考，其结论针对旧图，不表示新图已通过。旧图片文件保留在原存储目录，数据库归档其版本与文件元数据；页面仅展示最新图片，暂不提供历史图片预览或恢复入口。每条审阅含 `version`，旧版意见不影响新版状态。
- 若历史数据已有多个同名文件，返回 HTTP 409 对应的 MCP 错误，不修改任何设计图。可通过 `list_designs` 确认目标 ID，然后使用 `update_design_image` 精确更新，无需删除其他方案。
- 损坏、超限、无权限或数据库写入失败的请求不会替换旧图。PostgreSQL 通过页面和设计图行锁串行处理并发覆盖。
- 成功返回 `{"code": 0, "data": <DesignOut>, "message": "ok"}`，包含设计图 ID、`version`、原始文件名、展示名称、备注、尺寸、状态和最新图片地址。

底层接口为 `POST /api/pages/{page_id}/designs`，MCP 自动传入表单字段 `overwrite=true`。网页上传未传该字段时仍创建独立设计图。

### 按设计图 ID 更新图片

```python
update_design_image(
    design_id="设计图 UUID",
    file_path="/Users/gao/Designs/home-revised.png",
    name=None,
    notes=None,
    expected_version=1,
)
```

- 必填：`design_id`（来自 `list_designs`）和 `file_path`（本机绝对路径）。按 ID 精确匹配，不需要 `page_id`，新文件可以改名，页面中有重复文件名也可更新。
- 可选：`name` / `notes` 省略或传 `null` 时保留原值；`notes=""` 清空备注，`name` 不能是空字符串。改名后 `original_name` 更新为新文件的文件名，后续同名上传按这个新文件名匹配。
- 可选：`expected_version` 是客户端已读取的当前版本。建议传入：并发更新、请求重试时不匹配返回 409，避免重复提交产生额外版本。省略时每次成功调用都递增版本，包括上传内容完全相同的图片。
- ID、所属页面和创建时间不变；图片、尺寸、文件大小、修改时间更新；`version` 从 V1 → V2 → V3 递增，状态重置为 `pending`。
- 每次更新先归档旧文件的元数据，旧文件继续保存在配置的 `STORAGE_DIR` 中。归档与版本递增在同一数据库事务内；失败不消耗版本号，也不删除旧文件。
- 列表不会增加额外卡片，列表、详情和图片读取接口始终展示最新图片。旧版本图片目前没有网页浏览/恢复入口。
- 底层为 `PUT /api/designs/{design_id}/image`，使用 multipart 表单：必填 `file`，可选 `name`、`notes`、`expected_version`。成功返回统一 `code/data/message`，`data.version` 为更新后的版本。

### 获取版本对应的审阅

`get_review_results(design_id, version=2)` 仅返回 V2 的审阅记录。省略 `version` 返回全部版本历史，按时间倒序分页。`data.design` 始终是最新设计图，`data.reviews[].version` 表明意见针对的版本；不能将旧版的“已通过”当作新版已通过。

人工提交审阅自动绑定当时的图片版本。网页会传 `expected_version`，如果提交时图片已更新，后端拒绝并提示重新查看。删除审阅只依据当前版本的剩余记录计算状态，删完当前版本的意见恢复 `pending`，不会回退到旧版结论。

推荐流程：`list_designs` 获取 ID/版本 → `get_review_results` 读取反馈 → `update_design_image` 上传修订 → 人工审阅新版。

### 现有数据升级

迁移 `0002_image_versions` 把现有设计图和已有审阅统一归入 V1，保留既有状态和文字记录。这是版本跟踪的起点；启用该功能之前的多轮审阅无法再准确拆分版本，之前已覆盖删除的图片也无法补回。从升级后的第一次更新开始完整保留旧图片。

### 删除图片

`delete_design(design_id)` 使用 `list_designs` 返回的设计图 UUID，调用 `DELETE /api/designs/{design_id}`。

- 永久删除设计图记录、关联的全部审阅记录、版本归档及所有版本的本地图片文件，无法撤销。
- 只能操作当前令牌所属账号的数据；记录不存在、已删除或属于其他账号时返回 HTTP 404 对应的 MCP 错误。
- 成功返回 `{"code": 0, "data": null, "message": "设计图及审阅记录已删除"}`。
- 数据库提交后才清理文件；若文件系统清理失败，会记录日志，数据库中的设计图已删除，可能留下需要运维清理的孤立文件。

修改服务代码后，运行中的后端需重启，Codex 也需重启 CheckX MCP 连接以加载新增工具。

## 示例请求

- “列出 CheckX 项目，找到「品牌官网改版」的首页。”
- “将 `/Users/gao/Designs/home-v2.png` 上传到首页，名称为「首页 V2」，备注为「调整标题留白」。”
- “读取这张设计图的审阅结果，按需要修改的事项整理给我。”
- “将修改后的 `/Users/gao/Designs/home.png` 再次上传到同一页面，覆盖原来的 `home.png`，名称为「首页 V2」。”
- “按设计图 ID 更新 `/Users/gao/Designs/home-revised.png`，当前版本为 2，保留名称和备注。”
- “删除 ID 为 `设计图 UUID` 的设计图及其审阅记录。”

## 常见问题

- **找不到令牌**：检查变量是否实际传给 MCP 进程；网页登录 Cookie 不会自动传给 MCP。
- **401**：检查令牌是否撤销或过期；重新创建后更新配置。
- **404**：检查 UUID 和当前令牌所属账号；不同账号的数据不能混用。
- **连接失败**：先确认 `/api/health` 正常，API URL 不要加 `/api` 后缀。
- **图片不可读取**：本地文件需为有效 PNG/JPG/WebP，满足大小和像素限制；若设置上传根目录，文件必须位于该目录内。
- **同名图片**：MCP 按同一页面内的原始文件名覆盖，展示名称不参与匹配；多个匹配项返回 409，可改用 `update_design_image` 按 ID 精确更新。
