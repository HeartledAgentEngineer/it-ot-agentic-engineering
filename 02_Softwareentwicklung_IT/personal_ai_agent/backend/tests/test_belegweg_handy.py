"""Waechter-Tests fuer den Belegweg Job-Registrierung am Handy (N24b).

Alles OHNE Netz, ohne Kabel, ohne echtes Handy: geprueft werden der neue Block
in ``start-termux.sh`` (als Text und per ``bash -n``) und das neue PC-Werkzeug
``tools/handy/diag_holen.py`` (als Text **und** im Lauf gegen eine
**Attrappen-adb** — ein kleines Bash-Skript unter ``tmp_path``). Es wird nichts
an ein echtes Geraet geschickt und nichts aus dem Netz geladen.

Die Regelgruppen des Auftrags ``docs/auftrag-n24b-belegweg.md``:

 1. **Startskript-Block:** ``job_liste.txt`` und
    ``nachpflege_einrichtung_letzte.txt`` kommen vor; ``termux-job-scheduler
    --list`` kommt vor; ``command -v termux-job-scheduler`` als Waechter;
    ``mkdir -p "$DIAG"`` im NEUEN Block; ``JOB_ID_GEFUNDEN`` und
    ``JOB_ID_ERWARTET`` sind vorhanden.
 2. **Verbotene Muster** im Startskript: ``rm -rf``, ``deletefile``,
    ``deletefolder``, ``--force``, ``curl``, ``wget`` — 0 Treffer.
 3. **Kein Auseinanderlaufen:** die ``JOB_ID`` aus
    ``termux/nachpflege-einrichten.sh`` steht auch im Startskript (Zahl-
    Vergleich, aus beiden Dateien gelesen).
 4. **Reihenfolge:** der Beleg-Block steht NACH der Bestimmung von ``$DIAG``
    und NACH dem ``nachpflege-einrichten.sh``-Aufruf (nur Code-Zeilen zaehlen).
 5. **``bash -n start-termux.sh``** Exit 0 (nur wenn ``bash`` da ist, sonst skip).
 6. **Werkzeug offline:** Attrappen-adb — Trockenlauf schreibt nichts;
    ``--holen`` holt; beim zweiten Lauf gleicher Groesse -> ``uebersprungen``;
    ``GEHEIM-TESTTEXT`` aus einer Attrappen-``antworten_letzte.jsonl`` erscheint
    NICHT im Bericht; ``--ziel`` IM Repo -> Exit 2; fehlender Geraete-Ordner
    + ``--holen`` -> Exit 1.
 7. **Datenschutz:** keine echten Namen in den NEUEN Dateien, kein
    Geheimnismuster (``sk-``, Bearer-Kennung, Ziffernfolgen ab 30 Stellen).
 8. **Kein Netz/Geraet:** ``diag_holen.py`` kennt kein HTTP, kein pCloud,
    keinen Sockel; die Tests rufen ``adb`` nur ueber den Attrappen-Pfad auf.

**Nur erfundene/kunstliche Kennungen** — echte Namen, Orte, Nummern und
Schluesselwerte kommen hier nicht vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_belegweg_handy.py -q
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STARTTERMUX = REPO / "start-termux.sh"
EINRICHTEN = REPO / "termux" / "nachpflege-einrichten.sh"
WERKZEUG = REPO / "tools" / "handy" / "diag_holen.py"

# Der Geraete-Ordner, den die Attrappen-adb kennt (wie im Auftrag).
ORDNER_GERAET = "/sdcard/Download/hermes_diag"

# Fester Geheimnis-Platzhalter: darf im Bericht NIE auftauchen.
GEHEIM = "GEHEIM-TESTTEXT"

# Namen, die in einer ECHTEN Umgebung vorkommen und in NEUEN Dateien nichts zu
# suchen haben. Nur zur Absicherung — die neuen Dateien nennen bewusst niemanden.
VERBOTENE_NAMEN = ("Sebastian", "sebas", "Motorola", "Termux-Nutzer")


# ── Laden und kleine Helfer ───────────────────────────────────────────────

def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


dh = _laden(WERKZEUG, "diag_holen")


def _text(pfad: Path) -> str:
    assert pfad.is_file(), f"Datei fehlt: {pfad}"
    return pfad.read_text(encoding="utf-8")


def _ohne_kommentare(text: str) -> str:
    """Nur die Code-Zeilen (ohne ``#``-Kommentare) — fuer Reihenfolge-Pruefungen."""
    return "\n".join(z for z in text.splitlines()
                     if not z.lstrip().startswith("#"))


def _beleg_abschnitt() -> str:
    """Der NEUE Beleg-Block aus ``start-termux.sh`` (ab ``JOB_ID_ERWARTET=``)."""
    text = _text(STARTTERMUX)
    assert "JOB_ID_ERWARTET=" in text, "der Beleg-Block fehlt in start-termux.sh"
    return text[text.index("JOB_ID_ERWARTET="):]


def _attrappen_adb(tmp_path: Path) -> str:
    """Ein Bash-Skript als Attrappen-``adb`` bauen, das NIE ein Geraet anspricht.

    Auf POSIX wird das Skript direkt gestartet. Auf Windows kann ein
    Bash-Skript nicht direkt ausgefuehrt werden (kein Win32-Programm); dort
    entsteht daneben ein kleiner ``.cmd``-Umweg, der denselben Bash-Aufruf
    macht. In beiden Faellen liefert die Attrappe fuer ``shell ls -la`` eine
    feste Liste und fuer ``pull`` einen erfundenen Dateiinhalt.
    """
    skript = tmp_path / "attrappe-adb"
    skript.write_text(
        "#!/usr/bin/env bash\n"
        "# Attrappen-adb fuer die Tests: feste Antworten, kein echtes Geraet,\n"
        "# kein Netz. Nur erfundene Inhalte.\n"
        "set -u\n"
        f"ORDNER_ERWARTET='{ORDNER_GERAET}'\n"
        "JOB='JOB_ID_GEFUNDEN=ja'\n"
        "NACH='nachpflege_einrichtung ok'\n"
        f"ANT='{{\"text\":\"{GEHEIM}\"}}'\n"
        "gross() { printf '%s\\n' \"$1\" | wc -c | tr -d ' '; }\n"
        "case \"${1:-}\" in\n"
        "  shell)\n"
        "    ORDNER=\"${4:-}\"\n"
        "    if [ \"$ORDNER\" != \"$ORDNER_ERWARTET\" ]; then\n"
        "      echo \"ls: $ORDNER: No such file or directory\" >&2\n"
        "      exit 1\n"
        "    fi\n"
        "    printf 'total 12\\n'\n"
        "    printf -- '-rw-rw---- 1 u0_a1 u0_a1 %s 2026-09-29 03:00 job_liste.txt\\n'"
        " \"$(gross \"$JOB\")\"\n"
        "    printf -- '-rw-rw---- 1 u0_a1 u0_a1 %s 2026-09-29 03:00 "
        "nachpflege_letzte.txt\\n' \"$(gross \"$NACH\")\"\n"
        "    printf -- '-rw-rw---- 1 u0_a1 u0_a1 %s 2026-09-29 03:00 "
        "antworten_letzte.jsonl\\n' \"$(gross \"$ANT\")\"\n"
        "    exit 0\n"
        "    ;;\n"
        "  pull)\n"
        "    QUELLE=\"${2:-}\"; ZIEL=\"${3:-}\"\n"
        "    case \"$QUELLE\" in\n"
        "      *job_liste.txt) printf '%s\\n' \"$JOB\" > \"$ZIEL\" ;;\n"
        "      *nachpflege_letzte.txt) printf '%s\\n' \"$NACH\" > \"$ZIEL\" ;;\n"
        "      *antworten_letzte.jsonl) printf '%s\\n' \"$ANT\" > \"$ZIEL\" ;;\n"
        "      *) : > \"$ZIEL\" ;;\n"
        "    esac\n"
        "    exit 0\n"
        "    ;;\n"
        "esac\n"
        "exit 2\n",
        encoding="utf-8")

    bash = shutil.which("bash")
    assert bash, "bash wird fuer die Attrappen-adb gebraucht"
    if os.name != "nt":
        skript.chmod(0o755)
        return str(skript)

    umweg = tmp_path / "attrappe-adb.cmd"
    umweg.write_text(
        "@echo off\r\n"
        f'"{bash}" "%~dp0attrappe-adb" %*\r\n',
        encoding="ascii")
    return str(umweg)


def _lauf(argv: list):
    """``main`` aufrufen und Exit-Code + Ausgabe einsammeln (ohne echten adb)."""
    import io
    import contextlib
    puffer = io.StringIO()
    fehler = io.StringIO()
    with contextlib.redirect_stdout(puffer), contextlib.redirect_stderr(fehler):
        code = dh.main(argv)
    return code, puffer.getvalue(), fehler.getvalue()


# ── 1. Startskript-Block ───────────────────────────────────────────────────

def test_regel1_beleg_block_schreibt_job_liste_und_einricht_datei():
    abschnitt = _beleg_abschnitt()
    assert "job_liste.txt" in abschnitt
    assert "nachpflege_einrichtung_letzte.txt" in abschnitt
    assert "nachpflege-einrichten.log" in abschnitt, "Quelle des Einricht-Logs fehlt"
    assert "tail -n 20" in abschnitt, "die letzten 20 Log-Zeilen gehoeren dazu"


def test_regel1_beleg_block_nutzt_job_scheduler_liste_mit_waechter():
    abschnitt = _beleg_abschnitt()
    assert "termux-job-scheduler --list" in abschnitt
    assert "command -v termux-job-scheduler" in abschnitt, "Waechter fehlt"


def test_regel1_beleg_block_legt_hermes_diag_an():
    abschnitt = _beleg_abschnitt()
    assert 'mkdir -p "$DIAG"' in abschnitt, "der neue Block legt $DIAG selbst an"
    # Ehrliche Zeile statt Abbruch, wenn das Anlegen scheitert.
    assert "2>/dev/null" in abschnitt
    assert "exit" not in abschnitt, "der Beleg-Block darf den Start nicht abbrechen"


def test_regel1_job_id_zeilen_vorhanden():
    abschnitt = _beleg_abschnitt()
    assert "JOB_ID_GEFUNDEN=" in abschnitt
    assert "JOB_ID_ERWARTET=" in abschnitt
    # Alle drei Auspraegungen der Beleg-Zeile sind genannt.
    for wert in ("ja", "nein", "unbekannt"):
        assert f"JOB_ID_GEFUNDEN={wert}" in abschnitt, f"{wert} fehlt"


# ── 2. Verbotene Muster ────────────────────────────────────────────────────

def test_regel2_verbotene_muster_im_startskript():
    text = _text(STARTTERMUX)
    for muster in ("rm -rf", "deletefile", "deletefolder", "--force",
                   "curl", "wget"):
        assert muster not in text, f"{muster!r} ist im Startskript verboten"


# ── 3. Kein Auseinanderlaufen der JOB_ID ───────────────────────────────────

def test_regel3_job_id_stimmt_zwischen_einrichten_und_startskript():
    einrichten = re.search(r"^JOB_ID=(\d+)\s*$", _text(EINRICHTEN),
                           re.MULTILINE)
    assert einrichten is not None, "feste JOB_ID in nachpflege-einrichten.sh fehlt"
    start = re.search(r"^JOB_ID_ERWARTET=(\d+)\s*$", _text(STARTTERMUX),
                      re.MULTILINE)
    assert start is not None, "JOB_ID_ERWARTET im Startskript fehlt"
    assert start.group(1) == einrichten.group(1), \
        f"JOB_ID laeuft auseinander: {einrichten.group(1)} vs {start.group(1)}"


# ── 4. Reihenfolge im Startskript ──────────────────────────────────────────

def test_regel4_beleg_block_nach_diag_bestimmung():
    code = _ohne_kommentare(_text(STARTTERMUX))
    diag = code.index('DIAG_BASIS=')            # Bestimmung von $DIAG
    block = code.index("JOB_ID_ERWARTET=")
    assert diag < block, "der Beleg-Block muss nach der $DIAG-Bestimmung stehen"


def test_regel4_beleg_block_nach_nachpflege_einrichten_aufruf():
    code = _ohne_kommentare(_text(STARTTERMUX))
    aufruf = code.index("nachpflege-einrichten.sh")
    block = code.index("JOB_ID_ERWARTET=")
    assert aufruf < block, \
        "der Beleg-Block muss nach dem nachpflege-einrichten.sh-Aufruf stehen"


# ── 5. Syntaxpruefung mit bash -n ──────────────────────────────────────────

def test_regel5_bash_syntaxpruefung_startskript():
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash nicht vorhanden")
    ziel = str(STARTTERMUX).replace("\\", "/")
    ergebnis = subprocess.run([bash, "-n", ziel], capture_output=True, text=True)
    assert ergebnis.returncode == 0, f"bash -n scheiterte:\n{ergebnis.stderr}"


# ── 6. Werkzeug offline gegen eine Attrappen-adb ───────────────────────────

def test_regel6_trockenlauf_schreibt_nichts(tmp_path):
    attrappe = _attrappen_adb(tmp_path)
    ziel = tmp_path / "ziel"
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--ordner", ORDNER_GERAET])
    assert code == 0
    assert not ziel.exists(), "der Trockenlauf darf nichts anlegen"
    assert "job_liste.txt" in aus and "antworten_letzte.jsonl" in aus
    assert "Trockenlauf" in aus


def test_regel6_holen_holt_und_zweiter_lauf_ueberspringt(tmp_path):
    attrappe = _attrappen_adb(tmp_path)
    ziel = tmp_path / "ziel"
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--ordner", ORDNER_GERAET, "--holen"])
    assert code == 0, aus
    assert (ziel / "job_liste.txt").is_file()
    assert (ziel / "nachpflege_letzte.txt").is_file()
    assert (ziel / "antworten_letzte.jsonl").is_file()

    # Zweiter Lauf: gleiche Groesse -> nichts mehr laden.
    code2, aus2, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                            "--ordner", ORDNER_GERAET, "--holen"])
    assert code2 == 0
    assert "uebersprungen" in aus2
    assert "geholt 0" in aus2, "beim zweiten Lauf darf nichts geholt werden"


