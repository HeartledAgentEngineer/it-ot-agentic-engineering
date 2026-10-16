"""Automatische Übergabe Claude → Codex: Entscheidung und Ablauf.

**Entscheidung** (`faellige`, rein): Nur wenn die Automatik an ist, die Claude-Messung frisch
(≤ 10 min) und im Limit ist **und** Codex gemessen frei ist, entsteht je Paar und Limitfenster
genau ein Auftrag. Kennung ist `<thema>@<Rücksetzzeit des auslösenden Fensters>` – eine bereits
vorhandene Kennung (egal in welcher Phase) wird nie erneut gesendet.

**Ablauf** (`lauf`, je Thema unter der Themensperre):

1. Kopfzeile der laufenden Übergabe prüfen (`Übergabebereit: ja`, Zeit ≤ 2 h, HEAD-Kurzform als
   exakter Präfix der aktuellen HEAD). Sonst kein Vorgang, Status „wartet auf Übergabepunkt".
2. Eine verwaiste eigene Reservierung (`reserviert <lauf-id> <Zeit>`, zu der **kein** dauerhafter
   Vorgang existiert) wird zurückgesetzt – der Vorgänger war vor dem Versand beendet.
3. Reservieren (`reserviert <lauf-id> <Zeit>`), 30 s warten, **danach** Kopfzeile erneut lesen:
   nur wenn weiterhin `ja`, HEAD passend und der Kopfzeilen-Zeitstempel **älter als die
   Reservierung** ist, wird gesendet. Sonst zurück auf `claude <Zeit>`, kein Vorgang.
4. Unmittelbar vor dem Senden prüfen, dass die Besitzdatei noch genau die eigene Reservierung
   trägt; sonst Abbruch ohne Vorgang.

Die **globale** Zustandssperre wird nie während der 30-Sekunden-Wartezeit gehalten.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import ack, anzeige, besitz, codex_senden, modi, paare, rollen, signale, uebergabe, vorgaenge, zustand
from .auftrag import Auftrag

FRIST_KOPFZEILE = timedelta(hours=2)
FRIST_MESSUNG = timedelta(minutes=10)
FRIST_BESTAETIGUNG = timedelta(minutes=15)
WARTE_SEKUNDEN = 30

KOPFZEILE = re.compile(r"Übergabebereit: (ja|nein) · ([^·]+?) · ([0-9A-Fa-f]{7,12})\s*$")
KOPF_PRAEFIX = "Übergabebereit:"

STATUS_AUS = "Automatik aus"
STATUS_CLAUDE_MESSUNG = "Aktuelle Claude-Messung fehlt"
STATUS_CODEX_MESSUNG = "Aktuelle Codex-Messung fehlt"
STATUS_KEIN_LIMIT = "Claude nicht im Limit"
STATUS_UEBERGABEPUNKT = "wartet auf Übergabepunkt"
STATUS_VERALTET = "Übergabepunkt veraltet – Kopfzeile erneuern"
STATUS_CLAUDE_HOERT = "Claude arbeitet – später"
STATUS_RESERVIERT = "Übergabe läuft (Reservierung offen) – bitte prüfen"
STATUS_CODEX_MASTER = "Codex hat übernommen"
STATUS_UNKLAR = "Zustellung unklar – Besitz bleibt Codex, bitte prüfen"


@dataclass(frozen=True)
class Messung:
    claude: signale.Kontingent
    codex: signale.Kontingent


@dataclass(frozen=True)
class Stand:
    thema: str
    status: str
    phase: str | None = None


# --- Kopfzeile und HEAD -------------------------------------------------------

def kopf_hash(repo: Path, git: Callable[[Path, list[str]], str] | None = None) -> str:
    """Aktueller HEAD als voller Hash; leer, wenn Git nicht lesbar ist."""
    try:
        return (git or uebergabe._git)(repo, ["rev-parse", "HEAD"]).strip()
    except (uebergabe.GitFehler, OSError):
        return ""


def kopfzeile_lesen(pfad: Path) -> tuple[str, datetime, str] | None:
    """Erste Zeile der laufenden Übergabe als (Bereitschaft, Zeit, HEAD-Kurzform) – sonst None.

    Gelesen wird **nur die erste Zeile**; der restliche Dateiinhalt wird nie ausgewertet.
    """
    try:
        with pfad.open(encoding="utf-8", errors="replace") as f:
            zeile = f.readline().rstrip("\n\r")
    except OSError:
        return None
    treffer = KOPFZEILE.match(zeile)
    if treffer is None:
        return None
    zeit = signale._iso(treffer.group(2).strip())
    if zeit is None:
        return None
    return treffer.group(1), zeit, treffer.group(3)


def head_passt(kurzform: str, head: str) -> bool:
    """Die Kurzform (7–12 Hexzeichen) muss exakter Präfix des aktuellen HEAD sein."""
    if not 7 <= len(kurzform) <= 12 or not head:
        return False
    return head.lower().startswith(kurzform.lower())


def uebergabepunkt(pfad: Path, head: str, jetzt: datetime,
                   vor: datetime | None = None) -> tuple[bool, str]:
    """Ist der Übergabepunkt gültig? `vor` verlangt zusätzlich einen Zeitstempel älter als diese Zeit."""
    kopf = kopfzeile_lesen(pfad)
    if kopf is None:
        return False, STATUS_VERALTET
    bereit, zeit, kurz = kopf
    if bereit != "ja":
        return False, STATUS_UEBERGABEPUNKT
    if jetzt - zeit > FRIST_KOPFZEILE:
        return False, STATUS_VERALTET
    if vor is not None and zeit >= vor:
        return False, STATUS_VERALTET
    if not head_passt(kurz, head):
        return False, STATUS_VERALTET
    return True, ""


# --- Entscheidung -------------------------------------------------------------

def _gueltiges_fenster(f: signale.Fenster | None, jetzt: datetime) -> signale.Fenster | None:
    """Das Fenster, wenn es gemessen, im Bereich 0–100, nicht zurückgesetzt und Reset in der Zukunft liegt.

    Ausnahme (API-Form 16.10.2026): gemessene 0 % ohne Rücksetzzeit (Fenster nicht aktiv) ist gültig.
    """
    if f is None or f.prozent is None or f.zurueckgesetzt:
        return None
    if not 0 <= f.prozent <= 100:   # ungültige Messung zählt als unbekannt, nie als Freiheit
        return None
    if f.prozent == 0 and f.reset is None:
        return f
    if f.reset is None or f.reset <= jetzt:
        return None
    return f


def _messung_frisch(stand: datetime | None, jetzt: datetime) -> bool:
    return stand is not None and timedelta(0) <= jetzt - stand <= FRIST_MESSUNG


def _claude_im_limit(claude: signale.Kontingent, schwelle: int, jetzt: datetime):
    """(im Limit?, auslösendes Fenster) – nur bei frischer Messung und beiden gültigen Fenstern."""
    if claude.fehler or not _messung_frisch(claude.stand, jetzt):
        return False, None
    fuenf = _gueltiges_fenster(claude.fenster_nach_name("5h"), jetzt)
    woche = _gueltiges_fenster(claude.fenster_nach_name("Woche"), jetzt)
    if fuenf is None or woche is None:
        return False, None
    if fuenf.prozent >= schwelle:
        return True, fuenf
    if woche.prozent >= schwelle:
        return True, woche
    return False, None


def _codex_frei(codex: signale.Kontingent, schwelle: int, jetzt: datetime) -> bool:
    """Codex gemessen frei: beide Fenster endlich unter der Schwelle, Reset in der Zukunft, frisch."""
    if codex.fehler or not _messung_frisch(codex.stand, jetzt):
        return False
    for name in ("5h", "Woche"):
        f = _gueltiges_fenster(codex.fenster_nach_name(name), jetzt)
        if f is None or f.prozent >= schwelle:
            return False
    return True


def _warum_nichts(messung: Messung, schwelle: int, jetzt: datetime) -> str:
    im_limit, _ = _claude_im_limit(messung.claude, schwelle, jetzt)
    if not im_limit:
        return STATUS_KEIN_LIMIT if _messung_frisch(messung.claude.stand, jetzt) else STATUS_CLAUDE_MESSUNG
    if not _codex_frei(messung.codex, schwelle, jetzt):
        return STATUS_CODEX_MESSUNG
    return "kein fälliges Paar"


def faellige(paare_liste: list[paare.Paar], messung: Messung, schwelle: int, an: bool,
             vorgangsliste: list[vorgaenge.Vorgang], jetzt: datetime,
             lauf_id: str = "", modus_mapping: dict[str, str] | None = None) -> list[Auftrag]:
    """Reine Entscheidung: welche Paare jetzt übergeben werden (je Paar und Fenster höchstens einer)."""
    if not an:
        return []
    im_limit, ausloeser = _claude_im_limit(messung.claude, schwelle, jetzt)
    if not im_limit or ausloeser is None or not _codex_frei(messung.codex, schwelle, jetzt):
        return []
    lage = rollen.lage(messung.claude, messung.codex, schwelle)
    if lage is None:
        return []
    fuenf = _gueltiges_fenster(messung.claude.fenster_nach_name("5h"), jetzt)
    woche = _gueltiges_fenster(messung.claude.fenster_nach_name("Woche"), jetzt)
    if fuenf is None or woche is None:
        return []
    bekannt = {v.id for v in vorgangsliste}
    modus_mapping = modus_mapping or {}
    auftraege: list[Auftrag] = []
    for paar in paare_liste:
        if not paar.aktiv or modus_mapping.get(paar.thema, modi.KONTINGENT) == modi.HERMES_CODEX:
            continue
        kennung = f"{paar.thema}@{int(ausloeser.reset.timestamp())}"
        if kennung in bekannt:
            continue
        auftraege.append(Auftrag(paar.thema, lauf_id, kennung, paar.codex_thread, paar.laufend,
                                 paar.master_datei, float(fuenf.prozent), float(woche.prozent),
                                 ausloeser.reset, lage))
    return auftraege


# --- Anzeige ------------------------------------------------------------------

def _uhrzeit(iso: str) -> str:
    zeit = signale._iso(iso)
    return zeit.astimezone().strftime("%H:%M") if zeit else "?"


def _letzter(vorgangsliste: list[vorgaenge.Vorgang], thema: str) -> vorgaenge.Vorgang | None:
    eigene = [v for v in vorgangsliste if v.thema == thema]
    return max(eigene, key=lambda v: v.zeit) if eigene else None


def status_zeile(paar: paare.Paar, vorgangsliste: list[vorgaenge.Vorgang],
                 jetzt: datetime | None = None) -> str:
    """Status eines Paares für das Menü: `bereit` / `gesendet 12:03` / `bestätigt` / `Fehler` / `unklar`."""
    v = _letzter(vorgangsliste, paar.thema)
    if v is None or v.phase in ("entwertet", "fehler"):
        return "Fehler" if v is not None and v.phase == "fehler" else "bereit"
    if v.phase == "bestaetigt":
        return "bestätigt"
    if v.phase == "gesendet":
        jetzt = jetzt or datetime.now(timezone.utc)
        alt = signale._iso(v.zeit)
        if alt is not None and jetzt - alt > FRIST_BESTAETIGUNG:
            return "keine Bestätigung"
        return f"gesendet {_uhrzeit(v.zeit)}"
    return "unklar"


def menue_zeilen(paare_liste: list[paare.Paar], vorgangsliste: list[vorgaenge.Vorgang],
                 jetzt: datetime | None = None) -> list[str]:
    """Eine Zeile je Paar mit Status; unklare Zustellungen werden ausdrücklich benannt."""
    zeilen = [f"{p.thema}: {status_zeile(p, vorgangsliste, jetzt)}" for p in paare_liste]
    if any(v.phase in ("sende", "unklar") for v in vorgangsliste):
        zeilen.append(STATUS_UNKLAR)
    return zeilen


# --- Ablauf -------------------------------------------------------------------

def _neue_lauf_id() -> str:
    return uuid.uuid4().hex


def _reservierung_aufloesen(master: Path, jetzt: datetime) -> str:
    """Eine verwaiste eigene Reservierung freigeben, wenn für ihre Lauf-ID kein Vorgang existiert."""
    text = besitz.lesen(master)
    teile = text.split()
    if not teile or teile[0] != besitz.RESERVIERT or len(teile) < 2:
        return text
    alte = teile[1]
    dauert = any(v.lauf_id == alte and v.phase in ("sende", "gesendet", "unklar", "bestaetigt")
                 for v in vorgaenge.lesen())
    if dauert:
        return text   # möglicher Versand: nie automatisch freigeben
    # v0.3.2: Vorzustand aus der Reservierungszeile (`… vorzustand codex <alte-id>`) exakt
    # wiederherstellen; ohne Zusatz gilt das Bestandsverhalten (claude … wiederaufnahme).
    if "vorzustand" in teile:
        neu = " ".join(teile[teile.index("vorzustand") + 1:])   # wörtlicher Vorzustand
    else:
        neu = besitz.zeile(besitz.CLAUDE, jetzt.isoformat(), "wiederaufnahme", alte)
    besitz.vergleiche_und_schreibe(master, text, neu)
    return besitz.lesen(master)


def _head_lesen(repo: Path, git, head: str | Callable[[], str] | None) -> Callable[[], str]:
    """Eine Funktion, die den HEAD **jeweils frisch** liefert (fester Wert nur für Tests)."""
    if callable(head):
        return head
    if head is not None:
        return lambda: head
    return lambda: kopf_hash(repo, git)


def _ein_thema(auftrag: Auftrag, *, repo: Path, jetzt: datetime, warte: Callable[[float], None],
               head_lesen: Callable[[], str], sender, git, frist: float) -> Stand:
    master = besitz.pfad(repo, auftrag.laufend)
    laufend_datei = repo / auftrag.laufend
    with zustand.thema_sperre(auftrag.thema, frist=frist) as frei:
        if not frei:
            return Stand(auftrag.thema, "übersprungen – Sperre belegt")

        try:
            if modi.geschuetzt(auftrag.thema, repo=repo, laufend=auftrag.laufend):
                return Stand(auftrag.thema, "Hermes führt – Codex nur Ausführer")
        except modi.ModusFehler as fehler:
            return Stand(auftrag.thema, f"Modusstatus fehlerhaft – kein Versand ({fehler})")

        bereit, status = uebergabepunkt(laufend_datei, head_lesen(), jetzt)
        if not bereit:
            return Stand(auftrag.thema, status)

        text = _reservierung_aufloesen(master, jetzt)
        if besitz.besitzer(text) == besitz.RESERVIERT:
            return Stand(auftrag.thema, STATUS_RESERVIERT)
        if besitz.besitzer(text) != besitz.CLAUDE:
            return Stand(auftrag.thema, STATUS_CODEX_MASTER)

        lauf_id = auftrag.lauf_id or _neue_lauf_id()
        a = replace(auftrag, lauf_id=lauf_id)
        reservierung = besitz.zeile(besitz.RESERVIERT, lauf_id, jetzt.isoformat())
        besitz.schreiben(master, reservierung)

        warte(WARTE_SEKUNDEN)

        # HEAD **nach** der Wartezeit frisch ermitteln: ein Commit während der Wartezeit blockiert den Versand.
        bereit, status = uebergabepunkt(laufend_datei, head_lesen(), jetzt, vor=jetzt)
        if not bereit:
            besitz.vergleiche_und_schreibe(master, reservierung, besitz.zeile(besitz.CLAUDE, jetzt.isoformat()))
            return Stand(auftrag.thema, STATUS_CLAUDE_HOERT if status == STATUS_UEBERGABEPUNKT else status)

        if besitz.lesen(master) != reservierung:
            return Stand(auftrag.thema, "Reservierung ersetzt – kein Versand")

        try:
            ergebnis = sender(a, repo, master, reservierung, jetzt, git=git)
        except Exception as fehler:  # noqa: BLE001 - Absturz nach „sende“ bleibt unklar, kein zweiter Versand
            return Stand(auftrag.thema, f"{STATUS_UNKLAR} ({fehler})", "sende")
        if ergebnis.phase == "gesendet":
            return Stand(auftrag.thema, "gesendet", "gesendet")
        if ergebnis.phase == "unklar":
            return Stand(auftrag.thema, STATUS_UNKLAR, "unklar")
        if ergebnis.phase == "doppelt":
            return Stand(auftrag.thema, "Vorgang existiert bereits", "sende")
        return Stand(auftrag.thema, f"Fehler: {ergebnis.meldung}", "fehler")


def lauf(jetzt: datetime | None = None, *, repo: Path | None = None, sender=None,
         warte: Callable[[float], None] | None = None, head: str | Callable[[], str] | None = None,
         git=None,
         trocken: bool = False, paare_liste: list[paare.Paar] | None = None,
         messung: Messung | None = None, schwelle: int | None = None, an: bool | None = None,
         vorgangsliste: list[vorgaenge.Vorgang] | None = None, lauf_id: str = "",
         frist: float = zustand.FRIST_SEKUNDEN,
         modus_mapping: dict[str, str] | None = None) -> list[Stand]:
    """Einen Automatiklauf ausführen (oder trocken nur zeigen) und je Thema einen Stand zurückgeben.

    `head` darf ein fester Wert oder eine Funktion sein; als Funktion wird der HEAD **vor der
    Reservierung und noch einmal nach der Wartezeit** frisch ermittelt (Standard: `git rev-parse HEAD`).
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    schwelle = anzeige.schwelle() if schwelle is None else schwelle
    an = anzeige.automatik_an() if an is None else an
    if not an:
        return [Stand("", STATUS_AUS)]
    if messung is None:
        messung = Messung(signale.claude_lesen(jetzt=jetzt), signale.codex_lesen(jetzt=jetzt))
    liste = paare.aktive() if paare_liste is None else paare_liste
    vorgangsliste = vorgaenge.lesen() if vorgangsliste is None else vorgangsliste
    if modus_mapping is None:
        try:
            modus_mapping = modi.lesen()
        except modi.ModusFehler as fehler:
            return [Stand("", f"Modusstatus fehlerhaft – kein Versand ({fehler})")]
    auftraege = faellige(liste, messung, schwelle, an, vorgangsliste, jetzt, lauf_id, modus_mapping)
    if not auftraege:
        return [Stand("", _warum_nichts(messung, schwelle, jetzt))]
    if trocken:
        return [Stand(a.thema, "bereit (trocken)", a.id) for a in auftraege]
    repo = repo or uebergabe.repo_wurzel()
    head_lesen = _head_lesen(repo, git, head)
    warte = warte or time.sleep
    return [_ein_thema(a, repo=repo, jetzt=jetzt, warte=warte, head_lesen=head_lesen,
                       sender=sender or codex_senden.senden, git=git, frist=frist)
            for a in auftraege]


