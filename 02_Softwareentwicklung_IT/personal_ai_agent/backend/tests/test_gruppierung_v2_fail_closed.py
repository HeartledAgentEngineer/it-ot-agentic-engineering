"""Tests: fail-closed-Kern von v2 (Plan-Fassung 5.3, Auflage 1 + Auflage 6).

Alles offline mit ERFUNDENEN Vektoren (numpy, fester Seed), erfundenen Kennungen
und erfundenen Namen ("Person A"). Keine echten Gesichter, keine echten Namen,
nichts unter ``~/foto_sortierung``; Dateien nur in ``tmp_path``.

Geprueft wird der Schritt 1 der Plan-Fassung 5.3:

* **Auflage 1 (Bestandsschutz, Regel B):** ein benanntes Gesicht bleibt in seiner
  Kennung - auch ein unsicheres; Abweichungen nur als feste Einzelzuordnung
  (genehmigt, getrennt gezaehlt) oder als Ausschluss; alle uebrigen Wechsel
  landen als ``wechsel_unerlaubt`` im Bericht; Regelkonflikte sind fail-closed
  (Exit 2, nur Zahlen).
* **Auflage 6 (Schreib-Tor):** ``--verfahren v2 --schreiben`` schreibt nur in den
  Kandidatenordner und nur mit gueltiger Freigabedatei; ohne Freigabe, mit
  falschem Snapshot-hash, falschen Parametern, Urteil != pass oder einer
  Sperrzahl > 0 endet der Lauf mit Exit 3 und legt keine Datei an.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_gruppierung_v2_fail_closed.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
WERKZEUGE = os.path.join(os.path.dirname(BACKEND), "tools", "foto_sortierung")
sys.path.insert(0, WERKZEUGE)


def _laden(name):
    spez = importlib.util.spec_from_file_location(name, os.path.join(WERKZEUGE, name + ".py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


pg = _laden("personen_gruppieren")
D = 128


# ── Erfundene Szenen ───────────────────────────────────────────────────────

def _basis(rng, n):
    q, _ = np.linalg.qr(rng.normal(size=(D, n)))
    return q.T


def _gesicht(rng, mitte, naehe=0.85):
    rausch = rng.normal(size=D)
    rausch -= rausch.dot(mitte) * mitte
    rausch /= np.linalg.norm(rausch)
    return naehe * mitte + np.sqrt(1 - naehe ** 2) * rausch


class Szene:
    """Sammelt Gesichter und baut daraus das ``eingelesen`` des Gruppierers."""

    def __init__(self):
        self.zeilen = []
        self.zaehler = 0

    def dazu(self, vektor, jahr=2015, sauber=True, bild=None, index=0):
        self.zaehler += 1
        self.zeilen.append({"vektor": np.asarray(vektor), "bild": bild or f"b{self.zaehler}",
                            "index": index, "jahr": jahr, "sauber": sauber})
        return len(self.zeilen) - 1

    def person(self, rng, mitte, anzahl, jahre=(2015,), sauber=True, naehe=0.85, bild="p"):
        stellen = []
        for i in range(anzahl):
            stellen.append(self.dazu(_gesicht(rng, mitte, naehe), jahre[i % len(jahre)],
                                     sauber, bild=f"{bild}{self.zaehler + 1}"))
        return stellen

    def eingelesen(self):
        gesichter = []
        for z in self.zeilen:
            gesichter.append({
                "bild_id": z["bild"], "index": z["index"],
                "bbox": [0, 0, 100 if z["sauber"] else 30, 100], "breite": 1000, "hoehe": 1000,
                "anteil": 0.02, "score": 0.95 if z["sauber"] else 0.70,
                "aufnahme": f"{z['jahr']}-06-01T12:00:00", "video_id": None, "zeit_s": None})
        vektoren = pg.einheitsvektoren(np.array([z["vektor"] for z in self.zeilen]))
        return {"gesichter": gesichter, "vektoren": vektoren, "dateien": [],
                "bilder": len(gesichter), "bilder_gruppiert": len(gesichter),
                "je_grund": {}, "ungueltig": 0, "doppelt": 0}


def _zwei_namen(rng):
    """Zwei benannte, einander aehnliche Personen (Cosinus 0,7) + eine Stelle."""
    e = _basis(rng, 2)
    a = e[0]
    b = 0.7 * e[0] + np.sqrt(1 - 0.49) * e[1]
    szene = Szene()
    sa = szene.person(rng, a, 20, jahre=(2015, 2016), bild="a")
    sb = szene.person(rng, b, 20, jahre=(2015, 2016), bild="b")
    return szene, a, b, sa, sb


def _alte_zuordnung(szene, sa, sb):
    ein = szene.eingelesen()
    alt = {}
    for kennung, stellen in (("Person_001", sa), ("Person_002", sb)):
        for i in stellen:
            g = ein["gesichter"][i]
            alt[(g["bild_id"], g["index"])] = kennung
    return alt


def _lauf(szene, alt=None, namen=None, vorg=None, **kw):
    return pg.lauf_rechnen_v2(
        szene.eingelesen(), alte_zuordnung=alt,
        bestaetigt=namen if namen is not None else {"Person_001": "Person A",
                                                    "Person_002": "Person B"},
        vorgaben=vorg if vorg is not None else
        {"gleich": set(), "verschieden": set(), "ausgeschlossen": set(), "zugeordnet": {}},
        **kw)


# ── Auflage 1: Regel B (Bestandsschutz) ────────────────────────────────────

def test_regel_b_haelt_ein_sauberes_benanntes_gesicht_bei_seiner_kennung():
    """Das Gesicht sieht aus wie B, ist aber in A zugeordnet: es bleibt in A."""
    rng = np.random.default_rng(101)
    szene, a, b, sa, sb = _zwei_namen(rng)
    extra = szene.dazu(_gesicht(rng, b, 0.97), 2015, sauber=True)
    ein = szene.eingelesen()
    schluessel = pg._schluessel(ein["gesichter"][extra])
    for alt_kennung, erwartet in (("Person_001", "Person_001"), ("Person_002", "Person_002")):
        alt = _alte_zuordnung(szene, sa, sb)
        alt[schluessel] = alt_kennung
        lauf = _lauf(szene, alt=alt)
        assert lauf["gesichter"][extra]["kennung"] == erwartet
        assert lauf["bericht"]["v2"]["wechsel_unerlaubt"] == 0


def test_regel_b_haelt_auch_ein_unsicheres_benanntes_gesicht():
    """Unsicher (grob/klein), Vektor nah an B, zugeordnet zu A: bleibt in A."""
    rng = np.random.default_rng(103)
    szene, a, b, sa, sb = _zwei_namen(rng)
    extra = szene.dazu(_gesicht(rng, b, 0.97), 2015, sauber=False)
    ein = szene.eingelesen()
    schluessel = pg._schluessel(ein["gesichter"][extra])
    alt = _alte_zuordnung(szene, sa, sb)
    alt[schluessel] = "Person_001"
    lauf = _lauf(szene, alt=alt)
    assert lauf["gesichter"][extra]["kennung"] == "Person_001"
    assert lauf["bericht"]["v2"]["regel_b_geschuetzt"] == 1
    assert lauf["bericht"]["v2"]["wechsel_unerlaubt"] == 0


def test_regel_b_geschuetzte_gesichter_docken_nicht_anderswo_an():
    """Ohne Regel B wandert das unsichere Gesicht zu B; mit Regel B nicht."""
    rng = np.random.default_rng(105)
    szene, a, b, sa, sb = _zwei_namen(rng)
    extra = szene.dazu(_gesicht(rng, b, 0.99), 2015, sauber=False)
    ein = szene.eingelesen()
    schluessel = pg._schluessel(ein["gesichter"][extra])

    ohne = _lauf(szene, alt=_alte_zuordnung(szene, sa, sb))       # ohne Zuordnung von extra
    assert ohne["gesichter"][extra]["kennung"] == "Person_002"    # Beweis: es dockt sonst an B

    alt = _alte_zuordnung(szene, sa, sb)
    alt[schluessel] = "Person_001"
    mit = _lauf(szene, alt=alt)
    assert mit["gesichter"][extra]["kennung"] == "Person_001"


def test_ausnahme_feste_zuordnung_zaehlt_als_genehmigt():
    rng = np.random.default_rng(107)
    szene, a, b, sa, sb = _zwei_namen(rng)
    ziel = szene.dazu(_gesicht(rng, a, 0.97), 2015, sauber=True)
    ein = szene.eingelesen()
    g = ein["gesichter"][ziel]
    schluessel = pg._schluessel(g)
    alt = _alte_zuordnung(szene, sa, sb)
    alt[schluessel] = "Person_001"
    vorg = {"gleich": set(), "verschieden": set(), "ausgeschlossen": set(),
            "zugeordnet": {schluessel: {"kennung": "Person_001", "name": "Person B"}}}
    lauf = _lauf(szene, alt=alt, vorg=vorg)
    assert lauf["gesichter"][ziel]["kennung"] == "Person_002"          # der Name bestimmt das Ziel
    assert lauf["bericht"]["v2"]["wechsel_genehmigt"] == 1
    assert lauf["bericht"]["v2"]["wechsel_unerlaubt"] == 0
    assert lauf["sperrzahlen"]["wechsel_unerlaubt"] == 0


def test_ausnahme_ausschluss_zaehlt_nicht_als_wechsel():
    rng = np.random.default_rng(109)
    szene, a, b, sa, sb = _zwei_namen(rng)
    ein = szene.eingelesen()
    g = ein["gesichter"][sa[0]]
    schluessel = pg._schluessel(g)
    alt = _alte_zuordnung(szene, sa, sb)
    vorg = {"gleich": set(), "verschieden": set(), "zugeordnet": {},
            "ausgeschlossen": {("Person_001", schluessel[0], schluessel[1])}}
    lauf = _lauf(szene, alt=alt, vorg=vorg)
    assert lauf["gesichter"][sa[0]]["kennung"] is None                 # bleibt draussen
    assert lauf["bericht"]["v2"]["ausschluss_genehmigt"] == 1
    assert lauf["bericht"]["v2"]["wechsel_unerlaubt"] == 0


def test_verschieden_regel_bewegt_kein_benanntes_gesicht():
    """Die verschieden-Regel trennt nur; sie verschiebt kein Gesicht nach Regel B."""
    rng = np.random.default_rng(111)
    szene, a, b, sa, sb = _zwei_namen(rng)
    alt = _alte_zuordnung(szene, sa, sb)
    vorg = {"gleich": set(), "verschieden": {("Person_001", "Person_002")},
            "ausgeschlossen": set(), "zugeordnet": {}}
    lauf = _lauf(szene, alt=alt, vorg=vorg)
    mitglieder = {}
    for i, gesicht in enumerate(lauf["gesichter"]):
        if gesicht["kennung"]:
            mitglieder.setdefault(gesicht["kennung"], set()).add(i)
    assert set(mitglieder) == {"Person_001", "Person_002"}
    assert mitglieder["Person_001"] == set(sa)
    assert mitglieder["Person_002"] == set(sb)
    assert lauf["bericht"]["v2"]["wechsel_unerlaubt"] == 0


def test_regelkonflikt_gleich_und_verschieden_zugleich_ist_fail_closed():
    rng = np.random.default_rng(113)
    szene, a, b, sa, sb = _zwei_namen(rng)
    vorg = {"gleich": {("Person_001", "Person_002")},
            "verschieden": {("Person_001", "Person_002")},
            "ausgeschlossen": set(), "zugeordnet": {}}
    with pytest.raises(pg.PersonenFehler) as fehler:
        _lauf(szene, alt=_alte_zuordnung(szene, sa, sb), vorg=vorg)
    assert "Regelkonflikte: 1" in str(fehler.value)


def test_regel_b_konflikt_geschuetzte_kennung_ohne_gruppe_ist_fail_closed():
    """Eine benannte Kennung ohne sauberes Gesicht haelt ein unsicheres -> Exit 2."""
    rng = np.random.default_rng(115)
    e = _basis(rng, 2)
    szene = Szene()
    szene.person(rng, e[0], 20, jahre=(2015, 2016))                   # eine unbenannte Gruppe
    extra = szene.dazu(_gesicht(rng, e[0], 0.97), 2015, sauber=False)  # unsicher
    ein = szene.eingelesen()
    schluessel = pg._schluessel(ein["gesichter"][extra])
    alt = {schluessel: "Person_007"}
    namen = {"Person_007": "Person G"}                                 # hat kein sauberes Gesicht
    with pytest.raises(pg.PersonenFehler) as fehler:
        _lauf(szene, alt=alt, namen=namen)
    text = str(fehler.value)
    assert "Regel-B-Konflikte: 1" in text
    assert "Person_007" not in text                                   # keine Kennung im Text
    assert "b" + "1" not in text                                      # keine Bild-ID im Text


def test_bericht_nennt_die_sperrzahlen_und_die_wechsel():
    rng = np.random.default_rng(117)
    szene, a, b, sa, sb = _zwei_namen(rng)
    lauf = _lauf(szene, alt=_alte_zuordnung(szene, sa, sb))
    assert lauf["sperrzahlen"] == {"benannte_ohne_gruppe": 0, "leere_benannte_gruppe": 0,
                                   "wechsel_unerlaubt": 0}
    text = pg.bericht_text(lauf["bericht"])
    assert "Wechsel benannter Gesichter" in text and "Sperrzahlen der Freigabe" in text
    assert "UNERLAUBT 0" in text


# ── Auflage 6: Schreib-Tor + Kandidatenordner (ueber die Kommandozeile) ────

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


class _Args:
    """Die Parameter, die ``parameter_stand`` liest (Voreinstellungen des Werkzeugs)."""

    def __init__(self, **abweichend):
        self.zuordnung = pg.ZUORDNUNG_AEHNLICH
        self.verschmelzen = pg.VERSCHMELZ_AEHNLICH
        self.zwilling = pg.ZWILLING_AEHNLICH
        self.min_groesse = pg.MIN_GROESSE
        self.min_score = None
        for name, wert in abweichend.items():
            setattr(self, name, wert)


def _grund(tmp_path, datei, aus, kandidat, bestaetigt=None, zusatz=()):
    leer = str(tmp_path / "keine.json")
    return ["--vektoren", str(datei), "--ausgabe", str(aus), "--ausgabe-kandidat",
            str(kandidat), "--bestaetigt", bestaetigt or leer, "--vorgaben", leer,
            "--verfahren", "v2", *zusatz]


def _freigabe(tmp_path, pfade, bestaetigt, vorgaben, aus, parameter=None, urteil="pass",
              werte=None, hash_ist=None, name="freigabe.json"):
    parameter = parameter if parameter is not None else pg.parameter_stand(_Args())
    werte = {feld: 0 for feld in pg.SPERRZAHLEN} if werte is None else werte
    hash_ist = hash_ist or pg.eingabe_hash(
        pfade, bestaetigt, vorgaben, os.path.join(str(aus), pg.DATEI_KENNUNGEN),
        os.path.join(str(aus), pg.DATEI_ZUORDNUNG), parameter)
    datei = tmp_path / name
    datei.write_text(json.dumps({"snapshot_sha256": hash_ist, "parameter": parameter,
                                 "urteil": urteil, "werte": werte}), encoding="utf-8")
    return str(datei)


def test_trockenlauf_braucht_keine_freigabe(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    assert pg.main(_grund(tmp_path, datei, aus, kandidat)) == 0
    assert "NICHTS geschrieben" in capsys.readouterr().out
    assert not aus.exists() and not kandidat.exists()


def test_schreiben_ohne_freigabe_legt_keine_datei_an(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    assert pg.main(_grund(tmp_path, datei, aus, kandidat, zusatz=["--schreiben"])) == 3
    assert "Ohne Freigabe wird v2 nichts geschrieben" in capsys.readouterr().out
    assert not aus.exists() and not kandidat.exists()


def test_produktiv_ohne_freigabe_schreibt_nichts(tmp_path):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    assert pg.main(_grund(tmp_path, datei, aus, kandidat,
                          zusatz=["--schreiben", "--produktiv"])) == 3
    assert not aus.exists() and not kandidat.exists()


def test_gueltige_freigabe_schreibt_nur_in_den_kandidatenordner(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    aus.mkdir()
    alt = aus / pg.DATEI_ZUORDNUNG
    alt.write_text("{\"alt\": true}\n", encoding="utf-8")            # produktiver Stand
    vorher = alt.read_bytes()
    freigabe = _freigabe(tmp_path, [str(datei)], str(tmp_path / "keine.json"),
                         str(tmp_path / "keine.json"), aus)
    grund = _grund(tmp_path, datei, aus, kandidat, zusatz=["--schreiben", "--freigabe", freigabe])
    assert pg.main(grund) == 0
    ausgabe = capsys.readouterr().out
    assert "Freigabe gueltig" in ausgabe and "Ziel: Kandidatenordner" in ausgabe
    for name in (pg.DATEI_ZUORDNUNG, pg.DATEI_BEISPIELE, pg.DATEI_KENNUNGEN):
        assert (kandidat / name).is_file()
    assert alt.read_bytes() == vorher                                 # produktiv unveraendert


def test_produktiv_mit_freigabe_und_schalter_schreibt_in_den_produktivordner(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    freigabe = _freigabe(tmp_path, [str(datei)], str(tmp_path / "keine.json"),
                         str(tmp_path / "keine.json"), aus, name="produktiv.json")
    grund = _grund(tmp_path, datei, aus, kandidat,
                   zusatz=["--schreiben", "--produktiv", "--freigabe", freigabe])
    assert pg.main(grund) == 0
    assert "Ziel: PRODUKTIVER Ordner" in capsys.readouterr().out
    assert (aus / pg.DATEI_ZUORDNUNG).is_file()
    assert not kandidat.exists()


def test_freigabe_mit_falschem_snapshot_hash_wird_abgelehnt(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    leer = str(tmp_path / "keine.json")
    freigabe = _freigabe(tmp_path, [str(datei)], leer, leer, aus,
                         hash_ist="0" * 64)
    grund = _grund(tmp_path, datei, aus, kandidat, zusatz=["--schreiben", "--freigabe", freigabe])
    assert pg.main(grund) == 3
    assert "Snapshot-hash" in capsys.readouterr().out
    assert not kandidat.exists()


def test_freigabe_mit_anderen_parametern_wird_abgelehnt(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    leer = str(tmp_path / "keine.json")
    parameter = pg.parameter_stand(_Args())                    # wie der Lauf rechnet
    andere = pg.parameter_stand(_Args(min_groesse=99))         # was in der Datei steht
    hash_ist = pg.eingabe_hash([str(datei)], leer, leer,
                               os.path.join(str(aus), pg.DATEI_KENNUNGEN),
                               os.path.join(str(aus), pg.DATEI_ZUORDNUNG), parameter)
    freigabe = _freigabe(tmp_path, [str(datei)], leer, leer, aus, parameter=andere,
                         hash_ist=hash_ist)
    grund = _grund(tmp_path, datei, aus, kandidat, zusatz=["--schreiben", "--freigabe", freigabe])
    assert pg.main(grund) == 3
    assert "Parameter passen nicht" in capsys.readouterr().out
    assert not kandidat.exists()


def test_freigabe_mit_urteil_einwand_wird_abgelehnt(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    leer = str(tmp_path / "keine.json")
    freigabe = _freigabe(tmp_path, [str(datei)], leer, leer, aus, urteil="EINWAND")
    grund = _grund(tmp_path, datei, aus, kandidat, zusatz=["--schreiben", "--freigabe", freigabe])
    assert pg.main(grund) == 3
    assert "Urteil" in capsys.readouterr().out
    assert not kandidat.exists()


def test_freigabe_mit_verletzter_sperrzahl_wird_abgelehnt(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    leer = str(tmp_path / "keine.json")
    werte = {feld: 0 for feld in pg.SPERRZAHLEN}
    werte["wechsel_unerlaubt"] = 3
    freigabe = _freigabe(tmp_path, [str(datei)], leer, leer, aus, werte=werte)
    grund = _grund(tmp_path, datei, aus, kandidat, zusatz=["--schreiben", "--freigabe", freigabe])
    assert pg.main(grund) == 3
    assert "wechsel_unerlaubt" in capsys.readouterr().out
    assert not kandidat.exists()


def test_lauf_mit_eigener_sperrzahl_blockiert_die_freigabe(tmp_path, capsys):
    """Eine benannte Kennung ohne Gesicht: die Zahl des LAUFS sperrt, nicht nur die Datei."""
    datei = _vektordatei(tmp_path)
    bestaetigt = tmp_path / "bestaetigt.json"
    bestaetigt.write_text(json.dumps({"bestaetigt": {"Person_777": "Person G"}}),
                          encoding="utf-8")
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    leer = str(tmp_path / "keine.json")
    freigabe = _freigabe(tmp_path, [str(datei)], str(bestaetigt), leer, aus)   # werte alle 0
    grund = _grund(tmp_path, datei, aus, kandidat, bestaetigt=str(bestaetigt),
                   zusatz=["--schreiben", "--freigabe", freigabe])
    assert pg.main(grund) == 3
    ausgabe = capsys.readouterr().out
    assert "Sperrzahl benannte_ohne_gruppe dieses Laufs ist nicht 0" in ausgabe
    assert not kandidat.exists()


def test_fehlende_freigabedatei_ist_ein_fehler(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    fehlt = str(tmp_path / "gibtesnicht.json")
    grund = _grund(tmp_path, datei, aus, kandidat, zusatz=["--schreiben", "--freigabe", fehlt])
    assert pg.main(grund) == 2
    assert "Freigabedatei" in capsys.readouterr().out
    assert not kandidat.exists()


def test_kandidatenordner_im_repo_ist_verboten(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    im_repo = os.path.join(os.path.dirname(BACKEND), "kandidat_verboten")
    assert pg.main(_grund(tmp_path, datei, aus, im_repo)) == 2
    assert "ausserhalb" in capsys.readouterr().out.lower()


# ── Die Bausteine des Tors einzeln ────────────────────────────────────────

def test_eingabe_hash_ist_deterministisch_und_reagiert_auf_aenderungen(tmp_path):
    datei = tmp_path / "v.jsonl"
    datei.write_text("eins\n", encoding="utf-8")
    andere = tmp_path / "b.json"
    andere.write_text("{}\n", encoding="utf-8")
    leer = str(tmp_path / "keine.json")
    parameter = pg.parameter_stand(_Args())
    argumente = ([str(datei)], leer, leer, leer, leer)

    erster = pg.eingabe_hash(*argumente, parameter)
    assert len(erster) == 64
    assert pg.eingabe_hash(*argumente, parameter) == erster          # deterministisch
    assert pg.eingabe_hash(*argumente, pg.parameter_stand(_Args(min_groesse=7))) != erster
    datei.write_text("zwei\n", encoding="utf-8")
    assert pg.eingabe_hash(*argumente, parameter) != erster          # Inhalt zaehlt
    assert pg.eingabe_hash([], str(andere), leer, leer, leer, parameter) == \
        pg.eingabe_hash([], str(andere), leer, leer, leer, parameter)
    assert pg.eingabe_hash([], leer, leer, leer, leer, parameter) != \
        pg.eingabe_hash([], str(andere), leer, leer, leer, parameter)  # fehlt != vorhanden


def test_freigabe_pruefen_nennt_jeden_ablehnungsgrund(tmp_path):
    parameter = pg.parameter_stand(_Args())
    zahlen = {feld: 0 for feld in pg.SPERRZAHLEN}
    gut = {"snapshot_sha256": "a" * 64, "parameter": parameter, "urteil": "pass",
           "werte": dict(zahlen)}
    assert pg.freigabe_pruefen(gut, "a" * 64, parameter, zahlen) == ""
    assert "Snapshot" in pg.freigabe_pruefen(gut, "b" * 64, parameter, zahlen)
    assert "Parameter" in pg.freigabe_pruefen(gut, "a" * 64,
                                              pg.parameter_stand(_Args(zwilling=0.9)), zahlen)
    assert "Urteil" in pg.freigabe_pruefen({**gut, "urteil": "einwand"}, "a" * 64,
                                           parameter, zahlen)
    assert "Werte" in pg.freigabe_pruefen({**gut, "werte": None}, "a" * 64, parameter, zahlen)
    assert "nicht als 0" in pg.freigabe_pruefen(
        {**gut, "werte": {**zahlen, "leere_benannte_gruppe": 2}}, "a" * 64, parameter, zahlen)
    assert "dieses Laufs" in pg.freigabe_pruefen(
        gut, "a" * 64, parameter, {**zahlen, "benannte_ohne_gruppe": 1})
