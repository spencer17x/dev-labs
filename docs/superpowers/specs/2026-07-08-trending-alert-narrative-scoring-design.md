# Trending Alert Narrative Scoring Design

## Context

`apps/trending-alert-bot` currently monitors XXYY trending contracts, selects trend/anomaly candidates, enriches them with KOL holder data, and sends Telegram notifications. It does not fetch or analyze X posts. Notifications already include token metadata, project links, KOL holder status, and an X search URL.

The goal is to add long-running narrative enrichment for new trend/anomaly notifications without making the bot depend on browser sessions, personal X Premium login state, or Hermes-style interactive OAuth flows.

## Goals

- Add a narrative summary and score to initial trend/anomaly Telegram notifications.
- Use a hybrid approach: deterministic rules for evidence extraction and scoring, LLM for semantic narrative classification and concise summaries.
- Keep the existing notification flow resilient: narrative failure must not block trend/anomaly notifications.
- Control cost and rate limits by analyzing only candidates that are about to be notified.
- Cache analysis results per `chain + token_address` so repeated scans do not repeat expensive calls.

## Non-Goals

- Do not use Hermes as a production dependency.
- Do not depend on browser cookies, scraped Grok web sessions, or interactive login state.
- Do not use narrative score to suppress notifications in the first version.
- Do not build historical backtesting or full X ingestion in the first version.

## Data Sources

Primary production provider:

- xAI API with `x_search`, once an `XAI_API_KEY` is available.

Optional future providers:

- X API recent search plus a separate LLM summarizer.
- Third-party social/narrative APIs, if coverage and pricing are acceptable.
- Manual/mock provider for local development and tests.

The provider interface should hide the data source from the monitoring flow.

## Trigger Point

Narrative analysis runs only for a candidate contract immediately before sending an initial trend/anomaly notification.

It should not run for:

- Every contract on every scan.
- Contracts loaded during silent initialization.
- Multiplier notifications in the first version.
- Contracts that already have a real Telegram message id.

## Input Contract Context

The narrative provider receives:

- `chain`
- `token_address`
- `pair_address`
- `symbol`
- `name`
- `links`
- `dex_name`
- `launch_from`
- `market_cap_usd`
- `volume_24h`
- KOL holder summary, if already fetched

Search query priority:

1. Exact token address.
2. Official X handle or X URL from `links.x`.
3. Project website domain.
4. Symbol and name, treated as weaker evidence because ticker collisions are common.

## Evidence Preprocessing

Rules should normalize and score evidence before the LLM sees it:

- Prefer posts with exact token address matches.
- Prefer posts from known accounts by stable user id when available.
- Deduplicate repeated shill templates.
- Down-rank pure reposts and low-signal replies.
- Flag ticker/name-only matches as ambiguous.
- Flag posts that mention influential people without being authored by them.
- Keep a small evidence set, typically 10 to 30 posts, to control token usage.

## LLM Responsibility

The LLM should read the filtered evidence and return structured JSON only.

Expected fields:

```json
{
  "narrative_tags": ["meme", "binance_related"],
  "summary": "Short evidence-based narrative summary.",
  "confidence": "low|medium|high",
  "influencer_hits": [
    {
      "account": "cz_binance",
      "hit_type": "author|reply|quote|mentioned_by_others",
      "strength": "weak|medium|strong",
      "evidence_url": "https://x.com/..."
    }
  ],
  "risk_flags": ["ticker_ambiguity", "mostly_shill_posts"],
  "evidence_links": ["https://x.com/..."]
}
```

The LLM must not invent links, account identities, or claims. If evidence is weak, it must return low confidence.

## Rule-Based Final Score

The final `narrative_score` is computed by code, not by the LLM.

Base score components:

- Token link score, 0 to 20: exact contract address evidence is strongest; ticker/name-only evidence is weak.
- Source score, 0 to 30: known influential accounts carry the most weight.
- Engagement score, 0 to 15: likes, reposts, replies, and quote quality.
- Volume score, 0 to 15: independent accounts discussing the token in a short window.
- Narrative clarity score, 0 to 10: clear tag and summary with medium/high confidence.
- Freshness score, 0 to 10: recent posts count more than stale posts.

Risk deductions:

- Ticker ambiguity.
- Mostly copied shill posts.
- Claimed Elon/CZ/He Yi relation without direct author/reply/quote evidence.
- Suspicious lookalike accounts.
- No contract-address-level evidence.

The score is clamped to `0..100`.

## Influential Account Tiers

Known accounts should be config-driven and should prefer stable account ids over handles.

Initial tier model:

- Tier 0: Elon Musk, CZ, He Yi.
- Tier 1: Binance, Coinbase, Solana, Base, major ecosystem or exchange accounts.
- Tier 2: approved crypto KOL list maintained by the operator.
- Tier 3: ordinary accounts, contributing only volume and engagement.

Scoring examples:

- Tier 0 author with exact contract evidence: high source score.
- Tier 0 reply or quote with clear token relation: medium/high source score.
- Third-party post saying "CZ will buy this": no Tier 0 source credit and likely risk flag.
- Screenshot-only claims: risk flag unless supported by a real source link.

## Storage

Add SQLite persistence for narrative analysis.

Suggested table:

```sql
CREATE TABLE narrative_analysis (
  chain TEXT NOT NULL,
  token_address TEXT NOT NULL,
  provider TEXT NOT NULL,
  score INTEGER NOT NULL,
  confidence TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  summary TEXT NOT NULL,
  influencer_hits_json TEXT NOT NULL,
  risk_flags_json TEXT NOT NULL,
  evidence_links_json TEXT NOT NULL,
  raw_result_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  PRIMARY KEY (chain, token_address, provider)
);
```

Default cache TTL should be configurable, initially 6 to 24 hours.

## Configuration

Add environment-driven config:

- `NARRATIVE_ENABLED=false`
- `NARRATIVE_PROVIDER=xai`
- `NARRATIVE_CACHE_TTL_HOURS=12`
- `NARRATIVE_MIN_EVIDENCE=3`
- `XAI_API_KEY=...`
- `NARRATIVE_TIMEOUT_SECONDS=20`

The default must be disabled so existing deployments keep working without new secrets.

## Telegram Output

Add a compact section to initial trend/anomaly notifications only:

```text
Narrative: Binance/CZ + Meme
Score: 72/100
Evidence: CA matched in 8 posts; 2 mid-tier accounts; CZ only indirect
Confidence: medium
Risk: mostly shill posts, no direct CZ post
```

If analysis fails or is disabled, omit the section.

## Failure Handling

- Provider timeout returns no narrative result.
- Invalid JSON from LLM is treated as provider failure.
- Provider failures are logged with chain, symbol, and token address.
- The original trend/anomaly notification still sends.
- Failed analyses may be retried on a future candidate event, but not in a tight loop.

## Testing

Unit tests:

- Evidence preprocessing prioritizes exact contract matches.
- Influential-account scoring distinguishes direct authorship from third-party mentions.
- Risk deductions lower the final score and clamp at zero.
- Cached analysis avoids provider calls.
- Provider failure does not block notification formatting.
- Disabled config omits narrative output.

Integration-style tests:

- Mock provider returns narrative JSON and notification includes the compact section.
- Invalid provider JSON logs failure and sends notification without narrative.

## Rollout

Phase 1:

- Add provider abstraction, mock/manual provider, scoring rules, SQLite cache, and notification formatting.
- Narrative score is display-only.

Phase 2:

- Add xAI API provider with `x_search`.
- Add configurable influential account tiers.

Phase 3:

- Evaluate notification history and decide whether score should affect priority or filtering.
