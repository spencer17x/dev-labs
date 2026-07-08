import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List


def _as_list(value) -> List:
    return value if isinstance(value, list) else []


@dataclass
class EvidenceItem:
    url: str
    author_handle: str = ""
    author_id: str = ""
    text: str = ""
    created_at: str = ""
    like_count: int = 0
    repost_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    exact_token_match: bool = False
    symbol_or_name_match: bool = False


@dataclass
class InfluencerHit:
    account: str
    hit_type: str
    strength: str
    evidence_url: str = ""


@dataclass
class NarrativeLLMResult:
    narrative_tags: List[str] = field(default_factory=list)
    summary: str = ""
    confidence: str = "low"
    influencer_hits: List[InfluencerHit] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    evidence_links: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict) -> "NarrativeLLMResult":
        hits = [
            InfluencerHit(
                account=str(item.get("account", "")),
                hit_type=str(item.get("hit_type", "")),
                strength=str(item.get("strength", "")),
                evidence_url=str(item.get("evidence_url", "")),
            )
            for item in _as_list(data.get("influencer_hits"))
            if isinstance(item, dict)
        ]
        confidence = str(data.get("confidence", "low")).lower()
        if confidence not in {"low", "medium", "high"}:
            confidence = "low"
        return cls(
            narrative_tags=[
                str(item) for item in _as_list(data.get("narrative_tags")) if str(item)
            ],
            summary=str(data.get("summary", "")),
            confidence=confidence,
            influencer_hits=hits,
            risk_flags=[
                str(item) for item in _as_list(data.get("risk_flags")) if str(item)
            ],
            evidence_links=[
                str(item) for item in _as_list(data.get("evidence_links")) if str(item)
            ],
        )

    @classmethod
    def from_json(cls, value: str) -> "NarrativeLLMResult":
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("narrative result must be a JSON object")
        return cls.from_dict(parsed)


@dataclass
class NarrativeInput:
    chain: str
    token_address: str
    pair_address: str = ""
    symbol: str = ""
    name: str = ""
    links: Dict = field(default_factory=dict)
    dex_name: str = ""
    launch_from: str = ""
    market_cap_usd: float = 0.0
    volume_24h: float = 0.0
    kol_summary: List[Dict] = field(default_factory=list)


@dataclass
class NarrativeAnalysis:
    provider: str
    score: int
    confidence: str
    tags: List[str]
    summary: str
    influencer_hits: List[InfluencerHit] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    evidence_links: List[str] = field(default_factory=list)
    raw_result: Dict = field(default_factory=dict)

    def to_display_dict(self) -> Dict:
        return {
            "score": self.score,
            "confidence": self.confidence,
            "tags": self.tags,
            "summary": self.summary,
            "influencer_hits": [asdict(hit) for hit in self.influencer_hits],
            "risk_flags": self.risk_flags,
            "evidence_links": self.evidence_links,
        }
