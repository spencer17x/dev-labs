import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
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
    previous_env = {key: os.environ.get(key) for key in values}
    os.environ.update(values)

    try:
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

        import config
        import narrative_provider
        from narrative_types import NarrativeInput
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    return narrative_provider, NarrativeInput


class NarrativeProviderTests(unittest.TestCase):
    def _assert_provider_error(self, narrative_provider, callback):
        try:
            callback()
        except Exception as exc:
            self.assertIsInstance(exc, narrative_provider.NarrativeProviderError)
            return exc
        else:
            self.fail("NarrativeProviderError not raised")

    def _structured_output(
        self,
        evidence_url,
        *,
        text="TOKEN1",
        influencer_hits=None,
        **evidence_overrides,
    ):
        evidence = {
            "url": evidence_url,
            "text": text,
            "author_handle": "example",
            "author_id": "1",
            "created_at": "2026-07-10T01:00:00Z",
            "like_count": 1,
            "repost_count": 0,
            "reply_count": 0,
            "quote_count": 0,
        }
        evidence.update(evidence_overrides)
        return {
            "narrative_tags": ["meme"],
            "summary": "Cited token discussion.",
            "confidence": "medium",
            "influencer_hits": influencer_hits or [],
            "risk_flags": [],
            "evidence_links": [evidence_url],
            "evidence": [evidence],
        }

    def test_mock_provider_returns_structured_result_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(tmp)
            provider = narrative_provider.MockNarrativeProvider()

            result, evidence = provider.analyze(
                NarrativeInput(
                    chain="sol",
                    token_address="TOKEN1",
                    symbol="SAFE",
                    name="Safe Token",
                )
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
                                    self._structured_output(
                                        "https://x.com/example/status/1",
                                        text="Meme discussion for TOKEN1.",
                                    )
                                ),
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "url": "https://x.com/example/status/1",
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value=fake_response
            ):
                result, evidence = provider.analyze(
                    NarrativeInput(
                        chain="sol",
                        token_address="TOKEN1",
                        symbol="SAFE",
                        name="Safe Token",
                    )
                )

            self.assertEqual(result.narrative_tags, ["meme"])
            self.assertEqual(result.confidence, "medium")
            self.assertEqual(evidence[0].url, "https://x.com/example/status/1")
            self.assertTrue(evidence[0].exact_token_match)

    def test_xai_provider_accepts_only_cited_structured_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            evidence_url = "https://X.com/Alice/status/123/?s=20"
            cited_url = "https://x.com/alice/status/123"
            uncited_url = "https://x.com/elonmusk/status/456"
            output = self._structured_output(
                evidence_url,
                text="Safe Token is live at TOKEN1.",
                influencer_hits=[
                    {
                        "account": "@alice",
                        "hit_type": "author",
                        "strength": "high",
                        "evidence_url": evidence_url,
                    },
                    {
                        "account": "@elonmusk",
                        "hit_type": "author",
                        "strength": "high",
                        "evidence_url": evidence_url,
                    },
                    {
                        "account": "@elonmusk",
                        "hit_type": "mentioned_by_others",
                        "strength": "low",
                        "evidence_url": evidence_url,
                    },
                    {
                        "account": "@elonmusk",
                        "hit_type": "author",
                        "strength": "high",
                        "evidence_url": uncited_url,
                    },
                ],
                author_handle="spoofed",
                author_id="42",
                like_count=-10,
                repost_count="-2",
                reply_count=None,
                quote_count="bad",
            )
            output["evidence_links"] = [uncited_url]
            fake_response = {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(output),
                                "annotations": [
                                    {"type": "url_citation", "url": cited_url}
                                ],
                            }
                        ]
                    }
                ]
            }
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value=fake_response
            ) as post_response:
                result, evidence = provider.analyze(
                    NarrativeInput(
                        chain="sol",
                        token_address="TOKEN1",
                        symbol="SAFE",
                        name="Safe Token",
                    )
                )

            payload = post_response.call_args.args[0]
            response_format = payload["text"]["format"]
            self.assertEqual(payload["include"], ["no_inline_citations"])
            self.assertEqual(response_format["type"], "json_schema")
            self.assertTrue(response_format["strict"])
            self.assertIn("evidence", response_format["schema"]["required"])
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0].url, cited_url)
            self.assertEqual(evidence[0].author_handle, "alice")
            self.assertEqual(evidence[0].author_id, "")
            self.assertTrue(evidence[0].exact_token_match)
            self.assertTrue(evidence[0].symbol_or_name_match)
            self.assertEqual(evidence[0].like_count, 0)
            self.assertEqual(evidence[0].repost_count, 0)
            self.assertEqual(evidence[0].reply_count, 0)
            self.assertEqual(evidence[0].quote_count, 0)
            self.assertEqual(result.evidence_links, [cited_url])
            self.assertEqual(
                [(hit.account, hit.hit_type) for hit in result.influencer_hits],
                [
                    ("@alice", "author"),
                    ("@elonmusk", "mentioned_by_others"),
                ],
            )

            from narrative_scoring import compute_narrative_score

            self.assertGreater(compute_narrative_score(result, evidence), 20)

    def test_xai_provider_rejects_uncited_structured_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            evidence_url = "https://x.com/alice/status/123"
            fake_response = {
                "output_text": json.dumps(self._structured_output(evidence_url))
            }
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value=fake_response
            ):
                result, evidence = provider.analyze(
                    NarrativeInput(chain="sol", token_address="TOKEN1")
                )

            self.assertEqual(evidence, [])
            self.assertEqual(result.evidence_links, [])

    def test_xai_provider_deduplicates_x_status_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            first_url = "https://twitter.com/Alice/status/123?s=20"
            alias_url = "https://x.com/alice/status/123/photo/1"
            output = self._structured_output(first_url)
            duplicate = dict(output["evidence"][0])
            duplicate["url"] = alias_url
            output["evidence"].append(duplicate)
            fake_response = {
                "output_text": json.dumps(output),
                "citations": [first_url, alias_url],
            }
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value=fake_response
            ):
                result, evidence = provider.analyze(
                    NarrativeInput(chain="sol", token_address="TOKEN1")
                )

            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0].url, "https://x.com/alice/status/123")
            self.assertEqual(result.evidence_links, ["https://x.com/alice/status/123"])

    def test_xai_provider_rejects_unverified_direct_author(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            evidence_url = "https://x.com/i/web/status/123"
            output = self._structured_output(
                evidence_url,
                author_handle="elonmusk",
                influencer_hits=[
                    {
                        "account": "elonmusk",
                        "hit_type": "author",
                        "strength": "high",
                        "evidence_url": evidence_url,
                    }
                ],
            )
            fake_response = {
                "output_text": json.dumps(output),
                "citations": [evidence_url],
            }
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value=fake_response
            ):
                result, evidence = provider.analyze(
                    NarrativeInput(chain="sol", token_address="TOKEN1")
                )

            self.assertEqual(len(evidence), 1)
            self.assertEqual(result.influencer_hits, [])

    def test_xai_provider_matches_token_address_with_chain_case_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            evidence_url = "https://x.com/alice/status/123"
            fake_response = {
                "output_text": json.dumps(
                    self._structured_output(evidence_url, text="buy abcd now")
                ),
                "citations": [evidence_url],
            }
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value=fake_response
            ):
                _, sol_evidence = provider.analyze(
                    NarrativeInput(chain="sol", token_address="AbCd")
                )
                _, eth_evidence = provider.analyze(
                    NarrativeInput(chain="eth", token_address="AbCd")
                )

            self.assertFalse(sol_evidence[0].exact_token_match)
            self.assertTrue(eth_evidence[0].exact_token_match)

    def test_xai_provider_parses_top_level_output_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            fake_response = {
                "output_text": json.dumps(
                    {
                        **self._structured_output(
                            "https://x.com/example/status/2",
                            text="AI discussion for TOKEN1.",
                            author_id="2",
                        ),
                        "narrative_tags": ["ai"],
                        "summary": "AI discussion.",
                        "confidence": "high",
                    }
                ),
                "citations": ["https://x.com/example/status/2"],
            }
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value=fake_response
            ):
                result, evidence = provider.analyze(
                    NarrativeInput(
                        chain="sol",
                        token_address="TOKEN1",
                        symbol="SAFE",
                        name="Safe Token",
                    )
                )

            self.assertEqual(result.narrative_tags, ["ai"])
            self.assertEqual(result.confidence, "high")
            self.assertEqual(evidence[0].url, "https://x.com/example/status/2")

    def test_xai_provider_whitespace_output_raises_provider_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value={"output_text": " \n\t"}
            ):
                self._assert_provider_error(
                    narrative_provider,
                    lambda: provider.analyze(
                        NarrativeInput(
                            chain="sol",
                            token_address="TOKEN1",
                            symbol="SAFE",
                            name="Safe Token",
                        )
                    ),
                )

    def test_xai_provider_malformed_nested_response_raises_provider_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            fake_response = {
                "output": [
                    None,
                    "bad",
                    {"content": "bad"},
                    {"content": [None, "bad", {"type": "output_text"}]},
                ]
            }
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value=fake_response
            ):
                self._assert_provider_error(
                    narrative_provider,
                    lambda: provider.analyze(
                        NarrativeInput(
                            chain="sol",
                            token_address="TOKEN1",
                            symbol="SAFE",
                            name="Safe Token",
                        )
                    ),
                )

    def test_xai_provider_non_dict_response_raises_provider_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(provider, "_post_response", return_value=[]):
                self._assert_provider_error(
                    narrative_provider,
                    lambda: provider.analyze(
                        NarrativeInput(
                            chain="sol",
                            token_address="TOKEN1",
                            symbol="SAFE",
                            name="Safe Token",
                        )
                    ),
                )

    def test_xai_provider_blank_api_key_raises_before_request_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, _ = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            provider = narrative_provider.XaiNarrativeProvider(
                api_key=" \n\t", timeout_seconds=20
            )

            with mock.patch(
                "builtins.__import__",
                side_effect=AssertionError("request import should not happen"),
            ) as import_mock:
                self._assert_provider_error(
                    narrative_provider, lambda: provider._post_response({})
                )

            import_mock.assert_not_called()

    def test_build_provider_normalizes_name_and_strips_xai_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, _ = load_narrative_modules(tmp)

            try:
                provider = narrative_provider.build_provider(" XAI ", " key ", 20)
            except Exception as exc:
                self.fail(f"build_provider rejected normalized provider name: {exc}")

            self.assertIsInstance(provider, narrative_provider.XaiNarrativeProvider)
            self.assertEqual(provider.api_key, "key")

    def test_xai_provider_invalid_json_output_wraps_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value={"output_text": "not json"}
            ):
                exc = self._assert_provider_error(
                    narrative_provider,
                    lambda: provider.analyze(
                        NarrativeInput(
                            chain="sol",
                            token_address="TOKEN1",
                            symbol="SAFE",
                            name="Safe Token",
                        )
                    ),
                )

            self.assertIsNotNone(exc.__cause__)

    def test_xai_provider_json_array_output_wraps_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )

            with mock.patch.object(
                provider, "_post_response", return_value={"output_text": "[]"}
            ):
                exc = self._assert_provider_error(
                    narrative_provider,
                    lambda: provider.analyze(
                        NarrativeInput(
                            chain="sol",
                            token_address="TOKEN1",
                            symbol="SAFE",
                            name="Safe Token",
                        )
                    ),
                )

            self.assertIsNotNone(exc.__cause__)

    def test_xai_post_response_wraps_request_failure_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, _ = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            provider = narrative_provider.XaiNarrativeProvider(
                api_key="key", timeout_seconds=20
            )
            post_error = RuntimeError("request down")
            fake_requests = SimpleNamespace(post=mock.Mock(side_effect=post_error))

            with mock.patch.dict(
                sys.modules,
                {"curl_cffi": SimpleNamespace(requests=fake_requests)},
            ):
                exc = self._assert_provider_error(
                    narrative_provider, lambda: provider._post_response({})
                )

            self.assertIs(exc.__cause__, post_error)


