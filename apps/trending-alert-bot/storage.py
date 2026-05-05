import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from db_storage import connect, ensure_schema
from timezone_utils import beijing_now, beijing_today_start, format_beijing_time


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _json_loads(value, fallback):
    if not value:
        return fallback
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback
    return parsed if parsed is not None else fallback


class ContractStorage:
    def __init__(self, storage_file: str, chain: str = "", chat_id: Optional[int] = None):
        self.storage_file = storage_file
        self.chain = (chain or "").strip().lower()
        self.chat_id = chat_id
        self._infer_scope_from_storage_file()
        ensure_schema()
        self._migrate_legacy_json_if_empty()

    def _infer_scope_from_storage_file(self):
        if self.chain and self.chat_id is not None:
            return

        path = Path(self.storage_file)
        name = path.name
        prefix = "contracts_data_"
        suffix = ".json"
        if not name.startswith(prefix) or not name.endswith(suffix):
            self.chain = self.chain or ""
            self.chat_id = 0 if self.chat_id is None else self.chat_id
            return

        raw = name[len(prefix):-len(suffix)]
        parts = raw.rsplit("_", 1)
        if len(parts) == 2:
            inferred_chain, inferred_chat_id = parts
            self.chain = self.chain or inferred_chain
            if self.chat_id is None:
                self.chat_id = _safe_int(inferred_chat_id)
            return

        self.chain = self.chain or ""
        if self.chat_id is None:
            self.chat_id = _safe_int(raw)

    def _migrate_legacy_json_if_empty(self):
        if not os.path.exists(self.storage_file):
            return

        with connect() as conn:
            existing_count = conn.execute(
                """
                SELECT COUNT(*) FROM contracts
                WHERE chain = ? AND chat_id = ?
                """,
                (self.chain, self.chat_id),
            ).fetchone()[0]
            if existing_count > 0:
                return

            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    legacy_data = json.load(f)
            except Exception as e:
                print(f"⚠️  迁移合约缓存失败: {e}")
                return

            if not isinstance(legacy_data, dict):
                return

            for token_address, contract_data in legacy_data.items():
                if token_address and isinstance(contract_data, dict):
                    self._upsert_contract(conn, token_address, contract_data)

    def _row_to_contract(self, row) -> Dict:
        data = {
            "initial_price": _safe_float(row["initial_price"]),
            "initial_market_cap": _safe_float(row["initial_market_cap"]),
            "push_time": row["push_time"],
            "notified_multipliers": _json_loads(row["notified_multipliers_json"], []),
            "name": row["name"],
            "symbol": row["symbol"],
            "telegram_message_ids": _json_loads(row["telegram_message_ids_json"], {}),
        }
        pending = _json_loads(row["pending_multiplier_json"], None)
        if pending:
            data["pending_multiplier"] = pending
        if row["last_notify_time"]:
            data["last_notify_time"] = row["last_notify_time"]
        return data

    def _load_contract(self, token_address: str) -> Optional[Dict]:
        with connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM contracts
                WHERE chain = ? AND chat_id = ? AND token_address = ?
                """,
                (self.chain, self.chat_id, token_address),
            ).fetchone()
        return self._row_to_contract(row) if row else None

    def _upsert_contract(self, conn, token_address: str, contract_data: Dict):
        notified_multipliers = contract_data.get("notified_multipliers", [])
        if not isinstance(notified_multipliers, list):
            notified_multipliers = []

        telegram_message_ids = contract_data.get("telegram_message_ids", {})
        if not isinstance(telegram_message_ids, dict):
            telegram_message_ids = {}

        pending_multiplier = contract_data.get("pending_multiplier")
        pending_multiplier_json = ""
        if isinstance(pending_multiplier, dict):
            pending_multiplier_json = json.dumps(pending_multiplier, ensure_ascii=False)

        conn.execute(
            """
            INSERT INTO contracts (
                chain, chat_id, token_address, initial_price, initial_market_cap,
                push_time, notified_multipliers_json, name, symbol,
                telegram_message_ids_json, pending_multiplier_json, last_notify_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chain, chat_id, token_address) DO UPDATE SET
                initial_price=excluded.initial_price,
                initial_market_cap=excluded.initial_market_cap,
                push_time=excluded.push_time,
                notified_multipliers_json=excluded.notified_multipliers_json,
                name=excluded.name,
                symbol=excluded.symbol,
                telegram_message_ids_json=excluded.telegram_message_ids_json,
                pending_multiplier_json=excluded.pending_multiplier_json,
                last_notify_time=excluded.last_notify_time
            """,
            (
                self.chain,
                self.chat_id,
                token_address,
                _safe_float(contract_data.get("initial_price")),
                _safe_float(contract_data.get("initial_market_cap")),
                contract_data.get("push_time", ""),
                json.dumps(notified_multipliers, ensure_ascii=False),
                contract_data.get("name", ""),
                contract_data.get("symbol", ""),
                json.dumps(telegram_message_ids, ensure_ascii=False),
                pending_multiplier_json,
                contract_data.get("last_notify_time", ""),
            ),
        )

    def is_new_contract(self, token_address: str) -> bool:
        return self.get_contract(token_address) is None

    def add_contract(self, token_address: str, initial_price: float, contract_info: Dict):
        push_time = format_beijing_time()
        current_market_cap = _safe_float(contract_info.get("marketCapUSD"))
        data = {
            "initial_price": initial_price,
            "initial_market_cap": current_market_cap,
            "push_time": push_time,
            "notified_multipliers": [],
            "name": contract_info.get("name", ""),
            "symbol": contract_info.get("symbol", ""),
            "telegram_message_ids": {},
        }
        with connect() as conn:
            self._upsert_contract(conn, token_address, data)

    def get_contract(self, token_address: str) -> Optional[Dict]:
        return self._load_contract(token_address)

    def update_notified_multiplier(self, token_address: str, multiplier: float):
        data = self.get_contract(token_address)
        if not data:
            return
        data["notified_multipliers"].append(multiplier)
        with connect() as conn:
            self._upsert_contract(conn, token_address, data)

    def get_notified_multipliers(self, token_address: str) -> List[float]:
        data = self.get_contract(token_address)
        return data.get("notified_multipliers", []) if data else []

    def get_max_notified_integer_multiplier(self, token_address: str) -> int:
        multipliers = self.get_notified_multipliers(token_address)
        if multipliers:
            return int(max(multipliers))
        return 0

    def get_pending_multiplier(self, token_address: str) -> Optional[Dict]:
        data = self.get_contract(token_address)
        return data.get("pending_multiplier") if data else None

    def update_pending_multiplier(self, token_address: str, multiplier_int: int, count: int):
        data = self.get_contract(token_address)
        if not data:
            return
        data["pending_multiplier"] = {
            "multiplier_int": multiplier_int,
            "count": count,
        }
        with connect() as conn:
            self._upsert_contract(conn, token_address, data)

    def clear_pending_multiplier(self, token_address: str):
        data = self.get_contract(token_address)
        if not data or "pending_multiplier" not in data:
            return
        del data["pending_multiplier"]
        with connect() as conn:
            self._upsert_contract(conn, token_address, data)

    def update_telegram_message_id(self, token_address: str, chat_id: int, message_id: int):
        data = self.get_contract(token_address)
        if not data:
            return
        data.setdefault("telegram_message_ids", {})
        data["telegram_message_ids"][str(chat_id)] = message_id
        with connect() as conn:
            self._upsert_contract(conn, token_address, data)

    def get_telegram_message_id(self, token_address: str, chat_id: int) -> Optional[int]:
        data = self.get_contract(token_address)
        if not data:
            return None
        message_ids = data.get("telegram_message_ids", {})
        return message_ids.get(str(chat_id))

    def update_initial_price(self, token_address: str, new_price: float, new_market_cap: float):
        data = self.get_contract(token_address)
        if not data:
            return
        data["initial_price"] = new_price
        data["initial_market_cap"] = new_market_cap
        data["push_time"] = format_beijing_time()
        data["notified_multipliers"] = []
        with connect() as conn:
            self._upsert_contract(conn, token_address, data)

    def update_last_notify_time(self, token_address: str):
        data = self.get_contract(token_address)
        if not data:
            return
        data["last_notify_time"] = format_beijing_time()
        with connect() as conn:
            self._upsert_contract(conn, token_address, data)

    def get_last_notify_time(self, token_address: str) -> Optional[str]:
        data = self.get_contract(token_address)
        return data.get("last_notify_time") if data else None

    def get_today_trend_contracts(self) -> List[Dict]:
        today_start = beijing_today_start().replace(tzinfo=None)
        contracts = []

        with connect() as conn:
            rows = conn.execute(
                """
                SELECT token_address, * FROM contracts
                WHERE chain = ? AND chat_id = ?
                """,
                (self.chain, self.chat_id),
            ).fetchall()

        for row in rows:
            data = self._row_to_contract(row)
            telegram_message_ids = data.get("telegram_message_ids", {})
            if not telegram_message_ids:
                continue

            has_real_notification = any(
                msg_id != -1 for msg_id in telegram_message_ids.values()
            )
            if not has_real_notification:
                continue

            push_time_str = data.get("push_time")
            if push_time_str:
                try:
                    push_time = datetime.strptime(push_time_str, "%Y-%m-%d %H:%M:%S")
                    if push_time >= today_start:
                        contracts.append({
                            "token_address": row["token_address"],
                            "data": data
                        })
                except ValueError:
                    pass

        return contracts

    def cleanup_old_data(self, days_to_keep: int = 7) -> int:
        cutoff_date = beijing_now().replace(tzinfo=None) - timedelta(days=days_to_keep)

        with connect() as conn:
            rows = conn.execute(
                """
                SELECT token_address, push_time FROM contracts
                WHERE chain = ? AND chat_id = ?
                """,
                (self.chain, self.chat_id),
            ).fetchall()

            to_delete = []
            for row in rows:
                push_time_str = row["push_time"]
                if not push_time_str:
                    continue
                try:
                    push_time = datetime.strptime(push_time_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                if push_time < cutoff_date:
                    to_delete.append(row["token_address"])

            for token_address in to_delete:
                conn.execute(
                    """
                    DELETE FROM contracts
                    WHERE chain = ? AND chat_id = ? AND token_address = ?
                    """,
                    (self.chain, self.chat_id, token_address),
                )

        return len(to_delete)

    def clear_all(self):
        with connect() as conn:
            conn.execute(
                "DELETE FROM contracts WHERE chain = ? AND chat_id = ?",
                (self.chain, self.chat_id),
            )
