#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Importiert WhatsApp-Nachrichten aus der entschluesselten Sicherung ins Archiv.

Quelle ist die bereits entschluesselte ``msgstore.db`` (nur LESEND geoeffnet,
``file:...?mode=ro``). Ziel ist ``normalized/messages.jsonl`` im Archivordner -
es wird **angehaengt**, nie neu gebaut, nie neu sortiert: die Zeilennummer in
dieser Datei ist der Rueckweg vom Index zur Originalnachricht.

Was importiert wird
===================

Eine Zeile je Nachricht mit darstellbarem Inhalt:

* **Text** - alles mit ``text_data``.
* **Anhang** - Nachrichten ohne Text mit Medienbezug; als Platzhalter
  ``<Dateiname> (Datei angehaengt)`` - dieselbe Form, die der WhatsApp-Export
  benutzt und die der Adapter ``src/adapters/whatsapp.py`` bereits kennt.
* **geloescht** - geloeschte Nachrichten bekommen den Wortlaut aus dem Export
  (``Diese Nachricht wurde geloescht.`` bzw. ``Du hast diese Nachricht
  geloescht.``).
* **Anruf** - ``Verpasster Sprachanruf`` / ``Verpasster Videoanruf``
  (Dauer 0) bzw. ``Sprachanruf`` / ``Videoanruf``.
* **Standort** - ``Standort: <url>``, wenn eine URL vorliegt.

Nicht importiert werden Nachrichten ohne Text und ohne jeden dieser Bezuege:
Systemereignisse (Gruppenbeitritte, Einstellungen), Kontaktkarten, Umfragen
und aehnliches. Sie werden im Bericht gezaehlt - nichts wird still verschluckt.

Doppelte vermeiden
==================

Die beiden bereits per Chatexport importierten Gespraeche stecken auch in der
Datenbank. Der Abgleich laeuft ueber Inhalt statt Namen: je bestehendem
WhatsApp-Gespraech wird der Datenbank-Chat mit der groessten Uebereinstimmung
aus ``(Text, Minute)`` gesucht. Fuer verknuepfte Chats (und, bei einem zweiten
Lauf, fuer alle bereits importierten) werden Nachrichten uebersprungen, die in
dieser Form schon im Archiv stehen. Der Lauf ist damit **wiederholbar**: ein
zweiter Aufruf findet 0 Neues.

Rollen
======

``user`` = eigene Nachrichten (``from_me``), ``kontakt`` = fremde,
``system`` = Systemnachrichten mit Text. Fremde Beitraege bekommen bewusst
nicht ``user`` - der Filter ``src/filter.py`` kann so spaeter entscheiden, was
den Rechner verlassen darf.

Geheimnis-Regel
===============

stdout/stderr nennen **nur Zahlen** - keine Namen, Nummern, Chatnamen oder
Nachrichteninhalte. Der Bericht zaehlt, er zitiert nicht.

Aufruf
======

    cd backend
    .venv/Scripts/python -m scripts.whatsapp_db_import --trocken
    .venv/Scripts/python -m scripts.whatsapp_db_import --schreiben

