"""Lokale Hermes-CLI-Anbindung (Track C) — bearbeitet erkannte Programmierauftraege
direkt auf dem Geraet (dem Handy) und strahlt die Gedanken des Agenten live aus.

Live-Eingabe (seit Erweiterungsrunde):
  - Der lokale Hermes laeuft im interaktiven Modus, damit der Nutzer waehrend
    der Bearbeitung Kommentare direkt an den Agenten schicken kann.
  - Eine Job-Registry haelt eine offene tmux-Session pro Auftrag und bietet
    `sende()` an. Kommentare gehen per `tmux send-keys` an die laufende
    Session; parallel werden sie durch das persoenliche Gedaechtnis gefuehrt
    (siehe chat.py), damit der eigene Assistent mitlernt — aber nur Kommentare
    mit persoenlichem Mehrwert, keine trivialen Interjektionen.

Faellt `hermes`/`tmux` aus oder schlaegt der Start fehl, liefert der Stream
eine Fehlermeldung, und die Weiche faellt aufs Auftragsbuch zurueck (Track B).
"""

import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

# Wie lange der lokale Hermes-CLI hoechstens fuer einen Auftrag arbeitet.
DEFAULT_TIMEOUT = 900

# tmux-Pane-Groesse. Der Hermes-TUI braucht etwas Breite, sonst bricht er
# Zeilen um und die Gedanken-Boxen werden unleserlich zerteilt.
_TMUX_WIDTH = 240
_TMUX_HEIGHT = 80

# Box-Layout der Hermes-TUI.
_BOX_START = re.compile(r"╭.*Hermes")
_BOX_END = re.compile(r"╰")
_TOOL_ZEILE = re.compile(r"💻.*?\$\s*(.*)")
_BOX_INHALT = re.compile(r"^│\s*")

# Aktiver Denk-/Tool-Timer in der Fortschritts-Statuszeile der TUI ("... ⏱ <n>s ...").
# Nur eine laufende Zeit (n>0) zaehlt als Arbeit; ein stillgelegtes '⏱ 0s'
# oder fehlender Timer nach der Antwort ist es nicht.
_LIVE_TIMER_ZEILE = re.compile(r"⏱\s*[1-9]\d*\s*s", re.IGNORECASE)

# Wie lange die Pane stabil (unveraendert, kein Timer, kein Tool-Schritt)
# bleiben muss, bevor der Auftrag als abgeschlossen gilt. Faengt kurze
# Pausen zwischen zwei Denk-/Tool-Schritten ab, die sonst als "fertig"
# missdeutet wuerden.
_ABSCHLUSS_IDLE_S = 10


def _box_innen(zeile: str) -> str:
    """Entfernt die Box-Raender der TUI aus einer Inhaltszeile.

    Die Pane zeigt jede Zeile mit Fuehrungs- UND Abschluss-'│' (rechter Rand).
    Beide muessen weg, sonst kleben Kante + Auffuell-Leerzeichen am Text.
    """
    return _BOX_INHALT.sub("", zeile).rstrip().rstrip("│").rstrip()

# Kommentare ohne persoenlichen Mehrwert (Interjektionen / reine
# Aufforderungen) landen nicht im persoenlichen Gedaechtnis.
_TRIVIAL_KOMMENTARE = re.compile(
    r"^(weiter|ok(ay)?|ja|nein?|genau|aha|danke|ok|mach(ey) mal weiter|"
    r"alles klar|verstanden|gut|super|lol|nop?e?)\b",
    re.IGNORECASE,
)


def ist_verfuegbar() -> bool:
    """True, wenn der lokale Hermes-CLI und tmux auf dem Geraet installiert sind."""
    return shutil.which("hermes") is not None and shutil.which("tmux") is not None


