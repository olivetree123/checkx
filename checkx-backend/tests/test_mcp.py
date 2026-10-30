import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests.conftest import png


@pytest.fixture
async def live_api(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite://{tmp_path / 'mcp.sqlite3'}",
        "STORAGE_DIR": str(tmp_path / "uploads"),
        "AUTO_CREATE_SCHEMA": "true",
    }
    log_path = tmp_path / "server.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as api:
                for _ in range(100):
                    try:
                        if (await api.get("/api/health")).status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    await asyncio.sleep(0.1)
                else:
                    pytest.fail(f"Backend did not start: {log_path.read_text()}")
                yield api
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


async def test_stdio_protocol_upload_and_review_results(live_api, tmp_path):
    api = live_api
    response = await api.post(
        "/api/auth/register",
        json={
            "email": f"{uuid4().hex}@example.com",
            "password": "password123",
            "display_name": "MCP tester",
        },
    )
    assert response.status_code == 201
    credential = (await api.post("/api/tokens", json={"name": "Integration test"})).json()["data"]
    source = tmp_path / "source"
    source.mkdir()
    image = source / "design.png"
    image.write_bytes(png())
    outside = tmp_path / "outside.png"
    outside.write_bytes(png())
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve().parents[1] / "mcp_server.py")],
        env={
            **os.environ,
            "CHECKX_API_URL": str(api.base_url),
            "CHECKX_API_TOKEN": credential["token"],
            "CHECKX_UPLOAD_ROOT": str(source),
        },
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tool_names = {tool.name for tool in (await session.list_tools()).tools}
        assert {
            "upload_design",
            "get_review_results",
            "list_projects",
            "list_pages",
            "list_designs",
            "create_project",
            "create_page",
            "delete_design",
            "update_design_image",
        } == tool_names
        annotations = {tool.name: tool.annotations for tool in (await session.list_tools()).tools}
        assert annotations["upload_design"].destructiveHint
        assert annotations["delete_design"].destructiveHint
        assert annotations["update_design_image"].destructiveHint

        async def call(name, arguments):
            result = await session.call_tool(name, arguments)
            assert not result.isError, result.content
            return json.loads(result.content[0].text)["data"]

        project = await call("create_project", {"name": "MCP 项目"})
        page = await call("create_page", {"project_id": project["id"], "name": "首页"})
        design = await call(
            "upload_design",
            {
                "page_id": page["id"],
                "file_path": str(image),
                "name": "MCP 设计稿",
                "notes": "由 Codex 上传",
            },
        )
        assert design["notes"] == "由 Codex 上传" and design["status"] == "pending"
        await api.post(
            f"/api/designs/{design['id']}/reviews",
            json={"content": "请放大标题", "status": "changes_requested", "author_label": "审阅者"},
        )
        result = await call("get_review_results", {"design_id": design["id"]})
        assert result["design"]["status"] == "changes_requested"
        assert result["reviews"][0]["content"] == "请放大标题"
        assert (await call("list_designs", {"page_id": page["id"]}))[0]["id"] == design["id"]
        denied = await session.call_tool(
            "upload_design", {"page_id": page["id"], "file_path": str(outside), "name": "拒绝"}
        )
        assert denied.isError
        updated = await call(
            "upload_design",
            {"page_id": page["id"], "file_path": str(image), "name": "修改后的设计稿"},
        )
        assert updated["id"] == design["id"] and updated["status"] == "pending"
        assert updated["name"] == "修改后的设计稿" and updated["notes"] == ""
        assert len(await call("list_designs", {"page_id": page["id"]})) == 1
        assert len((await call("get_review_results", {"design_id": design["id"]}))["reviews"]) == 1
        assert updated["version"] == 2
        renamed = source / "renamed.png"
        renamed.write_bytes(png())
        revised = await call(
            "update_design_image",
            {
                "design_id": design["id"],
                "file_path": str(renamed),
                "expected_version": 2,
            },
        )
        assert revised["version"] == 3 and revised["id"] == design["id"]
        assert revised["name"] == updated["name"] and revised["notes"] == updated["notes"]
        assert revised["original_name"] == "renamed.png"
        assert len(list((tmp_path / "uploads").iterdir())) == 3
        history = await call("get_review_results", {"design_id": design["id"], "version": 1})
        assert history["reviews"][0]["version"] == 1
        assert history["design"]["version"] == 3
        assert (
            await call(
                "get_review_results",
                {
                    "design_id": design["id"],
                    "version": 3,
                },
            )
        )["reviews"] == []
        for arguments in [
            {"file_path": str(outside)},
            {"file_path": str(renamed), "expected_version": 2},
        ]:
            assert (
                await session.call_tool(
                    "update_design_image",
                    {
                        "design_id": design["id"],
                        **arguments,
                    },
                )
            ).isError
        assert await call("delete_design", {"design_id": design["id"]}) is None
        assert list((tmp_path / "uploads").iterdir()) == []
        assert await call("list_designs", {"page_id": page["id"]}) == []
        assert (await session.call_tool("get_review_results", {"design_id": design["id"]})).isError
        assert (await session.call_tool("delete_design", {"design_id": design["id"]})).isError
        await api.delete(f"/api/tokens/{credential['id']}")
        assert (await session.call_tool("list_projects", {})).isError
