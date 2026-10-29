"""Vorgänge des Wechselassistenten (`assistent.json` im Datenordner).

Ein Vorgang ist ein Masterwechsel eines Themas samt Zustellung an den neuen und den alten
Master. Die Datei ist bewusst **getrennt** von `vorgaenge.json`: Automatik, Legacy-Rückgabe
und `status_zeile` deuten sie nie. Der Vorgang wird dauerhaft vermerkt, **bevor** irgendetwas
geschieht (Write-ahead) – samt Vorzustand (Profil und wörtlicher Markentext), damit eine
Wiederaufnahme nach einem Absturz weiß, was schon passiert ist.

Reihenfolge eines Vorgangs (G8): erst gibt der **alte** Master ab, dann wird die Rolle gesetzt,
dann wird dem neuen Master zugestellt. Während der Abgabe gehört die Besitzmarke noch dem alten
Master – sie trägt dann **keine** Vorgangs-ID dieses Assistenten.

Phasen:
* `vorbereitet`         – vermerkt, vor jeder Nebenwirkung (Vorzustand liegt dabei)
* `abgabe_sende`        – vermerkt, **bevor** der Abgabe-Auftrag an den alten Master geht
  (`abgabe_seit` = Beginn der Frist; Absturz hier = unklar, nie neu senden)
* `abgabe_angefragt`    – Abgabe-Auftrag nachweislich abgeschickt bzw. im Postfach, Quittung offen
* `abgabe_unklar`       – Ergebnis des Abgabe-Transports unbekannt, Quittung weiter möglich
* `abgabe_fehler`       – Abgabe-Transport nachweislich nicht gestartet
* `abgegeben`           – der alte Master hat mit `masterwechsel quittieren <id> abgabe` abgegeben
* `abgabe_uebersprungen` – Abgabe nicht abgewartet (Grund in `fehler`); der alte Master bekommt
  stattdessen eine Info
* `rolle_gesetzt`       – Profil und Marke `… assistent <thema> <vorgang-id>` stehen
* `sende`               – vermerkt, **bevor** der Transport startet (Absturz hier = unklar, nie neu senden)
* `gesendet`            – Transport nachweislich abgeschickt (Codex-Queue)
* `im_postfach`         – Postfachdatei liegt bereit (Claude/Hermes/Antigravity), noch nicht abgeholt
* `fehler`              – Transport nachweislich nicht gestartet
* `unklar`              – Ergebnis des Transports unbekannt
* `im_chat`             – der Zielchat hat die Nachricht abgeholt (noch keine Übernahme!)
* `bestaetigt`          – der Zielchat hat mit `masterwechsel quittieren <id> neu` übernommen
* `verworfen`           – nichts geschehen bzw. durch einen späteren Wechsel überholt

Die Abgabe des alten Masters steht zusätzlich im Feld `abgabe` (`abgegeben` | `uebersprungen`) und
bleibt nach den späteren Phasen erhalten. `von_chat` / `nach_chat` (`{"werkzeug": …, "kennung": …}` oder
`None`) nennen den alten und den neuen Chat; die Kennungen stehen **nur** in dieser lokalen Datei (G9) –
nie in Nachrichtentexten, im Protokoll oder in Ausgaben. Alte Dateien ohne diese Felder lesen weiter. `abgabe_seit` ist die Zeit von `abgabe_sende` (Grundlage
der Frist), `abgabe_zugestellt` die Zeit, zu der der alte Chat Auftrag bzw. Info abgeholt hat.
Phasenwechsel, die nur aus bestimmten Phasen heraus gelten sollen, macht `phase_wechseln`
(Vergleich-und-Setzen unter der Dateisperre).

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

from . import besitz, modi, paare, protokoll, zustand
from .signale import _atomar_schreiben, daten_ordner

PHASEN = ("vorbereitet", "abgabe_sende", "abgabe_angefragt", "abgabe_unklar", "abgabe_fehler", "abgegeben",
          "abgabe_uebersprungen", "rolle_gesetzt", "sende", "gesendet", "im_postfach", "fehler", "unklar",
          "im_chat", "bestaetigt", "verworfen")
ABGABE_OFFEN = ("abgabe_sende", "abgabe_angefragt", "abgabe_unklar")   # Abgabe-Quittung des alten Masters möglich
ABGABE_FRISTBAR = (*ABGABE_OFFEN, "abgabe_fehler")        # hier läuft die 10-Minuten-Frist (abgabe_fehler: keine Quittung)
ABGABE_UEBERSPRINGBAR = ("vorbereitet", *ABGABE_FRISTBAR)  # Phasen, aus denen die Abgabe übersprungen werden darf
# Solange die Rolle noch nicht gesetzt ist oder gerade gesendet wird, blockiert ein Vorgang einen neuen Wechsel
# desselben Themas. Ab `rolle_gesetzt` überschreibt jeder spätere Wechsel die Marke (G3) und macht ihn ungültig.
WECHSEL_BLOCKIEREND = (*ABGABE_UEBERSPRINGBAR, "abgegeben", "abgabe_uebersprungen", "sende")
# Phasen, die ein späterer, erfolgreich gesetzter Wechsel desselben Themas als „überholt“ verwirft.
UEBERHOLBAR = ("rolle_gesetzt", "gesendet", "im_postfach", "im_chat", "unklar", "fehler")
ENDGUELTIG = ("bestaetigt", "verworfen")          # danach ändert sich am Vorgang nichts mehr
# Von Hand abbrechbar nur, solange die Rolle noch nicht gesetzt ist (ab `rolle_gesetzt` gilt die Marke und
# nur ein späterer Wechsel macht den Vorgang ungültig). `sende` gehört nicht dazu: es steht schon nach dem Rollensetzen.
ABBRECHBAR = (*ABGABE_UEBERSPRINGBAR, "abgegeben", "abgabe_uebersprungen")
ABBRUCH_GRUND = "von Hand abgebrochen"
GRUND_MAX = 200                                    # längere Gründe zeigt das Fenster gekürzt
ARTEN = ("neu", "abgabe")                          # Quittungsarten (Nachrichtenarten: `postfach.NACHRICHTEN`)
ABGABE_WERTE = ("abgegeben", "uebersprungen")      # mögliche Werte des Feldes `abgabe`
ABGABE_ERGEBNISSE = ("abgabe_angefragt", "abgabe_fehler", "abgabe_unklar")
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
    abgabe: str | None = None             # "abgegeben" | "uebersprungen"; bleibt nach späteren Phasen erhalten
    abgabe_seit: str | None = None        # ISO-Zeit von `abgabe_sende` (Beginn der 10-Minuten-Frist)
    abgabe_zugestellt: str | None = None  # ISO-Zeit der Abholung von Abgabe-Auftrag bzw. -Info
    von_chat: dict | None = None          # {"werkzeug": …, "kennung": …} des alten Chats (nur lokal, G9)
    nach_chat: dict | None = None         # {"werkzeug": …, "kennung": …} des neuen Chats (nur lokal, G9)
    ablauf_version: int = 1
    abgabe_modus: str = "frist"
    abgabe_nachweis: dict | None = None


@dataclass(frozen=True)
class Wiederaufnahme:
    """Ergebnis der Wiederaufnahme für einen Vorgang."""
    id: str
    thema: str
    status: str               # verworfen | reparatur | rolle_gesetzt | nachholbar | unklar | abgabe_offen | nicht_pruefbar
    hinweis: str


def datei() -> Path:
    return daten_ordner() / "assistent.json"


def neue_id(jetzt: datetime | None = None) -> str:
    """Eindeutige Vorgangs-ID nach Muster `^[A-Za-z0-9_-]{1,80}$`: Zeit plus Zufallsanteil."""
    zeit = (jetzt or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return f"{zeit}-{secrets.token_hex(4)}"


def chat_dict(roh: object) -> dict | None:
    """Chat-Referenz streng prüfen: genau `werkzeug` (claude|codex|hermes|agy) und `kennung` nach G6-Muster, sonst `None`."""
    if not isinstance(roh, dict) or set(roh) != {"werkzeug", "kennung"}:
        return None
    werkzeug, kennung = roh["werkzeug"], roh["kennung"]
    if not isinstance(werkzeug, str) or werkzeug not in modi.ZIEL_ROLLEN:
        return None
    if not isinstance(kennung, str) or modi.VORGANG_ID_MUSTER.fullmatch(kennung) is None:
        return None
    return {"werkzeug": werkzeug, "kennung": kennung}


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
    legacy = ("ablauf_version" not in roh and "abgabe_modus" not in roh
              and "abgabe_nachweis" not in roh)
    if legacy:
        version, modus = 0, "frist"
    else:
        version, modus = roh.get("ablauf_version"), roh.get("abgabe_modus")
        if (type(version) is not int or version not in (0, 1) or not isinstance(modus, str)
                or modus not in ("frist", "warten") or (version == 0 and modus != "frist")):
            return None
    nachweis = roh.get("abgabe_nachweis")
    if version == 0 and nachweis is not None:
        return None
    if nachweis is not None:
        if (not isinstance(nachweis, dict) or set(nachweis) != {"head", "kopfzeit", "datei_sha256", "geprueft_zeit"}
                or not all(isinstance(nachweis.get(k), str) and nachweis[k] for k in nachweis)
                or not isinstance(nachweis.get("head"), str)
                or not 40 <= len(nachweis["head"]) <= 64
                or any(c not in "0123456789abcdefABCDEF" for c in nachweis["head"])
                or len(nachweis["datei_sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in nachweis["datei_sha256"])):
            return None
        try:
            datetime.fromisoformat(nachweis["kopfzeit"].replace("Z", "+00:00"))
            datetime.fromisoformat(nachweis["geprueft_zeit"].replace("Z", "+00:00"))
        except ValueError:
            return None
    elif "abgabe_nachweis" in roh and roh["abgabe_nachweis"] is not None:
        return None
    fehler, abgabe = roh.get("fehler"), roh.get("abgabe")
    seit, zugestellt = roh.get("abgabe_seit"), roh.get("abgabe_zugestellt")
    if "fehler" in roh and fehler is not None and not isinstance(fehler, str):
        return None
    if "abgabe" in roh and abgabe is not None and abgabe not in ABGABE_WERTE:
        return None
    if "abgabe_seit" in roh and seit is not None and not isinstance(seit, str):
        return None
    if "abgabe_zugestellt" in roh and zugestellt is not None and not isinstance(zugestellt, str):
        return None
    for feld in ("von_chat", "nach_chat"):
        if feld in roh and roh[feld] is not None and chat_dict(roh[feld]) is None:
            return None
    return Vorgang(ident, thema, ziel, von, phase, zeit, dict(profil), marke,
                   fehler if isinstance(fehler, str) else None,
                   abgabe if abgabe in ABGABE_WERTE else None,
                   seit if isinstance(seit, str) else None,
                   zugestellt if isinstance(zugestellt, str) else None,
                   chat_dict(roh.get("von_chat")), chat_dict(roh.get("nach_chat")), version, modus, nachweis)


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


def lesen_geprueft(datei_pfad: Path | None = None) -> list[Vorgang]:
    """Vorgänge streng lesen: nur eine fehlende Datei ist ein gültig leerer Bestand.

    Anders als `lesen` wird ein beschädigter Bestand nicht still verkürzt. Er kann sonst eine
    laufende Übergabe verbergen und eine neue Auswahl fälschlich freigeben.
    """
    pfad = datei_pfad or datei()
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError, UnicodeError) as fehler:
        raise AssistentFehler("Wechselregister ist nicht lesbar oder beschädigt") from fehler
    if not isinstance(roh, list):
        raise AssistentFehler("Wechselregister hat kein gültiges Listenformat")

    vorgaenge: list[Vorgang] = []
    ids: set[str] = set()
    for position, eintrag in enumerate(roh, start=1):
        vorgang = _vorgang(eintrag)
        if vorgang is None:
            raise AssistentFehler(f"Wechselregister enthält einen ungültigen Vorgang an Position {position}")
        if vorgang.id in ids:
            raise AssistentFehler(f"Wechselregister enthält eine doppelte Vorgangskennung an Position {position}")
        ids.add(vorgang.id)
        vorgaenge.append(vorgang)
    return sorted(vorgaenge, key=lambda v: v.id)


@dataclass(frozen=True)
class RegisterDiagnose:
    status: str
    sha256: str | None
    ungueltige_positionen: tuple[int, ...] = ()
    doppelte_positionen: tuple[int, ...] = ()


def register_diagnose(datei_pfad: Path | None = None) -> RegisterDiagnose:
    """Nicht schreibende, inhaltsfreie Diagnose für das lokale Assistentenregister."""
    pfad = datei_pfad or datei()
    try:
        daten = pfad.read_bytes()
    except FileNotFoundError:
        return RegisterDiagnose("fehlend", None)
    except OSError:
        return RegisterDiagnose("beschädigt", None)
    import hashlib
    fingerprint = hashlib.sha256(daten).hexdigest()
    try:
        roh = json.loads(daten.decode("utf-8"))
    except (ValueError, UnicodeError):
        return RegisterDiagnose("beschädigt", fingerprint)
    if not isinstance(roh, list):
        return RegisterDiagnose("beschädigt", fingerprint)
    ungültig: list[int] = []
    doppelt: list[int] = []
    ids: set[str] = set()
    for position, eintrag in enumerate(roh, start=1):
        vorgang = _vorgang(eintrag)
        if vorgang is None:
            ungültig.append(position)
        elif vorgang.id in ids:
            doppelt.append(position)
        else:
            ids.add(vorgang.id)
    return RegisterDiagnose("beschädigt" if ungültig or doppelt else "lesbar", fingerprint,
                            tuple(ungültig), tuple(doppelt))


def aendern(funktion: Callable[[list[Vorgang]], list[Vorgang]], frist: float = zustand.FRIST_SEKUNDEN,
            datei_pfad: Path | None = None) -> list[Vorgang]:
    """Liste lesen, `funktion` darauf anwenden, atomar zurückschreiben – unter der dateiweiten Sperre.

    Der ganze Lesen–Ändern–Schreiben-Schritt liegt unter derselben Sperre; zwei Themen, die
    gleichzeitig ändern, verlieren so keinen Eintrag. Wirft die Funktion, bleibt die Datei unberührt.
    """
    with zustand.sperre(frist):
        alt = lesen_geprueft(datei_pfad)
        neu = funktion(alt)
        pfad = datei_pfad or datei()
        if neu != alt or not pfad.exists():
            _atomar_schreiben(pfad, json.dumps([asdict(v) for v in neu], ensure_ascii=False, indent=2))
        return neu


def finden(vorgang_id: str, datei_pfad: Path | None = None) -> Vorgang | None:
    return next((v for v in lesen_geprueft(datei_pfad) if v.id == vorgang_id), None)


def aktualisieren(vorgang_id: str, datei_pfad: Path | None = None, **felder: object) -> Vorgang | None:
    """Felder eines Vorgangs ändern (Zeit wird neu gesetzt); `None`, wenn er nicht existiert."""
    jetzt = datetime.now(timezone.utc).isoformat()

    def aendere(alt: list[Vorgang]) -> list[Vorgang]:
        return [replace(v, zeit=jetzt, **felder) if v.id == vorgang_id else v for v in alt]  # type: ignore[arg-type]

    aendern(aendere, datei_pfad=datei_pfad)
    return finden(vorgang_id, datei_pfad)


def phase_gewinnen(vorgang_id: str, von: tuple[str, ...], nach: str, datei_pfad: Path | None = None,
                   **felder: object) -> tuple[Vorgang | None, bool]:
    """Wie `phase_wechseln`, meldet aber zusätzlich, ob **dieser** Aufruf den Wechsel gemacht hat.

    Rückgabe `(Vorgang nach dem Schritt oder None, gewonnen)`. `gewonnen` ist nur dann wahr, wenn die
    Phase unter der Dateisperre tatsächlich in `von` lag und von diesem Aufruf gesetzt wurde. Nur wer
    gewinnt, darf die zum Wechsel gehörende Nebenwirkung (Senden) auslösen – ein zweiter Prozess, der
    zeitgleich denselben Wechsel versucht, verliert und sendet nichts.
    """
    if nach not in PHASEN:
        raise AssistentFehler(f"Unbekannte Phase: {nach!r}")
    jetzt = datetime.now(timezone.utc).isoformat()
    gewonnen: list[bool] = []

    def wechsle(alt: list[Vorgang]) -> list[Vorgang]:
        neu: list[Vorgang] = []
        for v in alt:
            if v.id == vorgang_id and v.phase in von:
                gewonnen.append(True)
                neu.append(replace(v, phase=nach, zeit=jetzt, **felder))  # type: ignore[arg-type]
            else:
                neu.append(v)
        return neu

    liste = aendern(wechsle, datei_pfad=datei_pfad)
    return next((v for v in liste if v.id == vorgang_id), None), bool(gewonnen)


def phase_wechseln(vorgang_id: str, von: tuple[str, ...], nach: str, datei_pfad: Path | None = None,
                   **felder: object) -> Vorgang | None:
    """Vergleich-und-Setzen: ändert nur, wenn die aktuelle Phase in `von` liegt (Zeit wird neu gesetzt).

    Prüfung und Änderung liegen unter derselben Dateisperre; ein Wettlauf überschreibt so keine
    weiterreichende Phase. Gibt den Vorgang **nach** dem Schritt zurück – auch unverändert, wenn die
    Phase nicht in `von` lag –, `None`, wenn er nicht existiert.
    """
    return phase_gewinnen(vorgang_id, von, nach, datei_pfad, **felder)[0]


def abgabe_beginnen(vorgang_id: str, datei_pfad: Path | None = None) -> Vorgang | None:
    """`vorbereitet` → `abgabe_sende`; `abgabe_seit` = jetzt (Beginn der Frist). Vermerk **vor** dem Senden."""
    return phase_wechseln(vorgang_id, ("vorbereitet",), "abgabe_sende", datei_pfad,
                          abgabe_seit=datetime.now(timezone.utc).isoformat())


def abgabe_ergebnis(vorgang_id: str, ergebnis: str, datei_pfad: Path | None = None) -> Vorgang | None:
    """Transportergebnis der Abgabe festhalten – nur aus `abgabe_sende`.

    `ergebnis` ∈ `abgabe_angefragt` | `abgabe_fehler` | `abgabe_unklar`. Hat der alte Master schon
    quittiert (`abgegeben`) oder ging der Vorgang anders weiter, bleibt die Phase unverändert.
    """
    if ergebnis not in ABGABE_ERGEBNISSE:
        raise AssistentFehler(f"Unbekanntes Abgabe-Ergebnis: {ergebnis!r} (erlaubt: {', '.join(ABGABE_ERGEBNISSE)})")
    return phase_wechseln(vorgang_id, ("abgabe_sende",), ergebnis, datei_pfad)


def abgabe_ueberspringen(vorgang_id: str, grund: str, datei_pfad: Path | None = None) -> Vorgang | None:
    """Legacy-Abgabe nicht abwarten; `warten` wird im gesperrten Callback sicher abgelehnt.

    Setzt `abgabe="uebersprungen"` und vermerkt den Grund in `fehler`.
    """
    ausgang: list[Vorgang] = []

    def aendere(alt: list[Vorgang]) -> list[Vorgang]:
        neu: list[Vorgang] = []
        for v in alt:
            if v.id == vorgang_id:
                if v.abgabe_modus == "warten":
                    raise AssistentFehler("Abgabe wird geprüft abgewartet und kann nicht übersprungen werden")
                if v.phase in ABGABE_UEBERSPRINGBAR:
                    v = replace(v, phase="abgabe_uebersprungen", zeit=datetime.now(timezone.utc).isoformat(),
                                abgabe="uebersprungen", fehler=grund)
                    ausgang.append(v)
            neu.append(v)
        return neu

    aendern(aendere, datei_pfad=datei_pfad)
    return ausgang[0] if ausgang else finden(vorgang_id, datei_pfad)


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
               datei_pfad: Path | None = None, *, jetzt: datetime | None = None,
               git: Callable[[Path, list[str]], str] | None = None) -> Vorgang:
    """Ausdrückliche Quittung des Zielchats (`neu`) bzw. des alten Chats (`abgabe`).

    Beides läuft unter der Themensperre; eine veraltete Marke lehnt ab, ohne etwas zu ändern.
    * `neu`: G5 – die Marke muss genau diesen Vorgang tragen und dem Ziel gehören → `bestaetigt`.
    * `abgabe`: gültig nur in einer Phase aus `ABGABE_OFFEN` (auch `abgabe_sende`, also schon vor dem
      Transportergebnis) und solange der aktuelle Markentext (gestrippt) dem Vorzustand des Vorgangs
      entspricht – die Marke gehört während der Abgabe noch dem alten Master und trägt keine
      Vorgangs-ID. Dann → `abgegeben`, Feld `abgabe="abgegeben"`.
    """
    if art not in ARTEN:
        # Ungeprüfte Eingaben und fremde Texte (Pfade, Markeninhalt) nie wiederholen – die Ausgabe landet
        # im quittierenden Chat (Prüfung P4 R7).
        raise AssistentFehler(f"Unbekannte Quittungsart (erlaubt: {', '.join(ARTEN)})")
    try:
        modi.vorgang_id_pruefen(vorgang_id)
    except modi.ModusFehler as fehler:
        raise AssistentFehler(f"Vorgangskennung unzulässig (erlaubt: {modi.VORGANG_ID_MUSTER.pattern})") from fehler
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
            if art == "neu":
                grund = marke_pruefen(aktuell.thema, vorgang_id, rolle=aktuell.ziel, repo=repo)
                if grund is not None:
                    raise AssistentFehler("Quittung abgelehnt, Vorgang ist veraltet: Marke gehört nicht mehr "
                                          "zu diesem Vorgang")
                neu = aktualisieren(vorgang_id, datei_pfad, phase="bestaetigt", fehler=None)
            else:
                neu = _abgabe_quittieren(aktuell, repo, datei_pfad, jetzt or datetime.now(timezone.utc), git)
            if neu is None:
                raise AssistentFehler(f"Vorgang unbekannt: {vorgang_id}")
            return neu
    except (modi.ModusFehler, zustand.SperrFehler, OSError) as fehler:
        raise AssistentFehler(f"Quittung gerade nicht möglich ({type(fehler).__name__})") from fehler


def _abgabe_quittieren(vorgang: Vorgang, repo: Path | None, datei_pfad: Path | None, jetzt: datetime,
                       git: Callable[[Path, list[str]], str] | None = None) -> Vorgang | None:
    """Abgabe-Quittung unter gehaltener Themensperre prüfen und `abgegeben` setzen (sonst `AssistentFehler`)."""
    nachbeleg = vorgang.abgabe_modus == "warten" and vorgang.phase == "abgegeben"
    if vorgang.phase not in ABGABE_OFFEN and not nachbeleg:
        raise AssistentFehler(f"Quittung abgelehnt: Abgabe ist nicht offen (Phase {vorgang.phase})")
    _, master_datei = modi._paar_pruefen(vorgang.thema, repo)
    if modi._besitz_text_lesen(master_datei) != vorgang.vorzustand_marke.strip():
        raise AssistentFehler("Quittung abgelehnt, Vorgang ist veraltet: Marke hat sich geändert")
    felder: dict[str, object] = {"abgabe": "abgegeben", "fehler": None}
    if vorgang.abgabe_modus == "warten":
        try:
            from .abgabe_nachweis import pruefen
            felder["abgabe_nachweis"] = pruefen(vorgang.thema, vorgang, repo, jetzt, git=git).als_dict()
        except Exception as fehler:
            protokoll.schreiben(vorgang.id, vorgang.thema, "abgabe_pruefung_abgelehnt", "Nachweis ungültig")
            raise AssistentFehler("Abgabe nicht bestätigt: geprüfter Übergabekopf fehlt oder ist ungültig") from fehler
    if nachbeleg:
        ausgang: list[Vorgang] = []
        zeit = datetime.now(timezone.utc).isoformat()

        def erneuern(alt: list[Vorgang]) -> list[Vorgang]:
            neu_liste = []
            for aktuell in alt:
                if aktuell.id == vorgang.id and aktuell.phase == "abgegeben" and aktuell.abgabe_modus == "warten":
                    neu = replace(aktuell, abgabe_nachweis=felder["abgabe_nachweis"], fehler=None, zeit=zeit)
                    ausgang.append(neu)
                    neu_liste.append(neu)
                else:
                    neu_liste.append(aktuell)
            return neu_liste

        aendern(erneuern, datei_pfad=datei_pfad)
        if not ausgang:
            raise AssistentFehler("Abgabequittung konnte nicht erneuert werden")
        protokoll.schreiben(vorgang.id, vorgang.thema, "abgabe_nachweis_erneuert", "geprüft")
        return ausgang[0]
    neu, gewonnen = phase_gewinnen(vorgang.id, ABGABE_OFFEN, "abgegeben", datei_pfad, **felder)
    if neu is not None and neu.phase != "abgegeben":
        raise AssistentFehler(f"Quittung abgelehnt: Abgabe ist nicht mehr offen (Phase {neu.phase})")
    if gewonnen and vorgang.abgabe_modus == "warten":
        protokoll.schreiben(vorgang.id, vorgang.thema, "abgabe_geprueft", "Nachweis gültig")
    return neu


def abbrechen(vorgang_id: str, datei_pfad: Path | None = None) -> Vorgang:
    """Einen Vorgang von Hand abbrechen (Fenster, Knopf „Abbrechen“) – nur **vor** `rolle_gesetzt`.

    Läuft unter der Themensperre (blockierend, kurze Frist): so kann `assistent.fortsetzen` nicht gleichzeitig
    die Rolle setzen und danach von diesem Abbruch überholt werden. Der Wechsel ist Vergleich-und-Setzen aus
    `ABBRECHBAR` nach `verworfen` mit dem Grund `ABBRUCH_GRUND`; liegende Postfachdateien werden dadurch nach
    G5 beim Abholen verworfen. Ein Protokolleintrag hält den Abbruch fest. Ist die Phase schon weiter oder
    der Vorgang schon endgültig, wirft die Funktion `AssistentFehler` und ändert nichts. Die Meldungen nennen
    nur feste Wörter und Phasennamen – nie eine Kennung außer der geprüften Vorgangs-ID.
    """
    try:
        modi.vorgang_id_pruefen(vorgang_id)
    except modi.ModusFehler as fehler:
        raise AssistentFehler(f"Vorgangskennung unzulässig (erlaubt: {modi.VORGANG_ID_MUSTER.pattern})") from fehler
    vorgang = finden(vorgang_id, datei_pfad)
    if vorgang is None:
        raise AssistentFehler(f"Vorgang unbekannt: {vorgang_id}")
    try:
        with zustand.thema_sperre(vorgang.thema, blockierend=True, frist=THEMENSPERRE_FRIST) as frei:
            if not frei:
                raise AssistentFehler("Übergabe läuft gerade – gleich erneut abbrechen")
            neu, gewonnen = phase_gewinnen(vorgang_id, ABBRECHBAR, "verworfen", datei_pfad, fehler=ABBRUCH_GRUND)
            if neu is None:
                raise AssistentFehler(f"Vorgang unbekannt: {vorgang_id}")
            if not gewonnen:
                raise AssistentFehler(f"Abbrechen nicht mehr möglich (Phase {neu.phase})")
            protokoll.schreiben(neu.id, neu.thema, "verworfen", ABBRUCH_GRUND)
            return neu
    except (zustand.SperrFehler, OSError) as fehler:
        raise AssistentFehler(f"Abbrechen gerade nicht möglich ({type(fehler).__name__})") from fehler


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
    * `abgabe_sende` ohne Ergebnis → `abgabe_unklar` (Status `unklar`, nie neu senden; `abgabe_seit`
      bleibt, die Frist läuft weiter)
    * `abgabe_angefragt` / `abgabe_unklar` → Phase bleibt, Status `abgabe_offen` (Frist läuft seit `abgabe_seit`)
    * `abgabe_fehler` → Phase bleibt, Status `abgabe_offen` (Transport nicht gestartet; nach der Frist wird übersprungen)
    * `abgegeben` / `abgabe_uebersprungen` → Phase bleibt, Status `nachholbar` (Rolle noch nicht gesetzt)
    """
    ergebnisse: list[Wiederaufnahme] = []
    for vorgang in lesen_geprueft(datei_pfad):
        if vorgang.phase not in ("vorbereitet", *ABGABE_OFFEN, "abgabe_fehler", "abgegeben", "abgabe_uebersprungen",
                                 "rolle_gesetzt", "sende"):
            continue
        try:
            with zustand.thema_sperre(vorgang.thema, blockierend=True, frist=THEMENSPERRE_FRIST) as frei:
                if not frei:
                    ergebnisse.append(Wiederaufnahme(vorgang.id, vorgang.thema, "nicht_pruefbar",
                                                     "Thema ist gerade belegt – später erneut prüfen"))
                    continue
                ergebnisse.append(_einordnen(vorgang, repo, datei_pfad))
        except (AssistentFehler, modi.ModusFehler, zustand.SperrFehler, OSError):
            ergebnisse.append(Wiederaufnahme(vorgang.id, vorgang.thema, "nicht_pruefbar",
                                             "Register oder Vorgang nicht prüfbar; keine automatische Änderung"))
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
    if aktuell.phase == "abgabe_sende":
        fehler = "Absturz während der Abgabe-Zustellung – nicht automatisch erneut gesendet"
        neu = phase_wechseln(aktuell.id, ("abgabe_sende",), "abgabe_unklar", datei_pfad, fehler=fehler)
        if neu is None or neu.phase == "abgabe_unklar":
            return Wiederaufnahme(aktuell.id, aktuell.thema, "unklar",
                                  "Abgabe-Zustellung unklar – bewusst nicht erneut gesendet")
        aktuell = neu             # inzwischen weiter (z. B. quittiert): unten neu einordnen
    if aktuell.phase == "abgabe_fehler" and aktuell.abgabe_modus == "warten":
        return Wiederaufnahme(aktuell.id, aktuell.thema, "abgabe_offen",
                              "Abgabe offen – wartet auf geprüfte Abgabe, kein automatisches Übergehen")
    if aktuell.phase == "abgabe_fehler":
        return Wiederaufnahme(aktuell.id, aktuell.thema, "abgabe_offen",
                              f"Abgabe-Transport nicht gestartet – Frist läuft seit {aktuell.abgabe_seit or aktuell.zeit}, "
                              "danach wird die Abgabe übersprungen")
    if aktuell.phase in ("abgabe_angefragt", "abgabe_unklar") and aktuell.abgabe_modus == "warten":
        return Wiederaufnahme(aktuell.id, aktuell.thema, "abgabe_offen",
                              "Abgabe offen – wartet auf geprüfte Abgabe, kein automatisches Übergehen")
    if aktuell.phase in ("abgabe_angefragt", "abgabe_unklar"):
        return Wiederaufnahme(aktuell.id, aktuell.thema, "abgabe_offen",
                              f"Abgabe offen – Frist läuft seit {aktuell.abgabe_seit}")
    if aktuell.phase in ("abgegeben", "abgabe_uebersprungen"):
        return Wiederaufnahme(aktuell.id, aktuell.thema, "nachholbar", "Abgabe erledigt, Rolle noch nicht gesetzt")
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