def test_regel6_privatinhalt_erscheint_nicht_im_bericht(tmp_path):
    attrappe = _attrappen_adb(tmp_path)
    ziel = tmp_path / "ziel"
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--ordner", ORDNER_GERAET, "--holen"])
    assert code == 0
    # Der Platzhalter steht in der Attrappen-antworten_letzte.jsonl, die Datei
    # wurde geholt — ihr INHALT darf trotzdem nirgends im Bericht stehen.
    assert (ziel / "antworten_letzte.jsonl").is_file()
    assert GEHEIM not in aus, "privater Inhalt darf nicht im Bericht erscheinen"
    # Nur die beiden technischen Berichte zeigen Inhalt.
    assert "job_1901_belegt=ja" in aus
    assert "antworten_letzte.jsonl: geholt" in aus, "Name+Groesse gehoeren dazu"


def test_regel6_ziel_im_repo_gibt_exit_2(tmp_path):
    attrappe = _attrappen_adb(tmp_path)
    ziel = REPO / "handy_diag_probe_verboten"
    code, _, fehler = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                             "--ordner", ORDNER_GERAET, "--holen"])
    assert code == 2, f"Repo-Ziel muss Exit 2 geben (war {code})"
    assert "IM Repo" in fehler
    assert not ziel.exists(), "bei Schutzfehler darf nichts angelegt werden"


