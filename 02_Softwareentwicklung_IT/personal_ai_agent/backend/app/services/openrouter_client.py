"""
OpenRouter Hardened Client mit ZDR-Erzwingung (openrouter_client.py).

Spezifikation Modul D (30.10.2026):
Erzwingt in jedem Payload strikt die Provider-Vorgaben:
  "provider": {
      "data_collection": "deny",
      "zdr": True,
      "allow_fallbacks": True
  }

Eigenschaften:
  - Kein API-Aufruf kann die ZDR-Garantie (Zero Data Retention) umgehen.
  - Unterstuetzt synchrones Requesting und Server-Sent Events (SSE) Streaming.
  - Optionale nahtlose Kopplung mit PIIShield fuer automatische Pre-Flight-Maskierung
    und Stream-Entschluesselung.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Generator, List, Optional, Union

import httpx

from app.services.pii_shield import PIIShield

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
STANDARD_TIMEOUT = 30.0

MANDATORY_PROVIDER_CONFIG = {
    "data_collection": "deny",
    "zdr": True,
    "allow_fallbacks": True,
}


class ZDREnforcementError(Exception):
    """Wird geworfen, wenn ein Aufruf versucht, die ZDR-Sicherheitsregeln aufzuweichen."""
    pass


def haerte_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Prueft und erzwingt zwingend die ZDR- und Datenschutz-Parameter."""
    gehaertet = dict(payload)

    # Wenn der Aufrufer explizit versucht, ZDR zu deaktivieren -> Verweigern
    benutzer_provider = gehaertet.get("provider", {})
    if isinstance(benutzer_provider, dict):
        if benutzer_provider.get("data_collection") == "allow":
            raise ZDREnforcementError("data_collection='allow' ist strikt verboten!")
        if benutzer_provider.get("zdr") is False:
            raise ZDREnforcementError("zdr=False ist strikt verboten!")

    # Erzeuge den geschuetzten Provider-Block
    provider = dict(benutzer_provider) if isinstance(benutzer_provider, dict) else {}
    provider.update(MANDATORY_PROVIDER_CONFIG)
    gehaertet["provider"] = provider

    return gehaertet


class OpenRouterZDRClient:
    """HTTP-Client fuer OpenRouter mit strikt erzwungenem Zero-Data-Retention-Schutz."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = OPENROUTER_BASE_URL,
        timeout: float = STANDARD_TIMEOUT,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://personal-ai.local",
            "X-Title": "Personal AI Agent (Privacy Hardened)",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Sendet einen Chat-Request an OpenRouter mit erzwungenem ZDR."""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra_payload:
            payload.update(extra_payload)

        sicherer_payload = haerte_payload(payload)
        url = f"{self.base_url}/chat/completions"

        if self._client:
            res = self._client.post(url, json=sicherer_payload, headers=self._get_headers(), timeout=self.timeout)
            res.raise_for_status()
            return res.json()

        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(url, json=sicherer_payload, headers=self._get_headers())
            res.raise_for_status()
            return res.json()

    def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """Streamt Antwort-Chunks von OpenRouter mit erzwungenem ZDR."""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra_payload:
            payload.update(extra_payload)

        sicherer_payload = haerte_payload(payload)
        url = f"{self.base_url}/chat/completions"

        client_ctx = self._client if self._client else httpx.Client(timeout=self.timeout)
        try:
            with client_ctx.stream("POST", url, json=sicherer_payload, headers=self._get_headers()) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    daten_str = line[6:].strip()
                    if daten_str == "[DONE]":
                        break
                    try:
                        daten = json.loads(daten_str)
                        choices = daten.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
        finally:
            if not self._client:
                client_ctx.close()

    def chat_shielded(
        self,
        messages: List[Dict[str, str]],
        model: str,
        shield: PIIShield,
        stream: bool = False,
        **kwargs,
    ) -> Union[str, Generator[str, None, None]]:
        """End-to-End geschuetzter Chat: Maskiert vor dem Senden, dekodiert nach dem Empfang."""
        geschuetzte_nachrichten = []
        for m in messages:
            geschuetzte_nachrichten.append({
                "role": m.get("role", "user"),
                "content": shield.encode(m.get("content", "")),
            })

        if stream:
            roher_stream = self.chat_completion_stream(geschuetzte_nachrichten, model=model, **kwargs)
            return shield.decode_stream(roher_stream)
        else:
            antwort = self.chat_completion(geschuetzte_nachrichten, model=model, **kwargs)
            choices = antwort.get("choices", [])
            roher_text = choices[0]["message"]["content"] if choices else ""
            return shield.decode(roher_text)
