"""Provider-compatible structured output for the DeepSeek OpenAI-compatible API."""

from __future__ import annotations

import inspect
import json
from typing import Any


def deepseek_json_output(model: Any, schema: type, instructions: str):
    """Return a JSON-mode parser and an explicit schema-bearing system prompt.

    Older dependency-injected fakes often expose only ``(schema)``. Preserve that
    test seam while selecting JSON mode whenever the model supports its method option.
    """
    method = model.with_structured_output
    parameters = inspect.signature(method).parameters.values()
    supports_method = any(
        parameter.name == "method" or parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )
    structured = method(schema, **({"method": "json_mode"} if supports_method else {}))
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
    prompt = (
        f"{instructions}\n\n"
        "Return valid json only, as one JSON object. Match this exact schema, including every "
        "field name and the exact allowed enum values; do not invent labels:\n"
        f"{schema_json}"
    )
    return structured, prompt
