# Trending Alert Narrative Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add long-running, display-only narrative summaries and scores to `trending-alert-bot` trend/anomaly notifications.

**Architecture:** Add a small narrative subsystem beside the existing bot modules. `monitor_flow.py` asks a `narrative_service` for enrichment only after a candidate is known to be sendable; the service checks config, reads/writes SQLite cache, calls a provider, computes a deterministic score, and returns a compact result for `notifier.py` to render. Provider behavior is abstracted so production can use xAI `x_search`, while tests use deterministic fake providers.

**Tech Stack:** Python 3.11, `unittest`, SQLite, existing `curl_cffi` dependency, xAI Responses API with `x_search` for the production provider.

---

## File Structure

Create:

- `apps/trending-alert-bot/narrative_types.py`
  - Dataclasses and JSON helpers for narrative input, LLM output, evidence, scoring, and final analysis.
- `apps/trending-alert-bot/narrative_scoring.py`
  - Deterministic scoring rules, risk deductions, and evidence helpers.
- `apps/trending-alert-bot/narrative_storage.py`
  - SQLite cache access for `narrative_analysis`.
- `apps/trending-alert-bot/narrative_provider.py`
  - Provider interface, fake/manual provider, and xAI provider.
- `apps/trending-alert-bot/narrative_service.py`
  - Orchestration: disabled config, cache, provider call, scoring, failure fallback.
- `apps/trending-alert-bot/tests/test_narrative_scoring.py`
  - Unit tests for scoring and evidence interpretation.
- `apps/trending-alert-bot/tests/test_narrative_storage.py`
  - Unit tests for schema and cache TTL behavior.
- `apps/trending-alert-bot/tests/test_narrative_service.py`
  - Unit tests for provider orchestration and failure fallback.

Modify:

- `apps/trending-alert-bot/bot_app.py`
  - Add runtime defaults and environment injection for narrative config.
- `apps/trending-alert-bot/config.py`
  - Parse narrative environment variables.
- `apps/trending-alert-bot/db_storage.py`
  - Create the narrative cache table in `ensure_schema()`.
- `apps/trending-alert-bot/notifier.py`
  - Render the optional compact narrative section.
- `apps/trending-alert-bot/monitor_flow.py`
  - Request narrative enrichment immediately before initial notifications.
- `apps/trending-alert-bot/.env.example`
  - Document new environment variables.
- `apps/trending-alert-bot/README.md`
  - Document the feature, disabled default, and production provider.
- Existing tests:
  - `apps/trending-alert-bot/tests/test_bot_app_config.py`
  - `apps/trending-alert-bot/tests/test_review_regressions.py`

## Task 1: Narrative Runtime Config

**Files:**
- Modify: `apps/trending-alert-bot/bot_app.py`
- Modify: `apps/trending-alert-bot/config.py`
- Test: `apps/trending-alert-bot/tests/test_bot_app_config.py`
- Test: `apps/trending-alert-bot/tests/test_review_regressions.py`

- [ ] **Step 1: Write failing tests for runtime defaults**

Add this to `BotAppConfigTests` in `apps/trending-alert-bot/tests/test_bot_app_config.py`:

```python
    def test_runtime_config_sets_narrative_defaults(self):
        with mock.patch.dict(os.environ, {"BSC_TELEGRAM_BOT_TOKEN": "123:test"}, clear=True):
            cfg = load_runtime_config("bsc")

        self.assertFalse(cfg.narrative_enabled)
        self.assertEqual(cfg.narrative_provider, "xai")
        self.assertEqual(cfg.narrative_cache_ttl_hours, 12)
        self.assertEqual(cfg.narrative_min_evidence, 3)
        self.assertEqual(cfg.narrative_timeout_seconds, 20)
        self.assertEqual(cfg.xai_api_key, "")
```

Add this import and test to `apps/trending-alert-bot/tests/test_review_regressions.py`:

```python
    def test_narrative_config_defaults_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, _, _, _ = load_runtime_modules(tmp)

            self.assertFalse(config.NARRATIVE_ENABLED)
            self.assertEqual(config.NARRATIVE_PROVIDER, "xai")
            self.assertEqual(config.NARRATIVE_CACHE_TTL_HOURS, 12)
            self.assertEqual(config.NARRATIVE_MIN_EVIDENCE, 3)
            self.assertEqual(config.NARRATIVE_TIMEOUT_SECONDS, 20)
            self.assertEqual(config.XAI_API_KEY, "")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest \
  tests.test_bot_app_config.BotAppConfigTests.test_runtime_config_sets_narrative_defaults \
  tests.test_review_regressions.ReviewRegressionTests.test_narrative_config_defaults_disabled
```

Expected: FAIL because `BotRuntimeConfig` and `config` do not expose narrative fields.

- [ ] **Step 3: Add runtime config fields in `bot_app.py`**

Modify `apps/trending-alert-bot/bot_app.py`:

```python
NARRATIVE_ENABLED = False
NARRATIVE_PROVIDER = "xai"
NARRATIVE_CACHE_TTL_HOURS = 12
NARRATIVE_MIN_EVIDENCE = 3
NARRATIVE_TIMEOUT_SECONDS = 20
```

Extend `BotRuntimeConfig`:

