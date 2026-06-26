from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — accepts any LiteLLM-compatible string:
    #   "openrouter/qwen/qwen3-235b-a22b-thinking-2507"
    #   "openai/gpt-4.1"
    #   "anthropic/claude-sonnet-4-6"
    #   "ollama/qwen3:32b"
    trading_model: str = "openrouter/qwen/qwen3-coder"

    # API keys (only the ones needed for the chosen model)
    openrouter_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Zerodha MCP
    zerodha_mcp_url: str = "https://mcp.kite.trade/mcp"

    # Risk
    risk_free_rate: float = 0.065  # India 10yr Gsec annualized

    # Server
    port: int = 8000


settings = Settings()
