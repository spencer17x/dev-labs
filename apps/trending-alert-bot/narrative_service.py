from typing import List, Optional

from config import (
    NARRATIVE_CACHE_TTL_HOURS,
    NARRATIVE_ENABLED,
    NARRATIVE_MIN_EVIDENCE,
    NARRATIVE_PROVIDER,
    NARRATIVE_TIMEOUT_SECONDS,
    XAI_API_KEY,
)
from narrative_provider import NarrativeProviderError, build_provider
from narrative_scoring import compute_narrative_score
from narrative_storage import load_cached_analysis, save_analysis
from narrative_types import NarrativeAnalysis, NarrativeInput

NARRATIVE_EVIDENCE_POLICY_VERSION = 1


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _get_provider():
    return build_provider(NARRATIVE_PROVIDER, XAI_API_KEY, NARRATIVE_TIMEOUT_SECONDS)


def _cache_meets_evidence_policy(cached: NarrativeAnalysis) -> bool:
    raw_result = cached.raw_result
    if not isinstance(raw_result, dict):
        return False
    policy_version = raw_result.get("evidence_policy_version")
    evidence_count = raw_result.get("evidence_count")
    return (
        type(policy_version) is int
        and policy_version == NARRATIVE_EVIDENCE_POLICY_VERSION
        and type(evidence_count) is int
        and evidence_count >= NARRATIVE_MIN_EVIDENCE
    )


def build_narrative_input(
    contract: dict, chain: str, kol_holders: List[dict]
) -> NarrativeInput:
    return NarrativeInput(
        chain=chain,
        token_address=str(contract.get("tokenAddress") or ""),
        pair_address=str(contract.get("pairAddress") or ""),
        symbol=str(contract.get("symbol") or ""),
        name=str(contract.get("name") or ""),
        links=contract.get("links") if isinstance(contract.get("links"), dict) else {},
        dex_name=str(contract.get("dexName") or ""),
        launch_from=str(contract.get("launchFrom") or ""),
        market_cap_usd=_safe_float(contract.get("marketCapUSD")),
        volume_24h=_safe_float(contract.get("volume")),
        kol_summary=kol_holders or [],
    )


def analyze_contract_narrative(
    contract: dict, chain: str, kol_holders: List[dict]
) -> Optional[NarrativeAnalysis]:
    if not NARRATIVE_ENABLED:
        return None

    token_address = str(contract.get("tokenAddress") or "")
    if not token_address:
        return None

    # Cache lookup happens before provider construction; save uses provider.provider_name.
    provider_key = NARRATIVE_PROVIDER
    try:
        cached = load_cached_analysis(chain, token_address, provider_key)
        if cached and _cache_meets_evidence_policy(cached):
            return cached
    except Exception as e:
        print(
            f"⚠️ [{chain.upper()}] narrative cache load failed: "
            f"{contract.get('symbol', 'N/A')} | {token_address} | {e}"
        )

    narrative_input = build_narrative_input(contract, chain, kol_holders)
    try:
        provider = _get_provider()
        llm_result, evidence = provider.analyze(narrative_input)
        evidence_items = list(evidence or [])
        if len(evidence_items) < NARRATIVE_MIN_EVIDENCE:
            print(
                f"⚠️ [{chain.upper()}] narrative evidence below minimum: "
                f"{contract.get('symbol', 'N/A')} | {token_address} | "
                f"{len(evidence_items)}/{NARRATIVE_MIN_EVIDENCE}"
            )
            return None
        score = compute_narrative_score(llm_result, evidence_items)
        analysis = NarrativeAnalysis(
            provider=provider.provider_name,
            score=score,
            confidence=llm_result.confidence,
            tags=llm_result.narrative_tags,
            summary=llm_result.summary,
            influencer_hits=llm_result.influencer_hits,
            risk_flags=llm_result.risk_flags,
            evidence_links=llm_result.evidence_links,
            raw_result={
                "llm_result": llm_result.to_json(),
                "evidence_count": len(evidence_items),
                "evidence_policy_version": NARRATIVE_EVIDENCE_POLICY_VERSION,
            },
        )
    except (NarrativeProviderError, ValueError, TypeError) as e:
        print(
            f"⚠️ [{chain.upper()}] narrative analysis failed: "
            f"{contract.get('symbol', 'N/A')} | {token_address} | {e}"
        )
        return None

    try:
        save_analysis(chain, token_address, analysis, NARRATIVE_CACHE_TTL_HOURS)
    except Exception as e:
        print(
            f"⚠️ [{chain.upper()}] narrative cache save failed: "
            f"{contract.get('symbol', 'N/A')} | {token_address} | {e}"
        )
    return analysis