# --- Bestätigungen ------------------------------------------------------------

def bestaetigungen_pruefen(jetzt: datetime | None = None, *, ordner: Path | None = None,
                           repo: Path | None = None, vorgangsliste: list[vorgaenge.Vorgang] | None = None,
                           paare_liste: list[paare.Paar] | None = None) -> list[Stand]:
    """Offene Vorgänge gegen die Assistentenantworten prüfen und `bestaetigt` setzen.

    Bestätigt wird nur, wenn der Vorgang noch `gesendet`/`unklar` ist **und** die Besitzdatei
    weiterhin genau `codex <id>` enthält – beides wird unter der Themensperre erneut geprüft.
    Ohne prüfbaren Besitz (kein auflösbares Repo) gibt es keine Bestätigung (fail-closed).
    Mit der Bestätigung wird – im **selben gesperrten Abschnitt** – der globale Master auf Codex
    gesetzt, damit ein gleichzeitiger Rückwechsel nicht danach überschrieben werden kann.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    liste = paare.lesen() if paare_liste is None else paare_liste
    vorgangsliste = vorgaenge.lesen() if vorgangsliste is None else vorgangsliste
    if repo is None:
        try:
            repo = uebergabe.repo_wurzel()
        except uebergabe.UebergabeFehler:
            repo = None
    if repo is None:
        return []  # Ohne geprüftes Repo weder Besitzdatei lesen noch ACK annehmen.
    ergebnisse: list[Stand] = []
    for v in vorgangsliste:
        if v.phase not in ("gesendet", "unklar"):
            continue
        paar = next((p for p in liste if p.thema == v.thema), None)
        if paar is None:
            continue
        try:
            if modi.geschuetzt(v.thema, repo=repo, laufend=paar.laufend):
                ergebnisse.append(Stand(v.thema, "Hermes führt – später ACK ignoriert", "entwertet"))
                continue
        except modi.ModusFehler as fehler:
            ergebnisse.append(Stand(v.thema, f"Modusstatus fehlerhaft – ACK ignoriert ({fehler})", "fehler"))
            continue
        seit = signale._iso(v.zeit)
        if seit is None or not ack.pruefen(v.id, paar.codex_thread, seit, ordner):
            continue
        if _bestaetigen(v, paar, repo):
            ergebnisse.append(Stand(v.thema, "bestätigt", "bestaetigt"))
    return ergebnisse


def _bestaetigen(v: vorgaenge.Vorgang, paar: paare.Paar, repo: Path | None) -> bool:
    """Bestätigen – **fail-closed**, atomar und **vollständig unter der Themensperre**.

    Ohne prüfbaren Besitz (kein auflösbares Repo) oder wenn der Vorgang zwischenzeitlich
    entwertet wurde, gibt es **keine** Bestätigung. Unter derselben Themensperre werden
    Besitz (`<thema>.master` genau `codex <id>`), die **frische** Phase und das Setzen des
    globalen Masters geprüft bzw. ausgeführt – ein Rückwechsel (derselbe Themensperren-Weg)
    läuft also entweder **komplett davor** (dann keine Bestätigung) oder **komplett danach**
    (dann bleibt er der letzte Wille). Der globale Master kann den Nutzerwunsch nicht mehr
    nachträglich überschreiben.

    **Sperrreihenfolge:** Themensperre zuerst, darin kurz die globale Zustandssperre – je
    Schreibvorgang einzeln, nie verschachtelt.

    **Teilschritte bei Absturz** (zwischen den beiden Schreibvorgängen gibt es keine
    Transaktion). Die Reihenfolge ist bewusst „globaler Master, dann Phase":

    * Absturz nach dem Master-Schreiben, vor dem Phasenschreiben: Der Vorgang bleibt
      `gesendet`/`unklar`. Der nächste Lauf findet ihn weiterhin offen und bestätigt erneut
      (idempotent) – **nichts blockiert**.
    * Umgekehrt (Phase zuerst) bliebe der Vorgang `bestaetigt`, während der globale Master nie
      gesetzt würde; ein erneuter Lauf überspränge ihn (Phase nicht mehr offen), der Zustand
      wäre dauerhaft widersprüchlich und nur manuell zu heilen. Deshalb diese Reihenfolge.
    """
    if repo is None:
        return False
    with zustand.thema_sperre(paar.thema, blockierend=True, frist=zustand.FRIST_SEKUNDEN) as frei:
        if not frei:
            return False
        try:
            if modi.geschuetzt(paar.thema, repo=repo, laufend=paar.laufend):
                return False
        except modi.ModusFehler:
            return False
        text = besitz.lesen(besitz.pfad(repo, paar.laufend))
        teile = text.split()
        if besitz.besitzer(text) != besitz.CODEX or len(teile) < 2 or teile[1] != v.id:
            return False   # Besitz inzwischen gewechselt (z. B. Rückwechsel) – ACK nur protokolliert
        offen = next((x for x in vorgaenge.lesen() if x.id == v.id), None)
        if offen is None or offen.phase not in ("gesendet", "unklar"):
            return False   # entwertet oder schon anders entschieden
        _master_codex()    # zuerst: ein Abbruch danach läßt den Vorgang offen und heilt sich
        return _phase_bestaetigen(v.id)


def _phase_bestaetigen(vorgangs_id: str) -> bool:
    """Phase auf `bestaetigt` setzen – nur bei weiterhin offenem Vorgang (zweite Sicherung)."""
    jetzt = datetime.now(timezone.utc).isoformat()
    bestaetigt: list[bool] = []

    def aenderung(alt: list[vorgaenge.Vorgang]) -> list[vorgaenge.Vorgang]:
        ziel = next((x for x in alt if x.id == vorgangs_id), None)
        if ziel is None or ziel.phase not in ("gesendet", "unklar"):
            return alt   # entwertet oder schon anders entschieden: nichts schreiben
        bestaetigt.append(True)
        return [replace(x, phase="bestaetigt", zeit=jetzt) if x.id == vorgangs_id else x for x in alt]

    vorgaenge.aendern(aenderung)
    return bool(bestaetigt)


def _master_codex() -> None:
    """Globalen Master auf Codex setzen, sobald mindestens ein Paar bestätigt ist."""
    gesetzt = datetime.now(timezone.utc).isoformat()
    zustand.aendern(lambda z: replace(z, master="codex", seit=gesetzt) if z.master != "codex" else z)
