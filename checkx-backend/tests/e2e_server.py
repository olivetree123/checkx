"""Isolated backend for Playwright; temporary files, no developer database writes."""

import os
from tempfile import TemporaryDirectory

import uvicorn

if __name__ == "__main__":
    with TemporaryDirectory(prefix="checkx-e2e-") as directory:
        os.environ["DATABASE_URL"] = f"sqlite://{directory}/test.sqlite3"
        os.environ["STORAGE_DIR"] = f"{directory}/uploads"
        os.environ["AUTO_CREATE_SCHEMA"] = "true"
        os.environ["CORS_ORIGINS"] = '["http://127.0.0.1:5174"]'
        uvicorn.run("app.main:app", host="127.0.0.1", port=8001)
