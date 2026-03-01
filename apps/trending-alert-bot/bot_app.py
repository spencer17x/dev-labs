"""Bot runtime bootstrap based on config files."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

COMMON_ALLOWED_KEYS = {
    "check_interval",
    "notify_cooldown_hours",
    "multiplier_confirmations",
}

BOT_ALLOWED_KEYS = {
    "chain",
    "chains",
    "notification_types",
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
    chains: List[str]
    telegram_bot_token: str
    data_dir: str
    check_interval: int = 15
    notify_cooldown_hours: int = 24
    multiplier_confirmations: int = 2
    notification_types: List[str] = None
    chain_allowlists: Optional[Dict[str, Dict[str, Any]]] = None


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

    supported_chains = {"bsc", "sol", "base"}
    raw_chains = merged.get("chains")
    if raw_chains is None:
        chain = merged.get("chain", "").strip().lower()
        if not chain:
            raise ValueError("bot config missing 'chain' or 'chains'")
        raw_chains = [chain]

    if not isinstance(raw_chains, list) or not raw_chains:
        raise ValueError("'chains' must be a non-empty list")

    chains: List[str] = []
    for item in raw_chains:
        chain = str(item).strip().lower()
        if not chain:
            continue
        if chain in chains:
            continue
        if chain not in supported_chains:
            raise ValueError(f"unsupported chain: {chain}")
        chains.append(chain)
    if not chains:
        raise ValueError("'chains' must contain at least one valid chain")

    token = merged.get("telegram_bot_token", "").strip()
    if not token:
        raise ValueError("bot config missing 'telegram_bot_token'")

    data_dir = merged.get("data_dir", "").strip()
    if not data_dir:
        raise ValueError("bot config missing 'data_dir'")
    resolved_data_dir = _resolve_data_dir(data_dir)

    allowlists = merged.get("chain_allowlists", {})
    if not isinstance(allowlists, dict):
        raise ValueError("'chain_allowlists' must be an object")

    chain_allowlists: Dict[str, Dict[str, Any]] = {}
    for chain in chains:
        chain_allow = allowlists.get(chain, {})
        if not isinstance(chain_allow, dict):
            raise ValueError(f"chain_allowlists.{chain} must be an object")
        chain_allowlists[chain] = chain_allow

    raw_notification_types = merged.get("notification_types", ["trending", "anomaly"])
    if not isinstance(raw_notification_types, list) or not raw_notification_types:
        raise ValueError("'notification_types' must be a non-empty list")
    supported_notification_types = {"trending", "anomaly"}
    notification_types: List[str] = []
    for item in raw_notification_types:
        notification_type = str(item).strip().lower()
        if not notification_type:
            continue
        if notification_type in notification_types:
            continue
        if notification_type not in supported_notification_types:
            raise ValueError(f"unsupported notification_type: {notification_type}")
        notification_types.append(notification_type)
    if not notification_types:
        raise ValueError("'notification_types' must contain at least one valid type")

    return BotRuntimeConfig(
        chain=chains[0],
        chains=chains,
        telegram_bot_token=token,
        data_dir=resolved_data_dir,
        check_interval=int(merged.get("check_interval", 15)),
        notify_cooldown_hours=int(merged.get("notify_cooldown_hours", 24)),
        multiplier_confirmations=int(merged.get("multiplier_confirmations", 2)),
        notification_types=notification_types,
        chain_allowlists=chain_allowlists,
    )


def apply_runtime_env(cfg: BotRuntimeConfig):
    os.environ["BOT_CHAIN"] = cfg.chain
    os.environ["BOT_CHAINS"] = json.dumps(cfg.chains, ensure_ascii=False)
    os.environ["BOT_TELEGRAM_TOKEN"] = cfg.telegram_bot_token
    os.environ["BOT_DATA_DIR"] = cfg.data_dir
    os.environ["BOT_CHECK_INTERVAL"] = str(cfg.check_interval)
    os.environ["BOT_NOTIFY_COOLDOWN_HOURS"] = str(cfg.notify_cooldown_hours)
    os.environ["BOT_MULTIPLIER_CONFIRMATIONS"] = str(cfg.multiplier_confirmations)
    os.environ["BOT_NOTIFICATION_TYPES"] = json.dumps(cfg.notification_types or [], ensure_ascii=False)
    os.environ["BOT_CHAIN_ALLOWLIST_JSON"] = json.dumps(cfg.chain_allowlists or {}, ensure_ascii=False)


def validate_runtime_config(cfg: BotRuntimeConfig):
    if cfg.telegram_bot_token.startswith("REPLACE_WITH_"):
        raise ValueError("invalid telegram_bot_token: placeholder value detected")
    if cfg.check_interval <= 0:
        raise ValueError("check_interval must be > 0")
    if cfg.notify_cooldown_hours < 0:
        raise ValueError("notify_cooldown_hours must be >= 0")
    if cfg.multiplier_confirmations <= 0:
        raise ValueError("multiplier_confirmations must be > 0")
    if not cfg.chains:
        raise ValueError("chains must not be empty")
    if not cfg.notification_types:
        raise ValueError("notification_types must not be empty")
    if not cfg.data_dir:
        raise ValueError("data_dir must not be empty")
    os.makedirs(cfg.data_dir, exist_ok=True)
