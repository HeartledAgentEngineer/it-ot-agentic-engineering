"""Automatische Erkennung aktiver Chats aus Antigravity, Claude Code und Codex."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import signale


@dataclass(frozen=True)
class ChatVorschlag:
    thema: str
    titel: str
    quelle: str
    sitzung_id: str
    zeit: str


def thema_bereinigen(titel: str) -> str:
    """Wandelt einen beliebigen Chattitel in einen zulässigen Themanamen um (nur a-z, 0-9, -)."""
    titel = titel.strip()
    if titel.lower().startswith("thema:"):
        titel = titel[6:].strip()
    # Umlaute und Sonderzeichen ersetzen
    ersetzungen = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
                   ("Ä", "ae"), ("Ö", "oe"), ("Ü", "ue"))
    for u, e in ersetzungen:
        titel = titel.replace(u, e)
    # Nur Kleinbuchstaben, Ziffern und Bindestriche
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", titel).strip("-").lower()
    return slug[:40] if slug else "neues-thema"


def antigravity_db_pfad() -> Path:
    return Path.home() / ".gemini" / "antigravity" / "conversation_summaries.db"


def antigravity_chats_finden(db_datei: Path | None = None) -> list[ChatVorschlag]:
    db_pfad = db_datei or antigravity_db_pfad()
    if not db_pfad.exists():
        return []
    vorschlaege: list[ChatVorschlag] = []
    try:
        con = sqlite3.connect(f"file:{db_pfad}?mode=ro", uri=True)
        try:
            cur = con.cursor()
            cur.execute("""
                SELECT conversation_id, title, last_modified_time
                FROM conversation_summaries
                WHERE title != ''
                ORDER BY last_modified_time DESC
                LIMIT 20
            """)
            for cid, title, lmt in cur.fetchall():
                if not title or not isinstance(title, str):
                    continue
                slug = thema_bereinigen(title)
                if slug:
                    vorschlaege.append(ChatVorschlag(
                        thema=slug,
                        titel=title.strip(),
                        quelle="Antigravity",
                        sitzung_id=str(cid),
                        zeit=str(lmt)[:19],
                    ))
        finally:
            con.close()
    except (sqlite3.Error, OSError):
        pass
    return vorschlaege


def codex_sessions_ordner() -> Path:
    return signale.codex_ordner()


def codex_chats_finden(ordner: Path | None = None) -> list[ChatVorschlag]:
    ordner = ordner or codex_sessions_ordner()
    if not ordner.exists():
        return []
    vorschlaege: list[ChatVorschlag] = []
    try:
        dateien = sorted(ordner.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
        for datei in dateien:
            stem = datei.stem
            slug = thema_bereinigen(stem)
            mtime = datetime.fromtimestamp(datei.stat().st_mtime, tz=timezone.utc).isoformat()[:19]
            vorschlaege.append(ChatVorschlag(
                thema=slug,
                titel=stem,
                quelle="Codex",
                sitzung_id=stem,
                zeit=mtime,
            ))
    except OSError:
        pass
    return vorschlaege


def claude_chats_finden(status_ordner: Path | None = None) -> list[ChatVorschlag]:
    ordner = status_ordner or (signale.daten_ordner() / "status")
    if not ordner.exists():
        return []
    vorschlaege: list[ChatVorschlag] = []
    try:
        dateien = sorted(ordner.glob("claude-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
        for datei in dateien:
            kennung = datei.stem.removeprefix("claude-")
            slug = thema_bereinigen(kennung)
            mtime = datetime.fromtimestamp(datei.stat().st_mtime, tz=timezone.utc).isoformat()[:19]
            vorschlaege.append(ChatVorschlag(
                thema=slug,
                titel=f"Claude-Session {kennung[:8]}",
                quelle="Claude",
                sitzung_id=kennung,
                zeit=mtime,
            ))
    except OSError:
        pass
    return vorschlaege


def neue_themen_vorschlaege(bestehende_themen: set[str],
                            db_datei: Path | None = None,
                            codex_ordner: Path | None = None,
                            status_ordner: Path | None = None) -> list[ChatVorschlag]:
    """Sucht neue Chats aller Institutionen (Antigravity, Codex, Claude), prüft Kontingente und filtert bereits registrierte Themen aus."""
    kandidaten: list[ChatVorschlag] = []
    
    # Antigravity Chats prüfen (wenn nicht im Limit)
    gemini_kont = signale.gemini_lesen()
    gemini_frei = not gemini_kont.fehler and all(f.prozent < 100 for f in gemini_kont.fenster)
    if gemini_frei or not gemini_kont.fenster:
        kandidaten.extend(antigravity_chats_finden(db_datei))

    # Codex Chats prüfen (wenn nicht im Limit)
    codex_kont = signale.codex_lesen()
    codex_frei = not codex_kont.fehler and all(f.prozent < 100 for f in codex_kont.fenster)
    if codex_frei or not codex_kont.fenster:
        kandidaten.extend(codex_chats_finden(codex_ordner))

    # Claude Chats prüfen (wenn nicht im Limit)
    claude_kont = signale.claude_lesen()
    claude_frei = not claude_kont.fehler and all(f.prozent < 100 for f in claude_kont.fenster)
    if claude_frei or not claude_kont.fenster:
        kandidaten.extend(claude_chats_finden(status_ordner))

    # Filtern: Nur neue Themen, die noch nicht in den bestehenden Themen vorkommen
    ergebnis: list[ChatVorschlag] = []
    gesehen: set[str] = set()
    for v in kandidaten:
        if v.thema not in bestehende_themen and v.thema not in gesehen:
            gesehen.add(v.thema)
            ergebnis.append(v)
    return ergebnis
