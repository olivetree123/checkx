import asyncio
from io import BytesIO

import pytest
from PIL import Image
from tortoise import connections

from app.config import settings
from app.models import Design, DesignImageVersion, Review
from tests.conftest import hierarchy, png, register, upload


def replacement():
    output = BytesIO()
    Image.new("RGB", (64, 48), "red").save(output, "PNG")
    return output.getvalue()


async def replace(client, design, data=None, content=None):
    return await client.put(
        f"/api/designs/{design['id']}/image",
        data=data or {},
        files={"file": ("renamed.png", content if content is not None else replacement())},
    )


async def test_update_by_id_archives_images_metadata_and_deletes_all_versions(client):
    _, page = await hierarchy(client)
    original = await upload(client, page)
    # Duplicate filenames do not make an explicit ID ambiguous.
    other = await upload(client, page)
    assert original["version"] == 1
    result = await replace(client, original, {"expected_version": 1})
    assert result.status_code == 200, result.text
    current = result.json()["data"]
    assert current["id"] == original["id"] and current["version"] == 2
    assert current["name"] == original["name"] and current["notes"] == original["notes"]
    assert current["original_name"] == "renamed.png"
    assert (current["width"], current["height"]) == (64, 48)
    assert current["created_at"] == original["created_at"]
    assert current["image_url"] != original["image_url"]
    assert (await client.get(current["image_url"])).content == replacement()
    archived = await DesignImageVersion.get(design_id=original["id"], version=1)
    assert archived.name == original["name"] and archived.notes == original["notes"]
    assert (settings.storage_dir / archived.stored_name).read_bytes() == png()
    assert (await client.get(other["image_url"])).content == png()

    result = await replace(client, original, {"name": "新标题", "notes": ""})
    current = result.json()["data"]
    assert current["version"] == 3 and current["name"] == "新标题" and current["notes"] == ""
    rows = (await client.get(f"/api/pages/{page['id']}/designs")).json()["data"]
    assert len(rows) == 2 and next(d for d in rows if d["id"] == original["id"])["version"] == 3
    assert await DesignImageVersion.filter(design_id=original["id"]).count() == 2
    assert len(list(settings.storage_dir.iterdir())) == 4
    await client.delete(f"/api/designs/{original['id']}")
    assert await DesignImageVersion.filter(design_id=original["id"]).count() == 0
    assert len(list(settings.storage_dir.iterdir())) == 1
    assert (await client.get(other["image_url"])).content == png()


async def test_review_version_binding_and_status_never_falls_back_to_old_version(client):
    _, page = await hierarchy(client)
    design = await upload(client, page)
    endpoint = f"/api/designs/{design['id']}/reviews"
    old = (await client.post(endpoint, json={"content": "旧图通过", "status": "approved"})).json()[
        "data"
    ]
    assert old["version"] == 1
    updated = await replace(client, design)
    assert updated.json()["data"]["status"] == "pending"
    rejected = await client.post(
        endpoint,
        json={
            "content": "尚未刷新的旧页面",
            "status": "approved",
            "expected_version": 1,
        },
    )
    assert rejected.status_code == 409
    assert await Review.filter(design_id=design["id"]).count() == 1
    new = (
        await client.post(
            endpoint,
            json={
                "content": "修改新版",
                "status": "changes_requested",
                "expected_version": 2,
            },
        )
    ).json()["data"]
    assert new["version"] == 2
    latest = (await client.get(endpoint, params={"version": 2})).json()["data"]
    assert latest["reviews"] == [new]
    historical = (await client.get(endpoint, params={"version": 1})).json()["data"]
    assert historical["reviews"] == [old] and historical["design"]["version"] == 2
    deleted = await client.delete(f"{endpoint}/{new['id']}")
    assert deleted.json()["data"]["status"] == "pending"
    approved = (
        await client.post(endpoint, json={"content": "新版通过", "status": "approved"})
    ).json()["data"]
    assert approved["version"] == 2
    assert (await client.delete(f"{endpoint}/{old['id']}")).json()["data"]["status"] == "approved"


async def test_replacement_validation_and_ownership_do_not_change_version_or_files(client):
    _, page = await hierarchy(client)
    design = await upload(client, page)
    files = set(settings.storage_dir.iterdir())
    assert (await replace(client, design, content=b"bad image")).status_code == 422
    for data, status in [
        ({"name": " "}, 422),
        ({"name": ""}, 422),
        ({"expected_version": 0}, 422),
        ({"expected_version": 2}, 409),
    ]:
        assert (await replace(client, design, data)).status_code == status
    await register(client)
    assert (await replace(client, design)).status_code == 404
    await client.post("/api/auth/logout")
    assert (await replace(client, design)).status_code == 401
    assert set(settings.storage_dir.iterdir()) == files
    assert (await Design.get(id=design["id"])).version == 1
    assert await DesignImageVersion.all().count() == 0


async def test_replacement_database_failure_rolls_back_archive_and_file(client, monkeypatch):
    _, page = await hierarchy(client)
    design = await upload(client, page)
    files = set(settings.storage_dir.iterdir())

    async def fail(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(Design, "save", fail)
    with pytest.raises(RuntimeError, match="simulated failure"):
        await replace(client, design)
    assert set(settings.storage_dir.iterdir()) == files
    assert (await Design.get(id=design["id"])).version == 1
    assert await DesignImageVersion.all().count() == 0


async def test_concurrent_replacements_increment_once_per_success_postgres(client):
    if connections.get("default").capabilities.dialect != "postgres":
        pytest.skip("Requires PostgreSQL row locks")
    _, page = await hierarchy(client)
    design = await upload(client, page)
    responses = await asyncio.gather(*(replace(client, design) for _ in range(3)))
    assert all(r.status_code == 200 for r in responses)
    assert sorted(r.json()["data"]["version"] for r in responses) == [2, 3, 4]
    responses = await asyncio.gather(
        *(replace(client, design, {"expected_version": 4}) for _ in range(2))
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert (await Design.get(id=design["id"])).version == 5
    assert sorted(
        await DesignImageVersion.filter(design_id=design["id"]).values_list("version", flat=True)
    ) == [1, 2, 3, 4]
    assert len(list(settings.storage_dir.iterdir())) == 5
