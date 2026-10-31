"""Tor mit Sperre und selektivem Testlauf: fuehrt den Pruefbefehl aus, aber nur einer zur Zeit.

Warum: mehrere Agenten (Hermes, Claude Code, Nachtlauf) teilen sich einen
Arbeitsbaum. Laufen zwei Test-Serien gleichzeitig, schreiben Tests
Laufzeitdateien neu (z. B. auftraege.json ueber .tmp) und die Dateibaum-Pruefungen
schlagen fehl - das Tor wird rot, obwohl der Code in Ordnung ist.

Best Practice (31.10.2026):
  * Selektiver Testlauf: Aenderungen an einzelnen Modulen/Services testen nur die
    zugehoerigen Testdateien (Laufzeit < 5 s statt 39 Minuten!).
  * Parallelisierung: Bei Gesamttests nutzt pytest -n auto alle CPU-Kerne.
  * Uebersteuern: `--alle` erzwingt die vollstaendige Suite; gezielte Pfade
    koennen direkt uebergeben werden: `tor.py tests/test_gruppen_quiz.py`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parent
REPO = HIER.parents[1]                      # .../personal_ai_agent
BACKEND = REPO / "backend"
TESTS_DIR = BACKEND / "tests"
PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
WORKSPACE_ROOT = REPO.parents[1]
SPERRE = WORKSPACE_ROOT / ".git" / "tor.lock"   # Workspace-Wurzel/.git/tor.lock
TOT_NACH = 3600                              # aeltere Sperre gilt als tot

# Dateien, deren Aenderung die gesamte Testsuite erzwingt
KERN_DATEIEN = {
    "app/config.py",
    "app/main.py",
    "app/sicherheit.py",
    "app/models.py",
    "conftest.py",
    "pytest.ini",
}


def _lebt(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, SystemError):
        # Windows: fuer eine tote PID wirft os.kill(pid, 0) je nach Lage OSError
        # (WinError 87) ODER SystemError ("returned a result with an exception
        # set"). Beides heisst: der Prozess lebt nicht.
        return False


def sperre_holen(wartezeit: int) -> bool:
    ende = time.time() + wartezeit
    while True:
        try:
            fd = os.open(SPERRE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            inhalt = {}
            try:
                inhalt = json.loads(SPERRE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
            pid = int(inhalt.get("pid") or 0)
            alter = time.time() - float(inhalt.get("zeit") or 0)
            if not _lebt(pid) or alter > TOT_NACH:
                print(f"[Tor] tote Sperre von PID {pid} ({alter:.0f} s alt) - uebernehmen", flush=True)
                try:
                    SPERRE.unlink()
                except OSError:
                    pass
                continue
            if time.time() >= ende:
                print(f"[Tor] Zeit abgelaufen: PID {pid} testet seit {alter:.0f} s", flush=True)
                return False
            print(f"[Tor] warte auf laufendes Tor (PID {pid}, {alter:.0f} s)", flush=True)
            time.sleep(10)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"pid": os.getpid(), "zeit": time.time(),
                       "rechner": os.environ.get("COMPUTERNAME", ""),
                       "wer": os.environ.get("TOR_WER", "")}, fh)
        return True


def sperre_freigeben() -> None:
    try:
        daten = json.loads(SPERRE.read_text(encoding="utf-8"))
        if int(daten.get("pid") or 0) == os.getpid():
            SPERRE.unlink()
    except (OSError, json.JSONDecodeError):
        pass


def hat_xdist() -> bool:
    """Prueft, ob pytest-xdist fuer Parallelisierung installiert ist."""
    try:
        import xdist  # noqa: F401
        return True
    except ImportError:
        return False


def geaenderte_git_dateien() -> list[str]:
    """Liest geaenderte Dateien aus dem Git-Index (staged) oder Working Tree."""
    try:
        res = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                             cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, check=False)
        dateien = [z.strip() for z in res.stdout.splitlines() if z.strip()]
        if not dateien:
            res = subprocess.run(["git", "diff", "HEAD", "--name-only", "--diff-filter=ACMR"],
                                 cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, check=False)
            dateien = [z.strip() for z in res.stdout.splitlines() if z.strip()]
        return dateien
    except Exception:
        return []


def finde_relevante_tests(geaenderte_dateien: list[str]) -> list[str]:
    """Ermittelt anhand geaenderter Dateien gezielt die auszufuehrenden Testdateien.

    Gibt eine Liste von relativen Pfaden (z. B. ['tests/test_gruppen_quiz.py']) zurueck.
    Faellt bei Kern-Aenderungen oder unbekannten Pfaden sicher auf ['tests/'] zurueck.
    """
    if not geaenderte_dateien:
        return ["tests/"]

    alle_tests = [f.name for f in TESTS_DIR.glob("test_*.py")] if TESTS_DIR.exists() else []
    gefundene_tests: set[str] = set()

    for datei in geaenderte_dateien:
        d = datei.replace("\\", "/")

        # 1. Pruefung: Kern-Infrastruktur -> sofort die gesamte Testsuite erzwingen
        for kern in KERN_DATEIEN:
            if d.endswith(kern) or f"/{kern}" in d:
                return ["tests/"]

        # 2. Pruefung: Direkte Testdatei in tests/ oder Tor-Tool
        if "tools/gate/tor.py" in d:
            gefundene_tests.add("tests/test_tor.py")
            continue
        if "/tests/test_" in d or d.startswith("tests/test_"):
            m = re.search(r"tests/(test_[a-zA-Z0-9_]+\.py)$", d)
            if m:
                gefundene_tests.add(f"tests/{m.group(1)}")
                continue

        # 3. Pruefung: Backend-Code in app/router oder app/services
        m_app = re.search(r"backend/app/(router|services)/([a-zA-Z0-9_]+)\.py$", d)
        if m_app:
            modul = m_app.group(2)
            # Basisbegriff bilden (z. B. gruppen_quiz -> gruppen, erzaehl_service -> erzaehl)
            basis = modul.replace("_service", "").replace("_router", "")
            # Spezifische Wortstaemme
            teil = basis.split("_")[0] if "_" in basis else basis

            treffer = 0
            for t_name in alle_tests:
                # Exakter Match, Stamm-Start (z. B. erzaehl -> test_erzaehlen) oder Wortstamm
                if (
                    f"test_{modul}.py" == t_name
                    or f"test_{basis}.py" == t_name
                    or t_name.startswith(f"test_{basis}")
                    or (len(teil) >= 4 and t_name.startswith(f"test_{teil}"))
                ):
                    gefundene_tests.add(f"tests/{t_name}")
                    treffer += 1
            if treffer > 0:
                continue

        # 4. Pruefung: Frontend-Code (z. B. frontend/gruppen_quiz.js -> tests/test_gruppen_*)
        m_fe = re.search(r"frontend/([a-zA-Z0-9_]+)\.js$", d)
        if m_fe:
            fe_name = m_fe.group(1)
            fe_basis = fe_name.split("_")[0]
            treffer_fe = 0
            for t_name in alle_tests:
                if f"test_{fe_name}" in t_name or (len(fe_basis) >= 5 and f"test_{fe_basis}_" in t_name):
                    gefundene_tests.add(f"tests/{t_name}")
                    treffer_fe += 1
            if treffer_fe > 0:
                continue

    if gefundene_tests:
        return sorted(gefundene_tests)

    # Sichere Rueckfallebene: Keine spezifische Zuordnung gefunden -> alle Tests
    return ["tests/"]


def pruefen(test_ziele: list[str] | None = None, erzwinge_parallel: bool = False) -> int:
    ziele = test_ziele or ["tests/"]
    befehl = [str(PYTHON), "-m", "pytest"]

    # Parallelisierung mit xdist:
    # Nur bei Gesamttests oder explizitem Wunsch aktivieren, da Einzeltests ohne Overhead schneller sind
    voll_lauf = (ziele == ["tests/"] or len(ziele) > 15)
    if (voll_lauf or erzwinge_parallel) and hat_xdist():
        befehl.extend(["-n", "auto"])

    befehl.extend(ziele)
    befehl.append("-q")

    print(f"[Tor] fuehre aus: {' '.join(befehl)} (in {BACKEND})", flush=True)
    ergebnis = subprocess.run(befehl, cwd=str(BACKEND))
    return ergebnis.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wartezeit", type=int, default=900)
    ap.add_argument("--auch-ohne-sperre", action="store_true",
                    help="nur ausfuehren, nicht sperren (Notfall)")
    ap.add_argument("--alle", action="store_true",
                    help="Gesamte Testsuite erzwingen (keine selektive Auswahl)")
    ap.add_argument("--parallel", action="store_true",
                    help="Parallelisierung (pytest -n auto) erzwingen")
    ap.add_argument("tests", nargs="*",
                    help="Spezifische Testdateien oder -ordner (uebersteuert automatische Erkennung)")
    a = ap.parse_args(argv)

    if not PYTHON.exists():
        print(f"[Tor] Pruefbefehl nicht gefunden: {PYTHON}")
        return 2

    # Testziele bestimmen
    if a.tests:
        ziele = a.tests
        print(f"[Tor] Gezielte Testauswahl: {len(ziele)} Pfad(e) angegeben.")
    elif a.alle or os.environ.get("TOR_ALLE") == "1":
        ziele = ["tests/"]
        print("[Tor] Gesamte Testsuite angefordert (--alle / TOR_ALLE).")
    else:
        dateien = geaenderte_git_dateien()
        ziele = finde_relevante_tests(dateien)
        if ziele == ["tests/"]:
            print("[Tor] Vollstaendiger Testlauf (Kern-Aenderung oder keine selektive Zuordnung).")
        else:
            print(f"[Tor] Selektiver Best-Practice-Lauf: {len(ziele)} Testdatei(en) fuer geaenderte Komponenten:")
            for z in ziele:
                print(f"  * {z}")

    if a.auch_ohne_sperre:
        return pruefen(ziele, a.parallel)
    if not sperre_holen(a.wartezeit):
        return 2
    try:
        return pruefen(ziele, a.parallel)
    finally:
        sperre_freigeben()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
