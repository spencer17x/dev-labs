import json
from datetime import timedelta

from db_storage import connect, ensure_schema
from narrative_types import InfluencerHit, NarrativeAnalysis
from timezone_utils import beijing_now, format_beijing_time, parse_time_to_beijing


def _json_list(value) -> str:
    return json.dumps(value or [], ensure_ascii=False, sort_keys=True)


def _json_dict(value) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def ensure_narrative_storage():
    ensure_schema()


def _row_to_analysis(row) -> NarrativeAnalysis:
    hits_raw = json.loads(row["influencer_hits_json"] or "[]")
    hits = [
        InfluencerHit(
            account=str(item.get("account", "")),
            hit_type=str(item.get("hit_type", "")),
            strength=str(item.get("strength", "")),
            evidence_url=str(item.get("evidence_url", "")),
        )
        for item in hits_raw
        if isinstance(item, dict)
    ]
    return NarrativeAnalysis(
        provider=row["provider"],
        score=int(row["score"]),
        confidence=row["confidence"],
        tags=json.loads(row["tags_json"] or "[]"),
        summary=row["summary"],
        influencer_hits=hits,
        risk_flags=json.loads(row["risk_flags_json"] or "[]"),
        evidence_links=json.loads(row["evidence_links_json"] or "[]"),
        raw_result=json.loads(row["raw_result_json"] or "{}"),
    )


def save_analysis(chain: str, token_address: str, analysis: NarrativeAnalysis, ttl_hours: int):
    ensure_schema()
    now = beijing_now().replace(tzinfo=None)
    expires_at = now + timedelta(hours=ttl_hours)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO narrative_analysis (
                chain, token_address, provider, score, confidence, tags_json,
                summary, influencer_hits_json, risk_flags_json, evidence_links_json,
                raw_result_json, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chain, token_address, provider) DO UPDATE SET
                score=excluded.score,
                confidence=excluded.confidence,
                tags_json=excluded.tags_json,
                summary=excluded.summary,
                influencer_hits_json=excluded.influencer_hits_json,
                risk_flags_json=excluded.risk_flags_json,
                evidence_links_json=excluded.evidence_links_json,
                raw_result_json=excluded.raw_result_json,
                created_at=excluded.created_at,
                expires_at=excluded.expires_at
            """,
            (
                chain,
                token_address,
                analysis.provider,
                int(analysis.score),
                analysis.confidence,
                _json_list(analysis.tags),
                analysis.summary,
                _json_list([hit.__dict__ for hit in analysis.influencer_hits]),
                _json_list(analysis.risk_flags),
                _json_list(analysis.evidence_links),
                _json_dict(analysis.raw_result),
                format_beijing_time(),
                expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )


def load_cached_analysis(chain: str, token_address: str, provider: str):
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM narrative_analysis
            WHERE chain = ? AND token_address = ? AND provider = ?
            """,
            (chain, token_address, provider),
        ).fetchone()
    if not row:
        return None
    try:
        expires_at = parse_time_to_beijing(row["expires_at"]).replace(tzinfo=None)
    except Exception:
        return None
    if expires_at <= beijing_now().replace(tzinfo=None):
        return None
    return _row_to_analysis(row)
