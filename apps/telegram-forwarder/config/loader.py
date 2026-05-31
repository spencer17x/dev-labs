"""
Configuration loader - loads and parses configuration files
"""

import json
import os
import logging
from typing import Dict, List, Any, Union, Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 加载 .env 文件中的环境变量
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


def parse_bool(value: Any, default: bool = False) -> bool:
    """Parse bool-like config/env values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def parse_int(value: Any, default: int = 0) -> int:
    """Parse int-like config/env values with a safe default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class GroupRule:
    """群组内的单条转发规则"""

    def __init__(
        self,
        rule_data: Dict[str, Any],
        source_id: Union[str, int],
        source_name: str = "",
        rule_index: int = 0,
    ):
        # 支持默认值
        self.enabled = rule_data.get("enabled", True)

        # 源信息（从父群组继承）
        self.source_id = source_id
        self.source_name = source_name

        # 目标群组 - 支持简化格式并验证
        targets = rule_data.get("targets", [])
        if not targets:
            raise ValueError(f"规则 {rule_index} 缺少目标群组")

        if isinstance(targets, (str, int)):
            targets = [targets]

        if not isinstance(targets, list):
            raise ValueError(f"规则 {rule_index} 的 targets 必须是数组或单个目标")

        # 简化格式：["@target1", "@target2"] 或 [-1001234, -1005678]
        if len(targets) > 0 and isinstance(targets[0], (str, int)):
            self.target_ids = targets
        elif len(targets) > 0 and isinstance(targets[0], dict):
            # 完整格式：[{"groupId": "@target1"}]
            self.target_ids = [
                t.get("groupId")
                for t in targets
                if isinstance(t, dict) and t.get("groupId")
            ]
            if not self.target_ids:
                raise ValueError(f"规则 {rule_index} 的目标群组格式错误")
        else:
            raise ValueError(f"规则 {rule_index} 的目标群组格式不支持")

        # 过滤器配置
        filters = rule_data.get("filters", {})
        self.filter_mode = filters.get("mode", "all")  # all | include | exclude

        # 验证过滤模式
        if self.filter_mode not in ["all", "include", "exclude"]:
            raise ValueError(f"规则 {rule_index} 的过滤模式 '{self.filter_mode}' 无效")

        self.filter_rules = filters.get("rules", [])

        delivery = rule_data.get("delivery", {})
        if not isinstance(delivery, dict):
            raise ValueError(f"规则 {rule_index} 的 delivery 必须是对象")

        self.forward_mode = rule_data.get(
            "forward_mode",
            delivery.get("mode", os.environ.get("FORWARD_MODE", "forward")),
        )
        self.silent = parse_bool(
            rule_data.get(
                "silent", delivery.get("silent", os.environ.get("SILENT_FORWARD"))
            ),
            False,
        )
        self.dedupe = parse_bool(rule_data.get("dedupe", delivery.get("dedupe")), True)

    def __repr__(self):
        return f"<GroupRule source={self.source_id} targets={len(self.target_ids)} mode={self.filter_mode}>"


class GroupConfig:
    """单个源群组的完整配置"""

    def __init__(self, group_data: Dict[str, Any]):
        self.id = group_data.get("id", "")
        self.name = group_data.get("name", "")
        self.enabled = group_data.get("enabled", True)

        if not self.id:
            raise ValueError("群组配置缺少 id 字段")
        if not self.name:
            raise ValueError(f"群组 {self.id} 缺少 name 字段")

        # 禁用的占位配置允许省略 source/rules，便于临时暂停。
        if not self.enabled:
            self.source_id = None
            self.rules = []
            source = group_data.get("source")
            if isinstance(source, dict):
                self.source_id = source.get("groupId")
            elif isinstance(source, (str, int)):
                self.source_id = source
            for idx, rule_data in enumerate(group_data.get("rules", []), 1):
                rule = GroupRule(rule_data, self.source_id, self.name, idx)
                self.rules.append(rule)
            return

        # 源群组信息 - 支持简化格式
        source = group_data.get("source")
        if not source:
            raise ValueError(f"群组 {self.id} 缺少 source 字段")

        if isinstance(source, dict):
            self.source_id = source.get("groupId")
            if not self.source_id:
                raise ValueError(f"群组 {self.id} 的 source.groupId 为空")
        elif isinstance(source, (str, int)):
            # 简化格式：直接是 groupId
            self.source_id = source
        else:
            raise ValueError(f"群组 {self.id} 的 source 格式不支持")

        # 规则列表
        rules_data = group_data.get("rules", [])
        if not rules_data:
            raise ValueError(f"群组 {self.id} 没有配置规则")

        self.rules = []
        for idx, rule_data in enumerate(rules_data, 1):
            try:
                rule = GroupRule(rule_data, self.source_id, self.name, idx)
                self.rules.append(rule)
            except Exception as e:
                raise ValueError(f"群组 {self.id} 的规则 {idx} 配置错误: {e}")

    def __repr__(self):
        enabled_rules = sum(1 for r in self.rules if r.enabled)
        return f"<GroupConfig id={self.id} source={self.source_id} rules={len(self.rules)} enabled={enabled_rules}>"