def hat_mehrwert(kommentar: str) -> bool:
    """Soll der Kommentar ins persoenliche Gedaechtnis gelernt werden?

    Nur Kommentare mit Projekt-/persoenlichem Mehrwert (>= 4 Zeichen, keine
    reine Bestuftigung) gelten als merkenswert. Der Hermes bekommt jeden
    Kommentar — dieses Filter entscheidet nur, ob er mitgelernt wird.
    """
    text = (kommentar or "").strip()
    if len(text) < 4:
        return False
    if _TRIVIAL_KOMMENTARE.match(text):
        return False
    return True


class LocalHermesJob:
    """Ein laufender lokaler Hermes-Auftrag in einer tmux-Pane (interaktiv).

    Startet `hermes chat` ohne Einzel-Query, laesst die Session offen und
    bietet `sende_zeile()` an — so kann der Nutzer waehrend der Bearbeitung
    Kommentare direkt an den Agenten schicken. Gedanken und Antworten werden
    per `capture-pane` gelesen und nach Inhalt dedupliziert.
    """

    _zaehler = 0

    def __init__(self, auftrag_text: str, timeout: int = DEFAULT_TIMEOUT):
        self.auftrag_text = auftrag_text
        self.timeout = timeout
        self._startzeit = time.time()

        werk = tempfile.mkdtemp(prefix="hermes-job-", dir=os.path.expanduser("~"))
        LocalHermesJob._zaehler += 1
        self.session = f"hermes_agent_{int(time.time()*1000)}_{LocalHermesJob._zaehler}"
        self._werk = werk

        self.gesehene_gedanken: set = set()

    # ------------------------------------------------------------------
    # Start / Stopp
    # ------------------------------------------------------------------

    def starten(self) -> bool:
        """Startet Hermes interaktiv in einer eigenen tmux-Pane und sendet den
        ersten Auftrag. True bei Erfolg.
        """
        try:
            inner = "hermes chat"
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", self.session,
                 "-x", str(_TMUX_WIDTH), "-y", str(_TMUX_HEIGHT), inner],
                capture_output=True, text=True, timeout=15, check=True,
            )
            # Warten bis der CLI bereit ist, dann den Auftrag hinten.
            time.sleep(6)
            if not self.sende_zeile(self.auftrag_text):
                logger.warning(
                    "Lokaler Hermes nahm Auftrag nicht an (Session %s)", self.session
                )
                return False
            logger.info(
                "Lokaler Hermes gestartet + Auftrag gesendet (Session %s)", self.session
            )
            return True
        except Exception as e:  # pragma: no cover
            logger.warning("Lokaler Hermes-Start fehlgeschlagen (%s)", e)
            return False

    def beende(self) -> None:
        """Raeumt die tmux-Session und die Arbeitsdateien wieder auf."""
        try:
            subprocess.run(["tmux", "kill-session", "-t", self.session],
                           capture_output=True, timeout=10)
        except Exception:  # pragma: no cover
            pass
        try:
            shutil.rmtree(self._werk, ignore_errors=True)
        except Exception:  # pragma: no cover
            pass
        logger.debug("Lokaler Hermes-Auftrag aufgeraeumt (%s)", self.session)

    # ------------------------------------------------------------------
    # Eingabe an den laufenden Agenten
    # ------------------------------------------------------------------

    def sende_zeile(self, text: str) -> bool:
        """Sendet eine Zeile (Auftrag oder Kommentar) in die tmux-Pane.

        `tmux send-keys` kann gegen eine sehr grosse Pane kurz haengen. Ein
        subprocess-Timeout verhindert, dass der API-Call endlos blockiert —
        stattdessen wird False geliefert und der Aufrufer kann sauber
        reagieren (z. B. 409 statt dauerhafter Haenger).
        """
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", self.session, text, "Enter"],
                capture_output=True, text=True, timeout=5, check=True,
            )
            return True
        except subprocess.TimeoutExpired:
            logger.warning("send-keys ueberschritt 5s (Pane voll?) - Session %s", self.session)
            return False
        except Exception as e:  # pragma: no cover
            logger.warning("send-keys fehlgeschlagen (%s)", e)
            return False

    # ------------------------------------------------------------------
    # Lesen / Zustand
    # ------------------------------------------------------------------

    def _pane_text(self) -> str:
        try:
            r = subprocess.run(
                ["tmux", "capture-pane", "-t", self.session, "-p", "-S", "-"],
                capture_output=True, text=True, timeout=10,
            )
            return r.stdout or ""
        except Exception:  # pragma: no cover
            return ""

    def lebt_noch(self) -> bool:
        """True, solange die tmux-Session (und damit Hermes) noch da ist."""
        r = subprocess.run(["tmux", "has-session", "-t", self.session],
                           capture_output=True)
        return r.returncode == 0

    def neue_gedanken(self) -> List[str]:
        """Neue Hermes-Gedanken-/Tool-Schritte seit letztem Poll, dedupliziert."""
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
                    # Zeilen MIT Umbruch verketten statt mit Leerzeichen —
                    # vorher wurden mehrzeilige Inhalte (Diff/Stat/Text) zu
                    # einem langen Fließtext mit komischen Brüchen gequetscht.
                    # Regression (LIVE-Fehler "Name T is not defined"): hier
                    # stand ein nie definiertes `t` — sobald die erste
                    # Antwort-Box fertig war, flog ein NameError und der
                    # Auftrag brach mit "Fehler im lokalen Hermes-Job" ab.
                    t = "\n".join(box_zeilen).strip()
                    if t:
                        gedanken.append(t)
                    continue

                innen = _box_innen(zeile)
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

    def alle_antwort_boxen(self) -> List[str]:
        """Alle Hermes-Antwort-Boxen aus der Pane (fuer das Endergebnis)."""
        return _extrahiere_boxen(self._pane_text())