```python
    narrative_enabled: bool = NARRATIVE_ENABLED
    narrative_provider: str = NARRATIVE_PROVIDER
    narrative_cache_ttl_hours: int = NARRATIVE_CACHE_TTL_HOURS
    narrative_min_evidence: int = NARRATIVE_MIN_EVIDENCE
    narrative_timeout_seconds: int = NARRATIVE_TIMEOUT_SECONDS
    xai_api_key: str = ""
```

Extend `load_runtime_config()` return:

```python
        narrative_enabled=NARRATIVE_ENABLED,
        narrative_provider=NARRATIVE_PROVIDER,
        narrative_cache_ttl_hours=NARRATIVE_CACHE_TTL_HOURS,
        narrative_min_evidence=NARRATIVE_MIN_EVIDENCE,
        narrative_timeout_seconds=NARRATIVE_TIMEOUT_SECONDS,
        xai_api_key=os.getenv("XAI_API_KEY", "").strip(),
```

Extend `apply_runtime_env()`:

```python
    os.environ["NARRATIVE_ENABLED"] = "1" if cfg.narrative_enabled else "0"
    os.environ["NARRATIVE_PROVIDER"] = cfg.narrative_provider
    os.environ["NARRATIVE_CACHE_TTL_HOURS"] = str(cfg.narrative_cache_ttl_hours)
    os.environ["NARRATIVE_MIN_EVIDENCE"] = str(cfg.narrative_min_evidence)
    os.environ["NARRATIVE_TIMEOUT_SECONDS"] = str(cfg.narrative_timeout_seconds)
    if cfg.xai_api_key:
        os.environ["XAI_API_KEY"] = cfg.xai_api_key
```

Extend `validate_runtime_config()`:

```python
    if cfg.narrative_provider not in {"mock", "xai"}:
        raise ValueError("narrative_provider must be one of: mock, xai")
    if cfg.narrative_cache_ttl_hours <= 0:
        raise ValueError("narrative_cache_ttl_hours must be > 0")
    if cfg.narrative_min_evidence < 0:
        raise ValueError("narrative_min_evidence must be >= 0")
    if cfg.narrative_timeout_seconds <= 0:
        raise ValueError("narrative_timeout_seconds must be > 0")
```

- [ ] **Step 4: Parse config in `config.py`**

Add to `apps/trending-alert-bot/config.py` after `DRY_RUN`:

```python
# Narrative analysis
NARRATIVE_ENABLED = _as_bool(os.getenv("NARRATIVE_ENABLED", "0"))
NARRATIVE_PROVIDER = os.getenv("NARRATIVE_PROVIDER", "xai").strip().lower() or "xai"
if NARRATIVE_PROVIDER not in {"mock", "xai"}:
    raise RuntimeError(f"unsupported narrative provider: {NARRATIVE_PROVIDER}")

NARRATIVE_CACHE_TTL_HOURS = int(os.getenv("NARRATIVE_CACHE_TTL_HOURS", "12"))
if NARRATIVE_CACHE_TTL_HOURS <= 0:
    raise RuntimeError("NARRATIVE_CACHE_TTL_HOURS must be > 0")

NARRATIVE_MIN_EVIDENCE = int(os.getenv("NARRATIVE_MIN_EVIDENCE", "3"))
if NARRATIVE_MIN_EVIDENCE < 0:
    raise RuntimeError("NARRATIVE_MIN_EVIDENCE must be >= 0")

NARRATIVE_TIMEOUT_SECONDS = int(os.getenv("NARRATIVE_TIMEOUT_SECONDS", "20"))
if NARRATIVE_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("NARRATIVE_TIMEOUT_SECONDS must be > 0")

XAI_API_KEY = os.getenv("XAI_API_KEY", "").strip()
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest \
  tests.test_bot_app_config.BotAppConfigTests.test_runtime_config_sets_narrative_defaults \
  tests.test_review_regressions.ReviewRegressionTests.test_narrative_config_defaults_disabled
```

Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add apps/trending-alert-bot/bot_app.py apps/trending-alert-bot/config.py apps/trending-alert-bot/tests/test_bot_app_config.py apps/trending-alert-bot/tests/test_review_regressions.py
git commit -m "feat(trending-alert-bot): add narrative runtime config"
```

## Task 2: Narrative Types

**Files:**
- Create: `apps/trending-alert-bot/narrative_types.py`
- Test: `apps/trending-alert-bot/tests/test_narrative_scoring.py`

- [ ] **Step 1: Write failing serialization tests**

Create `apps/trending-alert-bot/tests/test_narrative_scoring.py`:

```python
import unittest

from narrative_types import EvidenceItem, InfluencerHit, NarrativeLLMResult


