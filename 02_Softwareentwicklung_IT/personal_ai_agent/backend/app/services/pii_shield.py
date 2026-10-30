"""
Reversible PII-Maskierung fuer LLM-Aufrufe (pii_shield.py).

Spezifikation Modul C (30.10.2026):
1. Pre-Flight Encoding:
   Ersetzt bekannte Klardaten (Personennamen, Alias-Namen, Verwandtschaftsrollen,
   Orte, Telefonnummern, E-Mails) deterministisch durch Tokens ([PERSON_01], [LOC_01], etc.),
   bevor ein Prompt an ein Cloud-LLM (z. B. via OpenRouter) gesendet wird.
2. Stream-Decoding:
   Ein Streaming-Buffer haelt eintreffende LLM-Tokenfragmente kurz zurueck, bis ein
   Maskierungs-Token vollstaendig ist, und ersetzt es in Echtzeit wieder durch das
   Original, bevor der Text an die TTS/Sprachausgabe geht.
3. Deterministischer Fastpath:
   Haeufige Zaehl- und Faktenfragen (z. B. "Wie viele Bilder gibt es von X?") werden
   ohne Cloud-LLM direkt lokal aus der Datenbank beantwortet.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, Generator, Iterable, Iterator, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Standard-Muster fuer Telefonnummern und E-Mails
RE_PHONE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,5}\)?[-.\s]?\d{3,9}[-.\s]?\d{2,9}")
RE_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# Erkennung von Maskierungs-Tokens
RE_TOKEN = re.compile(r"\[([A-Z]+)_(\d+)\]")


class PIIShield:
    """Verwaltet deterministische PII-Maskierung und Stream-Rueckentschluesselung."""

    def __init__(self) -> None:
        self.plain_to_token: Dict[str, str] = {}
        self.token_to_plain: Dict[str, str] = {}
        self._counts: Dict[str, int] = {
            "PERSON": 0,
            "LOC": 0,
            "PHONE": 0,
            "EMAIL": 0,
            "ROLE": 0,
            "ENTITY": 0,
        }

    def register_entity(self, plain_value: str, category: str = "ENTITY") -> str:
        """Registriert eine Entitaet und liefert das zugewiesene Token."""
        wert = plain_value.strip()
        if not wert:
            return ""

        # Wenn bereits registriert, das vorhandene Token wiederverwenden
        if wert in self.plain_to_token:
            return self.plain_to_token[wert]

        kat = category.upper()
        self._counts[kat] = self._counts.get(kat, 0) + 1
        token = f"[{kat}_{self._counts[kat]:02d}]"

        self.plain_to_token[wert] = token
        self.token_to_plain[token] = wert
        return token

    def register_person(self, name: str, aliases: Optional[List[str]] = None) -> str:
        """Registriert eine Person und optionale Spitznamen/Aliase mit jeweils eindeutigem Token."""
        token = self.register_entity(name, category="PERSON")
        if aliases:
            for alias in aliases:
                a_clean = alias.strip()
                if a_clean:
                    # Jeder Alias erhaelt ein eigenes Token fuer 100% exakte Rueckentschluesselung
                    self.register_entity(a_clean, category="PERSON")
        return token


    def register_location(self, location: str) -> str:
        """Registriert einen geografischen Ort."""
        return self.register_entity(location, category="LOC")

    def register_role(self, role: str) -> str:
        """Registriert eine soziale oder familiaere Rolle (z. B. 'Mama', 'Opa')."""
        return self.register_entity(role, category="ROLE")

    def encode(self, text: str) -> str:
        """Maskiert bekannte PII-Werte sowie Telefonnummern und E-Mails im Text.

        Laengere Entitaeten werden zuerst ersetzt, um Teilstring-Kollisionen zu vermeiden.
        """
        if not text:
            return ""

        ergebnis = text

        # 1. E-Mails automatisch maskieren
        for match in RE_EMAIL.finditer(ergebnis):
            mail = match.group(0)
            token = self.register_entity(mail, category="EMAIL")
            ergebnis = ergebnis.replace(mail, token)

        # 2. Telefonnummern automatisch maskieren (nur wenn mind. 6 Ziffern)
        for match in RE_PHONE.finditer(ergebnis):
            phone = match.group(0).strip()
            # Mindestziffern pruefen, um Jahreszahlen/Zahlenketten nicht faelschlich zu maskieren
            ziffern = re.sub(r"\D", "", phone)
            if len(ziffern) >= 7 and not phone.startswith("["):
                token = self.register_entity(phone, category="PHONE")
                ergebnis = ergebnis.replace(phone, token)

        # 3. Registrierte Namen, Orte und Rollen nach Laenge absteigend ersetzen
        sortierte_eintraege = sorted(self.plain_to_token.items(), key=lambda kv: len(kv[0]), reverse=True)
        for plain, token in sortierte_eintraege:
            if not plain:
                continue
            # Wortgrenzen-sicheres Ersetzen fuer reine Woerter
            escaped = re.escape(plain)
            muster = rf"\b{escaped}\b"
            ergebnis = re.sub(muster, token, ergebnis, flags=re.IGNORECASE)

        return ergebnis

    def decode(self, text: str) -> str:
        """Ersetzt alle Maskierungs-Tokens wieder durch die echten Klardaten."""
        if not text:
            return ""

        def ersetzung(match: re.Match) -> str:
            token = match.group(0)
            return self.token_to_plain.get(token, token)

        return RE_TOKEN.sub(ersetzung, text)

    def decode_stream(self, chunk_generator: Iterable[str]) -> Generator[str, None, None]:
        """Streaming-Decoder fuer LLM-Antworten.

        Puffert unvollstaendige Token-Fragmente (z. B. '[PERS' ... 'ON_01]')
        und loest sie sofort auf, sobald das Token komplett ist.
        """
        buffer = ""
        in_token = False

        for chunk in chunk_generator:
            if not chunk:
                continue

            for char in chunk:
                if char == "[":
                    # Wenn bereits ein Buffer lief, der kein Token wurde, erst leeren
                    if in_token:
                        yield buffer
                        buffer = ""
                    in_token = True
                    buffer += char
                elif in_token:
                    buffer += char
                    if char == "]":
                        # Token ist abgeschlossen
                        in_token = False
                        if RE_TOKEN.fullmatch(buffer):
                            # Bekanntes oder unbekanntes Token ersetzen
                            yield self.token_to_plain.get(buffer, buffer)
                        else:
                            yield buffer
                        buffer = ""
                    elif len(buffer) > 25:
                        # Maximale Tokenlaenge ueberschritten -> kein Maskierungs-Token
                        in_token = False
                        yield buffer
                        buffer = ""
                else:
                    yield char

        # Verbliebenen Puffer ausgeben
        if buffer:
            if RE_TOKEN.fullmatch(buffer):
                yield self.token_to_plain.get(buffer, buffer)
            else:
                yield buffer

    def fastpath_statistik(self, anfrage: str, db_cursor: Any) -> Optional[str]:
        """Beantwortet haeufige Zaehlfragen deterministisch ohne Cloud-LLM."""
        anf = anfrage.lower().strip()

        # Muster: "wie viele fotos/bilder von <name> gibt es"
        m = re.search(r"wie viele (?:fotos|bilder) von ([a-zäöüß\s]+) gibt es", anf)
        if m:
            suchname = m.group(1).strip()
            # Finde die Person in der DB
            db_cursor.execute("SELECT kennung, name FROM persons WHERE lower(name) = ?", (suchname,))
            row = db_cursor.fetchone()
            if row:
                kennung, name = row[0], row[1]
                db_cursor.execute("SELECT COUNT(DISTINCT photo_fileid) FROM photo_faces WHERE person_kennung = ?", (kennung,))
                anzahl = db_cursor.fetchone()[0]
                return f"Von {name} gibt es {anzahl} Fotos im Archiv."

        # Muster: "wie viele fotos/bilder haben wir insgesamt"
        if "wie viele fotos" in anf and "insgesamt" in anf:
            db_cursor.execute("SELECT COUNT(*) FROM photos")
            gesamt = db_cursor.fetchone()[0]
            return f"Es sind insgesamt {gesamt} Fotos im Archiv gespeichert."

        return None
