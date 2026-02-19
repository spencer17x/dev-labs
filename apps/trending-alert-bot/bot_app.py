"""Bot runtime bootstrap based on config files."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

COMMON_ALLOWED_KEYS = {
    "check_interval",
    "notify_cooldown_hours",
    "multiplier_confirmations",
}

BOT_ALLOWED_KEYS = {
    "chain",
    "telegram_bot_token",
    "data_dir",
    "check_interval",
    "notify_cooldown_hours",
    "multiplier_confirmations",
    "chain_allowlists",
}


@dataclass
class BotRuntimeConfig:
    chain: str
    telegram_bot_token: str
    data_dir: str
    check_interval: int = 15
    notify_cooldown_hours: int = 24
    multiplier_confirmations: int = 2
    chain_allowlist: Optional[Dict[str, Any]] = None


def _app_root() -> Path:
    return Path(__file__).resolve().parent


def _resolve_data_dir(raw_data_dir: str) -> str:
    path = Path(raw_data_dir).expanduser()
    if path.is_absolute():
        return str(path)
    # Relative path is resolved from startup directory (cwd).
    return str((Path.cwd() / path).resolve())


def _load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _validate_keys(raw: Dict[str, Any], allowed: set, source: str):
    unknown = sorted([k for k in raw.keys() if k not in allowed])
    if unknown:
        raise ValueError(f"{source} has unsupported keys: {', '.join(unknown)}")


def load_runtime_config(bot_config_path: str, common_config_path: Optional[str] = None) -> BotRuntimeConfig:
    common: Dict[str, Any] = {}
    if common_config_path and os.path.exists(common_config_path):
        common = _load_json_file(common_config_path)
        _validate_keys(common, COMMON_ALLOWED_KEYS, "common config")

    bot = _load_json_file(bot_config_path)
    _validate_keys(bot, BOT_ALLOWED_KEYS, "bot config")
    merged = {**common, **bot}

    chain = merged.get("chain", "").strip().lower()
    if not chain:
        raise ValueError("bot config missing 'chain'")
    if chain not in {"bsc", "sol", "base"}:
        raise ValueError(f"unsupported chain: {chain}")

    token = merged.get("telegram_bot_token", "").strip()
    if not token:
        raise ValueError("bot config missing 'telegram_bot_token'")

    data_dir = merged.get("data_dir", "").strip()
    if not data_dir:
        raise ValueError("bot config missing 'data_dir'")
    resolved_data_dir = _resolve_data_dir(data_dir)

    allowlists = merged.get("chain_allowlists", {})
    chain_allowlist = allowlists.get(chain, {})

    return BotRuntimeConfig(
        chain=chain,
        telegram_bot_token=token,
        data_dir=resolved_data_dir,
        check_interval=int(merged.get("check_interval", 15)),
        notify_cooldown_hours=int(merged.get("notify_cooldown_hours", 24)),
        multiplier_confirmations=int(merged.get("multiplier_confirmations", 2)),
        chain_allowlist=chain_allowlist,
    )


def apply_runtime_env(cfg: BotRuntimeConfig):
    os.environ["BOT_CHAIN"] = cfg.chain
    os.environ["BOT_TELEGRAM_TOKEN"] = cfg.telegram_bot_token
    os.environ["BOT_DATA_DIR"] = cfg.data_dir
    os.environ["BOT_CHECK_INTERVAL"] = str(cfg.check_interval)
    os.environ["BOT_NOTIFY_COOLDOWN_HOURS"] = str(cfg.notify_cooldown_hours)
    os.environ["BOT_MULTIPLIER_CONFIRMATIONS"] = str(cfg.multiplier_confirmations)
    os.environ["BOT_CHAIN_ALLOWLIST_JSON"] = json.dumps(cfg.chain_allowlist or {}, ensure_ascii=False)


def validate_runtime_config(cfg: BotRuntimeConfig):
    if cfg.telegram_bot_token.startswith("REPLACE_WITH_"):
        raise ValueError("invalid telegram_bot_token: placeholder value detected")
    if cfg.check_interval <= 0:
        raise ValueError("check_interval must be > 0")
    if cfg.notify_cooldown_hours < 0:
        raise ValueError("notify_cooldown_hours must be >= 0")
    if cfg.multiplier_confirmations <= 0:
        raise ValueError("multiplier_confirmations must be > 0")
    if not cfg.data_dir:
        raise ValueError("data_dir must not be empty")
    os.makedirs(cfg.data_dir, exist_ok=True)
