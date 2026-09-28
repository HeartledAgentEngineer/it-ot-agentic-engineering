"""Chat-Andockung der Ereignis-Knoten (N27 Schritt 2, 28.09.2026).

Warum dieses Werkzeug:
  Schritt 1 (``ereignisse_bauen.py``) hat je Anlass einen **Ereignis-Knoten**
  mit Datum, Thema und Datei-Kennungen gelegt. Schritt 2 dockt die **Chats**
  an: zu jedem Ereignis wird gefragt, welche Chats rund um den Tag aktiv waren,
  wie viele Nachrichten sie trugen, welche **Kontakte** geschrieben haben und
  wie viele Medien dabei waren. Damit laesst sich ein Tag spaeter mit den
  Menschen und Gespraechen verbinden, die dazugehoeren.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Netz.** Kein pCloud-Aufruf, kein ``httpx``/``requests``, kein
    LLM-Aufruf. Gelesen werden ausschliesslich drei lokale Dateien.
  * **Kein Nachrichtentext.** Aus ``msgstore.db`` wird **nie** die Spalte mit
    dem Nachrichteninhalt gelesen; die Ausgabe traegt ausschliesslich Kennungen
    (``message._id``), Zaehlungen, Namen (nur wenn
    ``whatsapp_zuordnung.json`` sie liefert) und Nummern-Masken. Ein Feld fuer
    Nachrichteninhalt gibt es im Schema **nicht** (die Pruefungen belegen das).
  * **Keine Klartext-Nummern.** Nummern erscheinen nur als Maske ``***1234``
    (die letzten vier Ziffern), nie vollstaendig.
  * **Keine Bilder.** Es wird keine Bilddatei geoeffnet, kopiert oder
    gespeichert; ``medien`` ist nur eine **Zahl** je Chat.
  * **Kein Schreiben der Datenbank.** ``msgstore.db`` wird ausschliesslich
    ueber ``sqlite3.connect("file:<pfad>?mode=ro", uri=True)`` **nur lesend**
    geoeffnet. Es gibt im Quelltext keine schreibende Anweisung — nur lesende
    ``SELECT``-Abfragen.
  * **Keine Loeschung** ausser der eigenen temp-Datei beim atomaren Schreiben;
    es gibt keine Loeschfunktion, auch nicht "zur Sicherheit".
  * **Kein Schreiben ohne ``--schreiben``.** Der Standard ist ``--trocken``.

Eingabe (alle **nur lesend**):
  1. ``--ereignisse`` (Standard ``~/foto_sortierung/ereignisse.jsonl``):
     die Knoten aus N27a. Genutzt werden genau ``kennung``, ``anlass_id``,
     ``datum`` und ``art``; unbekannte Schluessel werden ignoriert. Das Feld
     ``art`` der Ereignisse traegt im Bestand immer ``"ereignis"`` und wird
     nicht in die Ausgabe uebernommen (die Ausgabe hat ihr eigenes ``art``).
  2. ``--db`` (Standard: die entschluesselte ``msgstore.db`` ausserhalb des
     Repos): die vier Tabellen ``message``, ``chat``, ``jid`` und
     ``message_media``. Es wird nur gelesen.
  3. ``--zuordnung`` (Standard ``~/foto_sortierung/whatsapp_zuordnung.json``):
     aus ``tools/whatsapp/zuordnung_bauen.py``. Je ``chat_row_id`` werden
     ``art``, ``telefonbuch_namen``, ``whatsapp_name``, ``nummer_maske`` und
     (bei Gruppen) ``teilnehmer`` gelesen.

Ausgabe (eingefrorenes Schema, JSONL):
  ``--ausgabe`` (Standard ``~/foto_sortierung/chat_andockung.jsonl``) ist reine
  JSONL: **je Zeile genau ein Ereignis**, kodiert mit ``ensure_ascii=True``
  (ASCII, keine Umlaute) und ``sort_keys=True``. Keine Kopfzeile, kein
  ``zahlen``-Block in der Datei; die Zahlen stehen nur auf der Konsole und im
  Rueckgabewert von ``andocken``. Eine Zeile hat genau diese Schluessel::

      {"anlass_id", "art": "chat_andockung", "fenster": {"von", "bis", "tage"},
       "kennung": "E-" + anlass_id, "kontakte_gesamt", "nachrichten_gesamt",
       "chats": [ {"art", "beteiligte": [{"name", "nummer_maske", "nachrichten"}],
                   "chat_name", "chat_row_id", "erste", "fenster_tage",
                   "gekuerzt", "letzte", "medien", "nachrichten",
                   "nachrichten_kennungen", "von_anderen", "von_mir"} ],
       "chats_anzahl", "datum", "quellen": {...}, "stand"}

  * Sortierung (fest, wie in N27a): ``datum`` aufsteigend, bei Gleichstand
    ``kennung`` aufsteigend; Ereignisse **ohne** Datum stehen hinter den
    datierten (Sortierschluessel ``1``) — reproduzierbar ohne ``None``-Vergleich.
  * ``fenster`` ist das **aeussere** Fenster des Ereignisses: ±1 Tag, also
    ``[datum-1 Tag 00:00, datum+2 Tage 00:00)`` in UTC; ``von``/``bis`` als
    ISO-8601 (``+00:00``), ``tage`` = 1 (der Rand ±1 Tag). Gruppen nutzen **im
    Chat** das strengere Fenster (``fenster_tage`` = 0, derselbe Tag), damit
    ist ``fenster`` bewusst die Obergrenze und je Chat genau notiert, welches
    Fenster galt.
  * ``erste``/``letzte`` = ISO-8601 (UTC, ``+00:00``) der ersten/letzten
    Nachricht **dieses** Chats im Fenster.
  * ``nachrichten_kennungen`` = ``message._id``-Werte aufsteigend,
    **hoechstens 25** je Chat; ``gekuerzt: true``, wenn mehr im Fenster liegen.
  * ``beteiligte`` = Absender (``from_me = 0``) im Fenster, absteigend nach
    Nachrichtenzahl, bei Gleichstand Name aufsteigend.
  * ``chat_name``: Gruppe → ``chat.subject`` (echter Gruppenname), sonst
    ``telefonbuch_namen[0]``, sonst ``whatsapp_name``, sonst ``"unbekannt"``;
    fehlt der Chat in der Zuordnung → ``"unbekannt"``. **Nie** eine Nummer im
    Klartext — der Name nur, wenn die Zuordnung ihn liefert.
  * ``chats`` ist absteigend nach ``nachrichten`` sortiert, bei Gleichstand
    ``chat_row_id`` aufsteigend (reproduzierbar).
  * ``quellen`` nennt ehrlich, woher jedes Feld stammt.

Regeln (so umgesetzt, nicht anders):
  1. **Zeitfenster** (Regel, nicht Auslegung): Einzelchat (``art`` =
     ``einzel``/``sonstiges``, auch unbekannte Art) = ±1 Tag →
     ``[datum-1 Tag 00:00, datum+2 Tage 00:00)``; **Gruppe** = derselbe Tag →
     ``[datum 00:00, datum+1 Tag 00:00)``; ``newsletter`` wie Einzelchat
     (±1 Tag), aber **ohne Kontakt** (traegt keine Namen bei). Die Grenzen
     sind halboffen: 23:59:59 des Vortags faellt hinein, 00:00 des +2. Tages
     nicht.
  2. Datum ohne Uhrzeit gilt als Tagesdatum (UTC); ein mitgegebener Zeitanteil
     wird auf den Tag gekuerzt. Ereignisse **ohne** Datum werden trotzdem als
     Knoten gefuehrt (``fenster: null``, ``nachrichten_gesamt: 0``,
     ``chats: []``) — nichts verschwindet.
  3. **Namensaufloesung der Absender — kein Raten.** Einzelchat: der Partner
     der Zuordnung liefert ``name`` (``telefonbuch_namen[0]`` /
     ``whatsapp_name`` / ``"unbekannt"``) und ``nummer_maske``. Gruppe: die
     Absender-Nummer wird auf die **letzten 4 Ziffern** maskiert und gegen die
     ``teilnehmer`` dieser Gruppe abgeglichen; **nur wenn genau ein Name
     uebrig bleibt**, steht er in ``name``, sonst ``"unbekannt"``. Mehrere
     Treffer mit **verschiedenen** Namen ergeben ebenfalls ``"unbekannt"``
     (kein Muenwurf) — die Maske bleibt stehen, damit nachpruefbar ist.
  4. ``from_me = 1`` zaehlt in ``von_mir`` und erscheint **nicht** unter
     ``beteiligte``. ``sender_jid_row_id IS NULL`` zaehlt in ``von_anderen``
     mit, aber nicht in ``beteiligte``.
  5. Nur Chats mit mindestens einer Nachricht im Fenster stehen in ``chats``.

Zaehlregeln (Invarianten, im Code als Zusicherung und im Test belegt):
  * ``chats_anzahl == len(chats)``
  * ``nachrichten_gesamt == sum(chat.nachrichten)``
  * je Chat: ``von_mir + von_anderen == nachrichten``
  * ``kontakte_gesamt`` = Anzahl **verschiedener** Namen unter allen
    ``beteiligte``-Eintraegen des Ereignisses; der Platzhalter ``"unbekannt"``
    zaehlt dabei **nicht** als Kontakt.

Vorgehen im Code (schnell, kein N+1):
  Ein **einziger** Scan ueber ``message`` (nach ``timestamp`` sortiert), dann
  je Ereignis nur noch Listen-Schnitte per ``bisect``. Dazu werden ``chat``
  (``_id → subject``), ``jid`` (``_id → user``) und ``message_media`` je Chat
  einmal geladen — nicht je Ereignis neu abgefragt.

Aufruf (Kommandozeile)::

    python tools/foto_sortierung/chat_andocken.py --trocken
    python tools/foto_sortierung/chat_andocken.py --limit 3
    python tools/foto_sortierung/chat_andocken.py --ausgabe C:/tmp/a.jsonl --schreiben

Als Modul (Tests, spaetere Schritte): ``haupt(argv=[...])`` sowie die reinen
Funktionen ``ereignisse_laden``, ``zuordnung_laden``, ``db_oeffnen``,
``nachrichten_lesen``, ``medien_lesen``, ``namen_lesen``, ``andocken``,
``knoten_zeile``, ``andockung_schreiben``, ``zahlen_text``.
"""

