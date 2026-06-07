from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class LLMUnavailable(RuntimeError):
    pass


class LLMQueryExpander:
    def __init__(self, cache_path: Path, model: str | None = None) -> None:
        self.cache_path = cache_path
        self.model = model or os.getenv("OPENAI_PROMPT_MODEL", "gpt-4.1-mini")
        self.cache = self._load_cache()

    def expand(self, query: str) -> dict[str, Any]:
        key = self._cache_key(query)
        if key in self.cache:
            return self.cache[key]
        if not os.getenv("OPENAI_API_KEY"):
            raise LLMUnavailable("OPENAI_API_KEY is not set")
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover
            raise LLMUnavailable(f"OpenAI Python SDK is not installed: {exc}") from exc

        client = OpenAI()
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "expanded_query": {"type": "string"},
                "query_variants": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 5,
                    "items": {"type": "string"},
                },
                "hyde_document": {"type": "string"},
            },
            "required": ["expanded_query", "query_variants", "hyde_document"],
        }
        prompt = (
            "Rewrite this AMI Meeting Corpus search query for retrieval. "
            "The corpus contains meeting transcripts about remote-control product design, project planning, "
            "market research, requirements, prototype evaluation, costs, user interfaces, displays, batteries, "
            "and final presentations. Return only grounded search text; do not invent meeting IDs, dates, "
            "speaker names, or facts. The HyDE document should sound like a plausible transcript excerpt but stay generic.\n\n"
            f"Query: {query}"
        )
        response = client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": "You produce concise retrieval rewrites as strict JSON."},
                {"role": "user", "content": prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "ami_query_expansion",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        payload = json.loads(response.output_text)
        result = {
            "model": self.model,
            "expanded_query": str(payload["expanded_query"]),
            "query_variants": [str(item) for item in payload["query_variants"]],
            "hyde_document": str(payload["hyde_document"]),
        }
        self.cache[key] = result
        self._write_cache()
        return result

    def _cache_key(self, query: str) -> str:
        raw = json.dumps({"model": self.model, "query": query}, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        if not self.cache_path.exists():
            return {}
        return json.loads(self.cache_path.read_text(encoding="utf-8"))

    def _write_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")