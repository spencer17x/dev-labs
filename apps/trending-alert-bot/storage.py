from datetime import datetime, timedelta
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


def _safe_text(value) -> str:
    return "" if value is None else str(value)


class ContractStorage:
    def __init__(self, chain: str, chat_id: int):
        self.chain = (chain or "").strip().lower()
        self.chat_id = _safe_int(chat_id)
        ensure_schema()

    def _load_message_ids(self, conn, token_address: str) -> Dict[str, int]:
        rows = conn.execute(
            """
            SELECT telegram_chat_id, message_id
            FROM contract_message_ids
            WHERE chain = ? AND chat_id = ? AND token_address = ?
            ORDER BY telegram_chat_id
            """,
            (self.chain, self.chat_id, token_address),
        ).fetchall()
        return {str(row["telegram_chat_id"]): row["message_id"] for row in rows}

    def _load_notified_multipliers(self, conn, token_address: str) -> List[float]:
        rows = conn.execute(
            """
            SELECT multiplier
            FROM contract_notified_multipliers
            WHERE chain = ? AND chat_id = ? AND token_address = ?
            ORDER BY multiplier
            """,
            (self.chain, self.chat_id, token_address),
        ).fetchall()
        return [_safe_float(row["multiplier"]) for row in rows]

    def _load_pending_multiplier(self, conn, token_address: str) -> Optional[Dict]:
        row = conn.execute(
            """
            SELECT multiplier_int, count
            FROM contract_pending_multipliers
            WHERE chain = ? AND chat_id = ? AND token_address = ?
            """,
            (self.chain, self.chat_id, token_address),
        ).fetchone()
        if not row:
            return None
        return {
            "multiplier_int": _safe_int(row["multiplier_int"]),
            "count": _safe_int(row["count"]),
        }

    def _row_to_contract(self, conn, row) -> Dict:
        token_address = row["token_address"]
        data = {
            "initial_price": _safe_float(row["initial_price"]),
            "initial_market_cap": _safe_float(row["initial_market_cap"]),
            "push_time": row["push_time"],
            "notified_multipliers": self._load_notified_multipliers(conn, token_address),
            "name": row["name"],
            "symbol": row["symbol"],
            "telegram_message_ids": self._load_message_ids(conn, token_address),
        }
        pending = self._load_pending_multiplier(conn, token_address)
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
            return self._row_to_contract(conn, row) if row else None

    def _upsert_contract(self, conn, token_address: str, contract_data: Dict):
        conn.execute(
            """
            INSERT INTO contracts (
                chain, chat_id, token_address, initial_price, initial_market_cap,
                push_time, name, symbol, last_notify_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chain, chat_id, token_address) DO UPDATE SET
                initial_price=excluded.initial_price,
                initial_market_cap=excluded.initial_market_cap,
                push_time=excluded.push_time,
                name=excluded.name,
                symbol=excluded.symbol,
                last_notify_time=excluded.last_notify_time
            """,
            (
                self.chain,
                self.chat_id,
                token_address,
                _safe_float(contract_data.get("initial_price")),
                _safe_float(contract_data.get("initial_market_cap")),
                _safe_text(contract_data.get("push_time")),
                _safe_text(contract_data.get("name")),
                _safe_text(contract_data.get("symbol")),
                _safe_text(contract_data.get("last_notify_time")),
            ),
        )

    def is_new_contract(self, token_address: str) -> bool:
        return self.get_contract(token_address) is None

    def add_contract(self, token_address: str, initial_price: float, contract_info: Dict):
        data = {
            "initial_price": initial_price,
            "initial_market_cap": _safe_float(contract_info.get("marketCapUSD")),
            "push_time": format_beijing_time(),
            "name": contract_info.get("name", ""),
            "symbol": contract_info.get("symbol", ""),
            "last_notify_time": "",
        }
        with connect() as conn:
            self._upsert_contract(conn, token_address, data)

    def get_contract(self, token_address: str) -> Optional[Dict]:
        return self._load_contract(token_address)

    def update_notified_multiplier(self, token_address: str, multiplier: float):
        if not self.get_contract(token_address):
            return
        with connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO contract_notified_multipliers (
                    chain, chat_id, token_address, multiplier, notified_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (self.chain, self.chat_id, token_address, multiplier, format_beijing_time()),
            )

    def get_notified_multipliers(self, token_address: str) -> List[float]:
        with connect() as conn:
            return self._load_notified_multipliers(conn, token_address)

    def get_max_notified_integer_multiplier(self, token_address: str) -> int:
        multipliers = self.get_notified_multipliers(token_address)
        if multipliers:
            return int(max(multipliers))
        return 0

    def get_pending_multiplier(self, token_address: str) -> Optional[Dict]:
        with connect() as conn:
            return self._load_pending_multiplier(conn, token_address)

    def update_pending_multiplier(self, token_address: str, multiplier_int: int, count: int):
        if not self.get_contract(token_address):
            return
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO contract_pending_multipliers (
                    chain, chat_id, token_address, multiplier_int, count
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chain, chat_id, token_address) DO UPDATE SET
                    multiplier_int=excluded.multiplier_int,
                    count=excluded.count
                """,
                (self.chain, self.chat_id, token_address, multiplier_int, count),
            )

    def clear_pending_multiplier(self, token_address: str):
        with connect() as conn:
            conn.execute(
                """
                DELETE FROM contract_pending_multipliers
                WHERE chain = ? AND chat_id = ? AND token_address = ?
                """,
                (self.chain, self.chat_id, token_address),
            )

    def update_telegram_message_id(self, token_address: str, chat_id: int, message_id: int):
        if not self.get_contract(token_address):
            return
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO contract_message_ids (
                    chain, chat_id, token_address, telegram_chat_id, message_id
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chain, chat_id, token_address, telegram_chat_id)
                DO UPDATE SET message_id=excluded.message_id
                """,
                (self.chain, self.chat_id, token_address, chat_id, message_id),
            )

    def get_telegram_message_id(self, token_address: str, chat_id: int) -> Optional[int]:
        with connect() as conn:
            row = conn.execute(
                """
                SELECT message_id
                FROM contract_message_ids
                WHERE chain = ?
                    AND chat_id = ?
                    AND token_address = ?
                    AND telegram_chat_id = ?
                """,
                (self.chain, self.chat_id, token_address, chat_id),
            ).fetchone()
        return row["message_id"] if row else None

    def update_initial_price(self, token_address: str, new_price: float, new_market_cap: float):
        data = self.get_contract(token_address)
        if not data:
            return
        data["initial_price"] = new_price
        data["initial_market_cap"] = new_market_cap
        data["push_time"] = format_beijing_time()
        with connect() as conn:
            self._upsert_contract(conn, token_address, data)
            conn.execute(
                """
                DELETE FROM contract_notified_multipliers
                WHERE chain = ? AND chat_id = ? AND token_address = ?
                """,
                (self.chain, self.chat_id, token_address),
            )

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
                SELECT * FROM contracts
                WHERE chain = ? AND chat_id = ?
                """,
                (self.chain, self.chat_id),
            ).fetchall()

            for row in rows:
                data = self._row_to_contract(conn, row)
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
                                "data": data,
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
