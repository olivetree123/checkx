from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from tortoise.exceptions import IntegrityError
from tortoise.functions import Count
from tortoise.transactions import in_transaction

from app import schemas as s
from app.config import settings
from app.models import Credential, Design, Page, Project, Review, User
from app.security import (
    COOKIE,
    current_user,
    issue_credential,
    password_hash,
    rate_limit,
    set_session,
)
from app.services import (
    add_review,
    design_out,
    owned_design,
    owned_page,
    owned_project,
    remove_design,
    remove_review,
    upload_design,
)

router = APIRouter(
    prefix="/api",
    responses={
        status: {"model": s.Envelope[object], "description": description}
        for status, description in {
            400: "无效请求",
            401: "未认证或凭据过期",
            403: "禁止访问",
            404: "资源不存在",
            409: "资源冲突",
            413: "上传超限",
            422: "参数或图片校验失败",
            429: "请求过于频繁",
            500: "服务器错误",
        }.items()
    },
)
Auth = Annotated[User, Depends(current_user)]


@router.post("/auth/register", response_model=s.Envelope[s.UserOut], status_code=201, tags=["认证"])
async def register(payload: s.RegisterInput, request: Request, response: Response):
    rate_limit(request)
    hashed = await run_in_threadpool(password_hash.hash, payload.password)
    try:
        user = await User.create(
            email=str(payload.email), display_name=payload.display_name, password_hash=hashed
        )
    except IntegrityError as exc:
        raise HTTPException(409, "该邮箱已注册") from exc
    _, token = await issue_credential(user, "session", "Browser", settings.session_days)
    set_session(response, token)
    return s.Envelope(data=s.UserOut.model_validate(user))


@router.post("/auth/login", response_model=s.Envelope[s.UserOut], tags=["认证"])
async def login(payload: s.LoginInput, request: Request, response: Response):
    rate_limit(request)
    user = await User.get_or_none(email=str(payload.email))
    if user is None:
        await run_in_threadpool(password_hash.hash, payload.password)
        raise HTTPException(401, "邮箱或密码错误")
    if not await run_in_threadpool(password_hash.verify, payload.password, user.password_hash):
        raise HTTPException(401, "邮箱或密码错误")
    _, token = await issue_credential(user, "session", "Browser", settings.session_days)
    set_session(response, token)
    return s.Envelope(data=s.UserOut.model_validate(user))


@router.get("/auth/me", response_model=s.Envelope[s.UserOut], tags=["认证"])
async def me(user: Auth):
    return s.Envelope(data=s.UserOut.model_validate(user))


@router.put("/auth/me", response_model=s.Envelope[s.UserOut], tags=["账号设置"])
async def update_account(payload: s.AccountInput, request: Request, user: Auth):
    if request.state.credential.kind != "session":
        raise HTTPException(403, "请在浏览器中登录后修改账号信息")
    rate_limit(request)
    try:
        async with in_transaction() as connection:
            locked = await User.filter(id=user.id).using_db(connection).select_for_update().get()
            if str(payload.email) != locked.email:
                if not payload.current_password or not await run_in_threadpool(
                    password_hash.verify, payload.current_password, locked.password_hash
                ):
                    raise HTTPException(400, "修改邮箱需要正确的当前密码")
            locked.email = str(payload.email)
            locked.display_name = payload.display_name
            await locked.save(using_db=connection, update_fields=["email", "display_name"])
    except IntegrityError as exc:
        raise HTTPException(409, "该邮箱已被其他账号使用") from exc
    return s.Envelope(data=s.UserOut.model_validate(locked))


@router.put("/auth/password", response_model=s.Envelope[None], tags=["账号设置"])
async def update_password(payload: s.PasswordInput, request: Request, user: Auth):
    if request.state.credential.kind != "session":
        raise HTTPException(403, "请在浏览器中登录后修改密码")
    rate_limit(request)
    async with in_transaction() as connection:
        locked = await User.filter(id=user.id).using_db(connection).select_for_update().get()
        if not await run_in_threadpool(
            password_hash.verify, payload.current_password, locked.password_hash
        ):
            raise HTTPException(400, "当前密码不正确")
        locked.password_hash = await run_in_threadpool(password_hash.hash, payload.new_password)
        await locked.save(using_db=connection, update_fields=["password_hash"])
        await (
            Credential.filter(user=user, kind="session")
            .exclude(id=request.state.credential.id)
            .using_db(connection)
            .delete()
        )
    return s.Envelope(message="密码已更新，其他浏览器会话已退出")


@router.post("/auth/logout", response_model=s.Envelope[None], tags=["认证"])
async def logout(request: Request, response: Response, user: Auth):
    await request.state.credential.delete()
    response.delete_cookie(
        COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax"
    )
    return s.Envelope(message="已退出登录")


