"""Lokale Hermes-CLI-Anbindung (Track C) — bearbeitet erkannte Programmierauftraege
direkt auf dem Geraet (dem Handy) und strahlt die Gedanken des Agenten live aus.

Warum dieser Dienst:
  - Ohne PC (unterwegs, Zug/Wochenende) ist der PC-Hermes nicht erreichbar.
  - Dieses Modul startet den lokalen `hermes`-CLI (Termux) in einer tmux-Pane
    und gibt seine Zwischengedanken (Hermes-Boxen) sowie seine Werkzeug-Schritte
    (Tool-Zeilen, z. B. "💻 $ ls -la ...") live an den Chat weiter — inhaltlich
    1:1, wie der Agent sie tippt. Erst am Ende kommt das Endergebnis.
  - Ist `hermes` oder `tmux` nicht installiert oder der Start schlaegt fehl,
    liefert der Stream eine Fehlermeldung, und die Weiche faellt aufs
    Auftragsbuch zurueck (Track B).

Warum tmux + Pane-Lesen statt blockierendem `subprocess.run`:
  - Ein blockierender Aufruf (`hermes chat -q ...`) liefert erst nach Minuten
    das Endergebnis als einen Textbrocken — ohne jeden Zwischenstand.
  - Im tmux ist die Pane ein TTY. Der CLI rendert seine Gedanken und
    Werkzeug-Schritte dort live. Das Backend liest sie mit `capture-pane`,
    dedupliziert nach Inhalt und schreibt sie als Status-Meldung ins
    Auftragsbuch (der Kanal, den das Frontend ohnehin alle 3 s pollt und
    als Chat-Blase zeigt).
"""

import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from typing import Iterator, List, Optional

logger = logging.getLogger(__name__)

# Wie lange der lokale Hermes-CLI hoechstens fuer einen Auftrag arbeitet.
# Coding-Auftraege koennen lange dauern (Dateien anlegen, testen, commiten).
DEFAULT_TIMEOUT = 900

# tmux-Pane-Groesse. Der Hermes-TUI braucht etwas Breite, sonst bricht er
# Zeilen um und die Gedanken-Boxen werden unleserlich zerteilt.
_TMUX_WIDTH = 240
_TMUX_HEIGHT = 80

# Wie lange die Session nach dem Ende des CLI noch am Leben bleibt, damit
# das Backend die endgueltige Antwort-Box noch aus der Pane lesen kann.
_NACHLESE_VERWEIL = 8

# Eine Hermes-Gedanken-Box im TUI-Layout beginnt mit "╭― ⚕ Hermes ..." und
# endet mit "╰". Dazwischen stehen die Gedanken (mit fuehrendem Rand "│").
_BOX_START = re.compile(r"╭.*Hermes")
_BOX_END = re.compile(r"╰")
# Werkzeug-Schritt-Zeile ausserhalb einer Box, z. B. "💻 $ ls -la ...".
_TOOL_ZEILE = re.compile(r"💻.*?\$\s*(.*)")
# Inhalt einer Box-Zeile: fuehrenden Rand '│' abstreifen.
_BOX_INHALT = re.compile(r"^│\s*")


def ist_verfuegbar() -> bool:
    """True, wenn der lokale Hermes-CLI und tmux auf dem Geraet installiert sind."""
    return shutil.which("hermes") is not None and shutil.which("tmux") is not None