def test_regel6_fehlender_geraeteordner(tmp_path):
    attrappe = _attrappen_adb(tmp_path)
    ziel = tmp_path / "ziel"
    # Trockenlauf: ehrliche Zeile, aber Exit 0.
    code, aus, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                          "--ordner", "/sdcard/Download/gibt_es_nicht"])
    assert code == 0
    assert "nicht vorhanden" in aus
    assert not ziel.exists()
    # --holen: fehlender Ordner ist ein Fehler -> Exit 1.
    code2, _, _ = _lauf(["--adb", attrappe, "--ziel", str(ziel),
                         "--ordner", "/sdcard/Download/gibt_es_nicht", "--holen"])
    assert code2 == 1


# ── 7. Datenschutz ─────────────────────────────────────────────────────────

def test_regel7_keine_echten_namen_in_den_neuen_dateien():
    # Nur die NEUE Datei wird geprueft: ``start-termux.sh`` nennt in einem
    # BESTEHENDEN Kommentar bereits einen echten Vornamen — der Auftrag verlangt
    # ausdruecklich, dort nur einzufuegen und nichts umzuformulieren.
    text = _text(WERKZEUG)
    for name in VERBOTENE_NAMEN:
        assert name not in text, f"{name!r} darf in diag_holen.py nicht vorkommen"