@router.get("/tokens", response_model=s.Envelope[list[s.TokenOut]], tags=["MCP 令牌"])
async def tokens(user: Auth):
    rows = await Credential.filter(
        user=user, kind="api", expires_at__gt=datetime.now(UTC)
    ).order_by("-created_at")
    return s.Envelope(data=[s.TokenOut.model_validate(row) for row in rows])


@router.post(
    "/tokens", response_model=s.Envelope[s.TokenCreated], status_code=201, tags=["MCP 令牌"]
)
async def create_token(payload: s.TokenInput, request: Request, user: Auth):
    if request.state.credential.kind != "session":
        raise HTTPException(403, "请在浏览器中登录后创建令牌")
    credential, token = await issue_credential(user, "api", payload.name, payload.expires_days)
    return s.Envelope(
        data=s.TokenCreated(**s.TokenOut.model_validate(credential).model_dump(), token=token)
    )


@router.delete("/tokens/{token_id}", response_model=s.Envelope[None], tags=["MCP 令牌"])
async def revoke_token(token_id: UUID, user: Auth):
    if not await Credential.filter(id=token_id, user=user, kind="api").delete():
        raise HTTPException(404, "令牌不存在")
    return s.Envelope(message="令牌已撤销")


async def project_out(project: Project):
    designs = Design.filter(page__project=project)
    counts = await designs.group_by("status").annotate(total=Count("id")).values("status", "total")
    statuses = {row["status"]: row["total"] for row in counts}
    cover = await designs.order_by("-created_at").first()
    return s.ProjectOut.model_validate(project).model_copy(
        update={
            "page_count": await Page.filter(project=project).count(),
            "design_count": sum(statuses.values()),
            "pending_count": statuses.get("pending", 0),
            "approved_count": statuses.get("approved", 0),
            "changes_requested_count": statuses.get("changes_requested", 0),
            "cover_url": f"/api/designs/{cover.id}/image" if cover else None,
        }
    )


