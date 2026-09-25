"""Tests: Spracheingabe des Agents (Erkennung + Glättung).

Anlass: Am 25.09.2026 fiel auf, dass die Glättung wochenlang still ausfiel —
das Modell `google/gemini-2.0-flash-001` war bei OpenRouter abgekündigt (404),
und weil kein Test und keine Warnung das meldete, fiel es nicht auf. Genau wie
in typeFREE. Diese Tests halten die Kette, den Rückfallweg und die Regeln fest.
"""
import os
import sys
import types

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.llm_service import (  # noqa: E402
    LLMService,
    POLISH_ANWEISUNG,
    POLISH_MODELS,
    TRANSCRIBE_MODELS,
    WHISPER_VOKABULAR,
)

WAV = b"RIFF" + b"\x00" * 200          # gültiger WAV-Kopf (Magic Bytes)
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200


class Erkennung:
    """Attrappe des Transkriptions-Endpunkts — merkt sich Modell und Parameter."""

    def __init__(self, antworten):
        self.antworten = antworten      # Modell -> Text oder Ausnahme
        self.aufrufe = []

    def create(self, **felder):
        puffer = felder.pop("file")
        self.aufrufe.append({
            "modell": felder.get("model"),
            "felder": dict(felder),
            "name": getattr(puffer, "name", None),
            "bytes": puffer.read(),
        })
        wert = self.antworten.get(felder.get("model"), Exception("unerwartetes Modell"))
        if isinstance(wert, Exception):
            raise wert
        return types.SimpleNamespace(text=wert)


class Chat:
    """Attrappe des Chat-Endpunkts für die Glättung."""

    def __init__(self, antworten):
        self.antworten = antworten      # Modell -> Text oder Ausnahme
        self.aufrufe = []

    def create(self, **felder):
        self.aufrufe.append({
            "modell": felder.get("model"),
            "anweisung": felder["messages"][0]["content"],
            "text": felder["messages"][1]["content"],
        })
        wert = self.antworten.get(felder.get("model"), Exception("unerwartetes Modell"))
        if isinstance(wert, Exception):
            raise wert
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=wert))],
        )


def dienst_mit(erkennung=None, chat=None):
    """LLMService mit Attrappen als Client (kein Schlüssel, kein Netz)."""
    dienst = LLMService()
    dienst.api_key = "nur-fuer-den-test"
    dienst.client = types.SimpleNamespace(
        audio=types.SimpleNamespace(transcriptions=erkennung or Erkennung({})),
        chat=types.SimpleNamespace(completions=chat or Chat({})),
    )
    return dienst


# ── Anweisung: Anrede, Sprechakt, Fachbegriffe ───────────────────────────────

def test_anweisung_haelt_anrede_und_sprechakt_fest():
    assert "ANREDE UND BLICKWINKEL BLEIBEN" in POLISH_ANWEISUNG
    assert "SPRECHAKT BLEIBT" in POLISH_ANWEISUNG
    assert "Die Anredeform oder den Sprechakt ändern." in POLISH_ANWEISUNG


def test_anweisung_verbietet_erzaehl_und_fragestil():
    assert "KEIN ERZÄHL- ODER FRAGESTIL" in POLISH_ANWEISUNG
    assert "erzählst nicht nach" in POLISH_ANWEISUNG


def test_anweisung_haelt_fachbegriffe_und_denglisch():
    assert "FACHBEGRIFFE UND DENGLISCH BLEIBEN" in POLISH_ANWEISUNG
    assert "'deployen' bleibt 'deployen'" in POLISH_ANWEISUNG
    assert "'Comet' ist der Browser" in POLISH_ANWEISUNG
    assert "'Commit' die Git-Aktion" in POLISH_ANWEISUNG


# ── Modellketten ─────────────────────────────────────────────────────────────

def test_glattungsmodelle_enthalten_kein_abgekuendigtes_modell():
    # `google/gemini-2.0-flash-001` war der stille Ausfall — er darf nicht
    # zurückkommen, und es muss einen Ausweichweg geben.
    assert "google/gemini-2.0-flash-001" not in POLISH_MODELS
    assert len(POLISH_MODELS) >= 2


def test_erkennungswege_haben_einen_rueckfall():
    assert len(TRANSCRIBE_MODELS) >= 2
    assert TRANSCRIBE_MODELS[0][0] == "microsoft/mai-transcribe-1.5"
    assert TRANSCRIBE_MODELS[1][0] == "openai/whisper-large-v3"


# ── Erkennung ────────────────────────────────────────────────────────────────

def test_erkennung_faellt_auf_ausweichmodell_zurueck():
    erkennung = Erkennung({
        TRANSCRIBE_MODELS[0][0]: Exception("HTTP 429"),
        TRANSCRIBE_MODELS[1][0]: "Der Commit ist durch.",
    })
    text = dienst_mit(erkennung=erkennung).transcribe(WAV)

    assert text == "Der Commit ist durch."
    assert [a["modell"] for a in erkennung.aufrufe] == [
        TRANSCRIBE_MODELS[0][0], TRANSCRIBE_MODELS[1][0]]


