"""Rückgabe an Codex: der abgebende Master übergibt Themen an ihre Codex-Chats (v0.3.2).

Manuell ausgelöst (Bestätigungsdialog im Menü oder `masterwechsel rueckgabe --ja`). Je aktivem Paar,
jeweils unter der OS-Themensperre:

1. Master erneut prüfen (nicht Codex ⇒ überspringen; schützt gegen einen parallelen Rückwechsel).
2. Kopfzeile **lesend** prüfen (`nein`/fehlend/ungültig ⇒ überspringen, schreibfrei).
3. Besitz reservieren (`reserviert <id> <Zeit> vorzustand <alte-marke>`, compare-and-write) – der
   Vorzustand liegt damit **dauerhaft** in der Reservierungszeile.
4. Kopfzeile auf `ja · jetzt · HEAD` ziehen (nur aus `ja`; die strenge Automatik-Prüfung bleibt
   unverändert – nur dieser bestätigte manuelle Weg darf ziehen).
5. Vorgang write-ahead Phase `sende` anlegen (id = lauf_id = `rueckgabe-<thema>-<yyyymmddHHMMSS>-<4Hex>`).
6. Besitzmarke `codex <id>` setzen, Nachricht senden (`codex.exe queue --thread …`).

Jeder Abbruch vor dem Transportstart stellt den gemerkten Vorzustand exakt wieder her (compare-and-
write gegen den jeweils eigenen Stand; nie bleibt eine Waise zurück). Fehler NACH Prozessstart
(Timeout, Rückgabewert ≠ 0) bleiben konservativ `unklar`, die Besitzmarke steht dann weiter auf Codex.
Der ACK-Abschluss läuft über `automatik.bestaetigungen_pruefen` (Phase `bestaetigt`).
"""
from __future__ import annotations

import secrets
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import automatik, besitz, codex_senden, modi, paare, signale, uebergabe, vorgaenge, zustand

KENNUNG_PRAEFIX = "rueckgabe"
OFFEN = ("sende", "gesendet", "unklar")

Transport = Callable[[list[str], int], int]


class RueckgabeFehler(Exception):
    """Rückgabe nicht möglich (z. B. Repo nicht auffindbar)."""


# --- Kennung ------------------------------------------------------------------

def neue_id(thema: str, jetzt: datetime) -> str:
    """Eindeutige Kennung `rueckgabe-<thema>-<yyyymmddHHMMSS>-<4Hex>` (fester Aufbau).

    Alle Kennungen sind gleich lang ⇒ keine ist Präfix einer anderen; der `startswith`-Vergleich
    in `ack.pruefen` bleibt eindeutig. Kollidiert sie doch (praktisch unmöglich), wird neu gezogen.
    """
    stempel = jetzt.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
    vergeben = {v.id for v in vorgaenge.lesen()}
    for _ in range(50):
        kandidat = f"{KENNUNG_PRAEFIX}-{thema}-{stempel}-{secrets.token_hex(2)}"
        if kandidat not in vergeben:
            return kandidat
    raise RueckgabeFehler("keine freie Kennung gefunden")


# --- Kopfzeile ----------------------------------------------------------------

def kopfzeile_ziehen(pfad: Path, head_kurz: str, jetzt: datetime) -> bool:
    """Erste Zeile auf `Übergabebereit: ja · <ISO> · <HEAD-Kurzform>` setzen.

    Nur wenn dort bereits eine Kopfzeile mit Präfix steht und `head_kurz` das Format erfüllt
    (7–12 Hexzeichen); sonst bleibt die Datei unberührt (`False`). Zeilenenden bleiben erhalten.
    """
    if not (7 <= len(head_kurz) <= 12):
        return False
    try:
        with pfad.open("r", encoding="utf-8", newline="") as datei:
            roh = datei.read()
    except OSError:
        return False
    zeilen = roh.split("\n")
    if not zeilen:
        return False
    erste = zeilen[0][:-1] if zeilen[0].endswith("\r") else zeilen[0]
    treffer = automatik.KOPFZEILE.match(erste)
    if treffer is None or treffer.group(1) != "ja":
        return False      # zweite Sicherung: „nein" wird nie überstimmt
    ende = "\r" if zeilen[0].endswith("\r") else ""
    zeilen[0] = f"Übergabebereit: ja · {jetzt.isoformat()} · {head_kurz}{ende}"
    try:
        with pfad.open("w", encoding="utf-8", newline="") as datei:
            datei.write("\n".join(zeilen))
    except OSError:
        return False
    return True


