"""Entry point for the packaged sidecar binary.

PyInstaller freezes this into a single executable that Tauri ships and
launches on desktop. It runs the FastAPI app with a plain uvicorn server
(no reload/import-string, which don't work inside a frozen binary).
"""
import os

import uvicorn

from src.main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
