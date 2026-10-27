"""Tests für die dynamischen Modellkataloge (`modelle.py`).

Alles läuft mit synthetischen Transporten – kein Netz, keine echten
Claude-/Codex-Aufrufe. Die Prozessbaum-Tests starten ausschließlich eigene
Python-Kindprozesse auf dem Testrechner; Fristen werden kurz gehalten.
"""
import ctypes
import dataclasses
import json
import signal
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import modelle, zustand

JETZT = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
KENNUNG = "master-schalter-testkennung"


@pytest.fixture
def daten(tmp_path, monkeypatch):
    ordner = tmp_path / "daten"
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(ordner))
    # Unabhängig von der echten Installation: feste Attrappen-Pfade (Transporte sind ohnehin Attrappen).
    monkeypatch.setenv("MASTER_SCHALTER_CLAUDE_CLI", "C:/werkzeug/fake-cli.js")
    monkeypatch.setenv("MASTER_SCHALTER_NODE", "C:/werkzeug/fake-node.exe")
    return ordner


# --- Hilfen ------------------------------------------------------------------

def _ausgang(inhalt: bytes, rc: int = 0) -> modelle.Ausgang:
    return modelle.Ausgang(rc, inhalt, b"")


def _codex_modell(slug="gpt-6-luna", name="GPT-6 Luna", sichtbar="list") -> dict:
    eintrag = {"slug": slug, "display_name": name}
    if sichtbar is not None:
        eintrag["visibility"] = sichtbar
    return eintrag


def _codex_zeile(*eintraege) -> bytes:
    return json.dumps({"models": list(eintraege)}, ensure_ascii=False).encode("utf-8")


def _transport_mit(inhalt: bytes, aufrufe: list | None = None):
    def transport(liste, umgebung, eingabe, frist):
        if aufrufe is not None:
            aufrufe.append((liste, umgebung, eingabe, frist))
        return _ausgang(inhalt)
    return transport


def _kennung(eingabe: bytes) -> str:
    return json.loads(eingabe.decode("utf-8").splitlines()[0])["request_id"]


def _claude_zeile(kennung: str, modelle_liste, *, subtype: str = "success",
                  art: str = "control_response", zusatz: dict | None = None) -> bytes:
    innen: dict = {"models": list(modelle_liste)}
    if zusatz:
        innen.update(zusatz)
    zeile = {"type": art, "response": {"subtype": subtype, "request_id": kennung, "response": innen}}
    return json.dumps(zeile, ensure_ascii=False).encode("utf-8")


def _claude_transport(modelle_liste, *, gesehen: list | None = None, zusatz: dict | None = None):
    def transport(liste, umgebung, eingabe, frist):
        if gesehen is not None:
            gesehen.append((liste, umgebung, eingabe, frist))
        antwort = _claude_zeile(_kennung(eingabe), modelle_liste, zusatz=zusatz)
        return _ausgang(antwort + b"\n")
    return transport


def _cache_schreiben(anbieter: dict) -> None:
    pfad = modelle.datei()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"version": 1, "anbieter": anbieter}, ensure_ascii=False), encoding="utf-8")


# --- Antwortformen, Filter, Deduplizierung -----------------------------------

def test_codex_antwortform_nur_visibility_list(daten):
    antwort = _codex_zeile(
        _codex_modell("gpt-6-luna", "GPT-6 Luna"),
        _codex_modell("intern-xy", "Intern", sichtbar="hidden"),
        {"slug": "ohne-sichtbarkeit", "display_name": "Ohne"},
    )

    k = modelle.aktualisieren("codex", transport=_transport_mit(antwort), jetzt=JETZT)

    assert k.fehler is None and k.veraltet is False and k.zeit == JETZT
    assert [(m.id, m.name) for m in k.modelle] == [("gpt-6-luna", "GPT-6 Luna")]
    assert modelle.lesen("codex", jetzt=JETZT) == k


def test_codex_dedupliziert_und_haelt_reihenfolge(daten):
    antwort = _codex_zeile(
        _codex_modell("b", "B"),
        _codex_modell("a", "A"),
        _codex_modell("b", "B zweitfassung"),
    )

    k = modelle.aktualisieren("codex", transport=_transport_mit(antwort), jetzt=JETZT)

    assert [(m.id, m.name) for m in k.modelle] == [("b", "B"), ("a", "A")]


def test_codex_name_faellt_auf_kennung_zurueck(daten):
    antwort = _codex_zeile(
        {"slug": "x", "display_name": 5, "visibility": "list"},
        {"slug": "y", "visibility": "list"},
        _codex_modell("z", "  Z mit Rand  "),
    )

    k = modelle.aktualisieren("codex", transport=_transport_mit(antwort), jetzt=JETZT)

    assert [(m.id, m.name) for m in k.modelle] == [("x", "x"), ("y", "y"), ("z", "Z mit Rand")]


def test_claude_antwortform_uebernimmt_value_und_displayname(daten):
    models = [
        {"value": "claude-opus-5.5", "displayName": "Opus 5.5", "unbekannt": "wird verworfen"},
        {"value": "claude-sonnet-5.5", "displayName": "Sonnet 5.5"},
    ]

    k = modelle.aktualisieren("claude", transport=_claude_transport(models), jetzt=JETZT)

    assert k.fehler is None and k.veraltet is False
    assert [(m.id, m.name) for m in k.modelle] == [
        ("claude-opus-5.5", "Opus 5.5"), ("claude-sonnet-5.5", "Sonnet 5.5")]