# --- kleine Helfer ------------------------------------------------------------

def _letzter(vorgangsliste: list[vorgaenge.Vorgang], thema: str) -> vorgaenge.Vorgang | None:
    """Neuester Vorgang des Themas **nach Zeit** (nicht nach Kennungs-Sortierung)."""
    treffer = [v for v in vorgangsliste if v.thema == thema]
    if not treffer:
        return None
    leer = datetime.min.replace(tzinfo=timezone.utc)
    return max(treffer, key=lambda v: signale._iso(v.zeit) or leer)


def _phase_setzen(vorgangs_id: str, phase: str, fehler: str | None = None) -> None:
    """Write-ahead-Phase wechseln – nur aus `sende` heraus (zweite Sicherung)."""
    jetzt_iso = datetime.now(timezone.utc).isoformat()

    def aenderung(alt: list[vorgaenge.Vorgang]) -> list[vorgaenge.Vorgang]:
        return [replace(v, phase=phase, zeit=jetzt_iso, fehler=fehler)
                if v.id == vorgangs_id and v.phase == "sende" else v for v in alt]

    vorgaenge.aendern(aenderung)


def _wiederherstellen(master_pfad: Path, erwartet: str, tokens: list[str]) -> bool:
    """Vorzustand **wörtlich** zurückholen – die vollständige alte Zeile (Tokenliste), nie neu gestempelt."""
    return besitz.vergleiche_und_schreibe(master_pfad, erwartet, " ".join(tokens))


def nachricht_text(paar: paare.Paar, kennung: str, hinweis: str | None,
                   kopfzeile_gezogen: bool, jetzt: datetime) -> str:
    """Kurzer deutscher Übergabetext für den Codex-Chat (keine sensiblen Inhalte)."""
    wann = jetzt.astimezone().strftime("%d.%m.%Y %H:%M")
    teile = [
        f"Rückgabe an Codex (manuell, {wann}): Thema „{paar.thema}“. "
        f"Der Master-Schalter übergibt das Thema an dich – du bist Master (Thinker) für „{paar.thema}“.",
        f"Maßgeblich ist `{paar.laufend}` im Repo – lies zuerst diese laufende Übergabe.",
    ]
    if kopfzeile_gezogen:
        teile.append("Hinweis: Die Kopfzeile war veraltet – ich habe sie beim Senden auf den "
                     "aktuellen HEAD und jetzt gezogen.")
    teile.append("Grenzen (AGENTS.md): Sensibles nur Hermes; Push nur nach grünem Prüfbefehl; "
                 "nie `git add -A`; Prüfprotokolle zeigen.")
    if hinweis:
        zusatz = " ".join(hinweis.split())[:300]
        if zusatz:
            teile.append(f"Zusatz: {zusatz}")
    teile.append(f"Halte die Kopfzeile von `{paar.laufend}` ab jetzt selbst aktuell "
                 "(`Übergabebereit: ja|nein · Zeit · HEAD-Kurzform`).")
    teile.append(f"Antworte als allererste Zeile genau: ACK {kennung}")
    return "\n".join(teile)


# --- Ablauf je Thema ----------------------------------------------------------