class NarrativeServiceTests(unittest.TestCase):
    def _contract(self, **overrides):
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
        contract.update(overrides)
        return contract

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

            with mock.patch.object(
                narrative_service, "_get_provider", return_value=FailingProvider()
            ):
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

    def test_insufficient_evidence_returns_none_without_caching(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_narrative_modules(tmp, {"NARRATIVE_MIN_EVIDENCE": "3"})
            import narrative_service
            from narrative_provider import BaseNarrativeProvider
            from narrative_types import EvidenceItem, NarrativeLLMResult

            class TwoEvidenceProvider(BaseNarrativeProvider):
                provider_name = "mock"

                def analyze(self, narrative_input):
                    return (
                        NarrativeLLMResult(
                            narrative_tags=["meme"],
                            summary="Only two cited posts.",
                            confidence="medium",
                        ),
                        [
                            EvidenceItem(url="https://x.com/a/status/1"),
                            EvidenceItem(url="https://x.com/b/status/2"),
                        ],
                    )

            with mock.patch.object(
                narrative_service,
                "_get_provider",
                return_value=TwoEvidenceProvider(),
            ), mock.patch.object(narrative_service, "save_analysis") as save:
                result = narrative_service.analyze_contract_narrative(
                    self._contract(), "sol", []
                )

            self.assertIsNone(result)
            save.assert_not_called()

    def test_cache_without_current_evidence_policy_is_refreshed(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_narrative_modules(tmp, {"NARRATIVE_MIN_EVIDENCE": "3"})
            import narrative_service
            from narrative_provider import BaseNarrativeProvider
            from narrative_types import (
                EvidenceItem,
                NarrativeAnalysis,
                NarrativeLLMResult,
            )

            class RefreshProvider(BaseNarrativeProvider):
                provider_name = "mock"

                def __init__(self):
                    self.calls = 0

                def analyze(self, narrative_input):
                    self.calls += 1
                    return (
                        NarrativeLLMResult(
                            narrative_tags=["fresh"],
                            summary="Fresh cited evidence.",
                            confidence="medium",
                        ),
                        [
                            EvidenceItem(url=f"https://x.com/a/status/{index}")
                            for index in range(3)
                        ],
                    )

            invalid_raw_results = [
                {"evidence_count": 2},
                {},
                {"evidence_count": "3"},
                {"evidence_count": 3},
            ]
            for raw_result in invalid_raw_results:
                with self.subTest(raw_result=raw_result):
                    cached = NarrativeAnalysis(
                        provider="mock",
                        score=99,
                        confidence="high",
                        tags=["stale"],
                        summary="Cached without current evidence policy.",
                        raw_result=raw_result,
                    )
                    provider = RefreshProvider()
                    with mock.patch.object(
                        narrative_service,
                        "load_cached_analysis",
                        return_value=cached,
                    ), mock.patch.object(
                        narrative_service, "_get_provider", return_value=provider
                    ), mock.patch.object(
                        narrative_service, "save_analysis"
                    ) as save:
                        result = narrative_service.analyze_contract_narrative(
                            self._contract(), "sol", []
                        )

                    self.assertEqual(result.summary, "Fresh cited evidence.")
                    self.assertEqual(provider.calls, 1)
                    save.assert_called_once()

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

            with mock.patch.object(
                narrative_service, "_get_provider", return_value=provider
            ):
                first = narrative_service.analyze_contract_narrative(
                    contract, "sol", []
                )
                second = narrative_service.analyze_contract_narrative(
                    contract, "sol", []
                )

            self.assertIsNotNone(first)
            self.assertEqual(first.raw_result.get("evidence_policy_version"), 2)
            self.assertEqual(second.score, first.score)
            self.assertEqual(provider.calls, 1)

    def test_generator_evidence_is_materialized_and_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_narrative_modules(tmp)
            import narrative_service
            from narrative_provider import BaseNarrativeProvider
            from narrative_types import EvidenceItem, NarrativeLLMResult

            class GeneratorProvider(BaseNarrativeProvider):
                provider_name = "mock"

                def __init__(self):
                    self.calls = 0

                def analyze(self, narrative_input):
                    self.calls += 1

                    def evidence_items():
                        yield EvidenceItem(
                            url="https://x.com/example/status/1",
                            exact_token_match=True,
                            author_handle="example",
                            author_id="1",
                            like_count=10,
                        )
                        yield EvidenceItem(
                            url="https://x.com/example/status/2",
                            exact_token_match=True,
                            author_handle="example2",
                            author_id="2",
                            like_count=20,
                        )

                    return (
                        NarrativeLLMResult(
                            narrative_tags=["meme"],
                            summary="Meme discussion.",
                            confidence="medium",
                            evidence_links=[
                                "https://x.com/example/status/1",
                                "https://x.com/example/status/2",
                            ],
                        ),
                        evidence_items(),
                    )

            provider = GeneratorProvider()

            with mock.patch.object(
                narrative_service, "_get_provider", return_value=provider
            ):
                first = narrative_service.analyze_contract_narrative(
                    self._contract(), "sol", []
                )
                second = narrative_service.analyze_contract_narrative(
                    self._contract(), "sol", []
                )

            self.assertIsNotNone(first)
            self.assertEqual(first.raw_result["evidence_count"], 2)
            self.assertEqual(second.raw_result["evidence_count"], 2)
            self.assertEqual(provider.calls, 1)

    def test_cache_load_failure_continues_to_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_narrative_modules(tmp)
            import narrative_service
            from narrative_provider import BaseNarrativeProvider
            from narrative_types import EvidenceItem, NarrativeLLMResult

            class CountingProvider(BaseNarrativeProvider):
                provider_name = "mock"

                def __init__(self):
                    self.calls = 0

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
                            )
                        ],
                    )

            provider = CountingProvider()

            with mock.patch.object(
                narrative_service,
                "load_cached_analysis",
                side_effect=RuntimeError("cache down"),
            ), mock.patch.object(
                narrative_service, "_get_provider", return_value=provider
            ):
                result = narrative_service.analyze_contract_narrative(
                    self._contract(), "sol", []
                )

            self.assertIsNotNone(result)
            self.assertEqual(provider.calls, 1)

    def test_cache_save_failure_returns_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_narrative_modules(tmp)
            import narrative_service
            from narrative_provider import BaseNarrativeProvider
            from narrative_types import EvidenceItem, NarrativeLLMResult

            class CountingProvider(BaseNarrativeProvider):
                provider_name = "mock"

                def analyze(self, narrative_input):
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
                            )
                        ],
                    )

            with mock.patch.object(
                narrative_service, "_get_provider", return_value=CountingProvider()
            ), mock.patch.object(
                narrative_service,
                "save_analysis",
                side_effect=RuntimeError("write down"),
            ):
                result = narrative_service.analyze_contract_narrative(
                    self._contract(), "sol", []
                )

            self.assertIsNotNone(result)
            self.assertEqual(result.raw_result["evidence_count"], 1)

    def test_missing_token_skips_cache_and_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_narrative_modules(tmp)
            import narrative_service

            with mock.patch.object(
                narrative_service, "load_cached_analysis"
            ) as load_cached, mock.patch.object(
                narrative_service, "_get_provider"
            ) as get_provider:
                result = narrative_service.analyze_contract_narrative(
                    self._contract(tokenAddress=""), "sol", []
                )

            self.assertIsNone(result)
            load_cached.assert_not_called()
            get_provider.assert_not_called()

    def test_build_narrative_input_sanitizes_optional_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_narrative_modules(tmp)
            import narrative_service

            narrative_input = narrative_service.build_narrative_input(
                self._contract(links=["bad"], marketCapUSD="bad", volume=None),
                "sol",
                [{"handle": "alice"}],
            )

            self.assertEqual(narrative_input.links, {})
            self.assertEqual(narrative_input.market_cap_usd, 0.0)
            self.assertEqual(narrative_input.volume_24h, 0.0)
            self.assertEqual(narrative_input.kol_summary, [{"handle": "alice"}])


if __name__ == "__main__":
    unittest.main()