from __future__ import annotations

import argparse
import bisect
import datetime
import json
import os
import sqlite3
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen private Kennungen und Namen.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_EREIGNISSE = os.path.join(STANDARD_BASIS, "ereignisse.jsonl")
STANDARD_ZUORDNUNG = os.path.join(STANDARD_BASIS, "whatsapp_zuordnung.json")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "chat_andockung.jsonl")

# Standard-Datenbank (woertlich so beauftragt, bewusst AUSSERHALB des Repos).
STANDARD_DB = (
    r"C:\Users\sebas\Desktop\workspace agentic engineering"
    r"\Chats von GPT, GEMINI, Claude\whatsapp_uebertragung"
    r"\backup-decrypted\Databases\msgstore.db"
)

# Die Ausgabe-Art und die Schluessel des eingefrorenen Schemas — bindend fuer
# die Folgeschritte (N27 Schritt 3 liest diese Datei).
ANDOCKUNG_ART = "chat_andockung"
KNOTEN_SCHLUESSEL = (
    "anlass_id", "art", "chats", "chats_anzahl", "datum", "fenster", "kennung",
    "kontakte_gesamt", "nachrichten_gesamt", "quellen", "stand",
)
CHAT_SCHLUESSEL = (
    "art", "beteiligte", "chat_name", "chat_row_id", "erste", "fenster_tage",
    "gekuerzt", "letzte", "medien", "nachrichten", "nachrichten_kennungen",
    "von_anderen", "von_mir",
)
BETEILIGTER_SCHLUESSEL = ("name", "nummer_maske", "nachrichten")
FENSTER_SCHLUESSEL = ("bis", "tage", "von")

