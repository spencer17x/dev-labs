import json
from typing import List, Tuple

from narrative_types import EvidenceItem, NarrativeInput, NarrativeLLMResult


class NarrativeProviderError(RuntimeError):
    pass


class BaseNarrativeProvider:
    provider_name = "base"

    def analyze(
        self, narrative_input: NarrativeInput
    ) -> Tuple[NarrativeLLMResult, List[EvidenceItem]]:
        raise NotImplementedError


class MockNarrativeProvider(BaseNarrativeProvider):
    provider_name = "mock"

    def analyze(
        self, narrative_input: NarrativeInput
    ) -> Tuple[NarrativeLLMResult, List[EvidenceItem]]:
        return NarrativeLLMResult(confidence="low"), []


class XaiNarrativeProvider(BaseNarrativeProvider):
    provider_name = "xai"

    def __init__(self, api_key: str, timeout_seconds: int):
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = timeout_seconds

    def _post_response(self, payload: dict) -> dict:
        if not self.api_key:
            raise NarrativeProviderError(
                "XAI_API_KEY is required for xai narrative provider"
            )
        try:
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
        except NarrativeProviderError:
            raise
        except Exception as exc:
            raise NarrativeProviderError("xai provider request failed") from exc

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
        if not isinstance(response_json, dict):
            return ""
        if isinstance(response_json.get("output_text"), str):
            return response_json["output_text"].strip()
        output = response_json.get("output")
        if not isinstance(output, list):
            return ""
        parts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content_items = item.get("content")
            if not isinstance(content_items, list):
                continue
            for content in content_items:
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if content.get("type") in {"output_text", "text"} and isinstance(
                    text, str
                ):
                    parts.append(text)
        return "\n".join(parts).strip()

    def analyze(
        self, narrative_input: NarrativeInput
    ) -> Tuple[NarrativeLLMResult, List[EvidenceItem]]:
        payload = {
            "model": "grok-4.3",
            "input": [{"role": "user", "content": self._build_prompt(narrative_input)}],
            "tools": [{"type": "x_search"}],
        }
        response_json = self._post_response(payload)
        output_text = self._extract_output_text(response_json)
        if not output_text:
            raise NarrativeProviderError("xai response did not contain output text")
        try:
            llm_result = NarrativeLLMResult.from_json(output_text)
        except NarrativeProviderError:
            raise
        except Exception as exc:
            raise NarrativeProviderError(
                "xai response contained invalid narrative JSON"
            ) from exc
        evidence = [EvidenceItem(url=url) for url in llm_result.evidence_links]
        return llm_result, evidence


def build_provider(
    provider_name: str, xai_api_key: str, timeout_seconds: int
) -> BaseNarrativeProvider:
    normalized_provider_name = (provider_name or "").strip().lower()
    if normalized_provider_name == "mock":
        return MockNarrativeProvider()
    if normalized_provider_name == "xai":
        return XaiNarrativeProvider(
            api_key=xai_api_key, timeout_seconds=timeout_seconds
        )
    raise NarrativeProviderError(f"unsupported narrative provider: {provider_name}")
