"""Ansichtsmodell des Wechselfensters (E7/E8): reine Funktionen und Momentaufnahmen, **ohne** Oberfläche.

Das Fenster (`fenster.py`) ist nur eine dünne Schicht darüber. Hier liegt alles, was sich ohne Bildschirm
prüfen lässt:

* `aufnehmen()` liest einmal alle Quellen (Paare, Marken, Kopfzeilen, Chat-Register, Statusregister,
  Vorgänge, Protokoll) und liefert eine unveränderliche `Momentaufnahme`. Jede Quelle ist einzeln
  fehlertolerant; ein Fehler steht nur als Klassenname in `Momentaufnahme.hinweise`. Das Fenster ruft die
  Funktion im Hintergrund-Thread auf, nie im Tk-Thread.
* `chat_optionen()` baut die Auswahllisten für „Von-Chat“ und „Nach-Chat“ (zuletzt aktiv zuerst, vorbelegt
  mit dem Vorschlag aus `chat_zuordnung`). **Ohne Vorschlag ist nichts vorbelegt**: Sebastian muss dann
  ausdrücklich einen Chat oder den Eintrag „ohne …“ wählen (sicherere Variante gegen versehentliches Überspringen
  der Abgabe).
* `zustellhinweis()` ist der ehrliche Hinweis nach E8 je Vorgang und Zustellweg – nie „zugestellt“ ohne Beleg.
* `uebergabe_ausfuehren`, `weiter`, `abbrechen` sind die drei Aktionen des Fensters; sie fangen jede Ausnahme
  und geben nur bereinigte Texte zurück (feste Sätze oder Fehlerklassen, nie Pfade oder Kennungen).
* `protokoll_klartext()` übersetzt einen Protokolleintrag in einen deutschen Satz aus einer Tabelle.

Datenschutz (G9): Chat-Titel, Ordner und Kennungen kommen nur in Texten für das **lokale** Fenster vor, nie in
Nachrichten, im Protokoll oder in Logs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from . import (anzeige, assistent, automatik, chat_register, chat_zuordnung, modi, paare, postfach, protokoll,
               status, uebergabe)
from . import assistent_vorgaenge as av

ABGESCHLOSSEN_ANZAHL = 10
PROTOKOLL_ANZAHL = 50
HINWEIS_ABGABE_NACH = timedelta(minutes=2)   # so lange darf die Abgabe offen sein, bevor Windows erinnert
HINWEIS_ALTER = timedelta(minutes=15)        # ältere Vorgänge melden nichts mehr (z. B. nach einem Neustart der Leiste)
ALT_CHAT_LEER = "ohne alten Chat (Abgabe überspringen)"
NEU_CHAT_LEER = "ohne (nur Rolle setzen)"
OHNE_TITEL = "(ohne Titel)"

# Kurzer Begriff für die Menüzeile „Wechsel <thema>: <Phase>“ und die Meldungen.
PHASE_KURZ = {
    "vorbereitet": "wird vorbereitet",
    "abgabe_sende": "wartet auf Abgabe",
    "abgabe_angefragt": "wartet auf Abgabe",
    "abgabe_unklar": "wartet auf Abgabe",
    "abgabe_fehler": "Abgabe nicht gestartet",
    "abgegeben": "Rolle wird gesetzt",
    "abgabe_uebersprungen": "Rolle wird gesetzt",
    "rolle_gesetzt": "Rolle gesetzt",
    "sende": "wird zugestellt",
    "gesendet": "zugestellt (Queue)",
    "im_postfach": "liegt im Postfach",
    "im_chat": "im Chat, Quittung offen",
    "fehler": "Zustellung fehlgeschlagen",
    "unklar": "Zustellung unklar",
    "bestaetigt": "übernommen",
    "verworfen": "verworfen",
}

# Phase in Klartext für die Vorgangsliste im Fenster.
PHASE_TEXT = {
    "vorbereitet": "wird vorbereitet",
    "abgabe_sende": "Abgabe-Auftrag wird gesendet",
    "abgabe_angefragt": "Abgabe angefragt",
    "abgabe_unklar": "Abgabe-Zustellung unklar",
    "abgabe_fehler": "Abgabe-Auftrag nicht gestartet",
    "abgegeben": "alter Chat hat abgegeben",
    "abgabe_uebersprungen": "Abgabe übersprungen",
    "rolle_gesetzt": "Rolle gesetzt",
    "sende": "Nachricht wird zugestellt",
    "gesendet": "Nachricht gesendet",
    "im_postfach": "Nachricht liegt im Postfach",
    "im_chat": "Nachricht im Chat angekommen",
    "fehler": "Zustellung fehlgeschlagen",
    "unklar": "Zustellung unklar",
    "bestaetigt": "übernommen",
    "verworfen": "verworfen",
}

# Feste Gründe, die Ablauf und Wiederaufnahme ins Protokoll schreiben; nur diese erscheinen im Klartext.
_GRUENDE = {
    "kein alter Chat gewählt": "kein alter Chat gewählt",
    "Frist abgelaufen": "Frist abgelaufen",
    "Stand geändert": "Stand hat sich geändert",
    "überholt": "durch einen späteren Wechsel überholt",
    "Marke gehört nicht mehr zu diesem Vorgang": "Besitzmarke gehört nicht mehr zu diesem Wechsel",
    "Vorgang verworfen": "Vorgang war schon verworfen",
    "Marke nicht lesbar": "Besitzmarke nicht lesbar",
    av.ABBRUCH_GRUND: "von Hand abgebrochen",
}
_ABGABE_ERGEBNIS = {
    "abgabe_angefragt": "Abgabe-Auftrag zugestellt, Quittung offen",
    "abgabe_fehler": "Abgabe-Auftrag nicht gestartet",
    "abgabe_unklar": "Abgabe-Zustellung unklar",
}
_NEU_ERGEBNIS = {
    "gesendet": "Nachricht an den neuen Chat gesendet",
    "im_postfach": "Nachricht liegt im Postfach des neuen Chats",
    "fehler": "Zustellung an den neuen Chat nicht gestartet",
    "unklar": "Zustellung an den neuen Chat unklar",
    "verworfen": "Zustellung entfallen, Wechsel verworfen",
}


def _name(rolle: object) -> str:
    return anzeige.MASTER_NAMEN.get(rolle, "unbekannt") if isinstance(rolle, str) else "unbekannt"


def _aware(zeit: datetime) -> datetime:
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)


def _zeit(text: object) -> datetime | None:
    if not isinstance(text, str):
        return None
    try:
        return _aware(datetime.fromisoformat(text))
    except ValueError:
        return None


def uhrzeit(zeit: datetime | None, jetzt: datetime | None = None) -> str:
    """`hh:mm` in Ortszeit; liegt der Tag nicht beim heutigen, steht das Datum davor."""
    if zeit is None:
        return "?"
    lokal = _aware(zeit).astimezone()
    heute = _aware(jetzt or datetime.now(timezone.utc)).astimezone().date()
    return lokal.strftime("%H:%M") if lokal.date() == heute else lokal.strftime("%d.%m. %H:%M")


def alter_text(zeit: datetime | None, jetzt: datetime) -> str:
    if zeit is None:
        return "Alter unbekannt"
    sekunden = max(0, int((_aware(jetzt) - _aware(zeit)).total_seconds()))
    if sekunden < 90:
        return "gerade eben"
    if sekunden < 3600 * 2:
        return f"vor {sekunden // 60} min"
    if sekunden < 86400 * 2:
        return f"vor {sekunden // 3600} h"
    return f"vor {sekunden // 86400} d"


def phase_kurz(phase: str) -> str:
    return PHASE_KURZ.get(phase, phase)


def offen(vorgang: av.Vorgang) -> bool:
    return vorgang.phase not in av.ENDGUELTIG


def kann_abbrechen(vorgang: av.Vorgang) -> bool:
    return vorgang.phase in av.ABBRECHBAR


# --- Vorgänge ------------------------------------------------------------------------

def frist_rest(vorgang: av.Vorgang, jetzt: datetime) -> timedelta | None:
    """Rest der Abgabefrist (kann negativ sein); `None`, wenn die Zeit nicht lesbar ist."""
    beginn = _zeit(vorgang.abgabe_seit or vorgang.zeit)
    if beginn is None:
        return None
    return assistent.ABGABE_FRIST - (_aware(jetzt) - beginn)


def _minuten_sekunden(rest: timedelta) -> str:
    gesamt = max(0, int(rest.total_seconds()))
    return f"{gesamt // 60}:{gesamt % 60:02d}"


def frist_ende(vorgang: av.Vorgang) -> datetime | None:
    beginn = _zeit(vorgang.abgabe_seit or vorgang.zeit)
    return None if beginn is None else beginn + assistent.ABGABE_FRIST


def zustellhinweis(vorgang: av.Vorgang, jetzt: datetime | None = None) -> str:
    """Ehrlicher Hinweis zum Zustellweg (E8): sagt nur, was die Phase belegt, und was Sebastian noch tun muss."""
    jetzt = jetzt or datetime.now(timezone.utc)
    phase, nach = vorgang.phase, vorgang.nach_chat
    ziel = _name(vorgang.ziel)
    if phase in av.ABGABE_OFFEN or phase == "abgabe_fehler":
        rest = frist_rest(vorgang, jetzt)
        if rest is None:
            frist = "Frist läuft"
        elif rest.total_seconds() <= 0:
            frist = "Frist abgelaufen, wird beim nächsten Takt übersprungen"
        else:
            frist = f"Frist läuft noch {_minuten_sekunden(rest)}"
        if phase == "abgabe_fehler":
            return f"Abgabe-Auftrag nicht gestartet – {frist}, danach wird die Abgabe übersprungen"
        text = f"wartet auf Abgabe des alten Chats ({frist})"
        if (vorgang.von_chat or {}).get("werkzeug") == "hermes":
            text += " · Hermes: noch kein automatischer Empfang – Text kopieren und im alten Chat einfügen"
        return text
    if phase == "bestaetigt":
        return "übernommen ✓"
    if phase in ("verworfen", "fehler", "unklar"):
        grund = (vorgang.fehler or "")[:av.GRUND_MAX]
        return f"{PHASE_TEXT[phase]}: {grund}" if grund else PHASE_TEXT[phase]
    if phase == "im_chat":
        return "im Chat angekommen, Quittung offen"
    if phase == "gesendet" and vorgang.ziel == "codex":
        return "Codex: zugestellt (Queue)"
    if phase == "im_postfach" and vorgang.ziel == "claude":
        return "Claude: liegt im Postfach, kommt mit der nächsten Eingabe/dem nächsten Werkzeugschritt in diesem Chat"
    if phase == "im_postfach" and vorgang.ziel == "hermes":
        return "Hermes: noch kein automatischer Empfang – Text unten kopieren und im Hermes-Chat einfügen"
    if phase == "rolle_gesetzt" and nach is None:
        return f"Rolle bei {ziel} gesetzt – kein neuer Chat gewählt, nichts zugestellt"
    if phase == "rolle_gesetzt":
        return f"Rolle bei {ziel} gesetzt, Zustellung folgt"
    if phase in ("abgegeben", "abgabe_uebersprungen"):
        return "Rolle wird beim nächsten Takt gesetzt"
    if phase == "vorbereitet":
        return "wird vorbereitet"
    if phase == "sende":
        return "Nachricht wird gerade zugestellt"
    return PHASE_TEXT.get(phase, phase)


def nachrichtentext(vorgang: av.Vorgang) -> str | None:
    """Text zum Kopieren für Hermes (noch kein automatischer Empfang); sonst `None`.

    Hermes als Ziel nach dem Postfach (`im_postfach`) bekommt die Übernahme-Nachricht; ist Hermes der alte
    Chat und die Abgabe offen, den Abgabe-Auftrag. Es sind feste Satzbausteine – keine Kennung, kein Titel.
    """
    try:
        laufend = paare.laufend_bilden(vorgang.thema)
        if vorgang.phase == "im_postfach" and vorgang.ziel == "hermes":
            return postfach.text("neu", vorgang.thema, laufend, vorgang.id, vorgang.abgabe == "uebersprungen")
        if vorgang.phase in av.ABGABE_OFFEN and (vorgang.von_chat or {}).get("werkzeug") == "hermes":
            return postfach.text("abgabe_auftrag", vorgang.thema, laufend, vorgang.id)
    except (paare.PaarFehler, KeyError):
        return None
    return None


@dataclass(frozen=True)
class VorgangZeile:
    id: str
    thema: str
    richtung: str                 # „Claude → Hermes“
    phase: str                    # Phase in Klartext
    hinweis: str                  # Zustellweg-Hinweis nach E8
    offen: bool
    kann_abbrechen: bool
    kopiertext: str | None = None


def vorgang_zeile(vorgang: av.Vorgang, jetzt: datetime | None = None) -> VorgangZeile:
    jetzt = jetzt or datetime.now(timezone.utc)
    return VorgangZeile(vorgang.id, vorgang.thema, f"{_name(vorgang.von)} → {_name(vorgang.ziel)}",
                        PHASE_TEXT.get(vorgang.phase, vorgang.phase), zustellhinweis(vorgang, jetzt),
                        offen(vorgang), kann_abbrechen(vorgang), nachrichtentext(vorgang))


def vorgang_zeilen(vorgaenge: Sequence[av.Vorgang], jetzt: datetime | None = None) -> list[VorgangZeile]:
    """Alle offenen Vorgänge (neueste zuerst) und danach die letzten `ABGESCHLOSSEN_ANZAHL` abgeschlossenen."""
    neueste_zuerst = sorted(vorgaenge, key=lambda v: v.id, reverse=True)
    auswahl = [v for v in neueste_zuerst if offen(v)]
    auswahl += [v for v in neueste_zuerst if not offen(v)][:ABGESCHLOSSEN_ANZAHL]
    return [vorgang_zeile(v, jetzt) for v in auswahl]


# --- Windows-Hinweise (Leiste) ----------------------------------------------------------

_ROLLE_PHASEN = ("rolle_gesetzt", "sende", "gesendet", "im_postfach", "im_chat")


def hinweis_fuer(vorgang: av.Vorgang, jetzt: datetime) -> tuple[str, str] | None:
    """`(Ereignis, Text)` des Windows-Hinweises, der zum aktuellen Stand des Vorgangs gehört, sonst `None`.

    Ereignisse: `abgabe_offen` (alter Chat hat nach `HINWEIS_ABGABE_NACH` noch nicht abgegeben), `rolle`,
    `uebernommen`, `blick` (Fehler, unklar, verworfen). Die Leiste meldet je Vorgang und Ereignis genau einmal.
    Vorgänge, deren letzte Änderung länger als `HINWEIS_ALTER` zurückliegt, melden nichts. Ein von Hand
    abgebrochener Vorgang braucht keinen Blick ins Fenster. Die Texte enthalten nur Thema, Zielname und Uhrzeit.
    """
    geaendert = _zeit(vorgang.zeit)
    if geaendert is None or _aware(jetzt) - geaendert > HINWEIS_ALTER:
        return None
    thema, ziel = vorgang.thema, _name(vorgang.ziel)
    if vorgang.phase in av.ABGABE_OFFEN:
        beginn = _zeit(vorgang.abgabe_seit or vorgang.zeit)
        ende = frist_ende(vorgang)
        if beginn is None or ende is None or _aware(jetzt) - beginn < HINWEIS_ABGABE_NACH:
            return None
        return "abgabe_offen", (f"{thema}: alter Chat hat noch nicht abgegeben – bitte kurz anstoßen "
                                f"(Frist bis {ende.astimezone().strftime('%H:%M')})")
    if vorgang.phase in _ROLLE_PHASEN:
        return "rolle", f"{thema}: Rolle jetzt bei {ziel}"
    if vorgang.phase == "bestaetigt":
        return "uebernommen", f"{thema}: {ziel} hat übernommen ✓"
    if vorgang.phase in ("fehler", "unklar") or (vorgang.phase == "verworfen" and vorgang.fehler != av.ABBRUCH_GRUND):
        return "blick", f"{thema}: Wechsel braucht Blick ins Fenster"
    return None


# --- Protokoll -----------------------------------------------------------------------

def _grund_text(grund: object) -> str:
    return _GRUENDE.get(grund, "") if isinstance(grund, str) else ""


def _satz(entscheidung: str, grund: object) -> str:
    if entscheidung == "angelegt":
        teile = grund.split(" -> ") if isinstance(grund, str) else []
        if len(teile) == 2 and all(t in anzeige.MASTER_NAMEN for t in teile):
            return f"Wechsel angelegt: {_name(teile[0])} → {_name(teile[1])}"
        return "Wechsel angelegt"
    if entscheidung in ("abgabe_uebersprungen", "verworfen", "info_entfallen"):
        titel = {"abgabe_uebersprungen": "Abgabe übersprungen", "verworfen": "Wechsel verworfen",
                 "info_entfallen": "Info an den alten Chat entfallen"}[entscheidung]
        zusatz = _grund_text(grund)
        return f"{titel}: {zusatz}" if zusatz else titel
    if entscheidung == "abgabe_zustellweg":
        return f"Abgabe-Auftrag an {_name(grund)} unterwegs"
    if entscheidung == "abgabe_ergebnis":
        return _ABGABE_ERGEBNIS.get(grund, "Abgabe-Auftrag: Ergebnis festgehalten") if isinstance(grund, str) \
            else "Abgabe-Auftrag: Ergebnis festgehalten"
    if entscheidung == "info_gesendet":
        return f"Info an den alten Chat ({_name(grund)}) gesendet"
    if entscheidung == "info_fehlgeschlagen":
        return f"Info an den alten Chat ({_name(grund)}) fehlgeschlagen"
    if entscheidung == "rolle_gesetzt":
        return f"Rolle gesetzt: {_name(grund)} führt das Thema"
    if entscheidung == "neu_zustellweg":
        return f"Nachricht an den neuen Chat ({_name(grund)}) unterwegs"
    if entscheidung == "neu_entfallen":
        return "Zustellung an den neuen Chat entfallen (Besitzmarke gehört nicht mehr zu diesem Wechsel)"
    if entscheidung == "neu_ergebnis":
        return _NEU_ERGEBNIS.get(grund, "Zustellung: Ergebnis festgehalten") if isinstance(grund, str) \
            else "Zustellung: Ergebnis festgehalten"
    if entscheidung == "automatik_ausgeloest":
        return "Automatik hat den Wechsel zu Codex über den Wechselassistenten ausgelöst"
    if entscheidung == "automatik_nicht_gestartet":
        klasse = grund if isinstance(grund, str) and grund.isidentifier() else "Fehler"
        return f"Automatik: Wechsel nicht gestartet ({klasse})"
    if entscheidung == "fortsetzen_fehlgeschlagen":
        klasse = grund if isinstance(grund, str) and grund.isidentifier() else "Fehler"
        return f"Fortsetzen fehlgeschlagen ({klasse}) – der nächste Takt versucht es erneut"
    return "Eintrag im Protokoll"


def protokoll_klartext(eintrag: dict, jetzt: datetime | None = None) -> str:
    """Eine Protokollzeile als deutscher Satz: `[Zeit] Thema: Satz`. Die Vorgangs-ID erscheint nie."""
    zeit = uhrzeit(_zeit(eintrag.get("zeit")), jetzt)
    thema = eintrag.get("thema")
    thema = thema if isinstance(thema, str) and paare.THEMA_MUSTER.fullmatch(thema) else "?"
    entscheidung = eintrag.get("entscheidung")
    satz = _satz(entscheidung, eintrag.get("grund")) if isinstance(entscheidung, str) else "Eintrag im Protokoll"
    return f"{zeit}  {thema}: {satz}"


def protokoll_zeilen(eintraege: Sequence[dict], jetzt: datetime | None = None) -> list[str]:
    """Neueste zuerst."""
    return [protokoll_klartext(e, jetzt) for e in reversed(list(eintraege))]


# --- Themen und Chats -----------------------------------------------------------------

@dataclass(frozen=True)
class ThemaZeile:
    thema: str
    master: str          # Anzeigename des Besitzers der Marke
    master_rolle: str | None   # claude | codex | hermes, sonst None (reserviert/unbekannt)
    kopf: str            # „ja · vor 5 min“ / „nein · vor 2 h“ / „fehlt“
    automatik: bool


@dataclass(frozen=True)
class ChatInfo:
    chat: chat_register.Chat
    vorschlag: str | None
    grund: str
    zustand: str         # arbeitet | ruht | unbekannt


@dataclass(frozen=True)
class ChatEintrag:
    """Ein Eintrag im Auswahlfeld; `werkzeug`/`kennung` sind bei den „ohne“-Einträgen `None`."""
    text: str
    werkzeug: str | None = None
    kennung: str | None = None
    vorschlag_thema: str | None = None

    @property
    def leer(self) -> bool:
        return self.kennung is None


@dataclass(frozen=True)
class Momentaufnahme:
    zeit: datetime
    themen: tuple[ThemaZeile, ...] = ()
    chats: tuple[ChatInfo, ...] = ()
    vorgaenge: tuple[VorgangZeile, ...] = ()
    protokoll: tuple[str, ...] = ()
    hinweise: tuple[str, ...] = ()


def _besitzer(thema: str, repo: Path | None) -> tuple[str, str | None]:
    """`(Anzeigename, Rolle)` des Besitzers der Marke; bei Lesefehlern „unbekannt“."""
    try:
        besitzer = modi.snapshot([thema], repo=repo)[thema][1]
    except Exception:  # noqa: BLE001 - ein Lesefehler macht das Thema „unbekannt“, nie einen Absturz
        return "unbekannt", None
    if besitzer in modi.ZIEL_ROLLEN:
        return _name(besitzer), besitzer
    return ("reserviert (Umschaltung läuft)" if besitzer == "reserviert" else "unbekannt"), None


def _kopf(paar: paare.Paar, repo: Path | None, jetzt: datetime) -> str:
    if repo is None:
        return "unbekannt"
    kopf = automatik.kopfzeile_lesen(repo / paar.laufend)
    if kopf is None:
        return "fehlt"
    bereit, zeit, _ = kopf
    return f"{bereit} · {alter_text(zeit, jetzt)}"


def _themen(jetzt: datetime) -> tuple[list[ThemaZeile], list[str]]:
    hinweise: list[str] = []
    try:
        liste = paare.lesen()
    except Exception as fehler:  # noqa: BLE001
        return [], [f"Themen nicht lesbar ({type(fehler).__name__})"]
    try:
        repo: Path | None = uebergabe.repo_wurzel()
    except Exception as fehler:  # noqa: BLE001
        repo = None
        hinweise.append(f"Repository nicht gefunden ({type(fehler).__name__})")
    zeilen = []
    for paar in liste:
        name, rolle = _besitzer(paar.thema, repo)
        zeilen.append(ThemaZeile(paar.thema, name, rolle, _kopf(paar, repo, jetzt), paar.aktiv))
    return zeilen, hinweise


def _zustand(chat: chat_register.Chat) -> str:
    stand = status.lesen(chat.werkzeug, chat.kennung)
    return "unbekannt" if stand is None else stand[0]


def _chats(jetzt: datetime) -> tuple[list[ChatInfo], list[str]]:
    try:
        ergebnis, zeilen = chat_zuordnung.uebersicht_mit_quellen(jetzt)
    except Exception as fehler:  # noqa: BLE001
        return [], [f"Chatliste nicht lesbar ({type(fehler).__name__})"]
    infos = [ChatInfo(chat, thema, grund, _zustand(chat)) for chat, thema, grund in zeilen]
    hinweise = [f"Chatquelle {quelle}: {stand}" for quelle, stand in ergebnis.quellen.items()
                if stand not in ("ok", "fehlt")]
    return infos, hinweise


def aufnehmen(jetzt: datetime | None = None) -> Momentaufnahme:
    """Alle Quellen einmal lesen. Jede Quelle ist einzeln fehlertolerant; diese Funktion wirft nie."""
    jetzt = jetzt or datetime.now(timezone.utc)
    hinweise: list[str] = []
    themen, h = _themen(jetzt)
    hinweise += h
    chats, h = _chats(jetzt)
    hinweise += h
    zeilen: list[VorgangZeile] = []
    try:
        zeilen = vorgang_zeilen(av.lesen(), jetzt)
    except Exception as fehler:  # noqa: BLE001
        hinweise.append(f"Vorgänge nicht lesbar ({type(fehler).__name__})")
    log: list[str] = []
    try:
        log = protokoll_zeilen(protokoll.lesen(PROTOKOLL_ANZAHL), jetzt)
    except Exception as fehler:  # noqa: BLE001
        hinweise.append(f"Protokoll nicht lesbar ({type(fehler).__name__})")
    return Momentaufnahme(jetzt, tuple(themen), tuple(chats), tuple(zeilen), tuple(log), tuple(hinweise))


# --- Chat-Auswahl ---------------------------------------------------------------------

def chat_text(info: ChatInfo, thema: str | None, jetzt: datetime | None = None) -> str:
    """`Titel · zuletzt hh:mm · arbeitet/ruht/unbekannt` (nur für das lokale Fenster; G9)."""
    chat = info.chat
    titel = chat.titel or f"{OHNE_TITEL} {chat.kennung[:8]}"
    text = f"{titel} · zuletzt {uhrzeit(chat.zuletzt, jetzt)} · {info.zustand}"
    if thema is not None and info.vorschlag == thema:
        text += f" · Vorschlag ({info.grund})"
    return text


def chat_optionen(chats: Sequence[ChatInfo], werkzeug: str | None, thema: str | None, *, alt: bool,
                  jetzt: datetime | None = None) -> tuple[list[ChatEintrag], int | None]:
    """Einträge des Auswahlfelds und die vorbelegte Stelle.

    Die Chats des Werkzeugs stehen zuletzt aktiv zuerst, am Ende der Eintrag „ohne …“ (`alt` wählt den Text).
    Vorbelegt wird der jüngste Chat, dessen Vorschlag auf `thema` lautet; gibt es keinen, bleibt die Auswahl
    **leer** (`None`) – Sebastian wählt ausdrücklich.
    """
    leer = ChatEintrag(ALT_CHAT_LEER if alt else NEU_CHAT_LEER)
    if werkzeug is None:
        return [leer], None
    passend = sorted((c for c in chats if c.chat.werkzeug == werkzeug), key=lambda c: c.chat.zuletzt, reverse=True)
    eintraege = [ChatEintrag(chat_text(c, thema, jetzt), c.chat.werkzeug, c.chat.kennung, c.vorschlag)
                 for c in passend]
    vorbelegt = next((i for i, e in enumerate(eintraege) if thema is not None and e.vorschlag_thema == thema), None)
    return [*eintraege, leer], vorbelegt


# --- Übergabe starten --------------------------------------------------------------------

@dataclass(frozen=True)
class Auswahl:
    thema: str | None
    ziel: str | None
    von_master: str | None       # Rolle des Besitzers der Marke (nur claude/codex/hermes)
    von: ChatEintrag | None      # None = noch nichts gewählt
    nach: ChatEintrag | None


def auswahl_pruefen(auswahl: Auswahl) -> str | None:
    """Fehlertext, wenn die Auswahl unvollständig oder widersprüchlich ist, sonst `None`."""
    if not auswahl.thema:
        return "Bitte ein Thema wählen."
    if auswahl.ziel not in modi.ZIEL_ROLLEN:
        return "Bitte ein Ziel wählen (Claude, Codex oder Hermes)."
    if auswahl.von_master is None:
        return "Das Thema ist gerade nicht übergebbar (Besitz unklar oder Umschaltung läuft)."
    if auswahl.von is None:
        return "Bitte den alten Chat wählen – oder ausdrücklich „ohne alten Chat“."
    if auswahl.nach is None:
        return "Bitte den neuen Chat wählen – oder ausdrücklich „ohne“."
    if not auswahl.von.leer and auswahl.von.werkzeug != auswahl.von_master:
        return "Der alte Chat gehört nicht zum aktuellen Master."
    if not auswahl.nach.leer and auswahl.nach.werkzeug != auswahl.ziel:
        return "Der neue Chat gehört nicht zum gewählten Ziel."
    if (not auswahl.von.leer and auswahl.von.werkzeug == auswahl.nach.werkzeug
            and auswahl.von.kennung == auswahl.nach.kennung):
        return "Alter und neuer Chat sind derselbe."
    return None


def zusammenfassung(auswahl: Auswahl) -> str:
    """Eine Zeile für die Bestätigung (nur lokal im Fenster)."""
    von = "ohne alten Chat" if auswahl.von is None or auswahl.von.leer else auswahl.von.text
    nach = "ohne neuen Chat (nur Rolle)" if auswahl.nach is None or auswahl.nach.leer else auswahl.nach.text
    return (f"Thema {auswahl.thema}: {_name(auswahl.von_master)} → {_name(auswahl.ziel)} · "
            f"alter Chat: {von} · neuer Chat: {nach}")


@dataclass(frozen=True)
class Ergebnis:
    ok: bool
    text: str


def _ref(eintrag: ChatEintrag | None) -> assistent.ChatRef | None:
    if eintrag is None or eintrag.leer:
        return None
    return assistent.ChatRef(eintrag.werkzeug or "", eintrag.kennung or "")


def _fehlertext(vorspann: str, fehler: BaseException) -> str:
    if isinstance(fehler, av.AssistentFehler):
        return f"{vorspann}: {fehler}"           # bereinigt (assistent._assistentfehler), nie Pfad oder Kennung
    return f"{vorspann} ({type(fehler).__name__})"


def uebergabe_ausfuehren(auswahl: Auswahl, transport=None) -> Ergebnis:
    """Wechsel starten und – bei einem Codex-Chat, der vom Vorschlag abweicht – als Paar merken.

    Fängt jede Ausnahme. Wurde der Wechsel angelegt, aber das Merken schlug fehl, bleibt das Ergebnis `ok` und
    der Text sagt es dazu.
    """
    fehler_text = auswahl_pruefen(auswahl)
    if fehler_text is not None:
        return Ergebnis(False, fehler_text)
    try:
        vorgang = assistent.uebergeben(auswahl.thema or "", auswahl.ziel or "", von_chat=_ref(auswahl.von),
                                       nach_chat=_ref(auswahl.nach), transport=transport)
    except Exception as fehler:  # noqa: BLE001 - das Fenster zeigt nur bereinigte Texte
        return Ergebnis(False, _fehlertext("Nicht übergeben", fehler))
    text = f"Wechsel {vorgang.thema}: {phase_kurz(vorgang.phase)}"
    nach = auswahl.nach
    if nach is not None and not nach.leer and nach.werkzeug == "codex" and nach.vorschlag_thema != auswahl.thema:
        try:
            chat_zuordnung.bestaetigen("codex", nach.kennung or "", auswahl.thema or "")
            text += " · Codex-Chat als Paar gemerkt"
        except Exception as fehler:  # noqa: BLE001
            text += f" · Paar nicht gemerkt ({type(fehler).__name__})"
    return Ergebnis(True, text)


def weiter(vorgang_id: str) -> Ergebnis:
    """„Jetzt weiter“: einen Takt für diesen Vorgang."""
    try:
        vorgang = assistent.fortsetzen(vorgang_id)
    except Exception as fehler:  # noqa: BLE001
        return Ergebnis(False, _fehlertext("Nicht fortgesetzt", fehler))
    return Ergebnis(True, f"Wechsel {vorgang.thema}: {phase_kurz(vorgang.phase)}")


def abbrechen(vorgang_id: str) -> Ergebnis:
    """„Abbrechen“: nur vor `rolle_gesetzt`."""
    try:
        vorgang = av.abbrechen(vorgang_id)
    except Exception as fehler:  # noqa: BLE001
        return Ergebnis(False, _fehlertext("Nicht abgebrochen", fehler))
    return Ergebnis(True, f"Wechsel {vorgang.thema}: {phase_kurz(vorgang.phase)} (von Hand abgebrochen)")
