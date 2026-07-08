"""Bot runtime bootstrap based on fixed targets and local environment."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


CHECK_INTERVAL = 15
NOTIFY_COOLDOWN_HOURS = 24
MULTIPLIER_CONFIRMATIONS = 2
NOTIFICATION_TYPES = ["trending", "anomaly"]
NARRATIVE_ENABLED = False
NARRATIVE_PROVIDER = "xai"
NARRATIVE_CACHE_TTL_HOURS = 12
NARRATIVE_MIN_EVIDENCE = 3
NARRATIVE_TIMEOUT_SECONDS = 20

BOT_TARGETS = {
    "bsc": {"chains": ["bsc"], "data_dir": "data/bsc-bot"},
    "sol": {"chains": ["sol"], "data_dir": "data/sol-bot"},
    "base": {"chains": ["base"], "data_dir": "data/base-bot"},
    "eth": {"chains": ["eth"], "data_dir": "data/eth-bot"},
    "multi": {"chains": ["bsc", "sol", "base", "eth"], "data_dir": "data/multi-bot"},
}


@dataclass
class BotRuntimeConfig:
    chain: str
    chains: List[str]
    telegram_bot_token: str
    data_dir: str
    check_interval: int = CHECK_INTERVAL
    notify_cooldown_hours: int = NOTIFY_COOLDOWN_HOURS
    multiplier_confirmations: int = MULTIPLIER_CONFIRMATIONS
    notification_types: List[str] = None
    chain_allowlists: Dict[str, Dict[str, Any]] = None
    narrative_enabled: bool = NARRATIVE_ENABLED
    narrative_provider: str = NARRATIVE_PROVIDER
    narrative_cache_ttl_hours: int = NARRATIVE_CACHE_TTL_HOURS
    narrative_min_evidence: int = NARRATIVE_MIN_EVIDENCE
    narrative_timeout_seconds: int = NARRATIVE_TIMEOUT_SECONDS
    xai_api_key: str = ""


def _app_root() -> Path:
    return Path(__file__).resolve().parent


def _resolve_data_dir(raw_data_dir: str) -> str:
    path = Path(raw_data_dir).expanduser()
    if path.is_absolute():
        return str(path)
    return str((_app_root() / path).resolve())


def _token_env_name(target: str) -> str:
    return f"{target.upper()}_TELEGRAM_BOT_TOKEN"


def _strip_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _as_bool(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def load_dotenv(path: Path = None):
    dotenv_path = path or (_app_root() / ".env")
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_env_value(raw_value)


def load_runtime_config(target: str) -> BotRuntimeConfig:
    normalized_target = str(target or "").strip().lower()
    if normalized_target not in BOT_TARGETS:
        supported = ", ".join(sorted(BOT_TARGETS))
        raise ValueError(f"unsupported target: {target}; supported targets: {supported}")

    load_dotenv()
    token_env = _token_env_name(normalized_target)
    token = os.getenv(token_env, "").strip()
    if not token:
        raise ValueError(f"missing required env: {token_env}")

    target_cfg = BOT_TARGETS[normalized_target]
    chains = list(target_cfg["chains"])
    chain_allowlists = {chain: {} for chain in chains}

    return BotRuntimeConfig(
        chain=chains[0],
        chains=chains,
        telegram_bot_token=token,
        data_dir=_resolve_data_dir(target_cfg["data_dir"]),
        check_interval=CHECK_INTERVAL,
        notify_cooldown_hours=NOTIFY_COOLDOWN_HOURS,
        multiplier_confirmations=MULTIPLIER_CONFIRMATIONS,
        notification_types=list(NOTIFICATION_TYPES),
        chain_allowlists=chain_allowlists,
        narrative_enabled=_as_bool(os.getenv("NARRATIVE_ENABLED", "1" if NARRATIVE_ENABLED else "0")),
        narrative_provider=os.getenv("NARRATIVE_PROVIDER", NARRATIVE_PROVIDER).strip().lower() or NARRATIVE_PROVIDER,
        narrative_cache_ttl_hours=_env_int("NARRATIVE_CACHE_TTL_HOURS", NARRATIVE_CACHE_TTL_HOURS),
        narrative_min_evidence=_env_int("NARRATIVE_MIN_EVIDENCE", NARRATIVE_MIN_EVIDENCE),
        narrative_timeout_seconds=_env_int("NARRATIVE_TIMEOUT_SECONDS", NARRATIVE_TIMEOUT_SECONDS),
        xai_api_key=os.getenv("XAI_API_KEY", "").strip(),
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
    os.environ["NARRATIVE_ENABLED"] = "1" if cfg.narrative_enabled else "0"
    os.environ["NARRATIVE_PROVIDER"] = cfg.narrative_provider
    os.environ["NARRATIVE_CACHE_TTL_HOURS"] = str(cfg.narrative_cache_ttl_hours)
    os.environ["NARRATIVE_MIN_EVIDENCE"] = str(cfg.narrative_min_evidence)
    os.environ["NARRATIVE_TIMEOUT_SECONDS"] = str(cfg.narrative_timeout_seconds)
    if cfg.xai_api_key:
        os.environ["XAI_API_KEY"] = cfg.xai_api_key


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
    if cfg.narrative_provider not in {"mock", "xai"}:
        raise ValueError("narrative_provider must be one of: mock, xai")
    if cfg.narrative_cache_ttl_hours <= 0:
        raise ValueError("narrative_cache_ttl_hours must be > 0")
    if cfg.narrative_min_evidence < 0:
        raise ValueError("narrative_min_evidence must be >= 0")
    if cfg.narrative_timeout_seconds <= 0:
        raise ValueError("narrative_timeout_seconds must be > 0")
    os.makedirs(cfg.data_dir, exist_ok=True)
