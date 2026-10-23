"""Provider-compatible structured output for the DeepSeek OpenAI-compatible API."""

from __future__ import annotations

import inspect
import json
from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import SystemMessage
from pydantic import ValidationError


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


def invoke_deepseek_json(
    model: Any,
    schema: type,
    instructions: str,
    messages: list,
    *,
    max_attempts: int = 2,
):
    """Invoke JSON mode with one bounded retry for malformed model output."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    structured, output_prompt = deepseek_json_output(model, schema, instructions)
    invocation_messages = [SystemMessage(content=output_prompt), *messages]
    for attempt in range(1, max_attempts + 1):
        try:
            raw = structured.invoke(invocation_messages)
            parsed = raw if isinstance(raw, schema) else schema.model_validate(raw)
            return parsed, attempt
        except (OutputParserException, ValidationError, json.JSONDecodeError):
            if attempt == max_attempts:
                raise
            invocation_messages = [
                *invocation_messages,
                SystemMessage(
                    content=(
                        "The previous output was invalid. Return one complete JSON object "
                        "matching the schema exactly."
                    )
                ),
            ]
    raise AssertionError("unreachable")