@router.get("/projects", response_model=s.Envelope[list[s.ProjectOut]], tags=["项目"])
async def projects(user: Auth, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    rows = (
        await Project.filter(owner=user).order_by("-created_at", "id").offset(offset).limit(limit)
    )
    return s.Envelope(data=[await project_out(row) for row in rows])


@router.post("/projects", response_model=s.Envelope[s.ProjectOut], status_code=201, tags=["项目"])
async def create_project(payload: s.ProjectInput, user: Auth):
    return s.Envelope(
        data=await project_out(await Project.create(owner=user, **payload.model_dump()))
    )


@router.get("/projects/{project_id}", response_model=s.Envelope[s.ProjectOut], tags=["项目"])
async def get_project(project_id: UUID, user: Auth):
    return s.Envelope(data=await project_out(await owned_project(project_id, user)))


@router.put("/projects/{project_id}", response_model=s.Envelope[s.ProjectOut], tags=["项目"])
async def update_project(project_id: UUID, payload: s.ProjectInput, user: Auth):
    project = await owned_project(project_id, user)
    project.update_from_dict(payload.model_dump())
    await project.save()
    return s.Envelope(data=await project_out(project))


@router.get(
    "/projects/{project_id}/pages", response_model=s.Envelope[list[s.PageOut]], tags=["页面"]
)
async def pages(
    project_id: UUID,
    user: Auth,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    await owned_project(project_id, user)
    rows = (
        await Page.filter(project_id=project_id)
        .annotate(design_count=Count("designs"))
        .order_by("created_at", "id")
        .offset(offset)
        .limit(limit)
    )
    return s.Envelope(data=[s.PageOut.model_validate(row) for row in rows])


@router.post(
    "/projects/{project_id}/pages",
    response_model=s.Envelope[s.PageOut],
    status_code=201,
    tags=["页面"],
)
async def create_page(project_id: UUID, payload: s.ProjectInput, user: Auth):
    project = await owned_project(project_id, user)
    page = await Page.create(project=project, **payload.model_dump())
    return s.Envelope(data=s.PageOut.model_validate(page))


@router.put("/pages/{page_id}", response_model=s.Envelope[s.PageOut], tags=["页面"])
async def update_page(page_id: UUID, payload: s.ProjectInput, user: Auth):
    page = await owned_page(page_id, user)
    page.update_from_dict(payload.model_dump())
    await page.save()
    return s.Envelope(
        data=s.PageOut.model_validate(page).model_copy(
            update={"design_count": await Design.filter(page=page).count()}
        )
    )


@router.get(
    "/pages/{page_id}/designs", response_model=s.Envelope[list[s.DesignOut]], tags=["设计图"]
)
async def designs(
    page_id: UUID,
    user: Auth,
    status: s.Status | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    await owned_page(page_id, user)
    query = Design.filter(page_id=page_id)
    if status:
        query = query.filter(status=status)
    rows = await query.order_by("-created_at", "id").offset(offset).limit(limit)
    return s.Envelope(data=[design_out(row) for row in rows])


@router.post(
    "/pages/{page_id}/designs",
    response_model=s.Envelope[s.DesignOut],
    status_code=201,
    tags=["设计图"],
)
async def upload(
    page_id: UUID,
    user: Auth,
    file: UploadFile = File(...),
    name: str = Form(..., min_length=1, max_length=180),
    notes: str = Form("", max_length=10000),
    overwrite: bool = Form(False, description="按同一页面的原始文件名覆盖；重复匹配返回 409"),
):
    page = await owned_page(page_id, user)
    try:
        payload = s.DesignInput(name=name, notes=notes)
    except ValidationError as exc:
        raise HTTPException(422, "图片名称不能为空，名称或备注过长") from exc
    try:
        design = await upload_design(page, file, payload, overwrite=overwrite)
    finally:
        await file.close()
    return s.Envelope(data=design_out(design))


@router.get("/designs/{design_id}", response_model=s.Envelope[s.DesignOut], tags=["设计图"])
async def get_design(design_id: UUID, user: Auth):
    return s.Envelope(data=design_out(await owned_design(design_id, user)))


@router.put("/designs/{design_id}/image", response_model=s.Envelope[s.DesignOut], tags=["设计图"])
async def update_design_image(
    design_id: UUID,
    user: Auth,
    request: Request,
    file: UploadFile = File(...),
    name: str | None = Form(None, description="省略则保留展示名称"),
    notes: str | None = Form(None, description="省略则保留备注，空字符串清空"),
    expected_version: int | None = Form(None, ge=1, description="可选的当前版本；不匹配返回 409"),
):
    """按 ID 更新图片，版本号加一，保留旧文件并重置为待审阅。"""
    design = await owned_design(design_id, user)
    page = await owned_page(design.page_id, user)
    try:
        # Preserve explicitly empty multipart fields (FastAPI treats them as missing).
        form = await request.form()
        payload = s.ImageUpdateInput.model_validate(
            {key: form[key] for key in ("name", "notes", "expected_version") if key in form}
        )
        updated = await upload_design(page, file, payload, design_id=design.id)
    except ValidationError as exc:
        raise HTTPException(422, "图片名称不能为空，名称、备注或版本参数无效") from exc
    finally:
        await file.close()
    return s.Envelope(data=design_out(updated), message="图片已更新，版本号已递增")


@router.put("/designs/{design_id}", response_model=s.Envelope[s.DesignOut], tags=["设计图"])
async def update_design(design_id: UUID, payload: s.DesignInput, user: Auth):
    design = await owned_design(design_id, user)
    design.update_from_dict(payload.model_dump())
    await design.save(update_fields=["name", "notes", "updated_at"])
    return s.Envelope(data=design_out(design))


@router.delete("/designs/{design_id}", response_model=s.Envelope[None], tags=["设计图"])
async def delete_design(design_id: UUID, user: Auth):
    await remove_design(await owned_design(design_id, user))
    return s.Envelope(message="设计图及审阅记录已删除")


@router.get("/designs/{design_id}/image", tags=["设计图"], response_class=FileResponse)
async def image(design_id: UUID, user: Auth):
    design = await owned_design(design_id, user)
    path = settings.storage_dir.resolve() / design.stored_name
    if not path.is_file():
        raise HTTPException(404, "图片文件不存在")
    return FileResponse(
        path,
        media_type=design.mime_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get(
    "/designs/{design_id}/reviews", response_model=s.Envelope[s.ReviewResults], tags=["审阅"]
)
async def reviews(
    design_id: UUID,
    user: Auth,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    version: int | None = Query(None, ge=1),
):
    design = await owned_design(design_id, user)
    query = Review.filter(design=design)
    if version is not None:
        query = query.filter(version=version)
    rows = await query.order_by("-created_at", "id").offset(offset).limit(limit)
    return s.Envelope(
        data=s.ReviewResults(
            design=design_out(design), reviews=[s.ReviewOut.model_validate(row) for row in rows]
        )
    )


@router.post(
    "/designs/{design_id}/reviews",
    response_model=s.Envelope[s.ReviewOut],
    status_code=201,
    tags=["审阅"],
)
async def create_review(design_id: UUID, payload: s.ReviewInput, user: Auth):
    design = await owned_design(design_id, user)
    return s.Envelope(data=s.ReviewOut.model_validate(await add_review(design, user, payload)))


@router.delete(
    "/designs/{design_id}/reviews/{review_id}",
    response_model=s.Envelope[s.DesignOut],
    tags=["审阅"],
)
async def delete_review(design_id: UUID, review_id: UUID, user: Auth):
    design = await owned_design(design_id, user)
    updated = await remove_review(design, review_id)
    return s.Envelope(data=design_out(updated), message="审阅记录已删除")
