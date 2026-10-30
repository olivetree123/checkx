"""Local stdio MCP bridge. Uses exactly the same authenticated HTTP API as the UI."""

import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

mcp = FastMCP(
    "CheckX",
    instructions="先列出项目和页面，再操作设计图。上传按同一页面内的原始文件名覆盖，"
    "保留 ID、旧图片与历史审阅，版本号递增并重置为待审阅。已有 ID 时优先使用 "
    "update_design_image 更新。删除设计图会永久删除所有版本图片和审阅记录。",
)


def client() -> httpx.AsyncClient:
    url = os.environ.get("CHECKX_API_URL", "http://127.0.0.1:8000").rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("CHECKX_API_URL must be an HTTP(S) origin")
    if parsed.scheme == "http" and parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("Remote CheckX connections require HTTPS to protect the access token")
    token = os.environ.get("CHECKX_API_TOKEN", "")
    if not token:
        raise ValueError("请在 CheckX 的 MCP 接入中创建令牌，并设置 CHECKX_API_TOKEN")
    return httpx.AsyncClient(
        base_url=url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
        follow_redirects=False,
    )


async def request(method: str, path: str, **kwargs) -> dict:
    async with client() as api:
        response = await api.request(method, path, **kwargs)
    try:
        result = response.json()
    except ValueError as exc:
        raise ValueError(f"CheckX 返回非 JSON 响应：HTTP {response.status_code}") from exc
    if response.is_error:
        raise ValueError(f"CheckX HTTP {response.status_code}: {result.get('message', '请求失败')}")
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_projects(offset: int = 0, limit: int = 50) -> dict:
    """列出当前账号的项目及审阅统计。支持 offset/limit 分页。"""
    return await request("GET", "/api/projects", params={"offset": offset, "limit": limit})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_project(name: str, description: str = "") -> dict:
    """创建一个设计项目。"""
    return await request("POST", "/api/projects", json={"name": name, "description": description})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_pages(project_id: UUID, offset: int = 0, limit: int = 100) -> dict:
    """列出项目下的页面及页面 ID。"""
    return await request(
        "GET", f"/api/projects/{project_id}/pages", params={"offset": offset, "limit": limit}
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_page(project_id: UUID, name: str, description: str = "") -> dict:
    """在项目下创建一个页面。"""
    return await request(
        "POST", f"/api/projects/{project_id}/pages", json={"name": name, "description": description}
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_designs(page_id: UUID, offset: int = 0, limit: int = 100) -> dict:
    """列出页面的设计图、备注和最新审阅状态。"""
    return await request(
        "GET", f"/api/pages/{page_id}/designs", params={"offset": offset, "limit": limit}
    )


def upload_path(file_path: str) -> Path:
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        raise ValueError("file_path 必须为绝对路径")
    path = path.resolve(strict=True)
    root = os.environ.get("CHECKX_UPLOAD_ROOT")
    if root and not path.is_relative_to(Path(root).expanduser().resolve(strict=True)):
        raise ValueError("图片必须位于 CHECKX_UPLOAD_ROOT 目录内")
    if not path.is_file():
        raise ValueError("路径不是普通文件")
    if path.stat().st_size > int(os.environ.get("CHECKX_MAX_UPLOAD_MB", "20")) * 1024 * 1024:
        raise ValueError("图片超过 MCP 上传大小限制")
    return path


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def upload_design(page_id: UUID, file_path: str, name: str, notes: str = "") -> dict:
    """上传 MCP 所在计算机的本地 PNG/JPG/WebP 图片，设置名称和备注。

    file_path 使用绝对路径；CHECKX_UPLOAD_ROOT 可限制允许上传的目录。
    同一页面中原始文件名（含扩展名，区分大小写）相同则覆盖；name 是展示名称，不是匹配键。
    覆盖保留设计图 ID、旧文件与历史审阅，版本号加一，替换图片、名称和备注，重置为 pending。
    历史数据若有多个同名文件则返回 409，不做修改。
    """
    path = upload_path(file_path)
    with path.open("rb") as file:
        return await request(
            "POST",
            f"/api/pages/{page_id}/designs",
            data={"name": name, "notes": notes, "overwrite": "true"},
            files={"file": (path.name, file, "application/octet-stream")},
        )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def update_design_image(
    design_id: UUID,
    file_path: str,
    name: str | None = None,
    notes: str | None = None,
    expected_version: int | None = None,
) -> dict:
    """按设计图 ID 更新图片，自动增加版本号并保留旧图片文件和全部审阅记录。

    file_path 为 MCP 所在计算机的绝对路径，受 CHECKX_UPLOAD_ROOT 限制。
    不按文件名匹配；新文件可以改名。省略 name/notes 保留原值，notes="" 清空备注。
    更新后状态为 pending，页面只显示最新图片。每次成功调用都会新增版本。
    建议传 expected_version（从 list_designs 获取），并发更新或重试时版本不匹配返回 409。
    """
    path = upload_path(file_path)
    data = {
        key: str(value)
        for key, value in {
            "name": name,
            "notes": notes,
            "expected_version": expected_version,
        }.items()
        if value is not None
    }
    with path.open("rb") as file:
        return await request(
            "PUT",
            f"/api/designs/{design_id}/image",
            data=data,
            files={"file": (path.name, file, "application/octet-stream")},
        )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_design(design_id: UUID) -> dict:
    """永久删除当前账号的设计图、所有版本图片文件及全部审阅历史。不可恢复。

    先通过 list_designs 确认 design_id；不存在或不属于当前账号时返回 404。
    """
    return await request("DELETE", f"/api/designs/{design_id}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_review_results(
    design_id: UUID, offset: int = 0, limit: int = 100, version: int | None = None
) -> dict:
    """获取设计图当前版本、状态、备注及审阅历史（最新记录在前，每条含 version）。

    默认返回全部版本审阅；传 version 只返回该版本审阅。design 始终为最新版本。
    """
    params = {"offset": offset, "limit": limit}
    if version is not None:
        params["version"] = version
    return await request("GET", f"/api/designs/{design_id}/reviews", params=params)


if __name__ == "__main__":
    mcp.run(transport="stdio")
