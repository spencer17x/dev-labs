"""Strategy models for Signal Trade."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class StrategyCondition:
    """One field comparison inside a strategy rule."""

    field: str
    op: str
    value: Any = None


@dataclass
class StrategyConditionGroup:
    """A recursive condition group with all/any logic."""

    logic: str = 'all'
    conditions: List[Union['StrategyConditionGroup', StrategyCondition]] = field(
        default_factory=list
    )


@dataclass
class Strategy:
    """Minimal rule model for matching normalized events."""

    id: str
    enabled: bool = True
    chains: List[str] = field(default_factory=list)
    source: Optional[str] = None
    subtypes: List[str] = field(default_factory=list)
    entry_logic: str = 'all'
    entry_conditions: List[StrategyCondition] = field(default_factory=list)
    entry_rule: Optional[StrategyConditionGroup] = None
    reject_logic: str = 'any'
    reject_conditions: List[StrategyCondition] = field(default_factory=list)
    reject_rule: Optional[StrategyConditionGroup] = None
    notify: List[str] = field(default_factory=lambda: ['stdout'])
    metadata: Dict[str, Any] = field(default_factory=dict)