def test_claude_ignoriert_fremde_kennung_fehlerantwort_und_rohe_zeilen(daten):
    def transport(liste, umgebung, eingabe, frist):
        eigene = _kennung(eingabe)
        zeilen = [
            b"Meldung vom Kindprozess",
            b"{kaputt",
            b'{"type":"system","subtype":"init","session_id":"x"}',
            _claude_zeile("andere-kennung", [{"value": "fremd", "displayName": "Fremd"}]),
            _claude_zeile(eigene, [{"value": "x", "displayName": "X"}], subtype="error"),
        ]
        return _ausgang(b"\n".join(zeilen) + b"\n")

    k = modelle.aktualisieren("claude", transport=transport, jetzt=JETZT)

    assert k.fehler == "Antwort ungültig" and k.modelle == ()


def test_claude_findet_eigene_antwort_zwischen_zeilen(daten):
    def transport(liste, umgebung, eingabe, frist):
        eigene = _kennung(eingabe)
        zeilen = [
            b'{"type":"system","subtype":"init"}',
            _claude_zeile(eigene, [{"value": "v1", "displayName": "V1"}]),
        ]
        return _ausgang(b"\n".join(zeilen) + b"\n")

    k = modelle.aktualisieren("claude", transport=transport, jetzt=JETZT)

    assert k.fehler is None and [m.id for m in k.modelle] == ["v1"]


def test_claude_rohdaten_landen_nicht_im_cache(daten):
    models = [{"value": "v1", "displayName": "V1", "beschreibung": "GEHEIM"}]
    zusatz = {"account": {"email": "GEHEIM@example.org"}, "sitzung": "GEHEIM"}

    k = modelle.aktualisieren("claude", transport=_claude_transport(models, zusatz=zusatz), jetzt=JETZT)

    assert k.fehler is None
    text = modelle.datei().read_text(encoding="utf-8")
    assert "GEHEIM" not in text
    roh = json.loads(text)
    assert set(roh) == {"version", "anbieter"}
    eintrag = roh["anbieter"]["claude"]
    assert set(eintrag) == {"zeit", "fehler", "modelle"}
    assert set(eintrag["modelle"][0]) == {"id", "name"}


# --- falsche Typen, Grenzen, kaputte Einträge --------------------------------

@pytest.mark.parametrize("kaputt, kategorie", [
    (b"kein json", "Antwort ungültig"),
    (b'["liste"]', "Antwort ungültig"),
    (b'{"models":"nein"}', "Antwort ungültig"),
    (b'{"models":[1,2]}', "keine Modelle gemeldet"),
    (b'{"models":[]}', "keine Modelle gemeldet"),
])
def test_falsche_typen_und_leere_listen_erhalten_alten_katalog(daten, kaputt, kategorie):
    modelle.aktualisieren("codex", transport=_transport_mit(_codex_zeile(_codex_modell())), jetzt=JETZT)

    k = modelle.aktualisieren("codex", transport=_transport_mit(kaputt), jetzt=JETZT)

    assert k.fehler == kategorie
    assert [m.id for m in k.modelle] == ["gpt-6-luna"] and k.zeit == JETZT
    gelesen = modelle.lesen("codex", jetzt=JETZT)
    assert [m.id for m in gelesen.modelle] == ["gpt-6-luna"]
    assert gelesen.zeit == JETZT and gelesen.fehler == kategorie and gelesen.veraltet is False


def test_kontrollzeichen_und_ueberlange_kennungen_werden_uebersprungen(daten):
    antwort = _codex_zeile(
        _codex_modell("gut", "Gut"),
        _codex_modell("boese\x01", "Kontrolle"),
        _codex_modell("zeile\numbruch", "Neu"),
        _codex_modell("a" * (modelle.MAX_FELD + 1), "Lang"),
        _codex_modell("", "Leer"),
        _codex_modell("   ", "Blanks"),
        _codex_modell("name-kaputt", "schlecht\x07name"),
    )

    k = modelle.aktualisieren("codex", transport=_transport_mit(antwort), jetzt=JETZT)

    assert [(m.id, m.name) for m in k.modelle] == [("gut", "Gut"), ("name-kaputt", "name-kaputt")]


def test_zu_viele_modelle_ist_ein_fehler(daten):
    antwort = _codex_zeile(*[_codex_modell(f"m{i}", f"M{i}") for i in range(modelle.MAX_MODELLE + 1)])

    k = modelle.aktualisieren("codex", transport=_transport_mit(antwort), jetzt=JETZT)

    assert k.fehler == "Ausgabelimit überschritten" and k.modelle == ()


def test_byte_und_zeilengrenze_ist_ein_fehler(daten):
    for zu_viel in (b"x" * (modelle.MAX_BYTES + 1), b"\n" * (modelle.MAX_ZEILEN + 1)):
        k = modelle.aktualisieren("codex", transport=_transport_mit(zu_viel), jetzt=JETZT)
        assert k.fehler == "Ausgabelimit überschritten"
        assert k.modelle == () and k.veraltet is True


# --- Fristen, Programm, Fehlerkategorien -------------------------------------

def test_timeout_erhaelt_alten_katalog(daten):
    modelle.aktualisieren("codex", transport=_transport_mit(_codex_zeile(_codex_modell())), jetzt=JETZT)

    def transport(liste, umgebung, eingabe, frist):
        raise subprocess.TimeoutExpired(liste, frist)

    k = modelle.aktualisieren("codex", transport=transport, jetzt=JETZT + timedelta(hours=1))

    assert k.fehler == "Zeitüberschreitung"
    assert [m.id for m in k.modelle] == ["gpt-6-luna"] and k.zeit == JETZT
    assert k.veraltet is False  # 1 h < 24 h: letztes gutes Ergebnis bleibt sichtbar frisch


def test_fehlendes_programm_ist_eigene_kategorie(daten):
    def transport(liste, umgebung, eingabe, frist):
        raise FileNotFoundError("codex.exe fehlt")

    k = modelle.aktualisieren("codex", transport=transport, jetzt=JETZT)

    assert k.fehler == "Programm nicht gefunden"
    assert k.modelle == () and k.zeit is None and k.veraltet is True