def _ein_thema(paar: paare.Paar, *, repo: Path, jetzt: datetime, hinweis: str | None,
               trocken: bool, erneut: bool, transport: Transport | None,
               git=None) -> automatik.Stand:
    master_pfad = besitz.pfad(repo, paar.laufend)
    laufend_datei = repo / paar.laufend
    with zustand.thema_sperre(paar.thema, blockierend=True, frist=zustand.FRIST_SEKUNDEN) as frei:
        if not frei:
            return automatik.Stand(paar.thema, "Thema gesperrt – später erneut versuchen")
        try:
            if modi.geschuetzt(paar.thema, repo=repo, laufend=paar.laufend):
                return automatik.Stand(paar.thema, "Hermes führt – keine Codex-Master-Rückgabe")
        except modi.ModusFehler as fehler:
            return automatik.Stand(paar.thema, f"Modusstatus fehlerhaft – keine Rückgabe ({fehler})", "fehler")
        # 1) Master unter der Sperre erneut prüfen (schützt gegen parallelen Rückwechsel)
        if zustand.lesen().master != "codex":
            return automatik.Stand(paar.thema, "Master ist nicht Codex – übersprungen")
        # 2) Kopfzeile LESEND prüfen – schreibfrei bei nein/fehlt/ungültig
        kopf = automatik.kopfzeile_lesen(laufend_datei)
        if kopf is None:
            return automatik.Stand(paar.thema, "Übergabestand fehlt/ungültig – Kopfzeile bewusst "
                                               "setzen; nichts gesendet")
        if kopf[0] != "ja":
            return automatik.Stand(paar.thema, "Übergabepunkt steht auf 'nein' – nichts gesendet",
                                   "nein")
        head = automatik.kopf_hash(repo, git)
        bereit, status = automatik.uebergabepunkt(laufend_datei, head, jetzt)
        if not bereit and status == automatik.STATUS_UEBERGABEPUNKT:
            return automatik.Stand(paar.thema, "Übergabepunkt steht auf 'nein' – nichts gesendet",
                                   "nein")
        kopf_hinweis = "" if bereit else f"Kopfzeile veraltet ({status})"
        # 3) Besitz lesen; verwaiste Reservierung nur simulationsweise auflösen (kein Schreibzugriff)
        text = besitz.lesen(master_pfad)
        teile = text.split()
        waise = False
        if besitz.besitzer(text) == besitz.RESERVIERT and len(teile) > 1:
            alt = teile[1]
            laeuft = any(v.lauf_id == alt and v.phase in ("sende", "gesendet", "unklar", "bestaetigt")
                         for v in vorgaenge.lesen())
            if laeuft:
                return automatik.Stand(paar.thema, "Übergabe läuft (Reservierung offen) – bitte prüfen")
            waise = True
            if "vorzustand" in teile:
                text = " ".join(teile[teile.index("vorzustand") + 1:])
            else:   # Alt-/Fremdreservierung: die Auflösung schreibt die Wiederaufnahme-Zeile
                text = besitz.zeile(besitz.CLAUDE, jetzt.isoformat(), "wiederaufnahme", teile[1])
            teile = text.split()
        vorzustand = teile            # wörtlicher Vorzustand (ggf. leer)
        if besitz.besitzer(text) == besitz.CODEX and not erneut:
            return automatik.Stand(paar.thema, "Codex hat schon übernommen – nichts gesendet "
                                               "(--erneut erzwingt)")
        if not erneut:
            letzter = _letzter(vorgaenge.lesen(), paar.thema)
            if letzter is not None and letzter.phase in ("sende", "gesendet", "unklar", "bestaetigt"):
                return automatik.Stand(paar.thema, "bereits übergeben – nichts gesendet (--erneut "
                                                   "erzwingt)", letzter.phase)
        if trocken:
            extra = f" – {kopf_hinweis}, würde beim Senden gezogen" if kopf_hinweis else ""
            waisen_hinweis = " – verwaiste Reservierung würde aufgelöst" if waise else ""
            return automatik.Stand(paar.thema, f"Trockenlauf: würde senden{extra}{waisen_hinweis} "
                                               f"(Ziel {paar.codex_thread})")
        # 4) Ab hier wird geschrieben. Waise zuerst auflösen (compare-and-write), dann reservieren.
        if waise:
            text = automatik._reservierung_aufloesen(master_pfad, jetzt)
        kennung = neue_id(paar.thema, jetzt)
        reservierung = besitz.zeile(besitz.RESERVIERT, kennung, jetzt.isoformat(),
                                    "vorzustand", *vorzustand)
        if not besitz.vergleiche_und_schreibe(master_pfad, text, reservierung):
            return automatik.Stand(paar.thema, "Fremdschreiber am Besitz – nichts gesendet", "fehler")
        # 5) Vorgang write-ahead ZUERST – jeder weitere Fehler hat damit eine Spur.
        try:
            vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
                kennung, paar.thema, kennung, "sende", jetzt.isoformat())])
        except Exception as fehler:  # noqa: BLE001
            _wiederherstellen(master_pfad, reservierung, vorzustand)
            return automatik.Stand(paar.thema, f"Vorgang nicht angelegt – Vorzustand "
                                               f"wiederhergestellt ({fehler})", "fehler")
        # 6) Kopfzeile ziehen (prüft selbst erneut auf „ja"); 7) Besitzmarke; 8) Transport.
        if not kopfzeile_ziehen(laufend_datei, head[:7], jetzt):
            _phase_setzen(kennung, "fehler", "Kopfzeile nicht ziehbar")
            _wiederherstellen(master_pfad, reservierung, vorzustand)
            return automatik.Stand(paar.thema, "Kopfzeile nicht schreibbar – Vorzustand "
                                               "wiederhergestellt", "fehler")
        marke = besitz.zeile(besitz.CODEX, kennung, jetzt.isoformat())
        if not besitz.vergleiche_und_schreibe(master_pfad, reservierung, marke):
            _phase_setzen(kennung, "fehler", "Besitzmarke zwischenzeitlich geändert")
            return automatik.Stand(paar.thema, "Besitzmarke geändert – kein Senden", "fehler")
        programm = codex_senden.programm() or "codex.exe"
        liste = [programm, codex_senden.QUEUE, "--thread", paar.codex_thread, "--message",
                 nachricht_text(paar, kennung, hinweis, bool(kopf_hinweis), jetzt)]
        try:
            rc = (transport or codex_senden._transport)(liste, codex_senden.TIMEOUT_SEKUNDEN)
        except codex_senden.START_FEHLER as fehler:
            _phase_setzen(kennung, "fehler", f"Transport nicht gestartet: {fehler}")
            _wiederherstellen(master_pfad, marke, vorzustand)
            return automatik.Stand(paar.thema, "Transport nicht gestartet – Vorzustand "
                                               "wiederhergestellt", "fehler")
        except Exception as fehler:  # noqa: BLE001 - alles nach dem Start gilt konservativ als unklar
            _phase_setzen(kennung, "unklar", str(fehler))
            return automatik.Stand(paar.thema, "Zustellung unklar – Besitz bleibt Codex, bitte prüfen",
                                   "unklar")
        if rc == 0:
            _phase_setzen(kennung, "gesendet")
            stand = "gesendet (Kopfzeile gezogen)" if kopf_hinweis else "gesendet"
            return automatik.Stand(paar.thema, f"{stand} ({kennung})", "gesendet")
        _phase_setzen(kennung, "unklar", f"Rückgabewert {rc}")
        return automatik.Stand(paar.thema, "Zustellung unklar – Besitz bleibt Codex, bitte prüfen",
                               "unklar")