Ohne ``--schreiben`` aendert der Lauf nichts (Trockenlauf).
"""
from __future__ import annotations

import argparse
import collections
import datetime
import io
import json
import os
import re
import shutil
import sqlite3
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

# ── Standardpfade (persoenliche Daten, bewusst AUSSERHALB des Repos) ─────────

STANDARD_DB = (
    r"C:\Users\sebas\Desktop\workspace agentic engineering\Chats von GPT, GEMINI, Claude"
    r"\whatsapp_uebertragung\backup-decrypted\Databases\msgstore.db"
)
STANDARD_ZIEL = (
    r"C:\Users\sebas\Desktop\workspace agentic engineering\Chats von GPT, GEMINI, Claude"
    r"\normalized\messages.jsonl"
)
STANDARD_ZUORDNUNG = r"C:\Users\sebas\foto_sortierung\whatsapp_zuordnung.json"

QUELLE = "whatsapp"

# Wortlaut wie im WhatsApp-Export bzw. in der App (nicht erfunden: die
# Formate stehen genau so in den bereits importierten Exportzeilen).
ZITAT_ANHANG = " (Datei angehängt)"
TEXT_GELOESCHT_FREMD = "Diese Nachricht wurde gelöscht."
TEXT_GELOESCHT_EIGEN = "Du hast diese Nachricht gelöscht."

# Verknuepfung bestehender Gespraeche: mindestens so viele (Text, Minute)-
# Treffer und mindestens dieser Anteil der bestehenden Zeilen.
MIN_TREFFER = 3
MIN_ANTEIL = 0.15

# Kostenschaetzung fuer den Index (archiv_index_bauen: 3,6 Zeichen/Token).
ZEICHEN_JE_TOKEN = 3.6
PREIS_JE_MIO_TOKEN = 0.02

UNSICHTBAR = re.compile("[\u200e\u200f\u202a\u202b\u202c\u202d\u202e\ufeff]")

TITEL_EINZEL = "WhatsApp mit {name}"
TITEL_GRUPPE = "WhatsApp-Gruppe: {name}"
TITEL_GRUPPE_OHNE = "WhatsApp-Gruppe"
TITEL_KANAL = "WhatsApp-Kanal: {name}"
TITEL_SONSTIGES = "WhatsApp"


def _normtext(text: Optional[str]) -> str:
    """Unsichtbare Steuerzeichen entfernen, aussen trimmen (wie der Adapter)."""
    return UNSICHTBAR.sub("", text or "").strip()


def zu_iso_ms(ms: Optional[int]) -> Optional[str]:
    """Epoch-Millisekunden nach ISO-8601 in UTC."""
    if ms is None:
        return None
    try:
        return datetime.datetime.fromtimestamp(
            ms / 1000, tz=datetime.timezone.utc
        ).isoformat()
    except (OSError, OverflowError, ValueError, TypeError):
        return None


def _minute_aus_iso(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp()) // 60


# ── Quelle lesen (nur lesend) ────────────────────────────────────────────────

def oeffne_ro(pfad: str) -> sqlite3.Connection:
    """Oeffnet die Datenbank strikt lesend."""
    if not os.path.isfile(pfad):
        raise FileNotFoundError(f"Datenbank nicht gefunden: {pfad}")
    con = sqlite3.connect(f"file:{pfad.replace(chr(92), '/')}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def lade_chats(con: sqlite3.Connection) -> Dict[int, Dict[str, Any]]:
    """Alle Chats: Art (server), Gruppenname (subject), Kanalname (newsletter)."""
    con.row_factory = sqlite3.Row
    chats: Dict[int, Dict[str, Any]] = {}
    for z in con.execute(
        "SELECT c._id AS id, j.server AS server, c.subject AS subject, "
        "       n.name AS kanal "
        "FROM chat c JOIN jid j ON j._id = c.jid_row_id "
        "LEFT JOIN newsletter n ON n.chat_row_id = c._id"
    ):
        chats[z["id"]] = {
            "server": z["server"] or "",
            "subject": (z["subject"] or "").strip() or None,
            "kanal": (z["kanal"] or "").strip() or None,
        }
    return chats


def lade_zusatz(con: sqlite3.Connection) -> Dict[str, Any]:
    """Medien, geloeschte, Anrufe, Standorte, Systemzeilen - je als Nachschlagewerk."""
    con.row_factory = sqlite3.Row
    medien: Dict[int, str] = {}
    for z in con.execute(
        "SELECT message_row_id AS mid, file_path AS pfad, media_name AS name "
        "FROM message_media"
    ):
        pfad = (z["pfad"] or "").replace("\\", "/").rstrip("/")
        dateiname = pfad.rsplit("/", 1)[-1] if pfad else ""
        medien[z["mid"]] = dateiname or (z["name"] or "").strip()

    geloescht: Set[int] = {
        z["message_row_id"] for z in con.execute("SELECT message_row_id FROM message_revoked")
    }
    system: Set[int] = {
        z["message_row_id"] for z in con.execute("SELECT message_row_id FROM message_system")
    }
    anrufe: Dict[int, Tuple[bool, int]] = {}
    for z in con.execute(
        "SELECT mc.message_row_id AS mid, cl.video_call AS video, cl.duration AS dauer "
        "FROM message_call_log mc JOIN call_log cl ON cl._id = mc.call_log_row_id"
    ):
        anrufe[z["mid"]] = (bool(z["video"]), int(z["dauer"] or 0))
    standorte: Dict[int, str] = {}
    for z in con.execute(
        "SELECT message_row_id AS mid, url FROM message_location "
        "WHERE url IS NOT NULL AND url != ''"
    ):
        standorte[z["mid"]] = z["url"]
    return {"medien": medien, "geloescht": geloescht, "system": system,
            "anrufe": anrufe, "standorte": standorte}


def lade_zuordnung(pfad: Optional[str]) -> Dict[int, Dict[str, Any]]:
    """Die private Zuordnung Chat <-> Telefonbuch (falls vorhanden).

    Fehlt die Datei, arbeitet der Import weiter - Chats ohne Namen bekommen
    dann die Ersatzkennung ``unbekannt-<chat_row_id>``.
    """
    if not pfad or not os.path.isfile(pfad):
        return {}
    with io.open(pfad, encoding="utf-8") as f:
        daten = json.load(f)
    karte: Dict[int, Dict[str, Any]] = {}
    for eintrag in daten.get("chats") or []:
        try:
            karte[int(eintrag["chat_row_id"])] = eintrag
        except (KeyError, TypeError, ValueError):
            continue
    return karte


def lade_db_nachrichten(con: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    return con.execute(
        "SELECT _id AS mid, chat_row_id AS chat, from_me AS von_mir, "
        "       timestamp AS ts, text_data AS text "
        "FROM message ORDER BY _id"
    ).fetchall()


# ── Archiv lesen (fuer Abgleich und Wiederholbarkeit) ────────────────────────

def lade_bestehende(ziel: str) -> Dict[str, Any]:
    """Bestehende WhatsApp-Zeilen: je Gespraech die (Text, Minute)-Schluessel.

    Ausserdem: Titel je Gespraech (fuer verknuepfte Gespraeche) und die Menge
    aller Gespraechskennungen (fuer stabile Ersatzkennungen).
    """
    pro_gespraech: Dict[str, Set[Tuple[str, int]]] = collections.defaultdict(set)
    zeilen_je_gespraech: collections.Counter = collections.Counter()
    titel: Dict[str, str] = {}
    alle_kennungen: Set[str] = set()
    zeilen_gesamt = 0
    with io.open(ziel, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile:
                continue
            zeilen_gesamt += 1
            rec = json.loads(zeile)
            kennung = rec.get("conversation_id") or ""
            alle_kennungen.add(kennung)
            if rec.get("source") != QUELLE:
                continue
            zeilen_je_gespraech[kennung] += 1
            minute = _minute_aus_iso(rec.get("timestamp"))
            if minute is None:
                continue
            schluessel = (_normtext(rec.get("text")), minute)
            pro_gespraech[kennung].add(schluessel)
            if kennung not in titel and rec.get("title"):
                titel[kennung] = rec["title"]
    return {"pro_gespraech": pro_gespraech, "zeilen_je_gespraech": zeilen_je_gespraech,
            "titel": titel, "alle_kennungen": alle_kennungen, "zeilen_gesamt": zeilen_gesamt}


def finde_verknuepfungen(bestehende: Dict[str, Any],
                         db_schluessel: Dict[Tuple[str, int], List[int]]) -> Dict[str, Any]:
    """Je bestehendem WhatsApp-Gespraech den passenden Datenbank-Chat finden.

    Gemessen wird die Schnittmenge der (Text, Minute)-Schluessel. Ein Gespraech
    gilt als verknuepft, wenn der beste Chat mindestens ``MIN_TREFFER`` Treffer
    und mindestens ``MIN_ANTEIL`` der bestehenden Zeilen deckt. Es wird nichts
    geraten: ohne Schwellwert bliebe die Zuordnung lieber offen.
    """
    verknuepft: Dict[str, int] = {}
    bericht: List[Dict[str, Any]] = []
    for kennung, schluessel in bestehende["pro_gespraech"].items():
        zaehler: collections.Counter = collections.Counter()
        for s in schluessel:
            for chat in db_schluessel.get(s, ()):
                zaehler[chat] += 1
        if not zaehler:
            continue
        (bester, treffer), *rest = zaehler.most_common(2)
        zweiter = rest[0][1] if rest else 0
        grenze = max(MIN_TREFFER, int(len(schluessel) * MIN_ANTEIL))
        if treffer >= grenze and treffer > zweiter:
            verknuepft[kennung] = bester
            bericht.append({"kennung": kennung, "chat": bester, "treffer": treffer,
                            "zweiter": zweiter,
                            "zeilen": bestehende["zeilen_je_gespraech"].get(kennung, len(schluessel))})
    return {"verknuepft": verknuepft, "bericht": bericht}


# ── Einordnung und Text je Nachricht ─────────────────────────────────────────

def klassifiziere(zeile: sqlite3.Row, zusatz: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Kategorie und Text einer Datenbankzeile (ohne Rollenlogik)."""
    mid = zeile["mid"]
    text = _normtext(zeile["text"])
    if text:
        return ("system_text" if mid in zusatz["system"] else "text"), text
    if mid in zusatz["medien"]:
        dateiname = zusatz["medien"][mid]
        return "anhang", (dateiname + ZITAT_ANHANG) if dateiname else ZITAT_ANHANG.strip()
    if mid in zusatz["geloescht"]:
        return "geloescht", (
            TEXT_GELOESCHT_EIGEN if zeile["von_mir"] else TEXT_GELOESCHT_FREMD
        )
    if mid in zusatz["anrufe"]:
        video, dauer = zusatz["anrufe"][mid]
        art = "Videoanruf" if video else "Sprachanruf"
        return "anruf", (art if dauer > 0 else f"Verpasster {art}")
    if mid in zusatz["standorte"]:
        return "standort", f"Standort: {zusatz['standorte'][mid]}"
    return ("uebersprungen_system" if mid in zusatz["system"] else "uebersprungen_sonstiges"), None