# Zeitfenster (Regel, gemessen): "±Tage" Rand um den Ereignistag.
# Einzelchat = ±1 Tag -> [datum-1 Tag 00:00, datum+2 Tage 00:00);
# Gruppe = derselbe Tag -> [datum 00:00, datum+1 Tag 00:00).
# Die Zahl unten ist der RAND in Tagen (Gruppe: 0 Rand = nur der Ereignistag),
# so wie die Quellenangabe ``regel:einzel_1_tag|gruppe_0_tage`` es nennt.
FENSTER_TAGE_EINZEL = 1
FENSTER_TAGE_GRUPPE = 0

ART_GRUPPE = "gruppe"
ART_NEWSLETTER = "newsletter"
ART_UNBEKANNT = "sonstiges"          # unbekannte/fehlende Art = wie Einzelchat
ART_EINZEL = ("einzel", "sonstiges")
PLATZHALTER = "unbekannt"
MAX_KENNUNGEN = 25                   # Hoechstzahl ``message._id`` je Chat

# Ein Tag in Millisekunden (fuer die Fenstergrenzen).
TAG_MS = 24 * 60 * 60 * 1000

# Herkunft der Felder (ehrlich, fuer den ``quellen``-Block).
QUELLE_DATUM = "ereignisse.jsonl"
QUELLE_FENSTER = "regel:einzel_1_tag|gruppe_0_tage"
QUELLE_NACHRICHTEN = "msgstore.db:message"
QUELLE_NAMEN = "whatsapp_zuordnung.json"
QUELLE_MEDIEN = "msgstore.db:message_media"

# Lesbares Datum = echte Kalenderangabe in der Form JJJJ-MM-TT (ASCII).
DATUM_MUSTER_LEN = 10


# ── Kleine Helfer (tolerant lesen, nie raten) ─────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``\\\"\\\"``."""
    return wert.strip() if isinstance(wert, str) else ""


def _als_int(wert):
    """Eine Zahl tolerant lesen — ``None`` statt Ausnahme, ``bool`` zaehlt nicht."""
    if isinstance(wert, bool):
        return None
    if isinstance(wert, int):
        return wert
    if isinstance(wert, str) and wert.strip():
        try:
            return int(wert.strip())
        except ValueError:
            return None
    return None


def _zahl(n) -> str:
    """Eine Zahl mit deutschen Tausenderpunkten (nur fuer die Ausgabe)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _datum_lesen(wert):
    """Ein Datum als ``date`` lesen — sonst ``None`` (nichts geraten).

    Ein Datum ohne Uhrzeit ist ein Tagesdatum; ein mitgegebener Zeitanteil wird
    auf den Tag gekuerzt (``JJJJ-MM-TT``). Nur eine echte Kalenderangabe gilt
    als lesbar.
    """
    text = _text(wert)
    if len(text) < DATUM_MUSTER_LEN:
        return None
    kern = text[:DATUM_MUSTER_LEN]
    if kern[4] != "-" or kern[7] != "-":
        return None
    if not (kern[:4].isdigit() and kern[5:7].isdigit() and kern[8:].isdigit()):
        return None
    try:
        return datetime.date(int(kern[:4]), int(kern[5:7]), int(kern[8:]))
    except ValueError:
        return None


def _letzte_ziffern(text, anzahl: int = 4) -> str:
    """Die letzten ``anzahl`` Ziffern eines Texts — ohne ``re``, nur Ziffern."""
    if not isinstance(text, str):
        return ""
    ziffern = "".join(zeichen for zeichen in text if zeichen.isdigit())
    return ziffern[-anzahl:]


def _maske(user) -> str | None:
    """Eine Nummer/Teilnehmerkennung zur Maske ``***1234`` machen — sonst ``None``.

    Es werden **nur** die letzten vier Ziffern gezeigt; eine Nummer im Klartext
    verlaesst dieses Modul nie.
    """
    rest = _letzte_ziffern(user, 4)
    return "***" + rest if rest else None


def _tag_ms(tag: datetime.date) -> int:
    """00:00 UTC eines Tages als Millisekunden seit der Epoche."""
    beginn = datetime.datetime(tag.year, tag.month, tag.day,
                               tzinfo=datetime.timezone.utc)
    return int(beginn.timestamp() * 1000)


def _iso(ms: int) -> str:
    """Millisekunden seit der Epoche als ISO-8601 in UTC (``+00:00``)."""
    zeit = datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)
    return zeit.isoformat(timespec="seconds")


# ── 1. Lesen (lokal, nur lesend, kein Netz) ───────────────────────────────

def ereignisse_laden(pfad: str) -> list:
    """Die Ereignis-Knoten aus ``ereignisse.jsonl`` lesen (nur lesend).

    Genutzt werden genau ``kennung``, ``anlass_id``, ``datum`` und ``art``.
    ``kennung`` wird ersatzweise ``"E-" + anlass_id``, wenn sie fehlt. Eine
    Zeile **ohne** brauchbare Kennung und ohne ``anlass_id`` traegt keinen
    stabilen Anker und wird uebersprungen (kein erfundener Knoten). Fehlende
    Datei, unlesbares JSON und eine Nicht-Liste ergeben eine deutsche
    ``ValueError``-Meldung.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Pfad fuer die Ereignisse angegeben.")
    if not os.path.isfile(pfad):
        raise ValueError(f"Ereignisse nicht gefunden: {pfad}")
    ereignisse = []
    try:
        with open(pfad, encoding="utf-8") as datei:
            for nummer, zeile in enumerate(datei, start=1):
                zeile = zeile.strip()
                if not zeile:
                    continue
                try:
                    roh = json.loads(zeile)
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Ereignisse nicht lesbar: Zeile {nummer} ist kein "
                        f"gueltiges JSON ({pfad})") from None
                if not isinstance(roh, dict):
                    continue
                anlass_id = _text(roh.get("anlass_id"))
                kennung = _text(roh.get("kennung"))
                if not kennung:
                    kennung = "E-" + anlass_id if anlass_id else ""
                if not kennung:
                    continue
                ereignisse.append({
                    "kennung": kennung,
                    "anlass_id": anlass_id,
                    "datum": _text(roh.get("datum")),
                    "art": _text(roh.get("art")),
                })
    except OSError as problem:
        raise ValueError(
            f"Ereignisse nicht lesbar ({problem.__class__.__name__}): "
            f"{pfad}") from None
    return ereignisse


