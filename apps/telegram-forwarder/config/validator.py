"""
Configuration validator - validates configuration integrity
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .loader import ConfigLoader

logger = logging.getLogger(__name__)


class ConfigValidator:
    """配置验证器"""

    @staticmethod
    def validate(config: 'ConfigLoader') -> None:
        """
        验证配置的有效性

        Args:
            config: 配置加载器实例

        Raises:
            ValueError: 配置无效时抛出
        """
        # 验证 API 凭据
        if not config.API_ID or not config.API_HASH:
            raise ValueError("API_ID and API_HASH must be provided in .env file")

        # 验证群组配置
        if not config.groups:
            raise ValueError("至少需要配置一个源群组")

        enabled_groups = [g for g in config.groups if g.enabled]
        if not enabled_groups:
            raise ValueError("至少需要启用一个源群组")

        # 验证每个群组配置
        for group in enabled_groups:
            ConfigValidator._validate_group(group)

        logger.info("✓ 配置验证通过")

    @staticmethod
    def _validate_group(group) -> None:
        """验证单个群组配置"""
        if not group.source_id:
            raise ValueError(f"群组 {group.id} 缺少源群组ID")

        if not group.rules:
            raise ValueError(f"群组 {group.id} 没有配置任何规则")

        # 验证规则
        enabled_rules = [r for r in group.rules if r.enabled]
        if not enabled_rules:
            logger.warning(f"群组 {group.id} 没有启用的规则")

        for rule in enabled_rules:
            if not rule.target_ids:
                raise ValueError(f"群组 {group.id} 的规则缺少目标群组")
