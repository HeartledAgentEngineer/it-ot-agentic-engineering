"""Aufträge an eine Claude-Code-Sitzung (v0.5.1): ein Master (Codex, Hermes) beauftragt Claude, z. B. als Prüfer.

Layout: `<datenordner>/auftraege/claude/<kennung>/<auftrag-id>.json` mit genau
`{auftrag, thema, von, datei, zeit}`. Der Auftrag selbst steht **nicht** im Postfach, sondern in der Datei `datei`:
ein repo-relativer Pfad unter `.hermes/` mit Endung `.md`, der beim Einlegen und beim Zustellen existieren muss und
nach `resolve()` nicht aus `.hermes/` herausführt. So bleibt das Postfach klein (höchstens 4 KB) und frei von Inhalten.

Getrennt vom Wechsel-Postfach (`postfach.py`): ein Auftrag gehört zu keinem Wechselvorgang und ändert weder Besitz
noch Profil; die Gültigkeitsregeln G5/G8 des Postfachs bleiben unberührt.

Zustellung wie beim Postfach in zwei Schritten: `vormerken` prüft und liefert die Texte, verschiebt nichts;
`bestaetigen` verschiebt erst nach erfolgreicher Ausgabe nach `erledigt/`. Ungültige Dateien wandern mit Grund nach
`verworfen/`. Nichts wird endgültig gelöscht.

Das Ergebnis legt Claude neben dem Auftrag ab (`<datei ohne .md>-ergebnis-<auftrag-id>.md`, `ergebnis_pfad`) – je
Auftrag eine eigene Datei, damit ein neuer Auftrag zur selben Datei nicht für eine Wiederholung gehalten wird. Die
letzte Zeile ist `ERGEBNIS: FERTIG` oder `ERGEBNIS: BLOCKIERT`.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import modi, paare
from .signale import _atomar_schreiben, daten_ordner

ZIEL = "claude"
VON = ("codex", "hermes")
FELDER = {"auftrag", "thema", "von", "datei", "zeit"}
MAX_BYTES = 4096
MAX_DATEIPFAD = 300
ERLEDIGT, VERWORFEN = "erledigt", "verworfen"
WURZEL_REPO = ".hermes"
LAEUFT = "ERGEBNIS: LÄUFT"
TEXT = ("Auftrag von {von} (Thema {thema}, Auftrag {auftrag}), Pfade im Hauptarbeitsbaum des Repos: "
        "Existiert `{ergebnis}` schon, ist der Auftrag angenommen – nicht erneut beginnen. Sonst lege zuerst "
        "`{ergebnis}` mit der Zeile `" + LAEUFT + " (Auftrag {auftrag})` an, lies dann `{datei}` und bearbeite ihn. "
        "Schreibe das Ergebnis in `{ergebnis}`; die letzte Zeile ist `ERGEBNIS: FERTIG` oder `ERGEBNIS: BLOCKIERT`.")


class AuftragFehler(Exception):
    """Kennung, Thema, Absender oder Auftragsdatei ist nicht zulässig."""


@dataclass(frozen=True)
class Vorgemerkt:
    """Zuzustellender Auftrag samt Datei und gelesenem Rohinhalt für `bestaetigen`."""
    auftrag: str
    text: str
    datei: Path
    roh: dict[str, str]


def wurzel() -> Path:
    return daten_ordner() / "auftraege"


def basis() -> Path:
    """Hauptarbeitsbaum des Repos, auf den sich Auftrags- und Ergebnisdateien beziehen.

    `MASTER_SCHALTER_REPO`, wenn gesetzt; sonst der Elternordner des gemeinsamen git-Ordners
    (`git rev-parse --git-common-dir`) – so finden Aufrufe aus einem Worktree dasselbe `.hermes/` wie der Hook;
    sonst `uebergabe.repo_wurzel()`.
    """
    from . import uebergabe

    if os.environ.get("MASTER_SCHALTER_REPO"):
        return uebergabe.repo_wurzel()
    try:
        lauf = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                              cwd=Path(__file__).parent, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=10)
        if lauf.returncode == 0 and lauf.stdout.strip():
            gemeinsam = Path(lauf.stdout.strip())
            if gemeinsam.name == ".git" and (gemeinsam.parent / WURZEL_REPO).is_dir():
                return gemeinsam.parent
    except (OSError, subprocess.SubprocessError):
        pass
    return uebergabe.repo_wurzel()


def _kennung(wert: object, was: str) -> str:
    if not isinstance(wert, str) or modi.VORGANG_ID_MUSTER.fullmatch(wert) is None:
        raise AuftragFehler(f"{was} unzulässig (erlaubt: {modi.VORGANG_ID_MUSTER.pattern})")
    return wert


def ordner(kennung: str) -> Path:
    """Auftragsordner einer Claude-Sitzung; `resolve()` muss unter der Wurzel liegen (wie G6)."""
    pfad = wurzel() / ZIEL / _kennung(kennung, "Sitzungskennung")
    if not pfad.resolve().is_relative_to(wurzel().resolve()):
        raise AuftragFehler("Auftragsordner liegt außerhalb der Wurzel")
    return pfad


def datei_pruefen(datei: object, repo: Path) -> str:
    """Repo-relativen Pfad der Auftragsdatei prüfen und in `/`-Schreibweise zurückgeben."""
    if not isinstance(datei, str) or not datei or len(datei) > MAX_DATEIPFAD or "\n" in datei:
        raise AuftragFehler("Auftragsdatei fehlt oder ist zu lang")
    rein = PurePosixPath(datei.replace("\\", "/"))
    if rein.is_absolute() or ":" in datei or ".." in rein.parts:
        raise AuftragFehler("Auftragsdatei muss ein repo-relativer Pfad ohne `..` sein")
    if not rein.parts or rein.parts[0] != WURZEL_REPO or rein.suffix != ".md":
        raise AuftragFehler(f"Auftragsdatei muss unter `{WURZEL_REPO}/` liegen und auf `.md` enden")
    repo_voll = repo.resolve()
    hermes_voll = (repo / WURZEL_REPO).resolve()
    voll = (repo / rein).resolve()
    if not hermes_voll.is_relative_to(repo_voll) or not voll.is_relative_to(hermes_voll):
        raise AuftragFehler(f"Auftragsdatei führt aus `{WURZEL_REPO}/` oder dem Repo heraus")
    if not voll.is_file():
        raise AuftragFehler(f"Auftragsdatei nicht gefunden: {rein}")
    return str(rein)


def ergebnis_pfad(datei: str, auftrag_id: str) -> str:
    """`.hermes/x/auftrag.md`, `a-1` → `.hermes/x/auftrag-ergebnis-a-1.md` (je Auftrag eine Datei)."""
    return f"{datei[:-3]}-ergebnis-{auftrag_id}.md"


def text(inhalt: dict[str, str]) -> str:
    return TEXT.format(von=inhalt["von"], thema=inhalt["thema"], auftrag=inhalt["auftrag"],
                       datei=inhalt["datei"], ergebnis=ergebnis_pfad(inhalt["datei"], inhalt["auftrag"]))


def neue_id(jetzt: datetime | None = None) -> str:
    zeit = (jetzt or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"a-{zeit}-{secrets.token_hex(3)}"


def einlegen(kennung: str, thema: str, datei: str, repo: Path, von: str = "codex",
             auftrag_id: str | None = None) -> tuple[str, Path]:
    """Auftrag atomar ablegen; `(Auftrags-ID, Datei)`. Dieselbe ID ergibt höchstens eine Datei (idempotent)."""
    ziel_ordner = ordner(kennung)
    auftrag_id = _kennung(auftrag_id or neue_id(), "Auftragskennung")
    if von not in VON:
        raise AuftragFehler(f"Absender unzulässig (erlaubt: {', '.join(VON)})")
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise AuftragFehler(str(fehler)) from fehler
    datei = datei_pruefen(datei, repo)
    name = f"{auftrag_id}.json"
    for vorhanden in (ziel_ordner / name, ziel_ordner / ERLEDIGT / name, ziel_ordner / VERWORFEN / name):
        if vorhanden.exists():
            return auftrag_id, vorhanden
    inhalt = json.dumps({"auftrag": auftrag_id, "thema": thema, "von": von, "datei": datei,
                         "zeit": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)
    if len(inhalt.encode("utf-8")) > MAX_BYTES:
        raise AuftragFehler(f"Auftrag größer als {MAX_BYTES} Bytes")
    _atomar_schreiben(ziel_ordner / name, inhalt)
    return auftrag_id, ziel_ordner / name


def _lesen(pfad: Path) -> object:
    if pfad.stat().st_size > MAX_BYTES:
        raise ValueError(f"Datei größer als {MAX_BYTES} Bytes")
    return json.loads(pfad.read_text(encoding="utf-8"))


def _pruefen(pfad: Path, roh: object, repo: Path) -> dict[str, str]:
    """Inhalt streng prüfen; wirft `AuftragFehler` mit Grund."""
    if not isinstance(roh, dict) or set(roh) != FELDER or not all(isinstance(v, str) for v in roh.values()):
        raise AuftragFehler("Inhalt ist kein gültiger Auftrag")
    _kennung(roh["auftrag"], "Auftragskennung")
    if pfad.stem != roh["auftrag"]:
        raise AuftragFehler("Auftragskennung passt nicht zum Dateinamen")
    if roh["von"] not in VON:
        raise AuftragFehler("Absender unzulässig")
    try:
        paare.thema_pruefen(roh["thema"])
    except paare.PaarFehler as fehler:
        raise AuftragFehler(str(fehler)) from fehler
    if datei_pruefen(roh["datei"], repo) != roh["datei"]:
        raise AuftragFehler("Auftragsdatei nicht in Normalform")
    return roh


def _verschieben(pfad: Path, unterordner: str, inhalt: dict[str, object]) -> None:
    """Neue Datei unter `unterordner/` schreiben, dann das Original entfernen (Verschieben samt Vermerk)."""
    _atomar_schreiben(pfad.parent / unterordner / pfad.name, json.dumps(inhalt, ensure_ascii=False))
    pfad.unlink(missing_ok=True)


def vormerken(kennung: str, repo: Path) -> list[Vorgemerkt]:
    """Alle zuzustellenden Aufträge einer Sitzung, älteste zuerst; Ungültiges wandert mit Grund nach `verworfen/`."""
    pfad = ordner(kennung)
    if not pfad.is_dir():
        return []
    vorgemerkt: list[Vorgemerkt] = []
    for datei in sorted(pfad.glob("*.json")):
        try:
            roh = _lesen(datei)
        except FileNotFoundError:
            continue                                  # ein zweiter Abholer war schneller
        except (OSError, ValueError):
            _verschieben(datei, VERWORFEN, {"inhalt": None, "grund": "Datei nicht lesbar oder kein JSON"})
            continue
        try:
            inhalt = _pruefen(datei, roh, repo)
        except AuftragFehler as fehler:
            vermerk = dict(roh) if isinstance(roh, dict) else {"inhalt": None}
            _verschieben(datei, VERWORFEN, {**vermerk, "grund": str(fehler)})
            continue
        if (repo / ergebnis_pfad(inhalt["datei"], inhalt["auftrag"])).exists():
            _verschieben(datei, ERLEDIGT, {**inhalt, "grund": "Ergebnis vorhanden – bereits angenommen"})
            continue                                  # Schutz vor doppelter Ausführung (Prüfbefund B2)
        vorgemerkt.append(Vorgemerkt(inhalt["auftrag"], text(inhalt), datei, inhalt))
    return vorgemerkt


def bestaetigen(vorgemerkt: list[Vorgemerkt]) -> list[str]:
    """Nach der Ausgabe: unveränderte Dateien nach `erledigt/` verschieben; gibt die zugestellten IDs zurück."""
    zugestellt = []
    for v in vorgemerkt:
        try:
            if _lesen(v.datei) != v.roh:
                continue                              # geändert oder ersetzt: beim nächsten Ereignis neu entscheiden
            ziel = v.datei.parent / ERLEDIGT / v.datei.name
            ziel.parent.mkdir(parents=True, exist_ok=True)
            os.replace(v.datei, ziel)
        except (OSError, ValueError):
            continue                                  # liegen lassen: lieber doppelt als verloren
        zugestellt.append(v.auftrag)
    return zugestellt
