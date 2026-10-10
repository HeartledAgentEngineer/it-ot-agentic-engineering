"""Laufende Arbeiten im Fortschritts-Werkzeug: zwei lebende Balken.

Prueft die neue Messung der Ergebnisdateien aus
``werkzeuge/fortschritt/fortschritt.py`` mit ERFUNDENEN Dateien in tmp_path —
die echten Ergebnisdateien in ``foto_sortierung/`` (Bildbeschreibung reich,
Gesichtserkennung Papas Fotos) werden nie angefasst; es gibt keine Netz- und
keine pCloud-Zugriffe.

Abgedeckt (Auftrag vom 10.10.2026):

* (a) Prozente stimmen bei 50 von 100,
* (b) fehlende Datei fuehrt zu 0 Prozent ohne Absturz,
* (c) eine kaputte letzte Zeile fuehrt nicht zum Absturz (letzte lesbare
  Zeile plus Hinweis),
* (d) Kosten werden summiert,
* dazu die Anzeige in Terminal UND HTML (Zahlen, Kosten, zuletzt bearbeitet).

Das Werkzeug liegt im Arbeitsbaum unter ``werkzeuge/fortschritt/``, das
Backend unter ``personal_ai_agent/backend`` — von dieser Testdatei aus vier
Ebenen hoch.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[4]
FORT_SCHRITT = WORKSPACE / "werkzeuge" / "fortschritt" / "fortschritt.py"


@pytest.fixture(scope="module")
def fortschritt():
    """Das Werkzeug als Modul laden (Datei-Import; kein Paket noetig)."""
    assert FORT_SCHRITT.is_file(), f"Werkzeug nicht gefunden: {FORT_SCHRITT}"
    spec = importlib.util.spec_from_file_location("fortschritt_laufend", FORT_SCHRITT)
    modul = importlib.util.module_from_spec(spec)
    sys.modules["fortschritt_laufend"] = modul
    spec.loader.exec_module(modul)
    return modul


def _zeile(**felder) -> str:
    """Eine Ergebniszeile als JSON-Text (ohne Zeilenende)."""
    return json.dumps(felder, ensure_ascii=False)


# ---------------------------------------------------------------------------
# (a) Prozente
# ---------------------------------------------------------------------------

def test_prozente_stimmen_bei_50_von_100(fortschritt, tmp_path):
    pfad = tmp_path / "fuenfzig.jsonl"
    pfad.write_text("".join(_zeile(nr=n) + "\n" for n in range(50)), encoding="utf-8")

    mess = fortschritt.messe_jsonl(pfad, 100)
    assert mess["fertig"] == 50
    assert mess["gesamt"] == 100
    assert mess["prozent"] == 50.0
    assert mess["hinweis"] == ""


def test_mehr_zeilen_als_geplant_kappen_bei_100_prozent(fortschritt, tmp_path):
    pfad = tmp_path / "zu_viel.jsonl"
    pfad.write_text("".join(_zeile(nr=n) + "\n" for n in range(101)), encoding="utf-8")
    mess = fortschritt.messe_jsonl(pfad, 100)
    assert mess["fertig"] == 101        # roh ehrlich gezaehlt
    assert mess["prozent"] == 100.0     # Balken nie ueber 100


# ---------------------------------------------------------------------------
# (b) Fehlende Datei
# ---------------------------------------------------------------------------

def test_fehlende_datei_ergibt_null_prozent_ohne_absturz(fortschritt, tmp_path):
    mess = fortschritt.messe_jsonl(tmp_path / "gibts_noch_nicht.jsonl", 100)
    assert mess["fertig"] == 0
    assert mess["gesamt"] == 100
    assert mess["prozent"] == 0.0
    assert mess["letzte_datei"] == ""
    assert "fehlt noch" in mess["hinweis"]


# ---------------------------------------------------------------------------
# (c) Kaputte letzte Zeile
# ---------------------------------------------------------------------------

def test_halb_geschriebene_letzte_zeile_stuerzt_nicht_ab(fortschritt, tmp_path):
    pfad = tmp_path / "angebrochen.jsonl"
    pfad.write_text(
        _zeile(datei="a.jpg", zeit="2026-10-10T07:00:01") + "\n"
        + _zeile(datei="b.jpg", zeit="2026-10-10T07:00:02") + "\n"
        + '{"datei": "c.jpg", "beschreib',          # halb geschrieben: kein Zeilenende
        encoding="utf-8",
    )

    mess = fortschritt.messe_jsonl(pfad, 100, mit_kosten=True)
    assert mess["fertig"] == 2                       # nur abgeschlossene Zeilen
    assert mess["letzte_datei"] == "b.jpg"           # letzte LESBARE Zeile
    assert mess["letzte_zeit"] == "10.10.2026 07:00:02"
    assert "nicht fertig geschrieben" in mess["hinweis"]


def test_kaputte_zeile_mitten_in_der_datei_wird_uebersprungen(fortschritt, tmp_path):
    """Eine abgeschlossene, aber unlesbare Zeile zaehlt nicht als Eintrag und wird gemeldet."""
    pfad = tmp_path / "eine_kaputt.jsonl"
    pfad.write_text(
        _zeile(datei="a.jpg") + "\n"
        + '{"datei": kaputt-ohne-anfuehrungszeichen}\n'
        + _zeile(datei="c.jpg") + "\n",
        encoding="utf-8",
    )

    mess = fortschritt.messe_jsonl(pfad, 100, mit_kosten=True)
    assert mess["letzte_datei"] == "c.jpg"
    assert "nicht lesbar" in mess["hinweis"]


# ---------------------------------------------------------------------------
# (d) Kosten
# ---------------------------------------------------------------------------

def test_kosten_werden_summiert(fortschritt, tmp_path):
    pfad = tmp_path / "kosten.jsonl"
    pfad.write_text("".join([
        _zeile(datei="a.jpg", kosten_usd=0.5) + "\n",
        _zeile(datei="b.jpg", kosten_usd=0.25) + "\n",
        _zeile(datei="c.jpg", kosten_usd=0.25) + "\n",
    ]), encoding="utf-8")

    mess = fortschritt.messe_jsonl(pfad, 100, mit_kosten=True)
    assert mess["fertig"] == 3
    assert mess["kosten_usd"] == pytest.approx(1.0)

    # Die Gesichtsdatei hat kein Kostenfeld — dann wird gar nicht summiert.
    ohne = fortschritt.messe_jsonl(pfad, 100, mit_kosten=False)
    assert ohne["kosten_usd"] is None


def test_kosten_mit_kaputtem_wert_zaehlen_als_null(fortschritt, tmp_path):
    pfad = tmp_path / "kosten_kaputt.jsonl"
    pfad.write_text(
        _zeile(datei="a.jpg", kosten_usd=0.125) + "\n"
        + _zeile(datei="b.jpg", kosten_usd="keine-zahl") + "\n",
        encoding="utf-8",
    )
    mess = fortschritt.messe_jsonl(pfad, 100, mit_kosten=True)
    assert mess["kosten_usd"] == pytest.approx(0.125)


# ---------------------------------------------------------------------------
# "Wo steht er gerade" — letzte Zeile und Ersatz-Uhrzeit
# ---------------------------------------------------------------------------

def test_letzte_zeile_ohne_zeitfeld_nutzt_die_dateiaenderung(fortschritt, tmp_path):
    pfad = tmp_path / "vektoren.jsonl"
    pfad.write_text(_zeile(bild_id="108861601298", gesichter=[]) + "\n", encoding="utf-8")

    mess = fortschritt.messe_jsonl(pfad, 10)
    assert mess["letzte_datei"] == "108861601298"
    assert mess["zeit_quelle"] == "datei"
    assert mess["letzte_zeit"]                       # aus dem Dateistand, nicht leer


def test_noch_leere_datei_meldet_das_ehrlich(fortschritt, tmp_path):
    pfad = tmp_path / "leer.jsonl"
    pfad.write_text("", encoding="utf-8")
    mess = fortschritt.messe_jsonl(pfad, 10)
    assert mess["fertig"] == 0
    assert "noch kein fertiger eintrag" in mess["hinweis"].lower()


# ---------------------------------------------------------------------------
# Anzeige: Terminal und HTML
# ---------------------------------------------------------------------------

def _probe_daten():
    return {
        "aufgabe": "Probe",
        "stand": "10.10.2026 08:00:00",
        "schritte": [],
        "laufende": [
            {
                "titel": "Bildbeschreibung reich",
                "auftrag": "489 Boegen zu je 36 Kacheln",
                "einheit": "Bilder",
                "fertig": 50, "gesamt": 100, "prozent": 50.0,
                "kosten_usd": 0.55, "budget_usd": 12.0,
                "datei": "C:/probe/reich.jsonl",
                "letzte_datei": "b.jpg", "letzte_zeit": "10.10.2026 07:00:02",
                "zeit_quelle": "eintrag", "hinweis": "",
            },
            {
                "titel": "Gesichtserkennung Papas Fotos",
                "auftrag": "", "einheit": "Bilder",
                "fertig": 25, "gesamt": 50, "prozent": 50.0,
                "kosten_usd": None, "budget_usd": None,
                "datei": "C:/probe/vektoren.jsonl",
                "letzte_datei": "1088", "letzte_zeit": "10.10.2026 07:00:03",
                "zeit_quelle": "datei", "hinweis": "",
            },
        ],
    }


def test_terminal_zeigt_balken_zahlen_kosten_und_zuletzt(fortschritt):
    text = fortschritt.terminal(_probe_daten())
    assert "Laufende Arbeiten:" in text
    assert "50 von 100 Bilder" in text
    assert "50,0 %" in text
    assert "0,5500 von 12,00 USD" in text
    assert "zuletzt bearbeitet: b.jpg — 10.10.2026 07:00:02" in text
    assert "zuletzt: 1088 — Datei geaendert 10.10.2026 07:00:03" in text


def test_html_zeigt_laufende_balken_ohne_fremdquellen(fortschritt):
    seite = fortschritt.html(_probe_daten())
    assert "Laufende Arbeiten" in seite
    assert "fuell-lauf" in seite                       # einfache CSS-Rechtecke
    assert "50 von 100 Bilder" in seite
    assert "0,5500 von 12,00 USD" in seite
    assert "zuletzt: 1088 — Datei geaendert 10.10.2026 07:00:03" in seite
    # Keine Fremdbibliotheken, kein Netzzugriff der Anzeige.
    assert "http://" not in seite and "https://" not in seite
    assert "<script" not in seite


def test_ohne_laufende_bleibt_die_alte_anzeige_unveraendert(fortschritt):
    daten = {"aufgabe": "Nur Schritte", "stand": "10.10.2026 08:00:00",
             "schritte": [{"nr": 1, "text": "Schritt eins", "lage": "fertig"}]}
    text = fortschritt.terminal(daten)
    assert "Laufende Arbeiten:" not in text
    assert "1. Schritt eins" in text
    seite = fortschritt.html(daten)
    assert "Laufende Arbeiten" not in seite
