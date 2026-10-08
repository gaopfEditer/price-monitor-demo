from __future__ import annotations

import json
from typing import Any

import httpx

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


def extract_field(text: str, field: str, selectors: dict[str, str] | None = None) -> dict[str, Any]:
    """Rules-first extraction; LLM only when configured."""
    selectors = selectors or {}
    if field in selectors:
        import re

        m = re.search(selectors[field], text, re.I | re.S)
        if m:
            return {"value": m.group(1).strip(), "evidence": m.group(0)[:200], "source": "regex"}
    if not LLM_API_KEY or not LLM_BASE_URL:
        return {"value": "Not disclosed", "evidence": "", "source": "offline_fallback"}
    prompt = f"Extract {field} from snippet. Return JSON {{value, evidence}}. Snippet:\n{text[:1500]}"
    try:
        with httpx.Client(timeout=20) as client:
            r = client.post(
                f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}]},
            )
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            if not parsed.get("evidence"):
                return {"value": "Not disclosed", "evidence": "", "source": "llm_rejected"}
            return {**parsed, "source": "llm"}
    except Exception:
        return {"value": "Not disclosed", "evidence": "", "source": "llm_error"}
