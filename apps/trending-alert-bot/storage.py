import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from timezone_utils import beijing_now, beijing_today_start, format_beijing_time


class ContractStorage:
    def __init__(self, storage_file: str):
        self.storage_file = storage_file
        self.data: Dict = self._load()

    def _load(self) -> Dict:
        if os.path.exists(self.storage_file):
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_new_contract(self, token_address: str) -> bool:
        return token_address not in self.data

    def add_contract(self, token_address: str, initial_price: float, contract_info: Dict):
        push_time = format_beijing_time()
        current_market_cap = float(contract_info.get("marketCapUSD", 0))
        self.data[token_address] = {
            "initial_price": initial_price,
            "initial_market_cap": current_market_cap,
            "push_time": push_time,
            "notified_multipliers": [],
            "name": contract_info.get("name", ""),
            "symbol": contract_info.get("symbol", ""),
            "telegram_message_ids": {},
        }
        self._save()

    def get_contract(self, token_address: str) -> Optional[Dict]:
        return self.data.get(token_address)

    def update_notified_multiplier(self, token_address: str, multiplier: float):
        if token_address in self.data:
            self.data[token_address]["notified_multipliers"].append(multiplier)
            self._save()

    def get_notified_multipliers(self, token_address: str) -> List[float]:
        if token_address in self.data:
            return self.data[token_address]["notified_multipliers"]
        return []

    def get_max_notified_integer_multiplier(self, token_address: str) -> int:
        """获取已通知的最高整数倍数"""
        if token_address in self.data:
            multipliers = self.data[token_address].get("notified_multipliers", [])
            if multipliers:
                return int(max(multipliers))
        return 0

    def update_price_history(self, token_address: str, price: float):
        # price_history 已移除以节省空间，保留此方法以保持兼容性
        pass

    def update_telegram_message_id(self, token_address: str, chat_id: int, message_id: int):
        if token_address in self.data:
            if "telegram_message_ids" not in self.data[token_address]:
                self.data[token_address]["telegram_message_ids"] = {}
            self.data[token_address]["telegram_message_ids"][str(chat_id)] = message_id
            self._save()

    def get_telegram_message_id(self, token_address: str, chat_id: int) -> Optional[int]:
        if token_address in self.data:
            message_ids = self.data[token_address].get("telegram_message_ids", {})
            return message_ids.get(str(chat_id))
        return None

    def update_initial_price(self, token_address: str, new_price: float, new_market_cap: float):
        if token_address in self.data:
            self.data[token_address]["initial_price"] = new_price
            self.data[token_address]["initial_market_cap"] = new_market_cap
            self.data[token_address]["push_time"] = format_beijing_time()
            self.data[token_address]["notified_multipliers"] = []
            self._save()

    def get_today_trend_contracts(self) -> List[Dict]:
        # 使用不带时区的北京时间进行比较
        today_start = beijing_today_start().replace(tzinfo=None)
        contracts = []

        for token_address, data in self.data.items():
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
                            "token_address": token_address,
                            "data": data
                        })
                except:
                    pass

        return contracts

    def cleanup_old_data(self, days_to_keep: int = 7) -> int:
        """清理 N 天前的数据（基于北京时间）"""
        cutoff_date = beijing_now().replace(tzinfo=None) - timedelta(days=days_to_keep)

        to_delete = []
        for token_address, data in self.data.items():
            push_time_str = data.get("push_time", "")
            if push_time_str:
                try:
                    push_time = datetime.strptime(push_time_str, "%Y-%m-%d %H:%M:%S")
                    if push_time < cutoff_date:
                        to_delete.append(token_address)
                except:
                    pass

        for addr in to_delete:
            del self.data[addr]

        if to_delete:
            self._save()

        return len(to_delete)

    def remove_all_price_history(self) -> int:
        """一次性移除所有合约的 price_history，用于清理旧数据"""
        count = 0
        for token_address in self.data:
            if "price_history" in self.data[token_address]:
                del self.data[token_address]["price_history"]
                count += 1

        if count > 0:
            self._save()

        return count

    def update_narrative(self, token_address: str, narrative: Dict):
        """更新合约的叙事数据"""
        if token_address in self.data:
            self.data[token_address]["narrative"] = narrative
            self.data[token_address]["narrative_notified"] = True
            self._save()

    def get_narrative(self, token_address: str) -> Optional[Dict]:
        """获取合约的叙事数据"""
        if token_address in self.data:
            return self.data[token_address].get("narrative")
        return None

    def is_narrative_notified(self, token_address: str) -> bool:
        """检查叙事是否已通知"""
        if token_address in self.data:
            return self.data[token_address].get("narrative_notified", False)
        return False

    def mark_narrative_pending(self, token_address: str):
        """标记叙事待更新"""
        if token_address in self.data:
            self.data[token_address]["narrative_pending"] = True
            self._save()

    def get_pending_narrative_contracts(self) -> List[str]:
        """获取所有待更新叙事的合约"""
        pending = []
        for token_address, data in self.data.items():
            if data.get("narrative_pending") and not data.get("narrative_notified"):
                pending.append(token_address)
        return pending
