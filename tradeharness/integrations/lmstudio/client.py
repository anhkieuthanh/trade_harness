from __future__ import annotations

import json
from typing import Any

import requests

from tradeharness.domain.models import ToolRequest


class LMStudioClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def chat(self, prompt: str) -> str:
        response = self.complete(
            [
                {"role": "system", "content": "Return strict JSON only."},
                {"role": "user", "content": prompt},
            ]
        )
        return get_message_content(response)


def get_message_content(response: dict[str, Any]) -> str:
    return str(response["choices"][0]["message"].get("content", ""))


def extract_tool_requests(response: dict[str, Any]) -> list[ToolRequest]:
    message = response["choices"][0]["message"]
    native_tool_calls = message.get("tool_calls") or []
    if native_tool_calls:
        requests_out: list[ToolRequest] = []
        for tool_call in native_tool_calls:
            function = tool_call["function"]
            requests_out.append(
                ToolRequest(
                    name=str(function["name"]),
                    arguments=json.loads(function["arguments"]),
                    call_id=str(tool_call.get("id")) if tool_call.get("id") else None,
                )
            )
        return requests_out

    content = _strip_code_fences(str(message.get("content", "")).strip())
    if not content:
        return []
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return []
    if "tool" not in payload:
        return []
    return [
        ToolRequest(
            name=str(payload["tool"]),
            arguments=dict(payload.get("arguments", {})),
        )
    ]


def _strip_code_fences(content: str) -> str:
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return content
