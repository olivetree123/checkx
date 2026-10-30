import logging
import warnings
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from tortoise.transactions import in_transaction

from app.config import settings
from app.models import Design, DesignImageVersion, Page, Project, Review, User
from app.schemas import DesignInput, DesignOut, ImageUpdateInput, ReviewInput

logger = logging.getLogger(__name__)


async def owned_project(project_id: UUID, user: User) -> Project:
    project = await Project.get_or_none(id=project_id, owner=user)
    if project is None:
        raise HTTPException(404, "项目不存在")
    return project


async def owned_page(page_id: UUID, user: User) -> Page:
    page = await Page.get_or_none(id=page_id, project__owner=user)
    if page is None:
        raise HTTPException(404, "页面不存在")
    return page


async def owned_design(design_id: UUID, user: User) -> Design:
    design = await Design.get_or_none(id=design_id, page__project__owner=user)
    if design is None:
        raise HTTPException(404, "设计图不存在")
    return design


def design_out(design: Design) -> DesignOut:
    return DesignOut.model_validate(design).model_copy(
        update={"image_url": f"/api/designs/{design.id}/image?v={design.stored_name}"},
    )


def image_info(data: bytes) -> tuple[str, str, int, int]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                width, height = image.size
                if width * height > settings.max_image_pixels:
                    raise HTTPException(422, "图片像素过大")
                if image_format not in {"PNG", "JPEG", "WEBP"}:
                    raise HTTPException(422, "仅支持 PNG、JPG 和 WebP 图片")
                image.verify()
            # Force decoding too: some truncated files pass header/verify checks.
            with Image.open(BytesIO(data)) as image:
                image.load()
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise HTTPException(422, "无法读取图片，文件损坏或像素过大") from exc
    extension, mime = {
        "PNG": ("png", "image/png"),
        "JPEG": ("jpg", "image/jpeg"),
        "WEBP": ("webp", "image/webp"),
    }[image_format]
    return extension, mime, width, height


async def upload_design(
    page: Page,
    file: UploadFile,
    payload: DesignInput | ImageUpdateInput,
    *,
    overwrite: bool = False,
    design_id: UUID | None = None,
) -> Design:
    limit = settings.max_upload_mb * 1024 * 1024
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(413, f"单张图片不能超过 {settings.max_upload_mb} MB")
    ext, mime, width, height = await run_in_threadpool(image_info, bytes(data))
    stored_name = f"{uuid4().hex}.{ext}"
    destination = settings.storage_dir.resolve() / stored_name
    original_name = Path(file.filename or "image").name[:255]
    try:
        await run_in_threadpool(destination.write_bytes, data)
        values = dict(
            **payload.model_dump(exclude_none=True, exclude={"expected_version"}),
            stored_name=stored_name,
            original_name=original_name,
            mime_type=mime,
            size=len(data),
            width=width,
            height=height,
            status="pending",
        )
        async with in_transaction() as connection:
            # Lock even when no matching design exists, including ordinary uploads.
            await Page.filter(id=page.id).using_db(connection).select_for_update().get()
            matches = []
            if design_id is not None:
                matches = await (
                    Design.filter(id=design_id, page_id=page.id)
                    .using_db(connection)
                    .select_for_update()
                )
                if not matches:
                    raise HTTPException(404, "设计图不存在")
            elif overwrite:
                matches = await (
                    Design.filter(page_id=page.id, original_name=original_name)
                    .using_db(connection)
                    .select_for_update()
                    .limit(2)
                )
            if len(matches) > 1:
                raise HTTPException(409, "页面中存在多个同名文件，请先删除多余设计图后再上传")
            if matches:
                design = matches[0]
                expected = getattr(payload, "expected_version", None)
                if expected is not None and expected != design.version:
                    raise HTTPException(409, "图片版本已更新，请获取最新版本后重试")
                await DesignImageVersion.create(
                    design_id=design.id,
                    **{
                        field: getattr(design, field)
                        for field in (
                            "version",
                            "name",
                            "notes",
                            "stored_name",
                            "original_name",
                            "mime_type",
                            "size",
                            "width",
                            "height",
                        )
                    },
                    using_db=connection,
                )
                values["version"] = design.version + 1
                design.update_from_dict(values)
                await design.save(using_db=connection, update_fields=[*values, "updated_at"])
            else:
                design = await Design.create(page_id=page.id, **values, using_db=connection)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return design


async def add_review(design: Design, user: User, payload: ReviewInput) -> Review:
    # Serialise reviews per design so current status agrees with append order.
    async with in_transaction() as connection:
        locked = await Design.filter(id=design.id).using_db(connection).select_for_update().first()
        if locked is None:
            raise HTTPException(404, "设计图不存在")
        if payload.expected_version is not None and payload.expected_version != locked.version:
            raise HTTPException(409, "图片版本已更新，请查看最新图片后重新审阅")
        review = await Review.create(
            design_id=design.id,
            version=locked.version,
            content=payload.content,
            status=payload.status,
            author_label=payload.author_label or user.display_name,
            using_db=connection,
        )
        locked.status = payload.status
        await locked.save(using_db=connection, update_fields=["status", "updated_at"])
    return review


async def remove_design(design: Design):
    # Fetch the current file under lock so concurrent replacements cannot leak it.
    async with in_transaction() as connection:
        locked = await Design.filter(id=design.id).using_db(connection).select_for_update().first()
        if locked is None:
            raise HTTPException(404, "设计图不存在")
        stored_names = (
            await DesignImageVersion.filter(design_id=design.id)
            .using_db(connection)
            .values_list("stored_name", flat=True)
        )
        stored_names.append(locked.stored_name)
        await locked.delete(using_db=connection)
    for stored_name in stored_names:
        await remove_image_file(stored_name)


async def remove_review(design: Design, review_id: UUID) -> Design:
    # Share the design lock with submit/overwrite/delete to keep status consistent.
    async with in_transaction() as connection:
        locked = await Design.filter(id=design.id).using_db(connection).select_for_update().first()
        if locked is None:
            raise HTTPException(404, "设计图不存在")
        deleted = (
            await Review.filter(id=review_id, design_id=design.id).using_db(connection).delete()
        )
        if not deleted:
            raise HTTPException(404, "审阅记录不存在")
        latest = await (
            Review.filter(design_id=design.id, version=locked.version)
            .using_db(connection)
            .order_by("-created_at", "id")
            .first()
        )
        locked.status = latest.status if latest else "pending"
        await locked.save(using_db=connection, update_fields=["status", "updated_at"])
    return locked


async def remove_image_file(stored_name: str):
    # Commit DB changes first; cleanup failure must not remove the new live file.
    try:
        await run_in_threadpool(
            (settings.storage_dir.resolve() / stored_name).unlink, missing_ok=True
        )
    except OSError:
        logger.exception("Orphaned image file after database change: %s", stored_name)
