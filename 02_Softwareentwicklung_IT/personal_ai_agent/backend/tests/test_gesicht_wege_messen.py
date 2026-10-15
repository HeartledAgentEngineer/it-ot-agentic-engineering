"""Pruefungen fuer ``tools/foto_sortierung/gesicht_wege_messen.py`` (15.10.2026).

Offline: erfundene Bildkennungen und erfundene Rahmen in winzigen JSONL-Dateien,
keine echten Bilddaten, kein Netz, kein Modell, kein Bild. Geprueft wird, dass
nur Zahlen entstehen, dass **keine Personennamen** im Bericht landen, dass
fehlende Dateien ehrlich gemeldet werden — und dass die Einstellungen wirklich
aus dem ECHTEN Code gelesen werden (Datei:Zeile), nicht behauptet sind.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "gesicht_wege_messen.py"

spez = importlib.util.spec_from_file_location("gesicht_wege_messen", WERKZEUG)
assert spez is not None and spez.loader is not None
gwm = importlib.util.module_from_spec(spez)
spez.loader.exec_module(gwm)


# ── Hilfen ───────────────────────────────────────────────────────────────────

def _zeile(bild_id, index=0, kennung=None, bbox=(10.0, 20.0, 100.0, 100.0),
           score=0.9, gid=None, video_id=None) -> str:
    eintrag = {"bild_id": bild_id, "index": index, "kennung": kennung,
               "bbox": list(bbox), "score": score, "video_id": video_id}
    if gid is not None:
        eintrag["gid"] = gid
    return json.dumps(eintrag)


def _datei(pfad: Path, zeilen) -> Path:
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return pfad


# ── 1. Die Einstellungen kommen aus dem ECHTEN Code (Datei:Zeile) ────────────

def test_einstellungen_beider_wege_aus_dem_echten_code():
    einstellungen = gwm.einstellungen_lesen()
    assert einstellungen["handy"]["da"] and einstellungen["pc"]["da"]
    for rolle in ("handy", "pc"):
        weg = einstellungen[rolle]
        assert weg["score"][0] == 0.6
        assert weg["nms"][0] == 0.3
        assert weg["topk"][0] == 5000
        assert weg["score"][1] > 0          # Zeilennummer bekannt, nicht geraten
        assert weg["eingabe"], f"keine gesetzte Eingabegroesse im {rolle}-Weg gefunden"


def test_die_voreinstellung_320_wird_vom_bild_ueberschrieben():
    """Befund: `create(..., (320, 320), ...)` ist NICHT die wirksame Groesse —
    beide Wege setzen setInputSize auf das echte Bild (belegt, Datei:Zeile)."""
    einstellungen = gwm.einstellungen_lesen()
    handy = einstellungen["handy"]
    gebaut = " ".join(text for _n, text in handy["bau"])
    assert "(320, 320)" in gebaut
    setzen = min(nummer for nummer, _t in handy["eingabe"])
    bauen = min(nummer for nummer, _t in handy["bau"])
    assert setzen > bauen, "setInputSize steht vor dem Bau — bitte nachsehen"
    assert any("w, h" in text or "shape" in text for _n, text in handy["eingabe"])


def test_beide_wege_haben_dieselben_zahlen():
    einstellungen = gwm.einstellungen_lesen()
    assert gwm.einstellungen_gleich(einstellungen) is True
    # Gegenprobe: ein anderer Score kippt den Vergleich (kein Blind-Ja).
    einstellungen["pc"]["score"] = (0.5, 1)
    assert gwm.einstellungen_gleich(einstellungen) is False


def test_bericht_der_wege_nennt_datei_und_zeile():
    zeilen = gwm.einstellungen_bericht(gwm.einstellungen_lesen())
    text = "\n".join(zeilen)
    assert "face_infer.py:" in text and "gesicht_erkennen.py:" in text
    assert "BEIDEN Wegen gleich" in text


# ── 2. Anzeige: die Filterzeile wird im echten Code gefunden ────────────────

def test_anzeige_orte_finden_filterzeile_und_einzelrahmen():
    stellen = gwm.anzeige_orte()
    orte = {was: (datei, nummer) for datei, nummer, _t, was in stellen}
    assert "Filterzeile: verbirgt ausgeschlossene und „kenne ich nicht\"" in orte
    filter_datei, _filter_zeile = orte["Filterzeile: verbirgt ausgeschlossene und „kenne ich nicht\""]
    assert filter_datei.endswith("gruppen_quiz.py")
    assert any(was.startswith("Editor bekommt genau EINEN Rahmen") for was in orte)
    assert any(was.startswith("Editor bekommt die LISTE") for was in orte)


def test_filterzeile_steht_wirklich_in_der_auswahlfunktion():
    """Die gefundene Zeile muss im Rumpf von gesichter_auf_bild liegen — sonst
    waere es ein Treffer aus einer anderen Funktion (Pruefung gegen den Code)."""
    stellen = gwm.anzeige_orte()
    zeilen = {nummer for datei, nummer, _t, was in stellen
              if was.startswith("Filterzeile") and datei.endswith("gruppen_quiz.py")}
    assert zeilen, "keine Filterzeile gefunden"
    rumpf = {nummer for nummer, _t in gwm.funktions_bereich(
        gwm.SERVICE_QUIZ, r"^def gesichter_auf_bild")}
    assert zeilen <= rumpf


# ── 3. Bestand: Zahlen, keine Inhalte ──────────────────────────────────────

def test_bestand_zaehlt_gesichter_je_bild(tmp_path):
    pfad = _datei(tmp_path / "zuordnung.jsonl", [
        _zeile("100", 0), _zeile("100", 1), _zeile("100", 2),   # ein Bild, drei Gesichter
        _zeile("200", 0),                                        # genau ein Gesicht
        _zeile("300", 0), _zeile("300", 1), _zeile("300", 2), _zeile("300", 3),
    ])
    zahlen = gwm.bestand_zahlen(gwm.bestand_lesen(pfad))
    assert zahlen["gesichter"] == 8
    assert zahlen["bilder"] == 3
    assert zahlen["bilder_genau_ein"] == 1
    assert zahlen["bilder_genau_drei"] == 1
    assert zahlen["bilder_vier_oder_mehr"] == 1
    assert zahlen["groesstes_bild"] == 4


def test_rahmenbreiten_scores_und_fehlende_gruppen_werden_gezaehlt(tmp_path):
    pfad = _datei(tmp_path / "zuordnung.jsonl", [
        _zeile("100", 0, bbox=(0, 0, 20.0, 20.0), score=0.5),      # sehr schmal, unsicher
        _zeile("100", 1, bbox=(0, 0, 50.0, 50.0), score=0.9),      # schmal
        _zeile("100", 2, bbox=(0, 0, 300.0, 300.0), score=0.95),   # breit
        _zeile("100", 3, bbox=(), score=None, gid="100:3"),        # ohne Masse
        _zeile("100", 4, bbox=(0, 0, 100.0, 100.0), score=0.9, video_id="v1"),
    ])
    zahlen = gwm.bestand_zahlen(gwm.bestand_lesen(pfad))
    assert zahlen["gesichter"] == 5
    assert zahlen["schmal"] == 2 and zahlen["sehr_schmal"] == 1
    assert zahlen["breite_median"] == 75.0
    assert zahlen["score_unsicher"] == 1
    assert zahlen["ohne_gruppe"] == 5
    assert zahlen["aus_video"] == 1
    assert zahlen["ohne_masse"] == 1


def test_kaputte_zeile_wird_gezaehlt_statt_geworfen(tmp_path):
    pfad = tmp_path / "zuordnung.jsonl"
    pfad.write_text('{"bild_id": "100", "bbox": [1,2,3,4], "score": 0.9}\n'
                    'kein json\n'
                    '[1, 2, 3]\n', encoding="utf-8")
    zahlen = gwm.bestand_zahlen(gwm.bestand_lesen(pfad))
    assert zahlen["gesichter"] == 1
    assert zahlen["kaputt"] == 2


def test_fehlende_datei_wird_ehrlich_gemeldet(tmp_path):
    fehlt = tmp_path / "gibtsnicht.jsonl"
    roh = gwm.bestand_lesen(fehlt)
    assert roh["fehlt"] is True
    text = "\n".join(gwm.bestand_bericht(roh, gwm.bestand_zahlen(roh)))
    assert "Datei fehlt" in text


# ── 4. Ein einzelnes Bild: was die Anzeige verbirgt ────────────────────────

def test_bild_zaehlen_verbirgt_ausgeschlossene_und_fremde_gruppen(tmp_path):
    pfad = _datei(tmp_path / "zuordnung.jsonl", [
        _zeile("100", 0, kennung="Person_1", gid="100:0"),   # ausgeschlossen
        _zeile("100", 1, kennung="Person_2", gid="100:1"),   # Gruppe „kenne ich nicht"
        _zeile("100", 2, kennung="Person_3", gid="100:2"),   # sichtbar
        _zeile("100", 3, kennung=None, gid="100:3"),         # ohne Gruppe -> sichtbar
        _zeile("999", 0, kennung="Person_3", gid="999:0"),   # anderes Bild
    ])
    zahlen = gwm.bild_zaehlen(pfad, "100", ausgeschlossen={"100:0"}, fremd={"Person_2"})
    assert zahlen["gesichter"] == 4
    assert zahlen["ohne_gruppe"] == 1
    assert zahlen["verborgen"] == 2
    text = "\n".join(gwm.bild_bericht(zahlen))
    assert "sichtbar: 2" in text


def test_bild_zaehlen_ohne_filterlisten_meldet_nicht_zaehlbar(tmp_path):
    pfad = _datei(tmp_path / "zuordnung.jsonl", [_zeile("100", 0)])
    zahlen = gwm.bild_zaehlen(pfad, "100")
    assert zahlen["verborgen"] is None
    text = "\n".join(gwm.bild_bericht(zahlen))
    assert "NICHT zaehlbar" in text


def test_bild_zaehlen_unbekannte_kennung_ist_null(tmp_path):
    pfad = _datei(tmp_path / "zuordnung.jsonl", [_zeile("100", 0)])
    zahlen = gwm.bild_zaehlen(pfad, "424242")
    assert zahlen["gesichter"] == 0
    assert "0 Gesichter" in "\n".join(gwm.bild_bericht(zahlen))


# ── 5. Keine Namen, kein Schreiben ──────────────────────────────────────────

def test_bericht_enthaelt_keinen_personennamen(tmp_path):
    pfad = _datei(tmp_path / "zuordnung.jsonl", [
        _zeile("100", 0, kennung="Erika_Musterfrau", gid="100:0", score=0.91),
    ])
    text = "\n".join(gwm.bericht(pfad, bilder=("100",)))
    assert "Erika" not in text and "Musterfrau" not in text
    assert "100" in text          # Bildkennung darf stehen (sie ist keine Person)


def test_werkzeug_oeffnet_nichts_zum_schreiben():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert not re.search(r"open\([^)]*[\"'](?:w|a|x|wb|ab|wt)[\"']", quelle)
    assert "_atomar_schreiben" not in quelle and "shutil.copy" not in quelle


def test_kommandozeile_laeuft_ohne_bildangabe(tmp_path, capsys):
    leer = tmp_path / "leer.jsonl"
    leer.write_text("", encoding="utf-8")
    assert gwm.main(["--zuordnung", str(leer)]) == 0
    ausgabe = capsys.readouterr().out
    assert "Einstellungen der beiden Erkennungswege" in ausgabe
    assert "0 Gesichter auf 0 Bildern" in ausgabe
