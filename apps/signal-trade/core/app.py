"""Application wiring for Signal Trade."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, List

from core.enricher import SignalContextEnricher
from models.notification import NotificationPayload
from models.signal_event import SignalEvent
from models.strategy import Strategy, StrategyCondition, StrategyConditionGroup
from notifications.stdout_notifier import StdoutNotifier
from notifications.webhook_notifier import WebhookNotifier
from core.strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)


class SignalTradeApp:
    """Small runtime that evaluates events and dispatches notifications."""

    def __init__(
        self,
        strategies: Iterable[Strategy],
        webhook_url: str = '',
        enricher: SignalContextEnricher | None = None,
    ) -> None:
        self._engine = StrategyEngine(strategies)
        self._enricher = enricher or SignalContextEnricher()
        self._stdout_notifier = StdoutNotifier()
        self._webhook_notifier = WebhookNotifier(webhook_url=webhook_url)

    async def process_event(self, event: SignalEvent) -> None:
        try:
            context = await self._enricher.enrich(event)
        except Exception as exc:
            logger.warning('failed to enrich event %s: %s', event.id, exc)
            context = {
                'token': {
                    'chain': event.chain,
                    'address': event.token.address,
                    'symbol': event.token.symbol,
                    'name': event.token.name,
                },
                'dexscreener': {
                    'source': event.subtype,
                    'paid': event.subtype == 'token_profiles_latest',
                    'timestamp': event.timestamp,
                },
                'xxyy': {},
                'twitter': {},
            }
        payloads = self._engine.evaluate(event, context)
        for payload in payloads:
            await self._dispatch(payload)

    async def _dispatch(self, payload: NotificationPayload) -> None:
        for channel in payload.channels:
            if channel == 'stdout':
                await self._stdout_notifier.send(payload)
            elif channel == 'webhook':
                await self._webhook_notifier.send(payload)


def load_strategies(path: str | Path) -> List[Strategy]:
    raw_rules = json.loads(Path(path).read_text())
    items = raw_rules.get('strategies', raw_rules) if isinstance(raw_rules, dict) else raw_rules
    strategies: List[Strategy] = []
    for item in items:
        entry_conditions = _parse_conditions(
            item.get('entry_conditions', item.get('conditions', []))
        )
        reject_conditions = _parse_conditions(item.get('reject_conditions', []))
        entry_rule = _parse_condition_group(item.get('entry_rule'))
        reject_rule = _parse_condition_group(item.get('reject_rule'))
        strategies.append(
            Strategy(
                id=item['id'],
                enabled=item.get('enabled', True),
                chains=list(item.get('chains', [])),
                source=item.get('source'),
                subtypes=list(item.get('subtypes', [])),
                entry_logic=item.get('entry_logic', 'all'),
                entry_conditions=entry_conditions,
                entry_rule=entry_rule,
                reject_logic=item.get('reject_logic', 'any'),
                reject_conditions=reject_conditions,
                reject_rule=reject_rule,
                notify=list(item.get('notify', item.get('action', {}).get('channels', ['stdout']))),
                metadata=dict(item.get('metadata', {})),
            )
        )
    return strategies


def _parse_conditions(items: list[dict]) -> List[StrategyCondition]:
    return [
        StrategyCondition(
            field=condition['field'],
            op=condition['op'],
            value=condition.get('value'),
        )
        for condition in items
    ]


def _parse_condition_group(item: dict | None) -> StrategyConditionGroup | None:
    if not isinstance(item, dict):
        return None
    raw_conditions = item.get('conditions', [])
    conditions: List[StrategyCondition | StrategyConditionGroup] = []
    for condition in raw_conditions:
        if not isinstance(condition, dict):
            continue
        if 'conditions' in condition:
            nested_group = _parse_condition_group(condition)
            if nested_group is not None:
                conditions.append(nested_group)
            continue
        conditions.append(
            StrategyCondition(
                field=condition['field'],
                op=condition['op'],
                value=condition.get('value'),
            )
        )
    return StrategyConditionGroup(
        logic=item.get('logic', 'all'),
        conditions=conditions,
    )
