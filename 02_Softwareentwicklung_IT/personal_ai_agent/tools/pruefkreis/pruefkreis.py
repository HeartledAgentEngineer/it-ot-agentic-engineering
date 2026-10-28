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
        [--pruefer codex|hermes] [--master claude|codex|hermes] [--sensibel] [--gruendlich] [--zeitgrenze 900]

``--master`` nennt den Master des geprueften Themas. Codex prueft nie die Arbeit eines Codex-Masters
(AGENTS.md: Pruefer aus einer anderen Modellfamilie als der Master): ohne ``--pruefer`` wird dann Hermes
gewaehlt, ``--pruefer codex`` wird abgelehnt. Fehlt ``--master``, liest das Werkzeug den Besitzer aus der
Besitzdatei des Master-Schalters ``.hermes/uebergabe/laufend/<name>.master``; ``<name>`` ist das Thema selbst
oder der laengste Anfang des Themas vor einem Bindestrich (``master-schalter-kurz`` -> ``master-schalter``).
Leere Datei = claude (wie ``besitz.py``). Unlesbar, unbekannter Besitzer oder keine Datei => Abbruch (Exit 2),
bis ``--master`` angegeben ist - sonst koennte Codex unbemerkt einen Codex-Master pruefen. Ausnahme ``--sensibel``
(Hermes ohnehin). Aus einem Git-Worktree heraus gelten Besitzdateien und Protokolle des Hauptarbeitsbaums.
Die Quelle steht im Protokoll.

Ohne ``--pruefer`` liest das Werkzeug ausserdem die Codex-Messung des Master-Schalters
(``codex-kontingent.json``): steht Codex laut frischer Messung (<= 15 min) bei 100 % mit kuenftigem Reset,
prueft gleich Hermes - ohne Codex-Fehlversuch. Unbekannte/alte Messung => wie bisher.

Waehrend eines Laufs steht "Pruefung R<n> laeuft" als Wartemeldung des Master-Schalters
(``wartet/<name>.json``), nur wenn keine andere Meldung da ist; am Ende wird nur die eigene entfernt.

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
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERMES_MODELL = "deepseek/deepseek-v4.1-flash"
CODEX_GRUENDLICH_MODELL = "gpt-6-astra"
ZEITGRENZE_STANDARD = 900
MESSUNG_FRISCH_SEKUNDEN = 15 * 60   # aeltere Codex-Messung zaehlt nicht (Leiste misst alle 5 min)
URTEIL_MUSTER = re.compile(r"^URTEIL:\s*(FREI|EINWAND)\s*$")
THEMA_MUSTER = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
FASSUNG_MUSTER = re.compile(r"Fassung\s*(\d+)", re.IGNORECASE)
# Codex gesperrt (Nutzungslimit o. ae.) -> Hermes prueft ersatzweise (Sebastian, 12.10.2026).
GESPERRT_MUSTER = re.compile(r"usage limit|rate.?limit|quota|\b429\b", re.IGNORECASE)


class PruefkreisFehler(Exception):
    """Aufruf ist nicht zulaessig (z. B. sensibel + Codex, fehlende Vorlage)."""