def zuordnung_laden(pfad: str) -> dict:
    """Die Chat-Zuordnung aus ``whatsapp_zuordnung.json`` lesen (nur lesend).

    Rueckgabe: ``chat_row_id → {art, telefonbuch_namen, whatsapp_name,
    nummer_maske, teilnehmer}``. ``teilnehmer`` ist eine Liste aus
    ``{name, nummer_maske}``. Unbekannte Schluessel werden ignoriert.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Pfad fuer die Zuordnung angegeben.")
    if not os.path.isfile(pfad):
        raise ValueError(f"Zuordnung nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except json.JSONDecodeError as problem:
        raise ValueError(
            f"Zuordnung ist kein gueltiges JSON "
            f"({problem.__class__.__name__}): {pfad}") from None
    except OSError as problem:
        raise ValueError(
            f"Zuordnung nicht lesbar ({problem.__class__.__name__}): "
            f"{pfad}") from None
    if not isinstance(daten, dict):
        raise ValueError(f"Zuordnung ist kein Woerterbuch: {pfad}")
    chats = daten.get("chats")
    if not isinstance(chats, list):
        raise ValueError(f"Zuordnung ohne 'chats'-Liste: {pfad}")

    ordnung: dict = {}
    for eintrag in chats:
        if not isinstance(eintrag, dict):
            continue
        chat_row_id = _als_int(eintrag.get("chat_row_id"))
        if chat_row_id is None:
            continue
        namen = eintrag.get("telefonbuch_namen")
        namen = [n for n in namen if isinstance(n, str) and n.strip()] \
            if isinstance(namen, list) else []
        teilnehmer = []
        roh_teilnehmer = eintrag.get("teilnehmer")
        if isinstance(roh_teilnehmer, list):
            for t in roh_teilnehmer:
                if not isinstance(t, dict):
                    continue
                teilnehmer.append({
                    "name": _text(t.get("name")),
                    "nummer_maske": _text(t.get("nummer_maske")),
                })
        ordnung[chat_row_id] = {
            "art": _text(eintrag.get("art")),
            "telefonbuch_namen": namen,
            "whatsapp_name": _text(eintrag.get("whatsapp_name")),
            "nummer_maske": _text(eintrag.get("nummer_maske")),
            "teilnehmer": teilnehmer,
        }
    return ordnung


def db_oeffnen(pfad: str) -> sqlite3.Connection:
    """``msgstore.db`` **nur lesend** oeffnen (``file:...?mode=ro``, ``uri=True``).

    Fehlender Pfad oder fehlende Datei ergeben eine deutsche ``ValueError``-
    Meldung — es wird nichts kopiert, entschluesselt oder geschrieben. Der Pfad
    wird fuer die URI in Schraegstriche gedreht (Windows-Rueckwaertsstriche
    sind in einer ``file:``-URI nicht gueltig).
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Pfad fuer die Datenbank angegeben.")
    if not os.path.isfile(pfad):
        raise ValueError(f"Datenbank nicht gefunden: {pfad}")
    uri = "file:" + pfad.replace("\\", "/") + "?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.Error as problem:
        raise ValueError(
            f"Datenbank nicht lesbar ({problem.__class__.__name__}): "
            f"{pfad}") from None


def nachrichten_lesen(con: sqlite3.Connection) -> dict:
    """**Ein** Scan ueber ``message``, nach ``timestamp`` sortiert.

    Liest nur ``timestamp``, ``chat_row_id``, ``from_me``, ``sender_jid_row_id``
    und ``_id`` — **nie** die Spalte mit dem Nachrichteninhalt. Zeilen ohne
    ``timestamp`` oder ohne ``chat_row_id`` tragen keinen Bezug und werden
    uebersprungen.

    Rueckgabe: ``{"timestamps": [...], "zeilen": [(ts, chat, from_me, sender,
    _id), ...]}`` — beide Listen sind gleich lang und nach ``timestamp``
    aufsteigend sortiert (stabile Sortierung, damit die ``_id``-Reihenfolge je
    Timestamp erhalten bleibt).
    """
    zeilen = []
    for ts, chat, from_me, sender, msg_id in con.execute(
            "SELECT timestamp, chat_row_id, from_me, sender_jid_row_id, _id "
            "FROM message"):
        if ts is None or chat is None:
            continue
        zeilen.append((int(ts), int(chat), int(from_me or 0), sender, msg_id))
    zeilen.sort(key=lambda eintrag: (eintrag[0], eintrag[4]
                                     if eintrag[4] is not None else -1))
    return {
        "timestamps": [eintrag[0] for eintrag in zeilen],
        "zeilen": zeilen,
    }


