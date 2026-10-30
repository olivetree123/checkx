"""Authenticated Streamable HTTP MCP and bounded, one-use local-file uploads."""

import asyncio
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, Request, UploadFile
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse

from app.config import settings
from app.schemas import DesignInput, ImageUpdateInput
from app.security import current_user, digest
from app.services import design_out, owned_design, owned_page
from app.services import upload_design as store_design


def create_server():
    return FastMCP(
        "CheckX",
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        instructions="先列出项目、页面再操作设计图。上传本地图片：调用 upload_design 或 "
        "update_design_image 获得临时上传 URL 和 headers，在本机用 curl -F file=@绝对路径 "
        "发送 POST，不要把本地路径传给服务器。凭证5分钟有效、成功后不可重用。"
        "上传完成后用 list_designs 或 get_review_results 确认结果。更新自动递增版本并保留旧图。",
        transport_security=TransportSecuritySettings(
            allowed_hosts=list(
                {
                    urlparse(url).netloc
                    for url in [
                        *settings.cors_origins,
                        str(settings.mcp_public_url or settings.cors_origins[0]),
                    ]
                }
            ),
            allowed_origins=settings.cors_origins,
        ),
    )


remote = create_server()
definitions = []


def tool(**options):
    def register(fn):
        definitions.append((fn, options))
        return fn

    return register


async def api(ctx: Context, method: str, path: str, **kwargs) -> dict:
    from app.main import app

    authorization = ctx.request_context.request.headers.get("authorization", "")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://checkx",
        headers={"Authorization": authorization},
    ) as client:
        response = await client.request(method, "/api" + path, **kwargs)
    result = response.json()
    if response.is_error:
        raise ValueError(f"CheckX HTTP {response.status_code}: {result['message']}")
    return result


@tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_projects(ctx: Context, offset: int = 0, limit: int = 50) -> dict:
    """列出当前账号项目和统计。"""
    return await api(ctx, "GET", "/projects", params={"offset": offset, "limit": limit})


@tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_project(ctx: Context, name: str, description: str = "") -> dict:
    """创建项目。"""
    return await api(ctx, "POST", "/projects", json={"name": name, "description": description})


@tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_pages(ctx: Context, project_id: UUID, offset: int = 0, limit: int = 100) -> dict:
    """列出项目页面。"""
    return await api(
        ctx, "GET", f"/projects/{project_id}/pages", params={"offset": offset, "limit": limit}
    )


@tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_page(ctx: Context, project_id: UUID, name: str, description: str = "") -> dict:
    """创建项目页面。"""
    return await api(
        ctx,
        "POST",
        f"/projects/{project_id}/pages",
        json={"name": name, "description": description},
    )


@tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_designs(ctx: Context, page_id: UUID, offset: int = 0, limit: int = 100) -> dict:
    """列出最新设计图、版本、备注和审阅状态。"""
    return await api(
        ctx, "GET", f"/pages/{page_id}/designs", params={"offset": offset, "limit": limit}
    )


@tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_review_results(
    ctx: Context, design_id: UUID, offset: int = 0, limit: int = 100, version: int | None = None
) -> dict:
    """获取审阅历史，可按版本筛选；design 始终是最新图片。"""
    params = {"offset": offset, "limit": limit}
    if version is not None:
        params["version"] = version
    return await api(ctx, "GET", f"/designs/{design_id}/reviews", params=params)


@tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_design(ctx: Context, design_id: UUID) -> dict:
    """永久删除设计图、所有图片版本及全部审阅。"""
    return await api(ctx, "DELETE", f"/designs/{design_id}")


@dataclass
class Ticket:
    secret_hash: str
    authorization: str
    expires: float
    page_id: UUID
    design_id: UUID | None
    payload: DesignInput | ImageUpdateInput
    busy: bool = False


tickets: dict[str, Ticket] = {}
lock = asyncio.Lock()