def test_codex_ohne_programm_fragt_nichts_ab(daten, monkeypatch, tmp_path):
    monkeypatch.delenv("MASTER_SCHALTER_CODEX", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata-leer"))
    aufrufe = []

    k = modelle.aktualisieren("codex", transport=lambda *a: aufrufe.append(a) or _ausgang(b""), jetzt=JETZT)

    assert aufrufe == []
    assert k.fehler == "Programm nicht gefunden"


def test_unbekannte_transportfehler_werden_einfache_kategorie(daten):
    def transport(liste, umgebung, eingabe, frist):
        raise RuntimeError("rohe Antwort GEHEIM")

    k = modelle.aktualisieren("codex", transport=transport, jetzt=JETZT)

    assert k.fehler == "Abfrage fehlgeschlagen"
    assert "GEHEIM" not in modelle.datei().read_text(encoding="utf-8")


def test_bereinigungsfehler_ist_sichtbare_kategorie(daten):
    def transport(liste, umgebung, eingabe, frist):
        raise modelle.BereinigungsFehler("Baum blieb stehen")

    k = modelle.aktualisieren("codex", transport=transport, jetzt=JETZT)

    assert k.fehler == "Bereinigung fehlgeschlagen" and k.modelle == ()


def test_unbekannter_provider_ist_ein_fehler(daten):
    with pytest.raises(modelle.KatalogFehler):
        modelle.lesen("hermes")
    with pytest.raises(modelle.KatalogFehler):
        modelle.aktualisieren("openrouter", transport=_transport_mit(b""), jetzt=JETZT)


# --- Cache lesen, TTL, getrennte Anbieter ------------------------------------

def test_lesen_ohne_oder_kaputte_datei(daten):
    k = modelle.lesen("codex", jetzt=JETZT)
    assert k.fehler == "keine Daten" and k.modelle == () and k.zeit is None and k.veraltet is True

    pfad = modelle.datei()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    for kaputt in ("{kaputt", "[]", '"text"', json.dumps({"version": 2, "anbieter": {}})):
        pfad.write_text(kaputt, encoding="utf-8")
        k = modelle.lesen("codex", jetzt=JETZT)
        assert k.fehler == "keine Daten" and k.veraltet is True


def test_ttl_24_stunden_und_veraltet(daten):
    modelle.aktualisieren("codex", transport=_transport_mit(_codex_zeile(_codex_modell())), jetzt=JETZT)

    assert modelle.lesen("codex", jetzt=JETZT + timedelta(hours=23, minutes=59)).veraltet is False
    assert modelle.lesen("codex", jetzt=JETZT + timedelta(hours=24, minutes=1)).veraltet is True


def test_cache_prueft_eintraege_und_dedupliziert(daten):
    _cache_schreiben({
        "codex": {"zeit": JETZT.isoformat(), "fehler": None, "modelle": [
            {"id": "a", "name": "A"},
            {"id": "a", "name": "A zweitfassung"},
            {"id": "b\x01", "name": "B"},
            {"id": 5, "name": "C"},
            {"id": "d", "name": "D", "fremdfeld": "egal"},
        ]},
        "claude": {"zeit": "kein Datum", "fehler": None, "modelle": [{"id": "c", "name": "C"}]},
    })

    k = modelle.lesen("codex", jetzt=JETZT)
    assert [(m.id, m.name) for m in k.modelle] == [("a", "A"), ("d", "D")]
    assert k.zeit == JETZT and k.veraltet is False

    c = modelle.lesen("claude", jetzt=JETZT)
    assert [m.id for m in c.modelle] == ["c"] and c.zeit is None and c.veraltet is True


def test_unbekannte_fehlerkategorie_ist_keine_daten(daten):
    _cache_schreiben({"codex": {"zeit": JETZT.isoformat(), "fehler": "rohe Antwort", "modelle": []}})

    k = modelle.lesen("codex", jetzt=JETZT)

    assert k.fehler == "keine Daten" and k.modelle == ()


def test_speichern_verweigert_fremde_cache_version(daten):
    pfad = modelle.datei()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    fremd = json.dumps({"version": 2, "anbieter": {"codex": {"zeit": None, "fehler": None, "modelle": []}}})
    pfad.write_text(fremd, encoding="utf-8")

    k = modelle.aktualisieren("codex", transport=_transport_mit(_codex_zeile(_codex_modell())), jetzt=JETZT)

    assert k.fehler == "Speichern fehlgeschlagen"
    assert pfad.read_text(encoding="utf-8") == fremd  # fremde neuere Struktur bleibt bytegleich


def test_anbieter_getrennt_bei_teilfehler(daten):
    modelle.aktualisieren("codex", transport=_transport_mit(_codex_zeile(_codex_modell())), jetzt=JETZT)

    def kaputt(liste, umgebung, eingabe, frist):
        raise subprocess.TimeoutExpired(liste, frist)

    k = modelle.aktualisieren("claude", transport=kaputt, jetzt=JETZT)

    assert k.fehler == "Zeitüberschreitung" and k.modelle == ()
    unberuehrt = modelle.lesen("codex", jetzt=JETZT)
    assert [m.id for m in unberuehrt.modelle] == ["gpt-6-luna"]
    assert unberuehrt.fehler is None and unberuehrt.zeit == JETZT


# --- Einmaligkeit, Sperren, verlustfreies Mergen -----------------------------

class _MeldeSperre:
    """Echte Sperre, die jeden Erwerbsversuch meldet – für den Überlappungstest ohne Schlaf."""

    def __init__(self) -> None:
        self._echte = threading.Lock()
        self.versuche: list[bool] = []
        self.wartend = threading.Event()
        self._zaehler = threading.Lock()

    def acquire(self, blocking=True, timeout=-1):
        with self._zaehler:
            self.versuche.append(blocking)
            if len(self.versuche) >= 2:
                self.wartend.set()
        if blocking:
            return self._echte.acquire()
        return self._echte.acquire(blocking=False)

    def release(self):
        self._echte.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *ausnahmen):
        self.release()