class NarrativeScoringTests(unittest.TestCase):
    def test_llm_result_round_trips_json(self):
        result = NarrativeLLMResult(
            narrative_tags=["meme", "binance_related"],
            summary="CA matched in active meme posts.",
            confidence="medium",
            influencer_hits=[
                InfluencerHit(
                    account="cz_binance",
                    hit_type="mentioned_by_others",
                    strength="weak",
                    evidence_url="https://x.com/example/status/1",
                )
            ],
            risk_flags=["mostly_shill_posts"],
            evidence_links=["https://x.com/example/status/1"],
        )

        encoded = result.to_json()
        decoded = NarrativeLLMResult.from_json(encoded)

        self.assertEqual(decoded.narrative_tags, ["meme", "binance_related"])
        self.assertEqual(decoded.influencer_hits[0].account, "cz_binance")
        self.assertEqual(decoded.risk_flags, ["mostly_shill_posts"])

    def test_evidence_item_flags_exact_token_matches(self):
        item = EvidenceItem(
            url="https://x.com/example/status/1",
            author_handle="example",
            author_id="123",
            text="Buying TOKEN1 now",
            created_at="2026-07-08T00:00:00Z",
            like_count=12,
            repost_count=3,
            reply_count=1,
            quote_count=0,
            exact_token_match=True,
            symbol_or_name_match=False,
        )

        self.assertTrue(item.exact_token_match)
        self.assertFalse(item.symbol_or_name_match)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_narrative_scoring.NarrativeScoringTests
```

Expected: FAIL with `ModuleNotFoundError: No module named 'narrative_types'`.

- [ ] **Step 3: Create `narrative_types.py`**

Create `apps/trending-alert-bot/narrative_types.py`:

```python
import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


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
            narrative_tags=[str(item) for item in _as_list(data.get("narrative_tags")) if str(item)],
            summary=str(data.get("summary", "")),
            confidence=confidence,
            influencer_hits=hits,
            risk_flags=[str(item) for item in _as_list(data.get("risk_flags")) if str(item)],
            evidence_links=[str(item) for item in _as_list(data.get("evidence_links")) if str(item)],
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
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_narrative_scoring.NarrativeScoringTests
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add apps/trending-alert-bot/narrative_types.py apps/trending-alert-bot/tests/test_narrative_scoring.py
git commit -m "feat(trending-alert-bot): add narrative result types"
```

## Task 3: Rule-Based Narrative Scoring

**Files:**
- Create: `apps/trending-alert-bot/narrative_scoring.py`
- Modify: `apps/trending-alert-bot/tests/test_narrative_scoring.py`

- [ ] **Step 1: Write failing scoring tests**

Append to `NarrativeScoringTests`:

```python
    def test_direct_tier_zero_author_scores_high(self):
        from narrative_scoring import compute_narrative_score

        llm = NarrativeLLMResult(
            narrative_tags=["elon_related", "meme"],
            summary="Elon authored a directly related post.",
            confidence="high",
            influencer_hits=[
                InfluencerHit(
                    account="elonmusk",
                    hit_type="author",
                    strength="strong",
                    evidence_url="https://x.com/elonmusk/status/1",
                )
            ],
            risk_flags=[],
            evidence_links=["https://x.com/elonmusk/status/1"],
        )
        evidence = [
            EvidenceItem(
                url="https://x.com/elonmusk/status/1",
                author_handle="elonmusk",
                author_id="44196397",
                text="TOKEN_CA",
                like_count=1000,
                repost_count=200,
                reply_count=50,
                quote_count=20,
                exact_token_match=True,
            )
        ]

        score = compute_narrative_score(llm, evidence)

        self.assertGreaterEqual(score, 80)

    def test_third_party_influencer_name_drop_does_not_get_source_credit(self):
        from narrative_scoring import compute_narrative_score

        llm = NarrativeLLMResult(
            narrative_tags=["cz_related"],
            summary="Third parties claim CZ relevance.",
            confidence="medium",
            influencer_hits=[
                InfluencerHit(
                    account="cz_binance",
                    hit_type="mentioned_by_others",
                    strength="weak",
                    evidence_url="https://x.com/random/status/1",
                )
            ],
            risk_flags=["claimed_influencer_without_direct_evidence"],
            evidence_links=["https://x.com/random/status/1"],
        )
        evidence = [
            EvidenceItem(
                url="https://x.com/random/status/1",
                author_handle="random",
                author_id="999",
                text="CZ will buy this TOKEN_CA",
                like_count=5,
                repost_count=1,
                reply_count=0,
                quote_count=0,
                exact_token_match=True,
            )
        ]

        score = compute_narrative_score(llm, evidence)

        self.assertLess(score, 55)

    def test_risk_deductions_clamp_score_at_zero(self):
        from narrative_scoring import compute_narrative_score

        llm = NarrativeLLMResult(
            narrative_tags=[],
            summary="Weak evidence.",
            confidence="low",
            risk_flags=[
                "ticker_ambiguity",
                "mostly_shill_posts",
                "no_contract_address_evidence",
                "claimed_influencer_without_direct_evidence",
            ],
        )

        self.assertEqual(compute_narrative_score(llm, []), 0)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_narrative_scoring.NarrativeScoringTests
```

Expected: FAIL with `ModuleNotFoundError: No module named 'narrative_scoring'`.

- [ ] **Step 3: Create `narrative_scoring.py`**

Create `apps/trending-alert-bot/narrative_scoring.py`:

```python
from typing import Dict, Iterable, List

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
    return item.like_count + item.repost_count * 2 + item.quote_count * 2 + item.reply_count


def token_link_score(evidence: Iterable[EvidenceItem]) -> int:
    items = list(evidence)
    if any(item.exact_token_match for item in items):
        return 20
    if any(item.symbol_or_name_match for item in items):
        return 8
    return 0