def haupt_repo(repo: Path = REPO) -> Path:
    """Hauptarbeitsbaum: in einem Git-Worktree ist ``.git`` eine Datei, die ueber ``commondir`` dorthin zeigt.

    ``.hermes/`` ist gitignored und liegt nur im Hauptarbeitsbaum - Besitz und Protokolle gelten dort.
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


def protokoll_ordner() -> Path:
    return Path(os.environ.get("PRUEFKREIS_DIR") or haupt_repo() / ".hermes" / "pruefkreis")


def besitz_ordner() -> Path:
    return Path(os.environ.get("PRUEFKREIS_BESITZ_DIR") or haupt_repo() / ".hermes" / "uebergabe" / "laufend")


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


MASTER_WERTE = ("claude", "codex", "hermes")


def pruefer_waehlen(pruefer: str | None, sensibel: bool, master: str | None = None) -> str:
    if master not in (None, *MASTER_WERTE):
        raise PruefkreisFehler(f"Unbekannter Master: {master}")
    if sensibel:
        if pruefer == "codex":
            raise PruefkreisFehler("Sensible Inhalte prueft ausschliesslich Hermes (AGENTS.md) - Codex verweigert.")
        return "hermes"
    if pruefer not in (None, "codex", "hermes"):
        raise PruefkreisFehler(f"Unbekannter Pruefer: {pruefer}")
    if master == "codex":
        if pruefer == "codex":
            raise PruefkreisFehler("Codex prueft nicht die Arbeit eines Codex-Masters (AGENTS.md: andere Modellfamilie).")
        return "hermes"
    return pruefer or "codex"


def master_ermitteln(thema: str, angegeben: str | None) -> tuple[str | None, str]:
    """Master und Quelle fuers Protokoll: ausdruecklich angegeben, sonst aus der Besitzdatei des Schalters."""
    if angegeben is not None:
        return angegeben, "angegeben"
    teile = thema.split("-")
    for laenge in range(len(teile), 0, -1):
        name = "-".join(teile[:laenge])
        datei = besitz_ordner() / f"{name}.master"
        if not datei.is_file():
            continue
        try:
            text = datei.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            return None, f"unbekannt ({name}.master unlesbar)"
        besitzer = text.split()[0] if text else "claude"
        if besitzer not in MASTER_WERTE:
            return None, f"unbekannt ({name}.master nennt keinen bekannten Master)"
        return besitzer, f"{name}.master"
    return None, "unbekannt (keine Besitzdatei)"


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


def kontingent_datei() -> Path:
    """Codex-Messung des Master-Schalters (`masterwechsel codex-messen`, Leiste alle 5 min)."""
    basis = os.environ.get("MASTER_SCHALTER_DATEN") or str(Path.home() / ".master-schalter")
    return Path(basis) / "codex-kontingent.json"


def codex_im_limit(jetzt: float | None = None) -> str | None:
    """Grund, wenn Codex laut FRISCHER Messung im Limit ist - sonst None (unbekannt/alt/kaputt = wie bisher).

    Frisch heisst hoechstens ``MESSUNG_FRISCH_SEKUNDEN`` alt; im Limit heisst ein Fenster bei 100 % mit Reset in der
    Zukunft. Gueltig ist eine Messung nur nach denselben Regeln wie ``signale._codex_filtern`` im Master-Schalter
    (beide Fenster, 0-100 %, darstellbarer Reset, ``resets_at: null`` nur bei 0 %). Gelesen werden nur ``gelesen_um``
    und je Fenster ``used_percent``/``resets_at``.
    """
    jetzt = time.time() if jetzt is None else jetzt
    try:
        roh = json.loads(kontingent_datei().read_text(encoding="utf-8"))
        stand = datetime.fromisoformat(roh["gelesen_um"].replace("Z", "+00:00"))   # wie `signale._iso`
        gelesen = (stand if stand.tzinfo else stand.replace(tzinfo=timezone.utc)).timestamp()
        fenster = roh["fenster"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    if not isinstance(fenster, dict) or not 0 <= jetzt - gelesen <= MESSUNG_FRISCH_SEKUNDEN:
        return None
    # Erst BEIDE Fenster prüfen (wie `_codex_filtern` im Master-Schalter): ein kaputtes Fenster macht die ganze
    # Messung ungültig, auch wenn das andere schon ein Limit zeigt.
    gueltig = []
    for name in ("5h", "Woche"):
        werte = fenster.get(name)
        if not isinstance(werte, dict):
            return None
        prozent, reset = werte.get("used_percent"), werte.get("resets_at")
        if not isinstance(prozent, (int, float)) or isinstance(prozent, bool) or not 0 <= prozent <= 100:
            return None
        if reset is None:   # kein offenes Fenster: gültig nur mit 0 % (wie `_codex_filtern`), nie ein Limit
            if prozent != 0:
                return None
            continue
        if not isinstance(reset, (int, float)) or isinstance(reset, bool):
            return None
        try:   # nicht darstellbare Zeit (z. B. 1e100, inf) = kaputte Messung
            bis = time.strftime("%d.%m. %H:%M", time.localtime(reset))
        except (OverflowError, OSError, ValueError):
            return None
        gueltig.append((name, prozent, reset, bis))
    for name, prozent, reset, bis in gueltig:
        if prozent == 100 and reset > jetzt:
            return f"Codex {name} 100 % laut Messung {time.strftime('%H:%M', time.localtime(gelesen))}, Reset {bis}"
    return None


def codex_gesperrt(exitcode: int, stderr: str) -> bool:
    """Codex endete wegen Limit/Kontingent - dann springt Hermes ein, statt zu warten."""
    return exitcode not in (0, -1) and bool(GESPERRT_MUSTER.search(stderr or ""))


def _lauf(wer: str, programm: str, auftrag: str, gruendlich: bool, zeitgrenze: float) -> dict:
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
    return {"exitcode": exitcode, "text": text, "stderr": stderr, "nutzung": nutzung, "dauer": dauer}


def modell_fuer(wer: str, gruendlich: bool) -> str:
    if wer == "hermes":
        return HERMES_MODELL
    return CODEX_GRUENDLICH_MODELL if gruendlich else "Codex-App-Standard (Denkstufe high)"


def planfassung_lesen(vorlage: str, angegeben: str | None) -> str:
    """Planfassung fuers Protokoll: ausdruecklich angegeben, sonst 'Fassung N' aus der Vorlage."""
    if angegeben:
        return angegeben
    datei = REPO / vorlage if (REPO / vorlage).is_file() else Path(vorlage)
    try:
        treffer = FASSUNG_MUSTER.search(datei.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        treffer = None
    return treffer.group(1) if treffer else "nicht angegeben"


def protokoll_block(ergebnis: dict) -> str:
    kopf = (f"## Runde {ergebnis['runde']} · {ergebnis['zeit']} · Pruefer {ergebnis['pruefer']}"
            f" · Vorlage `{ergebnis['vorlage']}`")
    zeilen = [kopf, "", f"**Status: {ergebnis['status'].upper()}**",
              f"Modell: {ergebnis.get('modell', '?')} · Planfassung: {ergebnis.get('planfassung', '?')}"]
    if ergebnis.get("master_quelle"):
        zeilen.append(f"Master: {ergebnis.get('master') or '?'} ({ergebnis['master_quelle']})")
    if ergebnis.get("ersatz"):
        zeilen.append(f"Ersatzpruefer: {ergebnis['ersatz']}")
    if ergebnis.get("grund"):
        zeilen.append(f"Grund: {ergebnis['grund']}")
    if ergebnis.get("sitzung"):
        zeilen.append(f"Hermes-Sitzung: `{ergebnis['sitzung']}`")
    if ergebnis.get("kosten_usd") is not None:
        zeilen.append(f"Kosten: {ergebnis['kosten_usd']:.4f} USD")
    zeilen += [f"Dauer: {ergebnis['dauer_s']} s", "", ergebnis["ausgabe"].strip() or "(keine Ausgabe)", ""]
    return "\n".join(zeilen)


def wartet_datei(name: str) -> Path:
    """„Wartet worauf“-Datei des Master-Schalters (`masterwechsel warte`, angezeigt von `kurz`)."""
    basis = os.environ.get("MASTER_SCHALTER_DATEN") or str(Path.home() / ".master-schalter")
    return Path(basis) / "wartet" / f"{name}.json"


def wartet_melden(name: str, text: str) -> str | None:
    """Meldung setzen, wenn keine da ist; liefert den eigenen Text oder None (fremde Meldung / Fehler).

    Eine vorhandene Meldung (von Sebastian oder einem Agenten) wird nie überschrieben. Fehler werden
    verschluckt - die Prüfung läuft immer weiter.
    """
    datei = wartet_datei(name)
    tmp = None
    try:
        datei.parent.mkdir(parents=True, exist_ok=True)
        inhalt = json.dumps({"text": text, "zeit": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(prefix=f"{name}.", suffix=".tmp", dir=datei.parent)   # je Aufruf neu (O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(inhalt)
        os.link(tmp, datei)   # atomar und nur, wenn das Ziel fehlt (FileExistsError) - nie überschreiben
    except OSError:
        return None
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return text


def wartet_aufraeumen(name: str, eigen: str | None) -> None:
    """Nur die eigene Meldung entfernen (gleicher Text); eine inzwischen geänderte bleibt stehen."""
    if not eigen:
        return
    datei = wartet_datei(name)
    try:
        if json.loads(datei.read_text(encoding="utf-8")).get("text") == eigen:
            datei.unlink()
    except (OSError, ValueError, AttributeError):
        pass


def pruefen(vorlage: str, thema: str, pruefer: str | None = None, sensibel: bool = False,
            gruendlich: bool = False, zeitgrenze: float = ZEITGRENZE_STANDARD,
            planfassung: str | None = None, master: str | None = None) -> dict:
    """Prüflauf mit „Wartet worauf“-Meldung für das Thema der Besitzdatei (nur wenn keine andere da ist)."""
    name = None
    if THEMA_MUSTER.match(thema):
        quelle = master_ermitteln(thema, master)[1]
        name = quelle[: -len(".master")] if quelle.endswith(".master") else None   # nur ein Schalter-Thema
    eigen = wartet_melden(name, f"Prüfung R{naechste_runde(thema)} läuft (pruefkreis, {thema})") if name else None
    try:
        return _pruefen(vorlage, thema, pruefer, sensibel, gruendlich, zeitgrenze, planfassung, master)
    finally:
        if name:
            wartet_aufraeumen(name, eigen)


def _pruefen(vorlage: str, thema: str, pruefer: str | None, sensibel: bool, gruendlich: bool,
             zeitgrenze: float, planfassung: str | None, master: str | None) -> dict:
    if not THEMA_MUSTER.match(thema):
        raise PruefkreisFehler("Thema nur aus a-z, 0-9 und Bindestrich (wird Dateiname).")
    if not (REPO / vorlage).is_file() and not Path(vorlage).is_file():
        raise PruefkreisFehler(f"Vorlage nicht gefunden: {vorlage}")
    master, master_quelle = master_ermitteln(thema, master)
    if master is None and not sensibel:
        raise PruefkreisFehler(f"Master {master_quelle} - bitte --master claude|codex|hermes angeben "
                               "(sonst koennte Codex einen Codex-Master pruefen).")
    wer = pruefer_waehlen(pruefer, sensibel, master)
    ersatz = ("Hermes statt Codex - Master ist Codex (keine Pruefung durch dieselbe Modellfamilie)"
              if master == "codex" and not sensibel and pruefer is None else "")
    limit = codex_im_limit() if wer == "codex" and pruefer is None else None
    if limit:   # gemessen im Limit: gleich Hermes statt erst eines Codex-Fehlversuchs
        wer, gruendlich = "hermes", False
        ersatz = f"Hermes statt Codex - {limit} (kein Fehlversuch)"
    programm = codex_programm() if wer == "codex" else hermes_programm()
    if not programm:
        raise PruefkreisFehler(f"Programm fuer {wer} nicht gefunden.")
    runde = naechste_runde(thema)
    auftrag = auftrag_text(vorlage, runde, sensibel)

    lauf = _lauf(wer, programm, auftrag, gruendlich, zeitgrenze)
    if wer == "codex" and codex_gesperrt(lauf["exitcode"], lauf["stderr"]):
        ersatz = f"Hermes statt Codex - Codex gesperrt ({fehlerzeile(lauf['stderr'])})"
        hermes = hermes_programm()
        if hermes:
            dauer_codex = lauf["dauer"]
            wer, gruendlich = "hermes", False
            lauf = _lauf("hermes", hermes, auftrag, False, zeitgrenze)
            lauf["dauer"] = round(lauf["dauer"] + dauer_codex, 1)
        else:
            ersatz += "; Hermes nicht gefunden - kein Ersatzlauf"
    exitcode, text, stderr, nutzung, dauer = (lauf["exitcode"], lauf["text"], lauf["stderr"],
                                              lauf["nutzung"], lauf["dauer"])

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
                "modell": modell_fuer(wer, gruendlich), "planfassung": planfassung_lesen(vorlage, planfassung),
                "status": status, "grund": grund, "ersatz": ersatz, "master": master,
                "master_quelle": master_quelle, "dauer_s": dauer, "ausgabe": ausgabe, **nutzung}
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
    p.add_argument("--master", choices=MASTER_WERTE, help="Master des Themas (sonst aus der Besitzdatei); Codex prueft nie einen Codex-Master")
    p.add_argument("--sensibel", action="store_true")
    p.add_argument("--gruendlich", action="store_true", help=f"Codex mit {CODEX_GRUENDLICH_MODELL}")
    p.add_argument("--zeitgrenze", type=float, default=ZEITGRENZE_STANDARD)
    p.add_argument("--planfassung", help="sonst 'Fassung N' aus der Vorlage")
    args = parser.parse_args(argv)
    try:
        ergebnis = pruefen(args.vorlage, args.thema, args.pruefer, args.sensibel, args.gruendlich, args.zeitgrenze,
                           args.planfassung, args.master)
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