class ConfigLoader:
    """配置加载器"""

    def __init__(self, config_path: Optional[str] = None):
        # API 凭据从环境变量获取
        self.API_ID = os.environ.get("TELEGRAM_API_ID")
        self.API_HASH = os.environ.get("TELEGRAM_API_HASH")
        self._session_name_from_env = os.environ.get("TELEGRAM_SESSION_PATH")
        self.SESSION_NAME = self._session_name_from_env or "telegram_forwarder_session"
        self.SEND_STARTUP_NOTIFICATION = parse_bool(
            os.environ.get("SEND_STARTUP_NOTIFICATION"), False
        )
        self.STARTUP_NOTIFICATION_DETAILS = parse_bool(
            os.environ.get("STARTUP_NOTIFICATION_DETAILS"), False
        )
        self.LOG_MESSAGE_CONTENT = parse_bool(
            os.environ.get("LOG_MESSAGE_CONTENT"), False
        )
        self.FLOOD_WAIT_MAX_SECONDS = parse_int(
            os.environ.get("FLOOD_WAIT_MAX_SECONDS"), 0
        )
        self.config_path = str(Path(config_path).resolve()) if config_path else None

        # 群组配置列表
        self.groups: List[GroupConfig] = []

        # 用于快速查找的映射
        self.groups_by_source: Dict[str, GroupConfig] = {}
        self.all_source_ids: List[Union[str, int]] = []

        # 加载配置
        if config_path:
            if os.path.exists(config_path):
                self.load_from_file(config_path)
                logger.info(f"配置已从 {config_path} 加载")
            else:
                logger.warning(f"配置文件未找到: {config_path}")

    def load_from_file(self, config_path: str):
        """从 JSON 文件加载配置"""
        try:
            self.config_path = str(Path(config_path).resolve())
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # Session 名称（可选）
            if not self._session_name_from_env:
                self.SESSION_NAME = config_data.get("session_name", self.SESSION_NAME)

            config_data = self._normalize_config_data(config_data)

            # 加载群组配置
            groups_data = config_data.get("groups", [])
            errors = []
            for group_data in groups_data:
                try:
                    group_config = GroupConfig(group_data)
                    self.groups.append(group_config)
                except Exception as e:
                    group_id = group_data.get("id", "unknown")
                    errors.append(f"加载群组配置失败 {group_id}: {e}")

            if errors:
                for error in errors:
                    logger.error(error)
                raise ValueError("; ".join(errors))

            # 构建查找映射
            self._build_lookup_maps()

            # 确保 API_ID 是整数
            if self.API_ID and isinstance(self.API_ID, str):
                self.API_ID = int(self.API_ID)

            # 统计信息
            total_rules = sum(len(g.rules) for g in self.groups)
            enabled_groups = sum(1 for g in self.groups if g.enabled)
            enabled_rules = sum(
                sum(1 for r in g.rules if r.enabled) for g in self.groups if g.enabled
            )

            logger.info(f"API ID: {'已设置' if self.API_ID else '未设置'}")
            logger.info(f"API Hash: {'已设置' if self.API_HASH else '未设置'}")
            logger.info(f"配置文件路径: {self.config_path}")
            logger.info(f"群组配置数量: {len(self.groups)} (启用: {enabled_groups})")
            logger.info(f"转发规则总数: {total_rules} (启用: {enabled_rules})")
            logger.info(f"监听源群组数: {len(self.all_source_ids)}")

        except Exception as e:
            logger.error(f"加载配置失败: {e}", exc_info=True)
            raise ValueError(f"Failed to load configuration: {e}")

    def _normalize_config_data(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize supported config shapes into the groups/rules model."""
        normalized = dict(config_data)
        groups = list(normalized.get("groups", []))

        forwards = normalized.get("forwards", [])
        if forwards:
            if not isinstance(forwards, list):
                raise ValueError("forwards 必须是数组")
            groups.extend(self._groups_from_forwards(forwards))

        normalized["groups"] = groups
        return normalized

    def _groups_from_forwards(
        self, forwards: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert simplified forwards entries to group configs."""
        groups = []
        for idx, forward in enumerate(forwards, 1):
            if not isinstance(forward, dict):
                raise ValueError(f"forwards[{idx}] 必须是对象")

            source = forward.get("from", forward.get("source"))
            targets = forward.get("to", forward.get("targets"))
            if not source:
                raise ValueError(f"forwards[{idx}] 缺少 from")
            if not targets:
                raise ValueError(f"forwards[{idx}] 缺少 to")

            filters = forward.get("filters")
            if filters is None:
                filters = self._filters_from_simple_forward(forward)

            target_names = targets if isinstance(targets, list) else [targets]
            target_display = ", ".join(str(t) for t in target_names)
            rule = {
                "enabled": forward.get("rule_enabled", True),
                "targets": targets,
                "filters": filters,
            }

            for key in ("forward_mode", "silent", "dedupe", "delivery"):
                if key in forward:
                    rule[key] = forward[key]

            groups.append(
                {
                    "id": forward.get("id", f"forward_{idx}"),
                    "name": forward.get("name", f"{source} -> {target_display}"),
                    "enabled": forward.get("enabled", True),
                    "source": source,
                    "rules": [rule],
                }
            )

        return groups

    def _filters_from_simple_forward(self, forward: Dict[str, Any]) -> Dict[str, Any]:
        """Build filter config from common shorthand fields."""
        simple_rules = []

        if forward.get("keywords"):
            simple_rules.append(
                {
                    "type": "keyword",
                    "config": {
                        "words": forward["keywords"],
                        "match_case": forward.get("match_case", False),
                        "match_mode": forward.get("match_mode", "any"),
                    },
                }
            )

        if forward.get("regex"):
            simple_rules.append(
                {
                    "type": "regex",
                    "config": {
                        "pattern": forward["regex"],
                        "flags": forward.get("regex_flags", ""),
                        "description": forward.get("regex_description", ""),
                    },
                }
            )

        if forward.get("users"):
            simple_rules.append(
                {
                    "type": "user",
                    "config": {
                        "users": forward["users"],
                    },
                }
            )

        if forward.get("media"):
            media_types = forward["media"]
            simple_rules.append(
                {
                    "type": "media",
                    "config": {
                        "types": (
                            media_types
                            if isinstance(media_types, list)
                            else [media_types]
                        ),
                        "match_mode": "any",
                    },
                }
            )

        if not simple_rules:
            return {"mode": "all"}

        return {
            "mode": forward.get("mode", "include"),
            "rules": simple_rules,
        }

    def _build_lookup_maps(self):
        """构建快速查找映射"""
        self.groups_by_source.clear()
        source_ids_set = set()

        for group in self.groups:
            if not group.enabled:
                continue

            source_id = group.source_id
            if not source_id:
                continue

            # 添加到源ID集合
            source_ids_set.add(source_id)

            # 构建不同格式的键映射
            keys = self._generate_id_variants(source_id)
            for key in keys:
                self.groups_by_source[key] = group

        self.all_source_ids = list(source_ids_set)

        logger.debug(
            f"构建查找映射完成: {len(self.groups_by_source)} 个键映射到群组配置"
        )

    def _generate_id_variants(self, group_id: Union[str, int]) -> List[str]:
        """生成群组ID的所有可能变体"""
        variants = [str(group_id)]

        if isinstance(group_id, str):
            # 处理用户名格式
            if group_id.startswith("@"):
                variants.append(group_id[1:])
            elif not group_id.lstrip("-").isdigit():
                variants.append(f"@{group_id}")

        # 处理数字ID
        if isinstance(group_id, int) or (
            isinstance(group_id, str) and group_id.lstrip("-").isdigit()
        ):
            try:
                num_id = int(str(group_id).lstrip("-"))
                variants.extend(
                    [str(num_id), str(-num_id), f"-{num_id}", f"-100{num_id}"]
                )
            except ValueError:
                pass

        return list(set(variants))

    def get_group_config(
        self, source_id: Union[str, int], username: Optional[str] = None
    ) -> Optional[GroupConfig]:
        """获取特定源群组的配置"""
        variants = self._generate_id_variants(source_id)
        if username:
            variants.extend(self._generate_id_variants(username))
            variants.extend(self._generate_id_variants(f"@{username}"))

        for variant in variants:
            if variant in self.groups_by_source:
                return self.groups_by_source[variant]

        return None


# 默认配置文件路径
def get_default_config_path() -> str:
    """获取默认配置文件路径"""
    root_dir = Path(__file__).parent.parent
    return str(root_dir / "forward_rules.json")


# 支持通过环境变量自定义配置文件路径
def load_config(config_path: Optional[str] = None) -> ConfigLoader:
    """加载配置"""
    if config_path is None:
        config_path = os.environ.get("FORWARD_RULES_PATH", get_default_config_path())
    return ConfigLoader(config_path)
