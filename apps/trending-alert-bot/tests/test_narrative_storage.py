import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

EXPECTED_NARRATIVE_COLUMNS = [
    "chain",
    "token_address",
    "provider",
    "score",
    "confidence",
    "tags_json",
    "summary",
    "influencer_hits_json",
    "risk_flags_json",
    "evidence_links_json",
    "raw_result_json",
    "created_at",
    "expires_at",
]


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
    from narrative_types import InfluencerHit, NarrativeAnalysis

    return config, narrative_storage, NarrativeAnalysis, InfluencerHit


class NarrativeStorageTests(unittest.TestCase):
    def test_schema_contains_narrative_table(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with tempfile.TemporaryDirectory() as tmp:
                config, narrative_storage, _, _ = load_narrative_storage_modules(tmp)
                narrative_storage.ensure_narrative_storage()

                with sqlite3.connect(config.SQLITE_DB_FILE) as conn:
                    table_info = conn.execute(
                        "PRAGMA table_info(narrative_analysis)"
                    ).fetchall()
                    columns = {row[1] for row in table_info}
                    primary_key = {row[1]: row[5] for row in table_info if row[5]}

            self.assertEqual(set(EXPECTED_NARRATIVE_COLUMNS), columns)
            self.assertEqual(
                primary_key,
                {"chain": 1, "token_address": 2, "provider": 3},
            )

    def test_save_and_load_cached_analysis(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with tempfile.TemporaryDirectory() as tmp:
                (
                    _,
                    narrative_storage,
                    NarrativeAnalysis,
                    InfluencerHit,
                ) = load_narrative_storage_modules(tmp)
                analysis = NarrativeAnalysis(
                    provider="mock",
                    score=72,
                    confidence="medium",
                    tags=["meme"],
                    summary="Meme narrative with CA evidence.",
                    influencer_hits=[
                        InfluencerHit(
                            account="@alice",
                            hit_type="mention",
                            strength="high",
                            evidence_url="https://x.com/alice/status/1",
                        )
                    ],
                    risk_flags=["mostly_shill_posts"],
                    evidence_links=["https://x.com/example/status/1"],
                    raw_result={
                        "model": "mock",
                        "scores": {"narrative": 72},
                        "labels": ["meme", "community"],
                    },
                )

                narrative_storage.save_analysis("sol", "TOKEN1", analysis, ttl_hours=12)
                loaded = narrative_storage.load_cached_analysis("sol", "TOKEN1", "mock")

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.score, 72)
            self.assertEqual(loaded.tags, ["meme"])
            self.assertEqual(len(loaded.influencer_hits), 1)
            self.assertEqual(loaded.influencer_hits[0].account, "@alice")
            self.assertEqual(loaded.influencer_hits[0].hit_type, "mention")
            self.assertEqual(loaded.influencer_hits[0].strength, "high")
            self.assertEqual(
                loaded.influencer_hits[0].evidence_url,
                "https://x.com/alice/status/1",
            )
            self.assertEqual(loaded.risk_flags, ["mostly_shill_posts"])
            self.assertEqual(
                loaded.raw_result,
                {
                    "model": "mock",
                    "scores": {"narrative": 72},
                    "labels": ["meme", "community"],
                },
            )

    def test_load_cached_analysis_returns_none_for_missing_row(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with tempfile.TemporaryDirectory() as tmp:
                _, narrative_storage, _, _ = load_narrative_storage_modules(tmp)

                loaded = narrative_storage.load_cached_analysis(
                    "sol",
                    "MISSING",
                    "mock",
                )

            self.assertIsNone(loaded)

    def test_load_cached_analysis_returns_none_for_expired_row(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with tempfile.TemporaryDirectory() as tmp:
                (
                    _,
                    narrative_storage,
                    NarrativeAnalysis,
                    _,
                ) = load_narrative_storage_modules(tmp)
                analysis = NarrativeAnalysis(
                    provider="mock",
                    score=72,
                    confidence="medium",
                    tags=["meme"],
                    summary="Expired narrative.",
                )

                narrative_storage.save_analysis("sol", "TOKEN1", analysis, ttl_hours=-1)
                loaded = narrative_storage.load_cached_analysis("sol", "TOKEN1", "mock")

            self.assertIsNone(loaded)


if __name__ == "__main__":
    unittest.main()