def rolle(zeile: sqlite3.Row, zusatz: Dict[str, Any]) -> str:
    if zeile["mid"] in zusatz["system"]:
        return "system"
    return "user" if zeile["von_mir"] else "kontakt"


# ── Kennungen und Titel ──────────────────────────────────────────────────────

def _name_aus_zuordnung(eintrag: Optional[Dict[str, Any]]) -> Optional[str]:
    if not eintrag:
        return None
    namen = [
        n.strip() for n in (eintrag.get("telefonbuch_namen") or [])
        if n and n.strip() and n.strip().lower() != "unbekannt"
    ]
    if namen:
        return " / ".join(namen)
    wa = (eintrag.get("whatsapp_name") or "").strip()
    if wa and wa.lower() != "unbekannt":
        return wa
    return None


def _maske_aus_zuordnung(eintrag: Optional[Dict[str, Any]]) -> Optional[str]:
    maske = ((eintrag or {}).get("nummer_maske") or "").strip()
    return maske or None


def basis_kennung(chat_id: int, chat: Dict[str, Any],
                  eintrag: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    """(Grundkennung, Titel) eines Chats - ohne Kollisionsbehandlung.

    Namen kommen aus der privaten Zuordnung (Telefonbuch, sonst
    WhatsApp-Anzeigename). Fehlt beides, steht statt einer vollen Nummer nur
    die Maske (``***1234``) in der Kennung - dieselbe Regel wie in
    ``zuordnung_bauen.py``.
    """
    server = chat.get("server") or ""
    if server == "g.us":
        name = chat.get("subject")
        if name:
            return f"whatsapp-gruppe-{name}", TITEL_GRUPPE.format(name=name)
        return f"whatsapp-gruppe-unbekannt-{chat_id}", TITEL_GRUPPE_OHNE
    if server == "newsletter":
        name = chat.get("kanal")
        if name:
            return f"whatsapp-kanal-{name}", TITEL_KANAL.format(name=name)
        return f"whatsapp-kanal-unbekannt-{chat_id}", TITEL_SONSTIGES

    name = _name_aus_zuordnung(eintrag)
    if name:
        return f"whatsapp-{name}", TITEL_EINZEL.format(name=name)
    maske = _maske_aus_zuordnung(eintrag)
    if maske:
        return f"whatsapp-unbekannt-{maske}", TITEL_EINZEL.format(name="unbekannt")
    if server in ("broadcast", "bot", "status_me", "temp"):
        return f"whatsapp-sonstiges-{chat_id}", TITEL_SONSTIGES
    return f"whatsapp-unbekannt-{chat_id}", TITEL_EINZEL.format(name="unbekannt")


def kennungen_bauen(chats: Dict[int, Dict[str, Any]], zuordnung: Dict[int, Dict[str, Any]],
                    belegt: Set[str]) -> Dict[int, Tuple[str, str]]:
    """Stabile Kennungen fuer alle Chats dieser Runde.

    Kollisionsaufloesung **nur innerhalb dieser Runde** (aufsteigend nach
    chat_row_id) und gegen die reservierten Kennungen (verknuepfte Gespraeche,
    bestehende Fremdquellen). So liefert ein wiederholter Lauf dieselben
    Kennungen, statt sich selbst auszuweichen.
    """
    ergebnis: Dict[int, Tuple[str, str]] = {}
    for chat_id in sorted(chats):
        base, titel = basis_kennung(chat_id, chats[chat_id], zuordnung.get(chat_id))
        kennung = base
        nummer = 2
        while kennung in belegt:
            kennung = f"{base}-{nummer}"
            nummer += 1
        belegt.add(kennung)
        ergebnis[chat_id] = (kennung, titel)
    return ergebnis


# ── Zusammenbau ──────────────────────────────────────────────────────────────

FELDER = ("conversation_id", "source", "timestamp", "role", "text", "title", "project")


def baue_zeilen(db: sqlite3.Connection, bestehende: Dict[str, Any],
                chats: Dict[int, Dict[str, Any]], zuordnung: Dict[int, Dict[str, Any]],
                zusatz: Dict[str, Any]) -> Dict[str, Any]:
    """Erzeugt die neuen Zeilen und den Zaehlbericht (keine Inhalte)."""
    nachrichten = [
        {"mid": z["mid"], "chat": z["chat"], "von_mir": z["von_mir"],
         "ts": z["ts"], "text": z["text"]}
        for z in lade_db_nachrichten(db)
    ]
    zahlen: Dict[str, Any] = collections.Counter()
    zahlen["nachrichten_gesamt"] = len(nachrichten)

    # Schluesselindex fuer den Verknuepfungsabgleich
    db_schluessel: Dict[Tuple[str, int], List[int]] = collections.defaultdict(list)
    for n in nachrichten:
        minute = int(n["ts"]) // 60000 if n["ts"] is not None else None
        if minute is not None:
            db_schluessel[(_normtext(n["text"]), minute)].append(n["chat"])

    verknuepfung = finde_verknuepfungen(bestehende, db_schluessel)

    # Kennungen: verknuepfte Gespraeche behalten ihre bestehende Kennung.
    belegt: Set[str] = {
        k for k in bestehende["alle_kennungen"]
        if not k.startswith("whatsapp-")
    }
    verknuepft_je_chat: Dict[int, str] = {}
    for kennung, chat_id in verknuepfung["verknuepft"].items():
        verknuepft_je_chat[chat_id] = kennung
        belegt.add(kennung)
    kennungen = kennungen_bauen(
        {cid: c for cid, c in chats.items() if cid not in verknuepft_je_chat},
        zuordnung, belegt,
    )
    for cid, kennung in verknuepft_je_chat.items():
        kennungen[cid] = (kennung, bestehende["titel"].get(kennung) or TITEL_EINZEL.format(name=""))

    # Nachrichten ohne Chat-Eintrag (verwaist) aussortieren
    mit_chat = [n for n in nachrichten if n["chat"] in chats]
    ohne_chat = [n for n in nachrichten if n["chat"] not in chats]
    zahlen["ohne_chat"] = len(ohne_chat)
    zahlen["ohne_chat_chats"] = len({n["chat"] for n in ohne_chat})
    zahlen["chats_mit_nachrichten"] = len({n["chat"] for n in mit_chat})

    neue: List[Dict[str, Any]] = []
    for n in mit_chat:
        kategorie, text = klassifiziere(n, zusatz)
        zahlen[kategorie] += 1
        if text is None:
            continue
        iso = zu_iso_ms(n["ts"])
        if iso is None:
            zahlen["ohne_zeit"] += 1
            continue
        kennung, titel = kennungen[n["chat"]]
        schluessel = (_normtext(text), int(n["ts"]) // 60000)
        if schluessel in bestehende["pro_gespraech"].get(kennung, ()):  # type: ignore[arg-type]
            zahlen["duplikat"] += 1
            continue
        neue.append({
            "conversation_id": kennung,
            "source": QUELLE,
            "timestamp": iso,
            "role": rolle(n, zusatz),
            "text": text,
            "title": titel,
            "project": None,
        })

    neue.sort(key=lambda r: (r["timestamp"], r["conversation_id"]))
    zeichen = sum(len(r["text"]) for r in neue)
    zahlen["neue_zeilen"] = len(neue)
    zahlen["neue_zeichen"] = zeichen
    zahlen["tokens_geschaetzt"] = int(zeichen / ZEICHEN_JE_TOKEN)
    zahlen["kosten_index_usd"] = round(zeichen / ZEICHEN_JE_TOKEN / 1e6 * PREIS_JE_MIO_TOKEN, 4)
    return {"zeilen": neue, "zahlen": zahlen, "verknuepfung": verknuepfung,
            "kennungen": kennungen}


# ── Schreiben (anhaengen, mit Sicherung) ─────────────────────────────────────

def schreibe_anhaengen(ziel: str, zeilen: Sequence[Dict[str, Any]],
                       bericht: Dict[str, Any], jetzt: Optional[str] = None) -> str:
    """Sichert die Datei und haengt die neuen Zeilen an (CRLF wie der Vorbestand)."""
    jetzt = jetzt or datetime.datetime.now().strftime("%Y%m%d-%H%M")
    stamm, endung = os.path.splitext(ziel)
    sicherung = f"{stamm}_vor_import_{jetzt}{endung}"
    if not os.path.exists(sicherung):
        shutil.copy2(ziel, sicherung)
    bericht["sicherung"] = sicherung

    vorher = os.path.getsize(ziel)
    with io.open(ziel, "ab") as f:
        for r in zeilen:
            f.write((json.dumps(r, ensure_ascii=False) + "\r\n").encode("utf-8"))
    bericht["datei_mb_vorher"] = round(vorher / 1e6, 1)
    bericht["datei_mb_nachher"] = round(os.path.getsize(ziel) / 1e6, 1)

    # Gegenprobe: Zeilen zaehlen (nicht schaetzen)
    neu_gezaehlt = 0
    gesamt = 0
    with io.open(ziel, encoding="utf-8") as f:
        for line in f:
            gesamt += 1
            if line.strip():
                neu_gezaehlt += 1
    bericht["zeilen_nachher"] = gesamt
    return sicherung


# ── Bericht ──────────────────────────────────────────────────────────────────

def _z(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def bericht_text(ergebnis: Dict[str, Any], bestehende: Dict[str, Any],
                 modus: str, chats: Dict[int, Dict[str, Any]]) -> str:
    z = ergebnis["zahlen"]
    v = ergebnis["verknuepfung"]
    kennungen = ergebnis["kennungen"]
    zeilen: List[str] = []
    zeilen.append(f"=== WhatsApp-Datenbank -> Archiv ({modus}) ===")
    zeilen.append(f"  Chats                     {_z(len(chats))}")
    zeilen.append(f"  davon mit Nachrichten     {_z(z['chats_mit_nachrichten'])}")
    zeilen.append(f"  Nachrichten gesamt        {_z(z['nachrichten_gesamt'])}")
    zeilen.append(f"  ohne Chat-Eintrag         {_z(z['ohne_chat'])} in {_z(z['ohne_chat_chats'])} "
                  f"verwaisten chat_row_ids  (nicht importiert)")
    zeilen.append("")
    zeilen.append("Kategorien:")
    for name, schluessel in (("Text", "text"), ("System mit Text", "system_text"),
                             ("Anhang (Platzhalter)", "anhang"),
                             ("geloescht", "geloescht"), ("Anruf", "anruf"),
                             ("Standort", "standort")):
        zeilen.append(f"  {name:<22} {_z(z[schluessel])}")
    zeilen.append(f"  {'System ohne Text':<22} {_z(z['uebersprungen_system'])}  (uebersprungen)")
    zeilen.append(f"  {'sonstiges ohne Text':<22} {_z(z['uebersprungen_sonstiges'])}  (uebersprungen)")
    zeilen.append("")
    zeilen.append("Abgleich mit dem Archiv:")
    zeilen.append(f"  Archivdatei               {_z(bestehende['zeilen_gesamt'])} Zeilen gesamt")
    zeilen.append(f"  bestehende WhatsApp-Zeilen {_z(sum(len(s) for s in bestehende['pro_gespraech'].values()))}"
                  f" in {_z(len(bestehende['pro_gespraech']))} Gespraechen")
    for b in sorted(v["bericht"], key=lambda b: -b["treffer"]):
        zeilen.append(f"  - chat_row_id {b['chat']}: {_z(b['treffer'])} von {_z(b['zeilen'])} Zeilen "
                      f"(zweitbester {_z(b['zweiter'])})")
    zeilen.append(f"  Duplikate uebersprungen   {_z(z['duplikat'])}")
    zeilen.append("")
    zeilen.append("Neue Zeilen:")
    zeilen.append(f"  Zeilen                    {_z(z['neue_zeilen'])}")
    zeilen.append(f"  Zeichen                   {_z(z['neue_zeichen'])}")
    zeilen.append(f"  Tokens (Schaetzung)       {_z(z['tokens_geschaetzt'])}")
    zeilen.append(f"  Kosten Index (Schaetzung) {z['kosten_index_usd']:.2f} $ "
                  f"({PREIS_JE_MIO_TOKEN} $/1M Token, {ZEICHEN_JE_TOKEN} Zeichen/Token) "
                  f"- nur die neuen Zeilen; ein voller Indexbau rechnet den ganzen Bestand")
    if "sicherung" in z:
        zeilen.append("")
        zeilen.append(f"  Sicherung                 {os.path.basename(z['sicherung'])}")
        zeilen.append(f"  Datei                     {z['datei_mb_vorher']} MB -> {z['datei_mb_nachher']} MB, "
                      f"{_z(z['zeilen_nachher'])} Zeilen")
    return "\n".join(zeilen)


def main(argv: Optional[Sequence[str]] = None) -> int:
    wahl = argparse.ArgumentParser(
        description="Importiert WhatsApp-Nachrichten aus msgstore.db (nur lesend) "
                    "ins Archiv - anhaengend, mit Sicherung.",
    )
    wahl.add_argument("--db", default=STANDARD_DB)
    wahl.add_argument("--ziel", default=STANDARD_ZIEL)
    wahl.add_argument("--zuordnung", default=STANDARD_ZUORDNUNG)
    wahl.add_argument("--schreiben", action="store_true",
                      help="Zeilen wirklich anhaengen (sonst Trockenlauf)")
    wahl.add_argument("--trocken", action="store_true",
                      help="nur rechnen und berichten (Standard ohne --schreiben)")
    args = wahl.parse_args(argv)
    if args.trocken and args.schreiben:
        print("Bitte nur eines von --trocken und --schreiben angeben.")
        return 2

    if not os.path.isfile(args.ziel):
        print(f"Zieldatei nicht gefunden: {args.ziel}")
        return 2

    bestehende = lade_bestehende(args.ziel)
    try:
        con = oeffne_ro(args.db)
    except FileNotFoundError as e:
        print(str(e))
        return 2
    try:
        chats = lade_chats(con)
        zuordnung = lade_zuordnung(args.zuordnung)
        zusatz = lade_zusatz(con)
        ergebnis = baue_zeilen(con, bestehende, chats, zuordnung, zusatz)
    finally:
        con.close()

    print(bericht_text(ergebnis, bestehende, "Trockenlauf", chats))

    if not args.schreiben:
        print("\nTrockenlauf - nichts geschrieben. Mit --schreiben anhaengen.")
        return 0

    bericht: Dict[str, Any] = {k: v for k, v in ergebnis["zahlen"].items()}
    schreibe_anhaengen(args.ziel, ergebnis["zeilen"], bericht)
    print()
    print(f"Angehaengt: {_z(bericht['neue_zeilen'])} Zeilen, "
          f"Sicherung {os.path.basename(bericht['sicherung'])}, "
          f"Datei jetzt {_z(bericht['zeilen_nachher'])} Zeilen ({bericht['datei_mb_nachher']} MB).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
