"""Grounded local Ollama extraction for fields rules could not resolve."""

import json
import os
import re
from urllib.request import Request, urlopen

_FIELD_CONTEXT = {
    "entity_name": r"(?:entity|company|to\s+(?:the\s+)?members\s+of)",
    "auditor_firm": r"(?:auditor|chartered\s+accountant)",
    "balance_sheet_date": r"balance\s+sheet\s+as\s+at",
    "as_on_date": r"as\s+on|as\s+at",
    "report_date": r"report\s+date|date",
    "revenue": r"revenue",
    "expenses": r"expenses?",
    "profit_before_tax": r"profit\s+before\s+tax",
    "profit": r"(?:net\s+profit|profit(?:\s*\(loss\))?\s+for\s+the\s+year)",
}


def _is_grounded(field: str, value: object, source_text: str) -> bool:
    """Require literal occurrence plus nearby field-specific source context."""
    needle = re.sub(r"\s+", " ", str(value)).casefold()
    source_norm = re.sub(r"\s+", " ", source_text).casefold()
    if not needle or needle not in source_norm:
        return False
    if field.endswith("date") and not re.search(r"\b\d{4}\b", needle):
        return False
    context_pattern = _FIELD_CONTEXT.get(field)
    if context_pattern is None:
        return True
    for match in re.finditer(re.escape(needle), source_norm):
        left = source_norm[max(0, match.start() - 120) : match.start()]
        right = source_norm[match.end() : match.end() + 120]
        if re.search(context_pattern, left + " " + needle + " " + right, re.I):
            return True
    return False


def extract_missing_fields(
    source_text: str, missing_fields: list[str]
) -> dict[str, object]:
    """Ask a local Ollama model for strict JSON and reject ungrounded values.

    The local service must be running and the configured model must already be
    available. Any model/service error raises RuntimeError for the pipeline to
    report in the document result.
    """
    if not missing_fields:
        return {}
    model = os.getenv("FEXTRACT_LLM_MODEL", "qwen2.5:3b")
    url = os.getenv("FEXTRACT_OLLAMA_URL", "http://localhost:11434").rstrip("/")
    if not url.endswith("/api/generate"):
        url += "/api/generate"
    prompt = (
        "Extract only requested values explicitly present in SOURCE. Return a JSON object "
        "with exactly these keys; use null when absent. Do not infer.\nKEYS: "
        + json.dumps(missing_fields)
        + "\nSOURCE:\n"
        + source_text[:24000]
    )
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
    ).encode()
    request = Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=180) as response:
            result = json.loads(response.read())
        values = json.loads(result["response"])
    except Exception as exc:
        raise RuntimeError(f"Ollama extraction unavailable ({model}): {exc}") from exc
    grounded = {}
    for key in missing_fields:
        value = values.get(key)
        if value is None or not isinstance(value, (str, int, float)):
            continue
        if _is_grounded(key, value, source_text):
            grounded[key] = value
    return grounded
