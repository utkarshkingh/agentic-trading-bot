"""User-adjustable model configuration set from the app at runtime.

Lets the user paste any vendor's API key and a LiteLLM model string in the UI
instead of editing .env. The value is persisted to a small JSON file so it
survives restarts, and seeded from environment settings for existing setups.
"""
import json
import logging
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from src.settings import settings

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path.home() / ".agentic-trading-bot" / "config.json"
_lock = threading.Lock()


@dataclass
class ModelConfig:
    """The active LLM selection. `api_base` is optional (Ollama, gateways)."""
    model: str
    api_key: str = ""
    api_base: str = ""


def _defaults() -> ModelConfig:
    # Seed from .env so existing configurations keep working with no UI changes.
    key = (
        settings.openrouter_api_key
        or settings.openai_api_key
        or settings.anthropic_api_key
        or ""
    )
    return ModelConfig(model=settings.trading_model, api_key=key)


_current: ModelConfig | None = None


def _load() -> ModelConfig:
    base = _defaults()
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            return replace(base, **{k: v for k, v in data.items() if k in asdict(base)})
        except Exception as e:
            logger.warning("Could not read model config (%s); using defaults", e)
    return base


def get_model_config() -> ModelConfig:
    global _current
    with _lock:
        if _current is None:
            _current = _load()
        return _current


def set_model_config(
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> ModelConfig:
    """Update and persist the config. Omitted/blank fields are left unchanged."""
    global _current
    with _lock:
        cfg = _current or _load()
        cfg = replace(
            cfg,
            model=model.strip() if model and model.strip() else cfg.model,
            api_key=api_key.strip() if api_key and api_key.strip() else cfg.api_key,
            # api_base may be intentionally cleared, so accept an empty string.
            api_base=api_base.strip() if api_base is not None else cfg.api_base,
        )
        _current = cfg
        try:
            _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            _CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Could not persist model config: %s", e)
        return cfg
