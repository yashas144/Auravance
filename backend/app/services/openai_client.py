from __future__ import annotations

import json
import os
from functools import lru_cache

from openai import APIConnectionError, APIError, OpenAI, RateLimitError

from app.core.config import settings


class OpenAIRagError(RuntimeError):
    pass


def has_openai_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    if not has_openai_api_key():
        raise OpenAIRagError(
            "OPENAI_API_KEY is not set. Configure it as an environment variable before using OpenAI-backed RAG."
        )
    return OpenAI()


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    try:
        response = _client().embeddings.create(
            model=settings.rag_embedding_model,
            input=texts,
            dimensions=settings.rag_embedding_dimensions,
            encoding_format="float",
        )
    except (APIConnectionError, APIError, RateLimitError) as exc:
        raise OpenAIRagError(f"Embedding request failed: {exc}") from exc

    return [list(item.embedding) for item in response.data]


def generate_root_cause_analysis(payload: dict) -> dict:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "grounded_summary": {"type": "string"},
            "likely_causes": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 4,
            },
            "recommended_actions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 4,
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
        },
        "required": [
            "grounded_summary",
            "likely_causes",
            "recommended_actions",
            "confidence",
        ],
    }

    instructions = (
        "You are an industrial reliability engineer performing root cause analysis. "
        "Return JSON only. Use only the retrieved evidence and supplied prediction context. "
        "Do not invent manuals, asset facts, or maintenance steps that are not grounded in the evidence. "
        "If evidence is weak, say so in the grounded_summary and lower confidence."
    )

    try:
        response = _client().responses.create(
            model=settings.rag_response_model,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=True),
            temperature=settings.rag_generation_temperature,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "root_cause_analysis",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
    except (APIConnectionError, APIError, RateLimitError) as exc:
        raise OpenAIRagError(f"Generation request failed: {exc}") from exc

    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIRagError("OpenAI response did not return valid JSON.") from exc
