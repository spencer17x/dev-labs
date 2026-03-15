"""Notification models for Signal Trade."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .signal_event import SignalEvent
from .strategy import Strategy


@dataclass
class NotificationPayload:
    """Notification generated after a strategy matches an event."""

    strategy: Strategy
    event: SignalEvent
    channels: List[str]
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
