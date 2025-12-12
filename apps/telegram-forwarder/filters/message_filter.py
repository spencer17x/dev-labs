"""
Message filter implementation
Supports flexible filtering rules with multiple modes and conditions
"""
import re
import logging
from typing import Dict, List, Any
from telethon.tl.types import Message

# Import GroupRule for type hints
from config.loader import GroupRule

logger = logging.getLogger(__name__)


class RuleEvaluator:
    """规则评估器"""

    @staticmethod
    def evaluate(message: Message, rule: Dict[str, Any]) -> bool:
        """
        评估单条规则是否匹配消息

        Args:
            message: Telegram 消息对象
            rule: 规则配置字典

        Returns:
            bool: 是否匹配
        """
        rule_type = rule.get("type")
        config = rule.get("config", {})

        if rule_type == "keyword":
            return RuleEvaluator._eval_keyword(message, config)
        elif rule_type == "regex":
            return RuleEvaluator._eval_regex(message, config)
        elif rule_type == "user":
            return RuleEvaluator._eval_user(message, config)
        elif rule_type == "user_conditional":
            return RuleEvaluator._eval_user_conditional(message, config)
        elif rule_type == "media":
            return RuleEvaluator._eval_media(message, config)
        elif rule_type == "composite":
            return RuleEvaluator._eval_composite(message, config)
        else:
            logger.warning(f"未知的规则类型: {rule_type}")
            return False

    @staticmethod
    def _eval_keyword(message: Message, config: Dict[str, Any]) -> bool:
        """关键词匹配"""
        if not message.text:
            return False

        words = config.get("words", [])
        match_case = config.get("match_case", False)
        match_mode = config.get("match_mode", "any")  # any | all

        text = message.text if match_case else message.text.lower()

        matches = []
        for word in words:
            keyword = word if match_case else word.lower()
            matches.append(keyword in text)

        if match_mode == "any":
            result = any(matches)
        else:  # all
            result = all(matches)

        if result:
            matched_words = [w for w, m in zip(words, matches) if m]
            logger.info(f"关键词匹配成功: {matched_words}")

        return result

    @staticmethod
    def _eval_regex(message: Message, config: Dict[str, Any]) -> bool:
        """正则表达式匹配"""
        if not message.text:
            return False

        pattern = config.get("pattern", "")
        if not pattern:
            return False

        flags_str = config.get("flags", "")
        description = config.get("description", "")

        # 解析正则标志
        flags = 0
        if 'i' in flags_str:
            flags |= re.IGNORECASE
        if 'm' in flags_str:
            flags |= re.MULTILINE
        if 's' in flags_str:
            flags |= re.DOTALL

        try:
            regex = re.compile(pattern, flags)
            match = regex.search(message.text)

            if match:
                desc_info = f" ({description})" if description else ""
                logger.info(f"正则匹配成功{desc_info}: '{match.group(0)}'")
                return True

            return False
        except re.error as e:
            logger.warning(f"无效的正则表达式: {pattern}, 错误: {e}")
            return False

    @staticmethod
    def _eval_user(message: Message, config: Dict[str, Any]) -> bool:
        """用户匹配"""
        sender_id = message.sender_id
        if not sender_id:
            return False

        users = config.get("users", [])
        forward_all = config.get("forward_all", True)

        # 检查发送者ID
        for user in users:
            if isinstance(user, int) and sender_id == user:
                if forward_all:
                    logger.info(f"用户ID匹配: {sender_id} (转发所有消息)")
                return True

        # 检查用户名
        if hasattr(message, 'sender') and message.sender and hasattr(message.sender, 'username'):
            sender_username = message.sender.username
            if sender_username:
                clean_sender = sender_username.replace('@', '').lower()

                for user in users:
                    if isinstance(user, str):
                        clean_user = user.replace('@', '').lower()
                        if clean_sender == clean_user:
                            if forward_all:
                                logger.info(f"用户名匹配: @{sender_username} (转发所有消息)")
                            return True

        return False

    @staticmethod
    def _eval_user_conditional(message: Message, config: Dict[str, Any]) -> bool:
        """用户条件匹配"""
        # 首先检查是否是指定用户
        if not RuleEvaluator._eval_user(message, config):
            return False

        # 获取发送者信息用于日志
        sender_info = RuleEvaluator._get_sender_info(message)

        conditions = config.get("conditions", [])
        condition_logic = config.get("condition_logic", "any")  # any | all

        # 如果没有附加条件，根据 forward_all 决定（已在 _eval_user 中处理）
        if not conditions:
            return True

        # 评估所有条件
        results = []
        for condition in conditions:
            result = RuleEvaluator.evaluate(message, condition)
            results.append(result)

        if condition_logic == "any":
            matched = any(results)
        else:  # all
            matched = all(results)

        if matched:
            logger.info(f"用户 {sender_info} 的消息满足附加条件")
        else:
            logger.info(f"用户 {sender_info} 的消息不满足附加条件")

        return matched

    @staticmethod
    def _eval_media(message: Message, config: Dict[str, Any]) -> bool:
        """媒体类型匹配"""
        types = config.get("types", [])
        match_mode = config.get("match_mode", "any")

        has_media = []

        if "photo" in types:
            has_media.append(bool(message.photo))
        if "video" in types:
            has_media.append(bool(message.video))
        if "document" in types:
            has_media.append(bool(message.document))
        if "audio" in types:
            has_media.append(bool(message.audio))
        if "sticker" in types:
            has_media.append(bool(message.sticker))
        if "voice" in types:
            has_media.append(bool(message.voice))

        if match_mode == "any":
            return any(has_media)
        else:  # all
            return all(has_media)

    @staticmethod
    def _eval_composite(message: Message, config: Dict[str, Any]) -> bool:
        """组合规则匹配"""
        logic = config.get("logic", "and")  # and | or
        rules = config.get("rules", [])

        if not rules:
            return False

        results = [RuleEvaluator.evaluate(message, rule) for rule in rules]

        if logic == "and":
            return all(results)
        else:  # or
            return any(results)

    @staticmethod
    def _get_sender_info(message: Message) -> str:
        """获取发送者信息用于日志"""
        sender_id = message.sender_id
        if hasattr(message, 'sender') and message.sender and hasattr(message.sender, 'username'):
            sender_username = message.sender.username
            if sender_username:
                return f"@{sender_username} (ID: {sender_id})"
        return f"ID: {sender_id}"