def medien_lesen(con: sqlite3.Connection) -> dict:
    """Medien je Chat einmal laden (``message_media`` ueber ``message`` gejoint).

    ``message_media`` hat keinen eigenen ``timestamp``; der Bezug kommt ueber
    ``message._id``. Rueckgabe: ``chat_row_id → [timestamp, ...]`` aufsteigend.
    """
    medien: dict = {}
    for chat, ts in con.execute(
            "SELECT mm.chat_row_id, m.timestamp FROM message_media mm "
            "JOIN message m ON m._id = mm.message_row_id"):
        if chat is None or ts is None:
            continue
        medien.setdefault(int(chat), []).append(int(ts))
    for liste in medien.values():
        liste.sort()
    return medien


def namen_lesen(con: sqlite3.Connection) -> dict:
    """Gruppen-Betreff und JID-Nummer einmal laden.

    Rueckgabe: ``{"chat_subject": {chat._id → subject},
    "jid_user": {jid._id → user}}``. Beides sind reine Nachschlagetabellen.
    """
    chat_subject: dict = {}
    for chat_id, subject in con.execute("SELECT _id, subject FROM chat"):
        if chat_id is not None:
            chat_subject[int(chat_id)] = subject
    jid_user: dict = {}
    for jid_id, user in con.execute("SELECT _id, user FROM jid"):
        if jid_id is not None:
            jid_user[int(jid_id)] = user
    return {"chat_subject": chat_subject, "jid_user": jid_user}


# ── 2. Namensaufloesung der Absender (kein Raten) ─────────────────────────

def _einzel_ident(eintrag: dict):
    """Name und Maske des Partners in einem Einzelchat — nie geraten."""
    namen = eintrag.get("telefonbuch_namen") or []
    name = _text(namen[0]) if namen else ""
    if not name:
        name = _text(eintrag.get("whatsapp_name"))
    if not name:
        name = PLATZHALTER
    return name, (_text(eintrag.get("nummer_maske")) or None)


def _gruppen_ident(teilnehmer: list, user):
    """Name eines Gruppen-Absenders ueber die maskierte Nummer bestimmen.

    Nur wenn **genau ein** Name uebrig bleibt, steht er im Ergebnis; mehrere
    Treffer mit verschiedenen Namen ergeben ``"unbekannt"`` (kein Muenwurf).
    Die Maske bleibt immer stehen, damit nachpruefbar ist.
    """
    maske = _maske(user)
    name = PLATZHALTER
    if maske:
        treffer = set()
        for t in teilnehmer:
            if _text(t.get("nummer_maske")) == maske:
                kandidat = _text(t.get("name"))
                if kandidat:
                    treffer.add(kandidat)
        if len(treffer) == 1:
            name = next(iter(treffer))
    return name, maske


def _chat_name(chat_row_id: int, art: str, eintrag, chat_subject: dict) -> str:
    """Den Anzeigenamen eines Chats bestimmen — **nie** eine Klartext-Nummer."""
    if art == ART_GRUPPE:
        return _text(chat_subject.get(chat_row_id)) or PLATZHALTER
    if eintrag is None:
        return PLATZHALTER
    name, _ = _einzel_ident(eintrag)
    return name


# ── 3. Die Andockung bauen (rein, ohne I/O) ───────────────────────────────

def _sortierschluessel(ereignis: dict):
    """Feste Sortierung: ``datum`` aufsteigend, dann ``kennung`` aufsteigend.

    Undatierte bekommen den Sortierschluessel ``1`` und stehen hinter den
    datierten (``0``) — reproduzierbar ohne ``None``-Vergleich.
    """
    datum = ereignis.get("datum") or ""
    kennung = ereignis.get("kennung") or ""
    if datum:
        return (0, datum, kennung)
    return (1, "", kennung)


def _fenster_fuer(art: str):
    """Fensterbreite in Tagen fuer eine Chat-Art (Regel, nicht Auslegung)."""
    return FENSTER_TAGE_GRUPPE if art == ART_GRUPPE else FENSTER_TAGE_EINZEL


