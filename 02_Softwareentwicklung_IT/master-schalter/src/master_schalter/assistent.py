"""Ablauf des Wechselassistenten (Baustein K4): „Thema X: alter Chat → neuer Chat" ohne Tippen.

Reihenfolge nach G8: erst gibt der **alte** Master ab, dann wird die Rolle gesetzt, dann wird dem
**neuen** Master zugestellt. Zwei Einstiege, beide ohne Oberfläche:

* `uebergeben(...)` legt den Vorgang an (Write-ahead, Vorzustand = Profil und wörtlicher Markentext),
  schickt dem alten Chat den Abgabe-Auftrag und ruft danach einmal `fortsetzen` auf.
* `fortsetzen(id)` ist der **idempotente Takt** (später von Leiste/Fenster alle paar Sekunden gerufen):
  Frist prüfen (10 min), Rolle setzen, neuen Chat benachrichtigen. Mehrfaches Aufrufen sendet nie doppelt.

Regeln, die den Ablauf tragen:

* **Transporte laufen nie unter der Themensperre und nie unter der Dateisperre.** Gesperrt wird nur,
  um zu prüfen und die Phase zu setzen (`postfach.abholen` und `quittieren` warten nur
  `THEMENSPERRE_FRIST`; Codex darf nach G8d quittieren, bevor der Rückgabewert da ist).
* **Write-ahead und Vergleich-und-Setzen:** vor jedem Senden steht die Phase `abgabe_sende` bzw. `sende`
  auf der Platte (`phase_gewinnen`); wer den Wechsel verliert, sendet nicht. Ein Absturz dazwischen heißt
  „unklar" – es wird **nie** automatisch neu gesendet.
* **Zustellwege:** Codex über `codex.exe queue --thread <Kennung> --message <Text>` (Argumentliste, keine
  Shell); Claude und Hermes über das Postfach (`postfach.einlegen`). Der Text besteht aus festen
  Satzbausteinen (`postfach.TEXTE`) – keine Chat-Kennung, kein Titel, kein Dateiinhalt.
* **Kennungen** der Chats liegen nur in `assistent.json` (lokal, G9); Protokoll (`protokoll.py`),
  Meldungen und CLI-Ausgaben nennen sie nie.
* Ein Transport gilt nur als **fehlgeschlagen**, wenn der Kindprozess nachweislich nicht gestartet ist
  (`START_FEHLER`, `codex.exe` nicht gefunden); Rückgabewert ≠ 0, Zeitüberschreitung oder jede andere
  Ausnahme gelten konservativ als **unklar**.

Noch nicht Teil dieses Bausteins: Ruhenachweis aus dem Statusregister (G8b, P3/P6), Empfang im
Claude-/Hermes-Chat (P3a/P6) und die Oberfläche (P5).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import assistent_vorgaenge as av
from . import besitz, codex_senden, modi, paare, postfach, protokoll, zustand
from .assistent_vorgaenge import AssistentFehler
from .codex_senden import Transport

ABGABE_FRIST = timedelta(minutes=10)
ABGABE_WEG = {"ok": "abgabe_angefragt", "fehler": "abgabe_fehler", "unklar": "abgabe_unklar"}
NEU_WEG = {"ok": "gesendet", "fehler": "fehler", "unklar": "unklar"}
NEU_FEHLER = {"fehler": "Zustellung nicht gestartet", "unklar": "Zustellung unklar – nicht erneut gesendet"}
_NACH_ABGABE = ("abgegeben", "abgabe_uebersprungen")   # Abgabe erledigt, Rolle noch nicht gesetzt

__all__ = ["ABGABE_FRIST", "AssistentFehler", "ChatRef", "fortsetzen", "uebergeben"]


@dataclass(frozen=True)
class ChatRef:
    """Ein Chat: Werkzeug (`claude|codex|hermes`) und Kennung nach G6-Muster `^[A-Za-z0-9_-]{1,80}$`.

    Die Fehlermeldungen nennen die Kennung nie.
    """
    werkzeug: str
    kennung: str

    def __post_init__(self) -> None:
        if not isinstance(self.werkzeug, str) or self.werkzeug not in modi.ZIEL_ROLLEN:
            raise AssistentFehler(f"Chat-Werkzeug unzulässig (erlaubt: {', '.join(modi.ZIEL_ROLLEN)})")
        if not isinstance(self.kennung, str) or modi.VORGANG_ID_MUSTER.fullmatch(self.kennung) is None:
            raise AssistentFehler(f"Chat-Kennung unzulässig (erlaubt: {modi.VORGANG_ID_MUSTER.pattern})")

    def als_dict(self) -> dict:
        return {"werkzeug": self.werkzeug, "kennung": self.kennung}

    @staticmethod
    def aus_dict(roh: dict | None) -> "ChatRef | None":
        """Referenz aus der gespeicherten Form (bereits von `assistent_vorgaenge.chat_dict` geprüft)."""
        return None if roh is None else ChatRef(roh["werkzeug"], roh["kennung"])


# --- Transporte ----------------------------------------------------------------------

def _codex_senden(kennung: str, text: str, transport: Transport | None) -> str:
    """Nachricht per `codex.exe queue` senden → `ok` | `fehler` (nachweislich nicht gestartet) | `unklar`.

    Läuft immer außerhalb von Themen- und Dateisperre.
    """
    programm = codex_senden.programm()
    if programm is None:
        return "fehler"
    liste = [programm, codex_senden.QUEUE, "--thread", kennung, "--message", text]
    try:
        rc = (transport or codex_senden._transport)(liste, codex_senden.TIMEOUT_SEKUNDEN)
    except codex_senden.START_FEHLER:
        return "fehler"
    except Exception:  # noqa: BLE001 - alles nach dem Start gilt konservativ als unklar
        return "unklar"
    return "ok" if rc == 0 else "unklar"


def _postfach_legen(ref: ChatRef, vorgang_id: str, thema: str, art: str) -> bool:
    """Nachricht ins Postfach legen; `False` bei jeder Ausnahme (Datei nicht geschrieben)."""
    try:
        postfach.einlegen(ref.werkzeug, ref.kennung, vorgang_id, thema, art, paare.laufend_bilden(thema))
    except Exception:  # noqa: BLE001
        return False
    return True


# --- Hilfen --------------------------------------------------------------------------

def _os_ursache(fehler: BaseException) -> BaseException | None:
    """Erste `OSError`/`SperrFehler` in der Ausnahmekette (`__cause__`/`__context__`), auch die Ausnahme selbst."""
    gesehen: set[int] = set()
    aktuell: BaseException | None = fehler
    while aktuell is not None and id(aktuell) not in gesehen and len(gesehen) < 20:
        if isinstance(aktuell, (OSError, zustand.SperrFehler)):
            return aktuell
        gesehen.add(id(aktuell))
        aktuell = aktuell.__cause__ or aktuell.__context__
    return None


def _assistentfehler(fehler: BaseException, *, vorspann: str = "") -> AssistentFehler:
    """`AssistentFehler` aus einer fremden Ausnahme – **nie** mit deren Text (er kann Pfade enthalten).

    * Steckt ein `OSError` in der Kette: fester Text mit der Fehlerklasse ("Besitz- oder Datendatei nicht
      lesbar (PermissionError)"); ein `SperrFehler`: "Sperre gerade belegt (SperrFehler)".
    * Sonst nur die Klasse (`vorspann (ModusFehler)`). Lesbare Prüftexte („Thema unbekannt …") erzeugt
      `uebergeben` selbst, bevor fremder Code läuft (Positivliste statt Pfadfilter).
    Die Ursache bleibt über `from fehler` an der Kette.
    """
    ursache = _os_ursache(fehler)
    if ursache is not None:
        if isinstance(ursache, zustand.SperrFehler):
            text = f"Sperre gerade belegt ({type(ursache).__name__})"
        else:
            text = f"Besitz- oder Datendatei nicht lesbar ({type(ursache).__name__})"
        return AssistentFehler(f"{vorspann}: {text}" if vorspann else text)
    return AssistentFehler(f"{vorspann or 'Fehler'} ({type(fehler).__name__})")


def _markentext(thema: str, repo: Path | None) -> str:
    _, master_datei = modi._paar_pruefen(thema, repo)
    return modi._besitz_text_lesen(master_datei)


def _laeuft(vorgang: av.Vorgang) -> bool:
    """Ein Vorgang blockiert einen neuen Wechsel nur, solange die Rolle nicht gesetzt ist oder gesendet wird."""
    return vorgang.phase in av.WECHSEL_BLOCKIEREND


def _aware(zeit: datetime) -> datetime:
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)


def _frist_abgelaufen(vorgang: av.Vorgang, jetzt: datetime) -> bool:
    """Frist ab `abgabe_seit` (ersatzweise `zeit`); eine nicht lesbare Zeit gilt als **nicht** abgelaufen."""
    try:
        beginn = datetime.fromisoformat(vorgang.abgabe_seit or vorgang.zeit)
    except ValueError:
        return False
    return _aware(jetzt) - _aware(beginn) >= ABGABE_FRIST


# --- Einstieg 1: übergeben ------------------------------------------------------------

def uebergeben(thema: str, ziel: str, *, von_chat: ChatRef | None = None, nach_chat: ChatRef | None = None,
               repo: Path | None = None, jetzt: datetime | None = None,
               transport: Transport | None = None) -> av.Vorgang:
    """Einen Wechsel starten: Vorgang anlegen, dem alten Chat den Abgabe-Auftrag schicken, einmal fortsetzen.

    Alle Prüfungen laufen vor jeder Nebenwirkung; ein Fehler (`AssistentFehler`) ändert nichts.
    Ohne `von_chat` wird die Abgabe sofort übersprungen („kein alter Chat gewählt"), ohne `nach_chat`
    bleibt der Vorgang nach dem Rollensetzen auf `rolle_gesetzt` (Zustellung später nachholbar).
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:   # die ungeprüfte Eingabe nie wiederholen (R6/1)
        raise AssistentFehler(f"Thema unzulässig (erlaubt: {paare.THEMA_MUSTER.pattern})") from fehler
    try:
        bekannt = any(p.thema == thema for p in paare.lesen())
    except Exception as fehler:  # noqa: BLE001 - Lesefehler nie mit Text (Pfad) weitergeben
        raise _assistentfehler(fehler, vorspann="Paare nicht lesbar") from fehler
    if not bekannt:
        raise AssistentFehler(f"Thema unbekannt (kein vorhandenes Paar): {thema}")
    if not isinstance(ziel, str) or ziel not in modi.ZIEL_ROLLEN:
        raise AssistentFehler(f"Zielrolle unzulässig (erlaubt: {', '.join(modi.ZIEL_ROLLEN)})")
    for name, ref in (("alter", von_chat), ("neuer", nach_chat)):
        if ref is not None and not isinstance(ref, ChatRef):
            raise AssistentFehler(f"Der {name} Chat ist keine Chat-Referenz")
    if nach_chat is not None and nach_chat.werkzeug != ziel:
        raise AssistentFehler("Der neue Chat gehört nicht zur Zielrolle")
    if von_chat is not None and von_chat == nach_chat:
        raise AssistentFehler("Alter und neuer Chat sind derselbe")

    try:
        with zustand.thema_sperre(thema) as frei:         # nicht blockierend: belegt = sofort melden
            if not frei:
                raise AssistentFehler("Thema gerade belegt")
            vorgang = _anlegen(thema, ziel, von_chat, nach_chat, repo, jetzt)
    except (modi.ModusFehler, zustand.SperrFehler, OSError) as fehler:
        raise _assistentfehler(fehler, vorspann="Wechsel nicht gestartet") from fehler

    # Ab hier ohne Sperre: Transporte laufen nie unter Themen- oder Dateisperre. Jede Ausnahme, die von hier an
    # entweicht (z. B. ein OSError aus `abgabe_ergebnis`), wird zu einem bereinigten `AssistentFehler`. Bleibt dabei
    # `abgabe_sende` stehen, ist das richtig: die Wiederaufnahme macht daraus `abgabe_unklar`, nie neu senden.
    try:
        laufend = paare.laufend_bilden(thema)
        if von_chat is None:
            protokoll.schreiben(vorgang.id, thema, "abgabe_uebersprungen", "kein alter Chat gewählt")
        else:
            _abgabe_senden(vorgang, von_chat, laufend, transport)
        try:
            return fortsetzen(vorgang.id, repo=repo, jetzt=jetzt, transport=transport)
        except AssistentFehler as fehler:
            # Der Vorgang steht; `masterwechsel fortsetzen` zeigt den Fehler erneut und macht weiter.
            # Nur die Fehlerklasse ins Protokoll: Ausnahmetexte können Pfade enthalten.
            protokoll.schreiben(vorgang.id, thema, "fortsetzen_fehlgeschlagen",
                                type(fehler.__cause__ or fehler).__name__)
            return av.finden(vorgang.id) or vorgang
    except AssistentFehler:
        raise
    except Exception as fehler:  # noqa: BLE001 - nach dem Anlegen verlässt nur ein bereinigter AssistentFehler die Funktion
        raise _assistentfehler(fehler, vorspann="Wechsel nicht abgeschlossen") from fehler


def _anlegen(thema: str, ziel: str, von_chat: ChatRef | None, nach_chat: ChatRef | None,
             repo: Path | None, jetzt: datetime) -> av.Vorgang:
    """Unter gehaltener Themensperre: prüfen, `vorbereitet` mit Vorzustand anlegen, Abgabe beginnen/überspringen."""
    if any(v.thema == thema and _laeuft(v) for v in av.lesen()):
        raise AssistentFehler("Wechsel läuft bereits")
    profil = modi.profil(thema)
    text = _markentext(thema, repo)
    alt = besitz.besitzer(text)
    if alt not in modi.ZIEL_ROLLEN:
        # Nur bekannte Wörter nennen; `besitzer` liefert sonst das erste Wort des Dateiinhalts (R5/1).
        anzeige = alt if alt == besitz.RESERVIERT else "unbekannt"
        raise AssistentFehler(f"Thema ist gerade nicht übergebbar (Besitz: {anzeige})")
    if von_chat is not None and von_chat.werkzeug != alt:
        raise AssistentFehler(f"Der alte Chat gehört nicht zum aktuellen Master ({alt})")
    vorgang = av.Vorgang(
        av.neue_id(jetzt), thema, ziel, alt, "vorbereitet", jetzt.isoformat(),
        {"master": profil.master, "worker": profil.worker, "modell": profil.modell}, text,
        von_chat=None if von_chat is None else von_chat.als_dict(),
        nach_chat=None if nach_chat is None else nach_chat.als_dict())
    av.aendern(lambda liste: [*liste, vorgang])
    protokoll.schreiben(vorgang.id, thema, "angelegt", f"{alt} -> {ziel}")
    if von_chat is None:
        neu = av.abgabe_ueberspringen(vorgang.id, "kein alter Chat gewählt")
    else:
        neu = av.abgabe_beginnen(vorgang.id)
    return neu or vorgang


def _abgabe_senden(vorgang: av.Vorgang, ref: ChatRef, laufend: str, transport: Transport | None) -> None:
    """Abgabe-Auftrag an den alten Chat (Phase ist bereits `abgabe_sende`), Ergebnis über `abgabe_ergebnis`."""
    protokoll.schreiben(vorgang.id, vorgang.thema, "abgabe_zustellweg", ref.werkzeug)
    if ref.werkzeug == "codex":
        text = postfach.text("abgabe_auftrag", vorgang.thema, laufend, vorgang.id)
        ergebnis = ABGABE_WEG[_codex_senden(ref.kennung, text, transport)]
    else:
        ok = _postfach_legen(ref, vorgang.id, vorgang.thema, "abgabe_auftrag")
        ergebnis = ABGABE_WEG["ok" if ok else "fehler"]
    av.abgabe_ergebnis(vorgang.id, ergebnis)
    protokoll.schreiben(vorgang.id, vorgang.thema, "abgabe_ergebnis", ergebnis)


# --- Einstieg 2: fortsetzen (idempotenter Takt) ---------------------------------------

def fortsetzen(vorgang_id: str, *, repo: Path | None = None, jetzt: datetime | None = None,
               transport: Transport | None = None) -> av.Vorgang:
    """Einen Vorgang so weit bringen, wie es jetzt sicher geht; mehrfaches Aufrufen sendet nie doppelt.

    1. Frist: offene Abgabe älter als `ABGABE_FRIST` → übersprungen; der Gewinner dieses Wechsels
       schickt dem alten Chat die Info (ein Fehler dabei hält nichts auf).
    2. Abgabe erledigt (`abgegeben`/`abgabe_uebersprungen`): Marke noch wie im Vorzustand → Rolle setzen,
       sonst `verworfen` („Stand geändert").
    3. `rolle_gesetzt` mit neuem Chat: `sende` (Write-ahead) → Zustellung → `gesendet` | `im_postfach` |
       `fehler` | `unklar`. Ohne neuen Chat bleibt es bei `rolle_gesetzt`.

    Alle anderen Phasen bleiben unverändert. Unbekannte ID: `AssistentFehler`.
    """
    try:
        modi.vorgang_id_pruefen(vorgang_id)
    except modi.ModusFehler as fehler:   # die ungeprüfte Eingabe nie wiederholen (R6/1)
        raise AssistentFehler(f"Vorgangskennung unzulässig (erlaubt: {modi.VORGANG_ID_MUSTER.pattern})") from fehler
    jetzt = jetzt or datetime.now(timezone.utc)
    try:
        vorgang = av.finden(vorgang_id)
        if vorgang is None:
            raise AssistentFehler(f"Vorgang unbekannt: {vorgang_id}")
        for schritt in (_frist, _rolle_setzen, _zustellen):
            vorgang = schritt(vorgang, repo=repo, jetzt=jetzt, transport=transport)
    except AssistentFehler:
        raise
    except Exception as fehler:  # noqa: BLE001
        # Eine nicht geschriebene Phase gilt nicht als gewonnen (Vergleich-und-Setzen): es wurde nichts gesendet,
        # der nächste Takt versucht es erneut. Die Meldung nennt nur die Fehlerart (keine Pfade).
        raise _assistentfehler(fehler, vorspann="Vorgang gerade nicht bearbeitbar") from fehler
    return vorgang


def _frist(vorgang: av.Vorgang, *, repo: Path | None, jetzt: datetime, transport: Transport | None) -> av.Vorgang:
    """Frist abgelaufen -> nur die Phase `abgabe_uebersprungen`. Die Info an den alten Chat geht **nicht** hier raus,
    sondern erst, wenn `_rolle_setzen` die Rolle wirklich gesetzt hat (sonst hörte der alte Master "du führst nicht
    mehr", obwohl er noch Master ist)."""
    if vorgang.phase not in av.ABGABE_FRISTBAR or not _frist_abgelaufen(vorgang, jetzt):
        return vorgang
    neu, gewonnen = av.phase_gewinnen(vorgang.id, av.ABGABE_FRISTBAR, "abgabe_uebersprungen",
                                      abgabe="uebersprungen", fehler="Frist abgelaufen")
    if gewonnen:
        protokoll.schreiben(vorgang.id, vorgang.thema, "abgabe_uebersprungen", "Frist abgelaufen")
    return neu or vorgang              # nicht gewonnen: zwischenzeitlich quittiert oder von einem anderen Takt erledigt


def _info_entfaellt(vorgang: av.Vorgang, repo: Path | None) -> str | None:
    """Grund (fester Text), warum die Info nicht mehr gilt, sonst `None`.

    Nach einem schnellen Rückwechsel führt der alte Master das Thema vielleicht wieder: die Info ginge dann an den
    falschen Empfänger. Sie wird nur gesendet, solange der Vorgang nicht verworfen ist und die Marke noch genau
    diesen Wechsel trägt (`<Ziel> … assistent <Thema> <Vorgang>`). Nicht lesbar = im Zweifel nicht senden.
    """
    try:
        aktuell = av.finden(vorgang.id)
        if aktuell is None or aktuell.phase == "verworfen":
            return "Vorgang verworfen"
        text = _markentext(vorgang.thema, repo)
    except Exception:  # noqa: BLE001
        return "Marke nicht lesbar"
    if besitz.assistent_marke(text) != (vorgang.ziel, vorgang.thema, vorgang.id):
        return "Marke gehört nicht mehr zu diesem Vorgang"
    return None


def _info_senden(vorgang: av.Vorgang, ref: ChatRef, transport: Transport | None, repo: Path | None = None) -> None:
    """Dem alten Chat sagen, dass er das Thema nicht mehr führt; nur der Gewinner des Rollensetzens ruft das."""
    grund = _info_entfaellt(vorgang, repo)
    if grund is not None:
        protokoll.schreiben(vorgang.id, vorgang.thema, "info_entfallen", grund)
        return
    laufend = paare.laufend_bilden(vorgang.thema)
    try:
        if ref.werkzeug == "codex":
            text = postfach.text("abgabe_info", vorgang.thema, laufend, vorgang.id)
            ok = _codex_senden(ref.kennung, text, transport) == "ok"
        else:
            # Der Aufrufer soll die Themensperre halten (postfach.info_statt_auftrag); ohne sie ist der
            # Ablauf trotzdem sicher (Abholer prüfen die Datei erneut), also läuft er auch bei belegter Sperre.
            with zustand.thema_sperre(vorgang.thema, blockierend=True, frist=av.THEMENSPERRE_FRIST):
                postfach.info_statt_auftrag(ref.werkzeug, ref.kennung, vorgang.id, vorgang.thema, laufend)
            ok = True
    except Exception:  # noqa: BLE001 - die Info hält den Ablauf nie auf
        ok = False
    protokoll.schreiben(vorgang.id, vorgang.thema, "info_gesendet" if ok else "info_fehlgeschlagen", ref.werkzeug)


def _rolle_setzen(vorgang: av.Vorgang, *, repo: Path | None, jetzt: datetime,
                  transport: Transport | None) -> av.Vorgang:
    if vorgang.phase not in _NACH_ABGABE:
        return vorgang
    info_an: ChatRef | None = None
    try:
        with zustand.thema_sperre(vorgang.thema, blockierend=True, frist=av.THEMENSPERRE_FRIST) as frei:
            if not frei:
                return vorgang          # Thema belegt: der nächste Takt versucht es erneut
            aktuell = av.finden(vorgang.id)
            if aktuell is None or aktuell.phase not in _NACH_ABGABE:
                return aktuell or vorgang
            if any(v.thema == aktuell.thema and v.id != aktuell.id and v.phase == "sende" for v in av.lesen()):
                return aktuell          # die Nachricht eines anderen Vorgangs geht gerade raus: Marke nicht wechseln
            text = _markentext(aktuell.thema, repo)
            schon_gesetzt = besitz.assistent_marke(text) == (aktuell.ziel, aktuell.thema, aktuell.id)
            eigene_zwischenmarke = (modi.ist_zwischenmarke(text, aktuell.thema)
                                    and text.split()[3] == aktuell.ziel)
            if not schon_gesetzt and not eigene_zwischenmarke and text != aktuell.vorzustand_marke.strip():
                neu, gewonnen = av.phase_gewinnen(aktuell.id, _NACH_ABGABE, "verworfen", fehler="Stand geändert")
                if gewonnen:
                    protokoll.schreiben(aktuell.id, aktuell.thema, "verworfen", "Stand geändert")
                return neu or aktuell
            if not schon_gesetzt:       # sonst ist ein früherer Lauf nach dem Rollensetzen abgebrochen
                modi.master_uebergeben_gesperrt(aktuell.thema, aktuell.ziel, vorgang_id=aktuell.id, repo=repo)
            neu, gewonnen = av.phase_gewinnen(aktuell.id, _NACH_ABGABE, "rolle_gesetzt")
            if gewonnen:
                protokoll.schreiben(aktuell.id, aktuell.thema, "rolle_gesetzt", aktuell.ziel)
                if neu is not None and neu.abgabe == "uebersprungen":
                    info_an = ChatRef.aus_dict(neu.von_chat)     # ohne alten Chat gibt es nichts zu sagen
            if neu is not None and neu.phase not in (*_NACH_ABGABE, "verworfen"):
                _ueberholte_verwerfen(neu)
            ergebnis = neu or aktuell
    except (modi.ModusFehler, zustand.SperrFehler, OSError) as fehler:
        raise _assistentfehler(fehler, vorspann="Rolle nicht gesetzt") from fehler
    # Erst jetzt, außerhalb der Themensperre und nur für den Gewinner: die Info an den alten Chat. Stürzt das
    # Programm hier ab, geht sie verloren (nie nachsenden); bei einem Fehler steht nur das Protokoll.
    if info_an is not None:
        _info_senden(ergebnis, info_an, transport, repo)
    return ergebnis


def _ueberholte_verwerfen(neu: av.Vorgang) -> None:
    """Unter gehaltener Themensperre: alle anderen Vorgänge des Themas, deren Rolle schon gesetzt war, verwerfen.

    Die Marke gehört jetzt `neu`; ältere Vorgänge (Phasen `av.UEBERHOLBAR`) sind nach G3 ungültig, ihre
    Postfachdateien werden beim Abholen verworfen. Ein einziger `av.aendern`-Schritt, danach je ein Protokolleintrag.
    """
    jetzt = datetime.now(timezone.utc).isoformat()
    verworfen: list[av.Vorgang] = []

    def aendere(alt: list[av.Vorgang]) -> list[av.Vorgang]:
        ergebnis = []
        for v in alt:
            if v.thema == neu.thema and v.id != neu.id and v.phase in av.UEBERHOLBAR:
                v = replace(v, phase="verworfen", fehler="überholt", zeit=jetzt)
                verworfen.append(v)
            ergebnis.append(v)
        return ergebnis

    av.aendern(aendere)
    for v in verworfen:
        protokoll.schreiben(v.id, v.thema, "verworfen", "überholt")


def _zustellen(vorgang: av.Vorgang, *, repo: Path | None, jetzt: datetime,
               transport: Transport | None) -> av.Vorgang:
    ref = ChatRef.aus_dict(vorgang.nach_chat)
    if vorgang.phase != "rolle_gesetzt" or ref is None:
        return vorgang                  # ohne neuen Chat später nachholbar ("Zustellung nachholen")
    # Markenprüfung und `sende`-Gewinn gehören unter dieselbe Themensperre: sonst könnte ein zweiter Wechsel
    # dazwischen seine Marke schreiben und der alte Vorgang schickte einen veralteten Übernahmeauftrag.
    # Der Transport selbst läuft weiter außerhalb jeder Sperre.
    try:
        with zustand.thema_sperre(vorgang.thema, blockierend=True, frist=av.THEMENSPERRE_FRIST) as frei:
            if not frei:
                return vorgang          # belegt: der nächste Takt versucht es erneut
            aktuell = av.finden(vorgang.id)
            if aktuell is None or aktuell.phase != "rolle_gesetzt":
                return aktuell or vorgang
            grund = av.marke_pruefen(aktuell.thema, aktuell.id, rolle=aktuell.ziel, repo=repo)
            if grund is not None:       # ein späterer Wechsel hat überholt: dem neuen Chat nichts mehr sagen
                grund = "Marke gehört nicht mehr zu diesem Vorgang"   # fester Text: die Prüfung zitiert Dateiinhalt
                neu, gewonnen = av.phase_gewinnen(aktuell.id, ("rolle_gesetzt",), "verworfen", fehler=grund)
                if gewonnen:
                    protokoll.schreiben(aktuell.id, aktuell.thema, "verworfen", grund)
                return neu or aktuell
            sende, gewonnen = av.phase_gewinnen(aktuell.id, ("rolle_gesetzt",), "sende")
    except (modi.ModusFehler, zustand.SperrFehler, OSError) as fehler:
        raise _assistentfehler(fehler, vorspann="Marke nicht prüfbar") from fehler
    if not gewonnen or sende is None:
        return sende or vorgang         # ein anderer Takt hat gewonnen: er sendet, wir nicht
    protokoll.schreiben(vorgang.id, vorgang.thema, "neu_zustellweg", ref.werkzeug)
    laufend = paare.laufend_bilden(vorgang.thema)
    text = postfach.text("neu", vorgang.thema, laufend, vorgang.id, sende.abgabe == "uebersprungen")
    # Restfenster: Seit dem Freigeben der Themensperre kann ein anderer Wechsel die Marke geändert haben. Ein
    # Transport unter der Sperre bleibt verboten (G8d), deshalb hier außerhalb der Sperre noch einmal prüfen. Ein
    # Rest bleibt grundsätzlich (auch nach dem Senden kann jemand wechseln); die Gültigkeit erzwingt die Quittung.
    try:
        veraltet = av.marke_pruefen(vorgang.thema, vorgang.id, rolle=vorgang.ziel, repo=repo)
        lesbar = True
    except Exception:  # noqa: BLE001 - nicht prüfbar: im Zweifel nichts senden
        veraltet, lesbar = None, False
    if veraltet is not None or not lesbar:
        phase, felder = ("verworfen", {"fehler": "Marke gehört nicht mehr zu diesem Vorgang"}) if lesbar \
            else ("fehler", {"fehler": NEU_FEHLER["fehler"]})
        neu = av.phase_wechseln(vorgang.id, ("sende",), phase, **felder)
        protokoll.schreiben(vorgang.id, vorgang.thema, "neu_entfallen", phase)
        return neu or sende
    if ref.werkzeug == "codex":
        erg = _codex_senden(ref.kennung, text, transport)
    else:
        erg = "ok" if _postfach_legen(ref, vorgang.id, vorgang.thema, "neu") else "fehler"
    phase = "im_postfach" if erg == "ok" and ref.werkzeug != "codex" else NEU_WEG[erg]
    felder = {} if erg == "ok" else {"fehler": NEU_FEHLER[erg]}   # sonst bleibt ein früherer Grund (z. B. übersprungene Abgabe)
    # Vergleich-und-Setzen nur aus `sende`: hat der neue Chat schon quittiert/abgeholt, bleibt dessen Phase.
    neu = av.phase_wechseln(vorgang.id, ("sende",), phase, **felder)
    protokoll.schreiben(vorgang.id, vorgang.thema, "neu_ergebnis", phase)
    return neu or sende
