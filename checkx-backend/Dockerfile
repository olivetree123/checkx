FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
COPY mcp_server.py ./
RUN useradd --uid 10001 --create-home checkx && mkdir -p /app/data/uploads && chown -R checkx:checkx /app/data
USER checkx
ENV PATH="/app/.venv/bin:$PATH" STORAGE_DIR=/app/data/uploads
EXPOSE 8000
CMD ["sh", "-c", "tortoise migrate && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