def test_ausweichweg_bekommt_sprache_und_vokabular():
    erkennung = Erkennung({
        TRANSCRIBE_MODELS[0][0]: Exception("HTTP 500"),
        TRANSCRIBE_MODELS[1][0]: "Alles gut.",
    })
    dienst_mit(erkennung=erkennung).transcribe(WAV)

    erster, zweiter = erkennung.aufrufe
    # mai-transcribe kennt weder language noch prompt — nichts erzwingen.
    assert "language" not in erster["felder"]
    assert "prompt" not in erster["felder"]
    # Der Rückfallweg schon: deutsche Sprache und die Fachwörter.
    assert zweiter["felder"]["language"] == "de"
    assert zweiter["felder"]["prompt"] == WHISPER_VOKABULAR


def test_erkennung_schickt_frischen_puffer_je_versuch():
    """Zweiter Versuch mit demselben Puffer hätte 0 Bytes geschickt."""
    erkennung = Erkennung({
        TRANSCRIBE_MODELS[0][0]: Exception("HTTP 500"),
        TRANSCRIBE_MODELS[1][0]: "Weiter.",
    })
    dienst_mit(erkennung=erkennung).transcribe(WAV)

    assert all(a["bytes"] for a in erkennung.aufrufe)
    assert [a["name"] for a in erkennung.aufrufe] == ["audio.wav", "audio.wav"]


def test_erkennung_erkennt_webm():
    erkennung = Erkennung({TRANSCRIBE_MODELS[0][0]: "Text."})
    dienst_mit(erkennung=erkennung).transcribe(WEBM)

    assert erkennung.aufrufe[0]["name"] == "audio.webm"


def test_erkennung_liefert_none_wenn_alle_wege_scheitern():
    erkennung = Erkennung({
        TRANSCRIBE_MODELS[0][0]: Exception("HTTP 429"),
        TRANSCRIBE_MODELS[1][0]: Exception("HTTP 503"),
    })
    assert dienst_mit(erkennung=erkennung).transcribe(WAV) is None
    assert len(erkennung.aufrufe) == 2


def test_erkennung_verwirft_leeren_text_und_nimmt_den_rueckfall():
    erkennung = Erkennung({
        TRANSCRIBE_MODELS[0][0]: "   ",
        TRANSCRIBE_MODELS[1][0]: "Doch noch Text.",
    })
    assert dienst_mit(erkennung=erkennung).transcribe(WAV) == "Doch noch Text."


# ── Glättung ─────────────────────────────────────────────────────────────────

def test_glattung_rueckt_bei_fehler_vor():
    chat = Chat({
        POLISH_MODELS[0]: Exception("HTTP 404 – Modell abgekündigt"),
        POLISH_MODELS[1]: "Der Commit ist durch.",
    })
    text = dienst_mit(chat=chat).polish_text("Ähm, der Commit ist durch.")

    assert text == "Der Commit ist durch."
    assert [a["modell"] for a in chat.aufrufe] == [POLISH_MODELS[0], POLISH_MODELS[1]]


def test_glattung_verwirft_unplausible_antwort_und_nimmt_das_naechste_modell():
    langer_text = "Ähm, " + "das ist ein langer gesprochener Satz. " * 8
    erwartet = ("Das ist ein langer gesprochener Satz. " * 8).strip()
    chat = Chat({
        POLISH_MODELS[0]: "Ja.",
        POLISH_MODELS[1]: erwartet,
    })
    text = dienst_mit(chat=chat).polish_text(langer_text)

    assert text == erwartet
    assert len(chat.aufrufe) == 2


def test_glattung_liefert_none_wenn_alle_modelle_scheitern():
    chat = Chat({m: Exception("HTTP 503") for m in POLISH_MODELS})
    assert dienst_mit(chat=chat).polish_text("Ähm, irgendein Text.") is None
    assert len(chat.aufrufe) == len(POLISH_MODELS)


def test_glattung_schickt_die_anweisung_mit():
    chat = Chat({POLISH_MODELS[0]: "Text."})
    dienst_mit(chat=chat).polish_text("Ähm, Text.")

    assert chat.aufrufe[0]["anweisung"] == POLISH_ANWEISUNG
    assert "Ähm, Text." in chat.aufrufe[0]["text"]


def test_glattung_ohne_text_fragt_niemanden():
    chat = Chat({POLISH_MODELS[0]: "Text."})
    assert dienst_mit(chat=chat).polish_text("") is None
    assert chat.aufrufe == []


# ── Vokabular ────────────────────────────────────────────────────────────────

def test_vokabular_enthaelt_fachbegriffe_und_denglisch():
    for begriff in ("Repository", "Commit", "Comet", "Azure", "Entra ID",
                    "Key Vault", "Board", "Sprint", "Termux"):
        assert begriff in WHISPER_VOKABULAR


def test_vokabular_bleibt_kurz_genug():
    """Whisper schneidet einen zu langen prompt STILL ab (Grenze 224 Tokens)."""
    assert len(WHISPER_VOKABULAR) < 700