def test_parallele_abfragen_beider_anbieter_erhalten_beide_eintraege(daten):
    schranke = threading.Barrier(2, timeout=10)

    def codex_transport(liste, umgebung, eingabe, frist):
        schranke.wait()
        return _ausgang(_codex_zeile(_codex_modell()))

    def claude_transport(liste, umgebung, eingabe, frist):
        schranke.wait()
        return _ausgang(_claude_zeile(_kennung(eingabe), [{"value": "opus", "displayName": "Opus"}]) + b"\n")

    erg: dict[str, modelle.Katalog] = {}

    def abfrage(provider, transport):
        erg[provider] = modelle.aktualisieren(provider, transport=transport, jetzt=JETZT)

    threads = [
        threading.Thread(target=abfrage, args=("codex", codex_transport), daemon=True),
        threading.Thread(target=abfrage, args=("claude", claude_transport), daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)

    assert not any(t.is_alive() for t in threads)
    assert [m.id for m in erg["codex"].modelle] == ["gpt-6-luna"]
    assert [m.id for m in erg["claude"].modelle] == ["opus"]
    assert [m.id for m in modelle.lesen("codex").modelle] == ["gpt-6-luna"]
    assert [m.id for m in modelle.lesen("claude").modelle] == ["opus"]


def test_ueberlappende_gleiche_abfrage_startet_einen_transport(daten, monkeypatch):
    lauf = modelle._Flug()
    melder = _MeldeSperre()
    lauf.lock = melder
    monkeypatch.setattr(modelle, "_FLUG", {"codex": lauf})
    gestartet = threading.Event()
    freigeben = threading.Event()
    zaehler = []

    def transport(liste, umgebung, eingabe, frist):
        zaehler.append(1)
        gestartet.set()
        assert freigeben.wait(10)
        return _ausgang(_codex_zeile(_codex_modell()))

    erg: dict[str, modelle.Katalog] = {}

    def abfrage(name):
        erg[name] = modelle.aktualisieren("codex", transport=transport, jetzt=JETZT)

    t1 = threading.Thread(target=abfrage, args=("eins",), daemon=True)
    t1.start()
    assert gestartet.wait(10)          # Leiter läuft und hält den Flug-Riegel
    t2 = threading.Thread(target=abfrage, args=("zwei",), daemon=True)
    t2.start()
    assert melder.wartend.wait(10)     # zweiter Aufruf wartet nachweislich auf denselben Anbieter
    freigeben.set()
    t1.join(15)
    t2.join(15)

    assert not t1.is_alive() and not t2.is_alive()
    assert zaehler == [1]
    assert [m.id for m in erg["eins"].modelle] == ["gpt-6-luna"]
    assert erg["zwei"] == erg["eins"]


def test_nacheinander_folgende_abfragen_fragen_erneut(daten):
    zaehler = []

    def transport(liste, umgebung, eingabe, frist):
        zaehler.append(1)
        return _ausgang(_codex_zeile(_codex_modell()))

    modelle.aktualisieren("codex", transport=transport, jetzt=JETZT)
    modelle.aktualisieren("codex", transport=transport, jetzt=JETZT)

    assert zaehler == [1, 1]


def test_schreibsperre_ist_waehrend_der_abfrage_frei(daten):
    freigegeben = []

    def transport(liste, umgebung, eingabe, frist):
        with zustand.sperre(0.5):
            freigegeben.append(True)
        return _ausgang(_codex_zeile(_codex_modell()))

    k = modelle.aktualisieren("codex", transport=transport, jetzt=JETZT)

    assert freigegeben == [True] and k.fehler is None


def test_fremder_eintrag_zwischen_abfrage_und_speichern_bleibt(daten):
    def transport(liste, umgebung, eingabe, frist):
        # Simuliert einen zweiten Schreiber, der während der Abfrage einen anderen Anbieter merkt.
        _cache_schreiben({"claude": {"zeit": JETZT.isoformat(), "fehler": None,
                                     "modelle": [{"id": "fremd", "name": "Fremd"}]}})
        return _ausgang(_codex_zeile(_codex_modell()))

    k = modelle.aktualisieren("codex", transport=transport, jetzt=JETZT)

    assert k.fehler is None
    assert [m.id for m in modelle.lesen("claude").modelle] == ["fremd"]
    assert [m.id for m in modelle.lesen("codex").modelle] == ["gpt-6-luna"]


def test_alle_aktualisieren_ohne_budget_fragt_nichts_ab(daten):
    aufrufe = []

    erg = modelle.alle_aktualisieren(
        claude=lambda *a: aufrufe.append(a) or _ausgang(b""),
        codex=lambda *a: aufrufe.append(a) or _ausgang(b""),
        jetzt=JETZT, frist=0.0)

    assert aufrufe == []
    assert erg["claude"].fehler == "Zeitüberschreitung"
    assert erg["codex"].fehler == "Zeitüberschreitung"


def test_alle_aktualisieren_gibt_restbudget_und_teilstatus(daten):
    gesehen = {}

    def claude_t(liste, umgebung, eingabe, frist):
        gesehen["claude"] = frist
        return _ausgang(_claude_zeile(_kennung(eingabe), [{"value": "opus", "displayName": "Opus"}]) + b"\n")

    def codex_t(liste, umgebung, eingabe, frist):
        gesehen["codex"] = frist
        raise subprocess.TimeoutExpired(liste, frist)

    erg = modelle.alle_aktualisieren(claude=claude_t, codex=codex_t, jetzt=JETZT)

    assert 0 < gesehen["claude"] <= modelle.FRIST_ABFRAGE
    assert 0 < gesehen["codex"] <= modelle.FRIST_ABFRAGE
    assert erg["claude"].fehler is None
    assert erg["codex"].fehler == "Zeitüberschreitung"
    assert [m.id for m in modelle.lesen("claude").modelle] == ["opus"]
    gelesen = modelle.lesen("codex")
    assert gelesen.fehler == "Zeitüberschreitung" and gelesen.modelle == ()


# --- Aufrufe: Argumente, Umgebung, Anfrage -----------------------------------

def test_codex_aufruf_argumente_und_bereinigte_umgebung(daten, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_CODEX", "C:/werkzeuge/codex.exe")
    monkeypatch.setenv("OPENAI_API_KEY", "GEHEIM")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "GEHEIM")
    gesehen = []

    k = modelle.aktualisieren("codex", transport=_transport_mit(_codex_zeile(_codex_modell()), gesehen),
                              jetzt=JETZT)

    liste, umgebung, eingabe, frist = gesehen[0]
    assert liste == ["C:/werkzeuge/codex.exe", "-c", "model_provider=openai", "-c",
                     "forced_login_method=chatgpt", "debug", "models"]
    assert "--ignore-user-config" not in liste
    assert eingabe == b"" and frist == modelle.FRIST_ABFRAGE
    assert "OPENAI_API_KEY" not in umgebung and "ANTHROPIC_API_KEY" not in umgebung
    assert "CLAUDE_CONFIG_DIR" not in umgebung
    assert umgebung["PATH"] == os.environ["PATH"]
    assert os.environ["OPENAI_API_KEY"] == "GEHEIM"   # Elternumgebung bleibt unverändert
    assert k.fehler is None


def test_claude_aufruf_argumente_umgebung_und_anfrage(daten, monkeypatch, tmp_path):
    cli = tmp_path / "cli.js"
    node = tmp_path / "node.exe"
    cli.write_text("x", encoding="utf-8")
    node.write_text("x", encoding="utf-8")
    monkeypatch.setenv("MASTER_SCHALTER_CLAUDE_CLI", str(cli))
    monkeypatch.setenv("MASTER_SCHALTER_NODE", str(node))
    for name in ("OPENROUTER_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY"):
        monkeypatch.setenv(name, "GEHEIM")
    gesehen = []

    k = modelle.aktualisieren("claude", transport=_claude_transport(
        [{"value": "opus", "displayName": "Opus"}], gesehen=gesehen), jetzt=JETZT)

    liste, umgebung, eingabe, frist = gesehen[0]
    assert liste == [str(node), str(cli), "--bare", "--print", "--input-format", "stream-json",
                     "--output-format", "stream-json", "--verbose", "--no-session-persistence",
                     "--disable-slash-commands", "--tools", "", "--strict-mcp-config",
                     "--mcp-config", '{"mcpServers":{}}']
    assert not liste[0].endswith(".cmd") and not liste[1].endswith(".cmd")
    for verboten in ("OPENROUTER_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY"):
        assert verboten not in umgebung
    for name, wert in (("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1"), ("DISABLE_TELEMETRY", "1"),
                       ("DISABLE_ERROR_REPORTING", "1"), ("DISABLE_AUTOUPDATER", "1")):
        assert umgebung[name] == wert
    config = umgebung["CLAUDE_CONFIG_DIR"]
    assert config and os.path.isdir(config) and list(os.scandir(config)) == []
    zeilen = eingabe.decode("utf-8").splitlines()
    assert len(zeilen) == 1 and eingabe.endswith(b"\n")
    anfrage = json.loads(zeilen[0])
    assert set(anfrage) == {"type", "request_id", "request"}
    assert anfrage["type"] == "control_request" and anfrage["request"] == {"subtype": "initialize"}
    assert isinstance(anfrage["request_id"], str) and anfrage["request_id"]
    assert k.fehler is None and [m.id for m in k.modelle] == ["opus"]


def test_claude_ohne_programm_meldet_fehler(daten, monkeypatch, tmp_path):
    monkeypatch.delenv("MASTER_SCHALTER_CLAUDE_CLI", raising=False)
    monkeypatch.delenv("MASTER_SCHALTER_NODE", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata-leer"))
    monkeypatch.setattr(modelle.Path, "home", classmethod(lambda cls: tmp_path / "heim-leer"))
    aufrufe = []

    k = modelle.aktualisieren("claude", transport=lambda *a: aufrufe.append(a) or _ausgang(b""), jetzt=JETZT)

    assert aufrufe == []
    assert k.fehler == "Programm nicht gefunden"


def test_claude_programm_findet_npm_layout(monkeypatch, tmp_path):
    monkeypatch.delenv("MASTER_SCHALTER_CLAUDE_CLI", raising=False)
    monkeypatch.delenv("MASTER_SCHALTER_NODE", raising=False)
    appdata = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("APPDATA", str(appdata))
    cli = appdata / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "cli.js"
    node = appdata / "npm" / "node.exe"
    for pfad in (cli, node):
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text("x", encoding="utf-8")

    assert modelle.claude_programm() == (str(node), str(cli))

    monkeypatch.setenv("MASTER_SCHALTER_CLAUDE_CLI", str(tmp_path / "eigene.js"))
    monkeypatch.setenv("MASTER_SCHALTER_NODE", str(tmp_path / "eigener_node.exe"))
    assert modelle.claude_programm() == (str(tmp_path / "eigener_node.exe"), str(tmp_path / "eigene.js"))


def test_claude_programm_findet_natives_programm(daten, monkeypatch, tmp_path):
    """npm-Paket ohne cli.js (ab 2.1.3xx): das native bin/claude.exe wird direkt aufgerufen."""
    monkeypatch.delenv("MASTER_SCHALTER_CLAUDE_CLI", raising=False)
    monkeypatch.delenv("MASTER_SCHALTER_NODE", raising=False)
    appdata = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setattr(modelle.Path, "home", classmethod(lambda cls: tmp_path / "heim-leer"))
    programm = appdata / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    programm.parent.mkdir(parents=True)
    programm.write_text("x", encoding="utf-8")
    gesehen = []

    modelle.aktualisieren("claude", transport=_claude_transport([{"value": "opus", "displayName": "Opus"}],
                                                                 gesehen=gesehen), jetzt=JETZT)

    assert modelle.claude_programm() == (str(programm),)
    assert gesehen and list(gesehen[0][0][:2]) == [str(programm), "--bare"]


def test_claude_programm_alte_cli_js_ohne_node_faellt_auf_nativ_zurueck(monkeypatch, tmp_path):
    """Liegt noch ein altes cli.js herum, aber kein Node, gilt das native Programm (Prüfung v0.4.1 R1)."""
    monkeypatch.delenv("MASTER_SCHALTER_CLAUDE_CLI", raising=False)
    monkeypatch.delenv("MASTER_SCHALTER_NODE", raising=False)
    monkeypatch.setattr(modelle.shutil, "which", lambda name: None)
    monkeypatch.setattr(modelle.Path, "home", classmethod(lambda cls: tmp_path / "heim-leer"))
    appdata = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("APPDATA", str(appdata))
    paket = appdata / "npm" / "node_modules" / "@anthropic-ai" / "claude-code"
    (paket / "bin").mkdir(parents=True)
    (paket / "cli.js").write_text("x", encoding="utf-8")
    (paket / "bin" / "claude.exe").write_text("x", encoding="utf-8")

    assert modelle.claude_programm() == (str(paket / "bin" / "claude.exe"),)


def test_claude_programm_findet_nativ_im_heimordner(monkeypatch, tmp_path):
    monkeypatch.delenv("MASTER_SCHALTER_CLAUDE_CLI", raising=False)
    monkeypatch.delenv("MASTER_SCHALTER_NODE", raising=False)
    monkeypatch.setattr(modelle.Path, "home", classmethod(lambda cls: tmp_path / "heim-leer"))
    heim_nativ = tmp_path / "heim-leer" / ".local" / "bin" / "claude.exe"
    heim_nativ.parent.mkdir(parents=True)
    heim_nativ.write_text("x", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata-leer"))
    assert modelle.claude_programm() == (str(heim_nativ),)


# --- Windows-Bereinigung: eigener Prozessbaum, nie Namenssuche ----------------

def _lebt(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def _warte_tot(pid: int, frist: float = 30.0) -> bool:
    ende = time.monotonic() + frist
    while time.monotonic() < ende:
        if not _lebt(pid):
            return True
        time.sleep(0.05)
    return False


def _pid_lesen(pid_datei, frist: float = 20.0) -> int:
    """Wartet auf die PID-Datei des Kindskripts: Unter Rechnerlast braucht der Python-Start des
    Kindes länger als die kurze Testfrist; die Budget-Prüfung bleibt davon unberührt."""
    ende = time.monotonic() + frist
    while time.monotonic() < ende:
        try:
            return int(pid_datei.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            time.sleep(0.05)
    raise AssertionError(f"Kindskript hat binnen {frist} s keine PID geschrieben")


def _skript(tmp_path, name: str, inhalt: str) -> str:
    pfad = tmp_path / name
    pfad.write_text(inhalt, encoding="utf-8")
    return str(pfad)


@pytest.mark.skipif(os.name != "nt", reason="Windows-Bereinigung")
def test_bereinigung_beendet_eigenen_baum_exakt(daten, tmp_path, monkeypatch):
    monkeypatch.setattr(modelle, "BEREINIGUNG_SEKUNDEN", 30.0)   # taskkill ist unter Volllast langsam
    monkeypatch.setattr(modelle, "PIPE_SEKUNDEN", 10.0)
    pid_datei = tmp_path / "pid.txt"
    haengt = _skript(tmp_path, "haengt.py",
                     "import os, pathlib, time\n"
                     f"pathlib.Path({str(pid_datei)!r}).write_text(str(os.getppid()) + ' ' + str(os.getpid()),"
                     " encoding='utf-8')\n"
                     "time.sleep(60)\n")
    gesehen = []
    echt = modelle._taskkill_argv

    def merken(pid):
        argv = echt(pid)
        gesehen.append(argv)
        return argv

    monkeypatch.setattr(modelle, "_taskkill_argv", merken)
    eingabe = json.dumps({"type": "control_request", "request_id": KENNUNG,
                          "request": {"subtype": "initialize"}}).encode("utf-8") + b"\n"

    with pytest.raises(modelle.ZeitFehler):
        modelle.claude_transport([sys.executable, haengt], dict(os.environ), eingabe, 6.0)

    # Die venv-python.exe leitet auf einen Kindprozess um: der vom Adapter gestartete Prozess
    # ist dann der Elternprozess des Skripts. Beide gehören zum eigenen Baum, keiner zum Testlauf.
    eltern_pid, skript_pid = (int(t) for t in pid_datei.read_text(encoding="utf-8").split())
    gestartete_pid = eltern_pid if eltern_pid != os.getpid() else skript_pid
    assert gesehen == [["taskkill", "/PID", str(gestartete_pid), "/T", "/F"]]
    assert _warte_tot(skript_pid) and (gestartete_pid == skript_pid or _warte_tot(gestartete_pid))


def test_kein_eigener_enkel_uebrig_kontrollprozess_erhalten(daten, tmp_path, monkeypatch):
    monkeypatch.setattr(modelle, "BEREINIGUNG_SEKUNDEN", 30.0)   # taskkill ist unter Volllast langsam
    monkeypatch.setattr(modelle, "PIPE_SEKUNDEN", 10.0)
    pid_datei = tmp_path / "pids.txt"
    eltern = _skript(tmp_path, "eltern.py",
                     "import os, subprocess, sys, pathlib, time\n"
                     "enkel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                     f"pathlib.Path({str(pid_datei)!r}).write_text(str(os.getpid()) + ' ' + str(enkel.pid),"
                     " encoding='utf-8')\n"
                     "time.sleep(60)\n")
    kontrolle = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        with pytest.raises(modelle.ZeitFehler):
            modelle.codex_transport([sys.executable, eltern], dict(os.environ), b"", 6.0)

        eltern_pid, enkel_pid = (int(t) for t in pid_datei.read_text(encoding="utf-8").split())
        assert _warte_tot(enkel_pid), "Enkelprozess des eigenen Baums lebt noch"
        assert _lebt(kontrolle.pid), "separater Kontrollprozess wurde mitbeendet"
        assert _warte_tot(eltern_pid)
    finally:
        kontrolle.kill()
        kontrolle.wait(5)


@pytest.mark.skipif(os.name != "nt", reason="Windows-Bereinigung")
def test_fehlgeschlagene_bereinigung_ist_sichtbarer_fehler(daten, tmp_path, monkeypatch):
    pid_datei = tmp_path / "pid.txt"
    haengt = _skript(tmp_path, "haengt.py",
                     "import os, pathlib, time\n"
                     f"pathlib.Path({str(pid_datei)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
                     "time.sleep(60)\n")
    monkeypatch.setattr(modelle, "_taskkill", lambda pid: None)
    monkeypatch.setattr(modelle, "BEREINIGUNG_SEKUNDEN", 0.3)
    monkeypatch.setenv("MASTER_SCHALTER_CODEX", "C:/werkzeug/fake-codex.exe")

    def transport(liste, umgebung, eingabe, frist):
        return modelle.codex_transport([sys.executable, haengt], dict(umgebung), b"", frist)

    k = modelle.aktualisieren("codex", transport=transport, jetzt=JETZT, frist=1.5)

    assert k.fehler == "Bereinigung fehlgeschlagen" and k.modelle == ()
    assert modelle.lesen("codex").fehler == "Bereinigung fehlgeschlagen"
    kind = _pid_lesen(pid_datei)
    assert _lebt(kind)  # nichts wurde stillschweigend „weggeräumt“
    subprocess.run(["taskkill", "/PID", str(kind), "/T", "/F"], capture_output=True)


# --- Budgetgrenzen: Abfrage + Bereinigung -------------------------------------

@pytest.mark.skipif(os.name != "nt", reason="Windows-Bereinigung")
def test_ungueltige_protokollantwort_bei_laufendem_prozess_bereinigt_baum(daten, tmp_path, monkeypatch):
    """Antwort besteht die Prüfung nicht, während der Prozess noch läuft: Kill-Pfad greift,
    Fehler bleibt sichtbar, der alte Katalog bleibt unverändert.

    Lastrobust/deterministisch: Die Zeitfenster sind absichtlich weit über jede normale Laufzeit
    hinaus gesetzt (Abfragefrist 30 s, Kill-Wartezeit 20 s, Einsammelfrist 10 s), damit unter
    Rechnerlast deterministisch genau der dokumentierte Ausgang „Antwort ungültig“ eintritt und
    der Test nicht in das engere Standardfenster (5 s Bereinigung) läuft. Scharf bleiben: exakt
    ein taskkill auf die eigene PID mit /T /F, das gestartete Kind ist danach tot, und der alte
    Katalog samt Fehlerstatus bleibt unverändert.
    """
    modelle.aktualisieren("claude", transport=_claude_transport(
        [{"value": "opus", "displayName": "Opus"}]), jetzt=JETZT)

    monkeypatch.setattr(modelle, "BEREINIGUNG_SEKUNDEN", 20.0)
    monkeypatch.setattr(modelle, "PIPE_SEKUNDEN", 10.0)
    pid_datei = tmp_path / "pid.txt"
    antwortet = _skript(tmp_path, "antwortet.py",
                        "import json, os, pathlib, sys, time\n"
                        "zeile = sys.stdin.readline()\n"
                        "kennung = json.loads(zeile)[\"request_id\"]\n"
                        f"pathlib.Path({str(pid_datei)!r}).write_text("
                        "str(os.getppid()) + ' ' + str(os.getpid()), encoding='utf-8')\n"
                        "antwort = {\"type\": \"control_response\", \"response\": "
                        "{\"subtype\": \"success\", \"request_id\": kennung, "
                        "\"response\": {\"models\": \"nein\"}}}\n"
                        "print(json.dumps(antwort), flush=True)\n"
                        "time.sleep(60)\n")
    cli = tmp_path / "cli.js"
    node = tmp_path / "node.exe"
    for pfad in (cli, node):
        pfad.write_text("x", encoding="utf-8")
    monkeypatch.setenv("MASTER_SCHALTER_CLAUDE_CLI", str(cli))
    monkeypatch.setenv("MASTER_SCHALTER_NODE", str(node))
    gesehen = []
    echt = modelle._taskkill_argv

    def merken(pid):
        argv = echt(pid)
        gesehen.append(argv)
        return argv

    monkeypatch.setattr(modelle, "_taskkill_argv", merken)

    def transport(liste, umgebung, eingabe, frist):
        return modelle.claude_transport([sys.executable, antwortet], dict(umgebung), eingabe, frist)

    k = modelle.aktualisieren("claude", transport=transport, jetzt=JETZT, frist=30.0)

    assert k.fehler == "Antwort ungültig"
    assert [m.id for m in k.modelle] == ["opus"] and k.zeit == JETZT
    gelesen = modelle.lesen("claude", jetzt=JETZT)
    assert [m.id for m in gelesen.modelle] == ["opus"] and gelesen.fehler == "Antwort ungültig"
    # Die venv-python.exe leitet auf einen Kindprozess um: der vom Adapter gestartete Prozess
    # ist dann der Elternprozess des Skripts. Beide gehören zum eigenen Baum, keiner zum Testlauf.
    eltern_pid, skript_pid = (int(t) for t in pid_datei.read_text(encoding="utf-8").split())
    gestartete_pid = eltern_pid if eltern_pid != os.getpid() else skript_pid
    assert gesehen == [["taskkill", "/PID", str(gestartete_pid), "/T", "/F"]]
    assert _warte_tot(skript_pid, 10.0) and (gestartete_pid == skript_pid or _warte_tot(gestartete_pid, 10.0))


@pytest.mark.skipif(os.name != "nt", reason="Windows-Bereinigung")
def test_haengender_anbieter_bleibt_im_gesamtbudget(daten, tmp_path, monkeypatch):
    """Kleines Abbild des 65-s-Budgets: Scheitert die Bereinigung eines hängenden Anbieters
    (Kill wirkt nicht), bleibt der Lauf trotzdem innerhalb der Frist — die Bereinigung
    verbraucht ihr Geld aus demselben Budget."""
    pid_datei = tmp_path / "pid.txt"
    haengt = _skript(tmp_path, "haengt.py",
                     "import os, pathlib, time\n"
                     f"pathlib.Path({str(pid_datei)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
                     "time.sleep(60)\n")
    monkeypatch.setattr(modelle, "_taskkill", lambda pid: None)      # Kill wirkt nicht
    monkeypatch.setattr(modelle, "BEREINIGUNG_SEKUNDEN", 0.6)
    monkeypatch.setattr(modelle, "PIPE_SEKUNDEN", 0.2)
    monkeypatch.setenv("MASTER_SCHALTER_CLAUDE_CLI", "C:/werkzeug/fake-cli.js")
    monkeypatch.setenv("MASTER_SCHALTER_NODE", "C:/werkzeug/fake-node.exe")
    monkeypatch.setenv("MASTER_SCHALTER_CODEX", "C:/werkzeug/fake-codex.exe")
    frist = 1.5

    def claude_t(liste, umgebung, eingabe, frist):
        return modelle.claude_transport([sys.executable, haengt], dict(umgebung), b"", frist)

    def codex_t(liste, umgebung, eingabe, frist):
        return _ausgang(_codex_zeile(_codex_modell()))

    try:
        beginn = time.monotonic()
        erg = modelle.alle_aktualisieren(claude=claude_t, codex=codex_t, jetzt=JETZT, frist=frist)
        dauer = time.monotonic() - beginn

        assert dauer <= frist + 0.3, f"Budget überschritten: {dauer:.2f}s > {frist + 0.3:.2f}s"
        assert erg["claude"].fehler == "Bereinigung fehlgeschlagen"
        assert erg["codex"].fehler == "Zeitüberschreitung"
        kind = _pid_lesen(pid_datei)
        assert _lebt(kind)  # der Kill wirkte nicht — genau dafür greift die Budgetgrenze
    finally:
        if pid_datei.exists():
            subprocess.run(["taskkill", "/PID", pid_datei.read_text(encoding="utf-8").strip(), "/T", "/F"],
                           capture_output=True)


# --- Datentypen ---------------------------------------------------------------

def test_modell_und_katalog_sind_unveraenderlich():
    m = modelle.Modell("a", "A")
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.id = "b"

    k = modelle.Katalog("codex")
    with pytest.raises(dataclasses.FrozenInstanceError):
        k.fehler = "x"
    assert k.modelle == () and k.zeit is None and k.fehler is None and k.veraltet is False


@pytest.mark.skipif(os.name != "nt", reason="Windows-Bereinigung")
def test_eltern_endet_waehrend_kind_die_pipe_haelt_haengt_nicht(daten, tmp_path, monkeypatch):
    """Der Elternprozess endet, ein Enkel hält stdout offen: `close()` auf dem lesenden Puffer würde ewig
    blockieren. Erwartet: fester Bereinigungsfehler in begrenzter Zeit, Datenströme werden nicht geschlossen."""
    pid_datei = tmp_path / "pids.txt"
    eltern = _skript(tmp_path, "eltern_endet.py",
                     "import os, subprocess, sys, pathlib\n"
                     "enkel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                     f"pathlib.Path({str(pid_datei)!r}).write_text(str(enkel.pid), encoding='utf-8')\n")
    monkeypatch.setattr(modelle, "PIPE_SEKUNDEN", 0.3)
    ergebnis = {}

    def lauf():
        try:
            modelle.codex_transport([sys.executable, eltern], dict(os.environ), b"", 5.0)
        except BaseException as fehler:  # noqa: BLE001
            ergebnis["fehler"] = fehler

    faden = threading.Thread(target=lauf, daemon=True)
    beginn = time.monotonic()
    faden.start()
    faden.join(30)
    try:
        assert not faden.is_alive(), "Bereinigung hängt (close() auf lesendem Puffer)"
        assert isinstance(ergebnis.get("fehler"), modelle.BereinigungsFehler)
        assert time.monotonic() - beginn < 15
    finally:
        if pid_datei.exists():
            try:
                os.kill(int(pid_datei.read_text(encoding="utf-8")), signal.SIGTERM)
            except OSError:
                pass
