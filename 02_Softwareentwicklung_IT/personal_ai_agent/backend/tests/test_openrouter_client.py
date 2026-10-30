import json
import httpx
import pytest

from app.services.openrouter_client import (
    MANDATORY_PROVIDER_CONFIG,
    OpenRouterZDRClient,
    ZDREnforcementError,
    haerte_payload,
)
from app.services.pii_shield import PIIShield


def test_haerte_payload_enforcement():
    payload = {"model": "deepseek/deepseek-chat", "messages": [{"role": "user", "content": "Hallo"}]}
    gehaertet = haerte_payload(payload)

    assert "provider" in gehaertet
    assert gehaertet["provider"] == MANDATORY_PROVIDER_CONFIG
    assert gehaertet["provider"]["data_collection"] == "deny"
    assert gehaertet["provider"]["zdr"] is True
    assert gehaertet["provider"]["allow_fallbacks"] is True


def test_haerte_payload_verweigert_unsichere_einstellungen():
    # Versuch 1: data_collection auf allow
    with pytest.raises(ZDREnforcementError, match="data_collection='allow' ist strikt verboten"):
        haerte_payload({"provider": {"data_collection": "allow"}})

    # Versuch 2: zdr auf False
    with pytest.raises(ZDREnforcementError, match="zdr=False ist strikt verboten"):
        haerte_payload({"provider": {"zdr": False}})


def test_chat_completion_mit_mock_transport():
    empfangener_body = None

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal empfangener_body
        empfangener_body = json.loads(request.content.decode("utf-8"))
        assert request.headers["Authorization"] == "Bearer test-key-123"
        assert request.headers["HTTP-Referer"] == "https://personal-ai.local"

        antwort_daten = {
            "id": "gen-123",
            "choices": [{"message": {"role": "assistant", "content": "Hallo zurück!"}}],
        }
        return httpx.Response(200, json=antwort_daten)

    transport = httpx.MockTransport(mock_handler)
    mock_http_client = httpx.Client(transport=transport)

    client = OpenRouterZDRClient(api_key="test-key-123", client=mock_http_client)
    res = client.chat_completion(
        messages=[{"role": "user", "content": "Test"}],
        model="google/gemini-2.5-flash",
    )

    assert res["choices"][0]["message"]["content"] == "Hallo zurück!"
    assert empfangener_body is not None
    assert empfangener_body["provider"]["data_collection"] == "deny"
    assert empfangener_body["provider"]["zdr"] is True


def test_chat_shielded_end_to_end_datenschutz():
    empfangener_body = None

    def mock_llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal empfangener_body
        empfangener_body = json.loads(request.content.decode("utf-8"))
        gesendeter_prompt = empfangener_body["messages"][0]["content"]

        # STRIKT PRUEFEN: Der echte Name 'Sebastian' darf NIEMALS im Request-Body ankommen!
        assert "Sebastian" not in gesendeter_prompt
        assert "[PERSON_01]" in gesendeter_prompt

        # Das LLM antwortet mit dem Token
        antwort = {
            "choices": [{
                "message": {"role": "assistant", "content": "Guten Tag [PERSON_01], wie kann ich helfen?"}
            }]
        }
        return httpx.Response(200, json=antwort)

    transport = httpx.MockTransport(mock_llm_handler)
    mock_http_client = httpx.Client(transport=transport)

    shield = PIIShield()
    shield.register_person("Sebastian")

    client = OpenRouterZDRClient(api_key="secret-key", client=mock_http_client)
    ergebnis_text = client.chat_shielded(
        messages=[{"role": "user", "content": "Hallo, ich bin Sebastian."}],
        model="deepseek/deepseek-chat",
        shield=shield,
        stream=False,
    )

    # Der Benutzer erhaelt lokal wieder seinen echten Namen zurueck
    assert ergebnis_text == "Guten Tag Sebastian, wie kann ich helfen?"
    assert empfangener_body["provider"]["zdr"] is True