async def prepare(
    ctx: Context,
    page_id: UUID | None,
    design_id: UUID | None,
    payload: DesignInput | ImageUpdateInput,
) -> dict:
    request = ctx.request_context.request
    user = await current_user(request)
    if design_id:
        design = await owned_design(design_id, user)
        page_id = design.page_id
        if payload.expected_version is not None and payload.expected_version != design.version:
            raise ValueError("图片版本已更新，请获取最新版本后重试")
    else:
        await owned_page(page_id, user)
    async with lock:
        now = time.monotonic()
        for key in list(tickets):
            if tickets[key].expires < now and not tickets[key].busy:
                del tickets[key]
        if len(tickets) >= 128:
            raise ValueError("上传任务过多，请稍后重试")
        key, secret = uuid4().hex, secrets.token_urlsafe(32)
        tickets[key] = Ticket(
            digest(secret), request.headers["authorization"], now + 300, page_id, design_id, payload
        )
    # The public origin is configured by the operator, never taken from forwarded headers.
    origin = str(settings.mcp_public_url or settings.cors_origins[0]).rstrip("/")
    return {
        "code": 0,
        "data": {
            "upload_url": f"{origin}/api/mcp-uploads/{key}",
            "method": "POST",
            "headers": {"X-Upload-Token": secret},
            "file_field": "file",
            "expires_in": 300,
            "max_upload_mb": settings.max_upload_mb,
            "instructions": "在本机运行 curl --fail-with-body -X POST <upload_url> "
            "-H 'X-Upload-Token: <凭证>' -F 'file=@/本地图片绝对路径'。"
            "不要手动设置 Content-Type；成功响应 data 为设计图，含 id 和 version。",
        },
        "message": "上传凭证已创建，图片尚未上传",
    }


@tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def upload_design(ctx: Context, page_id: UUID, name: str, notes: str = "") -> dict:
    """获取本地图片上传凭证；再在本机用 curl POST multipart file。

    同页同原始文件名覆盖，版本号加一，保留旧图片和审阅，重置为 pending。
    name 为展示名称，不是文件名匹配键。此调用只准备上传，不读取服务器本地文件。
    """
    return await prepare(ctx, page_id, None, DesignInput(name=name, notes=notes))


@tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def update_design_image(
    ctx: Context,
    design_id: UUID,
    name: str | None = None,
    notes: str | None = None,
    expected_version: int | None = None,
) -> dict:
    """按设计图 ID 获取更新图片凭证；在本机用 curl 上传，新文件可改名。

    成功后递增版本、保留旧文件并重置待审阅；省略名称备注保留原值，notes='' 清空。
    建议传 expected_version 防止重复更新及并发覆盖。
    """
    return await prepare(
        ctx,
        None,
        design_id,
        ImageUpdateInput(name=name, notes=notes, expected_version=expected_version),
    )


async def receive_upload(key: str, request: Request, file: UploadFile):
    async with lock:
        ticket = tickets.get(key)
        supplied = request.headers.get("x-upload-token", "")
        if ticket is None or not secrets.compare_digest(ticket.secret_hash, digest(supplied)):
            raise HTTPException(401, "无效上传凭证")
        if ticket.expires < time.monotonic():
            del tickets[key]
            raise HTTPException(410, "上传凭证已过期")
        if ticket.busy:
            raise HTTPException(409, "该上传正在处理")
        ticket.busy = True
    try:
        # Revalidate the originating API token, so revocation immediately invalidates tickets.
        auth_request = Request(
            {**request.scope, "headers": [(b"authorization", ticket.authorization.encode())]}
        )
        user = await current_user(auth_request)
        page = await owned_page(ticket.page_id, user)
        result = await store_design(
            page, file, ticket.payload, overwrite=True, design_id=ticket.design_id
        )
        async with lock:
            tickets.pop(key, None)
        return {
            "code": 0,
            "data": design_out(result).model_dump(mode="json"),
            "message": "图片已上传",
        }
    finally:
        ticket.busy = False
        await file.close()


class AuthenticateMCP:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope)
            try:
                if not request.headers.get("authorization", "").lower().startswith("bearer "):
                    raise HTTPException(401, "需要 CheckX MCP 访问令牌")
                await current_user(request)
            except HTTPException as exc:
                return await JSONResponse(
                    {"code": exc.status_code, "data": None, "message": exc.detail},
                    status_code=exc.status_code,
                    headers={"WWW-Authenticate": "Bearer"},
                )(scope, receive, send)
        await self.app(scope, receive, send)


mcp_app = AuthenticateMCP(None)


def configure():
    global remote
    remote = create_server()
    for fn, options in definitions:
        remote.add_tool(fn, **options)
    mcp_app.app = remote.streamable_http_app()
    return remote