def _extrahiere_boxen(text: str) -> List[str]:
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
            innen = _box_innen(zeile)
            if innen.strip():
                zeilen.append(innen)
    return boxen


# ----------------------------------------------------------------------
# Job-Registry: haelt laufende Sessions pro Auftrag am Leben, damit man
# waehrend der Bearbeitung Kommentare an den gleichen Agenten schicken kann.
# ----------------------------------------------------------------------

class HermesRegistry:
    """Verzeichnis der laufenden lokalen Hermes-Auftraege (Auftrag-ID -> Job)."""

    def __init__(self) -> None:
        self._jobs: Dict[str, LocalHermesJob] = {}
        self._sperre = threading.Lock()

    def starte(self, auftrag_id: str, auftrag_text: str) -> Optional[LocalHermesJob]:
        """Startet einen Job fuer die Auftrags-ID, falls noch keiner laeuft."""
        with self._sperre:
            if auftrag_id in self._jobs:
                return self._jobs[auftrag_id]
            job = LocalHermesJob(auftrag_text)
            if not job.starten():
                job.beende()
                return None
            self._jobs[auftrag_id] = job
            return job

    def holen(self, auftrag_id: str) -> Optional[LocalHermesJob]:
        with self._sperre:
            return self._jobs.get(auftrag_id)

    def sende_an(self, auftrag_id: str, text: str) -> bool:
        """Sendet einen Kommentar an den laufenden Job einer Auftrag. False,
        wenn es keinen laufenden Job (mehr) gibt.
        """
        job = self.holen(auftrag_id)
        if job is None or not job.lebt_noch():
            return False
        return job.sende_zeile(text)

    def entferne(self, auftrag_id: str) -> None:
        with self._sperre:
            job = self._jobs.pop(auftrag_id, None)
        if job is not None:
            job.beende()


hermes_registry = HermesRegistry()


