from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


ALLOWED_OLLAMA_MODELS = {"gemma3:1b", "gemma3:4b"}


@dataclass
class OllamaUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0


class OllamaBackend:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.usage = OllamaUsage()

    @staticmethod
    def model_tag(backend_name: str) -> str:
        if not backend_name.startswith("ollama/"):
            raise ValueError(f"Unsupported backend: {backend_name}")
        tag = backend_name.split("/", 1)[1]
        if tag not in ALLOWED_OLLAMA_MODELS:
            raise ValueError(
                "This PoC intentionally constrains Ollama backends to "
                "`gemma3:1b` and `gemma3:4b`."
            )
        return tag

    def complete_json(
        self,
        *,
        backend_name: str,
        system_prompt: str,
        user_prompt: str,
        seed: int,
    ) -> dict[str, Any] | None:
        model = self.model_tag(backend_name)
        request_payload = {
            "model": model,
            "format": "json",
            "stream": False,
            "system": system_prompt,
            "prompt": user_prompt,
            "options": {
                "temperature": self.config["backend"].get("temperature", 0),
                "seed": seed,
                "num_predict": self.config["backend"].get("max_tokens", 96),
            },
        }
        request = urllib.request.Request(
            url=self.config["backend"]["ollama_url"].rstrip("/") + "/api/generate",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout = self.config["backend"].get("request_timeout_s", 45)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None
        self.usage.calls += 1
        self.usage.prompt_tokens += int(raw_payload.get("prompt_eval_count", 0))
        self.usage.completion_tokens += int(raw_payload.get("eval_count", 0))
        response_text = raw_payload.get("response", "").strip()
        if not response_text:
            return None
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return None
