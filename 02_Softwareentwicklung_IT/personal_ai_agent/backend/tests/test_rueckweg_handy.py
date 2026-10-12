"""Waechter-Tests fuer den Rueckweg Handy -> PC (12.10.2026).

Alles OHNE Netz, ohne Kabel, ohne echtes Handy: geprueft werden

  * das neue Geraete-Skript ``termux/rueckweg-bereitstellen.sh`` (als Text, per
    ``bash -n`` und in einem echten Lauf gegen ein ``tmp_path``-Quellverzeichnis),
  * das neue PC-Werkzeug ``tools/handy/rueckweg_holen.py`` (als Text **und** im
    Lauf gegen eine **Attrappen-adb** — ein kleines Bash-Skript unter
    ``tmp_path``),
  * der **Waechter** gegen ein Auseinanderlaufen: die Dateiliste im Shell-Skript
    (``RUECKWEG_NAMEN``) muss genau ``ERLAUBTE_NAMEN`` im Werkzeug sein.

Die Regelgruppen:

 1. **Liste = Liste:** ``RUECKWEG_NAMEN`` aus dem Shell-Skript und
    ``ERLAUBTE_NAMEN`` aus dem Werkzeug sind dieselbe Menge (geordnet).
 2. **Geraete-Skript sauber:** ``bash -n`` Exit 0; keine verbotenen Muster
    (``rm``, ``delete``, ``unlink``, ``curl``, ``wget``, ``--force``); es
    kopiert (``cp``); Endzeile ist ``exit 0``.
 3. **Geraete-Skript im Lauf:** aus einem Quellordner werden genau die
    Listendateien in den Zielordner kopiert, eine unbekannte Datei **nicht**;
    der Quellordner bleibt unveraendert (gleiche Bytes); der zweite Lauf
    schreibt nichts (gleiche Groesse = ``unveraendert``); ein fehlender
    Quellordner ist kein Fehler (Exit 0).
 4. **Werkzeug offline:** Trockenlauf schreibt nichts (kein Ziel, kein
    Manifest); ``--holen`` holt die Listendateien; zweiter Lauf gleicher
    Groesse -> ``uebersprungen``; eine Datei, die NICHT auf der Liste steht,
    wird nicht geholt; ``GEHEIM-TESTTEXT`` erscheint NICHT im Bericht;
    ``--ziel`` IM Repo -> Exit 2; fehlender Geraete-Ordner -> Exit 1 mit
    ``--holen``, Exit 0 im Trockenlauf.
 5. **Rueckweg + Beleg:** eine geaenderte Zieldatei wird vorher als
    ``<name>.vorher`` gesichert (alte Bytes bleiben erhalten); je geholter
    Datei steht **eine** Manifest-Zeile mit passender sha256 und dem Vermerk
    ``handy->pc`` — dazu **Quelle, Ziel und Zeit** (AGENTS.md, Punkt 5); ohne
    ``--zeit`` wird die Zeit JETZT gebucht, ein ausdruecklich leerer Wert wird
    mit Exit 2 abgelehnt (nichts geschrieben).
 6. **Datenschutz/Kein Netz:** keine echten Namen in den neuen Dateien, kein
    Geheimnismuster; das Werkzeug kennt kein HTTP, kein pCloud, keinen Sockel
    und importiert nur die Standardbibliothek.

**Nur erfundene/kunstliche Kennungen** — echte Namen, Orte, Nummern und
Schluesselwerte kommen hier nicht vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_rueckweg_handy.py -q
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "handy" / "rueckweg_holen.py"
SKRIPT = REPO / "termux" / "rueckweg-bereitstellen.sh"

# Der Geraete-Ordner der Attrappen-adb.
ORDNER_GERAET = "/sdcard/Download/hermes_rueckweg"

# Fester Geheimnis-Platzhalter: darf im Bericht NIE auftauchen.
GEHEIM = "GEHEIM-TESTTEXT"

# Namen, die in einer ECHTEN Umgebung vorkommen und in NEUEN Dateien nichts zu
# suchen haben. Nur zur Absicherung — die neuen Dateien nennen bewusst niemanden.
VERBOTENE_NAMEN = ("Sebastian", "sebas", "Motorola", "Termux-Nutzer")

# Muster, die im Geraete-Skript nichts zu suchen haben (es kopiert nur).
VERBOTENE_MUSTER = ("rm ", "rm\t", "delete", "unlink", "curl", "wget", "--force")


# ── Laden und kleine Helfer ───────────────────────────────────────────────

def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


rh = _laden(WERKZEUG, "rueckweg_holen")


def _text(pfad: Path) -> str:
    assert pfad.is_file(), f"Datei fehlt: {pfad}"
    return pfad.read_text(encoding="utf-8")


def _bash() -> str:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash ist hier nicht vorhanden")
    return bash


def _lauf(argv: list):
    """``main`` aufrufen und Exit-Code + Ausgabe einsammeln (ohne echten adb)."""
    import contextlib
    import io
    puffer = io.StringIO()
    fehler = io.StringIO()
    with contextlib.redirect_stdout(puffer), contextlib.redirect_stderr(fehler):
        code = rh.main(argv)
    return code, puffer.getvalue(), fehler.getvalue()


def _namen_aus_skript() -> list:
    """``RUECKWEG_NAMEN`` aus dem Shell-Skript lesen (ohne Kommentare)."""
    for zeile in _text(SKRIPT).splitlines():
        if zeile.lstrip().startswith("#"):
            continue
        treffer = re.match(r'^RUECKWEG_NAMEN="\$\{RUECKWEG_NAMEN:-([^}]*)\}"', zeile.strip())
        if treffer:
            return treffer.group(1).split()
    raise AssertionError("RUECKWEG_NAMEN nicht im Skript gefunden")


def _attrappen_adb(tmp_path: Path, inhalt: dict) -> str:
    """Eine Attrappen-``adb`` bauen, die NIE ein Geraet anspricht.

    ``inhalt`` bildet Dateiname -> Textinhalt ab. ``shell ls -la`` liefert die
    passende Liste (Groessen aus dem Inhalt), ``pull`` schreibt den Inhalt.
    Nur erfundene Inhalte, kein Netz.
    """
    skript = tmp_path / "attrappe-adb"
    zeilen = [
        "#!/usr/bin/env bash",
        "# Attrappen-adb fuer die Tests: feste Antworten, kein echtes Geraet,",
        "# kein Netz. Nur erfundene Inhalte.",
        "set -u",
        f"ORDNER_ERWARTET='{ORDNER_GERAET}'",
        "gross() { printf '%s' \"$1\" | wc -c | tr -d ' '; }",
        "case \"${1:-}\" in",
        "  shell)",
        "    ORDNER=\"${4:-}\"",
        "    if [ \"$ORDNER\" != \"$ORDNER_ERWARTET\" ]; then",
        "      echo \"ls: $ORDNER: No such file or directory\" >&2",
        "      exit 1",
        "    fi",
        "    printf 'total 8\\n'",
    ]
    for name, text in inhalt.items():
        vari = "$INHALT_" + name.replace(".", "_")
        zeilen.append('    printf -- \'-rw-rw---- 1 u0_a1 u0_a1 %s 2026-10-12 10:00 '
                      + name + '\\n\' "$(gross "' + vari + '")"')
    zeilen += [
        "    exit 0",
        "    ;;",
        "  pull)",
        "    QUELLE=\"${2:-}\"; ZIEL=\"${3:-}\"",
        "    case \"$QUELLE\" in",
    ]
    for name in inhalt:
        zeilen.append("      *" + name + ") printf '%s' \"$INHALT_"
                      + name.replace(".", "_") + "\" > \"$ZIEL\" ;;")
    zeilen += [
        "      *) printf '%s' 'UNBEKANNT' > \"$ZIEL\" ;;",
        "    esac",
        "    exit 0",
        "    ;;",
        "esac",
        "exit 2",
        "",
    ]
    variablen = ["INHALT_" + name.replace(".", "_") + "=" + _shell(text)
                 for name, text in inhalt.items()]
    skript.write_text("\n".join(zeilen[:4] + variablen + zeilen[4:]), encoding="utf-8")

    bash = _bash()
    if os.name != "nt":
        skript.chmod(0o755)
        return str(skript)

    umweg = tmp_path / "attrappe-adb.cmd"
    umweg.write_text("@echo off\r\n" f'"{bash}" "%~dp0attrappe-adb" %*\r\n',
                     encoding="ascii")
    return str(umweg)


def _shell(text: str) -> str:
    """Text als einzeilige Shell-Zuweisung in einfache Anfuehrungszeichen."""
    return "'" + text.replace("'", "'\\''") + "'"


def _lauf_skript(ziel: Path, quelle: Path, namen: str = "") -> tuple:
    """Das Geraete-Skript mit umgeleiteten Ordnern starten."""
    umgebung = dict(os.environ)
    umgebung["RUECKWEG_QUELLE"] = str(quelle)
    umgebung["RUECKWEG_ZIEL"] = str(ziel)
    if namen:
        umgebung["RUECKWEG_NAMEN"] = namen
    lauf = subprocess.run([_bash(), str(SKRIPT)], capture_output=True, text=True,
                          env=umgebung)
    return lauf.returncode, lauf.stdout + lauf.stderr


# ── 1. Die Liste ist eine Liste ────────────────────────────────────────────

def test_regel1_liste_stimmt_zwischen_skript_und_werkzeug():
    assert list(rh.ERLAUBTE_NAMEN) == _namen_aus_skript()


def test_regel1_liste_ist_nicht_leer_und_ohne_pfade():
    assert rh.ERLAUBTE_NAMEN, "die Liste darf nicht leer sein"
    for name in rh.ERLAUBTE_NAMEN:
        assert "/" not in name and "\\" not in name and name.endswith(".jsonl")


# ── 2. Das Geraete-Skript als Text ─────────────────────────────────────────

def test_regel2_skript_hat_keine_verbotenen_muster():
    text = _text(SKRIPT)
    for muster in VERBOTENE_MUSTER:
        assert muster not in text, f"verbotenes Muster im Skript: {muster!r}"


def test_regel2_skript_kopiert_und_endet_mit_exit_0():
    text = _text(SKRIPT)
    assert "cp " in text, "das Skript muss kopieren"
    assert text.rstrip().splitlines()[-1].strip() == "exit 0"


def test_regel2_skript_ist_syntaktisch_gueltig():
    lauf = subprocess.run([_bash(), "-n", str(SKRIPT)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr


# ── 3. Das Geraete-Skript im Lauf ──────────────────────────────────────────

def test_regel3_skript_kopiert_nur_die_liste_und_laesst_quelle_in_ruhe(tmp_path):
    quelle = tmp_path / "quelle"
    ziel = tmp_path / "ziel"
    quelle.mkdir()
    (quelle / "geschichten.jsonl").write_text(GEHEIM, encoding="utf-8")
    (quelle / "anlass_umbenennung.jsonl").write_text("T", encoding="utf-8")
    (quelle / "fremd.jsonl").write_text("FREMD", encoding="utf-8")
    vorher = (quelle / "geschichten.jsonl").read_bytes()

    code, aus = _lauf_skript(ziel, quelle)
    assert code == 0, aus
    assert (ziel / "geschichten.jsonl").read_text(encoding="utf-8") == GEHEIM
    assert (ziel / "anlass_umbenennung.jsonl").is_file()
    assert not (ziel / "fremd.jsonl").exists(), "fremde Datei darf nicht mitgehen"
    assert (quelle / "geschichten.jsonl").read_bytes() == vorher, "Quelle veraendert"
    assert (quelle / "fremd.jsonl").is_file()
    assert "bereitgestellt 2" in aus


def test_regel3_zweiter_lauf_schreibt_nichts_und_fehlende_quelle_ist_kein_fehler(tmp_path):
    quelle = tmp_path / "quelle"
    ziel = tmp_path / "ziel"
    quelle.mkdir()
    (quelle / "geschichten.jsonl").write_text(GEHEIM, encoding="utf-8")

    code, _ = _lauf_skript(ziel, quelle)
    assert code == 0
    stempel = (ziel / "geschichten.jsonl").stat().st_mtime_ns
    code2, aus2 = _lauf_skript(ziel, quelle)
    assert code2 == 0
    assert "unveraendert 1" in aus2
    assert (ziel / "geschichten.jsonl").stat().st_mtime_ns == stempel, "wurde neu geschrieben"

    leer = tmp_path / "gibtsnicht"
    code3, aus3 = _lauf_skript(ziel, leer)
    assert code3 == 0, "fehlende Quelle ist kein Fehler"
    assert "nicht vorhanden" in aus3


def test_regel3_geaenderte_quelle_legt_alte_fassung_beiseite(tmp_path):
    quelle = tmp_path / "quelle"
    ziel = tmp_path / "ziel"
    quelle.mkdir()
    datei = quelle / "geschichten.jsonl"
    datei.write_text("erste Fassung", encoding="utf-8")
    code, _ = _lauf_skript(ziel, quelle)
    assert code == 0
    datei.write_text("zweite Fassung mit anderer Laenge", encoding="utf-8")
    code2, _ = _lauf_skript(ziel, quelle)
    assert code2 == 0
    assert (ziel / "geschichten.jsonl.vorher").read_text(
        encoding="utf-8") == "erste Fassung"
    assert (ziel / "geschichten.jsonl").read_text(
        encoding="utf-8") == "zweite Fassung mit anderer Laenge"


# ── 4./5. Das Werkzeug gegen die Attrappen-adb ─────────────────────────────

INHALT = {
    "geschichten.jsonl": GEHEIM,
    "anlass_umbenennung.jsonl": "TITEL-TEST",
    "fremd.jsonl": "FREMD-INHALT",
}


def test_regel4_trockenlauf_schreibt_nichts(tmp_path):
    attrappe = _attrappen_adb(tmp_path, INHALT)
    ziel = tmp_path / "pc_ziel"
    manifest = tmp_path / "manifest.jsonl"
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--manifest", str(manifest)])
    assert code == 0, aus
    assert not ziel.exists() or not list(ziel.iterdir()), "Trockenlauf schrieb etwas"
    assert not manifest.exists()
    assert "Trockenlauf" in aus
    assert "fremd.jsonl" in aus and "wird nicht geholt" in aus


def test_regel4_holen_und_zweiter_lauf_ueberspringt(tmp_path):
    attrappe = _attrappen_adb(tmp_path, INHALT)
    ziel = tmp_path / "pc_ziel"
    manifest = tmp_path / "manifest.jsonl"
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--manifest", str(manifest), "--holen"])
    assert code == 0, aus
    assert (ziel / "geschichten.jsonl").read_text(encoding="utf-8") == GEHEIM
    assert (ziel / "anlass_umbenennung.jsonl").is_file()
    assert not (ziel / "fremd.jsonl").exists(), "nicht gelistete Datei wurde geholt"
    assert "geholt 2" in aus

    code2, aus2, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                            "--manifest", str(manifest), "--holen"])
    assert code2 == 0, aus2
    assert "uebersprungen 2" in aus2 and "geholt 0" in aus2


def test_regel4_privatinhalt_erscheint_nicht_im_bericht(tmp_path):
    attrappe = _attrappen_adb(tmp_path, INHALT)
    ziel = tmp_path / "pc_ziel"
    manifest = tmp_path / "manifest.jsonl"
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--manifest", str(manifest), "--holen"])
    assert code == 0, aus
    assert GEHEIM not in aus, "Inhalt einer privaten Datei im Bericht"
    assert "FREMD-INHALT" not in aus
    assert manifest.read_text(encoding="utf-8").count("\n") == 2


def test_regel4_ziel_im_repo_gibt_exit_2(tmp_path):
    attrappe = _attrappen_adb(tmp_path, INHALT)
    ziel = REPO / "backend" / "tests" / "tmp_verboten"
    code, _, fehler = _lauf(["--adb", attrappe, "--ziel", str(ziel), "--holen"])
    assert code == 2
    assert "IM Repo" in fehler
    assert not ziel.exists(), "es darf nichts angelegt werden"


def test_regel4_fehlender_geraeteordner(tmp_path):
    attrappe = _attrappen_adb(tmp_path, INHALT)
    ziel = tmp_path / "pc_ziel"
    anderer = "/sdcard/Download/gibtsnicht"
    code, aus, _ = _lauf(["--adb", attrappe, "--ordner", anderer,
                          "--ziel", str(ziel)])
    assert code == 0, "Trockenlauf bei fehlendem Geraeteordner ist kein Fehler"
    assert "nicht vorhanden" in aus

    code2, _, _ = _lauf(["--adb", attrappe, "--ordner", anderer,
                         "--ziel", str(ziel), "--holen"])
    assert code2 == 1


def test_regel5_geaenderte_zielfassung_wird_beiseitegelegt(tmp_path):
    attrappe = _attrappen_adb(tmp_path, INHALT)
    ziel = tmp_path / "pc_ziel"
    manifest = tmp_path / "manifest.jsonl"
    ziel.mkdir()
    alt = ziel / "geschichten.jsonl"
    alt.write_text("alte Fassung", encoding="utf-8")
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--manifest", str(manifest), "--holen"])
    assert code == 0, aus
    assert (ziel / "geschichten.jsonl.vorher").read_text(
        encoding="utf-8") == "alte Fassung"
    assert alt.read_text(encoding="utf-8") == GEHEIM


def test_regel5_manifest_bucht_je_geholter_datei_eine_zeile_mit_sha256(tmp_path):
    attrappe = _attrappen_adb(tmp_path, INHALT)
    ziel = tmp_path / "pc_ziel"
    manifest = tmp_path / "manifest.jsonl"
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--manifest", str(manifest), "--holen"])
    assert code == 0, aus
    zeilen = [z for z in manifest.read_text(encoding="utf-8").splitlines() if z]
    assert len(zeilen) == 2, "je geholter Datei genau eine Buchung"
    buchungen = {json.loads(z)["name"]: json.loads(z) for z in zeilen}
    assert set(buchungen) == set(rh.ERLAUBTE_NAMEN)
    for name, buchung in buchungen.items():
        assert buchung["richtung"] == "handy->pc"
        assert buchung["bytes"] == (ziel / name).stat().st_size
        assert buchung["sha256"] == rh._sha256_datei(str(ziel / name))
        assert len(buchung["sha256"]) == 64


def test_regel5_buchung_traegt_zeit_quelle_und_ziel(tmp_path):
    """AGENTS.md Punkt 5: das Manifest nennt Quelle, Ziel und ZEIT.

    Gemessen am 12.10.2026 war die Zeit gebucht worden, aber LEER — die Zeile
    sagte nicht, wann die Datei den Weg genommen hat.
    """
    attrappe = _attrappen_adb(tmp_path, INHALT)
    ziel = tmp_path / "pc_ziel"
    manifest = tmp_path / "manifest.jsonl"
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--manifest", str(manifest), "--holen"])
    assert code == 0, aus
    zeilen = [z for z in manifest.read_text(encoding="utf-8").splitlines() if z]
    assert zeilen, "keine Buchung"
    for zeile in zeilen:
        buchung = json.loads(zeile)
        name = buchung["name"]
        assert buchung["zeit"], f"Zeit leer bei {name}"
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", buchung["zeit"]), \
            f"Zeit nicht in ISO-Form: {buchung['zeit']!r}"
        assert buchung["quelle"] == f"{ORDNER_GERAET}/{name}"
        assert buchung["ziel"] == str(ziel / name)


def test_regel5_zeit_option_setzt_den_wert_wortgleich(tmp_path):
    attrappe = _attrappen_adb(tmp_path, INHALT)
    ziel = tmp_path / "pc_ziel"
    manifest = tmp_path / "manifest.jsonl"
    fest = "2026-10-12T21:30:00+02:00"
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--manifest", str(manifest), "--holen",
                          "--zeit", fest])
    assert code == 0, aus
    zeilen = [z for z in manifest.read_text(encoding="utf-8").splitlines() if z]
    assert zeilen
    assert {json.loads(z)["zeit"] for z in zeilen} == {fest}


def test_regel5_leere_zeit_wird_abgelehnt_und_schreibt_nichts(tmp_path):
    """Ein LEERER --zeit-Wert wird nicht stillschweigend zur Uhrzeit."""
    attrappe = _attrappen_adb(tmp_path, INHALT)
    ziel = tmp_path / "pc_ziel"
    manifest = tmp_path / "manifest.jsonl"
    code, aus, fehler = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                               "--manifest", str(manifest), "--holen",
                               "--zeit", "  "])
    assert code == 2
    assert "leer" in fehler
    assert not manifest.exists(), "es darf nichts gebucht werden"
    assert not (ziel / "geschichten.jsonl").exists(), "es darf nichts geholt werden"


# ── 6. Datenschutz und kein Netz ──────────────────────────────────────────

def test_regel6_keine_echten_namen_in_den_neuen_dateien():
    for pfad in (WERKZEUG, SKRIPT):
        text = _text(pfad)
        for name in VERBOTENE_NAMEN:
            assert name not in text, f"{name!r} in {pfad.name}"


def test_regel6_keine_geheimnismuster():
    muster = (r"sk-[A-Za-z0-9]{8,}", r"Bearer\s+[A-Za-z0-9]", r"\d{30,}")
    for pfad in (WERKZEUG, SKRIPT):
        text = _text(pfad)
        for ausdruck in muster:
            assert not re.search(ausdruck, text), f"{ausdruck} in {pfad.name}"


def test_regel6_werkzeug_ohne_netz():
    """Nur der CODE wird geprueft (der Modulkopf nennt „kein Netz\\" als Grenze)."""
    text = _text(WERKZEUG)
    code = text.split('"""')[-1]
    for verboten in ("httpx", "requests", "urllib", "socket", "pcloud",
                     "http://", "https://"):
        assert verboten not in code, f"{verboten!r} im Werkzeug-Code"


def test_regel6_werkzeug_hat_genau_die_erwarteten_importe():
    text = _text(WERKZEUG)
    for erlaubt in ("argparse", "hashlib", "json", "os", "subprocess", "sys"):
        assert f"import {erlaubt}" in text


def test_regel6_vorgaben_liegen_ausserhalb_des_repos():
    """Ziel und Manifest sind Vorgaben in ``~/`` — nie im Repo (sonst testet der
    Lauf ins eigene Haus). Der Aufruf prueft das ohnehin mit ``_im_repo``."""
    assert not rh._im_repo(rh.STANDARD_ZIEL)
    assert not rh._im_repo(rh.STANDARD_MANIFEST)
    assert rh.STANDARD_ORDNER.startswith("/sdcard/")
