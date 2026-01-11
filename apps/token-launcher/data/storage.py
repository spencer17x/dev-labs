"""数据存储"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, asdict


@dataclass
class TokenRecord:
    """代币记录"""
    name: str
    symbol: str
    address: str
    tx_hash: str
    chain: str
    source_tweet_id: str
    source_username: str
    created_at: str
    platform_url: str = ""


class TokenStorage:
    def __init__(self, storage_path: str = None):
        if storage_path is None:
            storage_path = Path(__file__).parent / "tokens.json"
        self.storage_path = Path(storage_path)
        self._ensure_file()

    def _ensure_file(self):
        """确保存储文件存在"""
        if not self.storage_path.exists():
            self._save({"tokens": []})

    def _load(self) -> dict:
        """加载数据"""
        with open(self.storage_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict):
        """保存数据"""
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_token(self, record: TokenRecord):
        """添加代币记录"""
        data = self._load()
        data["tokens"].append(asdict(record))
        self._save(data)

    def get_all_tokens(self) -> List[dict]:
        """获取所有代币记录"""
        return self._load().get("tokens", [])

    def find_by_tweet_id(self, tweet_id: str) -> Optional[dict]:
        """根据推文ID查找代币"""
        tokens = self.get_all_tokens()
        for token in tokens:
            if token.get("source_tweet_id") == tweet_id:
                return token
        return None

    def has_processed_tweet(self, tweet_id: str) -> bool:
        """检查推文是否已处理过"""
        return self.find_by_tweet_id(tweet_id) is not None
