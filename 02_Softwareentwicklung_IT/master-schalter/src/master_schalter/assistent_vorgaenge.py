"""Vorgänge des Wechselassistenten (`assistent.json` im Datenordner).

Ein Vorgang ist ein Masterwechsel eines Themas samt Zustellung an den neuen und den alten
Master. Die Datei ist bewusst **getrennt** von `vorgaenge.json`: Automatik, Legacy-Rückgabe
und `status_zeile` deuten sie nie. Der Vorgang wird dauerhaft vermerkt, **bevor** irgendetwas
geschieht (Write-ahead) – samt Vorzustand (Profil und wörtlicher Markentext), damit eine
Wiederaufnahme nach einem Absturz weiß, was schon passiert ist.

Phasen:
* `vorbereitet`   – vermerkt, vor jeder Nebenwirkung (Vorzustand liegt dabei)
* `rolle_gesetzt` – Profil und Marke `… assistent <thema> <vorgang-id>` stehen
* `sende`         – vermerkt, **bevor** der Transport startet (Absturz hier = unklar, nie neu senden)
* `gesendet`      – Transport nachweislich abgeschickt (Codex-Queue)
* `im_postfach`   – Postfachdatei liegt bereit (Claude/Hermes), noch nicht abgeholt
* `fehler`        – Transport nachweislich nicht gestartet
* `unklar`        – Ergebnis des Transports unbekannt
* `im_chat`       – der Zielchat hat die Nachricht abgeholt (noch keine Übernahme!)
* `bestaetigt`    – der Zielchat hat mit `masterwechsel quittieren <id> neu` übernommen
* `verworfen`     – nichts geschehen bzw. durch einen späteren Wechsel überholt

Die Abgabe des alten Masters wird getrennt über `abgabe_bestaetigt` festgehalten.

Alle Schreibvorgänge laufen über `aendern(funktion)`: die dateiweite (globale) Sperre umschließt
Lesen–Ändern–Schreiben, danach wird atomar ersetzt. Sperrreihenfolge: **Themensperre vor
Dateisperre**, nie umgekehrt; `aendern` darf daher nicht innerhalb von `aendern` aufgerufen werden.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import besitz, modi, paare, zustand
from .signale import _atomar_schreiben, daten_ordner

PHASEN = ("vorbereitet", "rolle_gesetzt", "sende", "gesendet", "im_postfach", "fehler", "unklar",
          "im_chat", "bestaetigt", "verworfen")
ENDGUELTIG = ("bestaetigt", "verworfen")          # danach ändert sich am Vorgang nichts mehr
ARTEN = ("neu", "abgabe")                          # Nachrichtenart bzw. Quittungsart
THEMENSPERRE_FRIST = 1.0


class AssistentFehler(Exception):
    """Vorgang, Marke oder Quittung ist ungültig."""


@dataclass(frozen=True)
class Vorgang:
    id: str
    thema: str
    ziel: str                 # neue Masterrolle
    von: str                  # bisherige Masterrolle (Besitzer der Marke vor dem Wechsel)
    phase: str
    zeit: str                 # ISO-Zeit der letzten Änderung
    vorzustand_profil: dict   # {"master": …, "worker": …, "modell": …} vor dem Wechsel
    vorzustand_marke: str     # wörtlicher Markentext vor dem Wechsel ("" = Datei fehlte)
    fehler: str | None = None
    abgabe_bestaetigt: bool = False


@dataclass(frozen=True)
class Wiederaufnahme:
    """Ergebnis der Wiederaufnahme für einen Vorgang."""
    id: str
    thema: str
    status: str               # verworfen | reparatur | rolle_gesetzt | nachholbar | unklar | nicht_pruefbar
    hinweis: str


def datei() -> Path:
    return daten_ordner() / "assistent.json"


def neue_id(jetzt: datetime | None = None) -> str:
    """Eindeutige Vorgangs-ID nach Muster `^[A-Za-z0-9_-]{1,80}$`: Zeit plus Zufallsanteil."""
    zeit = (jetzt or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return f"{zeit}-{secrets.token_hex(4)}"


def _vorgang(roh: object) -> Vorgang | None:
    if not isinstance(roh, dict):
        return None
    ident, thema, ziel, von = roh.get("id"), roh.get("thema"), roh.get("ziel"), roh.get("von")
    phase, zeit = roh.get("phase"), roh.get("zeit")
    profil, marke = roh.get("vorzustand_profil"), roh.get("vorzustand_marke")
    if not isinstance(ident, str) or modi.VORGANG_ID_MUSTER.fullmatch(ident) is None:
        return None
    try:
        paare.thema_pruefen(thema)  # type: ignore[arg-type]
    except paare.PaarFehler:
        return None
    if not isinstance(ziel, str) or ziel not in modi.ZIEL_ROLLEN:
        return None
    if not isinstance(von, str) or von not in modi.MASTER_WERTE:
        return None
    if not isinstance(phase, str) or phase not in PHASEN:
        return None
    if not isinstance(zeit, str) or not zeit:
        return None
    if not isinstance(profil, dict) or not isinstance(marke, str):
        return None
    fehler, abgabe = roh.get("fehler"), roh.get("abgabe_bestaetigt", False)
    return Vorgang(ident, thema, ziel, von, phase, zeit, dict(profil), marke,
                   fehler if isinstance(fehler, str) else None, abgabe is True)


def lesen(datei_pfad: Path | None = None) -> list[Vorgang]:
    """Fehlende oder kaputte Datei ergibt eine leere Liste; unbrauchbare Einträge werden übersprungen."""
    try:
        roh = json.loads((datei_pfad or datei()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(roh, list):
        return []
    vorgaenge = [v for v in (_vorgang(e) for e in roh) if v is not None]
    return sorted(vorgaenge, key=lambda v: v.id)


def aendern(funktion: Callable[[list[Vorgang]], list[Vorgang]], frist: float = zustand.FRIST_SEKUNDEN,
            datei_pfad: Path | None = None) -> list[Vorgang]:
    """Liste lesen, `funktion` darauf anwenden, atomar zurückschreiben – unter der dateiweiten Sperre.

    Der ganze Lesen–Ändern–Schreiben-Schritt liegt unter derselben Sperre; zwei Themen, die
    gleichzeitig ändern, verlieren so keinen Eintrag. Wirft die Funktion, bleibt die Datei unberührt.
    """
    with zustand.sperre(frist):
        alt = lesen(datei_pfad)
        neu = funktion(alt)
        pfad = datei_pfad or datei()
        if neu != alt or not pfad.exists():
            _atomar_schreiben(pfad, json.dumps([asdict(v) for v in neu], ensure_ascii=False, indent=2))
        return neu


def finden(vorgang_id: str, datei_pfad: Path | None = None) -> Vorgang | None:
    return next((v for v in lesen(datei_pfad) if v.id == vorgang_id), None)


def aktualisieren(vorgang_id: str, datei_pfad: Path | None = None, **felder: object) -> Vorgang | None:
    """Felder eines Vorgangs ändern (Zeit wird neu gesetzt); `None`, wenn er nicht existiert."""
    jetzt = datetime.now(timezone.utc).isoformat()

    def aendere(alt: list[Vorgang]) -> list[Vorgang]:
        return [replace(v, zeit=jetzt, **felder) if v.id == vorgang_id else v for v in alt]  # type: ignore[arg-type]

    aendern(aendere, datei_pfad=datei_pfad)
    return finden(vorgang_id, datei_pfad)


# --- Marke prüfen (G5) -----------------------------------------------------------

def marke_pruefen(thema: str, vorgang_id: str, *, rolle: str | None = None,
                  repo: Path | None = None) -> str | None:
    """Prüft, ob die aktuelle Marke des Themas genau diesen Vorgang trägt.

    Gültig nur bei `… assistent <thema> <vorgang-id>`; mit `rolle` muss zusätzlich der Besitzer
    der Marke diese Rolle sein. Gibt `None` zurück, wenn gültig, sonst den Grund als Text.
    Ein nicht lesbarer Besitzstatus wirft `ModusFehler` (nichts entscheiden, nichts verwerfen).
    """
    _, master_datei = modi._paar_pruefen(thema, repo)
    text = modi._besitz_text_lesen(master_datei)
    marke = besitz.assistent_marke(text)
    if marke is None:
        return "Marke trägt keinen Assistentenvorgang mehr"
    wer, marke_thema, marke_id = marke
    if marke_thema != thema or marke_id != vorgang_id:
        return "Marke gehört zu einem anderen Vorgang (späterer Wechsel)"
    if rolle is not None and wer != rolle:
        return f"Marke nennt {wer}, erwartet wurde {rolle}"
    return None


def quittieren(vorgang_id: str, art: str, repo: Path | None = None,
               datei_pfad: Path | None = None) -> Vorgang:
    """Ausdrückliche Quittung des Zielchats (`neu`) bzw. des alten Chats (`abgabe`).

    Prüft G5 gegen die aktuelle Marke (bei `neu` zusätzlich: Besitzer = Zielrolle) unter der
    Themensperre; eine veraltete Marke lehnt ab, ohne etwas zu ändern.
    """
    if art not in ARTEN:
        raise AssistentFehler(f"Unbekannte Quittungsart: {art!r} (erlaubt: {', '.join(ARTEN)})")
    try:
        modi.vorgang_id_pruefen(vorgang_id)
    except modi.ModusFehler as fehler:
        raise AssistentFehler(str(fehler)) from fehler
    vorgang = finden(vorgang_id, datei_pfad)
    if vorgang is None:
        raise AssistentFehler(f"Vorgang unbekannt: {vorgang_id}")
    try:
        with zustand.thema_sperre(vorgang.thema, blockierend=True, frist=THEMENSPERRE_FRIST) as frei:
            if not frei:
                raise AssistentFehler("Übergabe läuft gerade – gleich erneut quittieren")
            aktuell = finden(vorgang_id, datei_pfad)
            if aktuell is None or aktuell.phase == "verworfen":
                raise AssistentFehler(f"Vorgang {vorgang_id} wurde verworfen – keine Quittung möglich")
            grund = marke_pruefen(aktuell.thema, vorgang_id,
                                  rolle=aktuell.ziel if art == "neu" else None, repo=repo)
            if grund is not None:
                raise AssistentFehler(f"Quittung abgelehnt, Vorgang ist veraltet: {grund}")
            if art == "neu":
                neu = aktualisieren(vorgang_id, datei_pfad, phase="bestaetigt", fehler=None)
            else:
                neu = aktualisieren(vorgang_id, datei_pfad, abgabe_bestaetigt=True)
            if neu is None:
                raise AssistentFehler(f"Vorgang unbekannt: {vorgang_id}")
            return neu
    except (modi.ModusFehler, zustand.SperrFehler) as fehler:
        raise AssistentFehler(str(fehler)) from fehler


# --- Wiederaufnahme (G2) ----------------------------------------------------------

def wiederaufnehmen(repo: Path | None = None, datei_pfad: Path | None = None) -> list[Wiederaufnahme]:
    """Abgebrochene Vorgänge einordnen – beim Fenster-/Leistenstart. **Sendet nie.**

    * `vorbereitet` + Marke unverändert → `verworfen` (nichts geschehen)
    * `vorbereitet` + eigene Zwischenmarke dieses Ziels → Phase bleibt, Status `reparatur`
      (die gleiche Wahl muss erneut übergeben werden)
    * `vorbereitet` + fertige Assistentenmarke mit dieser ID → `rolle_gesetzt`
    * `vorbereitet` + fremd veränderte Marke → `verworfen`
    * `rolle_gesetzt` ohne `sende` → bleibt, Status `nachholbar` (kein Automatismus)
    * `sende` ohne Ergebnis → `unklar` (nie automatisch neu senden)
    """
    ergebnisse: list[Wiederaufnahme] = []
    for vorgang in lesen(datei_pfad):
        if vorgang.phase not in ("vorbereitet", "rolle_gesetzt", "sende"):
            continue
        try:
            with zustand.thema_sperre(vorgang.thema, blockierend=True, frist=THEMENSPERRE_FRIST) as frei:
                if not frei:
                    ergebnisse.append(Wiederaufnahme(vorgang.id, vorgang.thema, "nicht_pruefbar",
                                                     "Thema ist gerade belegt – später erneut prüfen"))
                    continue
                ergebnisse.append(_einordnen(vorgang, repo, datei_pfad))
        except (modi.ModusFehler, zustand.SperrFehler, OSError) as fehler:
            ergebnisse.append(Wiederaufnahme(vorgang.id, vorgang.thema, "nicht_pruefbar", str(fehler)))
    return ergebnisse


def _einordnen(vorgang: Vorgang, repo: Path | None, datei_pfad: Path | None) -> Wiederaufnahme:
    """Einen Vorgang unter der Themensperre einordnen (frisch gelesen, falls inzwischen weiter)."""
    aktuell = finden(vorgang.id, datei_pfad)
    if aktuell is None:
        return Wiederaufnahme(vorgang.id, vorgang.thema, "nicht_pruefbar", "Vorgang nicht mehr vorhanden")
    if aktuell.phase == "sende":
        aktualisieren(aktuell.id, datei_pfad, phase="unklar",
                      fehler="Absturz während der Zustellung – Ergebnis unklar, nicht automatisch erneut gesendet")
        return Wiederaufnahme(aktuell.id, aktuell.thema, "unklar",
                              "Zustellung unklar – bewusst nicht erneut gesendet")
    if aktuell.phase == "rolle_gesetzt":
        return Wiederaufnahme(aktuell.id, aktuell.thema, "nachholbar", "Rolle gesetzt, Zustellung nachholbar")
    if aktuell.phase != "vorbereitet":
        return Wiederaufnahme(aktuell.id, aktuell.thema, "nicht_pruefbar", f"Phase {aktuell.phase} nicht betroffen")
    _, master_datei = modi._paar_pruefen(aktuell.thema, repo)
    text = modi._besitz_text_lesen(master_datei)
    if text == aktuell.vorzustand_marke.strip():
        grund = "Marke unverändert – nichts geschehen"
    elif besitz.assistent_marke(text) == (aktuell.ziel, aktuell.thema, aktuell.id):
        aktualisieren(aktuell.id, datei_pfad, phase="rolle_gesetzt", fehler=None)
        return Wiederaufnahme(aktuell.id, aktuell.thema, "rolle_gesetzt",
                              "Zielmarke stand schon – Rolle gesetzt nachgetragen")
    elif modi.ist_zwischenmarke(text, aktuell.thema) and text.split()[3] == aktuell.ziel:
        meldung = "Reparatur nötig: eigene Zwischenmarke steht – gleiche Wahl erneut übergeben"
        if aktuell.fehler != meldung:
            aktualisieren(aktuell.id, datei_pfad, fehler=meldung)
        return Wiederaufnahme(aktuell.id, aktuell.thema, "reparatur", meldung)
    else:
        grund = "Marke wurde anderweitig geändert – Vorgang überholt"
    aktualisieren(aktuell.id, datei_pfad, phase="verworfen", fehler=grund)
    return Wiederaufnahme(aktuell.id, aktuell.thema, "verworfen", grund)
