"""Tests fuer tools/handy/namen_aus_sicherung.py (09.10.2026).

Offline, erfundene Namen. Statt ``age -d`` liefert eine Attrappe den tar-Strom
direkt aus dem Speicher.
"""
from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[2]
spez = importlib.util.spec_from_file_location(
    "namen_aus_sicherung", PROJEKT / "tools" / "handy" / "namen_aus_sicherung.py")
assert spez is not None and spez.loader is not None
nas = importlib.util.module_from_spec(spez)
spez.loader.exec_module(nas)

BESTAETIGT = {"bestaetigt": {"Person_001": "Anna", "Person_007": "Anna", "Person_003": "Bert"}}
VORGABEN = {"gleich": [["Person_001", "Person_007"]], "verschieden": []}


def _tar(dateien: dict) -> bytes:
    puffer = io.BytesIO()
    with tarfile.open(fileobj=puffer, mode="w") as archiv:
        for name, inhalt in dateien.items():
            info = tarfile.TarInfo(name)
            info.size = len(inhalt)
            archiv.addfile(info, io.BytesIO(inhalt))
    return puffer.getvalue()


def _sicherung(tmp_path: Path, dateien: dict) -> tuple:
    ordner = tmp_path / "2026-10-08_2347"
    ordner.mkdir()
    (ordner / "home.tar.age").write_bytes(b"verschluesselt")
    daten = _tar(dateien)
    gesehen = []

    def oeffnen(pfad):
        gesehen.append(pfad)
        return io.BytesIO(daten)
    return ordner, oeffnen, gesehen


def _beide() -> dict:
    return {"home/notizen.txt": b"privat",
            "home/foto_sortierung/personen_bestaetigt.json": json.dumps(BESTAETIGT).encode(),
            "home/foto_sortierung/personen_vorgaben.json": json.dumps(VORGABEN).encode(),
            "home/foto_sortierung/anderes.json": b"{}"}


def _zuordnung(tmp_path: Path) -> Path:
    pfad = tmp_path / "gesicht_zuordnung.jsonl"
    zeilen = ([{"kennung": "Person_001"}] * 5 + [{"kennung": "Person_007"}] * 2
              + [{"kennung": "Person_003"}] * 9 + [{"kennung": None}])
    pfad.write_text("\n".join(json.dumps(z) for z in zeilen) + "\nkaputt\n", encoding="utf-8")
    return pfad


def test_dateien_holen_liest_nur_die_zwei_gesuchten():
    gefunden = nas.dateien_holen(io.BytesIO(_tar(_beide())))
    assert set(gefunden) == {"personen_bestaetigt.json", "personen_vorgaben.json"}
    assert json.loads(gefunden["personen_bestaetigt.json"]) == BESTAETIGT


def test_dateien_holen_akzeptiert_fuehrendes_punkt_schraegstrich():
    daten = _tar({"./home/foto_sortierung/personen_bestaetigt.json": b'{"bestaetigt": {}}'})
    assert set(nas.dateien_holen(io.BytesIO(daten))) == {"personen_bestaetigt.json"}


def test_ohne_uebernehmen_wird_nichts_geschrieben(tmp_path, capsys):
    ordner, oeffnen, gesehen = _sicherung(tmp_path, _beide())
    ziel = tmp_path / "ziel"
    code = nas.main([str(ordner), "--zuordnung", str(_zuordnung(tmp_path)),
                     "--ziel", str(ziel)], oeffnen=oeffnen)
    assert code == 0
    assert gesehen == [str(ordner / "home.tar.age")]
    assert not ziel.exists()
    text = capsys.readouterr().out
    assert "Benannte Gruppen: 3 · verschiedene Namen: 2" in text
    # nach Gesichtern sortiert: Bert (9) vor Anna (5 + 2)
    assert text.index("Bert: 1 Gruppe(n), 9 Gesichter") < text.index("Anna: 2 Gruppe(n), 7 Gesichter")
    assert "Person_001 (5), Person_007 (2)" in text


def test_ohne_namen_zeigt_nur_nummern(tmp_path, capsys):
    ordner, oeffnen, _ = _sicherung(tmp_path, _beide())
    nas.main([str(ordner), "--zuordnung", str(_zuordnung(tmp_path)), "--ohne-namen",
              "--ziel", str(tmp_path / "ziel")], oeffnen=oeffnen)
    text = capsys.readouterr().out
    assert "Anna" not in text and "Bert" not in text
    assert "Name 1: 1 Gruppe(n), 9 Gesichter" in text


def test_uebernehmen_sichert_vorhandene_datei_als_vorher(tmp_path):
    ordner, oeffnen, _ = _sicherung(tmp_path, _beide())
    ziel = tmp_path / "ziel"
    ziel.mkdir()
    (ziel / "personen_bestaetigt.json").write_text('{"alt": 1}', encoding="utf-8")
    code = nas.main([str(ordner), "--zuordnung", str(_zuordnung(tmp_path)),
                     "--ziel", str(ziel), "--uebernehmen"], oeffnen=oeffnen)
    assert code == 0
    assert json.loads((ziel / "personen_bestaetigt.json").read_text(encoding="utf-8")) == BESTAETIGT
    assert (ziel / "personen_bestaetigt.json.vorher").read_text(encoding="utf-8") == '{"alt": 1}'
    assert json.loads((ziel / "personen_vorgaben.json").read_text(encoding="utf-8")) == VORGABEN
    assert not (ziel / "personen_vorgaben.json.vorher").exists()
    assert not list(ziel.glob("*.neu"))


def test_fehlende_sicherung_exit_1(tmp_path):
    assert nas.main([str(tmp_path / "gibtsnicht")], oeffnen=lambda p: io.BytesIO()) == 1


def test_ohne_bestaetigte_namen_exit_3_und_nichts_geschrieben(tmp_path):
    ordner, oeffnen, _ = _sicherung(tmp_path, {"home/notizen.txt": b"x"})
    ziel = tmp_path / "ziel"
    code = nas.main([str(ordner), "--ziel", str(ziel), "--uebernehmen"], oeffnen=oeffnen)
    assert code == 3
    assert not ziel.exists()


def test_fehler_beim_schliessen_des_stroms_bricht_nicht_ab(tmp_path):
    ordner, _, _ = _sicherung(tmp_path, _beide())
    daten = _tar(_beide())

    class Strom(io.BytesIO):
        def close(self):
            raise RuntimeError("age vorzeitig beendet")
    code = nas.main([str(ordner), "--zuordnung", str(_zuordnung(tmp_path)),
                     "--ziel", str(tmp_path / "ziel")], oeffnen=lambda p: Strom(daten))
    assert code == 0
