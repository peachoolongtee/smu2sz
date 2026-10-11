"""Model backends: Claude (Anthropic SDK, structured outputs) and DeepSeek (OpenAI-compatible SDK,
JSON mode + Pydantic validation + retries).

The model sees only the documents and the output schema. API keys come from the environment and are
never logged. Tests inject mocked clients; nothing here is called on a network in CI.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.compiler.base import BackendError, ContractResult, OfferResult, TermSheetResult
from app.compiler.prompts import (
    CONTRACT_SYSTEM_PROMPT,
    OFFER_SYSTEM_PROMPT,
    TERM_SHEET_SYSTEM_PROMPT,
    contract_user_message,
    offer_user_message,
    term_sheet_user_message,
)
from app.compiler.schema import ContractExtraction, OfferExtraction, TermSheetExtraction
from app.domain.models import SourceDocument

M = TypeVar("M", bound=BaseModel)

CLAUDE_DEFAULT_MODEL = "claude-sonnet-5-5"
CLAUDE_HARD_MODEL = "claude-opus-5-5"
DEEPSEEK_MODEL = "deepseek-flash"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16_000
HARD_CHARS = 1_500  # longer inputs, multi-document offers and term sheets go to the hard model


def is_hard(docs: Sequence[SourceDocument]) -> bool:
    return len(docs) > 1 or sum(len(d.text) for d in docs) > HARD_CHARS


def output_schema(model: type[BaseModel]) -> dict[str, Any]:
    """The Pydantic JSON schema of an extraction model (extra='forbid' gives additionalProperties:
    false on every object; every field is required)."""
    return model.model_json_schema()


# ---------------------------------------------------------------- Claude


class ClaudeBackend:
    name = "claude"

    def __init__(
        self,
        client: Any | None = None,
        model: str = CLAUDE_DEFAULT_MODEL,
        hard_model: str = CLAUDE_HARD_MODEL,
        timeout_s: float = 60.0,
    ) -> None:
        self._client = client
        self.model = model
        self.hard_model = hard_model
        self.timeout_s = timeout_s

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import anthropic

                self._client = anthropic.Anthropic(timeout=self.timeout_s, max_retries=2)
            except Exception as e:  # missing credentials or SDK problems: fall through the chain
                raise BackendError(f"anthropic client unavailable: {type(e).__name__}") from e
        return self._client

    def _call(self, model: str, system: str, user: str, schema_model: type[M], effort: str) -> tuple[M, str]:
        try:
            resp = self.client.beta.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={
                    "effort": effort,
                    "format": {"type": "json_schema", "schema": output_schema(schema_model)},
                },
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except BackendError:
            raise
        except Exception as e:  # anthropic.APIError family, timeouts, connection errors
            raise BackendError(f"claude call failed: {type(e).__name__}") from e
        stop = getattr(resp, "stop_reason", None)
        if stop in ("refusal", "max_tokens"):
            raise BackendError(f"claude stop_reason={stop}")
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
        if not text.strip():
            raise BackendError("claude returned no text")
        try:
            parsed = schema_model.model_validate_json(text)
        except ValidationError as e:
            raise BackendError("claude output failed schema validation") from e
        return parsed, str(getattr(resp, "model", None) or model)

    def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult:
        hard = is_hard(docs)
        ex, served = self._call(
            self.hard_model if hard else self.model,
            OFFER_SYSTEM_PROMPT,
            offer_user_message(docs),
            OfferExtraction,
            "high" if hard else "medium",
        )
        return OfferResult(ex, served)

    def extract_term_sheet(self, doc: SourceDocument) -> TermSheetResult:
        ex, served = self._call(
            self.hard_model, TERM_SHEET_SYSTEM_PROMPT, term_sheet_user_message(doc), TermSheetExtraction, "high"
        )
        return TermSheetResult(ex, served)

    def extract_contract(self, chunk: SourceDocument) -> ContractResult:
        ex, served = self._call(
            self.hard_model, CONTRACT_SYSTEM_PROMPT, contract_user_message(chunk), ContractExtraction, "high"
        )
        return ContractResult(ex, served)


# ---------------------------------------------------------------- DeepSeek


class DeepSeekBackend:
    """JSON mode guarantees JSON syntax but not the schema, and may return empty content: validate with
    Pydantic and retry up to `retries` more times, then raise so the chain falls back."""

    name = "deepseek"

    def __init__(
        self,
        client: Any | None = None,
        model: str = DEEPSEEK_MODEL,
        retries: int = 2,
        timeout_s: float = 60.0,
    ) -> None:
        self._client = client
        self.model = model
        self.retries = retries
        self.timeout_s = timeout_s

    @property
    def client(self) -> Any:
        if self._client is None:
            key = os.environ.get("DEEPSEEK_API_KEY")
            if not key:
                raise BackendError("DEEPSEEK_API_KEY not set")
            try:
                import openai

                self._client = openai.OpenAI(
                    api_key=key, base_url=DEEPSEEK_BASE_URL, timeout=self.timeout_s, max_retries=1
                )
            except Exception as e:
                raise BackendError(f"deepseek client unavailable: {type(e).__name__}") from e
        return self._client

    def _call(self, system: str, user: str, schema_model: type[M]) -> M:
        sys_msg = (
            system
            + "\nReturn a single JSON object that validates against this JSON schema:\n"
            + json.dumps(output_schema(schema_model), ensure_ascii=False)
        )
        last = "no attempt"
        for _attempt in range(self.retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user}],
                    response_format={"type": "json_object"},
                    max_tokens=8_000,
                    temperature=0,
                )
            except BackendError:
                raise
            except Exception as e:  # noqa: BLE001 - any SDK/transport error counts as one failed attempt
                last = f"call failed: {type(e).__name__}"
                continue
            try:
                content = resp.choices[0].message.content
            except (AttributeError, IndexError):
                content = None
            if not content or not content.strip():
                last = "empty content"
                continue
            try:
                return schema_model.model_validate_json(content)
            except ValidationError:
                last = "schema validation failed"
                continue
        raise BackendError(f"deepseek failed after {self.retries + 1} attempts: {last}")

    def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult:
        return OfferResult(self._call(OFFER_SYSTEM_PROMPT, offer_user_message(docs), OfferExtraction), self.model)

    def extract_term_sheet(self, doc: SourceDocument) -> TermSheetResult:
        return TermSheetResult(
            self._call(TERM_SHEET_SYSTEM_PROMPT, term_sheet_user_message(doc), TermSheetExtraction), self.model
        )

    def extract_contract(self, chunk: SourceDocument) -> ContractResult:
        return ContractResult(
            self._call(CONTRACT_SYSTEM_PROMPT, contract_user_message(chunk), ContractExtraction), self.model
        )
