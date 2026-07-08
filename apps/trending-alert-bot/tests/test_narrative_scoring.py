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


if __name__ == "__main__":
    unittest.main()