def source_score(llm_result: NarrativeLLMResult, account_tiers: Dict[str, int] = None) -> int:
    tiers = account_tiers or DEFAULT_ACCOUNT_TIERS
    best = 0
    for hit in llm_result.influencer_hits:
        tier = tiers.get(hit.account.lower())
        if tier is None:
            continue
        best = max(best, SOURCE_POINTS.get(tier, {}).get(hit.hit_type, 0))
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
    authors = {item.author_id or item.author_handle for item in evidence if item.author_id or item.author_handle}
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


def freshness_score(evidence: Iterable[EvidenceItem]) -> int:
    return 10 if list(evidence) else 0


def risk_deduction(llm_result: NarrativeLLMResult, evidence: Iterable[EvidenceItem]) -> int:
    deduction = sum(RISK_DEDUCTIONS.get(flag, 0) for flag in llm_result.risk_flags)
    if token_link_score(evidence) == 0:
        deduction += RISK_DEDUCTIONS["no_contract_address_evidence"]
    return deduction


def compute_narrative_score(
    llm_result: NarrativeLLMResult,
    evidence: List[EvidenceItem],
    account_tiers: Dict[str, int] = None,
) -> int:
    total = (
        token_link_score(evidence)
        + source_score(llm_result, account_tiers)
        + engagement_score(evidence)
        + volume_score(evidence)
        + narrative_clarity_score(llm_result)
        + freshness_score(evidence)
        - risk_deduction(llm_result, evidence)
    )
    return _clamp(total)
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_narrative_scoring.NarrativeScoringTests
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add apps/trending-alert-bot/narrative_scoring.py apps/trending-alert-bot/tests/test_narrative_scoring.py
git commit -m "feat(trending-alert-bot): score narrative evidence"
```

## Task 4: Narrative SQLite Cache

**Files:**
- Modify: `apps/trending-alert-bot/db_storage.py`
- Create: `apps/trending-alert-bot/narrative_storage.py`
- Create: `apps/trending-alert-bot/tests/test_narrative_storage.py`

- [ ] **Step 1: Write failing storage tests**

Create `apps/trending-alert-bot/tests/test_narrative_storage.py`:

```python
import json
import os
import sqlite3
import sys
import tempfile
import unittest


def load_narrative_storage_modules(data_dir: str):
    os.environ.update(
        {
            "BOT_CHECK_INTERVAL": "15",
            "BOT_CHAINS": json.dumps(["sol"]),
            "BOT_CHAIN": "sol",
            "BOT_NOTIFY_COOLDOWN_HOURS": "24",
            "BOT_MULTIPLIER_CONFIRMATIONS": "1",
            "BOT_NOTIFICATION_TYPES": json.dumps(["trending", "anomaly"]),
            "BOT_CHAIN_ALLOWLIST_JSON": json.dumps({"sol": {}}),
            "BOT_DATA_DIR": data_dir,
            "BOT_TELEGRAM_TOKEN": "123:test",
            "BOT_DRY_RUN": "0",
            "NARRATIVE_ENABLED": "1",
            "NARRATIVE_PROVIDER": "mock",
            "NARRATIVE_CACHE_TTL_HOURS": "12",
        }
    )

    for name in ["config", "db_storage", "narrative_types", "narrative_storage"]:
        if name in sys.modules:
            del sys.modules[name]

    import config
    import narrative_storage
    from narrative_types import NarrativeAnalysis

    return config, narrative_storage, NarrativeAnalysis