def andocken(ereignisse: list, zuordnung: dict, nachrichten: dict,
             medien: dict, namen: dict, *, stand: str | None = None) -> dict:
    """Die Chat-Andockung bauen — **reine** Funktion ohne Datei/Netz.

    Kein Dateizugriff, kein Netzzugriff, keine Seiteneffekte; die uebergebenen
    Strukturen werden nicht veraendert. ``stand`` ist injizierbar (Tests bleiben
    reproduzierbar); ohne ``stand`` wird der aktuelle Zeitpunkt mit Zeitzone
    gesetzt. Die Zaehlregeln des Modulkopfes sind hier als Zusicherung
    verankert.
    """
    if not isinstance(ereignisse, list):
        raise ValueError("Die Ereignisse muessen eine Liste sein.")
    if stand is not None and (not isinstance(stand, str) or not stand.strip()):
        raise ValueError("Der Stand muss ein nicht-leerer Text sein.")
    if stand is None:
        stand = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    timestamps = nachrichten.get("timestamps") or []
    zeilen = nachrichten.get("zeilen") or []
    chat_subject = namen.get("chat_subject") or {}
    jid_user = namen.get("jid_user") or {}

    knoten_liste = []
    for ereignis in sorted(ereignisse, key=_sortierschluessel):
        if not isinstance(ereignis, dict):
            continue
        anlass_id = _text(ereignis.get("anlass_id"))
        kennung = _text(ereignis.get("kennung")) or ("E-" + anlass_id)
        tag0 = _datum_lesen(ereignis.get("datum"))

        if tag0 is None:
            knoten_liste.append({
                "anlass_id": anlass_id,
                "art": ANDOCKUNG_ART,
                "chats": [],
                "chats_anzahl": 0,
                "datum": None,
                "fenster": None,
                "kennung": kennung,
                "kontakte_gesamt": 0,
                "nachrichten_gesamt": 0,
                "quellen": _quellen(),
                "stand": stand,
            })
            continue

        tag_start = _tag_ms(tag0)
        von_ms = tag_start - TAG_MS                 # ±1 Tag: Vortag 00:00
        tag_ende = tag_start + TAG_MS               # Ereignistag + 1 Tag 00:00
        bis_ms = tag_start + 2 * TAG_MS             # datum+2 Tage 00:00

        # Aeusseres Fenster [von, bis) einmal schneiden; je Chat dann die
        # art-eigene (engere) Grenze anwenden.
        i0 = bisect.bisect_left(timestamps, von_ms)
        i1 = bisect.bisect_left(timestamps, bis_ms)

        chatschalen: dict = {}
        for idx in range(i0, i1):
            ts, chat_row_id, from_me, sender, msg_id = zeilen[idx]
            eintrag = zuordnung.get(chat_row_id)
            art = eintrag["art"] if eintrag else ART_UNBEKANNT
            if art == ART_GRUPPE:
                grenze_von, grenze_bis = tag_start, tag_ende   # derselbe Tag
                breite = FENSTER_TAGE_GRUPPE
            else:
                grenze_von, grenze_bis = von_ms, bis_ms        # ±1 Tag
                breite = FENSTER_TAGE_EINZEL
            if ts < grenze_von or ts >= grenze_bis:
                continue

            schale = chatschalen.get(chat_row_id)
            if schale is None:
                schale = {
                    "art": art,
                    "fenster_von": grenze_von,
                    "fenster_bis": grenze_bis,
                    "fenster_tage": breite,
                    "nachrichten": 0,
                    "von_mir": 0,
                    "von_anderen": 0,
                    "erste": None,
                    "letzte": None,
                    "kennungen": [],
                    "kontakte": {},
                }
                chatschalen[chat_row_id] = schale

            schale["nachrichten"] += 1
            if msg_id is not None:
                schale["kennungen"].append(int(msg_id))
            if schale["erste"] is None or ts < schale["erste"]:
                schale["erste"] = ts
            if schale["letzte"] is None or ts > schale["letzte"]:
                schale["letzte"] = ts

            if from_me == 1:
                schale["von_mir"] += 1
                continue
            schale["von_anderen"] += 1
            if art == ART_NEWSLETTER or sender is None:
                # Newsletter traegt keinen Kontakt; ein Absender ohne Bezug
                # zaehlt mit, hat aber keinen Namen.
                continue
            if art == ART_GRUPPE and eintrag is not None:
                name, maske = _gruppen_ident(
                    eintrag.get("teilnehmer") or [], jid_user.get(sender))
            elif eintrag is not None:
                name, maske = _einzel_ident(eintrag)
            else:
                # Chat fehlt in der Zuordnung: kein Name, keine Maske — nur
                # die Zaehlung bleibt (kein geratener Kontakt).
                name, maske = PLATZHALTER, None
            schluessel = (name, maske)
            schale["kontakte"][schluessel] = \
                schale["kontakte"].get(schluessel, 0) + 1

        chats = []
        for chat_row_id, schale in chatschalen.items():
            alle = sorted(schale["kennungen"])
            gekuerzt = len(alle) > MAX_KENNUNGEN
            beteiligte = [
                {"name": name, "nummer_maske": maske, "nachrichten": anzahl}
                for (name, maske), anzahl in schale["kontakte"].items()
            ]
            beteiligte.sort(key=lambda b: (-b["nachrichten"], b["name"]))
            medien_anzahl = _zaehle_medien(
                medien.get(chat_row_id, []),
                schale["fenster_von"], schale["fenster_bis"])
            chats.append({
                "art": schale["art"],
                "beteiligte": beteiligte,
                "chat_name": _chat_name(chat_row_id, schale["art"],
                                        zuordnung.get(chat_row_id), chat_subject),
                "chat_row_id": chat_row_id,
                "erste": _iso(schale["erste"]) if schale["erste"] is not None
                else None,
                "fenster_tage": schale["fenster_tage"],
                "gekuerzt": gekuerzt,
                "letzte": _iso(schale["letzte"]) if schale["letzte"] is not None
                else None,
                "medien": medien_anzahl,
                "nachrichten": schale["nachrichten"],
                "nachrichten_kennungen": alle[:MAX_KENNUNGEN],
                "von_anderen": schale["von_anderen"],
                "von_mir": schale["von_mir"],
            })
        chats.sort(key=lambda c: (-c["nachrichten"], c["chat_row_id"]))

        nachrichten_gesamt = sum(chat["nachrichten"] for chat in chats)
        kontakte = {b["name"] for chat in chats for b in chat["beteiligte"]
                    if b["name"] and b["name"] != PLATZHALTER}

        knoten_liste.append({
            "anlass_id": anlass_id,
            "art": ANDOCKUNG_ART,
            "chats": chats,
            "chats_anzahl": len(chats),
            "datum": tag0.isoformat(),
            "fenster": {
                "von": _iso(von_ms),
                "bis": _iso(bis_ms),
                "tage": FENSTER_TAGE_EINZEL,
            },
            "kennung": kennung,
            "kontakte_gesamt": len(kontakte),
            "nachrichten_gesamt": nachrichten_gesamt,
            "quellen": _quellen(),
            "stand": stand,
        })

    # Zusicherungen: die Zaehlregeln des Modulkopfes halten immer.
    for knoten in knoten_liste:
        assert knoten["chats_anzahl"] == len(knoten["chats"]), \
            "chats_anzahl != len(chats)"
        assert knoten["nachrichten_gesamt"] == sum(
            chat["nachrichten"] for chat in knoten["chats"]), \
            "nachrichten_gesamt != Summe der Chats"
        for chat in knoten["chats"]:
            assert chat["von_mir"] + chat["von_anderen"] == chat["nachrichten"], \
                "von_mir + von_anderen != nachrichten"

    zahlen = {
        "ereignisse": len(knoten_liste),
        "mit_nachrichten": sum(1 for knoten in knoten_liste
                               if knoten["nachrichten_gesamt"] > 0),
        "ohne_datum": sum(1 for knoten in knoten_liste
                          if knoten["datum"] is None),
        "nachrichten_gesamt": sum(knoten["nachrichten_gesamt"]
                                  for knoten in knoten_liste),
        "chats_gesamt": sum(knoten["chats_anzahl"] for knoten in knoten_liste),
        "kontakte_gesamt": sum(knoten["kontakte_gesamt"] for knoten in knoten_liste),
        "max_nachrichten": max((knoten["nachrichten_gesamt"]
                                for knoten in knoten_liste), default=0),
    }

    return {
        "art": ANDOCKUNG_ART,
        "stand": stand,
        "zahlen": zahlen,
        "ereignisse": knoten_liste,
    }