def stream_auftrag(
    auftrag_id: str, auftrag_text: str, timeout: int = DEFAULT_TIMEOUT
) -> Iterator[dict]:
    """Startet den lokalen Hermes (interaktiv) und liefert seine Ereignisse.

    Wird in einem Daemon-Thread betrieben (siehe _starte_lokale_hermes). Die
    Session bleibt ueber die Registry am Leben, damit waehrend des Laufs
    Kommentare an denselben Agenten gehen koennen.

    Yields:
        {"art": "gedanke", "text": ...}
        {"art": "ergebnis", "text": ...}
        {"art": "fehler", "text": ...}
    """
    if not ist_verfuegbar():
        yield {"art": "fehler", "text": "Lokaler Hermes/tmux nicht verfuegbar"}
        return

    job = hermes_registry.starte(auftrag_id, auftrag_text)
    if job is None:
        yield {"art": "fehler", "text": "Lokaler Hermes nicht startbar"}
        return

    try:
        start = time.time()
        # Im interaktiven Modus beendet sich Hermes nicht von selbst:
        # Nach einer Antwort zeigt er wieder den Eingabe-Prompt. Ein Auftrag
        # gilt als abgeschlossen, wenn eine Antwort-Box vorliegt, der Agent
        # laut Pane nicht mehr arbeitet UND die Pane ueber ein kurzes
        # Idle-Fenster stabil bleibt (kein neuer Timer / keine neue Zeile).
        # Grund: Der '❯' steht auch waehrend der Arbeit permanent unten, und
        # zwischen zwei Denk-/Tool-Schritten gibt es kurze Vorschauboxen. Ein
        # einzelner Sichtbarkeits-Check wuerde den Auftrag dadurch viel zu
        # frueh beenden (Regression: der noch arbeitende Agent wurde abgebaut,
        # siehe "_arbeitet_noch").
        letzte_pane = ""
        stabil_seit: Optional[float] = None
        while time.time() - start < timeout:
            neu = job.neue_gedanken()
            for gd in neu:
                yield {"art": "gedanke", "text": gd}

            pane = job._pane_text()
            # Pane bewegt sich (neue Gedanken, hochzaehlender Timer, neue Box)
            # oder der Agent arbeitet erkennbar weiter => Stabilitaet numm ab.
            if neu or pane != letzte_pane or _arbeitet_noch(pane):
                stabil_seit = None
            elif "❯" in pane:
                if stabil_seit is None:
                    stabil_seit = time.time()
                elif time.time() - stabil_seit >= _ABSCHLUSS_IDLE_S:
                    boxen = job.alle_antwort_boxen()
                    if boxen:
                        yield {"art": "ergebnis", "text": boxen[-1]}
                        return
            letzte_pane = pane

            if not job.lebt_noch():
                boxen = job.alle_antwort_boxen()
                yield {"art": "ergebnis", "text": boxen[-1] if boxen else "—"}
                return

            time.sleep(1)

        logger.warning("Lokaler Hermes-Auftrag ueberschritt %ds", timeout)
        yield {"art": "fehler", "text": f"Lokaler Hermes brauchte laenger als {timeout}s"}
    finally:
        # Der Job bleibt in der Registry (fuer spaetere Kommentare). Aufgeraumt
        # wird erst, wenn der Auftrag schliesslich abgeschlossen wird.
        pass


def _arbeitet_noch(pane: str) -> bool:
    """True, solange der Agent offensichtlich noch arbeitet.

    Der '❯'-Prompt steht in der Hermes-TUI AUCH während der Arbeit permanent
    unten (die Nachrichten scrollen darüber) — er ist also KEIN verlaessliches
    "fertig"-Signal allein. Als Arbeit gilt stattdessen: Initialisierungs-
    zeile, ein laufender Fortschritts-Timer ('⏱ <n>s' mit n>0) oder eine
    sichtbare Werkzeug-Zeile ohne Prompt am Ende.
    """
    if "Initializing agent" in pane:
        return True
    # Aktiver Denk-/Tool-Timer (Fortschrittszeile unten) => Agent arbeitet.
    if _LIVE_TIMER_ZEILE.search(pane):
        return True
    # Werkzeug-Zeile sichtbar, aber noch kein Prompt am Ende.
    return "💻" in pane and "❯" not in pane