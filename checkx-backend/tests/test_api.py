import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from app.config import settings
from app.main import app
from app.models import Credential, Design, User
from app.security import digest
from tests.conftest import hierarchy, png, register, upload


async def test_auth_shared_sessions_password_exact_and_logout(client):
    email = "Studio@Example.com"
    payload = {"email": email, "password": "  password123  ", "display_name": "Studio"}
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["data"]["email"] == email.lower()
    assert "password" not in response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert (await User.get(email=email.lower())).password_hash != payload["password"]
    first_cookie = client.cookies.get("checkx_session")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as second:
        bad = await second.post("/api/auth/login", json={"email": email, "password": "password123"})
        assert bad.status_code == 401
        response = await second.post(
            "/api/auth/login", json={k: v for k, v in payload.items() if k != "display_name"}
        )
        assert response.status_code == 200
        assert second.cookies.get("checkx_session") != first_cookie
        assert (await client.get("/api/auth/me")).status_code == 200
        await client.post("/api/auth/logout")
        assert (await client.get("/api/auth/me")).status_code == 401
        assert (await second.get("/api/auth/me")).status_code == 200
    duplicate = await client.post("/api/auth/register", json=payload)
    assert duplicate.status_code == 409


async def test_complete_review_flow_and_statistics(client):
    project, page = await hierarchy(client)
    first = await upload(client, page)
    second = await upload(client, page, "首屏 V2")
    assert first["mime_type"] == "image/png"  # Actual bytes override fake extension and MIME.
    assert first["status"] == "pending" and first["width"] == 120
    assert first["original_name"] == "fake.jpg"
    image = await client.get(first["image_url"])
    assert image.content == png() and image.headers["content-type"] == "image/png"
    assert "private" in image.headers["cache-control"]
    for status, text in [
        ("changes_requested", "标题留白增加 16px"),
        ("approved", "调整已确认，通过"),
    ]:
        response = await client.post(
            f"/api/designs/{first['id']}/reviews",
            json={"status": status, "content": text, "author_label": "产品同事"},
        )
        assert response.status_code == 201, response.text
    result = (await client.get(f"/api/designs/{first['id']}/reviews")).json()["data"]
    assert result["design"]["status"] == "approved"
    assert len(result["reviews"]) == 2
    assert result["reviews"][0]["status"] == "approved"
    assert result["reviews"][1]["content"] == "标题留白增加 16px"
    stats = (await client.get(f"/api/projects/{project['id']}")).json()["data"]
    assert (
        stats["page_count"],
        stats["design_count"],
        stats["approved_count"],
        stats["pending_count"],
    ) == (1, 2, 1, 1)
    updated_page = await client.put(f"/api/pages/{page['id']}", json={"name": "首页更新"})
    assert updated_page.json()["data"]["design_count"] == 2
    filtered = (await client.get(f"/api/pages/{page['id']}/designs?status=pending")).json()["data"]
    assert [row["id"] for row in filtered] == [second["id"]]
    assert (
        len((await client.get(f"/api/pages/{page['id']}/designs?limit=1&offset=1")).json()["data"])
        == 1
    )
    changed = await client.put(
        f"/api/designs/{first['id']}", json={"name": "最终稿", "notes": "确认"}
    )
    assert changed.json()["data"]["status"] == "approved"
    assert changed.json()["data"]["name"] == "最终稿"


async def test_account_isolation_on_all_resource_routes(client):
    project, page = await hierarchy(client)
    design = await upload(client, page)
    await register(client)  # Separate owner.
    assert (await client.get("/api/projects")).json()["data"] == []
    routes = [
        ("GET", f"/api/projects/{project['id']}", None),
        ("PUT", f"/api/projects/{project['id']}", {"name": "hacked"}),
        ("GET", f"/api/projects/{project['id']}/pages", None),
        ("POST", f"/api/projects/{project['id']}/pages", {"name": "hacked"}),
        ("PUT", f"/api/pages/{page['id']}", {"name": "hacked"}),
        ("GET", f"/api/pages/{page['id']}/designs", None),
        ("GET", f"/api/designs/{design['id']}", None),
        ("GET", design["image_url"], None),
        ("GET", f"/api/designs/{design['id']}/reviews", None),
        (
            "POST",
            f"/api/designs/{design['id']}/reviews",
            {"status": "approved", "content": "hacked"},
        ),
        ("PUT", f"/api/designs/{design['id']}", {"name": "hacked"}),
        ("DELETE", f"/api/designs/{design['id']}", None),
    ]
    for method, route, body in routes:
        response = await client.request(method, route, json=body)
        assert response.status_code == 404, (method, route, response.text)
    denied = await client.post(
        f"/api/pages/{page['id']}/designs", data={"name": "no"}, files={"file": ("x.png", png())}
    )
    assert denied.status_code == 404


