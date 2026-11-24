"""Minimal async-free Ollama client (local models only, no paid APIs).

All failures are converted into ``AIUnavailableError`` with an actionable message
so the rest of the app can degrade gracefully to deterministic logic.
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.errors import AIUnavailableError

log = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclass
class AIStatus:
    reachable: bool
    models: list[str]
    chat_model: str
    chat_model_installed: bool
    embedding_model: str
    embedding_model_installed: bool
    message: str


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        embedding_model: str | None = None,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
        enabled: bool = True,
    ):
        s = get_settings()
        self.base_url = (base_url or s.ollama_base_url).rstrip("/")
        self.model = model or s.default_model
        self.embedding_model = embedding_model or s.embedding_model
        self.timeout = timeout or s.ai_timeout_seconds
        self._transport = transport
        self.enabled = enabled

    # ------------------------------------------------------------------ http
    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout, transport=self._transport)

    def _request(self, method: str, path: str, **kw) -> dict:
        if not self.enabled:
            raise AIUnavailableError("AI features are turned off in AI Settings.")
        try:
            with self._client() as c:
                r = c.request(method, path, **kw)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise AIUnavailableError(
                "Ollama is not running. Install it from https://ollama.com and start it "
                "(`ollama serve`), or disable AI features in AI Settings."
            ) from exc
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"Could not talk to Ollama: {type(exc).__name__}") from exc
        if r.status_code == 404:
            raise AIUnavailableError(
                f"Model not found. Run `ollama pull {self.model}` (and "
                f"`ollama pull {self.embedding_model}` for semantic matching)."
            )
        if r.status_code >= 400:
            raise AIUnavailableError(f"Ollama returned HTTP {r.status_code}.")
        try:
            return r.json()
        except ValueError as exc:
            raise AIUnavailableError("Ollama returned an invalid response.") from exc

    # ---------------------------------------------------------------- status
    def status(self) -> AIStatus:
        try:
            data = self._request("GET", "/api/tags")
        except AIUnavailableError as exc:
            return AIStatus(False, [], self.model, False, self.embedding_model, False, exc.message)
        names = [m.get("name", "") for m in data.get("models", [])]

        def has(n: str) -> bool:
            return any(x == n or x.split(":")[0] == n.split(":")[0] and (":" not in n or x == n) for x in names)

        chat_ok, emb_ok = has(self.model), has(self.embedding_model)
        msg = "Ready" if chat_ok else f"Model '{self.model}' not installed: run `ollama pull {self.model}`"
        return AIStatus(True, names, self.model, chat_ok, self.embedding_model, emb_ok, msg)

    # ------------------------------------------------------------------ chat
    def chat(self, system: str, user: str, *, json_mode: bool = False, temperature: float = 0.3) -> str:
        payload: dict = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"
        data = self._request("POST", "/api/chat", json=payload)
        content = (data.get("message") or {}).get("content", "")
        return _THINK_RE.sub("", content).strip()

    def chat_json(self, system: str, user: str, temperature: float = 0.2) -> dict:
        raw = self.chat(system, user, json_mode=True, temperature=temperature)
        parsed = extract_json(raw)
        if parsed is None:
            raise AIUnavailableError("The model returned output that was not valid JSON.")
        return parsed

    # ------------------------------------------------------------ embeddings
    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._request("POST", "/api/embed", json={"model": self.embedding_model, "input": texts})
        vectors = data.get("embeddings")
        if not vectors or len(vectors) != len(texts):
            raise AIUnavailableError("Embedding model returned an unexpected response.")
        return vectors


def extract_json(raw: str) -> dict | None:
    raw = _THINK_RE.sub("", raw).strip()
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else None
    except ValueError:
        pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            v = json.loads(m.group(0))
            return v if isinstance(v, dict) else None
        except ValueError:
            return None
    return None


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


_client_override: OllamaClient | None = None
_runtime: dict = {"enabled": True, "model": None, "embedding_model": None}
transport_override: httpx.BaseTransport | None = None  # tests only


def configure_runtime(cfg: dict) -> None:
    """Apply the user's saved AI settings (model names, enable switch) to every future call."""
    _runtime.update(
        enabled=bool(cfg.get("enabled", True)),
        model=(cfg.get("model") or None),
        embedding_model=(cfg.get("embedding_model") or None),
    )


def get_ai() -> OllamaClient:
    """Return the shared client (overridable in tests); honours saved AI settings."""
    if _client_override:
        return _client_override
    return OllamaClient(model=_runtime["model"], embedding_model=_runtime["embedding_model"],
                        enabled=_runtime["enabled"], transport=transport_override)


def set_ai_override(client: OllamaClient | None) -> None:
    global _client_override
    _client_override = client
