"""Four.meme 平台部署器 - 通过智能合约创建代币"""

import logging
import asyncio
from typing import Optional
from web3 import Web3
from eth_account import Account
from .base import BaseDeployer, TokenInfo, DeployResult

logger = logging.getLogger(__name__)

# Four.meme TokenManager 合约地址 (BSC Mainnet)
TOKEN_MANAGER_ADDRESS = "0x5c952063c7fc8610FFDB798152D69F0B9550762b"

# BSC RPC URLs
BSC_RPC_URLS = {
    "mainnet": "https://bsc-dataseed1.binance.org/",
    "testnet": "https://data-seed-prebsc-1-s1.binance.org:8545/",
}

# Bag 合约 ABI (createBump 和 createBumpAndBuy 函数)
# 基于 https://github.com/Four-Meme/Four-Smart-Contracts/blob/main/src/v1/Bag.sol
BAG_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "_name", "type": "string"},
            {"internalType": "string", "name": "_symbol", "type": "string"},
            {"internalType": "string", "name": "_introduction", "type": "string"},
            {"internalType": "string", "name": "_iconAddress", "type": "string"},
            {"internalType": "string", "name": "_twitterAddress", "type": "string"},
            {"internalType": "string", "name": "_telegramAddress", "type": "string"},
            {"internalType": "string", "name": "_websiteAddress", "type": "string"},
        ],
        "name": "createBump",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "_name", "type": "string"},
            {"internalType": "string", "name": "_symbol", "type": "string"},
            {"internalType": "string", "name": "_introduction", "type": "string"},
            {"internalType": "string", "name": "_iconAddress", "type": "string"},
            {"internalType": "string", "name": "_twitterAddress", "type": "string"},
            {"internalType": "string", "name": "_telegramAddress", "type": "string"},
            {"internalType": "string", "name": "_websiteAddress", "type": "string"},
        ],
        "name": "createBumpAndBuy",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "deployer", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "token", "type": "address"},
        ],
        "name": "OpenBumpPresale",
        "type": "event",
    },
]


