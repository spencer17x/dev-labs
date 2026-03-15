"""Shared event models for signal collectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SignalToken:
    """Normalized token identity from an upstream source."""

    symbol: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None


@dataclass
class SignalAuthor:
    """Normalized author identity from an upstream source."""

    id: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None


@dataclass
class SignalEvent:
    """Normalized event exchanged inside Signal Trade."""

    id: str
    source: str
    subtype: str
    timestamp: int
    chain: Optional[str] = None
    token: SignalToken = field(default_factory=SignalToken)
    author: Optional[SignalAuthor] = None
    text: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for serialization or transport."""

        return asdict(self)
