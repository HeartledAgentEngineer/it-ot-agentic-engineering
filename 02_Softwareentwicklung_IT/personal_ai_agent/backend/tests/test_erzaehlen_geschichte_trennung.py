"""Tests G1: Bildgeschichte/Anlassgeschichte getrennt von den Notizen (02.11.2026).

Plan: ``.hermes/plans/2026-11-02_geschichte-sprachmodell.md`` (Schritt G1),
Satzliste: ``.hermes/plans/2026-11-02_geschichte-altbestand-saetze.md``.

Alles offline: ``ereignisse.jsonl`` und ``geschichten.jsonl`` werden je Test in
``tmp_path`` erfunden (Pfade über ``ERZAEHL_*_PFAD``), erfundene Namen, kein Netz,
kein echter Ordner ``~/foto_sortierung``.

Prüfkriterien (Plan G1): (a) (b) (c) (f) (g) (h) (i) (j) (k) (m) (n) und der
Backend-Teil von (o). Die Texte in ``ALTBESTAND_TEXTE`` hat die damalige
Generator-Funktion aus ``git show <commit>:…/erzaehl_service.py`` mit erfundenen
Daten erzeugt (Commits 1da2f9f, 27466f2, 96de1fc, 05db80b); sie sind hier fest
abgelegt, damit der Test auch nach dem Umbau des Generators (G3) dieselben
Altbestände prüft.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_erzaehlen_geschichte_trennung.py -q
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router import erzaehlen as erzaehlen_router  # noqa: E402
from app.services import erzaehl_service as es  # noqa: E402
from app.services import notizen_service  # noqa: E402

EK = "E-t1"
EREIGNIS = {
    "anlass_id": "t1", "kennung": EK, "anzahl_dateien": 3, "art": "anlass",
    "datei_kennungen": [101, 102, 103], "datum": "2021-08-01", "event": "Sommerfest Muster",
    "jahr": 2021, "kategorie": "Feiern", "quellen": ["cloud"],
}

# Mit der damaligen Funktion erzeugt (erfundene Daten): Schlüssel „<Commit>:<Variante>".
ALTBESTAND_TEXTE = {
    "05db80b:anlass_erzaehler": (
        "Eine Fotodokumentation zu „Sommerfest Muster“ am 4. "
        "Mai 2019 in Musterstadt mit 3 Aufnahmen. "
        "Im Mittelpunkt stehen Anna Beispiel und Bernd Beispiel. "
        "Aus den überlieferten Aufzeichnungen: Wir haben lange gegrillt. "
        "Ein authentisches Zeitdokument, das diesen Lebensabschnitt festhält."
    ),
    "05db80b:anlass_ich": (
        "Eine wunderbare Erinnerung an „Sommerfest Muster“ am 4. "
        "Mai 2019 in Musterstadt – festgehalten zusammen mit Anna Beispiel und Bernd Beispiel. "
        "Wir haben lange gegrillt. "
        "Eine lebendige Bilderreihe, die diese gemeinsamen Erinnerungen für immer bewahrt."
    ),
    "05db80b:bild_erzaehler": (
        "Eine Aufnahme am 4. "
        "Mai 2019 in Musterstadt. "
        "Im Mittelpunkt stehen Anna Beispiel und Bernd Beispiel. "
        "Die visuelle Aufnahme zeigt: Zwei Freunde lachen am Flussufer. "
        "Aus den überlieferten Aufzeichnungen: Das war vor unserem Testkonzert. "
        "Ein authentisches Zeitdokument, das diesen Lebensabschnitt festhält."
    ),
    "05db80b:bild_ich": (
        "Ich erinnere mich gut an diesen Moment am 4. "
        "Mai 2019 in Musterstadt, mit Anna Beispiel und Bernd Beispiel. "
        "Das war vor unserem Testkonzert. "
        "Auf dem Foto wird dieser Augenblick lebendig: Zwei Freunde lachen am Flussufer. "
        "Ein Augenblick voller Geborgenheit, der diese Zeit lebendig hält."
    ),
    "1da2f9f:bild_erzaehler": (
        "Eine Aufnahme am 4. "
        "Mai 2019 aus Musterstadt. "
        "Auf diesem Bild sind Anna Beispiel und Bernd Beispiel zu sehen. "
        "Die Aufnahme zeigt two friends laughing by the river. "
        "Dazu die persoenliche Notiz: \"Das war vor unserem Testkonzert\"."
    ),
    "1da2f9f:bild_ich": (
        "Ich erinnere mich gut an diesen Moment am 4. "
        "Mai 2019 in Musterstadt. "
        "Auf dem Bild sind Anna Beispiel und Bernd Beispiel zu sehen. "
        "Das Bild zeigt two friends laughing by the river. "
        "Meine Erinnerung dazu: Das war vor unserem Testkonzert."
    ),
    "27466f2:bild_erzaehler": (
        "Eine Aufnahme am 4. "
        "Mai 2019 aus Musterstadt. "
        "Auf diesem Bild sind Anna Beispiel und Bernd Beispiel zu sehen. "
        "Bildaufnahme: Two friends laughing by the river. "
        "Dazu die persoenliche Notiz: \"Das war vor unserem Testkonzert\"."
    ),
    "27466f2:bild_ich": (
        "Ich erinnere mich gut an diesen Moment am 4. "
        "Mai 2019 in Musterstadt. "
        "Auf dem Bild sind Anna Beispiel und Bernd Beispiel zu sehen. "
        "Auf dem Bild zu sehen: Two friends laughing by the river. "
        "Meine Erinnerung dazu: Das war vor unserem Testkonzert."
    ),
    "96de1fc:anlass_erzaehler": (
        "Fotodokumentation zum Anlass „Sommerfest Muster“ am 4. "
        "Mai 2019 in Musterstadt. "
        "Die Fotoreihe umfasst 3 Aufnahmen. "
        "Erkannte Beteiligte: Anna Beispiel und Bernd Beispiel. "
        "Aus den überlieferten Aufzeichnungen: Wir haben lange gegrillt. "
        "Ein archiviertes Kapitel im Fotobestand."
    ),
    "96de1fc:anlass_ich": (
        "Das ist die Geschichte zu „Sommerfest Muster“ am 4. "
        "Mai 2019 in Musterstadt. "
        "Zu diesem Anlass gehören 3 Fotos. "
        "Mit dabei waren Anna Beispiel und Bernd Beispiel. "
        "Wir haben lange gegrillt. "
        "Eine wunderbare Fotoserie, die diesen Anlass lebendig hält."
    ),
    "96de1fc:bild_erzaehler": (
        "Eine Aufnahme am 4. "
        "Mai 2019 aus Musterstadt. "
        "Auf diesem Bild sind Anna Beispiel und Bernd Beispiel zu sehen. "
        "Die visuelle Bildanalyse dokumentiert: Zwei Freunde lachen am Flussufer. "
        "Aus den überlieferten Aufzeichnungen: Das war vor unserem Testkonzert."
    ),
    "96de1fc:bild_ich": (
        "Ich erinnere mich gut an diesen Moment am 4. "
        "Mai 2019 in Musterstadt. "
        "Auf dem Bild sind Anna Beispiel und Bernd Beispiel zu sehen. "
        "Das Foto fängt diesen Augenblick ein: Zwei Freunde lachen am Flussufer. "
        "Das war vor unserem Testkonzert."
    ),
}


# ── Hilfen ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def geschichten_pfad(tmp_path, monkeypatch) -> str:
    ereignisse = tmp_path / "ereignisse.jsonl"
    ereignisse.write_text(json.dumps(EREIGNIS, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ereignisse))
    ziel = tmp_path / "geschichten.jsonl"
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(ziel))
    return str(ziel)


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(erzaehlen_router.router)
    return TestClient(app)


def _zeilen(pfad: str):
    if not os.path.isfile(pfad):
        return []
    with open(pfad, encoding="utf-8") as datei:
        return [json.loads(z) for z in datei if z.strip()]


def _notiz(text: str, dk=None, **extra):
    return es.geschichte_speichern(EK, text, "tippen", datei_kennung=dk, **extra)


def _bildgeschichte(text: str, dk=101, ersetzt=None):
    return es.geschichte_speichern(
        EK, text, "generiert", datei_kennung=dk, ersetzt=ersetzt, art="bildgeschichte")


def _anlassgeschichte(text: str, ersetzt=None):
    return es.geschichte_speichern(
        EK, text, "generiert", ersetzt=ersetzt, art="anlassgeschichte")


# ── Satzliste ────────────────────────────────────────────────────────────────

def test_satzliste_hat_69_eintraege_39_e_30_m():
    saetze = es.ALTE_GENERATOR_SAETZE
    assert len(saetze) == 69
    assert sum(1 for _, stufe in saetze if stufe == "E") == 39
    assert sum(1 for _, stufe in saetze if stufe == "M") == 30
    assert len({satz for satz, _ in saetze}) == 69          # keine Doppelten
    assert all(stufe in ("E", "M") for _, stufe in saetze)


def test_quelle_generiert_ist_erlaubt_unbekannte_nicht(geschichten_pfad):
    assert "generiert" in es.QUELLEN_ERLAUBT
    with pytest.raises(es.GeschichteValidierungsfehler):
        es.geschichte_speichern(EK, "Text", "unsinn")


# ── (a) gespeicherte Bildgeschichte ist keine Quelle ─────────────────────────

def test_a_gespeicherte_bildgeschichte_ist_beim_naechsten_lauf_keine_quelle(geschichten_pfad):
    _notiz("Wir waren zusammen am See.", dk=101)
    _bildgeschichte("QQQMARKEQQQ Ein erzeugter Text, der nie Quelle sein darf.", dk=101)
    res = es.ki_geschichte_generieren(fileid=101, ereignis_kennung=EK)
    assert res["ok"] is True
    assert "am See" in res["geschichte"]
    assert "QQQMARKEQQQ" not in res["geschichte"]
    assert "QQQMARKEQQQ" not in res["daten"]["notiz"]


def test_a_erzeugen_speichern_erzeugen_verschachtelt_nicht(geschichten_pfad):
    _notiz("Wir waren zusammen am See.", dk=101)
    erste = es.ki_geschichte_generieren(fileid=101, ereignis_kennung=EK)["geschichte"]
    gespeichert = _bildgeschichte(erste, dk=101)
    zweite = es.ki_geschichte_generieren(fileid=101, ereignis_kennung=EK)["geschichte"]
    assert zweite == erste                                   # gleiche Quelle, gleiche Geschichte
    _bildgeschichte(zweite, dk=101, ersetzt=gespeichert["id"])
    dritte = es.ki_geschichte_generieren(fileid=101, ereignis_kennung=EK)["geschichte"]
    assert dritte == erste
    assert dritte.count("am See") == 1


def test_a_uebergebene_notiz_ist_keine_quelle(geschichten_pfad):
    _notiz("Eine echte Notiz am Bild.", dk=101)
    res = es.ki_geschichte_generieren(fileid=101, ereignis_kennung=EK, notiz="FREMDERTEXT")
    assert "FREMDERTEXT" not in res["geschichte"]
    assert "echte Notiz" in res["geschichte"]


def test_a_route_ignoriert_notiz_aus_der_anfrage(geschichten_pfad, client):
    _notiz("Eine echte Notiz am Bild.", dk=101)
    antwort = client.post("/api/erzaehlen/ki-geschichte", json={
        "fileid": "101", "ereignis_kennung": EK, "notiz": "FREMDERTEXT"}).json()
    assert antwort["ok"] is True
    assert "FREMDERTEXT" not in antwort["geschichte"]
    assert "echte Notiz" in antwort["geschichte"]


# ── (b) alle Notizen fließen ein ─────────────────────────────────────────────

def test_b_alle_notizen_fliessen_ein_neue_notiz_nach_alter_geschichte_auch(geschichten_pfad):
    _notiz("Erste Notiz vom Morgen.", dk=101)
    _notiz("Zweite Notiz vom Mittag.", dk=101)
    _notiz("Gruppennotiz zum ganzen Fest.")                  # ohne Bild: gilt für alle Bilder
    _notiz("Notiz zu einem anderen Bild.", dk=102)
    geschichte = es.ki_geschichte_generieren(fileid=101, ereignis_kennung=EK)
    _bildgeschichte(geschichte["geschichte"], dk=101)
    _notiz("Dritte Notiz, nachträglich eingefügt.", dk=101)

    neu = es.ki_geschichte_generieren(fileid=101, ereignis_kennung=EK)
    text = neu["geschichte"]
    for erwartet in ("Erste Notiz vom Morgen", "Zweite Notiz vom Mittag",
                     "Gruppennotiz zum ganzen Fest", "Dritte Notiz, nachträglich eingefügt"):
        assert erwartet in text, erwartet
    assert "anderen Bild" not in text
    assert text.index("Erste Notiz") < text.index("Zweite Notiz") < text.index("Dritte Notiz")


def test_b_eigene_notizen_zeitlich_sortiert_nur_neueste_fassung(geschichten_pfad):
    spaet = _notiz("Spät geschrieben.", dk=101)
    zeilen = _zeilen(geschichten_pfad)
    zeilen[0]["zeit"] = "2026-11-02T12:00:00+01:00"
    with open(geschichten_pfad, "w", encoding="utf-8") as datei:
        datei.write(json.dumps(zeilen[0], ensure_ascii=False) + "\n")
    frueh = es.geschichte_speichern(EK, "Früher geschrieben.", "tippen", datei_kennung=101)
    zeilen = _zeilen(geschichten_pfad)
    zeilen[1]["zeit"] = "2026-11-01T08:00:00+01:00"
    with open(geschichten_pfad, "w", encoding="utf-8") as datei:
        for z in zeilen:
            datei.write(json.dumps(z, ensure_ascii=False) + "\n")
    # Korrektur der späten Notiz: nur die neueste Fassung zählt.
    es.geschichte_speichern(EK, "Spät, korrigiert.", "tippen", datei_kennung=101, ersetzt=spaet["id"])
    texte = [n["text"] for n in es.eigene_notizen(EK, 101)]
    assert "Spät geschrieben." not in texte
    assert texte[0] == "Früher geschrieben."
    assert "Spät, korrigiert." in texte
    assert frueh["id"] in [n["id"] for n in es.eigene_notizen(EK, 101)]


def test_b_eigene_notizen_ohne_angaben_ist_leer(geschichten_pfad):
    _notiz("Eine Notiz.", dk=101)
    assert es.eigene_notizen(None, None) == []
    assert es.eigene_notizen("", "") == []


# ── (c) Altbestand wird erkannt, normale Notizen nicht ───────────────────────

ALT_SCHLUESSEL = sorted(ALTBESTAND_TEXTE)


def test_c_je_commit_ist_mindestens_ein_text_vorhanden():
    commits = {schluessel.split(":")[0] for schluessel in ALTBESTAND_TEXTE}
    assert commits == {"1da2f9f", "27466f2", "96de1fc", "05db80b"}


@pytest.mark.parametrize("schluessel", ALT_SCHLUESSEL)
def test_c_altbestand_je_fassung_wird_erkannt(schluessel):
    text = ALTBESTAND_TEXTE[schluessel]
    assert es.ist_erzeugt_alt(text) is True, schluessel
    # Auch wenn der Text mit Sebastians eigenem Notizsatz beginnt.
    assert es.ist_erzeugt_alt("Das war ein richtig schöner Tag mit der Familie. " + text) is True
    assert es.ist_erzeugt_alt("Erste eigene Zeile.\n" + text) is True


@pytest.mark.parametrize("schluessel", ALT_SCHLUESSEL)
def test_c_altbestand_als_tippen_zeile_ist_keine_notiz(schluessel):
    zeile = {"id": "x", "text": ALTBESTAND_TEXTE[schluessel], "quelle": "tippen"}
    einordnung = es.zeile_einordnen(zeile)
    assert einordnung == {"ist_notiz": False, "ist_altbestand": True, "art": None}


NORMALE_NOTIZEN = [
    "Heute war ein schöner Tag am See. Wir haben gegrillt und gelacht.",
    "Papa hat das Zelt aufgebaut, Mama hat Kuchen mitgebracht.",
    "Meine Erinnerung dazu: Es hat den ganzen Tag geregnet.",
    "Ich erinnere mich gut an diesen Moment, weil wir so gefroren haben.",
    "Auf dem Bild sind wir noch ganz klein.",
    "Das Bild zeigt unseren alten Garten.",
    "Ein weiteres Foto hält fest: Opa beim Angeln.",
    "Ein schöner Moment zusammen mit Oma.",
]


@pytest.mark.parametrize("text", NORMALE_NOTIZEN)
def test_c_normale_notiz_wird_nicht_erkannt(text):
    assert es.ist_erzeugt_alt(text) is False
    assert es.zeile_einordnen({"text": text, "quelle": "tippen"})["ist_notiz"] is True
    assert es.zeile_einordnen({"text": text, "quelle": "sprache"})["ist_notiz"] is True
    assert es.zeile_einordnen({"text": text, "quelle": "import"})["ist_notiz"] is True


def test_c_leere_und_fremde_eingaben_werfen_nicht():
    assert es.ist_erzeugt_alt("") is False
    assert es.ist_erzeugt_alt(None) is False
    assert es.ist_erzeugt_alt(42) is False
    assert es.zeile_einordnen(None) == {"ist_notiz": False, "ist_altbestand": False, "art": None}
    assert es.zeile_einordnen("kaputt")["ist_notiz"] is False


def test_c_altbestand_bleibt_in_der_datei_und_wird_markiert(geschichten_pfad):
    alt = _notiz(ALTBESTAND_TEXTE["05db80b:bild_ich"], dk=101)
    echte = _notiz("Eine echte Notiz.", dk=101)
    zeilen = {z["id"]: z for z in es.geschichten(ereignis_kennung=EK)}
    assert zeilen[alt["id"]]["ist_altbestand"] is True
    assert zeilen[alt["id"]]["ist_notiz"] is False
    assert zeilen[echte["id"]]["ist_notiz"] is True
    assert zeilen[echte["id"]]["ist_altbestand"] is False
    assert len(_zeilen(geschichten_pfad)) == 2               # nichts gelöscht, nichts umgeschrieben
    assert [n["id"] for n in es.eigene_notizen(EK, 101)] == [echte["id"]]


def test_c_altbestand_fliesst_nie_in_die_quelle(geschichten_pfad):
    _notiz("Eine echte Notiz.", dk=101)
    _notiz(ALTBESTAND_TEXTE["05db80b:bild_ich"], dk=101)        # neueste Zeile ist der Altbestand
    res = es.ki_geschichte_generieren(fileid=101, ereignis_kennung=EK)
    assert "echte Notiz" in res["geschichte"]
    assert "Geborgenheit" not in res["daten"]["notiz"]
    assert res["daten"]["notiz"].count("Eine echte Notiz") == 1


# ── (f) Anlassweg ────────────────────────────────────────────────────────────

def test_f_anlassweg_nimmt_weder_anlassgeschichte_noch_altbestand(geschichten_pfad):
    _notiz("Wir haben lange gegrillt.", dk=101)
    _notiz("Gruppennotiz vom Abend.")
    _notiz(ALTBESTAND_TEXTE["05db80b:anlass_ich"])           # Altbestand als „tippen"-Zeile
    _anlassgeschichte("QQQANLASSQQQ Eine erzeugte Anlassgeschichte.")
    _bildgeschichte("QQQBILDQQQ Eine erzeugte Bildgeschichte.", dk=101)

    res = es.anlass_geschichte_generieren(ereignis_kennung=EK)
    assert res["ok"] is True
    notiz = res["daten"]["notiz"]
    assert "Wir haben lange gegrillt" in notiz
    assert "Gruppennotiz vom Abend" in notiz
    for verboten in ("QQQANLASSQQQ", "QQQBILDQQQ", "Bilderreihe", "wunderbare Erinnerung"):
        assert verboten not in notiz, verboten
    # Die Schablone selbst enthält Sätze wie „Eine lebendige Bilderreihe …": geprüft werden
    # deshalb nur die Marker der gespeicherten Geschichten.
    assert "QQQANLASSQQQ" not in res["geschichte"] and "QQQBILDQQQ" not in res["geschichte"]


def test_f_anlassweg_zaehlt_die_verwendeten_notizen(geschichten_pfad):
    """Zählzeile (03.11.2026): Am Handy sichtbar, wie viele Notizen in die Geschichte flossen."""
    _notiz("Bildnotiz eins.", dk=101)
    _notiz("Bildnotiz zwei.", dk=102)
    _notiz("Gruppennotiz.")
    _anlassgeschichte("QQQANLASSQQQ zählt nicht mit.")
    res = es.anlass_geschichte_generieren(ereignis_kennung=EK)
    assert res["daten"]["anzahl_notizen"] == 3
    assert res["daten"]["erzaehlquelle"] in ("ki", "vorlage")


def test_f_anlassweg_eine_neue_notiz_erscheint_in_der_neuen_quelle(geschichten_pfad):
    _notiz("Alte Notiz.", dk=101)
    erste = es.anlass_geschichte_generieren(ereignis_kennung=EK)
    _anlassgeschichte(erste["geschichte"])
    _notiz("Neue Notiz danach.", dk=102)
    zweite = es.anlass_geschichte_generieren(ereignis_kennung=EK)
    assert "Neue Notiz danach" in zweite["daten"]["notiz"]
    assert "Alte Notiz" in zweite["daten"]["notiz"]
    assert zweite["daten"]["notiz"].count("Alte Notiz") == 1


def test_f_anlassweg_uebergebene_notiz_ist_keine_quelle(geschichten_pfad):
    _notiz("Echte Notiz.", dk=101)
    res = es.anlass_geschichte_generieren(ereignis_kennung=EK, notiz="FREMDERTEXT")
    assert "FREMDERTEXT" not in res["geschichte"]
    assert "Echte Notiz" in res["geschichte"]


# ── (g) notizen_service ──────────────────────────────────────────────────────

def test_g_notizen_service_liefert_keine_art_zeile_und_keinen_altbestand(geschichten_pfad):
    _notiz("Eine echte Notiz zum Fest.", dk=101)
    _bildgeschichte("QQQBILDQQQ erzeugt.", dk=101)
    _anlassgeschichte("QQQANLASSQQQ erzeugt.")
    _notiz(ALTBESTAND_TEXTE["96de1fc:bild_ich"], dk=101)
    texte = [z["text"] for z in notizen_service.geschichten()]
    assert texte == ["Eine echte Notiz zum Fest."]
    antwort = notizen_service.suche("Fest")
    assert [g["text"] for g in antwort["geschichten"]] == ["Eine echte Notiz zum Fest."]
    assert antwort["gesamt_geschichten"] == 1


# ── (h) Router: unbekannte art -> 400 ────────────────────────────────────────

def test_h_router_lehnt_unbekannte_art_mit_400_ab(geschichten_pfad, client):
    antwort = client.post("/api/erzaehlen/geschichten", json={
        "ereignis_kennung": EK, "text": "Text", "quelle": "generiert", "art": "unsinn"})
    assert antwort.status_code == 400
    assert "Art" in antwort.json()["detail"]
    assert _zeilen(geschichten_pfad) == []                   # nichts geschrieben


def test_h_service_art_validierung(geschichten_pfad):
    with pytest.raises(es.GeschichteValidierungsfehler):
        es.geschichte_speichern(EK, "Text", "tippen", art="Bildgeschichte")   # Schreibweise zählt
    with pytest.raises(es.GeschichteValidierungsfehler):
        es.geschichte_speichern(EK, "Text", "tippen", art="notiz")
    # leere Art = keine Art = Notiz
    zeile = es.geschichte_speichern(EK, "Text", "tippen", art="")
    assert zeile["art"] is None and zeile["ist_notiz"] is True
    assert "art" not in _zeilen(geschichten_pfad)[0]


# ── (i) „Das ist keine Notiz, sondern eine Geschichte" ───────────────────────

def test_i_keine_notiz_knopf_haengt_genau_eine_zeile_an(geschichten_pfad, client):
    alt = _notiz("Von Hand nachbearbeiteter Rest ohne festen Satz.", dk=101)
    vorher = len(_zeilen(geschichten_pfad))
    antwort = client.post("/api/erzaehlen/geschichten", json={
        "ereignis_kennung": EK, "text": alt["text"], "quelle": "generiert",
        "datei_kennung": 101, "ersetzt": alt["id"], "art": "bildgeschichte"})
    assert antwort.status_code == 200
    zeilen = _zeilen(geschichten_pfad)
    assert len(zeilen) == vorher + 1
    neu = zeilen[-1]
    assert neu["ersetzt"] == alt["id"] and neu["art"] == "bildgeschichte"
    assert neu["quelle"] == "generiert" and neu["text"] == alt["text"]
    aktuell = es.geschichten(ereignis_kennung=EK)
    assert [(g["id"] == neu["id"], g["ist_notiz"], g["art"]) for g in aktuell] == [
        (True, False, "bildgeschichte")]
    assert es.eigene_notizen(EK, 101) == []                  # jetzt keine Notiz mehr


# ── (j) Stufen-Pflichtfälle ──────────────────────────────────────────────────

def test_j_ein_m_anfang_bleibt_notiz():
    for text in ("Meine Erinnerung dazu: Papa kam spät.",
                 "Ein weiteres Foto hält fest: Opa beim Angeln.",
                 "Auf dem Bild sind wir. Danach gab es Kuchen."):
        assert es.ist_erzeugt_alt(text) is False, text


def test_j_zwei_verschiedene_m_am_satzanfang_zaehlen():
    assert es.ist_erzeugt_alt("Auf dem Bild sind wir zu sehen. Das Bild zeigt uns beim Spielen.") is True
    assert es.ist_erzeugt_alt("Ich war da! Auf dem Bild sind wir. Wirklich? Das Bild zeigt uns.") is True
    # Zeilenumbruch gilt als Satzanfang
    assert es.ist_erzeugt_alt("Auf dem Bild sind wir\nDas Bild zeigt uns") is True


def test_j_derselbe_m_satz_zweimal_zaehlt_einmal():
    assert es.ist_erzeugt_alt("Auf dem Bild sind wir. Auf dem Bild sind auch Opa und Oma.") is False


def test_j_m_mitten_im_satz_zaehlt_nicht():
    assert es.ist_erzeugt_alt(
        "Ich sage immer: Auf dem Bild sind wir klein und ich meine: Das Bild zeigt uns.") is False
    assert es.ist_erzeugt_alt("Wir fanden, Das Bild zeigt uns. Dabei: Auf dem Bild sind alle.") is False


def test_j_e_treffer_irgendwo_genuegt_auch_mitten_im_text():
    assert es.ist_erzeugt_alt("Mein eigener Satz, dann Auf dem Foto wird dieser Augenblick lebendig: nichts.") is True
    assert es.ist_erzeugt_alt("Vorne steht etwas. Ein festgehaltener Augenblick aus dem Fotoarchiv.") is True


def test_j_leerraum_wird_normalisiert():
    assert es.ist_erzeugt_alt("Ein festgehaltener   Augenblick\naus dem  Fotoarchiv.") is True
    assert es.ist_erzeugt_alt("Auf dem   Bild sind wir.\n\n   Das Bild   zeigt uns.") is True


def test_j_bestaetigt_schlaegt_e(geschichten_pfad):
    e_text = ALTBESTAND_TEXTE["05db80b:bild_ich"]
    assert es.zeile_einordnen({"text": e_text, "quelle": "tippen"})["ist_altbestand"] is True
    bestaetigt = es.zeile_einordnen({"text": e_text, "quelle": "tippen", "notiz_bestaetigt": True})
    assert bestaetigt == {"ist_notiz": True, "ist_altbestand": False, "art": None}
    # nur echtes True zählt
    assert es.zeile_einordnen({"text": e_text, "quelle": "tippen", "notiz_bestaetigt": "ja"})["ist_altbestand"] is True


def test_j_art_schlaegt_alles():
    e_text = ALTBESTAND_TEXTE["05db80b:bild_ich"]
    assert es.zeile_einordnen({"text": e_text, "quelle": "generiert", "art": "bildgeschichte"}) == {
        "ist_notiz": False, "ist_altbestand": False, "art": "bildgeschichte"}
    assert es.zeile_einordnen({"text": "x", "quelle": "tippen", "art": "anlassgeschichte",
                               "notiz_bestaetigt": True})["ist_notiz"] is False


def test_j_quelle_generiert_ohne_art_ist_keine_notiz():
    assert es.zeile_einordnen({"text": "x", "quelle": "generiert"})["ist_notiz"] is False
    assert es.zeile_einordnen({"text": "x", "quelle": "tippen"})["ist_notiz"] is True


# ── (k) „Das ist meine Notiz" ────────────────────────────────────────────────

def test_k_das_ist_meine_notiz_haengt_genau_eine_zeile_an(geschichten_pfad, client):
    alt = _notiz(ALTBESTAND_TEXTE["05db80b:bild_erzaehler"], dk=101)
    assert es.geschichten(ereignis_kennung=EK)[0]["ist_notiz"] is False
    vorher = len(_zeilen(geschichten_pfad))
    antwort = client.post("/api/erzaehlen/geschichten", json={
        "ereignis_kennung": EK, "text": alt["text"], "quelle": "tippen", "datei_kennung": 101,
        "ersetzt": alt["id"], "notiz_bestaetigt": True})
    assert antwort.status_code == 200
    zeilen = _zeilen(geschichten_pfad)
    assert len(zeilen) == vorher + 1
    assert zeilen[-1]["notiz_bestaetigt"] is True and zeilen[-1]["ersetzt"] == alt["id"]
    aktuell = es.geschichten(ereignis_kennung=EK)
    assert len(aktuell) == 1
    assert aktuell[0]["ist_notiz"] is True and aktuell[0]["ist_altbestand"] is False
    assert [n["id"] for n in es.eigene_notizen(EK, 101)] == [aktuell[0]["id"]]


# ── (m) Kachelzähler ─────────────────────────────────────────────────────────

def test_m_kachelzaehler_zaehlt_nur_notizen(geschichten_pfad):
    _notiz("Eine echte Notiz.", dk=101)
    _notiz("Noch eine echte Notiz.")
    _bildgeschichte("Erzeugt.", dk=101)
    _anlassgeschichte("Erzeugt für den Anlass.")
    _notiz(ALTBESTAND_TEXTE["27466f2:bild_ich"], dk=102)
    eintrag = next(e for e in es.ereignisse_liste()["eintraege"] if e["kennung"] == EK)
    assert eintrag["anzahl_geschichten"] == 2


def test_m_bestaetigte_notiz_zaehlt_wieder(geschichten_pfad):
    alt = _notiz(ALTBESTAND_TEXTE["27466f2:bild_ich"], dk=102)
    liste = lambda: next(e for e in es.ereignisse_liste()["eintraege"] if e["kennung"] == EK)  # noqa: E731
    assert liste()["anzahl_geschichten"] == 0
    es.geschichte_speichern(EK, alt["text"], "tippen", datei_kennung=102, ersetzt=alt["id"],
                            notiz_bestaetigt=True)
    assert liste()["anzahl_geschichten"] == 1


def test_m_detail_traegt_die_felder(geschichten_pfad):
    _notiz("Eine echte Notiz.", dk=101)
    _bildgeschichte("Erzeugt.", dk=101)
    detail = es.ereignis_detail(EK)
    assert sorted(g["ist_notiz"] for g in detail["geschichten"]) == [False, True]
    assert {g["art"] for g in detail["geschichten"]} == {None, "bildgeschichte"}


# ── (n) Transportweg: POST -> Datei -> geschichten() ─────────────────────────

def test_n_rundreise_art_und_notiz_bestaetigt_bleiben_erhalten(geschichten_pfad, client):
    a = client.post("/api/erzaehlen/geschichten", json={
        "ereignis_kennung": EK, "text": "Eine Bildgeschichte.", "quelle": "generiert",
        "datei_kennung": 101, "art": "bildgeschichte"}).json()
    b = client.post("/api/erzaehlen/geschichten", json={
        "ereignis_kennung": EK, "text": "Eine bestätigte Notiz.", "quelle": "tippen",
        "datei_kennung": 101, "notiz_bestaetigt": True}).json()
    assert a["ok"] and b["ok"]
    zeilen = _zeilen(geschichten_pfad)
    assert zeilen[0]["art"] == "bildgeschichte" and "notiz_bestaetigt" not in zeilen[0]
    assert zeilen[1]["notiz_bestaetigt"] is True and "art" not in zeilen[1]
    gelesen = {g["id"]: g for g in es.geschichten(ereignis_kennung=EK)}
    assert gelesen[a["geschichte"]["id"]]["art"] == "bildgeschichte"
    assert gelesen[b["geschichte"]["id"]]["notiz_bestaetigt"] is True
    assert gelesen[b["geschichte"]["id"]]["ist_notiz"] is True


def test_n_unbekannter_schluessel_wird_verworfen(geschichten_pfad, client):
    antwort = client.post("/api/erzaehlen/geschichten", json={
        "ereignis_kennung": EK, "text": "Notiz.", "quelle": "tippen",
        "boese": "x", "ist_notiz": False, "ist_altbestand": True})
    assert antwort.status_code == 200
    zeile = _zeilen(geschichten_pfad)[0]
    assert "boese" not in zeile
    assert "ist_notiz" not in zeile and "ist_altbestand" not in zeile   # Einordnung wird nie gespeichert
    assert antwort.json()["geschichte"]["ist_notiz"] is True


def test_n_notiz_bestaetigt_false_wird_nicht_gespeichert(geschichten_pfad):
    es.geschichte_speichern(EK, "Notiz.", "tippen", notiz_bestaetigt=False)
    assert "notiz_bestaetigt" not in _zeilen(geschichten_pfad)[0]


# ── (o) Backend: POST-Antwort mit Einordnung ─────────────────────────────────

def test_o_post_antwort_traegt_ist_notiz_und_art(geschichten_pfad, client):
    notiz = client.post("/api/erzaehlen/geschichten", json={
        "ereignis_kennung": EK, "text": "Eine Notiz.", "quelle": "tippen"}).json()["geschichte"]
    assert notiz["ist_notiz"] is True and notiz["ist_altbestand"] is False and notiz["art"] is None
    bild = client.post("/api/erzaehlen/geschichten", json={
        "ereignis_kennung": EK, "text": "Eine Geschichte.", "quelle": "generiert",
        "datei_kennung": 101, "art": "bildgeschichte"}).json()["geschichte"]
    assert bild["ist_notiz"] is False and bild["ist_altbestand"] is False and bild["art"] == "bildgeschichte"
    alt = client.post("/api/erzaehlen/geschichten", json={
        "ereignis_kennung": EK, "text": ALTBESTAND_TEXTE["96de1fc:bild_erzaehler"],
        "quelle": "tippen"}).json()["geschichte"]
    assert alt["ist_notiz"] is False and alt["ist_altbestand"] is True


def test_o_get_geschichten_traegt_die_felder(geschichten_pfad, client):
    _notiz("Eine Notiz.", dk=101)
    _bildgeschichte("Eine Geschichte.", dk=101)
    liste = client.get("/api/erzaehlen/geschichten", params={"ereignis_kennung": EK}).json()["geschichten"]
    assert sorted((g["ist_notiz"], g["art"]) for g in liste) == [(False, "bildgeschichte"), (True, None)]
