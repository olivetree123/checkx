import json

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.main import app
from app.remote_mcp import remote, tickets
from tests.conftest import hierarchy, png, register


@pytest.fixture(autouse=True)
def remote_settings(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "cors_origins", ["http://testserver"])
    monkeypatch.setattr(remote.settings.transport_security, "allowed_hosts", ["testserver"])
    monkeypatch.setattr(
        remote.settings.transport_security, "allowed_origins", ["http://testserver"]
    )
    tickets.clear()
    yield
    tickets.clear()


async def test_remote_protocol_upload_version_auth_and_isolation(client):
    _, page = await hierarchy(client)
    token = (await client.post("/api/tokens", json={"name": "remote test"})).json()["data"]
    assert (await client.post("/mcp/", json={})).status_code == 401  # Cookie is insufficient.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token['token']}"},
    ) as http:
        async with streamable_http_client("http://testserver/mcp/", http_client=http) as (
            read,
            write,
            _,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                assert len(tools) == 9
                upload_schema = next(t.inputSchema for t in tools if t.name == "upload_design")
                assert "file_path" not in upload_schema["properties"]

                async def call(name, arguments):
                    result = await session.call_tool(name, arguments)
                    assert not result.isError, result.content
                    return json.loads(result.content[0].text)["data"]

                ticket = await call(
                    "upload_design", {"page_id": page["id"], "name": "remote image"}
                )
                url = ticket["upload_url"]
                assert (await client.post(url, files={"file": ("x.png", png())})).status_code == 401
                rejected = await client.post(
                    url, headers=ticket["headers"], files={"file": ("x.png", b"invalid")}
                )
                assert rejected.status_code == 422
                response = await client.post(
                    url, headers=ticket["headers"], files={"file": ("x.png", png())}
                )
                assert response.status_code == 200, response.text
                design = response.json()["data"]
                assert design["version"] == 1
                assert (
                    await client.post(
                        url, headers=ticket["headers"], files={"file": ("x.png", png())}
                    )
                ).status_code == 401
                update = await call(
                    "update_design_image", {"design_id": design["id"], "expected_version": 1}
                )
                response = await client.post(
                    update["upload_url"],
                    headers=update["headers"],
                    files={"file": ("renamed.png", png())},
                )
                assert response.json()["data"]["version"] == 2
                assert (await call("list_designs", {"page_id": page["id"]}))[0]["version"] == 2
                await register(client)
                # Original bearer remains scoped to the first account regardless of browser cookies.
                assert len(await call("list_projects", {})) == 1
                second = (await client.post("/api/tokens", json={"name": "other"})).json()["data"]
                http.headers["Authorization"] = f"Bearer {second['token']}"
                assert await call("list_projects", {}) == []
                result = await session.call_tool("update_design_image", {"design_id": design["id"]})
                assert result.isError
                http.headers["Authorization"] = f"Bearer {token['token']}"
                pending = await call("upload_design", {"page_id": page["id"], "name": "pending"})
                from app.models import Credential

                await Credential.filter(id=token["id"]).delete()
                denied = await client.post(
                    pending["upload_url"],
                    headers=pending["headers"],
                    files={"file": ("x.png", png())},
                )
                assert denied.status_code == 401
        assert (await http.post("/mcp/", json={})).status_code == 401


async def test_upload_ticket_expiry(client):
    _, page = await hierarchy(client)
    token = (await client.post("/api/tokens", json={"name": "expiry"})).json()["data"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token['token']}"},
    ) as http:
        async with streamable_http_client("http://testserver/mcp/", http_client=http) as (
            read,
            write,
            _,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "upload_design", {"page_id": page["id"], "name": "expire"}
                )
                ticket = json.loads(result.content[0].text)["data"]
                next(iter(tickets.values())).expires = 0
                response = await client.post(
                    ticket["upload_url"],
                    headers=ticket["headers"],
                    files={"file": ("x.png", png())},
                )
                assert response.status_code == 410