class LocalHermesJob:
    """Ein laufender lokaler Hermes-Auftrag in einer tmux-Pane.

    Laesst den CLI im tmux-Pane (TTY) arbeiten, damit er seine Gedanken live
    rendert, und liest sie per ``neue_gedanken()`` aus der Pane. Das
    Endergebnis wird am Schluss aus der letzten Hermes-Box der Pane gelesen.
    """

    _zähler = 0

    def __init__(self, auftrag: str, timeout: int = DEFAULT_TIMEOUT):
        self.auftrag = auftrag
        self.timeout = timeout
        self._startzeit = time.time()

        # Eindeutige tmux-Session + Arbeitsverzeichnis in einem schreibbaren
        # Ort (Termux: /tmp ist nicht beschreibbar -> HOME).
        werk = tempfile.mkdtemp(prefix="hermes-job-", dir=os.path.expanduser("~"))
        LocalHermesJob._zähler += 1
        self.session = f"hermes_agent_{int(time.time()*1000)}_{LocalHermesJob._zähler}"
        self.query_file = os.path.join(werk, "query.txt")
        self._werk = werk

        # Auftrag in eine Datei schreiben und per --query-file uebergeben:
        # Anfuehrungszeichen, $(), Backticks und Umlaute bleiben exakt erhalten,
        # nichts wird von der Shell interpretiert.
        with open(self.query_file, "w", encoding="utf-8") as f:
            f.write(auftrag)

        # Bereits gemeldete Gedanken (Inhalts-Dedupe).
        self.gesehene_gedanken: set = set()

    # ------------------------------------------------------------------
    # Start / Zustand / Stopp
    # ------------------------------------------------------------------

    def starten(self) -> bool:
        """Startet den CLI in einer eigenen tmux-Pane. True bei Erfolg."""
        try:
            # Wichtig: KEINE stdout-Umleitung. Die Pane ist das TTY, in dem der
            # CLI seine Gedanken live rendert. Das nachgestellte `sleep` haelt
            # die Session kurz nach dem Ende des CLI am Leben, damit das
            # Ergebnis noch aus der Pane gelesen werden kann.
            inner = (
                f"hermes chat --query-file {shlex.quote(self.query_file)}; "
                f"sleep {_NACHLESE_VERWEIL}"
            )
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", self.session,
                 "-x", str(_TMUX_WIDTH), "-y", str(_TMUX_HEIGHT), inner],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
            logger.info("Lokaler Hermes gestartet (Session %s)", self.session)
            return True
        except Exception as e:  # pragma: no cover - Startfehler
            logger.warning("Lokaler Hermes-Start fehlgeschlagen (%s)", e)
            return False

    def beende(self) -> None:
        """Raeumt die tmux-Session und die Arbeitsdateien wieder auf."""
        try:
            subprocess.run(["tmux", "kill-session", "-t", self.session],
                           capture_output=True, timeout=10)
        except Exception:  # pragma: no cover - Session evtl. schon weg
            pass
        try:
            shutil.rmtree(self._werk, ignore_errors=True)
        except Exception:  # pragma: no cover
            pass
        logger.debug("Lokaler Hermes-Auftrag aufgeraeumt (%s)", self.session)

    def _pane_text(self) -> str:
        """Ganzen Scrollback der tmux-Pane holen (fuer Gedanken + Ergebnis)."""
        try:
            r = subprocess.run(
                ["tmux", "capture-pane", "-t", self.session, "-p", "-S", "-"],
                capture_output=True, text=True, timeout=10,
            )
            return r.stdout or ""
        except Exception:  # pragma: no cover
            return ""

    def abgeschlossen(self) -> bool:
        """True, sobald der CLI seine Abschluss-Zeile (Session-Fusszeile)
        gerendert hat bzw. die Session endete. Am Ende erscheint im -q-Modus
        eine Fusszeile mit "Resume this session" und einer "Session:"-Zeile.
        """
        pane = self._pane_text()
        if "Resume this session" in pane or re.search(r"\bSession:\s+\d{8}_", pane):
            return True
        # Session weg = CLI (und das nachgestellte sleep) lange genug vorbei.
        r = subprocess.run(["tmux", "has-session", "-t", self.session],
                           capture_output=True)
        return r.returncode != 0

    def neue_gedanken(self) -> List[str]:
        """Neue, noch nicht gemeldete Gedanken-/Werkzeug-Schritte seit letztem
        Poll: Hermes-Boxen und "💻 $ ..."-Tool-Zeilen, nach Inhalt dedupliziert.
        """
        pane = self._pane_text()
        if not pane:
            return []

        gedanken: List[str] = []
        in_box = False
        box_zeilen: List[str] = []

        for zeile in pane.splitlines():
            if not in_box and _BOX_START.search(zeile):
                in_box = True
                box_zeilen = []
                continue
            if in_box:
                if _BOX_END.search(zeile):
                    in_box = False
                    text = " ".join(box_zeilen).strip()
                    if text:
                        gedanken.append(text)
                    continue
                innen = _BOX_INHALT.sub("", zeile).rstrip()
                if innen.strip():
                    box_zeilen.append(innen)
                continue
            m = _TOOL_ZEILE.search(zeile)
            if m:
                gedanken.append("🔧 " + m.group(1).strip())

        neu = []
        for g in gedanken:
            if g and g not in self.gesehene_gedanken:
                self.gesehene_gedanken.add(g)
                neu.append(g)
        return neu

    def ergebnis(self) -> Optional[str]:
        """Endergebnis = letzte Hermes-Box aus der Pane (die Antwort-Box)."""
        boxen = _extrahiere_boxen(self._pane_text())
        return boxen[-1] if boxen else None


def _extrahiere_boxen(text: str) -> List[str]:
    """Extrahiert alle Hermes-Box-Texte aus einem Text (Pane/Log)."""
    boxen: List[str] = []
    in_box = False
    zeilen: List[str] = []
    for zeile in text.splitlines():
        if not in_box and _BOX_START.search(zeile):
            in_box = True
            zeilen = []
            continue
        if in_box:
            if _BOX_END.search(zeile):
                in_box = False
                t = " ".join(zeilen).strip()
                if t:
                    boxen.append(t)
                continue
            innen = _BOX_INHALT.sub("", zeile).rstrip()
            if innen.strip():
                zeilen.append(innen)
    return boxen


def stream_auftrag(
    auftrag: str, timeout: int = DEFAULT_TIMEOUT
) -> Iterator[dict]:
    """Startet den lokalen Hermes und liefert seine Ereignisse als Generator.

    Yields:
        {"art": "gedanke", "text": "..."}  — Zwischengedanke / Werkzeug-Schritt
        {"art": "ergebnis", "text": "..."} — finales Endergebnis (am Schluss)
        {"art": "fehler", "text": "..."}   — Start/Timeout-Fehler
    """
    if not ist_verfuegbar():
        yield {"art": "fehler", "text": "Lokaler Hermes/tmux nicht verfuegbar"}
        return

    job = LocalHermesJob(auftrag, timeout=timeout)
    if not job.starten():
        yield {"art": "fehler", "text": "Lokaler Hermes nicht startbar"}
        job.beende()
        return

    try:
        start = time.time()
        while time.time() - start < timeout:
            for gedanke in job.neue_gedanken():
                yield {"art": "gedanke", "text": gedanke}
            if job.abgeschlossen():
                # Kurze Nachlese fuer die endgueltige Antwort-Box.
                time.sleep(1)
                ergebnis = job.ergebnis()
                yield {"art": "ergebnis", "text": ergebnis or ""}
                return
            time.sleep(1)

        logger.warning("Lokaler Hermes-Auftrag ueberschritt %ds", timeout)
        yield {"art": "fehler", "text": f"Lokaler Hermes brauchte laenger als {timeout}s"}
    finally:
        job.beende()