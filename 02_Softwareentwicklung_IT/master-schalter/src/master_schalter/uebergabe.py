"""Übergabepaket: eine Markdown-Datei mit technischen Metadaten für den neuen Master.

Das Paket liegt unter `<repo>/.hermes/uebergabe/` (gitignored) und enthält vier Abschnitte
(Stand, Offen, Plan, Hinweise). In v0.2 steht **kein Dateiinhalt** darin: nur Commit-Kurzzeilen,
Dateinamen aus `git status`, Pfade und Änderungszeiten technisch eingeordneter Pläne und der
Hinweistext des abgebenden Masters. Pläne erscheinen nur per Positivliste – eine ihrer ersten
20 Zeilen muss genau mit `Einordnung: technisch` beginnen.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable

MARKER = "Einordnung: technisch"
MARKER_ZEILEN = 20
MAX_PLAENE = 3
MAX_STATUS = 50
GESPERRTER_ORDNER = "Chats von GPT, GEMINI, Claude"
KEINE_PLANLISTE = "Keine repo-weite Planliste; laufende Übergabe siehe Hinweise."

Git = Callable[[Path, list[str]], str]


class UebergabeFehler(Exception):
    """Paket konnte nicht gebaut oder geschrieben werden."""


class GitFehler(Exception):
    """Git lieferte einen Fehler."""


def _hat_git(ordner: Path) -> bool:
    return (ordner / ".git").exists()


def repo_wurzel(quelle: Path | None = None) -> Path:
    """Repo-Wurzel: `MASTER_SCHALTER_REPO`, sonst erster Elternordner der Quelldatei mit `.git`.

    Die Suche geht von der Quelldatei aus, nicht vom Arbeitsordner (pythonw startet überall).
    """
    eigen = os.environ.get("MASTER_SCHALTER_REPO")
    if eigen:
        pfad = Path(eigen)
        if not pfad.is_dir():
            raise UebergabeFehler(f"Repo nicht gefunden: MASTER_SCHALTER_REPO={eigen} ist kein Ordner")
        return pfad
    start = (quelle or Path(__file__)).resolve()
    for ordner in start.parents:
        if _hat_git(ordner):
            return ordner
    raise UebergabeFehler("Repo nicht gefunden (kein Elternordner mit .git, MASTER_SCHALTER_REPO nicht gesetzt)")


def haupt_wurzel(repo: Path) -> Path:
    """Hauptarbeitsbaum zu `repo`: in einem Git-Worktree ist `.git` eine Datei, die über `commondir` dorthin zeigt.

    `.hermes/` ist gitignored und liegt nur im Hauptarbeitsbaum. Gleiche Auflösung wie `pruefkreis.haupt_repo`
    (ohne Git-Aufruf); bei jedem Lesefehler bleibt es bei `repo`. Nur lesend genutzt (`kurz`).
    """
    verweis = repo / ".git"
    if not verweis.is_file():
        return repo
    try:
        zeile = verweis.read_text(encoding="utf-8").strip()
        if not zeile.startswith("gitdir:"):
            return repo
        gitdir = Path(zeile[len("gitdir:"):].strip())
        if not gitdir.is_absolute():
            gitdir = repo / gitdir
        common = (gitdir / (gitdir / "commondir").read_text(encoding="utf-8").strip()).resolve()
    except OSError:
        return repo
    return common.parent if common.name == ".git" else repo


def _git(repo: Path, args: list[str]) -> str:
    try:
        lauf = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=repo, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError) as fehler:
        raise GitFehler(str(fehler)) from fehler
    if lauf.returncode != 0:
        raise GitFehler(f"git {args[0]}: Rückgabewert {lauf.returncode}")
    return lauf.stdout


def _zeit(sekunden: float) -> str:
    return datetime.fromtimestamp(sekunden).astimezone().strftime("%d.%m.%Y %H:%M")


def _ist_technisch(datei: Path) -> bool:
    try:
        with datei.open(encoding="utf-8", errors="replace") as f:
            for _, zeile in zip(range(MARKER_ZEILEN), f):
                if zeile.startswith(MARKER):
                    return True
    except OSError:
        pass
    return False


def _plaene(repo: Path) -> tuple[list[tuple[float, Path]], int]:
    """(technisch eingeordnete Pläne, neueste zuerst; Anzahl der übrigen Pläne)."""
    ordner = repo / ".hermes" / "plans"
    technisch: list[tuple[float, Path]] = []
    uebrige = 0
    try:
        kandidaten = [p for p in ordner.glob("*.md") if p.is_file()]
    except OSError:
        return [], 0
    for datei in kandidaten:
        try:
            mtime = datei.stat().st_mtime
        except OSError:
            continue
        if _ist_technisch(datei):
            technisch.append((mtime, datei))
        else:
            uebrige += 1
    technisch.sort(key=lambda e: (e[0], e[1].name), reverse=True)
    return technisch, uebrige


def _stand(repo: Path, git: Git) -> list[str]:
    zeilen = ["## Stand", ""]
    try:
        log = [z for z in git(repo, ["log", "--oneline", "-5"]).splitlines() if z.strip()]
        status = [z for z in git(repo, ["status", "--short"]).splitlines() if z.strip()]
    except (GitFehler, OSError):
        return zeilen + ["git nicht lesbar – Commits und Dateistand fehlen.", ""]
    zeilen.append("Letzte Commits (`git log --oneline -5`):")
    zeilen += [f"- {z}" for z in log] or ["- keine"]
    gesperrt = [z for z in status if GESPERRTER_ORDNER in z]
    status = [z for z in status if GESPERRTER_ORDNER not in z]
    zeilen += ["", "Uncommittete Dateien (`git status --short`, nur Namen):"]
    zeilen += [f"- {z}" for z in status[:MAX_STATUS]] or ["- keine"]
    if len(status) > MAX_STATUS:
        zeilen.append(f"- … und {len(status) - MAX_STATUS} weitere")
    if gesperrt:
        n = len(gesperrt)
        zeilen.append(f"- {n} Pfad{'e' if n != 1 else ''} aus gesperrtem Archivordner nicht aufgeführt")
    return zeilen + [""]


def _stand_minimal(repo: Path, git: Git, jetzt: datetime) -> list[str]:
    """Stand **ohne** Repo-Freitext: nur Zeitpunkt, HEAD, Zählwerte – keine Betreffzeilen, keine Dateinamen."""
    zeilen = ["## Stand", ""]
    try:
        kurz = git(repo, ["rev-parse", "--short", "HEAD"]).strip()
        anzahl = git(repo, ["rev-list", "--count", "HEAD"]).strip()
        status = [z for z in git(repo, ["status", "--short"]).splitlines() if z.strip()]
    except (GitFehler, OSError):
        return zeilen + ["git nicht lesbar – Git-Metadaten fehlen.", ""]
    gesperrt = [z for z in status if GESPERRTER_ORDNER in z]
    offen = len(status) - len(gesperrt)
    zeilen.append(f"Zeitpunkt: {jetzt.strftime('%d.%m.%Y %H:%M:%S')}")
    zeilen.append(f"HEAD: {kurz or '?'} · Commits: {anzahl or '?'}")
    zeilen.append(f"Uncommittete Pfade: {offen} (nur Anzahl, keine Dateinamen)")
    if gesperrt:
        n = len(gesperrt)
        zeilen.append(f"{n} Pfad{'e' if n != 1 else ''} aus gesperrtem Archivordner nicht gezählt")
    return zeilen + [""]


def _offen_hinweis() -> list[str]:
    return ["## Offen", "", KEINE_PLANLISTE, ""]


def _plan_hinweis() -> list[str]:
    return ["## Plan", "", KEINE_PLANLISTE, ""]


def _offen(repo: Path, technisch: list[tuple[float, Path]], uebrige: int) -> list[str]:
    zeilen = ["## Offen", "", f"Technisch eingeordnete Pläne (`{MARKER}` in den ersten {MARKER_ZEILEN} Zeilen), "
                              f"zuletzt geändert:"]
    for mtime, datei in technisch[:MAX_PLAENE]:
        zeilen.append(f"- `{datei.relative_to(repo).as_posix()}` (geändert {_zeit(mtime)})")
    if not technisch:
        zeilen.append("- kein technisch eingeordneter Plan gefunden")
    if len(technisch) > MAX_PLAENE:
        zeilen.append(f"- {len(technisch) - MAX_PLAENE} ältere technische Pläne nicht aufgeführt")
    if uebrige:
        zeilen.append(f"- {uebrige} weitere Pläne nicht aufgeführt – nicht als technisch eingeordnet")
    return zeilen + [""]


def _plan(repo: Path, technisch: list[tuple[float, Path]]) -> list[str]:
    zeilen = ["## Plan", ""]
    if technisch:
        zeilen.append(f"Neuester technischer Plan: `{technisch[0][1].relative_to(repo).as_posix()}`")
    else:
        zeilen.append("kein technisch eingeordneter Plan")
    return zeilen + [""]


def paket_bauen(von: str, nach: str, hinweis: str | None, repo: Path | None = None,
                jetzt: datetime | None = None, git: Git | None = None, *,
                plaene: bool = True, minimal: bool = False) -> Path:
    """Schreibt das Paket und gibt seinen Pfad zurück; ein vorhandenes Paket wird nie überschrieben.

    Die ersten sechs Argumente bleiben unverändert (v0.2-Aufrufe behalten ihr Verhalten). Die
    benannten Schalter betreffen nur den Automatikweg:

    * `minimal=True`: Der Abschnitt „Stand" enthält **keinen** Repo-Freitext – keine
      Commit-Betreffzeilen, keine Dateinamen. Stattdessen Zeitpunkt, HEAD-Kurzform, Anzahl
      Commits und die **Anzahl** uncommitteter Pfade (der Zähler für den gesperrten Ordner bleibt).
    * `plaene=False`: `_plaene` wird **gar nicht** aufgerufen – keine Plan-Datei geöffnet oder
      aufgelistet. „Offen" und „Plan" enthalten nur den festen Hinweis auf die laufende Übergabe.
    """
    repo = repo or repo_wurzel()
    jetzt = jetzt or datetime.now().astimezone()
    git = git or _git
    if plaene:
        technisch, uebrige = _plaene(repo)
        stand = _stand_minimal(repo, git, jetzt) if minimal else _stand(repo, git)
        offen, plan = _offen(repo, technisch, uebrige), _plan(repo, technisch)
        umfang = "Umfang: nur technische Metadaten (Commits, Dateinamen, Planpfade), kein Dateiinhalt."
    else:
        stand = _stand_minimal(repo, git, jetzt) if minimal else _stand(repo, git)
        offen, plan = _offen_hinweis(), _plan_hinweis()
        umfang = ("Umfang: nur Git-Metadaten (Zeitpunkt, HEAD, Zählwerte) – keine Betreffzeilen, "
                  "keine Dateinamen, kein Dateiinhalt.")
    text = "\n".join([
        f"# Masterwechsel {von} → {nach}", "",
        f"Zeit: {jetzt.strftime('%d.%m.%Y %H:%M:%S')}",
        umfang, "",
        *stand,
        *offen,
        *plan,
        "## Hinweise", "", (hinweis or "").strip() or "—", "",
    ])
    ordner = repo / ".hermes" / "uebergabe"
    basis = f"{jetzt:%Y-%m-%d_%H%M%S}_masterwechsel-{von}-{nach}"
    try:
        ordner.mkdir(parents=True, exist_ok=True)
        zaehler = 1
        while True:
            pfad = ordner / (f"{basis}.md" if zaehler == 1 else f"{basis}-{zaehler}.md")
            try:
                f = pfad.open("x", encoding="utf-8")
            except FileExistsError:
                zaehler += 1
                continue
            break
        try:
            with f:
                f.write(text)
        except BaseException:
            pfad.unlink(missing_ok=True)   # nur die eben selbst angelegte, halb geschriebene Datei
            raise
    except OSError as fehler:
        raise UebergabeFehler(f"Paket nicht geschrieben: {fehler}") from fehler
    return pfad