def test_regel7_keine_geheimnismuster():
    verboten = "Bea" + "rer "                 # getrennt, sonst prueft sich der Test selbst
    for pfad in (STARTTERMUX, WERKZEUG, Path(__file__)):
        text = _text(pfad)
        assert verboten not in text, f"Bearer-Muster in {pfad.name}"
        assert re.search(r"sk-[A-Za-z0-9-]{20,}", text) is None, \
            f"Schluessel-Muster in {pfad.name}"
        assert re.search(r"\d{30,}", text) is None, \
            f"lange Ziffernfolge in {pfad.name}"


# ── 8. Kein Netz, kein echtes Geraet ───────────────────────────────────────

def test_regel8_werkzeug_ohne_netz():
    text = _text(WERKZEUG)
    for muster in ("http", "pcloud", "requests", "urllib", "socket"):
        assert muster not in text.lower(), f"{muster!r} hat im Werkzeug nichts zu suchen"


def test_regel8_tests_nutzen_nur_die_attrappen_adb():
    eigen = _text(Path(__file__))
    # Jeder Werkzeug-Aufruf geht ueber den Attrappen-Pfad.
    assert eigen.count("_lauf(") >= 5
    assert '"--adb"' in eigen
    assert "adb " + "devices" not in eigen, "kein echter adb-Aufruf in den Tests"
