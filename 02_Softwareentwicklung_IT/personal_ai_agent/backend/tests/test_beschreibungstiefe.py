"""Pruefungen fuer ``tools/foto_sortierung/beschreibungstiefe_messen.py`` (15.10.2026).

Offline: erfundene Beschreibungen und Kennungen, keine echten Daten, kein Netz, kein Bild,
kein Modell. Geprueft wird, dass nur Zahlen entstehen und kein Textinhalt im Bericht landet.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "beschreibungstiefe_messen.py"
BESCHREIBEN = REPO / "tools" / "foto_sortierung" / "bild_beschreiben.py"

spez = importlib.util.spec_from_file_location("beschreibungstiefe_messen", WERKZEUG)
assert spez is not None and spez.loader is not None
bt = importlib.util.module_from_spec(spez)
spez.loader.exec_module(bt)


# ── Hilfen ───────────────────────────────────────────────────────────────────

def _datei(pfad: Path, beschreibungen, kaputt: bool = False) -> Path:
    zeilen = [json.dumps({"fileid": i, "beschreibung": t, "modell": "erfunden"}) + "\n"
              for i, t in enumerate(beschreibungen)]
    if kaputt:
        zeilen.append("{kein json\n")
    pfad.write_text("".join(zeilen), encoding="utf-8")
    return pfad


# ── 1. Zahlen ────────────────────────────────────────────────────────────────

def test_zaehlt_woerter_zeichen_und_saetze(tmp_path):
    texte = ["ein zwei drei", "eins zwei drei vier fünf sechs sieben acht neun zehn elf zwolf"]
    k = bt.kennzahlen(texte)
    assert k["n"] == 2
    assert k["woerter_median"] == 7.5          # (3 + 12) / 2
    assert k["woerter_max"] == 12
    assert k["zeichen_median"] == (len(texte[0]) + len(texte[1])) / 2
    assert k["saetze_median"] == 1.0           # beide ohne Satzzeichen
    assert k["leer"] == 0


def test_leere_liste_ergibt_nullen():
    k = bt.kennzahlen([])
    assert k["n"] == 0 and k["woerter_max"] == 0 and k["saetze_max"] == 0


def test_satzgrenzen_werden_gezaehlt():
    k = bt.kennzahlen(["eins. zwei. drei. vier."])
    assert k["saetze_max"] == 4 and k["saetze_median"] == 4.0


def test_lesen_zaehlt_kaputte_zeile_statt_zu_werfen(tmp_path):
    pfad = _datei(tmp_path / "a.jsonl", ["eins zwei", "drei vier"], kaputt=True)
    texte, kaputt = bt.texte_lesen(pfad)
    assert kaputt == 1
    assert texte == ["eins zwei", "drei vier"]


def test_fehlende_beschreibung_zaehlt_als_leer(tmp_path):
    pfad = tmp_path / "b.jsonl"
    pfad.write_text(json.dumps({"fileid": 1}) + "\n" + json.dumps({"beschreibung": 42}) + "\n",
                    encoding="utf-8")
    texte, kaputt = bt.texte_lesen(pfad)
    assert kaputt == 0
    assert texte == ["", ""]
    assert bt.kennzahlen(texte)["leer"] == 2


# ── 2. Sprache (grob, nur Anteile) ───────────────────────────────────────────

def test_sprachschaetzung_trennt_deutsch_und_englisch():
    deutsch = ["der Mann ist mit dem Hund auf der Wiese und die Frau lacht"]
    englisch = ["the man is with the dog on the field and the woman is laughing"]
    d, e = bt.sprache_schaetzen(deutsch + englisch)
    assert d == 50.0 and e == 50.0
    d2, e2 = bt.sprache_schaetzen(deutsch)
    assert d2 == 100.0 and e2 == 0.0
    assert bt.sprache_schaetzen([]) == (0.0, 0.0)


# ── 3. Bericht ───────────────────────────────────────────────────────────────

def test_fehlende_datei_wird_gemeldet_ohne_abbruch(tmp_path):
    zeilen = list(bt.bericht([("erfunden", "gibtsnicht.jsonl")], tmp_path, grenzen={}))
    text = "\n".join(zeilen)
    assert "erfunden" in text and "fehlt" in text
    assert "Wortgrenzen nicht gelesen" in text


def test_bericht_enthaelt_nur_zahlen_und_keinen_text(tmp_path):
    geheim = "ZwiebelkuchenMitGeheimwort"
    pfad = _datei(tmp_path / "c.jsonl", [f"{geheim} eins zwei drei vier fünf"])
    zeilen = list(bt.bericht([("erfunden", "c.jsonl")], tmp_path, grenzen={"stichwort": 14}))
    text = "\n".join(zeilen)
    assert geheim not in text                      # kein Beschreibungstext im Bericht
    assert "Zeilen 1" in text
    assert "stichwort: 14 Woerter" in text


def test_perzentil_bei_kleinen_listen():
    assert bt._perzentil([], 0.9) == 0
    assert bt._perzentil([5], 0.9) == 5
    assert bt._perzentil([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9) == 9


# ── 4. Wortgrenzen aus dem echten Werkzeug ───────────────────────────────────

def test_wortgrenzen_liest_das_echte_werkzeug():
    grenzen = bt.wortgrenzen(BESCHREIBEN)
    assert grenzen.get("stichwort") == 14
    assert grenzen.get("bildgeschichte") == 70
    assert bt.wortgrenzen(Path(WERKZEUG.parent / "gibtsnicht.py")) == {}


# ── 5. Kommandozeile ─────────────────────────────────────────────────────────

def test_main_meldet_wenn_keine_datei_da_ist(tmp_path, capsys):
    assert bt.main(["--ordner", str(tmp_path)]) == 2
    assert "keine Beschreibungsdatei gefunden" in capsys.readouterr().out


def test_main_mit_eigener_datei(tmp_path, capsys):
    _datei(tmp_path / "d.jsonl", ["eins zwei drei", "vier fünf sechs sieben"])
    assert bt.main(["--ordner", str(tmp_path), "--dateien", "eigene=d.jsonl"]) == 0
    ausgabe = capsys.readouterr().out
    assert "eigene (d.jsonl)" in ausgabe
    assert "Woerter Median 3.5" in ausgabe
    assert "Wortgrenze je Prompt-Fassung" in ausgabe


def test_main_weist_falsche_dateiangabe_ab(capsys):
    assert bt.main(["--dateien", "ohnepfad"]) == 2
    assert "Name=pfad" in capsys.readouterr().out
