from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Optional

from narrative_types import EvidenceItem, NarrativeLLMResult

DEFAULT_ACCOUNT_TIERS = {
    "elonmusk": 0,
    "cz_binance": 0,
    "heyibinance": 0,
    "binance": 1,
    "coinbase": 1,
    "solana": 1,
    "base": 1,
}

SOURCE_POINTS = {
    0: {"author": 30, "reply": 22, "quote": 24, "mentioned_by_others": 0},
    1: {"author": 20, "reply": 14, "quote": 16, "mentioned_by_others": 0},
    2: {"author": 12, "reply": 8, "quote": 10, "mentioned_by_others": 0},
}

RISK_DEDUCTIONS = {
    "ticker_ambiguity": 12,
    "mostly_shill_posts": 15,
    "claimed_influencer_without_direct_evidence": 18,
    "suspicious_lookalike_accounts": 20,
    "no_contract_address_evidence": 20,
}


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def _engagement(item: EvidenceItem) -> int:
    return (
        item.like_count
        + item.repost_count * 2
        + item.quote_count * 2
        + item.reply_count
    )


def _normalize_handle(value: str) -> str:
    return str(value).strip().lower().lstrip("@")


def _normalize_now(now: Optional[datetime]) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _parse_created_at(value: str) -> Optional[datetime]:
    created_at = str(value).strip()
    if not created_at:
        return None
    if created_at.endswith("Z"):
        created_at = f"{created_at[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(created_at)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def token_link_score(evidence: Iterable[EvidenceItem]) -> int:
    items = list(evidence)
    if any(item.exact_token_match for item in items):
        return 20
    if any(item.symbol_or_name_match for item in items):
        return 8
    return 0


def source_score(
    llm_result: NarrativeLLMResult,
    account_tiers: Optional[Mapping[str, int]] = None,
) -> int:
    tier_source = DEFAULT_ACCOUNT_TIERS if account_tiers is None else account_tiers
    tiers = {_normalize_handle(account): tier for account, tier in tier_source.items()}
    best = 0
    for hit in llm_result.influencer_hits:
        tier = tiers.get(_normalize_handle(hit.account))
        if tier is None:
            continue
        hit_type = str(hit.hit_type).strip().lower()
        best = max(best, SOURCE_POINTS.get(tier, {}).get(hit_type, 0))
    return best


def engagement_score(evidence: Iterable[EvidenceItem]) -> int:
    total = sum(_engagement(item) for item in evidence)
    if total >= 1000:
        return 15
    if total >= 250:
        return 12
    if total >= 50:
        return 8
    if total > 0:
        return 4
    return 0


def volume_score(evidence: Iterable[EvidenceItem]) -> int:
    authors = set()
    for item in evidence:
        author_id = str(item.author_id).strip()
        if author_id:
            authors.add(author_id)
            continue
        author_handle = _normalize_handle(item.author_handle)
        if author_handle:
            authors.add(author_handle)
    count = len(authors)
    if count >= 20:
        return 15
    if count >= 10:
        return 12
    if count >= 5:
        return 8
    if count >= 2:
        return 4
    return 0


def narrative_clarity_score(llm_result: NarrativeLLMResult) -> int:
    if not llm_result.narrative_tags or not llm_result.summary:
        return 0
    if llm_result.confidence == "high":
        return 10
    if llm_result.confidence == "medium":
        return 6
    return 2


def freshness_score(
    evidence: Iterable[EvidenceItem], now: Optional[datetime] = None
) -> int:
    current = _normalize_now(now)
    best = 0
    for item in evidence:
        created_at = _parse_created_at(item.created_at)
        if created_at is None:
            continue
        age = current - created_at
        if age < timedelta(0):
            continue
        if age <= timedelta(hours=6):
            best = max(best, 10)
        elif age <= timedelta(hours=24):
            best = max(best, 6)
        elif age <= timedelta(hours=72):
            best = max(best, 3)
    return best


def risk_deduction(
    llm_result: NarrativeLLMResult, evidence: Iterable[EvidenceItem]
) -> int:
    risk_flags = {
        str(flag).strip().lower() for flag in llm_result.risk_flags if str(flag).strip()
    }
    deduction = sum(RISK_DEDUCTIONS.get(flag, 0) for flag in risk_flags)
    if (
        "no_contract_address_evidence" not in risk_flags
        and token_link_score(evidence) == 0
    ):
        deduction += RISK_DEDUCTIONS["no_contract_address_evidence"]
    return deduction


def compute_narrative_score(
    llm_result: NarrativeLLMResult,
    evidence: Iterable[EvidenceItem],
    account_tiers: Optional[Mapping[str, int]] = None,
    now: Optional[datetime] = None,
) -> int:
    items = list(evidence)
    total = (
        token_link_score(items)
        + source_score(llm_result, account_tiers)
        + engagement_score(items)
        + volume_score(items)
        + narrative_clarity_score(llm_result)
        + freshness_score(items, now=now)
        - risk_deduction(llm_result, items)
    )
    return _clamp(total)