def _quellen() -> dict:
    """Der ``quellen``-Block (Herkunft der Felder) — eine frische Kopie."""
    return {
        "datum": QUELLE_DATUM,
        "fenster": QUELLE_FENSTER,
        "medien": QUELLE_MEDIEN,
        "nachrichten": QUELLE_NACHRICHTEN,
        "namen": QUELLE_NAMEN,
    }


def _zaehle_medien(zeitliste: list, von_ms: int, bis_ms: int) -> int:
    """Medien eines Chats im Fenster ``[von, bis)`` zaehlen (per ``bisect``)."""
    if not zeitliste:
        return 0
    links = bisect.bisect_left(zeitliste, von_ms)
    rechts = bisect.bisect_left(zeitliste, bis_ms)
    return rechts - links


# ── 4. Eine Knotenzeile (reine Funktion) ──────────────────────────────────

def knoten_zeile(knoten: dict) -> str:
    """Einen Knoten als eine JSONL-Zeile — **rein**, kein Dateizugriff.

    Kodierung ``ensure_ascii=True`` und ``sort_keys=True`` (ASCII, kein Umlaut):
    dieselbe Eingabe ergibt immer dieselbe Zeile. Ein zweiter Lauf mit
    **demselben** ``stand`` ist byte-gleich; ohne ``stand`` unterscheiden sich
    zwei Laeufe ausschliesslich im Feld ``stand``.
    """
    if not isinstance(knoten, dict):
        raise ValueError("Ein Knoten muss ein Woerterbuch sein.")
    return json.dumps(knoten, ensure_ascii=True, sort_keys=True)


# ── 5. Schreiben: atomar als JSONL, nur ausserhalb des Repos ──────────────