@pytest.mark.parametrize(
    "body", [b"not an image", b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', png()[:30]]
)
async def test_invalid_images_leave_no_files(client, body):
    _, page = await hierarchy(client)
    response = await client.post(
        f"/api/pages/{page['id']}/designs",
        data={"name": "test"},
        files={"file": ("test.png", body, "image/png")},
    )
    assert response.status_code == 422
    assert not list(settings.storage_dir.iterdir())
    assert await Design.all().count() == 0


async def test_upload_size_and_pixels_are_bounded(client, monkeypatch):
    _, page = await hierarchy(client)
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    large = await client.post(
        f"/api/pages/{page['id']}/designs",
        data={"name": "test"},
        files={"file": ("x.png", b"x" * (1024 * 1024 + 1))},
    )
    assert large.status_code == 413
    monkeypatch.setattr(settings, "max_image_pixels", 100)
    pixels = await client.post(
        f"/api/pages/{page['id']}/designs", data={"name": "test"}, files={"file": ("x.png", png())}
    )
    assert pixels.status_code == 422

    async def chunks():
        for _ in range(4):
            yield b"x" * 1024 * 1024

    chunked = await client.post(f"/api/pages/{page['id']}/designs", content=chunks())
    assert chunked.status_code == 413 and chunked.json()["code"] == 413
    assert not list(settings.storage_dir.iterdir())


async def test_uniform_errors_and_csrf(client):
    responses = [
        await client.get("/api/projects"),
        await client.get("/api/missing"),
        await client.post("/api/auth/register", json={"email": "bad"}),
        await client.post("/api/auth/login", headers={"Origin": "https://evil.example"}, json={}),
        await client.patch("/api/auth/login"),
    ]
    assert [r.status_code for r in responses] == [401, 404, 422, 403, 405]
    for response in responses:
        assert set(response.json()) == {"code", "data", "message"}
        assert response.json()["code"] == response.status_code
    await register(client)
    assert (await client.post("/api/projects", json={"name": "   "})).status_code == 422
    assert (await client.get(f"/api/projects/{uuid4()}")).status_code == 404
    assert (await client.get("/api/projects/not-uuid")).status_code == 422


async def test_api_token_hash_expiry_revocation_and_isolation(client):
    await register(client)
    created = (await client.post("/api/tokens", json={"name": "Codex", "expires_days": 30})).json()[
        "data"
    ]
    credential = await Credential.get(id=created["id"])
    assert credential.token_hash == digest(created["token"])
    rows = (await client.get("/api/tokens")).json()["data"]
    assert "token" not in rows[0] and "token_hash" not in rows[0]
    headers = {"Authorization": f"Bearer {created['token']}"}
    assert (await client.get("/api/projects", headers=headers)).status_code == 200
    assert (
        await client.post("/api/tokens", headers=headers, json={"name": "chain"})
    ).status_code == 403
    credential.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await credential.save()
    assert (await client.get("/api/projects", headers=headers)).status_code == 401
    assert (await client.delete(f"/api/tokens/{created['id']}")).status_code == 200
    assert (await client.get("/api/projects", headers=headers)).status_code == 401


async def test_delete_removes_file_and_reviews(client):
    _, page = await hierarchy(client)
    design = await upload(client, page)
    await client.post(
        f"/api/designs/{design['id']}/reviews", json={"content": "通过", "status": "approved"}
    )
    assert len(list(settings.storage_dir.iterdir())) == 1
    assert (await client.delete(f"/api/designs/{design['id']}")).status_code == 200
    assert not list(settings.storage_dir.iterdir())
    assert (await client.get(design["image_url"])).status_code == 404


async def test_concurrent_reviews_preserve_both_and_latest_status(client):
    _, page = await hierarchy(client)
    design = await upload(client, page)
    responses = await asyncio.gather(
        *[
            client.post(
                f"/api/designs/{design['id']}/reviews",
                json={"content": f"意见 {i}", "status": status},
            )
            for i, status in enumerate(["approved", "changes_requested", "approved"])
        ]
    )
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    result = (await client.get(f"/api/designs/{design['id']}/reviews")).json()["data"]
    assert len(result["reviews"]) == 3
    assert result["design"]["status"] == result["reviews"][0]["status"]


async def test_login_rate_limited(client):
    for _ in range(20):
        response = await client.post(
            "/api/auth/login", json={"email": "missing@example.com", "password": "password123"}
        )
        assert response.status_code == 401
    assert (
        await client.post(
            "/api/auth/login", json={"email": "missing@example.com", "password": "password123"}
        )
    ).status_code == 429


async def test_account_update_requires_password_for_email_and_is_atomic(client):
    user = await register(client)
    payload = {"display_name": "新的名字", "email": user["email"]}
    assert (await client.put("/api/auth/me", json=payload)).json()["data"][
        "display_name"
    ] == "新的名字"
    payload["email"] = "new-email@example.com"
    assert (await client.put("/api/auth/me", json=payload)).status_code == 400
    assert (await client.get("/api/auth/me")).json()["data"]["email"] == user["email"]
    payload["current_password"] = "test password 123"
    assert (await client.put("/api/auth/me", json=payload)).status_code == 200
    await client.post("/api/auth/logout")
    assert (
        await client.post(
            "/api/auth/login", json={"email": user["email"], "password": "test password 123"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/auth/login", json={"email": payload["email"], "password": "test password 123"}
        )
    ).status_code == 200


async def test_account_duplicate_email_and_api_token_cannot_change_credentials(client):
    first = await register(client)
    other = await register(client)
    response = await client.put(
        "/api/auth/me",
        json={
            "display_name": "不要保存",
            "email": first["email"],
            "current_password": "test password 123",
        },
    )
    assert response.status_code == 409
    me = (await client.get("/api/auth/me")).json()["data"]
    assert me["email"] == other["email"] and me["display_name"] == other["display_name"]
    token = (await client.post("/api/tokens", json={"name": "MCP"})).json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert (
        await client.put(
            "/api/auth/me", headers=headers, json={"display_name": "no", "email": other["email"]}
        )
    ).status_code == 403
    assert (
        await client.put(
            "/api/auth/password",
            headers=headers,
            json={"current_password": "test password 123", "new_password": "new password 123"},
        )
    ).status_code == 403


async def test_password_change_revokes_other_browser_sessions(client):
    user = await register(client)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as second:
        await second.post(
            "/api/auth/login", json={"email": user["email"], "password": "test password 123"}
        )
        bad = await client.put(
            "/api/auth/password",
            json={"current_password": "incorrect 123", "new_password": "  new password 123  "},
        )
        assert bad.status_code == 400
        assert (await second.get("/api/auth/me")).status_code == 200
        response = await client.put(
            "/api/auth/password",
            json={"current_password": "test password 123", "new_password": "  new password 123  "},
        )
        assert response.status_code == 200
        assert (await client.get("/api/auth/me")).status_code == 200
        assert (await second.get("/api/auth/me")).status_code == 401
        assert (
            await second.post(
                "/api/auth/login", json={"email": user["email"], "password": "test password 123"}
            )
        ).status_code == 401
        assert (
            await second.post(
                "/api/auth/login", json={"email": user["email"], "password": "  new password 123  "}
            )
        ).status_code == 200


async def test_upload_overwrite_file_history_cleanup_and_page_scope(client):
    from io import BytesIO

    from PIL import Image

    from app.models import Review

    project, page = await hierarchy(client)
    design = await upload(client, page)
    record = await Design.get(id=design["id"])
    old_path = settings.storage_dir / record.stored_name
    await client.post(
        f"/api/designs/{design['id']}/reviews",
        json={"content": "旧版本通过", "status": "approved"},
    )
    replacement = BytesIO()
    Image.new("RGB", (48, 32), "red").save(replacement, "PNG")
    endpoint = f"/api/pages/{page['id']}/designs"
    invalid = await client.post(
        endpoint,
        data={"name": "invalid", "overwrite": "true"},
        files={"file": ("fake.jpg", b"invalid")},
    )
    assert invalid.status_code == 422
    assert old_path.read_bytes() == png()
    assert (await Design.get(id=design["id"])).status == "approved"
    updated = await client.post(
        endpoint,
        data={"name": "新名称", "notes": "新版", "overwrite": "true"},
        files={"file": ("fake.jpg", replacement.getvalue())},
    )
    assert updated.status_code == 201, updated.text
    new = updated.json()["data"]
    assert new["id"] == design["id"] and new["created_at"] == design["created_at"]
    assert (new["name"], new["notes"], new["status"], new["width"], new["height"]) == (
        "新名称",
        "新版",
        "pending",
        48,
        32,
    )
    assert new["image_url"] != design["image_url"]
    assert (await client.get(new["image_url"])).content == replacement.getvalue()
    assert old_path.read_bytes() == png()
    assert await Design.filter(page_id=page["id"]).count() == 1
    assert await Review.filter(design_id=design["id"]).count() == 1
    other_page = (
        await client.post(f"/api/projects/{project['id']}/pages", json={"name": "其他页面"})
    ).json()["data"]
    other = await client.post(
        f"/api/pages/{other_page['id']}/designs",
        data={"name": "新名称", "overwrite": "true"},
        files={"file": ("fake.jpg", png())},
    )
    assert other.json()["data"]["id"] != design["id"]
    # Same display name but different original file name creates another design.
    different = await client.post(
        endpoint,
        data={"name": "新名称", "overwrite": "true"},
        files={"file": ("other.png", png())},
    )
    assert different.json()["data"]["id"] != design["id"]
    new_path = settings.storage_dir / (await Design.get(id=design["id"])).stored_name
    assert (await client.delete(f"/api/designs/{design['id']}")).status_code == 200
    assert not new_path.exists()
    assert not old_path.exists()
    assert await Review.filter(design_id=design["id"]).count() == 0


async def test_upload_overwrite_duplicates_and_ownership(client):
    _, page = await hierarchy(client)
    first = await upload(client, page)
    second = await upload(client, page)
    paths = set(settings.storage_dir.iterdir())
    endpoint = f"/api/pages/{page['id']}/designs"
    response = await client.post(
        endpoint,
        data={"name": "新名称", "overwrite": "true"},
        files={"file": ("fake.jpg", png())},
    )
    assert response.status_code == 409
    assert set(settings.storage_dir.iterdir()) == paths
    assert await Design.filter(id__in=[first["id"], second["id"]]).count() == 2
    await register(client)
    response = await client.post(
        endpoint,
        data={"name": "新名称", "overwrite": "true"},
        files={"file": ("fake.jpg", png())},
    )
    assert response.status_code == 404
    assert set(settings.storage_dir.iterdir()) == paths


async def test_upload_overwrite_concurrent_postgres(client):
    from tortoise import connections

    if connections.get("default").capabilities.dialect != "postgres":
        pytest.skip("Requires PostgreSQL row locks")
    _, page = await hierarchy(client)

    async def put(name):
        response = await client.post(
            f"/api/pages/{page['id']}/designs",
            data={"name": name, "overwrite": "true"},
            files={"file": ("same.png", png())},
        )
        assert response.status_code == 201, response.text
        return response.json()["data"]

    results = await asyncio.gather(put("A"), put("B"), put("C"))
    assert len({result["id"] for result in results}) == 1
    assert await Design.filter(page_id=page["id"]).count() == 1
    assert len(list(settings.storage_dir.iterdir())) == 3
    assert sorted(result["version"] for result in results) == [1, 2, 3]


async def test_upload_overwrite_database_failure_preserves_original(client, monkeypatch):
    _, page = await hierarchy(client)
    design = await upload(client, page)
    paths = set(settings.storage_dir.iterdir())

    async def fail_save(*args, **kwargs):
        raise RuntimeError("simulated database write failure")

    monkeypatch.setattr(Design, "save", fail_save)
    with pytest.raises(RuntimeError, match="simulated database write failure"):
        await client.post(
            f"/api/pages/{page['id']}/designs",
            data={"name": "新名称", "overwrite": "true"},
            files={"file": ("fake.jpg", png())},
        )
    assert set(settings.storage_dir.iterdir()) == paths
    record = await Design.get(id=design["id"])
    assert record.name == design["name"]
    assert (settings.storage_dir / record.stored_name).read_bytes() == png()


async def test_delete_review_updates_status_history_stats_and_keeps_image(client):
    project, page = await hierarchy(client)
    design = await upload(client, page)
    endpoint = f"/api/designs/{design['id']}/reviews"
    ids = []
    for index, status in enumerate(["approved", "changes_requested", "approved", "approved"]):
        result = await client.post(endpoint, json={"status": status, "content": f"意见 {index}"})
        ids.append(result.json()["data"]["id"])
    # Removing an older review must leave the latest decision intact.
    deleted = await client.delete(f"{endpoint}/{ids[0]}")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["status"] == "approved"
    assert (await client.delete(f"{endpoint}/{ids[3]}")).json()["data"]["status"] == "approved"
    assert (await client.delete(f"{endpoint}/{ids[2]}")).json()["data"][
        "status"
    ] == "changes_requested"
    stats = (await client.get(f"/api/projects/{project['id']}")).json()["data"]
    assert (stats["approved_count"], stats["changes_requested_count"]) == (0, 1)
    result = await client.delete(f"{endpoint}/{ids[1]}")
    assert result.json()["data"]["status"] == "pending"
    assert (await client.get(endpoint)).json()["data"]["reviews"] == []
    assert (await client.get(design["image_url"])).content == png()
    assert (await client.delete(f"{endpoint}/{ids[1]}")).status_code == 404


async def test_delete_review_rejects_cross_design_and_cross_account(client):
    _, page = await hierarchy(client)
    design = await upload(client, page)
    second = await upload(client, page)
    endpoint = f"/api/designs/{design['id']}/reviews"
    review = (
        await client.post(endpoint, json={"content": "保留意见", "status": "approved"})
    ).json()["data"]
    assert (
        await client.delete(f"/api/designs/{second['id']}/reviews/{review['id']}")
    ).status_code == 404
    await register(client)
    assert (await client.delete(f"{endpoint}/{review['id']}")).status_code == 404
    assert (await Design.get(id=design["id"])).status == "approved"
    await client.post("/api/auth/logout")
    assert (await client.delete(f"{endpoint}/{review['id']}")).status_code == 401


async def test_delete_review_preserves_image_overwrite_pending_reset(client):
    _, page = await hierarchy(client)
    design = await upload(client, page)
    endpoint = f"/api/designs/{design['id']}/reviews"
    for _ in range(2):
        review = (
            await client.post(endpoint, json={"content": "旧图通过", "status": "approved"})
        ).json()["data"]
    await client.post(
        f"/api/pages/{page['id']}/designs",
        data={"name": "新版", "overwrite": "true"},
        files={"file": ("fake.jpg", png())},
    )
    result = await client.delete(f"{endpoint}/{review['id']}")
    assert result.json()["data"]["status"] == "pending"


async def test_delete_review_concurrent_submit_and_delete(client):
    _, page = await hierarchy(client)
    design = await upload(client, page)
    endpoint = f"/api/designs/{design['id']}/reviews"
    original = (
        await client.post(endpoint, json={"status": "approved", "content": "旧意见"})
    ).json()["data"]
    responses = await asyncio.gather(
        client.delete(f"{endpoint}/{original['id']}"),
        client.delete(f"{endpoint}/{original['id']}"),
        client.post(endpoint, json={"status": "changes_requested", "content": "新意见"}),
    )
    assert sorted(response.status_code for response in responses) == [200, 201, 404]
    result = (await client.get(endpoint)).json()["data"]
    assert len(result["reviews"]) == 1
    assert result["design"]["status"] == result["reviews"][0]["status"] == "changes_requested"