class FourMemeDeployer(BaseDeployer):
    """
    通过 Four.meme 智能合约创建代币

    合约地址: 0x5c952063c7fc8610FFDB798152D69F0B9550762b (BSC)
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.private_key = config.get("private_key")
        self.chain = config.get("chain", "bsc")
        self.network = config.get("network", "mainnet")
        self.contract_address = config.get("contract_address", TOKEN_MANAGER_ADDRESS)
        self.buy_amount = config.get("buy_amount", 0)  # BNB amount to buy on creation

        # 初始化 Web3
        rpc_url = config.get("rpc_url") or BSC_RPC_URLS.get(self.network, BSC_RPC_URLS["mainnet"])
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        # 初始化账户
        if self.private_key:
            self.account = Account.from_key(self.private_key)
            self.address = self.account.address
        else:
            self.account = None
            self.address = None

        # 初始化合约
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=BAG_ABI
        )

    def _check_connection(self) -> bool:
        """检查网络连接"""
        try:
            return self.w3.is_connected()
        except Exception:
            return False

    def _get_balance(self) -> float:
        """获取账户 BNB 余额"""
        if not self.address:
            return 0
        balance_wei = self.w3.eth.get_balance(self.address)
        return self.w3.from_wei(balance_wei, "ether")

    async def deploy(self, token_info: TokenInfo, buy_amount: float = None) -> DeployResult:
        """
        调用 Four.meme 合约创建代币

        Args:
            token_info: 代币信息
            buy_amount: 创建时购买的 BNB 数量，0 表示只创建不购买

        Returns:
            DeployResult: 部署结果
        """
        logger.info(f"准备在 Four.meme 创建代币: {token_info.name} ({token_info.symbol})")

        # 检查配置
        if not self.private_key:
            return DeployResult(success=False, error="未配置钱包私钥 (FOUR_MEME_PRIVATE_KEY)")

        if not self._check_connection():
            return DeployResult(success=False, error=f"无法连接到 BSC 网络")

        # 检查余额
        balance = self._get_balance()
        logger.info(f"钱包地址: {self.address}")
        logger.info(f"BNB 余额: {balance:.4f}")

        if balance < 0.01:
            return DeployResult(success=False, error=f"BNB 余额不足: {balance:.4f} BNB")

        try:
            # 确定是否购买
            actual_buy_amount = buy_amount if buy_amount is not None else self.buy_amount

            # 构建交易参数
            args = (
                token_info.name,
                token_info.symbol,
                token_info.description,
                token_info.image_url,
                token_info.twitter_url,
                token_info.telegram_url,
                token_info.website_url,
            )

            # 获取 gas 价格和 nonce
            gas_price = self.w3.eth.gas_price
            nonce = self.w3.eth.get_transaction_count(self.address)

            if actual_buy_amount > 0:
                # createBumpAndBuy - 创建并购买
                logger.info(f"使用 createBumpAndBuy，购买金额: {actual_buy_amount} BNB")
                value_wei = self.w3.to_wei(actual_buy_amount, "ether")

                tx = self.contract.functions.createBumpAndBuy(*args).build_transaction({
                    "from": self.address,
                    "value": value_wei,
                    "gas": 3000000,
                    "gasPrice": gas_price,
                    "nonce": nonce,
                })
            else:
                # createBump - 只创建
                logger.info("使用 createBump，只创建不购买")
                tx = self.contract.functions.createBump(*args).build_transaction({
                    "from": self.address,
                    "value": 0,
                    "gas": 3000000,
                    "gasPrice": gas_price,
                    "nonce": nonce,
                })

            # 签名交易
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)

            # 发送交易
            logger.info("发送交易...")
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()
            logger.info(f"交易已发送: {tx_hash_hex}")

            # 等待交易确认
            logger.info("等待交易确认...")
            receipt = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            )

            if receipt["status"] == 1:
                # 解析事件获取代币地址
                token_address = self._parse_token_address(receipt)

                logger.info(f"✅ 代币创建成功!")
                logger.info(f"   代币地址: {token_address}")
                logger.info(f"   交易哈希: {tx_hash_hex}")

                return DeployResult(
                    success=True,
                    token_address=token_address,
                    tx_hash=tx_hash_hex,
                    platform_url=f"https://four.meme/token/{token_address}" if token_address else None,
                )
            else:
                return DeployResult(
                    success=False,
                    tx_hash=tx_hash_hex,
                    error="交易执行失败",
                )

        except Exception as e:
            logger.error(f"创建代币失败: {e}")
            return DeployResult(success=False, error=str(e))

    def _parse_token_address(self, receipt) -> Optional[str]:
        """从交易回执中解析代币地址"""
        try:
            # 尝试从 OpenBumpPresale 事件中获取
            logs = self.contract.events.OpenBumpPresale().process_receipt(receipt)
            if logs:
                return logs[0]["args"]["token"]
        except Exception as e:
            logger.warning(f"解析事件失败: {e}")

        # 备选方案：从 logs 中直接解析
        try:
            for log in receipt["logs"]:
                # OpenBumpPresale 事件的 topic
                if len(log["topics"]) >= 3:
                    # topic[2] 是 token 地址
                    token_address = "0x" + log["topics"][2].hex()[-40:]
                    return Web3.to_checksum_address(token_address)
        except Exception as e:
            logger.warning(f"备选解析失败: {e}")

        return None

    async def check_status(self, tx_hash: str) -> dict:
        """检查交易状态"""
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            if receipt:
                return {
                    "status": "success" if receipt["status"] == 1 else "failed",
                    "tx_hash": tx_hash,
                    "block_number": receipt["blockNumber"],
                    "gas_used": receipt["gasUsed"],
                }
            else:
                return {"status": "pending", "tx_hash": tx_hash}
        except Exception as e:
            return {"status": "error", "tx_hash": tx_hash, "error": str(e)}
