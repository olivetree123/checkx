import os
from io import BytesIO
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pytest
from PIL import Image

from app.config import TORTOISE_ORM, settings
from app.main import app
from app.models import User
from app.security import _attempts


@pytest.fixture
async def client(tmp_path, monkeypatch):
    database = os.environ.get("TEST_DATABASE_URL", f"sqlite://{tmp_path / 'test.sqlite3'}")
    if database.startswith("postgres") and urlparse(database).path != "/checkx_test":
        raise RuntimeError("PostgreSQL tests require a dedicated database named checkx_test")
    monkeypatch.setitem(TORTOISE_ORM["connections"], "default", database)
    monkeypatch.setattr(settings, "auto_create_schema", True)
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "uploads")
    _attempts.clear()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as api:
            yield api
        # Only test DB is used; remove test accounts and cascading child rows.
        await User.all().delete()


async def register(client, email=None):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": email or f"{uuid4().hex}@example.com",
            "password": "test password 123",
            "display_name": "设计师",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def hierarchy(client):
    await register(client)
    project = (
        await client.post("/api/projects", json={"name": "网站改版", "description": "一期"})
    ).json()["data"]
    page = (
        await client.post(f"/api/projects/{project['id']}/pages", json={"name": "首页"})
    ).json()["data"]
    return project, page


def png():
    output = BytesIO()
    Image.new("RGB", (120, 80), "#6757e8").save(output, "PNG")
    return output.getvalue()


async def upload(client, page, name="首屏 V1"):
    response = await client.post(
        f"/api/pages/{page['id']}/designs",
        data={"name": name, "notes": "关注标题留白"},
        files={"file": ("../../fake.jpg", png(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]
