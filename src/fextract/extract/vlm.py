"""Optional local Ollama vision-language fallback for difficult page images."""

import base64
import json
import os
import re
from io import BytesIO
from urllib.request import Request, urlopen


def extract_from_image(
    image, missing_fields: list[str], source_text: str = ""
) -> dict[str, object]:
    """Query a configured local Ollama VLM and retain only source-grounded values."""
    model = os.getenv("FEXTRACT_VLM_MODEL")
    if not model:
        raise RuntimeError(
            "VLM unavailable: set FEXTRACT_VLM_MODEL to a locally installed vision model"
        )
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    prompt = (
        "Return strict JSON only, exactly requested keys, null if not visible. "
        "Never infer. Keys: " + json.dumps(missing_fields)
    )
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "images": [base64.b64encode(buffer.getvalue()).decode()],
            "options": {"temperature": 0},
        }
    ).encode()
    url = os.getenv("FEXTRACT_OLLAMA_URL", "http://localhost:11434").rstrip("/")
    if not url.endswith("/api/generate"):
        url += "/api/generate"
    req = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=180) as response:
            values = json.loads(json.loads(response.read())["response"])
    except Exception as exc:
        raise RuntimeError(
            f"Local VLM extraction unavailable ({model}): {exc}"
        ) from exc
    source = re.sub(r"\s+", " ", source_text).casefold()
    return {
        key: value
        for key, value in values.items()
        if key in missing_fields
        and value is not None
        and re.sub(r"\s+", " ", str(value)).casefold() in source
    }
