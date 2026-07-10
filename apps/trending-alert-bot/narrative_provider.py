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

_X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}


def _safe_nonnegative_int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _normalize_url(value: str) -> str:
    parsed = urlsplit(str(value).strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if scheme not in {"http", "https"} or not netloc:
        return ""
    if netloc in _X_HOSTS:
        author, status_id = _x_status_parts(value)
        if status_id:
            if author:
                return f"https://x.com/{author}/status/{status_id}"
            return f"https://x.com/i/status/{status_id}"
        netloc = "x.com"
    return urlunsplit(
        (
            scheme,
            netloc,
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )


def _x_status_parts(value: str) -> Tuple[str, str]:
    parsed = urlsplit(value)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc.lower() not in _X_HOSTS:
        return "", ""
    if len(parts) >= 3 and parts[1].lower() == "status":
        status_id = parts[2]
        if status_id.isdigit() and parts[0].lower() != "i":
            return parts[0].lstrip("@").lower(), status_id
    if (
        len(parts) >= 4
        and parts[0].lower() == "i"
        and parts[1].lower() == "web"
        and parts[2].lower() == "status"
        and parts[3].isdigit()
    ):
        return "", parts[3]
    if (
        len(parts) >= 3
        and parts[0].lower() == "i"
        and parts[1].lower() == "status"
        and parts[2].isdigit()
    ):
        return "", parts[2]
    return "", ""


def _x_author_from_url(value: str) -> str:
    return _x_status_parts(value)[0]


def _evidence_identity(value: str) -> str:
    normalized = _normalize_url(value)
    if not normalized:
        return ""
    _, status_id = _x_status_parts(normalized)
    if status_id:
        return f"x-status:{status_id}"
    return normalized


def _normalize_handle(value: str) -> str:
    return str(value or "").strip().lstrip("@").lower()


def _contains_exact_value(text: str, value: str, *, ignore_case: bool = True) -> bool:
    needle = str(value or "").strip()
    if not needle:
        return False
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])",
            str(text or ""),
            flags=re.IGNORECASE if ignore_case else 0,
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
    by_identity = {}
    if not isinstance(raw_evidence, list):
        return accepted, by_identity

    cited_identities = {
        identity for url in cited_urls if (identity := _evidence_identity(url))
    }

    for row in raw_evidence:
        if not isinstance(row, dict):
            continue
        url = _normalize_url(row.get("url", ""))
        identity = _evidence_identity(url)
        if not url or identity not in cited_identities or identity in by_identity:
            continue
        text = str(row.get("text") or "")
        author_handle = _x_author_from_url(url)
        item = EvidenceItem(
            url=url,
            author_handle=author_handle,
            author_id="",
            text=text,
            created_at=str(row.get("created_at") or "").strip(),
            like_count=_safe_nonnegative_int(row.get("like_count")),
            repost_count=_safe_nonnegative_int(row.get("repost_count")),
            reply_count=_safe_nonnegative_int(row.get("reply_count")),
            quote_count=_safe_nonnegative_int(row.get("quote_count")),
            exact_token_match=_contains_exact_value(
                text,
                narrative_input.token_address,
                ignore_case=str(narrative_input.chain).strip().lower() != "sol",
            ),
            symbol_or_name_match=(
                _contains_exact_value(text, narrative_input.symbol)
                or _contains_exact_value(text, narrative_input.name)
            ),
        )
        accepted.append(item)
        by_identity[identity] = item
    return accepted, by_identity


def _validated_influencer_hits(
    hits: List[InfluencerHit], evidence_by_identity: Dict[str, EvidenceItem]
) -> List[InfluencerHit]:
    accepted = []
    for hit in hits:
        evidence_identity = _evidence_identity(hit.evidence_url)
        evidence = evidence_by_identity.get(evidence_identity)
        if evidence is None:
            continue
        hit_type = str(hit.hit_type).strip().lower()
        if hit_type == "mentioned_by_others":
            pass
        elif hit_type in {"author", "reply", "quote"}:
            verified_author = _x_author_from_url(evidence.url)
            if not verified_author or _normalize_handle(
                hit.account
            ) != _normalize_handle(verified_author):
                continue
        else:
            continue
        accepted.append(
            InfluencerHit(
                account=hit.account,
                hit_type=hit_type,
                strength=hit.strength,
                evidence_url=evidence.url,
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
        evidence, evidence_by_identity = _build_evidence(
            parsed.get("evidence"),
            _extract_citation_urls(response_json),
            narrative_input,
        )
        llm_result.evidence_links = [item.url for item in evidence]
        llm_result.influencer_hits = _validated_influencer_hits(
            llm_result.influencer_hits, evidence_by_identity
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
