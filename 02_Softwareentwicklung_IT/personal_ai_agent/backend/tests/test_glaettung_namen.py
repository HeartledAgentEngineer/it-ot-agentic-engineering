"""Glättung maskiert Namen wirklich (03.11.2026) — erfundene Namen, kein Netz.

Befund: ``polish_text`` registrierte nur volle Namen und die in Umschrift aus
``bekannte_namen_streng`` („juergen testmueller"). Der Schild sucht ohne Umschrift —
„Jürgen" ging so im Klartext raus, ein Vorname allein ohnehin.
"""
import types

from app.services import werkzeuge
from app.services.llm_service import POLISH_MODELS, LLMService


class Chat:
    def __init__(self, antwort):
        self.antwort = antwort
        self.texte = []

    def create(self, **felder):
        self.texte.append(felder["messages"][1]["content"])
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=self.antwort))])


class Echo(Chat):
    """Gibt den maskierten Text zurück — prüft Hin- und Rückweg ohne Kürzelnummern."""

    def __init__(self):
        super().__init__("")

    def create(self, **felder):
        self.antwort = felder["messages"][1]["content"].split("\n\n", 1)[-1]
        return super().create(**felder)


def _dienst(chat):
    dienst = LLMService()
    dienst.api_key = "nur-fuer-den-test"
    dienst.client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=chat))
    return dienst


def test_vorname_mit_umlaut_geht_nur_maskiert_raus(monkeypatch):
    monkeypatch.setattr(werkzeuge, "namen_fuer_maskierung", lambda: ["Jürgen Testmüller"])
    chat = Chat("Ich treffe [PERSON_02] morgen.")
    text = _dienst(chat).polish_text("Ähm, ich treffe jürgen morgen.")
    assert chat.texte and "jürgen" not in chat.texte[0].lower()
    assert text == "Ich treffe jürgen morgen."          # Schreibweise wie gesprochen


def test_voller_name_und_nachname(monkeypatch):
    monkeypatch.setattr(werkzeuge, "namen_fuer_maskierung", lambda: ["Zoë Probe"])
    chat = Chat("[PERSON_01] und Frau [PERSON_03] kommen.")
    _dienst(chat).polish_text("Also Zoë Probe und äh Frau Probe kommen.")
    assert "Zoë" not in chat.texte[0] and "Probe" not in chat.texte[0]


def test_umschrift_im_satz_wird_auch_maskiert(monkeypatch):
    monkeypatch.setattr(werkzeuge, "namen_fuer_maskierung", lambda: ["Jürgen Testmüller"])
    chat = Echo()
    text = _dienst(chat).polish_text("Ich treffe Juergen und äh Herrn Testmueller.")
    assert "juergen" not in chat.texte[0].lower() and "testmueller" not in chat.texte[0].lower()
    assert text == "Ich treffe Juergen und äh Herrn Testmueller."


def test_ohne_namensliste_geht_nichts_raus(monkeypatch):
    # Hermes-Einwand #19 (03.11.2026): wie Websuche und Alltagsprotokoll fail-closed —
    # der Rohtext bleibt lokal, statt ungeschützt geglättet zu werden.
    monkeypatch.setattr(werkzeuge, "namen_fuer_maskierung", lambda: None)
    chat = Chat("Der Commit ist durch.")
    assert _dienst(chat).polish_text("Ähm, der Commit ist durch.") is None
    assert chat.texte == [] and POLISH_MODELS


def test_kaputte_namensquelle_geht_nichts_raus(monkeypatch):
    def kaputt():
        raise RuntimeError("kaputt")
    monkeypatch.setattr(werkzeuge, "namen_fuer_maskierung", kaputt)
    chat = Chat("x")
    assert _dienst(chat).polish_text("Ähm, Text.") is None and chat.texte == []
