"""
Configuration validator - validates configuration integrity
"""

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .loader import ConfigLoader

logger = logging.getLogger(__name__)


class ConfigValidator:
    """配置验证器"""

    @staticmethod
    def validate(config: "ConfigLoader", require_credentials: bool = True) -> None:
        """
        验证配置的有效性

        Args:
            config: 配置加载器实例

        Raises:
            ValueError: 配置无效时抛出
        """
        # 验证 API 凭据
        if require_credentials and (not config.API_ID or not config.API_HASH):
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

        for rule_idx, rule in enumerate(enabled_rules, 1):
            if not rule.target_ids:
                raise ValueError(f"群组 {group.id} 的规则缺少目标群组")
            ConfigValidator._validate_delivery(group, rule, rule_idx)
            ConfigValidator._validate_filters(group, rule, rule_idx)

    @staticmethod
    def _validate_delivery(group, rule, rule_idx: int) -> None:
        if rule.forward_mode not in {"forward", "copy"}:
            raise ValueError(
                f"群组 {group.id} 的规则 {rule_idx} forward_mode 必须是 forward 或 copy"
            )

    @staticmethod
    def _validate_filters(group, rule, rule_idx: int) -> None:
        if rule.filter_mode not in {"all", "include", "exclude"}:
            raise ValueError(f"群组 {group.id} 的规则 {rule_idx} 过滤模式无效")

        if rule.filter_mode == "all":
            return

        if not isinstance(rule.filter_rules, list) or not rule.filter_rules:
            raise ValueError(
                f"群组 {group.id} 的规则 {rule_idx} 在 {rule.filter_mode} 模式下需要过滤规则"
            )

        for filter_idx, filter_rule in enumerate(rule.filter_rules, 1):
            ConfigValidator._validate_filter_rule(
                filter_rule,
                f"群组 {group.id} 的规则 {rule_idx} 过滤规则 {filter_idx}",
            )

    @staticmethod
    def _validate_filter_rule(rule_config, context: str) -> None:
        if not isinstance(rule_config, dict):
            raise ValueError(f"{context} 必须是对象")

        rule_type = rule_config.get("type")
        config = rule_config.get("config", {})
        if not isinstance(config, dict):
            raise ValueError(f"{context}.config 必须是对象")

        if rule_type == "keyword":
            ConfigValidator._validate_keyword(config, context)
        elif rule_type == "regex":
            ConfigValidator._validate_regex(config, context)
        elif rule_type == "user":
            ConfigValidator._validate_user(config, context)
        elif rule_type == "user_conditional":
            ConfigValidator._validate_user_conditional(config, context)
        elif rule_type == "media":
            ConfigValidator._validate_media(config, context)
        elif rule_type == "composite":
            ConfigValidator._validate_composite(config, context)
        elif rule_type == "length":
            ConfigValidator._validate_length(config, context)
        elif rule_type == "link":
            ConfigValidator._validate_bool_option(config, context, "contains")
        elif rule_type == "reply":
            ConfigValidator._validate_bool_option(config, context, "is_reply")
        elif rule_type == "bot":
            ConfigValidator._validate_bool_option(config, context, "is_bot")
        elif rule_type == "channel_post":
            ConfigValidator._validate_bool_option(config, context, "is_channel_post")
        else:
            raise ValueError(f"{context}.type 未知: {rule_type}")

    @staticmethod
    def _validate_match_mode(config, context: str) -> None:
        match_mode = config.get("match_mode", "any")
        if match_mode not in {"any", "all"}:
            raise ValueError(f"{context}.match_mode 必须是 any 或 all")

    @staticmethod
    def _validate_keyword(config, context: str) -> None:
        words = config.get("words", [])
        if not isinstance(words, list) or not words:
            raise ValueError(f"{context}.config.words 必须是非空数组")
        if not all(isinstance(word, str) and word for word in words):
            raise ValueError(f"{context}.config.words 只能包含非空字符串")
        ConfigValidator._validate_match_mode(config, context)

    @staticmethod
    def _validate_regex(config, context: str) -> None:
        pattern = config.get("pattern", "")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(f"{context}.config.pattern 必须是非空字符串")

        flags_str = config.get("flags", "")
        if not isinstance(flags_str, str) or any(
            flag not in "ims" for flag in flags_str
        ):
            raise ValueError(f"{context}.config.flags 只能包含 i、m、s")

        flags = 0
        if "i" in flags_str:
            flags |= re.IGNORECASE
        if "m" in flags_str:
            flags |= re.MULTILINE
        if "s" in flags_str:
            flags |= re.DOTALL

        try:
            config["_compiled_pattern"] = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"{context} 正则表达式无效: {e}") from e

    @staticmethod
    def _validate_user(config, context: str) -> None:
        users = config.get("users", [])
        if not isinstance(users, list) or not users:
            raise ValueError(f"{context}.config.users 必须是非空数组")
        for user in users:
            if not isinstance(user, (str, int)):
                raise ValueError(f"{context}.config.users 只能包含用户名或用户 ID")
            if isinstance(user, str) and not user:
                raise ValueError(f"{context}.config.users 不能包含空字符串")

    @staticmethod
    def _validate_user_conditional(config, context: str) -> None:
        ConfigValidator._validate_user(config, context)
        condition_logic = config.get("condition_logic", "any")
        if condition_logic not in {"any", "all"}:
            raise ValueError(f"{context}.config.condition_logic 必须是 any 或 all")

        conditions = config.get("conditions", [])
        forward_all = config.get("forward_all", False)
        if forward_all:
            return
        if not isinstance(conditions, list) or not conditions:
            raise ValueError(
                f"{context}.config.conditions 必须是非空数组，除非 forward_all=true"
            )
        for idx, condition in enumerate(conditions, 1):
            ConfigValidator._validate_filter_rule(
                condition, f"{context}.conditions[{idx}]"
            )

    @staticmethod
    def _validate_media(config, context: str) -> None:
        media_types = config.get("types", [])
        allowed_types = {"photo", "video", "document", "audio", "sticker", "voice"}
        if not isinstance(media_types, list) or not media_types:
            raise ValueError(f"{context}.config.types 必须是非空数组")
        unknown = [
            media_type for media_type in media_types if media_type not in allowed_types
        ]
        if unknown:
            raise ValueError(f"{context}.config.types 包含未知媒体类型: {unknown}")
        ConfigValidator._validate_match_mode(config, context)

    @staticmethod
    def _validate_composite(config, context: str) -> None:
        logic = config.get("logic", "and")
        if logic not in {"and", "or"}:
            raise ValueError(f"{context}.config.logic 必须是 and 或 or")

        rules = config.get("rules", [])
        if not isinstance(rules, list) or not rules:
            raise ValueError(f"{context}.config.rules 必须是非空数组")
        for idx, child_rule in enumerate(rules, 1):
            ConfigValidator._validate_filter_rule(child_rule, f"{context}.rules[{idx}]")

    @staticmethod
    def _validate_length(config, context: str) -> None:
        min_length = config.get("min")
        max_length = config.get("max")
        if min_length is None and max_length is None:
            raise ValueError(f"{context}.config 需要 min 或 max")
        for key, value in (("min", min_length), ("max", max_length)):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{context}.config.{key} 必须是非负整数")
        if (
            min_length is not None
            and max_length is not None
            and min_length > max_length
        ):
            raise ValueError(f"{context}.config.min 不能大于 max")

    @staticmethod
    def _validate_bool_option(config, context: str, key: str) -> None:
        if key in config and not isinstance(config[key], bool):
            raise ValueError(f"{context}.config.{key} 必须是布尔值")