def _pruefe_ziel_ausserhalb_repo(pfad: str) -> str:
    """Sicherstellen, dass die Zieldatei AUSSERHALB des Repos liegt.

    Geprueft wird der absolut aufgeloeste Pfad; Gross-/Kleinschreibung und
    Schraeg-/Rueckwaertsstriche spielen keine Rolle (``abspath`` + ``normcase``
    + ``commonpath``). Liegt das Ziel im Repo, gibt es eine deutsche
    ``ValueError``-Meldung — geschrieben wird dann nichts. Sonst kommt der
    Pfad zurueck.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Zielpfad fuer die Chat-Andockung angegeben.")
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                        # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        raise ValueError(
            f"Zieldatei liegt IM Repo und ist nicht erlaubt: {pfad}\n"
            f"Die Chat-Andockung gehoert ausserhalb des Repos (Standard: "
            f"{STANDARD_AUSGABE}); es wird NICHTS geschrieben.")
    return pfad


def andockung_schreiben(pfad: str, daten: dict) -> str:
    """Die Chat-Andockung als JSONL schreiben — atomar, nur ausserhalb des Repos.

    Erst vollstaendig in ``<ziel>.tmp`` im **Zielordner** schreiben, dann per
    ``os.replace`` ersetzen: es entsteht nie eine halbe Datei. Scheitert das
    Schreiben, wird ausschliesslich die eigene temp-Datei wieder entfernt (die
    einzige Loeschung in diesem Modul) — eine vorhandene alte Zieldatei bleibt
    unangetastet. Ein Ziel im Repo ergibt eine deutsche ``ValueError``-Meldung.

    Rueckgabe: der geschriebene Pfad.
    """
    ziel = _pruefe_ziel_ausserhalb_repo(pfad)
    if not isinstance(daten, dict):
        raise ValueError("Keine Chat-Andockung zum Schreiben uebergeben "
                         "(erwartet wird ein Woerterbuch).")
    knoten = daten.get("ereignisse")
    if not isinstance(knoten, list):
        raise ValueError("Zum Schreiben fehlt die Knotenliste 'ereignisse'.")
    ordner = os.path.dirname(os.path.abspath(ziel))
    os.makedirs(ordner, exist_ok=True)
    temp_pfad = ziel + ".tmp"
    try:
        with open(temp_pfad, "w", encoding="utf-8") as datei:
            for eintrag in knoten:
                datei.write(knoten_zeile(eintrag))
                datei.write("\n")
        os.replace(temp_pfad, ziel)
    except Exception:
        if os.path.exists(temp_pfad):
            os.remove(temp_pfad)              # nur die eigene temp-Datei
        raise
    return ziel


# ── 6. Der Bericht als Klartext (deutsch) ─────────────────────────────────

def zahlen_text(daten: dict) -> str:
    """Die Zahlen des Laufs als mehrzeiliger deutscher Klartext.

    Enthaelt Stand und **alle** Zaehler (Ereignisse, mit Nachrichten, ohne
    Datum, Nachrichten gesamt, Chats gesamt, Kontakte gesamt, Maximum je
    Ereignis). Fehlende Felder ergeben ``0`` statt eines Absturzes. Es stehen
    hier **keine** Namen, Nummern oder Nachrichteninhalte.
    """
    d: dict = daten if isinstance(daten, dict) else {}
    roh_zahlen = d.get("zahlen")
    zahlen: dict = roh_zahlen if isinstance(roh_zahlen, dict) else {}

    def wert(name: str) -> int:
        zahl = _als_int(zahlen.get(name))
        return zahl if zahl is not None else 0

    zeilen = [
        f"Chat-Andockung N27 Schritt 2 - Stand "
        f"{_text(d.get('stand')) or 'unbekannt'}",
        f"Ereignisse: {_zahl(wert('ereignisse'))}   "
        f"mit Nachrichten: {_zahl(wert('mit_nachrichten'))}   "
        f"ohne Datum: {_zahl(wert('ohne_datum'))}",
        f"Nachrichten gesamt: {_zahl(wert('nachrichten_gesamt'))}   "
        f"Chats gesamt: {_zahl(wert('chats_gesamt'))}   "
        f"Kontakte gesamt: {_zahl(wert('kontakte_gesamt'))}",
        f"Maximum Nachrichten je Ereignis: {_zahl(wert('max_nachrichten'))}",
        "ohne Nachrichtentext, ohne Klartext-Nummern, nur Kennungen und Zahlen",
    ]
    return "\n".join(zeilen)


# ── 7. Kommandozeile ─────────────────────────────────────────────────────

def haupt(argv=None) -> int:
    """Kommandozeile: lesen, Zahlen zeigen, nur mit ``--schreiben`` ablegen.

    ``--ereignisse``/``--db``/``--zuordnung``/``--ausgabe`` haben die
    beauftragten Standardpfade; ``--trocken`` ist der **Standard**,
    ``--schreiben`` legt atomar ab; ``--limit N`` zeigt nur die ersten N Knoten
    auf der Konsole (Standard 5). Ohne ``--schreiben`` ist es ein reiner
    Trockenlauf: dieselben Zahlen, keine Datei. Fehlende Eingaben oder ein Ziel
    im Repo ergeben eine deutsche Meldung auf ``stderr`` und Exit 2.
    """
    zerleger = argparse.ArgumentParser(
        description="Chat-Andockung N27 Schritt 2: liest NUR die lokalen "
                    "Ereignis-Knoten, die msgstore.db (nur lesend) und die "
                    "Zuordnung und dockt je Ereignis die Chats im Zeitfenster "
                    "an — nur Kennungen, Zaehlungen und Masken, kein Text.")
    zerleger.add_argument("--ereignisse", dest="ereignisse",
                          default=STANDARD_EREIGNISSE,
                          help="Ereignis-Knoten aus N27a (JSONL, ausserhalb des Repos)")
    zerleger.add_argument("--db", dest="db", default=STANDARD_DB,
                          help="msgstore.db (wird nur lesend geoeffnet)")
    zerleger.add_argument("--zuordnung", dest="zuordnung",
                          default=STANDARD_ZUORDNUNG,
                          help="WhatsApp-Zuordnung (JSON, ausserhalb des Repos)")
    zerleger.add_argument("--ausgabe", dest="ausgabe", default=STANDARD_AUSGABE,
                          help="Zieldatei der Andockung (JSONL, ausserhalb des Repos)")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur Zahlen zeigen, nichts schreiben (Standard)")
    zerleger.add_argument("--schreiben", action="store_true",
                          help="die Datei wirklich schreiben (atomar, nur "
                               "ausserhalb des Repos); --trocken hat Vorrang")
    zerleger.add_argument("--limit", dest="limit", type=int, default=5,
                          help="nur die ersten N Knoten auf der Konsole zeigen "
                               "(Standard 5)")
    args = zerleger.parse_args(argv)

    schreiben = bool(args.schreiben) and not bool(args.trocken)
    limit = args.limit

    con = None
    try:
        if limit < 0:
            raise ValueError("Das Limit muss eine Zahl >= 0 sein.")
        _pruefe_ziel_ausserhalb_repo(args.ausgabe)
        ereignisse = ereignisse_laden(args.ereignisse)
        zuordnung = zuordnung_laden(args.zuordnung)
        con = db_oeffnen(args.db)
        nachrichten = nachrichten_lesen(con)
        medien = medien_lesen(con)
        namen = namen_lesen(con)
        daten = andocken(ereignisse, zuordnung, nachrichten, medien, namen)
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2
    finally:
        if con is not None:
            con.close()

    print("Chat-Andockung N27 Schritt 2 - "
          + ("SCHREIBEN" if schreiben else "TROCKENLAUF (es wird nichts geschrieben)"))
    print(f"Ereignisse: {args.ereignisse}")
    print(f"Datenbank (nur lesend): {args.db}")
    print(f"Zuordnung: {args.zuordnung}")
    print(zahlen_text(daten))

    knoten = daten["ereignisse"]
    for eintrag in knoten[:limit]:
        print(knoten_zeile(eintrag))
    if limit < len(knoten):
        print(f"... und {_zahl(len(knoten) - limit)} weitere Knoten")

    if not schreiben:
        print(f"Trockenlauf: {args.ausgabe} wurde NICHT geschrieben.")
        return 0

    try:
        ziel = andockung_schreiben(args.ausgabe, daten)
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2
    print(f"Chat-Andockung geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(haupt())
