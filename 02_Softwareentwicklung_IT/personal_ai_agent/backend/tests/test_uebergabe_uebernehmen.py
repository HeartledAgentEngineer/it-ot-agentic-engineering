"""Pruefungen fuer ``uebergabe_uebernehmen.py`` (Nachtlauf-Schritt N13c, 28.09.2026).

Alles OHNE Netz, ohne Kabel, ohne echtes Handy: Quelle und Ziel sind
künstliche Ordner unter ``tmp_path``, die Dateien darin sind erfundene
Beispielinhalte. Geprueft werden die Zaehler, die byte-genaue Uebernahme
(sha256 hart verglichen), die Sicherung als ``.vorher`` (Rueckweg), das
Entfernen **nur** der eigenen Uebergabedatei, der Trockenlauf, die Idempotenz,
das Protokoll, die Schutzsperre gegen Ziele IM Repo und die Grenzen im
Quelltext (kein Netz, kein Fremdaufruf, genau eine Loeschstelle).

**Nur erfundene Beispielinhalte** — echte Kennungen, Namen und Schluesselwerte
kommen hier nicht vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_uebergabe_uebernehmen.py -q
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest

# ``app.services`` liegt unter ``backend/`` — wie in den Nachbardateien wird
# dieses Verzeichnis vor dem Import an den Suchpfad gehaengt.
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services import beziehungen_service as dienst_beziehungen  # noqa: E402
from app.services import erzaehl_service as dienst_erzaehlung  # noqa: E402
from app.services import foto_bilder as dienst_bilder  # noqa: E402
from app.services import foto_uebersicht as dienst_foto_uebersicht  # noqa: E402
from app.services import gruppen_quiz as dienst_gruppen  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "handy" / "uebergabe_uebernehmen.py"
STARTTERMUX = REPO / "start-termux.sh"

# Erfundene Beispielnamen und -inhalte.
DATEI_A = "fotos_dateien.json"
DATEI_B = "fotos_uebersicht.json"
INHALT_A = b'{"art": "beispiel_dateien", "zahlen": {"events": 2}}'
INHALT_B = b'{"art": "beispiel_uebersicht", "zahlen": {"events": 2}}'
INHALT_ALT = b'{"art": "beispiel_alt", "zahlen": {"events": 1}}'


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


uu = _laden(WERKZEUG, "uebergabe_uebernehmen")


# ── kleine Helfer ──────────────────────────────────────────────────────────

def _hash(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


def _bestand(ordner: Path) -> dict:
    """Bestandsaufnahme eines Baums: relativer Pfad -> sha256 des Inhalts.

    Damit laesst sich ein Trockenlauf pruefen: schreibt oder loescht er
    irgendetwas, aendert sich diese Aufnahme.
    """
    aufnahme = {}
    for pfad in sorted(ordner.rglob("*")):
        if pfad.is_file():
            aufnahme[str(pfad.relative_to(ordner)).replace("\\", "/")] = \
                _hash(pfad.read_bytes())
    return aufnahme


def _quelle(tmp_path: Path, **dateien: bytes) -> tuple[Path, Path]:
    """Quell- und Zielordner anlegen; ``dateien`` sind Name -> Inhalt der Quelle."""
    quelle = tmp_path / "quelle"
    ziel = tmp_path / "ziel"
    quelle.mkdir()
    for name, inhalt in dateien.items():
        (quelle / name.replace("_json", ".json")).write_bytes(inhalt)
    return quelle, ziel


def _ordnung(tmp_path: Path) -> tuple[Path, Path]:
    """Die ueblichen zwei Uebergabedateien in der Quelle."""
    return _quelle(tmp_path, fotos_dateien_json=INHALT_A,
                   fotos_uebersicht_json=INHALT_B)


def _lauf(quelle: Path, ziel: Path, *extra, dateien=(DATEI_A, DATEI_B),
          protokoll=None) -> int:
    """``main`` mit den ueblichen Argumenten aufrufen."""
    argv = ["--quelle", str(quelle), "--ziel", str(ziel),
            "--dateien", *dateien]
    if protokoll is not None:
        argv += ["--protokoll", str(protokoll)]
    argv += list(extra)
    return uu.main(argv)


# ── Konstanten und Plan (rein) ─────────────────────────────────────────────

def test_standard_suffix_ist_vorher():
    assert uu.STANDARD_VORHER_SUFFIX == ".vorher"


def test_zustandsnamen_sind_fest():
    assert (uu.ZUSTAND_FEHLT, uu.ZUSTAND_UNVERAENDERT, uu.ZUSTAND_UEBERNEHMEN) \
        == ("fehlt", "unveraendert", "uebernehmen")


def test_zaehlernamen_sind_fest():
    assert set(uu.ZAEHLER_NAMEN) == {"uebernommen", "unveraendert",
                                     "uebersprungen", "fehler"}


def test_sha256_datei_ist_der_bekannte_wert(tmp_path):
    probe = tmp_path / "probe.bin"
    probe.write_bytes(b"Beispielinhalt")
    assert uu.sha256_datei(str(probe)) == _hash(b"Beispielinhalt")


def test_sha256_datei_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        uu.sha256_datei(str(tmp_path / "gibtsnicht.bin"))
    assert "nicht gefunden" in str(fehler.value)


def test_sha256_datei_ohne_pfad_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        uu.sha256_datei("   ")
    assert "Kein Pfad" in str(fehler.value)


def test_plan_ordnet_fehlen_zu(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    plan = uu.uebernahme_planen(str(quelle), str(ziel), [DATEI_A, DATEI_B])
    assert [eintrag["zustand"] for eintrag in plan] == \
        [uu.ZUSTAND_UEBERNEHMEN, uu.ZUSTAND_UEBERNEHMEN]


def test_plan_zeigt_gleiche_pruefsumme_als_unveraendert(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_A)
    plan = uu.uebernahme_planen(str(quelle), str(ziel), [DATEI_A, DATEI_B])
    assert [eintrag["zustand"] for eintrag in plan] == \
        [uu.ZUSTAND_UNVERAENDERT, uu.ZUSTAND_UEBERNEHMEN]


def test_plan_zeigt_abweichende_pruefsumme_als_uebernehmen(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_ALT)
    plan = uu.uebernahme_planen(str(quelle), str(ziel), [DATEI_A, DATEI_B])
    assert plan[0]["zustand"] == uu.ZUSTAND_UEBERNEHMEN
    assert plan[0]["sha256_ziel"] == _hash(INHALT_ALT)


def test_plan_zeigt_fehlende_uebergabedatei(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    plan = uu.uebernahme_planen(str(quelle), str(ziel), [DATEI_A, "fehlt.json"])
    assert plan[1]["zustand"] == uu.ZUSTAND_FEHLT
    assert plan[1]["groesse"] is None


def test_plan_haelt_die_reihenfolge_der_dateien(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    plan = uu.uebernahme_planen(str(quelle), str(ziel), [DATEI_B, DATEI_A])
    assert [eintrag["name"] for eintrag in plan] == [DATEI_B, DATEI_A]


def test_plan_schreibt_nichts_und_liest_zweimal_dasselbe(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    vorher = _bestand(tmp_path)
    erst = uu.uebernahme_planen(str(quelle), str(ziel), [DATEI_A, DATEI_B])
    zweit = uu.uebernahme_planen(str(quelle), str(ziel), [DATEI_A, DATEI_B])
    assert erst == zweit
    assert _bestand(tmp_path) == vorher
    assert not ziel.exists()


def test_plan_ohne_quelle_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        uu.uebernahme_planen("", "Ziel", [DATEI_A])
    assert "Quelle und Ziel" in str(fehler.value)


def test_plan_ohne_dateien_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        uu.uebernahme_planen("Quelle", "Ziel", [])
    assert "keine Uebergabedatei" in str(fehler.value)


def test_plan_ohne_vorher_suffix_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        uu.uebernahme_planen("Quelle", "Ziel", [DATEI_A], vorher_suffix="")
    assert "Vorher-Suffix" in str(fehler.value)


def test_plan_lehnt_pfadanteile_im_namen_ab():
    for name in ("../fremd.json", "unter/datei.json", "unter\\datei.json", ".."):
        with pytest.raises(ValueError):
            uu.uebernahme_planen("Quelle", "Ziel", [name])


# ── (a) Ziel fehlt -> kopiert ──────────────────────────────────────────────

def test_a_ziel_fehlt_wird_kopiert(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    assert _lauf(quelle, ziel) == 0
    assert (ziel / DATEI_A).read_bytes() == INHALT_A
    assert (ziel / DATEI_B).read_bytes() == INHALT_B
    assert not (quelle / DATEI_A).exists(), "Uebergabedatei muss weg sein"
    assert not (quelle / DATEI_B).exists(), "Uebergabedatei muss weg sein"
    ausgabe = capsys.readouterr().out
    assert "uebernommen 2" in ausgabe
    assert "Fehler 0" in ausgabe


def test_a_ziel_ist_byte_gleich_nach_der_uebernahme(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    _lauf(quelle, ziel)
    assert _hash((ziel / DATEI_A).read_bytes()) == _hash(INHALT_A)
    assert _hash((ziel / DATEI_B).read_bytes()) == _hash(INHALT_B)


def test_a_keine_temp_datei_bleibt_liegen(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    _lauf(quelle, ziel)
    assert list(ziel.glob("*.teil")) == []


def test_a_ohne_vorhandenes_ziel_entsteht_keine_sicherung(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    _lauf(quelle, ziel)
    assert list(ziel.glob("*.vorher")) == []


# ── (b) Ziel identisch -> unveraendert ─────────────────────────────────────

def test_b_identisches_ziel_bleibt_unveraendert(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_A)
    (ziel / DATEI_B).write_bytes(INHALT_ALT)          # B ist anders
    assert _lauf(quelle, ziel) == 0
    ausgabe = capsys.readouterr().out
    assert f"{DATEI_A}: unveraendert" in ausgabe
    assert (ziel / DATEI_A).read_bytes() == INHALT_A


def test_b_identisches_ziel_legt_keine_sicherung_an(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_A)
    _lauf(quelle, ziel, dateien=[DATEI_A])
    assert not (ziel / (DATEI_A + ".vorher")).exists()


def test_b_identisches_ziel_entfernt_die_uebergabedatei(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_A)
    _lauf(quelle, ziel, dateien=[DATEI_A])
    assert not (quelle / DATEI_A).exists()


def test_b_zaehler_zeigt_unveraendert(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_A)
    _lauf(quelle, ziel, dateien=[DATEI_A])
    assert "unveraendert 1" in capsys.readouterr().out


# ── (c) Ziel unterschiedlich -> Sicherung + neue Bytes ────────────────────

def test_c_alte_zielbytes_liegen_vollstaendig_in_der_sicherung(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_ALT)
    assert _lauf(quelle, ziel, dateien=[DATEI_A]) == 0
    sicherung = ziel / (DATEI_A + ".vorher")
    assert sicherung.is_file()
    assert sicherung.read_bytes() == INHALT_ALT
    assert _hash(sicherung.read_bytes()) == _hash(INHALT_ALT)


def test_c_ziel_traegt_die_neuen_bytes(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_ALT)
    _lauf(quelle, ziel, dateien=[DATEI_A])
    assert (ziel / DATEI_A).read_bytes() == INHALT_A


def test_c_uebergabedatei_ist_entfernt(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_ALT)
    _lauf(quelle, ziel, dateien=[DATEI_A])
    assert not (quelle / DATEI_A).exists()


def test_c_bericht_nennt_die_sicherung(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_ALT)
    _lauf(quelle, ziel, dateien=[DATEI_A])
    assert f"gesichert als {DATEI_A}.vorher" in capsys.readouterr().out


def test_c_eigenes_suffix_wird_benutzt(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_ALT)
    assert _lauf(quelle, ziel, "--vorher-suffix", ".alt", dateien=[DATEI_A]) == 0
    assert (ziel / (DATEI_A + ".alt")).read_bytes() == INHALT_ALT
    assert _hash((ziel / DATEI_A).read_bytes()) == _hash(INHALT_A)


def test_c_zweite_uebernahme_sichert_die_vorherige_fassung(tmp_path):
    """Nach zwei Uebernahmen liegt die mittlere Fassung in der Sicherung."""
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_ALT)
    _lauf(quelle, ziel, dateien=[DATEI_A])                  # ALT -> INHALT_A
    (quelle / DATEI_A).write_bytes(b"dritte Fassung")
    _lauf(quelle, ziel, dateien=[DATEI_A])                  # INHALT_A -> dritte
    assert (ziel / (DATEI_A + ".vorher")).read_bytes() == INHALT_A
    assert (ziel / DATEI_A).read_bytes() == b"dritte Fassung"


# ── (d) Quelle fehlt -> kein Fehler ────────────────────────────────────────

def test_d_fehlende_quelle_ist_kein_fehler(tmp_path, capsys):
    ziel = tmp_path / "ziel"
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_A)
    quelle = tmp_path / "quelle_leer"
    quelle.mkdir()
    vorher = _bestand(tmp_path)
    assert _lauf(quelle, ziel) == 0
    assert _bestand(tmp_path) == vorher, "es darf nichts geschrieben werden"
    ausgabe = capsys.readouterr().out
    assert "uebersprungen 2" in ausgabe


def test_d_fehlende_quelle_legt_den_zielordner_nicht_an(tmp_path):
    quelle = tmp_path / "quelle_leer"
    quelle.mkdir()
    ziel = tmp_path / "gar_nicht_da"
    assert _lauf(quelle, ziel) == 0
    assert not ziel.exists()


# ── (e) Trockenlauf: keine Wirkung ─────────────────────────────────────────

def test_e_trockenlauf_schreibt_und_loescht_nichts(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    vorher = _bestand(tmp_path)
    assert _lauf(quelle, ziel, "--trocken") == 0
    assert _bestand(tmp_path) == vorher
    assert not ziel.exists()
    ausgabe = capsys.readouterr().out
    assert "TROCKENLAUF" in ausgabe
    assert "wuerde uebernommen" in ausgabe


def test_e_trockenlauf_laesst_auch_ein_abweichendes_ziel_unberuehrt(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_ALT)
    vorher = _bestand(tmp_path)
    assert _lauf(quelle, ziel, "--trocken") == 0
    assert _bestand(tmp_path) == vorher
    assert (ziel / DATEI_A).read_bytes() == INHALT_ALT


def test_e_trockenlauf_entfernt_die_uebergabedatei_nicht(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    _lauf(quelle, ziel, "--trocken")
    assert (quelle / DATEI_A).is_file()
    assert (quelle / DATEI_B).is_file()


def test_e_trockenlauf_entfernt_auch_bei_gleichem_ziel_nichts(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_A)
    assert _lauf(quelle, ziel, "--trocken", dateien=[DATEI_A]) == 0
    assert (quelle / DATEI_A).is_file()
    assert "wuerde entfernt" in capsys.readouterr().out


def test_e_trockenlauf_schreibt_kein_protokoll(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    protokoll = tmp_path / "protokoll" / "uebergabe_letzte.txt"
    assert _lauf(quelle, ziel, "--trocken", protokoll=protokoll) == 0
    assert not protokoll.exists()


# ── (f) Idempotenz ─────────────────────────────────────────────────────────

def test_f_zweiter_lauf_hat_nichts_mehr_zu_tun(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    assert _lauf(quelle, ziel) == 0
    capsys.readouterr()
    assert _lauf(quelle, ziel) == 0
    ausgabe = capsys.readouterr().out
    assert "uebernommen 0" in ausgabe
    assert "Fehler 0" in ausgabe
    assert "uebersprungen 2" in ausgabe
    assert (ziel / DATEI_A).read_bytes() == INHALT_A


def test_f_zweiter_lauf_aendert_nichts_am_bestand(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    _lauf(quelle, ziel)
    vorher = _bestand(tmp_path)
    _lauf(quelle, ziel)
    assert _bestand(tmp_path) == vorher


def test_f_wiederholte_uebergabe_desselben_standes_aendert_das_ziel_nicht(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    ziel.mkdir()
    (ziel / DATEI_A).write_bytes(INHALT_A)
    _lauf(quelle, ziel, dateien=[DATEI_A])
    vorher = (ziel / DATEI_A).read_bytes()
    (quelle / DATEI_A).write_bytes(INHALT_A)          # derselbe Stand erneut
    _lauf(quelle, ziel, dateien=[DATEI_A])
    assert (ziel / DATEI_A).read_bytes() == vorher


# ── (g) Protokoll ──────────────────────────────────────────────────────────

def test_g_protokoll_haelt_die_zeilen_fest(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    protokoll = tmp_path / "protokoll" / "uebergabe_letzte.txt"
    assert _lauf(quelle, ziel, protokoll=protokoll) == 0
    text = protokoll.read_text(encoding="utf-8")
    assert f"{DATEI_A}: uebernommen" in text
    assert "Zusammenfassung: uebernommen 2" in text
    assert f"Ziel:   {ziel}" in text


def test_g_protokoll_zwei_laeufe_haengt_an_statt_zu_ueberschreiben(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    protokoll = tmp_path / "protokoll" / "uebergabe_letzte.txt"
    _lauf(quelle, ziel, protokoll=protokoll)
    erster_text = protokoll.read_text(encoding="utf-8")
    # Zweiter Lauf mit frischer Uebergabedatei (neuer Inhalt).
    (quelle / DATEI_A).write_bytes(b"zweiter Stand")
    _lauf(quelle, ziel, protokoll=protokoll)
    zweiter_text = protokoll.read_text(encoding="utf-8")
    assert zweiter_text.startswith(erster_text), "das Protokoll wird anghaengt"
    assert "zweiter Stand" not in zweiter_text, "kein Inhalt, nur Zustand"
    assert zweiter_text.count("Ziel:") == 2, "je Lauf eine Zeile"
    assert "uebernommen 1" in zweiter_text


def test_g_protokoll_ziele_stehen_je_lauf_drin(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    protokoll = tmp_path / "protokoll" / "uebergabe_letzte.txt"
    _lauf(quelle, ziel, protokoll=protokoll)
    _lauf(quelle, ziel, protokoll=protokoll)
    text = protokoll.read_text(encoding="utf-8")
    assert text.count("Quelle:") == 2, "je Lauf eine Kopfzeile"
    assert text.count("Zusammenfassung:") == 2
    assert "uebernommen 2" in text, "erster Lauf hat uebernommen"
    assert "uebersprungen 2" in text, "zweiter Lauf hatte nichts zu tun"


def test_g_protokoll_legt_den_ordner_an(tmp_path):
    quelle, ziel = _ordnung(tmp_path)
    protokoll = tmp_path / "tief" / "tiefer" / "uebergabe_letzte.txt"
    _lauf(quelle, ziel, protokoll=protokoll)
    assert protokoll.is_file()


def test_g_protokoll_enthaelt_keine_schluesselnamen(tmp_path):
    """Nur Dateiname, Groesse, Pruefsumme und Zustand — nie ein Inhalt."""
    quelle, ziel = _ordnung(tmp_path)
    protokoll = tmp_path / "protokoll" / "uebergabe_letzte.txt"
    _lauf(quelle, ziel, protokoll=protokoll)
    text = protokoll.read_text(encoding="utf-8")
    assert "beispiel_dateien" not in text
    assert "zahlen" not in text


# ── (h) Schutz: Ziel im Repo ───────────────────────────────────────────────

def test_h_ziel_im_repo_ergibt_exit_2(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    verboten = REPO / "foto_sortierung_pruefung"
    assert not verboten.exists(), "Vorbedingung: den Ordner gibt es nicht"
    assert _lauf(quelle, verboten) == 2
    assert "IM Repo" in capsys.readouterr().err
    assert not verboten.exists(), "im Repo darf nichts angelegt werden"
    assert (quelle / DATEI_A).is_file(), "nichts uebernommen"


def test_h_ziel_im_repo_legt_auch_keine_unterordner_an(tmp_path):
    quelle, _ = _ordnung(tmp_path)
    verboten = REPO / "docs" / "pruefung_ziel"
    assert not verboten.exists(), "Vorbedingung: den Ordner gibt es nicht"
    assert _lauf(quelle, verboten) == 2
    assert not verboten.exists()


def test_h_protokoll_im_repo_ergibt_exit_2(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    protokoll = REPO / "uebergabe_protokoll_pruefung.txt"
    assert not protokoll.exists(), "Vorbedingung: die Datei gibt es nicht"
    assert _lauf(quelle, ziel, protokoll=protokoll) == 2
    assert "IM Repo" in capsys.readouterr().err
    assert not protokoll.exists()
    assert not ziel.exists(), "vor dem Schutzfehler darf nichts entstehen"
    assert (quelle / DATEI_A).is_file()


def test_h_im_repo_helfer_erkennt_beide_schreibweisen():
    assert uu._im_repo(str(REPO))
    assert uu._im_repo(str(REPO / "tools" / "handy"))


def test_h_im_repo_helfer_ist_fuer_fremde_pfade_falsch(tmp_path):
    assert not uu._im_repo(str(tmp_path))


# ── Aufruf-Fehler ──────────────────────────────────────────────────────────

def test_ohne_quelle_ergibt_exit_2(capsys):
    assert uu.main(["--ziel", "Ziel", "--dateien", DATEI_A]) == 2
    assert "--quelle" in capsys.readouterr().err


def test_ohne_ziel_ergibt_exit_2(capsys):
    assert uu.main(["--quelle", "Quelle", "--dateien", DATEI_A]) == 2
    assert "--ziel" in capsys.readouterr().err


def test_ohne_dateien_ergibt_exit_2(capsys):
    assert uu.main(["--quelle", "Quelle", "--ziel", "Ziel"]) == 2
    assert "--dateien" in capsys.readouterr().err


def test_leeres_vorher_suffix_ergibt_exit_2(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    assert _lauf(quelle, ziel, "--vorher-suffix", "") == 2
    assert "--vorher-suffix" in capsys.readouterr().err


# ── Bericht (Klartext deutsch) ─────────────────────────────────────────────

def test_zaehler_text_ist_deutsch():
    text = uu.zaehler_text({"uebernommen": 2, "unveraendert": 1,
                            "uebersprungen": 0, "fehler": 0})
    assert text == "uebernommen 2 · unveraendert 1 · uebersprungen 0 · Fehler 0"


def test_zaehler_text_haelt_fehlende_werte_aus():
    assert "uebernommen 0" in uu.zaehler_text({})


def test_uebernehmen_mit_leerem_plan_ergibt_null_zaehler():
    ergebnis = uu.uebernehmen([])
    assert ergebnis["zaehler"] == {"uebernommen": 0, "unveraendert": 0,
                                   "uebersprungen": 0, "fehler": 0}
    assert ergebnis["fehler"] is False
    assert ergebnis["zeilen"] == []


def test_bericht_zeigt_groesse_und_pruefsumme(tmp_path, capsys):
    quelle, ziel = _ordnung(tmp_path)
    _lauf(quelle, ziel, dateien=[DATEI_A])
    ausgabe = capsys.readouterr().out
    assert str(len(INHALT_A)) in ausgabe
    assert _hash(INHALT_A)[:12] in ausgabe


def test_meldung_ohne_kennung_ist_kein_geheimnis_im_bericht(tmp_path, capsys):
    """Der Bericht nennt nur Namen, Groesse und Pruefsumme."""
    quelle, ziel = _ordnung(tmp_path)
    _lauf(quelle, ziel)
    ausgabe = capsys.readouterr().out
    assert "beispiel_dateien" not in ausgabe
    assert "art" not in ausgabe


# ── (i) Quelltext: keine Netze, kein Fremdaufruf, eine Loeschstelle ────────

def _baum():
    return ast.parse(WERKZEUG.read_text(encoding="utf-8"))


def _aufrufe(methode: str) -> list:
    """Alle Aufrufe ``<etwas>.<methode>(...)`` im Quelltext."""
    return [knoten for knoten in ast.walk(_baum())
            if isinstance(knoten, ast.Call)
            and isinstance(knoten.func, ast.Attribute)
            and knoten.func.attr == methode]


def test_quelltext_importiert_nur_standardbibliothek():
    erlaubt = {"argparse", "datetime", "hashlib", "os", "sys", "__future__"}
    namen: set = set()
    for knoten in ast.walk(_baum()):
        if isinstance(knoten, ast.Import):
            for eintrag in knoten.names:
                namen.add(eintrag.name.split(".")[0])
        elif isinstance(knoten, ast.ImportFrom):
            namen.add((knoten.module or "").split(".")[0])
    assert namen <= erlaubt, f"unerlaubter Import: {namen - erlaubt}"


def test_quelltext_ohne_netz_fremdaufruf_und_cloud():
    quelle = WERKZEUG.read_text(encoding="utf-8").lower()
    verboten = ("requests", "urllib", "httpx", "socket", "subprocess",
                "pcloud", "urllib3", "aiohttp", "curl ", "wget ",
                "import git", "git ", "os.system", "popen", "eval(")
    for wort in verboten:
        assert wort not in quelle, f"verbotener Aufruf im Quelltext: {wort}"


def test_quelltext_hat_genau_eine_loeschstelle():
    """Geloescht wird nur an EINER Stelle: der eigenen Uebergabe-/temp-Datei."""
    aufrufe = _aufrufe("remove") + _aufrufe("unlink")
    assert len(aufrufe) == 1, "genau eine Loeschstelle im ganzen Modul"
    assert isinstance(aufrufe[0].func.value, ast.Name)
    assert aufrufe[0].func.value.id == "os"


def test_quelltext_loescht_nur_in_der_erlaubten_funktion():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "def _entferne(" in quelle
    definierungen = [knoten for knoten in ast.walk(_baum())
                     if isinstance(knoten, ast.FunctionDef)
                     and knoten.name == "_entferne"]
    assert len(definierungen) == 1
    rumpf = ast.get_source_segment(quelle, definierungen[0]) or ""
    assert "os.remove(" in rumpf
    assert "os.unlink(" not in rumpf


def test_quelltext_ohne_loeschfunktion_fuer_bestaende():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("def loeschen", "def delete", "def entfernen", "shutil",
                     "rmtree", "rmdir", "os.removedirs"):
        assert verboten not in quelle, f"Loeschfunktion im Quelltext: {verboten}"


def test_quelltext_loescht_die_uebergabedatei_erst_nach_der_pruefung():
    """Das Entfernen im Erfolgszweig steht HINTER dem Pruefsummenvergleich."""
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert quelle.index("if pruefsumme_ziel != eintrag[\"sha256_quelle\"]") \
        < quelle.rindex("_entferne(eintrag[\"quelle\"])")


def test_quelltext_schreibt_atomar():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "os.replace(" in quelle
    assert "TEMP_SUFFIX" in quelle


def test_quelltext_prueft_das_repo():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "_pruefe_ausserhalb_repo" in quelle
    assert "IM Repo" in quelle


def test_quelltext_haengt_das_protokoll_nur_an():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert 'open(pfad, "a", encoding="utf-8")' in quelle
    assert 'open(pfad, "w"' not in quelle


def test_quelltext_ohne_feste_ausgabepfade():
    """Keine Vorgabepfade: Quelle und Ziel kommen ausschliesslich von aussen."""
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "STANDARD_AUSGABE" not in quelle
    assert "expanduser" not in quelle


# ── Waechter: Startskript uebernimmt die vom Dienst gelesenen Datendateien ───
#
# Der Fehler, den diese Waechter verhindern: im Startskript stand in der
# Dateiliste nur `fotos_dateien.json fotos_uebersicht.json`. Die drei Dateien,
# die die Dienste am Handy tatsaechlich lesen (ereignisse.jsonl fuer die
# Erzaehl-Diashow, beziehungen.jsonl/beziehungen.json fuer "was war am
# <Datum>?"), fehlten — die Dienste liefen ins Leere, obwohl der PC sie
# bereitstellte. Die erwarteten Namen kommen deshalb NICHT abgeschrieben aus
# dem Skript, sondern aus den Dienst-Konstanten (Quelle der Wahrheit).

def _erwartete_dateinamen() -> set:
    """Die von den Diensten gelesenen Dateinamen aus den Modulkonstanten.

    Alle **zwoelf** Dateien, die ein Dienst am Handy aus ``~/foto_sortierung``
    liest — nicht nur die drei in diesem Schritt ergaenzten. Sonst koennte eine
    spaetere Aenderung die zwei aelteren Namen aus dem Startskript entfernen,
    ohne dass ein Waechter anschlaegt. ``geschichten.jsonl`` fehlt bewusst: die
    schreibt das Handy selbst.
    """
    return {
        dienst_bilder.DATEIEN_DATEINAME,               # fotos_dateien.json
        dienst_foto_uebersicht.UEBERSICHT_DATEINAME,   # fotos_uebersicht.json
        dienst_erzaehlung.EREIGNISSE_DATEINAME,        # ereignisse.jsonl
        dienst_beziehungen.BEZIEHUNGEN_DATEINAME,      # beziehungen.jsonl
        dienst_beziehungen.UEBERSICHT_DATEINAME,       # beziehungen.json
        dienst_gruppen.BEISPIELE_DATEINAME,            # personen_beispiele.json (01.10.)
        dienst_gruppen.ZUORDNUNG_DATEINAME,            # gesicht_zuordnung.jsonl (01.10.)
        dienst_gruppen.KONTAKTE_DATEINAME,             # kontakte.json (02.10., Issue #3)
        dienst_erzaehlung.FOTOBUCH_DATEINAME,          # fotobuch_ereignisse.jsonl (02.10.)
        dienst_erzaehlung.ORDNER_EREIGNISSE_DATEINAME, # ordner_ereignisse.jsonl (07.10., Issue #4 A1)
        dienst_erzaehlung.BESCHREIBUNGEN_DATEINAME,    # bild_beschreibungen.jsonl (07.10., Was und wo)
        dienst_erzaehlung.BILD_ORTE_DATEINAME,         # bild_orte.csv (07.10., Was und wo)
    }


def test_waechter_erwartete_namen_deckt_alle_gelesenen_datendateien():
    """Der Waechter kennt genau die zwoelf Dateien, die die Dienste lesen."""
    namen = _erwartete_dateinamen()
    assert len(namen) == 12, f"unerwartete Namensmenge: {sorted(namen)}"
    for alt in (dienst_bilder.DATEIEN_DATEINAME,
                dienst_foto_uebersicht.UEBERSICHT_DATEINAME):
        assert alt in namen, f"vorbestehende Datei fehlt im Waechter: {alt}"


def _startskript_text() -> str:
    """Den Quelltext von start-termux.sh lesen (Pfad relativ zur Testdatei)."""
    assert STARTTERMUX.is_file(), f"Startskript fehlt: {STARTTERMUX}"
    return STARTTERMUX.read_text(encoding="utf-8")


def _uebergabedateien_im_startskript(text: str) -> list:
    """Reine Funktion: die Dateinamen aus allen ``--dateien``-Aufrufen.

    Gueltig ist nur ein reiner Dateiname: nicht leer, ohne Pfadanteil
    (kein ``/``, ``\\``, ``~``, ``..``) und kein weiteres Argument. Verstoesst
    ein Eintrag dagegen, wird ``ValueError`` geworfen — so kann eine
    unvollstaendige oder falsch aufgebaute Liste nie unbemerkt durchgehen.
    """
    namen: list = []
    for zeile in text.splitlines():
        if zeile.lstrip().startswith("#") or "--dateien" not in zeile:
            continue
        rumpf = zeile.split("--dateien", 1)[1].replace("\\", " ")
        for wort in rumpf.split():
            if wort in ("||", "&&", "|", ";") or wort.startswith("-"):
                break
            rein = wort.strip("'\"")
            if (not rein or "/" in rein or "\\" in rein or ".." in rein
                    or "~" in rein):
                raise ValueError(f"kein reiner Dateiname: {wort!r}")
            namen.append(rein)
    return namen


def _ziel_argumente_im_startskript(text: str) -> list:
    """Reine Funktion: die Werte hinter ``--ziel`` (einer je Uebergabeaufruf)."""
    werte: list = []
    for zeile in text.splitlines():
        if zeile.lstrip().startswith("#") or "--ziel" not in zeile:
            continue
        rest = zeile.split("--ziel", 1)[1].split()
        if rest:
            werte.append(rest[0].strip("'\"").rstrip("\\"))
    return werte


def _fehlende_namen(text: str) -> list:
    """Reine Funktion: welche erwarteten Dienst-Dateinamen im Skript fehlen."""
    vorhanden = set(_uebergabedateien_im_startskript(text))
    return sorted(_erwartete_dateinamen() - vorhanden)


def _pruefe_startskript(text: str) -> list:
    """Reine Prueffunktion: die uebernommenen Namen, sofern das Skript voll ist.

    Wirft ``ValueError``, wenn ein ``--ziel``-Argument fehlt oder ein von den
    Diensten gelesener Dateiname nicht im ``--dateien``-Aufruf steht.
    """
    if not _ziel_argumente_im_startskript(text):
        raise ValueError("kein --ziel im Startskript")
    fehlend = _fehlende_namen(text)
    if fehlend:
        raise ValueError(f"Dateiliste unvollstaendig, es fehlen: {fehlend}")
    return _uebergabedateien_im_startskript(text)


def test_waechter_startskript_uebernimmt_die_gelesenen_datendateien():
    """Das Startskript nennt die drei von den Diensten gelesenen Dateien."""
    namen = _pruefe_startskript(_startskript_text())
    fehlend = sorted(_erwartete_dateinamen() - set(namen))
    assert not fehlend, f"im Startskript fehlen: {fehlend}"


def test_waechter_startskript_nennt_die_dateien_in_beiden_aufrufen():
    """Mit und ohne ``--protokoll`` steht dieselbe vollstaendige Liste."""
    text = _startskript_text()
    zeilen = [z for z in text.splitlines()
              if "--dateien" in z and not z.lstrip().startswith("#")]
    assert len(zeilen) >= 2, "beide Uebergabeaufrufe muessen die Liste nennen"
    for zeile in zeilen:
        geparst = _uebergabedateien_im_startskript(zeile)
        for erwartet in _erwartete_dateinamen():
            assert erwartet in geparst, f"in Zeile fehlt {erwartet}: {zeile.strip()}"


def test_waechter_startskript_faellt_durch_bei_fehlendem_ziel_oder_luecke():
    """Gegenprobe: fehlt ``--ziel`` oder ein Name, schlaegt die Pruefung fehl."""
    echt = _startskript_text()
    # (1) Zielordner-Argument entfernt -> keine --ziel-Werte mehr
    ohne_ziel = "\n".join(z for z in echt.splitlines() if "--ziel" not in z)
    assert _ziel_argumente_im_startskript(ohne_ziel) == []
    with pytest.raises(ValueError):
        _pruefe_startskript(ohne_ziel)
    # (2) Dateiliste unvollstaendig -> der fehlende Name wird gemeldet
    unvollstaendig = echt.replace(" ereignisse.jsonl", " ")  # nur das alleinstehende Wort (fotobuch_ereignisse.jsonl bleibt)
    assert _fehlende_namen(unvollstaendig) == [dienst_erzaehlung.EREIGNISSE_DATEINAME]
    with pytest.raises(ValueError):
        _pruefe_startskript(unvollstaendig)


def test_waechter_prueffunktion_weist_pfadanteil_und_leeren_eintrag_ab():
    """Ein Name mit Pfadanteil oder ein leerer Eintrag geht nicht durch."""
    basis = "        --dateien fotos_dateien.json fotos_uebersicht.json"
    with pytest.raises(ValueError):
        _uebergabedateien_im_startskript(basis + " ../beziehungen.jsonl")
    with pytest.raises(ValueError):
        _uebergabedateien_im_startskript(basis + " pfad/beziehungen.json")
    with pytest.raises(ValueError):
        _uebergabedateien_im_startskript(basis + ' ""')
    # Gegenprobe: reine Namen gehen durch
    sauber = _uebergabedateien_im_startskript(
        basis + " ereignisse.jsonl beziehungen.jsonl beziehungen.json")
    assert sauber[-3:] == ["ereignisse.jsonl", "beziehungen.jsonl",
                           "beziehungen.json"]


# ── Waechter: auch der ECHTE App-Startweg uebernimmt (01.10.2026) ─────────────
#
# Befund 30.09.2026: Die Uebernahme stand nur in start-termux.sh (Widget-Tipp).
# Die App "Hey Agent" startet aber ueber termux/agent-ensure.sh — dort kam sie
# nie vorbei, per Kabel gelegte Dateien blieben im Download-Ordner liegen.

AGENT_ENSURE = REPO / "termux" / "agent-ensure.sh"


def test_waechter_app_startweg_uebernimmt_dieselben_dateien():
    text = AGENT_ENSURE.read_text(encoding="utf-8")
    assert _pruefe_startskript(text)                      # --ziel da, Liste vollstaendig
    zeilen = [z for z in text.splitlines()
              if "--dateien" in z and not z.lstrip().startswith("#")]
    assert len(zeilen) == 2, "mit und ohne Protokoll"
    for zeile in zeilen:
        geparst = _uebergabedateien_im_startskript(zeile)
        for erwartet in _erwartete_dateinamen():
            assert erwartet in geparst, f"in agent-ensure.sh fehlt {erwartet}"


def test_waechter_app_startweg_uebernahme_vor_dem_serverstart_und_abgefangen():
    text = AGENT_ENSURE.read_text(encoding="utf-8")
    uebernahme = text.index("uebergabe_uebernehmen.py")
    assert text.index("pull --ff-only") < uebernahme < text.index("python -m uvicorn")
    # Jeden Aufruf als ganzen Befehl lesen (Fortsetzungszeilen mit \ verbunden).
    befehle = text.replace("\\\n", " ").splitlines()
    aufrufe = [b for b in befehle if "uebergabe_uebernehmen.py" in b and not b.lstrip().startswith("#")]
    assert len(aufrufe) == 2
    for befehl in aufrufe:
        assert befehl.rstrip().endswith("|| true"), "Uebernahme darf den Start nie verhindern"


# ── Waechter: auch das Widget agent-start uebernimmt (10.10.2026) ─────────────
#
# Befund 10.10.2026: Neue Gruppen vom PC lagen nach dem Widget-Tipp weiter im
# Download-Ordner - agent-start rief die Uebernahme nie auf, agent-ensure.sh nur,
# wenn das Backend gerade nicht lief. Das Quiz zeigte weiter die alten Gruppen.

WIDGET = REPO / "termux" / "agent-start"


def test_waechter_widget_uebernimmt_dieselben_dateien():
    text = WIDGET.read_text(encoding="utf-8")
    assert _pruefe_startskript(text)
    zeilen = [z for z in text.splitlines()
              if "--dateien" in z and not z.lstrip().startswith("#")]
    assert len(zeilen) == 2, "mit und ohne Protokoll"
    for zeile in zeilen:
        geparst = _uebergabedateien_im_startskript(zeile)
        for erwartet in _erwartete_dateinamen():
            assert erwartet in geparst, f"in agent-start fehlt {erwartet}"


def test_waechter_widget_uebernahme_nach_pull_vor_serverstart_und_abgefangen():
    text = WIDGET.read_text(encoding="utf-8")
    uebernahme = text.index("uebergabe_uebernehmen.py")
    assert text.index("git pull --ff-only") < uebernahme < text.rindex("uvicorn")
    befehle = text.replace("\\\n", " ").splitlines()
    aufrufe = [b for b in befehle if "uebergabe_uebernehmen.py" in b and not b.lstrip().startswith("#")]
    assert len(aufrufe) == 2
    for befehl in aufrufe:
        assert befehl.rstrip().endswith("|| true"), "Uebernahme darf den Start nie verhindern"


def test_waechter_widget_und_app_haben_dieselbe_dateiliste():
    def liste(pfad):
        return sorted({n for z in pfad.read_text(encoding="utf-8").splitlines()
                       if "--dateien" in z and not z.lstrip().startswith("#")
                       for n in _uebergabedateien_im_startskript(z)
                       if "." in n and not n.startswith(("$", ">", "2>"))})  # Log-Umleitung ist kein Dateiname
    assert liste(WIDGET) == liste(AGENT_ENSURE)
