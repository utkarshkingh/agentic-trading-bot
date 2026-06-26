"""FastAPI application — exposes the LangGraph trading agent via AG-UI protocol."""
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint

from src.graph.trading_graph import trading_graph
from src.mcp.zerodha_client import zerodha_client
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

# Allow the Next.js dev server (port 3000) and any local origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the AG-UI endpoint — the frontend HttpAgent points here
trading_agent = LangGraphAgent(name="trading_agent", graph=trading_graph)
add_langgraph_fastapi_endpoint(app, trading_agent, "/")


@app.get("/status")
async def status():
    zerodha_ok = await zerodha_client.health()
    return {
        "status": "ok",
        "model": settings.trading_model,
        "zerodha_mcp": "connected" if zerodha_ok else "disconnected",
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", str(settings.port)))
    uvicorn.run("src.main:app", host="localhost", port=port, reload=True)
