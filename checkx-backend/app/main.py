import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from tortoise import connections
from tortoise.contrib.fastapi import RegisterTortoise

from app.api import router
from app.config import TORTOISE_ORM, settings
from app.schemas import Envelope


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.storage_dir.resolve().mkdir(parents=True, exist_ok=True)
    async with RegisterTortoise(
        app, config=TORTOISE_ORM, generate_schemas=settings.auto_create_schema
    ):
        yield


app = FastAPI(title="CheckX API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


def error(status: int, message: str, data=None):
    return JSONResponse(
        status_code=status, content={"code": status, "data": data, "message": message}
    )


@app.middleware("http")
async def request_guard(request: Request, call_next):
    # Protect cookie-authenticated writes, including login CSRF. Bearer clients
    # don't carry browser ambient credentials and don't need an Origin header.
    if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
        origin = request.headers.get("origin")
        if origin and origin not in settings.cors_origins:
            return error(403, "不允许的请求来源")
        if request.headers.get("sec-fetch-site") == "cross-site" and not origin:
            return error(403, "不允许的跨站请求")
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


class BodyLimit:
    """Bound all request bodies, including chunked multipart, before parsing/spooling."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = (settings.max_upload_mb + 1) * 1024 * 1024
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await error(400, "无效的请求长度")(scope, receive, send)
        if length > limit:
            return await error(413, "请求体过大")(scope, receive, send)
        # A bounded spool lets us reject chunked bodies without exceptions being
        # swallowed by the multipart parser; memory stays below 1 MiB/request.
        from tempfile import SpooledTemporaryFile

        from starlette.concurrency import run_in_threadpool

        with SpooledTemporaryFile(max_size=1024 * 1024) as spool:
            total = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                data = message.get("body", b"")
                total += len(data)
                if total > limit:
                    return await error(413, "请求体过大")(scope, receive, send)
                await run_in_threadpool(spool.write, data)
                if not message.get("more_body", False):
                    break
            await run_in_threadpool(spool.seek, 0)
            delivered = 0

            async def replay():
                nonlocal delivered
                if delivered > total:
                    return await receive()
                chunk = await run_in_threadpool(spool.read, 1024 * 1024)
                delivered += len(chunk)
                more = delivered < total
                if not more:
                    delivered = total + 1
                return {"type": "http.request", "body": chunk, "more_body": more}

            await self.app(scope, replay, send)


app.add_middleware(BodyLimit)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return error(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    issues = [
        {"field": ".".join(map(str, item["loc"])), "message": item["msg"]} for item in exc.errors()
    ]
    return error(422, "请求参数有误", issues)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logging.getLogger(__name__).error("Unhandled server error", exc_info=exc)
    return error(500, "服务器发生错误，请稍后重试")


@app.get("/api/health", response_model=Envelope[dict[str, str]], tags=["状态"])
async def health():
    try:
        await connections.get("default").execute_query("SELECT 1")
    except Exception:
        return error(503, "数据库暂不可用")
    return Envelope(data={"status": "ok"})


app.include_router(router)
