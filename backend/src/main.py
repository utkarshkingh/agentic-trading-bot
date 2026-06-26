"""FastAPI application — exposes the LangGraph trading agent via AG-UI protocol."""
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint

from src.graph.trading_graph import trading_graph
from src.mcp.zerodha_client import zerodha_client
from src.runtime_config import get_model_config, set_model_config
from src.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting agentic-trading-bot backend (model=%s)", settings.trading_model)
    # Attempt a non-blocking MCP connection — OK if it fails (user may not have Zerodha configured)
    connected = await zerodha_client.connect()
    if connected:
        logger.info("Zerodha MCP connected: %s", settings.zerodha_mcp_url)
    else:
        logger.warning(
            "Zerodha MCP not available (%s). Portfolio tools will return auth-required responses.",
            settings.zerodha_mcp_url,
        )
    yield
    await zerodha_client.close()
    logger.info("Backend shutdown complete")


app = FastAPI(
    title="Agentic Trading Bot",
    version="0.2.0",
    lifespan=lifespan,
)

# The UI can run as a browser dev server (localhost:3000), a desktop Tauri
# webview (tauri://localhost), or an Android webview (https://tauri.localhost),
# so allow any origin. No cookies/credentials are used — this is an auth-free
# personal app whose secrets live only in the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the AG-UI endpoint — the frontend HttpAgent points here
trading_agent = LangGraphAgent(name="trading_agent", graph=trading_graph)
add_langgraph_fastapi_endpoint(app, trading_agent, "/")


@app.get("/status")
async def status():
    zerodha_ok = await zerodha_client.health()
    cfg = get_model_config()
    return {
        "status": "ok",
        "model": cfg.model,
        "zerodha_mcp": "connected" if zerodha_ok else "disconnected",
    }


class ModelConfigUpdate(BaseModel):
    """Partial update — omitted or blank fields keep their current value."""
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None


def _config_view() -> dict:
    """Public view of the model config — never exposes the raw API key."""
    cfg = get_model_config()
    return {"model": cfg.model, "api_base": cfg.api_base, "has_api_key": bool(cfg.api_key)}


@app.get("/config")
async def read_config():
    return _config_view()


@app.post("/config")
async def write_config(update: ModelConfigUpdate):
    set_model_config(update.model, update.api_key, update.api_base)
    return _config_view()


if __name__ == "__main__":
    port = int(os.getenv("PORT", str(settings.port)))
    uvicorn.run("src.main:app", host="localhost", port=port, reload=True)
