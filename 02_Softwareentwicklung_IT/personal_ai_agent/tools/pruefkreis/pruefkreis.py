"""pruefkreis - automatische Gegenpruefung durch Codex oder Hermes.

Der Master (Claude Code oder Codex) schreibt einen Plan oder ein Ergebnis als
Datei und ruft ``pruefen`` auf. Das Werkzeug startet einen FRISCHEN Prueflauf,
liest das Urteil, haengt die Runde an das Diskussionsprotokoll an und gibt
dieselbe Runde fuer den Master-Chat aus. Der Nutzer liest nur mit.

Plan und Pruefjournal: ``.hermes/plans/2026-10-12_hermes-auftraege-statt-bus.md``
(Schritt 1). Rollen: Abschnitt "Rollen und Datenschutz" in ``AGENTS.md``.

Regeln, die hier fest eingebaut sind:
* ``--sensibel`` => Pruefer ist IMMER Hermes; Codex wird verweigert.
* Der Pruefer muss als letzte Zeile ``URTEIL: FREI`` oder ``URTEIL: EINWAND``
  schreiben. Fehlt sie, scheitert der Lauf oder laeuft er in die Zeitgrenze,
  ist der Status ``fehler`` - nie ``frei``.
* Bei ``--sensibel`` gelangt bis zum Datenschutz-Tor (Schritt 2) nur die
  Urteilszeile in die Ausgabe; die Begruendung bleibt in der Hermes-Sitzung.

Codex laeuft ueber das Programm der Codex-App (``%LOCALAPPDATA%\\OpenAI\\Codex\\
bin\\<Kennung>\\codex.exe``, neueste Kennung): die npm-CLI 0.145 scheitert an der
Sandbox der App und kennt ``gpt-6.1-sol`` nicht (gemessen 12.10.2026).

Aufruf::

    python pruefkreis.py pruefen --vorlage <datei> --thema <kennung>
        [--pruefer codex|hermes] [--sensibel] [--gruendlich] [--zeitgrenze 900]

Exit-Code: 0 = FREI, 1 = EINWAND, 2 = Fehler (Lauf, Urteilszeile, Aufruf).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERMES_MODELL = "deepseek/deepseek-v4.1-flash"
CODEX_GRUENDLICH_MODELL = "gpt-6-astra"
ZEITGRENZE_STANDARD = 900
URTEIL_MUSTER = re.compile(r"^URTEIL:\s*(FREI|EINWAND)\s*$")
THEMA_MUSTER = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")


class PruefkreisFehler(Exception):
    """Aufruf ist nicht zulaessig (z. B. sensibel + Codex, fehlende Vorlage)."""


def protokoll_ordner() -> Path:
    return Path(os.environ.get("PRUEFKREIS_DIR") or REPO / ".hermes" / "pruefkreis")


def codex_programm() -> str | None:
    """Neuestes codex.exe der Codex-App (die Kennung wechselt mit App-Updates)."""
    if os.environ.get("PRUEFKREIS_CODEX"):
        return os.environ["PRUEFKREIS_CODEX"]
    basis = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    treffer = sorted(basis.glob("*/codex.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(treffer[0]) if treffer else None


def hermes_programm() -> str | None:
    if os.environ.get("PRUEFKREIS_HERMES"):
        return os.environ["PRUEFKREIS_HERMES"]
    for name in ("hermes.exe", "hermes"):
        kandidat = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "bin" / name
        if kandidat.is_file():
            return str(kandidat)
    return shutil.which("hermes")


def pruefer_waehlen(pruefer: str | None, sensibel: bool) -> str:
    if sensibel:
        if pruefer == "codex":
            raise PruefkreisFehler("Sensible Inhalte prueft ausschliesslich Hermes (AGENTS.md) - Codex verweigert.")
        return "hermes"
    if pruefer not in (None, "codex", "hermes"):
        raise PruefkreisFehler(f"Unbekannter Pruefer: {pruefer}")
    return pruefer or "codex"


def urteil_lesen(text: str) -> str | None:
    """'frei' / 'einwand' aus der LETZTEN nichtleeren Zeile - sonst None."""
    zeilen = [z.strip() for z in (text or "").splitlines() if z.strip()]
    if not zeilen:
        return None
    treffer = URTEIL_MUSTER.match(zeilen[-1])
    return treffer.group(1).lower() if treffer else None


def naechste_runde(thema: str) -> int:
    datei = protokoll_ordner() / f"{thema}.md"
    if not datei.is_file():
        return 1
    return datei.read_text(encoding="utf-8").count("\n## Runde ") + 1


def auftrag_text(vorlage: str, runde: int, sensibel: bool) -> str:
    teile = [
        "Rolle: Du bist PRUEFER, nicht Ausfuehrer (Rollen: Abschnitt 'Rollen und Datenschutz' in AGENTS.md).",
        f"Pruefrunde {runde}: Pruefe kritisch die Datei {vorlage}.",
        "Wenn sie ein Pruefjournal hat: pruefe je frueherem Einwand, ob er erledigt ist.",
        "Verifiziere Behauptungen selbst am Code und belege jeden Einwand mit Datei:Zeile.",
        "Keine neuen Wuensche ohne konkreten Fehler. NUR LESEN: nichts schreiben, aendern, loeschen oder starten.",
        "Antworte auf Deutsch, knapp, hoechstens 35 Zeilen.",
    ]
    if sensibel:
        teile.append("Die Datei kann sensible Inhalte betreffen: zitiere keine persoenlichen Inhalte.")
    teile.append("Letzte Zeile exakt 'URTEIL: FREI' oder 'URTEIL: EINWAND'.")
    return " ".join(teile)


def befehl_codex(programm: str, auftrag: str, ausgabe: Path, gruendlich: bool) -> list[str]:
    befehl = [programm, "exec", "--ephemeral", "-s", "read-only", "-o", str(ausgabe)]
    befehl += ["-m", CODEX_GRUENDLICH_MODELL] if gruendlich else ["-c", "model_reasoning_effort=high"]
    return befehl + [auftrag]


def befehl_hermes(programm: str, auftrag: str, nutzung: Path) -> list[str]:
    return [programm, "-z", auftrag, "-m", HERMES_MODELL, "--usage-file", str(nutzung),
            "-t", "file,todo", "--in", str(REPO)]


def starte(befehl: list[str], zeitgrenze: float) -> tuple[int, str, str]:
    """Pruefer-Prozess starten -> (Exit, stdout, stderr). Zeitgrenze => -1, Startfehler => -2."""
    try:
        lauf = subprocess.run(befehl, cwd=str(REPO), stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=zeitgrenze)
        return lauf.returncode, lauf.stdout or "", lauf.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", ""
    except OSError as fehler:
        return -2, "", str(fehler)


def fehlerzeile(stderr: str) -> str:
    """Letzte Zeile mit 'ERROR' (sonst letzte Zeile) der Fehlerausgabe, gekuerzt - z. B. das Codex-Limit."""
    zeilen = [z.strip() for z in (stderr or "").splitlines() if z.strip()]
    treffer = [z for z in zeilen if "ERROR" in z.upper()] or zeilen
    return treffer[-1][:300] if treffer else ""


def _nutzung_lesen(datei: Path) -> dict:
    try:
        daten = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {"sitzung": daten.get("session_id"), "kosten_usd": daten.get("estimated_cost_usd")}


def protokoll_block(ergebnis: dict) -> str:
    kopf = (f"## Runde {ergebnis['runde']} · {ergebnis['zeit']} · Pruefer {ergebnis['pruefer']}"
            f" · Vorlage `{ergebnis['vorlage']}`")
    zeilen = [kopf, "", f"**Status: {ergebnis['status'].upper()}**"]
    if ergebnis.get("grund"):
        zeilen.append(f"Grund: {ergebnis['grund']}")
    if ergebnis.get("sitzung"):
        zeilen.append(f"Hermes-Sitzung: `{ergebnis['sitzung']}`")
    if ergebnis.get("kosten_usd") is not None:
        zeilen.append(f"Kosten: {ergebnis['kosten_usd']:.4f} USD")
    zeilen += [f"Dauer: {ergebnis['dauer_s']} s", "", ergebnis["ausgabe"].strip() or "(keine Ausgabe)", ""]
    return "\n".join(zeilen)


def pruefen(vorlage: str, thema: str, pruefer: str | None = None, sensibel: bool = False,
            gruendlich: bool = False, zeitgrenze: float = ZEITGRENZE_STANDARD) -> dict:
    if not THEMA_MUSTER.match(thema):
        raise PruefkreisFehler("Thema nur aus a-z, 0-9 und Bindestrich (wird Dateiname).")
    if not (REPO / vorlage).is_file() and not Path(vorlage).is_file():
        raise PruefkreisFehler(f"Vorlage nicht gefunden: {vorlage}")
    wer = pruefer_waehlen(pruefer, sensibel)
    programm = codex_programm() if wer == "codex" else hermes_programm()
    if not programm:
        raise PruefkreisFehler(f"Programm fuer {wer} nicht gefunden.")
    runde = naechste_runde(thema)
    auftrag = auftrag_text(vorlage, runde, sensibel)

    with tempfile.TemporaryDirectory(prefix="pruefkreis-") as tmp:
        ablage = Path(tmp) / ("antwort.md" if wer == "codex" else "nutzung.json")
        befehl = (befehl_codex(programm, auftrag, ablage, gruendlich) if wer == "codex"
                  else befehl_hermes(programm, auftrag, ablage))
        start = time.monotonic()
        exitcode, stdout, stderr = starte(befehl, zeitgrenze)
        dauer = round(time.monotonic() - start, 1)
        if wer == "codex":
            text = ablage.read_text(encoding="utf-8") if ablage.is_file() else stdout
            nutzung = {}
        else:
            text, nutzung = stdout, _nutzung_lesen(ablage)

    urteil = urteil_lesen(text)
    if exitcode == -1:
        status, grund = "fehler", f"Zeitgrenze {zeitgrenze:g} s ueberschritten"
    elif exitcode != 0:
        status, grund = "fehler", f"Pruefer endete mit Exit {exitcode}"
        # Bei sensibel keine Prozessausgabe weitergeben - auch Fehlerzeilen koennten Inhalt tragen.
        if not sensibel and fehlerzeile(stderr):
            grund += f": {fehlerzeile(stderr)}"
    elif urteil is None:
        status, grund = "fehler", "keine Urteilszeile am Ende"
    else:
        status, grund = urteil, ""

    if sensibel:
        sitzung = nutzung.get("sitzung") or "unbekannt"
        ausgabe = (f"URTEIL: {urteil.upper()}" if urteil else "(kein Urteil)") + \
                  f"\n(Begruendung bleibt in der Hermes-Sitzung {sitzung} - sensibel.)"
    else:
        ausgabe = text

    ergebnis = {"runde": runde, "zeit": time.strftime("%Y-%m-%d %H:%M"), "pruefer": wer, "vorlage": vorlage,
                "status": status, "grund": grund, "dauer_s": dauer, "ausgabe": ausgabe, **nutzung}
    ordner = protokoll_ordner()
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / f"{thema}.md"
    if not datei.is_file():
        datei.write_text(f"# Pruefkreis: {thema}\n", encoding="utf-8")
    with datei.open("a", encoding="utf-8") as fh:
        fh.write("\n" + protokoll_block(ergebnis))
    ergebnis["protokoll"] = str(datei)
    return ergebnis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pruefkreis", description="Automatische Gegenpruefung durch Codex oder Hermes")
    unter = parser.add_subparsers(dest="befehl", required=True)
    p = unter.add_parser("pruefen", help="Vorlage frisch pruefen lassen")
    p.add_argument("--vorlage", required=True)
    p.add_argument("--thema", required=True)
    p.add_argument("--pruefer", choices=("codex", "hermes"))
    p.add_argument("--sensibel", action="store_true")
    p.add_argument("--gruendlich", action="store_true", help=f"Codex mit {CODEX_GRUENDLICH_MODELL}")
    p.add_argument("--zeitgrenze", type=float, default=ZEITGRENZE_STANDARD)
    args = parser.parse_args(argv)
    try:
        ergebnis = pruefen(args.vorlage, args.thema, args.pruefer, args.sensibel, args.gruendlich, args.zeitgrenze)
    except PruefkreisFehler as fehler:
        print(f"FEHLER: {fehler}", file=sys.stderr)
        return 2
    print(protokoll_block(ergebnis))
    print(f"Protokoll: {ergebnis['protokoll']}")
    return {"frei": 0, "einwand": 1}.get(ergebnis["status"], 2)


if __name__ == "__main__":
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass
    sys.exit(main())
