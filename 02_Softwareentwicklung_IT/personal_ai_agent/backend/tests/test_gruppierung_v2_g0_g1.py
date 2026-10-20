"""Tests: G0/G1 von v2 — Pflichtquellen, Geraetenachweis, Zustand (Auflage 2).

Plan ``.hermes/plans/2026-10-20_gruppierung-v2-fassung5.md``, Auflage 2:

* **G0 Pflichtquellen:** ``personen_bestaetigt.json`` und
  ``personen_vorgaben.json`` sind Pflicht — eine FEHLENDE Datei ist kein leerer
  Bestand, sondern Exit 2 ohne Rechnen und ohne Schreiben.
* **Vollstaendigkeitsnachweis:** je Pflichtquelle werden sha256 und die
  durchgezaehlten Eintraege der PC-Datei gegen den **Geraetestand** des Handys
  gehalten (``geraetestand.json``, geschrieben von
  ``termux/rueckweg-bereitstellen.sh``). Abweichung -> Exit 2; ohne Nachweis
  rechnet v2 nur als **Trockenmessung** (``--ohne-geraetenachweis``), ein
  Schreiben damit wird abgelehnt.
* **G1:** die Zustaende ``vorlaeufig`` und ``veraltet`` aus
  ``gruppierung_bewerten.grundwahrheit()`` sperren ``--schreiben`` (Exit 3) —
  auch fuer den Kandidatenordner; die Trockenmessung bleibt erlaubt.

Alles offline mit ERFUNDENEN Vektoren und ERFUNDENEN Namen ("Person A") — keine
echten Gesichter, keine echten Namen, kein Netz, kein Geraet, nichts unter
``~/foto_sortierung``. Der Geraetestand wird hier von Hand gebaut (sha256 ueber
``hashlib``, Zaehlung im Test selbst) — absichtlich NICHT ueber die Funktionen
des Werkzeugs, damit der Nachweis unabhaengig geprueft wird.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_gruppierung_v2_g0_g1.py -q
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time

import numpy as np
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
WERKZEUGE = os.path.join(os.path.dirname(BACKEND), "tools", "foto_sortierung")
sys.path.insert(0, WERKZEUGE)
REPO = os.path.dirname(BACKEND)


def _laden(name):
    spez = importlib.util.spec_from_file_location(name, os.path.join(WERKZEUGE, name + ".py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


pg = _laden("personen_gruppieren")
gb = _laden("gruppierung_bewerten")
D = 128


# ── Erfundene Grundlage ────────────────────────────────────────────────────

def _bestaetigt(tmp_path, anzahl=1, name="personen_bestaetigt.json"):
    """Eine ``personen_bestaetigt.json`` mit erfundenen Namen."""
    daten = {"bestaetigt": {f"Person_{i:03d}": f"Person {chr(64 + i)}"
                            for i in range(1, anzahl + 1)}}
    ziel = tmp_path / name
    ziel.write_text(json.dumps(daten), encoding="utf-8")
    return ziel


def _vorgaben(tmp_path, regeln=0, name="personen_vorgaben.json"):
    """Eine ``personen_vorgaben.json``; ``regeln`` fuellt Ausschluesse (G1)."""
    daten = {"gleich": [], "verschieden": [], "ausgeschlossen": [], "zugeordnet": []}
    for i in range(regeln):
        daten["ausgeschlossen"].append({"kennung": f"Person_{i:03d}",
                                        "bild_id": str(900000 + i), "index": 0})
    ziel = tmp_path / name
    ziel.write_text(json.dumps(daten), encoding="utf-8")
    return ziel


def _stand_eintrag(pfad):
    """Der Eintrag, den das Handy zu einer Datei schreibt (sha256 + Zaehlung)."""
    roh = pfad.read_bytes()
    daten = json.loads(roh.decode("utf-8"))
    if pfad.name.endswith("bestaetigt.json"):
        eintraege = daten.get("bestaetigt") or {}
        zaehler = {"benannte_kennungen": len(eintraege),
                   "namen": sum(1 for w in eintraege.values()
                                if isinstance(w, str) and w.strip())}
    else:
        zaehler = {"gleich": len(daten.get("gleich") or []),
                   "verschieden": len(daten.get("verschieden") or []),
                   "ausgeschlossen": len(daten.get("ausgeschlossen") or []),
                   "fest": len(daten.get("zugeordnet") or [])}
    return {"bytes": len(roh), "sha256": hashlib.sha256(roh).hexdigest(),
            "zaehler": zaehler}


def _stand(tmp_path, bestaetigt, vorgaben, name="geraetestand.json", stand=None,
           dateien=None):
    """Einen Geraetestand schreiben, wie ihn das Handy erzeugt."""
    if dateien is None:
        dateien = {bestaetigt.name: _stand_eintrag(bestaetigt),
                   vorgaben.name: _stand_eintrag(vorgaben)}
    ziel = tmp_path / name
    ziel.write_text(json.dumps({
        "stand": stand or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "quelle": "handy", "pflicht": list(pg.PFLICHTQUELLEN), "dateien": dateien}),
        encoding="utf-8")
    return str(ziel)


# ── Erfundene Vektoren (wie in den Nachbardateien) ─────────────────────────

def _basis(rng, n):
    q, _ = np.linalg.qr(rng.normal(size=(D, n)))
    return q.T


def _gesicht(rng, mitte, naehe=0.85):
    rausch = rng.normal(size=D)
    rausch -= rausch.dot(mitte) * mitte
    rausch /= np.linalg.norm(rausch)
    return naehe * mitte + np.sqrt(1 - naehe ** 2) * rausch


def _zeile(bild_id, vektor, jahr=2016, seite=200):
    return json.dumps({
        "bild_id": bild_id, "breite": 1000, "hoehe": 1000,
        "metadaten": {"aufnahme": f"{jahr}-06-01T12:00:00"},
        "gesichter": [{"bbox": [10, 10, seite, seite], "score": 0.95,
                       "embedding": [float(x) for x in vektor]}]})


def _vektordatei(tmp_path, personen=2, je=8, seed=41):
    rng = np.random.default_rng(seed)
    e = _basis(rng, personen)
    zeilen = [_zeile(str(1000 + 100 * p + i), _gesicht(rng, e[p]), 2015 + (i % 3))
              for p in range(personen) for i in range(je)]
    datei = tmp_path / "v.jsonl"
    datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return datei


# ── Die Funktion selbst: entscheidungen_pruefen ───────────────────────────

def test_pruefung_ohne_geraetestand_ist_nicht_erbracht(tmp_path):
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path)
    for stand in (None, {}, {"stand": "2026-10-20T10:00:00Z"}):
        ergebnis = pg.entscheidungen_pruefen(str(b), str(v), stand, None)
        assert ergebnis["erbracht"] is False
        assert ergebnis["abweichung"] is False, "kein Geraet ist keine Messung"
        assert ergebnis["zeilen"] and "nicht erbracht" in ergebnis["zeilen"][0]
        assert str(tmp_path) not in ergebnis["zeilen"][0], "kein Pfad im Bericht"


def test_pruefung_mit_passendem_stand_ist_erbracht(tmp_path):
    b, v = _bestaetigt(tmp_path, anzahl=3), _vorgaben(tmp_path, regeln=2)
    stand = _stand(tmp_path, b, v)
    ergebnis = pg.entscheidungen_pruefen(str(b), str(v), pg.geraetestand_lesen(stand), None)
    assert ergebnis["erbracht"] is True
    assert ergebnis["abweichung"] is False
    assert ergebnis["gruende"] == []
    assert "erbracht" in ergebnis["zeilen"][0]


@pytest.mark.parametrize("feld", ["benannte_kennungen", "namen"])
def test_pruefung_zahl_weicht_ab_bestaetigt(tmp_path, feld):
    """Halb uebertragene Entscheidungen: die ZAHL weicht ab, nicht nur der hash."""
    b, v = _bestaetigt(tmp_path, anzahl=3), _vorgaben(tmp_path)
    dateien = {b.name: _stand_eintrag(b), v.name: _stand_eintrag(v)}
    dateien[b.name]["zaehler"][feld] += 1
    stand = _stand(tmp_path, b, v, dateien=dateien, name=f"stand_{feld}.json")
    ergebnis = pg.entscheidungen_pruefen(str(b), str(v), pg.geraetestand_lesen(stand), None)
    assert ergebnis["erbracht"] is False and ergebnis["abweichung"] is True
    assert "Zahl weicht ab" in ergebnis["zeilen"][0]
    assert str(tmp_path) not in ergebnis["zeilen"][0]


@pytest.mark.parametrize("feld", ["gleich", "verschieden", "ausgeschlossen", "fest"])
def test_pruefung_zahl_weicht_ab_vorgaben(tmp_path, feld):
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path, regeln=2)
    dateien = {b.name: _stand_eintrag(b), v.name: _stand_eintrag(v)}
    dateien[v.name]["zaehler"][feld] += 1
    stand = _stand(tmp_path, b, v, dateien=dateien, name=f"stand_{feld}.json")
    ergebnis = pg.entscheidungen_pruefen(str(b), str(v), pg.geraetestand_lesen(stand), None)
    assert ergebnis["erbracht"] is False and ergebnis["abweichung"] is True
    assert "Zahl weicht ab (personen_vorgaben.json" in ergebnis["zeilen"][0]


def test_pruefung_sha256_abweichung_ist_eine_abweichung(tmp_path):
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path)
    dateien = {b.name: _stand_eintrag(b), v.name: _stand_eintrag(v)}
    dateien[v.name]["sha256"] = "0" * 64
    ergebnis = pg.entscheidungen_pruefen(str(b), str(v),
                                         pg.geraetestand_lesen(
                                             _stand(tmp_path, b, v, dateien=dateien)),
                                         None)
    assert ergebnis["abweichung"] is True
    assert "sha256 weicht ab" in ergebnis["zeilen"][0]


def test_pruefung_bytezahl_abweichung_ist_eine_abweichung(tmp_path):
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path)
    dateien = {b.name: _stand_eintrag(b), v.name: _stand_eintrag(v)}
    dateien[b.name]["bytes"] += 5
    ergebnis = pg.entscheidungen_pruefen(str(b), str(v),
                                         pg.geraetestand_lesen(
                                             _stand(tmp_path, b, v, dateien=dateien)),
                                         None)
    assert ergebnis["abweichung"] is True
    assert "Bytezahl weicht ab" in ergebnis["zeilen"][0]


def test_pruefung_ohne_zaehlung_ist_nicht_erbracht(tmp_path):
    """Ein Handy ohne Python liefert keine Zaehlung: kein Nachweis, keine Abweichung."""
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path)
    dateien = {b.name: _stand_eintrag(b), v.name: _stand_eintrag(v)}
    dateien[b.name]["zaehler"] = None
    ergebnis = pg.entscheidungen_pruefen(str(b), str(v),
                                         pg.geraetestand_lesen(
                                             _stand(tmp_path, b, v, dateien=dateien)),
                                         None)
    assert ergebnis["erbracht"] is False and ergebnis["abweichung"] is False
    assert "ohne Zaehlung" in ergebnis["zeilen"][0]


def test_pruefung_fehlende_pflichtquelle_im_stand_ist_nicht_erbracht(tmp_path):
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path)
    dateien = {b.name: _stand_eintrag(b)}                      # vorgaben fehlt
    ergebnis = pg.entscheidungen_pruefen(str(b), str(v),
                                         pg.geraetestand_lesen(
                                             _stand(tmp_path, b, v, dateien=dateien)),
                                         None)
    assert ergebnis["erbracht"] is False and ergebnis["abweichung"] is False
    assert "nicht" in ergebnis["zeilen"][0]


def test_pruefung_fehlende_pc_datei_ist_eine_abweichung(tmp_path):
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path)
    stand = _stand(tmp_path, b, v)
    ergebnis = pg.entscheidungen_pruefen(str(tmp_path / "gibtsnicht.json"), str(v),
                                         pg.geraetestand_lesen(stand), None)
    assert ergebnis["abweichung"] is True
    assert "Grundlage fehlt: personen_bestaetigt.json" in ergebnis["zeilen"][0]


def test_pruefung_alte_stand_zeit_ist_eine_abweichung(tmp_path):
    """Der Geraetestand ist aelter als die bestehende Zuordnung -> Exit 2."""
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path)
    alt = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7200))
    stand = _stand(tmp_path, b, v, stand=alt)
    frisch = time.time()
    ergebnis = pg.entscheidungen_pruefen(str(b), str(v), pg.geraetestand_lesen(stand),
                                         frisch)
    assert ergebnis["abweichung"] is True
    assert "aelter als die Zuordnung" in ergebnis["zeilen"][0]
    # Innerhalb der Toleranz (Uhren laufen nicht sekundengenau) gilt er:
    assert pg.entscheidungen_pruefen(str(b), str(v), pg.geraetestand_lesen(stand),
                                     time.time() - 7200 + 60)["erbracht"] is True


def test_pruefung_unlesbare_stand_zeit_ist_eine_abweichung(tmp_path):
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path)
    stand = _stand(tmp_path, b, v, stand="irgendwann")
    ergebnis = pg.entscheidungen_pruefen(str(b), str(v), pg.geraetestand_lesen(stand), None)
    assert ergebnis["abweichung"] is True
    assert "nicht lesbar" in ergebnis["zeilen"][0]


def test_geraetestand_lesen_fehlend_kaputt_und_fremd(tmp_path):
    assert pg.geraetestand_lesen(str(tmp_path / "nichts.json")) is None
    assert pg.geraetestand_lesen(None) is None
    kaputt = tmp_path / "kaputt.json"
    kaputt.write_text("{kein json", encoding="utf-8")
    with pytest.raises(pg.PersonenFehler):
        pg.geraetestand_lesen(str(kaputt))
    liste = tmp_path / "liste.json"
    liste.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(pg.PersonenFehler):
        pg.geraetestand_lesen(str(liste))


def test_pflichtquellen_sind_beim_lesen_pflicht(tmp_path):
    fehlt = str(tmp_path / "gibtsnicht.json")
    assert pg.bestaetigt_lesen(fehlt) == {}                  # alter Weg bleibt
    assert pg.vorgaben_lesen(fehlt)["gleich"] == set()
    with pytest.raises(pg.PersonenFehler) as fehler:
        pg.bestaetigt_lesen(fehlt, pflicht=True)
    assert "personen_bestaetigt.json" in str(fehler.value)
    assert str(tmp_path) not in str(fehler.value), "kein Pfad im Text"
    with pytest.raises(pg.PersonenFehler) as fehler2:
        pg.vorgaben_lesen(fehlt, pflicht=True)
    assert "personen_vorgaben.json" in str(fehler2.value)


# ── Die Kommandozeile: G0 sperrt das Rechnen ───────────────────────────────

def _grund(tmp_path, datei, aus, kandidat, bestaetigt, vorgaben, stand=None):
    """Argumente fuer v2; der Geraetestand zeigt per Vorgabe auf eine leere Stelle."""
    return ["--vektoren", str(datei), "--ausgabe", str(aus), "--ausgabe-kandidat",
            str(kandidat), "--bestaetigt", str(bestaetigt), "--vorgaben", str(vorgaben),
            "--geraetestand", str(stand or (tmp_path / "kein_stand.json"))]


def test_v2_ohne_pflichtdatei_gibt_exit_2_und_rechnet_nicht(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    grund = _grund(tmp_path, datei, aus, kandidat, tmp_path / "fehlt.json",
                   tmp_path / "auch_nicht.json")
    assert pg.main(grund + ["--verfahren", "v2", "--ohne-geraetenachweis"]) == 2
    ausgabe = capsys.readouterr().out
    assert "Pflichtquelle fehlt: personen_bestaetigt.json" in ausgabe
    assert "nichts gerechnet" in ausgabe
    assert not kandidat.exists() and not aus.exists()


def test_v2_ohne_vorgabendatei_gibt_exit_2(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    b = _bestaetigt(tmp_path)
    grund = _grund(tmp_path, datei, aus, kandidat, b, tmp_path / "fehlt.json")
    assert pg.main(grund + ["--verfahren", "v2", "--ohne-geraetenachweis"]) == 2
    assert "Pflichtquelle fehlt: personen_vorgaben.json" in capsys.readouterr().out


def test_v1_bleibt_ohne_die_regeldateien_erlaubt(tmp_path, capsys):
    """Auflage 2 gilt fuer v2 — v1 (Standard) veraendert sich nicht."""
    datei = _vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    grund = ["--vektoren", str(datei), "--ausgabe", str(aus),
             "--bestaetigt", str(tmp_path / "fehlt.json"),
             "--vorgaben", str(tmp_path / "fehlt.json"), "--schreiben"]
    assert pg.main(grund) == 0
    assert capsys.readouterr().out.count("Pflichtquelle") == 0
    assert (aus / pg.DATEI_ZUORDNUNG).is_file()


def test_v2_trockenlauf_ohne_nachweis_ist_gesperrt(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    grund = _grund(tmp_path, datei, aus, kandidat, _bestaetigt(tmp_path),
                   _vorgaben(tmp_path, regeln=50))
    assert pg.main(grund + ["--verfahren", "v2"]) == 2
    ausgabe = capsys.readouterr().out
    assert "nicht erbracht" in ausgabe and "--ohne-geraetenachweis" in ausgabe
    assert not aus.exists() and not kandidat.exists()


def test_v2_trockenmessung_mit_schalter_ist_erlaubt_und_schreibt_nichts(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    grund = _grund(tmp_path, datei, aus, kandidat, _bestaetigt(tmp_path),
                   _vorgaben(tmp_path, regeln=50))
    assert pg.main(grund + ["--verfahren", "v2", "--ohne-geraetenachweis",
                            "--bewerten"]) == 0
    ausgabe = capsys.readouterr().out
    assert "Warnung: Trockenmessung ohne Geraetenachweis" in ausgabe
    assert "Grundwahrheit in Ordnung" in ausgabe
    assert not aus.exists() and not kandidat.exists()


def test_ohne_geraetenachweis_mit_schreiben_gibt_exit_2(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    grund = _grund(tmp_path, datei, aus, kandidat, _bestaetigt(tmp_path),
                   _vorgaben(tmp_path, regeln=50))
    freigabe = tmp_path / "freigabe.json"
    freigabe.write_text("{}", encoding="utf-8")               # kommt nicht so weit
    assert pg.main(grund + ["--verfahren", "v2", "--ohne-geraetenachweis",
                            "--schreiben", "--freigabe", str(freigabe)]) == 2
    ausgabe = capsys.readouterr().out
    assert "erlaubt nur eine Trockenmessung" in ausgabe
    assert not kandidat.exists()


def test_abweichender_geraetestand_gibt_exit_2_und_rechnet_nicht(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path, regeln=50)
    dateien = {b.name: _stand_eintrag(b), v.name: _stand_eintrag(v)}
    dateien[b.name]["sha256"] = "a" * 64
    stand = _stand(tmp_path, b, v, dateien=dateien)
    grund = _grund(tmp_path, datei, aus, kandidat, b, v, stand=stand)
    assert pg.main(grund + ["--verfahren", "v2", "--ohne-geraetenachweis"]) == 2
    ausgabe = capsys.readouterr().out
    assert "ABWEICHUNG" in ausgabe and "sha256 weicht ab" in ausgabe
    assert not kandidat.exists()


def test_kaputter_geraetestand_gibt_exit_2(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    kaputt = tmp_path / "kaputt.json"
    kaputt.write_text("{kein json", encoding="utf-8")
    grund = _grund(tmp_path, datei, aus, kandidat, _bestaetigt(tmp_path),
                   _vorgaben(tmp_path, regeln=50), stand=kaputt)
    assert pg.main(grund + ["--verfahren", "v2"]) == 2
    assert "Geraetestand nicht lesbar" in capsys.readouterr().out


def _freigabe(tmp_path, datei, aus, b, v, stand=None):
    """Gueltige Freigabe fuer den Lauf (Auflage 6) — Parameter wie die Vorgaben."""
    class Args:
        zuordnung = pg.ZUORDNUNG_AEHNLICH
        verschmelzen = pg.VERSCHMELZ_AEHNLICH
        zwilling = pg.ZWILLING_AEHNLICH
        min_groesse = pg.MIN_GROESSE
        min_score = None

    parameter = pg.parameter_stand(Args())
    hash_ist = pg.eingabe_hash([str(datei)], str(b), str(v),
                               os.path.join(str(aus), pg.DATEI_KENNUNGEN),
                               os.path.join(str(aus), pg.DATEI_ZUORDNUNG), parameter)
    ziel = tmp_path / "freigabe.json"
    ziel.write_text(json.dumps({"snapshot_sha256": hash_ist, "parameter": parameter,
                                "urteil": "pass",
                                "werte": {feld: 0 for feld in pg.SPERRZAHLEN}}),
                    encoding="utf-8")
    assert stand is None or os.path.isfile(stand)
    return str(ziel)


def test_gueltiger_nachweis_und_volle_grundwahrheit_schreiben_in_den_kandidaten(
        tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    # Keine Namen (die haetten in diesem Lauf kein Gesicht und wuerden die
    # Sperrzahl heben), aber 50 Regeln: damit ist die Grundwahrheit nicht
    # "vorlaeufig" und der Schreibweg frei.
    b, v = _bestaetigt(tmp_path, anzahl=0), _vorgaben(tmp_path, regeln=50)
    stand = _stand(tmp_path, b, v)
    freigabe = _freigabe(tmp_path, datei, aus, b, v, stand)
    grund = _grund(tmp_path, datei, aus, kandidat, b, v, stand=stand)
    assert pg.main(grund + ["--verfahren", "v2", "--schreiben", "--freigabe",
                            freigabe]) == 0
    ausgabe = capsys.readouterr().out
    assert "Geraetenachweis erbracht" in ausgabe
    assert "Grundwahrheit in Ordnung" in ausgabe
    assert "Ziel: Kandidatenordner" in ausgabe
    for name in (pg.DATEI_ZUORDNUNG, pg.DATEI_BEISPIELE, pg.DATEI_KENNUNGEN):
        assert (kandidat / name).is_file()
    assert not aus.exists(), "der produktive Ordner bleibt unberuehrt"


def test_vorlaeufige_grundwahrheit_sperrt_das_schreiben(tmp_path, capsys):
    """Zu wenig Entscheidungen: --schreiben ist gesperrt (Exit 3), keine Datei."""
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path)          # 1 Name, 0 Regeln
    stand = _stand(tmp_path, b, v)
    freigabe = _freigabe(tmp_path, datei, aus, b, v, stand)
    grund = _grund(tmp_path, datei, aus, kandidat, b, v, stand=stand)
    assert pg.main(grund + ["--verfahren", "v2", "--schreiben", "--freigabe",
                            freigabe]) == 3
    ausgabe = capsys.readouterr().out
    assert "vorlaeufig" in ausgabe and "gesperrt" in ausgabe
    assert not kandidat.exists()


def test_veraltete_grundwahrheit_sperrt_das_schreiben(tmp_path, capsys):
    """Entscheidungen aelter als die bestehende Zuordnung: Exit 3 (G1)."""
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path, regeln=50)
    alt = time.time() - 7200
    os.utime(b, (alt, alt))
    os.utime(v, (alt, alt))
    aus.mkdir()
    zuordnung = aus / pg.DATEI_ZUORDNUNG
    zuordnung.write_text("", encoding="utf-8")                # leer, nur der Stand zaehlt
    # Der Geraetestand selbst ist frisch (sonst greift schon G0) — "veraltet"
    # kommt aus dem Alter der beiden Regeldateien gegenueber der Zuordnung.
    stand = _stand(tmp_path, b, v)
    freigabe = _freigabe(tmp_path, datei, aus, b, v, stand)
    grund = _grund(tmp_path, datei, aus, kandidat, b, v, stand=stand)
    assert pg.main(grund + ["--verfahren", "v2", "--schreiben", "--freigabe",
                            freigabe]) == 3
    ausgabe = capsys.readouterr().out
    assert "veraltet" in ausgabe and "gesperrt" in ausgabe
    assert not kandidat.exists()


def test_vorlaeufige_grundwahrheit_erlaubt_die_trockenmessung(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    b, v = _bestaetigt(tmp_path), _vorgaben(tmp_path)
    stand = _stand(tmp_path, b, v)
    grund = _grund(tmp_path, datei, aus, kandidat, b, v, stand=stand)
    assert pg.main(grund + ["--verfahren", "v2", "--bewerten"]) == 0
    ausgabe = capsys.readouterr().out
    assert "Geraetenachweis erbracht" in ausgabe
    assert "Warnung: die Grundwahrheit ist vorlaeufig" in ausgabe
    assert "Bewertung an den eigenen Entscheidungen" in ausgabe
    assert not kandidat.exists() and not aus.exists()


def test_bericht_nennt_keine_pfade_keine_namen_keine_inhalte(tmp_path, capsys):
    """Der G0-Teil des Berichts nennt Dateinamen und Zahlen — sonst nichts."""
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    b, v = _bestaetigt(tmp_path, anzahl=2), _vorgaben(tmp_path, regeln=50)
    dateien = {b.name: _stand_eintrag(b), v.name: _stand_eintrag(v)}
    dateien[b.name]["zaehler"]["namen"] += 1
    stand = _stand(tmp_path, b, v, dateien=dateien)
    grund = _grund(tmp_path, datei, aus, kandidat, b, v, stand=stand)
    assert pg.main(grund + ["--verfahren", "v2"]) == 2
    ausgabe = capsys.readouterr().out
    assert "Person A" not in ausgabe and "Person B" not in ausgabe
    assert str(tmp_path) not in ausgabe
    assert "Zahl weicht ab (personen_bestaetigt.json: 1 von 2 Feldern)" in ausgabe