class NarrativeStorageTests(unittest.TestCase):
    def test_schema_contains_narrative_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, narrative_storage, _ = load_narrative_storage_modules(tmp)
            narrative_storage.ensure_narrative_storage()

            with sqlite3.connect(config.SQLITE_DB_FILE) as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(narrative_analysis)").fetchall()}

            self.assertIn("chain", columns)
            self.assertIn("token_address", columns)
            self.assertIn("score", columns)
            self.assertIn("expires_at", columns)

    def test_save_and_load_cached_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, narrative_storage, NarrativeAnalysis = load_narrative_storage_modules(tmp)
            analysis = NarrativeAnalysis(
                provider="mock",
                score=72,
                confidence="medium",
                tags=["meme"],
                summary="Meme narrative with CA evidence.",
                risk_flags=["mostly_shill_posts"],
                evidence_links=["https://x.com/example/status/1"],
            )

            narrative_storage.save_analysis("sol", "TOKEN1", analysis, ttl_hours=12)
            loaded = narrative_storage.load_cached_analysis("sol", "TOKEN1", "mock")

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.score, 72)
            self.assertEqual(loaded.tags, ["meme"])
            self.assertEqual(loaded.risk_flags, ["mostly_shill_posts"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_narrative_storage.NarrativeStorageTests
```

Expected: FAIL with `ModuleNotFoundError: No module named 'narrative_storage'`.

- [ ] **Step 3: Add schema creation to `db_storage.py`**

Add this helper before `ensure_schema()`:

```python
def _create_narrative_analysis_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS narrative_analysis (
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
        )
        """
    )
```

Call it inside `ensure_schema()` after `_ensure_contract_schema(conn)`:

```python
            _create_narrative_analysis_table(conn)
```

- [ ] **Step 4: Create `narrative_storage.py`**

Create `apps/trending-alert-bot/narrative_storage.py`:

```python
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
```

- [ ] **Step 5: Run storage tests and existing SQLite tests**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest \
  tests.test_narrative_storage.NarrativeStorageTests \
  tests.test_sqlite_storage.SqliteStorageTests
```

Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add apps/trending-alert-bot/db_storage.py apps/trending-alert-bot/narrative_storage.py apps/trending-alert-bot/tests/test_narrative_storage.py
git commit -m "feat(trending-alert-bot): cache narrative analysis"
```

## Task 5: Narrative Providers

**Files:**
- Create: `apps/trending-alert-bot/narrative_provider.py`
- Create: `apps/trending-alert-bot/tests/test_narrative_service.py`

- [ ] **Step 1: Write failing provider tests**

Create `apps/trending-alert-bot/tests/test_narrative_service.py`:

```python
import json
import os
import sys
import tempfile
import unittest
from unittest import mock


def load_narrative_modules(data_dir: str, env=None):
    values = {
        "BOT_CHECK_INTERVAL": "15",
        "BOT_CHAINS": json.dumps(["sol"]),
        "BOT_CHAIN": "sol",
        "BOT_NOTIFY_COOLDOWN_HOURS": "24",
        "BOT_MULTIPLIER_CONFIRMATIONS": "1",
        "BOT_NOTIFICATION_TYPES": json.dumps(["trending", "anomaly"]),
        "BOT_CHAIN_ALLOWLIST_JSON": json.dumps({"sol": {}}),
        "BOT_DATA_DIR": data_dir,
        "BOT_TELEGRAM_TOKEN": "123:test",
        "BOT_DRY_RUN": "0",
        "NARRATIVE_ENABLED": "1",
        "NARRATIVE_PROVIDER": "mock",
        "NARRATIVE_CACHE_TTL_HOURS": "12",
        "NARRATIVE_MIN_EVIDENCE": "1",
        "NARRATIVE_TIMEOUT_SECONDS": "20",
    }
    if env:
        values.update(env)
    os.environ.update(values)

    for name in [
        "config",
        "db_storage",
        "narrative_types",
        "narrative_scoring",
        "narrative_storage",
        "narrative_provider",
        "narrative_service",
    ]:
        if name in sys.modules:
            del sys.modules[name]

    import narrative_provider
    from narrative_types import NarrativeInput

    return narrative_provider, NarrativeInput


class NarrativeProviderTests(unittest.TestCase):
    def test_mock_provider_returns_structured_result_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(tmp)
            provider = narrative_provider.MockNarrativeProvider()

            result, evidence = provider.analyze(
                NarrativeInput(chain="sol", token_address="TOKEN1", symbol="SAFE", name="Safe Token")
            )

            self.assertEqual(result.confidence, "low")
            self.assertEqual(result.narrative_tags, [])
            self.assertEqual(evidence, [])

    def test_xai_provider_extracts_output_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            fake_response = {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "narrative_tags": ["meme"],
                                        "summary": "Meme discussion.",
                                        "confidence": "medium",
                                        "influencer_hits": [],
                                        "risk_flags": [],
                                        "evidence_links": ["https://x.com/example/status/1"],
                                    }
                                ),
                            }
                        ]
                    }
                ]
            }
            provider = narrative_provider.XaiNarrativeProvider(api_key="key", timeout_seconds=20)

            with mock.patch.object(provider, "_post_response", return_value=fake_response):
                result, evidence = provider.analyze(
                    NarrativeInput(chain="sol", token_address="TOKEN1", symbol="SAFE", name="Safe Token")
                )

            self.assertEqual(result.narrative_tags, ["meme"])
            self.assertEqual(result.confidence, "medium")
            self.assertEqual(evidence[0].url, "https://x.com/example/status/1")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_narrative_service.NarrativeProviderTests
```

Expected: FAIL with `ModuleNotFoundError: No module named 'narrative_provider'`.

- [ ] **Step 3: Create `narrative_provider.py`**

Create `apps/trending-alert-bot/narrative_provider.py`:

```python
import json
from typing import List, Tuple

from narrative_types import EvidenceItem, NarrativeInput, NarrativeLLMResult


class NarrativeProviderError(RuntimeError):
    pass


class BaseNarrativeProvider:
    provider_name = "base"

    def analyze(self, narrative_input: NarrativeInput) -> Tuple[NarrativeLLMResult, List[EvidenceItem]]:
        raise NotImplementedError


class MockNarrativeProvider(BaseNarrativeProvider):
    provider_name = "mock"

    def analyze(self, narrative_input: NarrativeInput) -> Tuple[NarrativeLLMResult, List[EvidenceItem]]:
        return NarrativeLLMResult(confidence="low"), []


class XaiNarrativeProvider(BaseNarrativeProvider):
    provider_name = "xai"

    def __init__(self, api_key: str, timeout_seconds: int):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _post_response(self, payload: dict) -> dict:
        if not self.api_key:
            raise NarrativeProviderError("XAI_API_KEY is required for xai narrative provider")
        from curl_cffi import requests

        response = requests.post(
            "https://api.x.ai/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
            impersonate="chrome120",
        )
        response.raise_for_status()
        return response.json()

    def _build_prompt(self, narrative_input: NarrativeInput) -> str:
        return (
            "Search X for evidence about this crypto token and return JSON only. "
            "Do not invent links, accounts, or claims. Distinguish direct posts by influential accounts "
            "from third-party posts that only mention those people. "
            "JSON keys: narrative_tags, summary, confidence, influencer_hits, risk_flags, evidence_links. "
            f"chain={narrative_input.chain}; "
            f"token_address={narrative_input.token_address}; "
            f"symbol={narrative_input.symbol}; "
            f"name={narrative_input.name}; "
            f"links={json.dumps(narrative_input.links, ensure_ascii=False)}"
        )

    def _extract_output_text(self, response_json: dict) -> str:
        if isinstance(response_json.get("output_text"), str):
            return response_json["output_text"]
        parts = []
        for item in response_json.get("output", []) or []:
            for content in item.get("content", []) or []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    parts.append(str(content["text"]))
        return "\n".join(parts).strip()

    def analyze(self, narrative_input: NarrativeInput) -> Tuple[NarrativeLLMResult, List[EvidenceItem]]:
        payload = {
            "model": "grok-4.3",
            "input": [{"role": "user", "content": self._build_prompt(narrative_input)}],
            "tools": [{"type": "x_search"}],
        }
        response_json = self._post_response(payload)
        output_text = self._extract_output_text(response_json)
        if not output_text:
            raise NarrativeProviderError("xai response did not contain output text")
        llm_result = NarrativeLLMResult.from_json(output_text)
        evidence = [
            EvidenceItem(url=url, exact_token_match=True)
            for url in llm_result.evidence_links
        ]
        return llm_result, evidence


def build_provider(provider_name: str, xai_api_key: str, timeout_seconds: int) -> BaseNarrativeProvider:
    if provider_name == "mock":
        return MockNarrativeProvider()
    if provider_name == "xai":
        return XaiNarrativeProvider(api_key=xai_api_key, timeout_seconds=timeout_seconds)
    raise NarrativeProviderError(f"unsupported narrative provider: {provider_name}")
```

- [ ] **Step 4: Run provider tests**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_narrative_service.NarrativeProviderTests
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add apps/trending-alert-bot/narrative_provider.py apps/trending-alert-bot/tests/test_narrative_service.py
git commit -m "feat(trending-alert-bot): add narrative providers"
```

## Task 6: Narrative Service Orchestration

**Files:**
- Create: `apps/trending-alert-bot/narrative_service.py`
- Modify: `apps/trending-alert-bot/tests/test_narrative_service.py`

- [ ] **Step 1: Write failing service tests**

Append to `apps/trending-alert-bot/tests/test_narrative_service.py`:

```python
class NarrativeServiceTests(unittest.TestCase):
    def test_disabled_service_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_narrative_modules(tmp, {"NARRATIVE_ENABLED": "0"})
            import narrative_service

            result = narrative_service.analyze_contract_narrative(
                {
                    "tokenAddress": "TOKEN1",
                    "pairAddress": "PAIR1",
                    "symbol": "SAFE",
                    "name": "Safe Token",
                    "links": {},
                    "priceUSD": "1.0",
                    "marketCapUSD": "1000",
                    "volume": "100",
                },
                "sol",
                [],
            )

            self.assertIsNone(result)

    def test_provider_failure_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_narrative_modules(tmp)
            import narrative_provider
            import narrative_service

            class FailingProvider(narrative_provider.BaseNarrativeProvider):
                provider_name = "mock"

                def analyze(self, narrative_input):
                    raise narrative_provider.NarrativeProviderError("down")

            with mock.patch.object(narrative_service, "_get_provider", return_value=FailingProvider()):
                result = narrative_service.analyze_contract_narrative(
                    {
                        "tokenAddress": "TOKEN1",
                        "pairAddress": "PAIR1",
                        "symbol": "SAFE",
                        "name": "Safe Token",
                        "links": {},
                        "priceUSD": "1.0",
                        "marketCapUSD": "1000",
                        "volume": "100",
                    },
                    "sol",
                    [],
                )

            self.assertIsNone(result)

    def test_successful_result_is_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_narrative_modules(tmp)
            import narrative_service
            from narrative_provider import BaseNarrativeProvider
            from narrative_types import EvidenceItem, NarrativeLLMResult

            class CountingProvider(BaseNarrativeProvider):
                provider_name = "mock"
                calls = 0

                def analyze(self, narrative_input):
                    self.calls += 1
                    return (
                        NarrativeLLMResult(
                            narrative_tags=["meme"],
                            summary="Meme discussion.",
                            confidence="medium",
                            evidence_links=["https://x.com/example/status/1"],
                        ),
                        [
                            EvidenceItem(
                                url="https://x.com/example/status/1",
                                exact_token_match=True,
                                author_handle="example",
                                author_id="1",
                                like_count=10,
                            )
                        ],
                    )

            provider = CountingProvider()
            contract = {
                "tokenAddress": "TOKEN1",
                "pairAddress": "PAIR1",
                "symbol": "SAFE",
                "name": "Safe Token",
                "links": {},
                "priceUSD": "1.0",
                "marketCapUSD": "1000",
                "volume": "100",
            }

            with mock.patch.object(narrative_service, "_get_provider", return_value=provider):
                first = narrative_service.analyze_contract_narrative(contract, "sol", [])
                second = narrative_service.analyze_contract_narrative(contract, "sol", [])

            self.assertIsNotNone(first)
            self.assertEqual(second.score, first.score)
            self.assertEqual(provider.calls, 1)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_narrative_service.NarrativeServiceTests
```

Expected: FAIL with `ModuleNotFoundError: No module named 'narrative_service'`.

- [ ] **Step 3: Create `narrative_service.py`**

Create `apps/trending-alert-bot/narrative_service.py`:

```python
from typing import List, Optional

from config import (
    NARRATIVE_CACHE_TTL_HOURS,
    NARRATIVE_ENABLED,
    NARRATIVE_PROVIDER,
    NARRATIVE_TIMEOUT_SECONDS,
    XAI_API_KEY,
)
from narrative_provider import NarrativeProviderError, build_provider
from narrative_scoring import compute_narrative_score
from narrative_storage import load_cached_analysis, save_analysis
from narrative_types import NarrativeAnalysis, NarrativeInput


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _get_provider():
    return build_provider(NARRATIVE_PROVIDER, XAI_API_KEY, NARRATIVE_TIMEOUT_SECONDS)


def build_narrative_input(contract: dict, chain: str, kol_holders: List[dict]) -> NarrativeInput:
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


def analyze_contract_narrative(contract: dict, chain: str, kol_holders: List[dict]) -> Optional[NarrativeAnalysis]:
    if not NARRATIVE_ENABLED:
        return None

    token_address = str(contract.get("tokenAddress") or "")
    if not token_address:
        return None

    cached = load_cached_analysis(chain, token_address, NARRATIVE_PROVIDER)
    if cached:
        return cached

    narrative_input = build_narrative_input(contract, chain, kol_holders)
    try:
        provider = _get_provider()
        llm_result, evidence = provider.analyze(narrative_input)
        score = compute_narrative_score(llm_result, evidence)
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
                "evidence_count": len(evidence),
            },
        )
        save_analysis(chain, token_address, analysis, NARRATIVE_CACHE_TTL_HOURS)
        return analysis
    except (NarrativeProviderError, ValueError, TypeError) as e:
        print(f"⚠️ [{chain.upper()}] narrative analysis failed: {contract.get('symbol', 'N/A')} | {token_address} | {e}")
        return None
```

- [ ] **Step 4: Run service tests**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_narrative_service.NarrativeServiceTests
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add apps/trending-alert-bot/narrative_service.py apps/trending-alert-bot/tests/test_narrative_service.py
git commit -m "feat(trending-alert-bot): orchestrate narrative analysis"
```

## Task 7: Notification Formatting

**Files:**
- Modify: `apps/trending-alert-bot/notifier.py`
- Modify: `apps/trending-alert-bot/tests/test_review_regressions.py`

- [ ] **Step 1: Write failing notification formatting test**

Add this to `ReviewRegressionTests`:

```python
    def test_initial_notification_includes_narrative_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, notifier, _ = load_runtime_modules(tmp)

            msg = notifier.format_initial_notification(
                sample_contract(),
                "sol",
                narrative={
                    "tags": ["meme", "binance_related"],
                    "score": 72,
                    "summary": "CA matched in active meme posts.",
                    "confidence": "medium",
                    "risk_flags": ["mostly_shill_posts"],
                },
            )

            self.assertIn("🧠 叙事: meme, binance_related", msg)
            self.assertIn("⭐ 叙事分: 72/100", msg)
            self.assertIn("📌 依据: CA matched in active meme posts.", msg)
            self.assertIn("⚠️ 风险: mostly_shill_posts", msg)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_review_regressions.ReviewRegressionTests.test_initial_notification_includes_narrative_section
```

Expected: FAIL because `format_initial_notification()` does not accept `narrative`.

- [ ] **Step 3: Add narrative formatting helper**

Add this to `apps/trending-alert-bot/notifier.py` near `_format_kol_sections()`:

```python
def _format_narrative_section(narrative=None) -> str:
    if not narrative:
        return ""

    tags = narrative.get("tags") or []
    tag_text = ", ".join(_html_escape(tag) for tag in tags) if tags else "N/A"
    score = _safe_int(narrative.get("score"))
    summary = _html_escape(narrative.get("summary", ""))
    confidence = _html_escape(narrative.get("confidence", "low"))
    risk_flags = narrative.get("risk_flags") or []
    risk_text = ", ".join(_html_escape(flag) for flag in risk_flags) if risk_flags else "none"

    return f"""

🧠 叙事: {tag_text}
⭐ 叙事分: {score}/100
📌 依据: {summary}
🔎 置信度: {confidence}
⚠️ 风险: {risk_text}"""
```

Change `format_initial_notification()` signature:

```python
def format_initial_notification(
    contract: Dict,
    chain: str = "",
    kol_holders: Optional[List[Dict]] = None,
    kol_leavers: Optional[List[Dict]] = None,
    is_anomaly: bool = False,
    narrative: Optional[Dict] = None,
) -> str:
```

Append the section after KOL sections:

```python
    msg += _format_kol_sections(kol_holders, kol_leavers)
    msg += _format_narrative_section(narrative)
```

- [ ] **Step 4: Run notification test**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_review_regressions.ReviewRegressionTests.test_initial_notification_includes_narrative_section
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add apps/trending-alert-bot/notifier.py apps/trending-alert-bot/tests/test_review_regressions.py
git commit -m "feat(trending-alert-bot): render narrative in notifications"
```

## Task 8: Monitor Flow Integration

**Files:**
- Modify: `apps/trending-alert-bot/monitor_flow.py`
- Modify: `apps/trending-alert-bot/tests/test_review_regressions.py`

- [ ] **Step 1: Write failing integration test**

Add this to `ReviewRegressionTests`:

```python
    def test_candidate_notification_uses_narrative_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(chain="sol", chat_id=111)
            contract = sample_contract(tokenAddress="TOKEN1", priceUSD="1.0")
            fake_analysis = mock.Mock()
            fake_analysis.to_display_dict.return_value = {
                "tags": ["meme"],
                "score": 66,
                "summary": "Meme posts with CA evidence.",
                "confidence": "medium",
                "risk_flags": [],
            }

            monitor_flow.ENABLE_TELEGRAM = False
            monitor_flow.DRY_RUN = True
            with (
                mock.patch.object(monitor_flow, "analyze_contract_narrative", return_value=fake_analysis) as narrative_mock,
                mock.patch.object(monitor_flow, "format_initial_notification", return_value="msg") as format_mock,
            ):
                sent = monitor_flow._send_candidate_notification(
                    storage,
                    111,
                    "sol",
                    contract,
                    [],
                    [],
                    False,
                )

            self.assertEqual(sent, 1)
            narrative_mock.assert_called_once()
            self.assertEqual(format_mock.call_args.kwargs["narrative"]["score"], 66)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_review_regressions.ReviewRegressionTests.test_candidate_notification_uses_narrative_when_available
```

Expected: FAIL because `monitor_flow` does not import or call `analyze_contract_narrative`.

- [ ] **Step 3: Integrate narrative service in `monitor_flow.py`**

Add import:

```python
from narrative_service import analyze_contract_narrative
```

In `_send_candidate_notification()`, before `format_initial_notification()`:

```python
    narrative_analysis = analyze_contract_narrative(
        contract,
        chain,
        kol_with_positions,
    )
    narrative = narrative_analysis.to_display_dict() if narrative_analysis else None
```

Change the formatter call:

```python
    msg = format_initial_notification(
        contract,
        chain,
        kol_with_positions,
        kol_without_positions,
        is_anomaly,
        narrative=narrative,
    )
```

- [ ] **Step 4: Run integration test**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_review_regressions.ReviewRegressionTests.test_candidate_notification_uses_narrative_when_available
```

Expected: OK.

- [ ] **Step 5: Run full app tests**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/trending-alert-bot/monitor_flow.py apps/trending-alert-bot/tests/test_review_regressions.py
git commit -m "feat(trending-alert-bot): enrich notifications with narratives"
```

## Task 9: Documentation and Env Samples

**Files:**
- Modify: `apps/trending-alert-bot/.env.example`
- Modify: `apps/trending-alert-bot/README.md`

- [ ] **Step 1: Update `.env.example`**

Append:

```env
# Narrative analysis (disabled by default)
NARRATIVE_ENABLED=false
NARRATIVE_PROVIDER=xai
NARRATIVE_CACHE_TTL_HOURS=12
NARRATIVE_MIN_EVIDENCE=3
NARRATIVE_TIMEOUT_SECONDS=20
XAI_API_KEY=
```

- [ ] **Step 2: Update README**

Add this section after `Validate Env`:

```markdown
## Narrative Analysis

Narrative analysis is disabled by default. When enabled, the bot analyzes only contracts that are about to receive an initial trend/anomaly notification.

```bash
NARRATIVE_ENABLED=true
NARRATIVE_PROVIDER=xai
XAI_API_KEY=...
```

The first production provider uses xAI Responses API with `x_search`. The bot computes the final score locally from the returned structured result, so the model summarizes evidence while deterministic rules control scoring.

The narrative result is cached in SQLite per `chain + token_address + provider`. If the provider fails or times out, the normal trend/anomaly notification is still sent without the narrative section.
```

- [ ] **Step 3: Commit docs**

```bash
git add apps/trending-alert-bot/.env.example apps/trending-alert-bot/README.md
git commit -m "docs(trending-alert-bot): document narrative analysis"
```

## Task 10: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run all tests**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 2: Inspect diff summary**

Run:

```bash
git status -sb
git log --oneline -10
```

Expected: working tree clean, with the task commits visible.

- [ ] **Step 3: Manual dry-run smoke check with narrative disabled**

Run:

```bash
cd apps/trending-alert-bot
uv run python main.py sol --dry-run
```

Expected: if Telegram token env is configured, dry-run scans one round. If token env is missing, the command exits with the existing missing-token validation and no narrative-specific import or config errors.

- [ ] **Step 4: Report completion**

Report:

- Test command and result.
- Whether dry-run reached scan or stopped on missing local token.
- Commit list.
- Any remaining need for `XAI_API_KEY` before production narrative analysis can be enabled.
