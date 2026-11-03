"""Alltagsprotokoll S3 (03.11.2026): Text → Eintrag über ein Modell — nur mit Attrappe, kein Netz.

Plan ``.hermes/plans/alltagsprotokoll.md`` S3: Der Beispielsatz aus den Erfolgskriterien ergibt
das erwartete JSON; nichts im Klartext im Aufruf, was als Name registriert ist; ZDR im Aufruf.
Alle Sätze und Namen erfunden.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.services import alltag_struktur as st

MEZ = timezone(timedelta(hours=1))
JETZT = datetime(2026, 11, 3, 15, 40, tzinfo=MEZ)
SATZ = "Letzte Stunde Wäsche gemacht, Stimmung gut, Anspannung 30, etwas genervt"


class Attrappe:
    def __init__(self, antwort=None, fehler=None):
        self.antwort = antwort
        self.fehler = fehler
        self.aufrufe = []

    def chat_completion(self, messages, model, temperature, max_tokens, extra_payload):
        self.aufrufe.append({"messages": messages, "model": model, "extra_payload": extra_payload})
        if self.fehler:
            raise self.fehler
        inhalt = self.antwort if isinstance(self.antwort, str) else json.dumps(self.antwort)
        return {"choices": [{"message": {"content": inhalt}}], "usage": {"cost": 0.0001}}


def _json(**felder):
    basis = {"art": "stunde", "von": None, "bis": None, "stimmung": None, "anspannung": None,
             "gefuehle": [], "vorherrschend": None, "aktivitaet": None, "ereignis": None, "zeit": None}
    basis.update(felder)
    return basis


def test_beispielsatz_wird_zum_eintrag():
    kasten = Attrappe(_json(stimmung=4, anspannung=30, gefuehle=["Ärger"], vorherrschend="Ärger",
                            aktivitaet="Wäsche gemacht"))
    r = st.strukturieren(SATZ, quelle="sprache", jetzt=JETZT, client=kasten, namen=[])
    assert r["ok"], r
    e = r["eintrag"]
    assert e == {"art": "stunde", "von": "2026-11-03T14:40:00+01:00", "bis": "2026-11-03T15:40:00+01:00",
                 "stimmung": 4, "anspannung": 30, "gefuehle": ["Ärger"], "vorherrschend": "Ärger",
                 "aktivitaet": "Wäsche gemacht", "originalworte": SATZ, "quelle": "sprache"}
    assert r["fehlt"] == []


def test_zdr_und_reasoning_im_aufruf():
    kasten = Attrappe(_json(aktivitaet="Lesen"))
    st.strukturieren("Gelesen", quelle="tastatur", jetzt=JETZT, client=kasten, namen=[])
    payload = kasten.aufrufe[0]["extra_payload"]
    assert payload["provider"]["data_collection"] == "deny"


def test_namen_gehen_nur_maskiert_raus_und_kommen_zurueck():
    kasten = Attrappe(_json(aktivitaet="Kaffee mit [PERSON_01]", gefuehle=["Freude"]))
    r = st.strukturieren("Kaffee mit Testperson Anna, schön", quelle="sprache", jetzt=JETZT,
                         client=kasten, namen=["Testperson Anna"])
    gesendet = json.dumps(kasten.aufrufe[0]["messages"], ensure_ascii=False)
    assert "Testperson" not in gesendet and "Anna" not in gesendet
    assert r["eintrag"]["aktivitaet"] == "Kaffee mit Testperson Anna"
    assert r["eintrag"]["originalworte"] == "Kaffee mit Testperson Anna, schön"   # lokal, unmaskiert


def test_name_kommt_in_der_schreibweise_des_satzes_zurueck():
    kasten = Attrappe(_json(aktivitaet="Telefoniert mit [PERSON_02]"))
    r = st.strukturieren("Telefoniert mit Bertram", quelle="sprache", jetzt=JETZT,
                         client=kasten, namen=["bertram testmann"])
    assert "Bertram" not in json.dumps(kasten.aufrufe[0]["messages"], ensure_ascii=False)
    assert r["eintrag"]["aktivitaet"] == "Telefoniert mit Bertram"


def test_zeitbereich_aus_uhrzeiten_auch_ueber_mitternacht():
    kasten = Attrappe(_json(von="23:00", bis="01:00", aktivitaet="Film"))
    jetzt = datetime(2026, 11, 3, 1, 30, tzinfo=MEZ)
    e = st.strukturieren("Von 23 bis 1 Film", quelle="sprache", jetzt=jetzt, client=kasten, namen=[])["eintrag"]
    assert (e["von"], e["bis"]) == ("2026-11-02T23:00:00+01:00", "2026-11-03T01:00:00+01:00")


def test_spaetere_uhrzeit_als_jetzt_gilt_fuer_gestern():
    kasten = Attrappe(_json(von="20:00", bis="21:00", aktivitaet="Sport"))
    e = st.strukturieren("20 bis 21 Uhr Sport", quelle="sprache", jetzt=JETZT, client=kasten, namen=[])["eintrag"]
    assert e["von"].startswith("2026-11-02T20:00")


def test_nur_beginn_endet_jetzt_nicht_in_der_zukunft():
    for von, erwartet in (("15:00", "2026-11-03T15:00:00+01:00"), ("15:40", "2026-11-03T14:40:00+01:00")):
        kasten = Attrappe(_json(von=von, aktivitaet="Wäsche"))
        e = st.strukturieren("Seit 15 Uhr Wäsche", quelle="sprache", jetzt=JETZT, client=kasten, namen=[])["eintrag"]
        assert (e["von"], e["bis"]) == (erwartet, "2026-11-03T15:40:00+01:00")


def test_schlaf_ereignis():
    kasten = Attrappe(_json(art="schlaf", ereignis="schlafen", zeit="15:30"))
    r = st.strukturieren("Ich gehe jetzt schlafen", quelle="sprache", jetzt=JETZT, client=kasten, namen=[])
    assert r["eintrag"] == {"art": "schlaf", "ereignis": "schlafen", "zeit": "2026-11-03T15:30:00+01:00",
                            "originalworte": "Ich gehe jetzt schlafen", "quelle": "sprache"}
    assert r["fehlt"] == []


def test_strenge_pruefung_verwirft_unsinn():
    kasten = Attrappe(_json(stimmung=9, anspannung="viel", gefuehle=["Wut", 3, "", "x" * 200],
                            vorherrschend="Neid", aktivitaet="  ", geheim="weg", von="25:99"))
    e = st.strukturieren("irgendwas", quelle="sprache", jetzt=JETZT, client=kasten, namen=[])["eintrag"]
    assert "geheim" not in e and e["stimmung"] is None and e["anspannung"] is None
    assert e["gefuehle"] == ["Ärger"]                     # Wut -> Ärger, Neid ist kein Grundgefühl
    assert e["vorherrschend"] is None
    assert e["aktivitaet"] is None
    assert e["von"] == "2026-11-03T14:40:00+01:00"        # unlesbare Uhrzeit -> letzte Stunde


def test_nur_die_sechs_grundgefuehle_nach_ekman():
    assert st.GRUNDGEFUEHLE == ("Freude", "Trauer", "Angst", "Ärger", "Ekel", "Überraschung")
    kasten = Attrappe(_json(gefuehle=["traurigkeit", "Ruhe", "verliebt", "FREUDE", "Furcht"],
                            vorherrschend="glück", aktivitaet="Spaziert"))
    e = st.strukturieren("x", quelle="sprache", jetzt=JETZT, client=kasten, namen=[])["eintrag"]
    assert e["gefuehle"] == ["Freude", "Trauer", "Angst"]   # vorherrschend vorn, Rest verworfen
    assert e["vorherrschend"] == "Freude"


def test_aufforderung_erlaubt_keine_eigenen_worte():
    text = st.baue_nachricht("x", JETZT)
    assert "eigenes" not in text and "nur aus Freude, Trauer, Angst, Ärger, Ekel, Überraschung" in text


def test_unbrauchbare_antwort_ist_ehrlicher_fehler():
    for antwort in ("kein json", json.dumps(["liste"]), json.dumps(_json(art="essen"))):
        r = st.strukturieren("x", quelle="sprache", jetzt=JETZT, client=Attrappe(antwort), namen=[])
        assert r["ok"] is False and r["grund"]


def test_netzfehler_ohne_ausnahmetext():
    kasten = Attrappe(fehler=httpx.ConnectError("geheime-url.example"))
    r = st.strukturieren("x", quelle="sprache", jetzt=JETZT, client=kasten, namen=[])
    assert r["ok"] is False and "geheime" not in r["grund"]


def test_ohne_schluessel_kein_aufruf(monkeypatch):
    monkeypatch.setattr(st, "_schluessel", lambda: "")
    r = st.strukturieren("x", quelle="sprache", jetzt=JETZT, namen=[])
    assert r["ok"] is False and "Schlüssel" in r["grund"]


def test_leerer_text_kein_aufruf():
    kasten = Attrappe(_json())
    assert st.strukturieren("   ", quelle="sprache", jetzt=JETZT, client=kasten, namen=[])["ok"] is False
    assert kasten.aufrufe == []


def test_log_ohne_inhalt(caplog):
    kasten = Attrappe(_json(aktivitaet="Geheimaktivität Zebra"))
    with caplog.at_level(logging.DEBUG):
        st.strukturieren("Geheimsatz Zebra", quelle="sprache", jetzt=JETZT, client=kasten, namen=[])
    assert "Zebra" not in caplog.text
