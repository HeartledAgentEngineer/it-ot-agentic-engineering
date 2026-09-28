#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baut die private Zuordnung WhatsApp-Chat <-> Telefonbuch-Kontakt.

Bruecke ist die Telefonnummer: der Chat bzw. das Gruppenmitglied liefert eine
Nummer (``s.whatsapp.net`` direkt, LID ueber ``jid_map``), das Telefonbuch den
Namen. Zweite Namensquelle ist der selbst gewaehlte WhatsApp-Anzeigename
(``lid_display_name``).

Eingaben (beide NUR lesend):
  * msgstore.db - ueber ``file:...?mode=ro`` geoeffnet. Kein Schreiben, kein
    Entschluesseln, kein Download.
  * Telefonbuch vom Handy per ADB (``content query`` auf
    ``content://com.android.contacts/data/phones``) und die Termin-Zeilen
    (Geburtstage, mimetype ``vnd.android.cursor.item/contact_event``).
    Alternativ vorher gespeicherte Rohausgaben (``--telefonbuch-datei``,
    ``--events-datei``) - damit laeuft das Werkzeug auch ohne Handy.

Ausgabe: genau EINE JSON-Datei AUSSERHALB des Repos (``--ausgabe``,
Standard ``C:/Users/sebas/foto_sortierung/whatsapp_zuordnung.json``).
Der Inhalt ist privat: Telefonbuch-Namen, WhatsApp-Anzeigenamen und je Nummer
nur die **letzten 4 Ziffern** (Maske ``***1234``).

Geheimnis-Regel: stdout/stderr nennen NUR Zaehlungen - nie Namen, Nummern,
Chatnamen oder Nachrichteninhalte. Auch Fehlermeldungen bleiben ohne Daten.

Gruppen-Mitglieder: In diesem WhatsApp-Schema gibt es die Tabelle
``group_participant`` **nicht** (per ``PRAGMA table_info`` geprueft). Quelle 1
ist die moderne Tabelle ``group_participant_user`` (in aelteren Staenden
``group_participant``, beide Formen werden zur Laufzeit erkannt), Quelle 2 die
Text-Variante ``group_participants`` (gjid/jid). Ersatz- und Zusatzweg sind die
System-Nachrichten ``message_system_chat_participant`` und die Absender aus
``message`` (from_me=0). Je Mitglied wird die Quelle (``gruppe``/``verlauf``)
mitgeschrieben.

Offline pruefbar (reine Funktionen + DB-Zugriff auf uebergebene Verbindung):
    cd backend && .venv/Scripts/python -m pytest tests/test_whatsapp_zuordnung.py -q

Aufruf:
    python tools/whatsapp/zuordnung_bauen.py [--db PFAD] [--ausgabe PFAD]
        [--geraet SERIENNUMMER] [--telefonbuch-datei DATEI] [--events-datei DATEI]
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

# ── Standardpfade (persoenliche Daten, bewusst AUSSERHALB des Repos) ─────────

STANDARD_DB = (
    r"C:\Users\sebas\Desktop\workspace agentic engineering\Chats von GPT, GEMINI, Claude"
    r"\whatsapp_uebertragung\backup-decrypted\Databases\msgstore.db"
)
STANDARD_AUSGABE = r"C:\Users\sebas\foto_sortierung\whatsapp_zuordnung.json"

TELEFONBUCH_QUERY = (
    "content query --uri content://com.android.contacts/data/phones "
    "--projection display_name:data1"
)
EVENTS_QUERY = (
    "content query --uri content://com.android.contacts/data "
    "--projection display_name:data1:data2:data3:mimetype "
    "--where \"mimetype='vnd.android.cursor.item/contact_event'\""
)

MIMETYPE_EVENT = "vnd.android.cursor.item/contact_event"
# Android CommonDataKinds.Event: TYPE_BIRTHDAY = 3 (Jahrestag waere 0)
EVENT_TYP_GEBURTSTAG = 3

QUELLE_GRUPPE = "gruppe"
QUELLE_VERLAUF = "verlauf"


# ── Nummern: normalisieren, vergleichen, maskieren ───────────────────────────

def _ziffern(text: str | None) -> str:
    """Nur die Ziffern eines Texts (None/leer -> leerer String)."""
    return re.sub(r"\D", "", text or "")


def normalisiere_nummer(text: str | None) -> str | None:
    """Laendercode-behaftete Normalform, nur Ziffern.

    ``+49 151 ...`` -> ``49151...`` | ``0049 151 ...`` -> ``49151...`` |
    ``+49 (0) 151 ...`` -> ``49151...`` (Trunk-Null nach dem Laendercode) |
    ``0151 ...`` -> ``49151...`` (eine fuehrende Null gilt als deutsche
    Ortsnetz-/Mobilvorwahl). Ohne Ziffern -> ``None``.
    """
    d = _ziffern(text)
    if not d:
        return None
    if d.startswith("00"):
        d = d[2:]
    if d.startswith("490"):
        d = "49" + d[3:]  # Trunk-Null direkt nach dem Laendercode 49
    if d.startswith("0"):
        d = "49" + d[1:]
    return d or None


def nummer_varianten(text: str | None) -> set[str]:
    """Vergleichs-Varianten als Ziffernketten.

    Damit treffen sich ``+49``/``0049``/``0``/``+49 (0)``/ohne-Null-
    Schreibweisen beim Vergleich. Es wird nichts geraten, was nicht als
    Schreibvariante der selben Nummer lesbar ist: die deutsche Mobilform
    ``1...`` (10-12 Ziffern) wird zusaetzlich mit ``49`` davor gefuehrt.
    """
    d = _ziffern(text)
    if not d:
        return set()
    varianten = {d}
    basis = d[2:] if d.startswith("00") else d
    if basis != d:
        varianten.add(basis)
    if basis.startswith("490"):
        basis = "49" + basis[3:]
        varianten.add(basis)
    if basis.startswith("0"):
        varianten.add(basis[1:])
        varianten.add("49" + basis[1:])
    elif not basis.startswith("49") and re.fullmatch(r"1\d{9,11}", basis):
        varianten.add("49" + basis)
    normal = normalisiere_nummer(d)
    if normal:
        varianten.add(normal)
    return varianten


def maske_nummer(text: str | None) -> str | None:
    """Nur die letzten 4 Ziffern, z. B. ``***1234``; sonst ``None``."""
    d = _ziffern(text)
    if not d:
        return None
    return "***" + d[-4:]


def _ist_nummerkandidat(user: str | None) -> bool:
    """Echte Telefonnummern haben mindestens 7 Ziffern.

    Sehr kurze Kennungen (z. B. der WhatsApp-Systemkontakt ``0@s.whatsapp.net``)
    sind keine Personen und werden nicht als Nummer gefuehrt.
    """
    return len(_ziffern(user)) >= 7


def baue_kontakt_index(telefonbuch: list[dict]) -> dict[str, list[str]]:
    """Nummer-Varianten -> Telefonbuch-Namen (Mehrfachnamen bleiben erhalten)."""
    index: dict[str, list[str]] = {}
    for eintrag in telefonbuch:
        name = (eintrag.get("name") or "").strip()
        if not name:
            continue
        for variante in nummer_varianten(eintrag.get("nummer")):
            namen = index.setdefault(variante, [])
            if name not in namen:
                namen.append(name)
    return index


def kontakte_fuer(index: dict[str, list[str]], nummer: str | None) -> list[str]:
    """Alle Telefonbuch-Namen zu einer Nummer (leer, wenn kein Treffer)."""
    treffer: list[str] = []
    for variante in nummer_varianten(nummer):
        for name in index.get(variante, []):
            if name not in treffer:
                treffer.append(name)
    return sorted(treffer)


# ── ADB-Rohausgaben parsen ───────────────────────────────────────────────────

def _felder_zerlegen(rest: str, schluessel: list[str]) -> dict[str, str]:
    """``key=wert``-Paare aus einer ``content query``-Zeile.

    Werte duerfen Kommas enthalten (Namen); die Felder werden an den Positionen
    der bekannten Schluessel geschnitten.
    """
    positionen: list[tuple[int, str]] = []
    for schluesselwort in schluessel:
        position = rest.find(schluesselwort + "=")
        if position >= 0:
            positionen.append((position, schluesselwort))
    positionen.sort()
    felder: dict[str, str] = {}
    for i, (position, schluesselwort) in enumerate(positionen):
        start = position + len(schluesselwort) + 1
        ende = positionen[i + 1][0] if i + 1 < len(positionen) else len(rest)
        wert = rest[start:ende].strip().rstrip(",").strip()
        felder[schluesselwort] = wert
    return felder


def _zeilen_zerlegen(rohtext: str, schluessel: list[str]):
    """Alle ``Row: N ...``-Zeilen einer content-query-Ausgabe als dicts."""
    for zeile in (rohtext or "").splitlines():
        zeile = zeile.strip()
        if not zeile.startswith("Row: "):
            continue
        m = re.match(r"^Row:\s*\d+\s+(.*)$", zeile)
        if not m:
            continue
        yield _felder_zerlegen(m.group(1), schluessel)


def parse_telefonbuch(rohtext: str) -> list[dict]:
    """``[{name, nummer}, ...]`` aus der ADB-Ausgabe der Telefonbuch-Abfrage."""
    eintraege: list[dict] = []
    for felder in _zeilen_zerlegen(rohtext, ["display_name", "data1"]):
        eintraege.append(
            {"name": (felder.get("display_name") or "").strip(),
             "nummer": (felder.get("data1") or "").strip()}
        )
    return eintraege


def _datum_zerlegen(datum: str | None) -> tuple[int, int] | None:
    """``(tag, monat)`` aus ``YYYY-MM-DD`` oder ``--MM-DD``; sonst None."""
    datum = (datum or "").strip()
    treffer = re.fullmatch(r"\d{4}-(\d{2})-(\d{2})", datum) or re.fullmatch(r"--(\d{2})-(\d{2})", datum)
    if not treffer:
        return None
    monat, tag = int(treffer.group(1)), int(treffer.group(2))
    if not (1 <= monat <= 12 and 1 <= tag <= 31):
        return None
    return tag, monat


def parse_geburtstage(rohtext: str) -> list[dict]:
    """``[{name, tag, monat}, ...]`` aus den contact_event-Zeilen des Telefonbuchs.

    Nur echte Geburtstage (Typ 3); Jahrestage und kaputte Daten fallen raus.
    """
    geburtstage: list[dict] = []
    for felder in _zeilen_zerlegen(rohtext, ["display_name", "data1", "data2", "data3", "mimetype"]):
        if (felder.get("mimetype") or "") != MIMETYPE_EVENT:
            continue
        try:
            typ = int(felder.get("data2") or "-1")
        except ValueError:
            continue
        if typ != EVENT_TYP_GEBURTSTAG:
            continue
        zerlegt = _datum_zerlegen(felder.get("data1"))
        if zerlegt is None:
            continue
        tag, monat = zerlegt
        eintrag = {"name": (felder.get("display_name") or "").strip(),
                   "tag": tag, "monat": monat}
        if eintrag not in geburtstage:
            geburtstage.append(eintrag)
    return geburtstage


# ── msgstore.db lesen (nur lesend) ───────────────────────────────────────────

def lade_jids(con: sqlite3.Connection) -> dict[int, dict]:
    """``jid._id`` -> ``{user, server, type, raw}``."""
    jids: dict[int, dict] = {}
    for jid_id, user, server, typ, raw in con.execute(
            "SELECT _id, user, server, type, raw_string FROM jid"):
        jids[int(jid_id)] = {
            "user": (user or "").split(":")[0],
            "server": server or "",
            "type": typ,
            "raw": raw or "",
        }
    return jids


def lade_lid_lookup(con: sqlite3.Connection) -> tuple[dict[int, int], dict[int, str]]:
    """``(lid_row_id -> jid_row_id, lid_row_id -> WhatsApp-Anzeigename)``.

    Beide Tabellen koennen fehlen (aeltere Staende) - dann leere Zuordnungen.
    """
    mapping: dict[int, int] = {}
    namen: dict[int, str] = {}
    try:
        for lid, ziel in con.execute("SELECT lid_row_id, jid_row_id FROM jid_map"):
            if lid is not None and ziel is not None:
                mapping[int(lid)] = int(ziel)
    except sqlite3.Error:
        pass
    try:
        for lid, name in con.execute("SELECT lid_row_id, display_name FROM lid_display_name"):
            name = (name or "").strip()
            if lid is not None and name:
                namen[int(lid)] = name
    except sqlite3.Error:
        pass
    return mapping, namen


def lade_chats(con: sqlite3.Connection) -> list[dict]:
    """Alle Chats mit ihrem jid (``chat.jid_row_id`` -> ``jid``)."""
    chats: list[dict] = []
    for chat_id, subject, jid_id, user, server in con.execute(
            """SELECT c._id, c.subject, j._id, j.user, j.server
               FROM chat c LEFT JOIN jid j ON j._id = c.jid_row_id
               ORDER BY c._id"""):
        chats.append({
            "chat_id": int(chat_id),
            "subject": (subject or ""),
            "jid_id": int(jid_id) if jid_id is not None else None,
            "user": (user or "").split(":")[0],
            "server": server or "",
        })
    return chats


def _lade_participant_tabelle(con: sqlite3.Connection, tabellenname: str, merke) -> bool:
    """Liest eine Gruppen-Mitglieder-Tabelle, Spalten zur Laufzeit per PRAGMA.

    Unterstuetzte Formen: ``group_jid_row_id``/``user_jid_row_id`` (moderne
    Tabellen) und ``gjid``/``jid`` als Text (Text-Variante). Fehlt die Tabelle,
    passiert nichts (Ersatzweg greift).
    """
    try:
        spalten = {zeile[1] for zeile in con.execute(f"PRAGMA table_info({tabellenname})")}
    except sqlite3.Error:
        return False
    if not spalten:
        return False
    if {"group_jid_row_id", "user_jid_row_id"} <= spalten:
        try:
            for gruppe, nutzer in con.execute(
                    f"SELECT group_jid_row_id, user_jid_row_id FROM {tabellenname}"):
                merke(gruppe, nutzer, QUELLE_GRUPPE)
        except sqlite3.Error:
            return False
        return True
    if {"gjid", "jid"} <= spalten:
        try:
            for gruppe, nutzer in con.execute(
                    f"""SELECT gj._id, ju._id FROM {tabellenname} t
                        JOIN jid gj ON gj.raw_string = t.gjid
                        JOIN jid ju ON ju.raw_string = t.jid
                        WHERE t.gjid IS NOT NULL AND t.gjid != ''
                          AND t.jid IS NOT NULL AND t.jid != ''"""):
                merke(gruppe, nutzer, QUELLE_GRUPPE)
        except sqlite3.Error:
            return False
        return True
    return False


def lade_gruppenmitglieder(con: sqlite3.Connection) -> dict[int, dict[int, str]]:
    """``group_jid_row_id`` -> ``{user_jid_row_id: quelle}``.

    Reihenfolge: ``group_participant`` (falls vorhanden), ``group_participant_user``,
    ``group_participants`` (Textform); danach als Ersatz/Zusatz die
    System-Nachrichten und die Absender aus dem Verlauf. Die Quelle gewinnt
    ``gruppe`` gegen ``verlauf``.
    """
    ergebnis: dict[int, dict[int, str]] = {}

    def merke(gruppe, nutzer, quelle):
        if not gruppe or not nutzer:
            return
        vorhanden = ergebnis.setdefault(int(gruppe), {})
        if int(nutzer) not in vorhanden or quelle == QUELLE_GRUPPE:
            vorhanden[int(nutzer)] = quelle

    for tabellenname in ("group_participant", "group_participant_user", "group_participants"):
        _lade_participant_tabelle(con, tabellenname, merke)

    # Ersatzweg 1: System-Nachrichten (Mitglied beigetreten/entfernt)
    try:
        for gruppe, nutzer in con.execute(
                """SELECT c.jid_row_id, msp.user_jid_row_id
                   FROM message_system_chat_participant msp
                   JOIN message m ON m._id = msp.message_row_id
                   JOIN chat c ON c._id = m.chat_row_id"""):
            merke(gruppe, nutzer, QUELLE_VERLAUF)
    except sqlite3.Error:
        pass

    # Ersatzweg 2: Absender im Verlauf (nicht ich)
    try:
        for gruppe, nutzer in con.execute(
                """SELECT c.jid_row_id, m.sender_jid_row_id
                   FROM message m
                   JOIN chat c ON c._id = m.chat_row_id
                   WHERE m.from_me = 0 AND m.sender_jid_row_id > 0"""):
            merke(gruppe, nutzer, QUELLE_VERLAUF)
    except sqlite3.Error:
        pass

    return ergebnis


def loese_person(jids: dict[int, dict], lid_map: dict[int, int], lid_namen: dict[int, str],
                 rueck_namen: dict[int, str], jid_id: int | None) -> dict:
    """Person zu einer jid-Zeile: Nummer (falls bekannt), WhatsApp-Name, Selbst?"""
    person = {"nummer": None, "whatsapp_name": None, "server": "", "selbst": False}
    if jid_id is None:
        return person
    jid = jids.get(int(jid_id))
    if not jid:
        return person
    server = jid["server"]
    person["server"] = server
    if server == "s.whatsapp.net":
        person["nummer"] = jid["user"] if _ist_nummerkandidat(jid["user"]) else None
        person["whatsapp_name"] = rueck_namen.get(int(jid_id))
    elif server == "lid":
        person["whatsapp_name"] = lid_namen.get(int(jid_id))
        ziel = lid_map.get(int(jid_id))
        ziel_jid = jids.get(ziel) if ziel is not None else None
        if ziel_jid and ziel_jid["server"] == "s.whatsapp.net" \
                and _ist_nummerkandidat(ziel_jid["user"]):
            person["nummer"] = ziel_jid["user"] or None
    elif server == "lid_me":
        person["selbst"] = True
    else:
        person["whatsapp_name"] = lid_namen.get(int(jid_id))
    return person


def _rueck_namen_bauen(lid_map: dict[int, int], lid_namen: dict[int, str]) -> dict[int, str]:
    """jid_row_id (Nummer) -> WhatsApp-Anzeigename ueber die LID-Zuordnung."""
    rueck: dict[int, str] = {}
    for lid, ziel in lid_map.items():
        name = lid_namen.get(lid)
        if name and ziel not in rueck:
            rueck[ziel] = name
    return rueck


# ── Zuordnung bauen ──────────────────────────────────────────────────────────

def baue_zuordnung(con: sqlite3.Connection, telefonbuch: list[dict],
                   geburtstage: list[dict]) -> dict:
    """Baut das Gesamtergebnis (nur Zaehlungen + die private Chat-Liste)."""
    jids = lade_jids(con)
    lid_map, lid_namen = lade_lid_lookup(con)
    rueck_namen = _rueck_namen_bauen(lid_map, lid_namen)
    mitglieder_je_gruppe = lade_gruppenmitglieder(con)
    index = baue_kontakt_index(telefonbuch)
    chats = lade_chats(con)

    eintraege: list[dict] = []
    zahlen = {
        "chats_mit_kontakt": 0, "chats_ohne_kontakt": 0,
        "chats_mit_whatsapp_namen": 0,
        "gruppen_gesamt": 0, "gruppen_vollstaendig": 0, "gruppen_teilweise": 0,
        "gruppen_unbekannt": 0, "gruppen_ohne_mitgliederdaten": 0,
        "mitglieder_gesamt": 0, "mitglieder_mit_kontakt": 0,
        "chats_einzel": 0, "chats_newsletter": 0, "chats_sonstiges": 0,
    }

    for chat in chats:
        server = chat["server"]
        if server == "g.us":
            art = "gruppe"
        elif server in ("s.whatsapp.net", "lid"):
            art = "einzel"
        elif server == "newsletter":
            art = "newsletter"
        else:
            art = "sonstiges"
        eintrag: dict = {"chat_row_id": chat["chat_id"], "art": art}

        if art == "einzel":
            person = loese_person(jids, lid_map, lid_namen, rueck_namen, chat["jid_id"])
            namen = kontakte_fuer(index, person["nummer"])
            eintrag["telefonbuch_namen"] = namen
            eintrag["whatsapp_name"] = person["whatsapp_name"]
            eintrag["nummer_maske"] = maske_nummer(person["nummer"])
            eintrag["kontakt_treffer"] = bool(namen)
            zahlen["chats_einzel"] += 1
            if person["whatsapp_name"]:
                zahlen["chats_mit_whatsapp_namen"] += 1
        elif art == "gruppe":
            teilnehmer: list[dict] = []
            for jid_id, quelle in sorted(mitglieder_je_gruppe.get(chat["jid_id"] or -1, {}).items()):
                person = loese_person(jids, lid_map, lid_namen, rueck_namen, jid_id)
                if person["selbst"]:
                    continue  # Sebastian selbst ist kein Kontakt
                if person["server"] not in ("lid", "s.whatsapp.net"):
                    continue  # z. B. Broadcast-Reste - keine Person
                namen = kontakte_fuer(index, person["nummer"])
                if namen:
                    name, quelle_name = namen[0], "telefonbuch"
                elif person["whatsapp_name"]:
                    name, quelle_name = person["whatsapp_name"], "whatsapp"
                else:
                    name, quelle_name = "unbekannt", "unbekannt"
                teilnehmer.append({
                    "name": name,
                    "nummer_maske": maske_nummer(person["nummer"]),
                    "quelle": quelle_name,
                    "im_telefonbuch": bool(namen),
                    "_herkunft": quelle,
                })
            teilnehmer.sort(key=lambda t: t["name"].casefold())
            mit_kontakt = sum(1 for t in teilnehmer if t["im_telefonbuch"])
            eintrag["anzahl_mitglieder"] = len(teilnehmer)
            eintrag["mitglieder_mit_kontakt"] = mit_kontakt
            eintrag["teilnehmer"] = teilnehmer
            eintrag["kontakt_treffer"] = mit_kontakt > 0
            zahlen["gruppen_gesamt"] += 1
            zahlen["mitglieder_gesamt"] += len(teilnehmer)
            zahlen["mitglieder_mit_kontakt"] += mit_kontakt
            if not teilnehmer:
                zahlen["gruppen_ohne_mitgliederdaten"] += 1
                zahlen["gruppen_unbekannt"] += 1
            elif mit_kontakt == len(teilnehmer):
                zahlen["gruppen_vollstaendig"] += 1
            elif mit_kontakt > 0:
                zahlen["gruppen_teilweise"] += 1
            else:
                zahlen["gruppen_unbekannt"] += 1
        else:
            eintrag["kontakt_treffer"] = False
            zahlen["chats_newsletter" if art == "newsletter" else "chats_sonstiges"] += 1

        if eintrag["kontakt_treffer"]:
            zahlen["chats_mit_kontakt"] += 1
        else:
            zahlen["chats_ohne_kontakt"] += 1
        eintraege.append(eintrag)

    geburtstage_sortiert = sorted(
        geburtstage, key=lambda g: (g["monat"], g["tag"], g["name"].casefold()))
    geburtstags_namen = {g["name"] for g in geburtstage if g["name"]}
    statistik = {
        "telefonbuch_eintraege": len(telefonbuch),
        "telefonbuch_namen": len({(e.get("name") or "").strip() for e in telefonbuch if (e.get("name") or "").strip()}),
        "geburtstage_im_telefonbuch": len(geburtstags_namen),
        "geburtstage_zeilen": len(geburtstage),
        "chats_gesamt": len(eintraege),
        **zahlen,
    }
    statistik["mitglieder_ohne_kontakt"] = (
        statistik["mitglieder_gesamt"] - statistik["mitglieder_mit_kontakt"])
    return {
        "erstellt": datetime.date.today().isoformat(),
        "hinweis": (
            "Private Zuordnung WhatsApp-Chat <-> Telefonbuch. Nummern nur als "
            "letzte 4 Ziffern maskiert. Quelle: msgstore.db (nur lesend) und "
            "Telefonbuch per ADB."
        ),
        "statistik": statistik,
        "geburtstage": geburtstage_sortiert,
        "chats": eintraege,
    }


def bericht_zeilen(statistik: dict) -> list[str]:
    """Kurzer Bericht - ausschliesslich Zaehlungen, nie Namen oder Nummern."""
    return [
        f"Telefonbuch: {statistik['telefonbuch_eintraege']} Eintraege, "
        f"{statistik['telefonbuch_namen']} Namen, "
        f"{statistik['geburtstage_im_telefonbuch']} mit Geburtstag",
        f"Chats: {statistik['chats_gesamt']} gesamt | mit Kontakt "
        f"{statistik['chats_mit_kontakt']} | ohne Kontakt {statistik['chats_ohne_kontakt']} "
        f"(Einzel {statistik['chats_einzel']}, Gruppen {statistik['gruppen_gesamt']}, "
        f"Newsletter {statistik['chats_newsletter']}, Sonstige {statistik['chats_sonstiges']})",
        f"Gruppen: {statistik['gruppen_gesamt']} | vollstaendig "
        f"{statistik['gruppen_vollstaendig']} | teilweise {statistik['gruppen_teilweise']} | "
        f"unbekannt {statistik['gruppen_unbekannt']} "
        f"(davon ohne Mitgliederdaten {statistik['gruppen_ohne_mitgliederdaten']})",
        f"Mitglieder: {statistik['mitglieder_gesamt']} | mit Kontakt "
        f"{statistik['mitglieder_mit_kontakt']} | ohne Kontakt "
        f"{statistik['mitglieder_ohne_kontakt']}",
    ]


def schreibe_json(daten: dict, pfad: str | Path) -> Path:
    """Schreibt die JSON-Datei (UTF-8, lesbar formatiert) an den Zielpfad."""
    ziel = Path(pfad)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("w", encoding="utf-8") as datei:
        json.dump(daten, datei, ensure_ascii=False, indent=1)
        datei.write("\n")
    return ziel


# ── ADB / Hauptlauf ──────────────────────────────────────────────────────────

def adb_ausfuehren(geraet: str | None, befehl: str) -> str:
    """Fuehrt ein ``adb shell <befehl>`` aus und liefert stdout."""
    aufruf = ["adb"] + (["-s", geraet] if geraet else []) + ["shell", befehl]
    ergebnis = subprocess.run(aufruf, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
    if ergebnis.returncode != 0:
        raise RuntimeError(f"adb endete mit Rueckgabewert {ergebnis.returncode} "
                           f"({(ergebnis.stderr or '').strip()[:120]!r})")
    return ergebnis.stdout or ""


def _rohtext_holen(datei: str | None, geraet: str | None, befehl: str) -> str:
    if datei:
        return Path(datei).read_text(encoding="utf-8", errors="replace")
    return adb_ausfuehren(geraet, befehl)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Baut die private Zuordnung WhatsApp-Chat <-> Telefonbuch (nur lesend).")
    parser.add_argument("--db", default=STANDARD_DB, help="Pfad zu msgstore.db (nur lesend)")
    parser.add_argument("--ausgabe", default=STANDARD_AUSGABE, help="Ziel-JSON (ausserhalb des Repos)")
    parser.add_argument("--geraet", default=None, help="ADB-Seriennummer (bei mehreren Geraeten)")
    parser.add_argument("--telefonbuch-datei", default=None,
                        help="Statt ADB: gespeicherte Rohausgabe der Telefonbuch-Abfrage")
    parser.add_argument("--events-datei", default=None,
                        help="Statt ADB: gespeicherte Rohausgabe der contact_event-Abfrage")
    args = parser.parse_args(argv)

    db_pfad = Path(args.db)
    if not db_pfad.is_file():
        print(f"FEHLER: Datenbank nicht gefunden: {db_pfad}", file=sys.stderr)
        return 2

    try:
        telefonbuch = parse_telefonbuch(
            _rohtext_holen(args.telefonbuch_datei, args.geraet, TELEFONBUCH_QUERY))
        geburtstage = parse_geburtstage(
            _rohtext_holen(args.events_datei, args.geraet, EVENTS_QUERY))
    except (RuntimeError, OSError) as fehler:
        print(f"FEHLER: Telefonbuch konnte nicht gelesen werden ({fehler})", file=sys.stderr)
        return 3
    if not telefonbuch:
        print("FEHLER: Telefonbuch lieferte keine Eintraege - Datei wird nicht geschrieben.",
              file=sys.stderr)
        return 3

    uri = db_pfad.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        daten = baue_zuordnung(con, telefonbuch, geburtstage)
    finally:
        con.close()

    ziel = schreibe_json(daten, args.ausgabe)
    for zeile in bericht_zeilen(daten["statistik"]):
        print(zeile)
    print(f"Geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
