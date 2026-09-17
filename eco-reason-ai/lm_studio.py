"""Small OpenAI-compatible client for a local LM Studio server."""

from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


def generate_answer(assessment: dict, timeout: float = 8.0) -> str | None:
    """Ask the configured local model to explain an existing assessment.

    The model receives retrieved evidence and must not invent citations. The
    structured assessment remains authoritative if LM Studio is unavailable.
    """
    base_url = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
    model = os.getenv("LM_STUDIO_MODEL", "gemma-3-1b")
    prompt = {
        "role": "user",
        "content": (
            "You are EcoReason AI, an environmental scientist. Explain the assessment below "
            "in concise Markdown. Keep the recommendation, impacted metrics, time horizons, "
            "and evidence IDs exactly grounded in the supplied data. Do not invent studies, "
            "numbers, or citations. Mention that field measurements should validate projections.\n\n"
            + json.dumps(assessment, indent=2)
        ),
    }
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps({"model": model, "temperature": 0.2, "messages": [prompt]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
        return payload["choices"][0]["message"]["content"]
    except (KeyError, TypeError, ValueError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None