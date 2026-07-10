import json
import re
from typing import Dict, List, Set, Tuple
from urllib.parse import urlsplit, urlunsplit

from narrative_types import (
    EvidenceItem,
    InfluencerHit,
    NarrativeInput,
    NarrativeLLMResult,
)

_NARRATIVE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative_tags": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "influencer_hits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "account": {"type": "string"},
                    "hit_type": {"type": "string"},
                    "strength": {"type": "string"},
                    "evidence_url": {"type": "string"},
                },
                "required": ["account", "hit_type", "strength", "evidence_url"],
                "additionalProperties": False,
            },
        },
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "evidence_links": {"type": "array", "items": {"type": "string"}},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "text": {"type": "string"},
                    "author_handle": {"type": "string"},
                    "author_id": {"type": "string"},
                    "created_at": {"type": "string"},
                    "like_count": {"type": "integer"},
                    "repost_count": {"type": "integer"},
                    "reply_count": {"type": "integer"},
                    "quote_count": {"type": "integer"},
                },
                "required": [
                    "url",
                    "text",
                    "author_handle",
                    "author_id",
                    "created_at",
                    "like_count",
                    "repost_count",
                    "reply_count",
                    "quote_count",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "narrative_tags",
        "summary",
        "confidence",
        "influencer_hits",
        "risk_flags",
        "evidence_links",
        "evidence",
    ],
    "additionalProperties": False,
}


def _safe_nonnegative_int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _normalize_url(value: str) -> str:
    parsed = urlsplit(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )


def _x_author_from_url(value: str) -> str:
    parsed = urlsplit(value)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc.lower() in {
        "x.com",
        "www.x.com",
        "twitter.com",
        "www.twitter.com",
    }:
        if len(parts) >= 3 and parts[1] == "status" and parts[0].lower() != "i":
            return parts[0].lstrip("@").lower()
    return ""


def _normalize_handle(value: str) -> str:
    return str(value or "").strip().lstrip("@").lower()


def _contains_exact_value(text: str, value: str) -> bool:
    needle = str(value or "").strip()
    if not needle:
        return False
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _citation_url(value) -> str:
    if isinstance(value, str):
        return _normalize_url(value)
    if not isinstance(value, dict):
        return ""
    direct_url = value.get("url") or value.get("uri")
    if direct_url:
        return _normalize_url(direct_url)
    nested = value.get("url_citation")
    if isinstance(nested, dict):
        return _normalize_url(nested.get("url") or nested.get("uri") or "")
    return ""


def _extract_citation_urls(response_json: dict) -> Set[str]:
    if not isinstance(response_json, dict):
        return set()

    urls = set()
    citations = response_json.get("citations")
    if isinstance(citations, list):
        for citation in citations:
            normalized = _citation_url(citation)
            if normalized:
                urls.add(normalized)

    output = response_json.get("output")
    if not isinstance(output, list):
        return urls
    for item in output:
        if not isinstance(item, dict):
            continue
        content_items = item.get("content")
        if not isinstance(content_items, list):
            continue
        for content in content_items:
            if not isinstance(content, dict):
                continue
            annotations = content.get("annotations")
            if not isinstance(annotations, list):
                continue
            for annotation in annotations:
                if not isinstance(annotation, dict):
                    continue
                if annotation.get("type") != "url_citation":
                    continue
                normalized = _citation_url(annotation)
                if normalized:
                    urls.add(normalized)
    return urls


def _build_evidence(
    raw_evidence,
    cited_urls: Set[str],
    narrative_input: NarrativeInput,
) -> Tuple[List[EvidenceItem], Dict[str, EvidenceItem]]:
    accepted = []
    by_url = {}
    if not isinstance(raw_evidence, list):
        return accepted, by_url

    for row in raw_evidence:
        if not isinstance(row, dict):
            continue
        url = _normalize_url(row.get("url", ""))
        if not url or url not in cited_urls or url in by_url:
            continue
        text = str(row.get("text") or "")
        author_handle = _x_author_from_url(url) or _normalize_handle(
            row.get("author_handle", "")
        )
        item = EvidenceItem(
            url=url,
            author_handle=author_handle,
            author_id=str(row.get("author_id") or "").strip(),
            text=text,
            created_at=str(row.get("created_at") or "").strip(),
            like_count=_safe_nonnegative_int(row.get("like_count")),
            repost_count=_safe_nonnegative_int(row.get("repost_count")),
            reply_count=_safe_nonnegative_int(row.get("reply_count")),
            quote_count=_safe_nonnegative_int(row.get("quote_count")),
            exact_token_match=_contains_exact_value(
                text, narrative_input.token_address
            ),
            symbol_or_name_match=(
                _contains_exact_value(text, narrative_input.symbol)
                or _contains_exact_value(text, narrative_input.name)
            ),
        )
        accepted.append(item)
        by_url[url] = item
    return accepted, by_url


def _validated_influencer_hits(
    hits: List[InfluencerHit], evidence_by_url: Dict[str, EvidenceItem]
) -> List[InfluencerHit]:
    accepted = []
    for hit in hits:
        evidence_url = _normalize_url(hit.evidence_url)
        evidence = evidence_by_url.get(evidence_url)
        if evidence is None:
            continue
        hit_type = str(hit.hit_type).strip().lower()
        if hit_type == "mentioned_by_others":
            pass
        elif hit_type in {"author", "reply", "quote"}:
            if not evidence.author_handle or _normalize_handle(
                hit.account
            ) != _normalize_handle(evidence.author_handle):
                continue
        else:
            continue
        accepted.append(
            InfluencerHit(
                account=hit.account,
                hit_type=hit_type,
                strength=hit.strength,
                evidence_url=evidence_url,
            )
        )
    return accepted


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
            "Search X for evidence about this crypto token and return the requested structured JSON. "
            "Do not invent links, accounts, or claims. Distinguish direct posts by influential accounts "
            "from third-party posts that only mention those people. "
            "Every evidence row must describe a specific cited post and include its excerpt, author, "
            "timestamp, and engagement counts. "
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
            "include": ["no_inline_citations"],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "token_narrative",
                    "schema": _NARRATIVE_RESPONSE_SCHEMA,
                    "strict": True,
                }
            },
        }
        response_json = self._post_response(payload)
        output_text = self._extract_output_text(response_json)
        if not output_text:
            raise NarrativeProviderError("xai response did not contain output text")
        try:
            parsed = json.loads(output_text)
            if not isinstance(parsed, dict):
                raise ValueError("narrative result must be a JSON object")
            llm_result = NarrativeLLMResult.from_dict(parsed)
        except NarrativeProviderError:
            raise
        except Exception as exc:
            raise NarrativeProviderError(
                "xai response contained invalid narrative JSON"
            ) from exc
        evidence, evidence_by_url = _build_evidence(
            parsed.get("evidence"),
            _extract_citation_urls(response_json),
            narrative_input,
        )
        llm_result.evidence_links = [item.url for item in evidence]
        llm_result.influencer_hits = _validated_influencer_hits(
            llm_result.influencer_hits, evidence_by_url
        )
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
