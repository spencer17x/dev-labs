"""部署器基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenInfo:
    """代币信息"""
    name: str
    symbol: str
    description: str = ""
    image_url: str = ""
    twitter_url: str = ""
    website_url: str = ""


@dataclass
class DeployResult:
    """部署结果"""
    success: bool
    token_address: Optional[str] = None
    tx_hash: Optional[str] = None
    error: Optional[str] = None
    platform_url: Optional[str] = None  # 如 four.meme 上的链接


class BaseDeployer(ABC):
    """部署器基类，方便扩展到其他链/平台"""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def deploy(self, token_info: TokenInfo) -> DeployResult:
        """部署代币"""
        pass

    @abstractmethod
    async def check_status(self, tx_hash: str) -> dict:
        """检查交易状态"""
        pass
