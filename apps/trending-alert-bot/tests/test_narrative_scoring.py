from datetime import datetime, timezone
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

        from dataclasses import asdict

        self.assertEqual(asdict(decoded), asdict(result))

    def test_invalid_confidence_normalizes_to_low(self):
        result = NarrativeLLMResult.from_dict({"confidence": "very_high"})

        self.assertEqual(result.confidence, "low")

    def test_non_list_fields_are_treated_as_empty_lists(self):
        result = NarrativeLLMResult.from_dict(
            {
                "narrative_tags": "meme",
                "influencer_hits": {"account": "cz_binance"},
                "risk_flags": "mostly_shill_posts",
                "evidence_links": "https://x.com/example/status/1",
            }
        )

        self.assertEqual(result.narrative_tags, [])
        self.assertEqual(result.influencer_hits, [])
        self.assertEqual(result.risk_flags, [])
        self.assertEqual(result.evidence_links, [])

    def test_non_object_json_raises_value_error(self):
        with self.assertRaises(ValueError):
            NarrativeLLMResult.from_json('["meme"]')

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

    def test_direct_tier_zero_author_scores_high(self):
        from narrative_scoring import compute_narrative_score

        now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
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
                created_at="2026-07-08T06:00:00Z",
                exact_token_match=True,
            )
        ]

        score = compute_narrative_score(llm, evidence, now=now)

        self.assertGreaterEqual(score, 80)

    def test_third_party_influencer_name_drop_does_not_get_source_credit(self):
        from narrative_scoring import compute_narrative_score, source_score

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

        self.assertEqual(source_score(llm), 0)
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

    def test_generator_evidence_scores_like_list_input(self):
        from narrative_scoring import compute_narrative_score

        now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
        llm = NarrativeLLMResult(
            narrative_tags=["elon_related"],
            summary="Elon authored a directly related post.",
            confidence="high",
            influencer_hits=[
                InfluencerHit(
                    account="elonmusk",
                    hit_type="author",
                    strength="strong",
                    evidence_url="https://x.com/elonmusk/status/2",
                )
            ],
            risk_flags=[],
            evidence_links=["https://x.com/elonmusk/status/2"],
        )
        evidence = [
            EvidenceItem(
                url="https://x.com/elonmusk/status/2",
                author_handle="elonmusk",
                author_id="44196397",
                text="TOKEN_CA",
                like_count=500,
                repost_count=100,
                reply_count=20,
                quote_count=10,
                created_at="2026-07-08T06:00:00Z",
                exact_token_match=True,
            )
        ]

        list_score = compute_narrative_score(llm, evidence, now=now)
        generator_score = compute_narrative_score(
            llm, (item for item in evidence), now=now
        )

        self.assertEqual(generator_score, list_score)

    def test_empty_account_tiers_disable_source_credit(self):
        from narrative_scoring import source_score

        llm = NarrativeLLMResult(
            influencer_hits=[
                InfluencerHit(
                    account="elonmusk",
                    hit_type="author",
                    strength="strong",
                )
            ]
        )

        self.assertEqual(source_score(llm, account_tiers={}), 0)

    def test_duplicate_risk_flags_do_not_double_deduct(self):
        from narrative_scoring import risk_deduction

        llm = NarrativeLLMResult(
            risk_flags=[
                "ticker_ambiguity",
                "ticker_ambiguity",
                "no_contract_address_evidence",
            ]
        )

        self.assertEqual(risk_deduction(llm, []), 32)

    def test_freshness_score_uses_recent_timestamp_buckets(self):
        from narrative_scoring import freshness_score

        now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)

        self.assertEqual(
            freshness_score(
                [EvidenceItem(url="fresh", created_at="2026-07-08T06:00:00Z")], now=now
            ),
            10,
        )
        self.assertEqual(
            freshness_score(
                [EvidenceItem(url="daily", created_at="2026-07-07T12:00:00Z")], now=now
            ),
            6,
        )
        self.assertEqual(
            freshness_score(
                [EvidenceItem(url="older", created_at="2026-07-05T12:00:00Z")], now=now
            ),
            3,
        )

    def test_freshness_score_ignores_stale_missing_and_unparseable_timestamps(self):
        from narrative_scoring import freshness_score

        now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)

        self.assertEqual(
            freshness_score(
                [EvidenceItem(url="stale", created_at="2026-07-05T11:59:59Z")], now=now
            ),
            0,
        )
        self.assertEqual(freshness_score([EvidenceItem(url="missing")], now=now), 0)
        self.assertEqual(
            freshness_score(
                [EvidenceItem(url="bad", created_at="not-a-date")], now=now
            ),
            0,
        )

    def test_freshness_score_interprets_offset_and_naive_timestamps_consistently(self):
        from narrative_scoring import freshness_score

        now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)

        self.assertEqual(
            freshness_score(
                [EvidenceItem(url="offset", created_at="2026-07-08T14:00:00+02:00")],
                now=now,
            ),
            10,
        )
        self.assertEqual(
            freshness_score(
                [EvidenceItem(url="naive", created_at="2026-07-08T12:00:00")],
                now=now,
            ),
            10,
        )

    def test_source_score_normalizes_hit_and_custom_tier_handles(self):
        from narrative_scoring import source_score

        decorated_hit = NarrativeLLMResult(
            influencer_hits=[
                InfluencerHit(
                    account=" @Special ",
                    hit_type="author",
                    strength="strong",
                )
            ]
        )
        decorated_tier = NarrativeLLMResult(
            influencer_hits=[
                InfluencerHit(
                    account="special",
                    hit_type="author",
                    strength="strong",
                )
            ]
        )

        self.assertEqual(source_score(decorated_hit, account_tiers={"special": 1}), 20)
        self.assertEqual(
            source_score(decorated_tier, account_tiers={" @special ": 1}), 20
        )

    def test_source_score_normalizes_hit_type(self):
        from narrative_scoring import source_score

        llm = NarrativeLLMResult(
            influencer_hits=[
                InfluencerHit(
                    account="elonmusk",
                    hit_type=" Author ",
                    strength="strong",
                )
            ]
        )

        self.assertEqual(source_score(llm), 30)

    def test_volume_score_normalizes_author_handles_without_ids(self):
        from narrative_scoring import volume_score

        evidence = [
            EvidenceItem(url="https://x.com/a/status/1", author_handle=" @Alice "),
            EvidenceItem(url="https://x.com/a/status/2", author_handle="alice"),
        ]

        self.assertEqual(volume_score(evidence), 0)


if __name__ == "__main__":
    unittest.main()