# --- Einstieg -----------------------------------------------------------------

def rueckgabe(jetzt: datetime | None = None, *, themen: list[str] | None = None,
              hinweis: str | None = None, trocken: bool = False, erneut: bool = False,
              repo: Path | None = None, transport: Transport | None = None,
              git=None) -> list[automatik.Stand]:
    """Rückgabe an Codex für alle aktiven Paare (oder die genannten Themen).

    `trocken=True`: nur anzeigen, was passieren würde – nichts schreiben, nichts senden.
    `erneut=True`: auch senden, wenn bereits übergeben (ersetzt die Codex-Besitzmarke bewusst).
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    if repo is None:
        try:
            repo = uebergabe.repo_wurzel()
        except uebergabe.UebergabeFehler as fehler:
            raise RueckgabeFehler(str(fehler)) from fehler
    ergebnisse: list[automatik.Stand] = []
    namen = set(themen) if themen else None
    for paar in paare.lesen():
        if namen is not None and paar.thema not in namen:
            continue
        if not paar.aktiv:
            ergebnisse.append(automatik.Stand(paar.thema, "Paar ist aus – nichts gesendet"))
            continue
        ergebnisse.append(_ein_thema(paar, repo=repo, jetzt=jetzt, hinweis=hinweis,
                                     trocken=trocken, erneut=erneut, transport=transport, git=git))
    return ergebnisse
