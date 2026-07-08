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
                                    {
                                        "narrative_tags": ["meme"],
                                        "summary": "Meme discussion.",
                                        "confidence": "medium",
                                        "influencer_hits": [],
                                        "risk_flags": [],
                                        "evidence_links": [
                                            "https://x.com/example/status/1"
                                        ],
                                    }
                                ),
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
            self.assertFalse(evidence[0].exact_token_match)

    def test_xai_provider_parses_top_level_output_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            narrative_provider, NarrativeInput = load_narrative_modules(
                tmp,
                {"NARRATIVE_PROVIDER": "xai", "XAI_API_KEY": "key"},
            )
            fake_response = {
                "output_text": json.dumps(
                    {
                        "narrative_tags": ["ai"],
                        "summary": "AI discussion.",
                        "confidence": "high",
                        "influencer_hits": [],
                        "risk_flags": [],
                        "evidence_links": ["https://x.com/example/status/2"],
                    }
                )
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


if __name__ == "__main__":
    unittest.main()
