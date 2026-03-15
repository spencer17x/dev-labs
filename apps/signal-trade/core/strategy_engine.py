"""Minimal strategy matching for Signal Trade."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from models.notification import NotificationPayload
from models.signal_event import SignalEvent
from models.strategy import Strategy, StrategyCondition, StrategyConditionGroup


class StrategyEngine:
    """Evaluate normalized events against configured strategies."""

    def __init__(self, strategies: Iterable[Strategy]) -> None:
        self._strategies = [strategy for strategy in strategies if strategy.enabled]

    def evaluate(self, event: SignalEvent, context: Dict[str, Any]) -> List[NotificationPayload]:
        matches: List[NotificationPayload] = []
        for strategy in self._strategies:
            if not self._matches_strategy(strategy, event, context):
                continue
            matches.append(
                NotificationPayload(
                    strategy=strategy,
                    event=event,
                    channels=strategy.notify or ['stdout'],
                    message=_build_message(strategy, event, context),
                    context=context,
                )
            )
        return matches

    def _matches_strategy(
        self,
        strategy: Strategy,
        event: SignalEvent,
        context: Dict[str, Any],
    ) -> bool:
        if strategy.source and strategy.source != f'{event.source}.{event.subtype}':
            return False
        if strategy.chains and (event.chain or '') not in strategy.chains:
            return False
        if strategy.subtypes and event.subtype not in strategy.subtypes:
            return False

        if strategy.entry_rule is not None:
            if not self._matches_group(strategy.entry_rule, context):
                return False
        else:
            entry_conditions = strategy.entry_conditions
            if entry_conditions:
                entry_matches = [
                    self._matches_condition(condition, context) for condition in entry_conditions
                ]
                if strategy.entry_logic == 'any':
                    if not any(entry_matches):
                        return False
                elif not all(entry_matches):
                    return False

        if strategy.reject_rule is not None:
            if self._matches_group(strategy.reject_rule, context):
                return False
        else:
            reject_conditions = strategy.reject_conditions
            if reject_conditions:
                reject_matches = [
                    self._matches_condition(condition, context) for condition in reject_conditions
                ]
                if strategy.reject_logic == 'all':
                    if all(reject_matches):
                        return False
                elif any(reject_matches):
                    return False

        return True

    def _matches_group(self, group: StrategyConditionGroup, context: Dict[str, Any]) -> bool:
        if not group.conditions:
            return True
        matches = [
            self._matches_group(condition, context)
            if isinstance(condition, StrategyConditionGroup)
            else self._matches_condition(condition, context)
            for condition in group.conditions
        ]
        if group.logic == 'any':
            return any(matches)
        return all(matches)

    def _matches_condition(self, condition: StrategyCondition, context: Dict[str, Any]) -> bool:
        actual = _resolve_field(context, condition.field)
        op = condition.op
        expected = condition.value

        if op == 'exists':
            return actual not in (None, '', [], {})
        if op in ('==', 'eq'):
            return actual == expected
        if op in ('!=', 'ne'):
            return actual != expected
        if op == 'in':
            return actual in (expected or [])
        if op == 'contains':
            return actual is not None and str(expected).lower() in str(actual).lower()
        if op in ('contains_any', 'intersects'):
            return _contains_any(actual, expected)
        if op == '>=':
            return _coerce_number(actual) >= _coerce_number(expected)
        if op == '<=':
            return _coerce_number(actual) <= _coerce_number(expected)
        if op == '>':
            return _coerce_number(actual) > _coerce_number(expected)
        if op == '<':
            return _coerce_number(actual) < _coerce_number(expected)
        raise ValueError(f'unsupported operator: {op}')


def _resolve_field(context: Dict[str, Any], field: str) -> Any:
    current: Any = context
    for part in field.split('.'):
        if hasattr(current, part):
            current = getattr(current, part)
            continue
        if isinstance(current, dict):
            current = current.get(part)
            continue
        return None
    return current


def _coerce_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float('-inf')


def _contains_any(actual: Any, expected: Any) -> bool:
    if not isinstance(actual, list) or not isinstance(expected, list):
        return False
    actual_values = {
        str(item).strip().lower()
        for item in actual
        if item not in (None, '')
    }
    expected_values = {
        str(item).strip().lower()
        for item in expected
        if item not in (None, '')
    }
    if not actual_values or not expected_values:
        return False
    return bool(actual_values & expected_values)


def _build_message(strategy: Strategy, event: SignalEvent, context: Dict[str, Any]) -> str:
    token_ref = event.token.symbol or event.token.address or 'unknown-token'
    market_cap = _resolve_field(context, 'xxyy.market_cap')
    holder_count = _resolve_field(context, 'xxyy.holder_count')
    community_count = _resolve_field(context, 'twitter.community_count')
    return (
        f'[{strategy.id}] '
        f'source={event.source}.{event.subtype} '
        f'token={token_ref} '
        f'market_cap={market_cap} holders={holder_count} twitter_community={community_count}'
    )