class MessageFilter:
    """消息过滤器"""

    def __init__(self):
        """初始化过滤器"""
        pass

    def should_forward(self, message: Message, rule: GroupRule) -> bool:
        """
        判断消息是否应该根据规则转发

        Args:
            message: Telegram 消息对象
            rule: GroupRule 对象（包含过滤模式和规则）

        Returns:
            bool: 是否应该转发
        """
        filter_mode = rule.filter_mode
        filter_rules = rule.filter_rules

        # 模式1: 转发所有消息
        if filter_mode == "all":
            logger.debug("过滤模式: all - 转发所有消息")
            return True

        # 模式2: 白名单模式 - 只转发匹配的消息
        if filter_mode == "include":
            if not filter_rules:
                # 没有规则的include模式，不转发任何消息
                logger.debug("include 模式但无规则，不转发")
                return False

            # 任一规则匹配即转发
            for i, rule_config in enumerate(filter_rules):
                if RuleEvaluator.evaluate(message, rule_config):
                    logger.debug(f"匹配规则 #{i+1} (类型: {rule_config.get('type')})")
                    return True

            logger.debug("所有 include 规则都不匹配，不转发")
            return False

        # 模式3: 黑名单模式 - 转发所有但排除匹配的消息
        if filter_mode == "exclude":
            if not filter_rules:
                # 没有规则的exclude模式，转发所有消息
                logger.debug("exclude 模式但无规则，转发所有")
                return True

            # 任一规则匹配即不转发
            for i, rule_config in enumerate(filter_rules):
                if RuleEvaluator.evaluate(message, rule_config):
                    logger.debug(f"匹配排除规则 #{i+1} (类型: {rule_config.get('type')})")
                    return False

            logger.debug("所有 exclude 规则都不匹配，转发")
            return True

        # 未知模式
        logger.warning(f"未知的过滤模式: {filter_mode}")
        return False

    def evaluate_rule(self, message: Message, rule: Dict[str, Any]) -> bool:
        """
        评估单条规则（公开接口）

        Args:
            message: Telegram 消息对象
            rule: 规则配置

        Returns:
            bool: 是否匹配
        """
        return RuleEvaluator.evaluate(message, rule)

