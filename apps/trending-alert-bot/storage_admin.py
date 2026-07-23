"""跨 Bot 数据目录的存储管理操作。"""

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Mapping, Optional

from bot_app import BOT_TARGETS

_DATABASE_FILENAME = "trending_alert_bot.sqlite"


@dataclass(frozen=True)
class NotificationDataClearResult:
    target: str
    database_path: Path
    status: str
    deleted_contracts: int = 0
    backup_path: Optional[Path] = None


def _resolve_database_path(app_root: Path, raw_data_dir: str) -> Path:
    data_dir = Path(raw_data_dir).expanduser()
    if not data_dir.is_absolute():
        data_dir = app_root / data_dir
    return data_dir.resolve() / _DATABASE_FILENAME


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _backup_database(conn: sqlite3.Connection, backup_path: Path):
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(backup_path)) as backup_conn:
        conn.backup(backup_conn)


def clear_all_notification_data(
    app_root: Optional[Path] = None,
    bot_targets: Optional[Mapping[str, Mapping[str, object]]] = None,
    now: Optional[datetime] = None,
) -> list[NotificationDataClearResult]:
    """备份并清理所有 target 数据库中的合约通知跟踪数据。"""
    resolved_app_root = (app_root or Path(__file__).resolve().parent).resolve()
    targets = BOT_TARGETS if bot_targets is None else bot_targets
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S-%f")
    backup_dir = (
        resolved_app_root
        / "data"
        / "backups"
        / f"notification-data-{timestamp}"
    )
    results = []

    for target, target_config in targets.items():
        database_path = _resolve_database_path(
            resolved_app_root,
            str(target_config["data_dir"]),
        )
        if not database_path.exists():
            results.append(
                NotificationDataClearResult(
                    target=target,
                    database_path=database_path,
                    status="missing",
                )
            )
            continue

        with closing(sqlite3.connect(database_path, timeout=5)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            if not _table_exists(conn, "contracts"):
                results.append(
                    NotificationDataClearResult(
                        target=target,
                        database_path=database_path,
                        status="missing_schema",
                    )
                )
                continue

            contract_count = conn.execute(
                "SELECT COUNT(*) FROM contracts"
            ).fetchone()[0]
            if contract_count == 0:
                results.append(
                    NotificationDataClearResult(
                        target=target,
                        database_path=database_path,
                        status="empty",
                    )
                )
                continue

            backup_path = backup_dir / f"{target}.sqlite"
            _backup_database(conn, backup_path)
            with conn:
                conn.execute("DELETE FROM contracts")

        results.append(
            NotificationDataClearResult(
                target=target,
                database_path=database_path,
                status="cleared",
                deleted_contracts=contract_count,
                backup_path=backup_path,
            )
        )

    return results
