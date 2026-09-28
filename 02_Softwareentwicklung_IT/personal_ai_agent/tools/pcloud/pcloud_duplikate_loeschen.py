"""pCloud-Duplikate loeschen — TROCKENLAUF ist der Standard, echt nur mit ``--wirklich``.

Wozu dieses Werkzeug (Feinauftrag N18, 28.09.2026):
    ``tools/pcloud/pcloud_duplikate.py`` liefert den Bericht mit den
    Loesch-Kandidaten (gleiche Groesse UND gleiche pCloud-Pruefsumme) — aber
    geloescht hat bisher nichts: der geforderte Loesch-Schritt war im Plan
    notiert, "gebaut wurde er nicht"
    (``docs/abschlussbericht-nachtlauf-2026-09-26.md``). Dieses Werkzeug loest
    genau eine Aufgabe: die Kopien im Upload-Baum ``Automatic Upload``, die
    im Bericht als ``loesch_kandidaten`` stehen, in den **pCloud-Papierkorb**
    legen — sonst nichts.

Was dieses Werkzeug bewusst NICHT tut:
    * **Kein Loeschen ohne ``--wirklich``.** Ohne den Schalter wird keine
      schreibende API-Methode gesendet (auch nicht "probeweise").
    * **Kein Entfernen ganzer Ordner** — es gibt in dieser Datei keinen
      Aufruf dafuer und auch keine Positivlisten-Eintragung.
    * **Kein Verschieben, kein Umbenennen, kein Kopieren.**
    * **Kein Herunterladen von Dateiinhalten** — gelesen werden nur
      Metadaten (Name, Groesse, Pruefsumme). Kein Vorschaubild, kein Inhalt.
    * **Kein endgueltiges Loeschen:** pCloud legt Geloeschtes in den
      Papierkorb. Zurueckgeholt wird von Hand ueber ``trash_list`` (anzeigen)
      und ``trash_restore`` (zuruecklegen) — dieses Werkzeug ruft
      ``trash_restore`` nie auf und baut es nicht nach.
    * **Kein zweiter Manifest-Weg:** jede Loeschung wird sofort als **eine**
      Zeile ueber ``manifest_anhaengen`` aus ``tools/pcloud/pcloud_bewegungen.py``
      gebucht (Standard ``~/foto_sortierung/manifest.jsonl``); ein Pfad im
      Git-Repo wird verweigert.

Schutzregeln (jede einzeln getestet):
    1. **Trockenlauf ist der Standard** — er sendet nichts (ausser dem
       ausdruecklich verlangten, rein lesenden Papierkorb-Blick ``--papierkorb``).
    2. **Nur Kopien im Baum** ``upload``. Ein Kandidat aus der Sammlung
       (``Bilder & Videos``) wird verweigert — auch wenn er ueber
       ``--nur-dateien`` ausdruecklich genannt wird (deutsche Meldung, Exit 2,
       nichts geschrieben).
    3. **Frische Gegenprobe vor jedem Loeschen:** Groesse UND Pruefsumme
       werden unmittelbar vor dem Loeschen live neu gelesen und gegen den
       Bericht verglichen. Abweichung oder "nicht mehr auffindbar" ⇒
       **Abbruch des ganzen Laufs**, Exit 2, kein weiteres Loeschen, keine
       Manifest-Zeile fuer den abweichenden Eintrag. Es wird nicht geraten.
    4. **Manifest-Pflicht:** keine Loeschung ohne Buchung. Ist der
       Manifest-Ort unbrauchbar (z. B. im Repo), passiert **gar nichts**.
    5. **Grenze je Lauf** (``--grenze``, Standard 25, hart geklemmt auf
       1…200); die Restzahl wird ehrlich genannt.
    6. **Idempotent:** was laut Manifest schon als ``loeschen`` gebucht ist,
       wird uebersprungen — ein zweiter Lauf am selben Stand hat nichts zu
       tun (``geloescht: 0``, keine neue Zeile, Exit 0).
    7. **Kein Geheimnis:** der Token wird nie ausgegeben, nie geloggt und
       steht in keiner Datei, die dieses Modul schreibt; Anbieter-Fehlertexte
       werden wie im Nachbarmodul bereinigt.

Positivliste der API-Methoden (genau diese drei):
    ``listfolder`` (lesen), ``deletefile`` (in den Papierkorb), ``trash_list``
    (Papierkorb anzeigen — nur lesend). Jeder andere Methodenname wird
    abgewiesen, BEVOR etwas gesendet wird.

Aufruf (Bericht aus ``pcloud_duplikate.py``; Token aus Umgebung oder ``backend/.env``):
    cd backend
    .venv/Scripts/python ../tools/pcloud/pcloud_duplikate_loeschen.py
    .venv/Scripts/python ../tools/pcloud/pcloud_duplikate_loeschen.py --papierkorb
    .venv/Scripts/python ../tools/pcloud/pcloud_duplikate_loeschen.py --wirklich --grenze 25
    .venv/Scripts/python ../tools/pcloud/pcloud_duplikate_loeschen.py --wirklich --nur-dateien kandidaten.txt

Rueckgabewerte: 0 = Trockenlauf gelaufen bzw. Loeschungen vollstaendig
gebucht; 2 = Bedien-/Konfigurationsfehler, Schutzverletzung oder Abbruch
(kein Loeschen ohne Manifest, kein Loeschen bei Abweichung).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import httpx

# Damit ``import pcloud_bewegungen`` auch dann klappt, wenn dieses Werkzeug
# aus einem anderen Arbeitsverzeichnis gestartet oder per Pfad geladen wird
# (Tests): das eigene Verzeichnis in den Suchpfad aufnehmen.
_HIER = Path(__file__).resolve().parent
if str(_HIER) not in sys.path:
    sys.path.insert(0, str(_HIER))

import pcloud_bewegungen as bewegen  # noqa: E402

# EU-Rechenzentrum des Kontos (wie in den Nachbarmodulen).
STANDARD_HOST = "eapi.pcloud.com"

# Ein Aufruf soll schnell scheitern, statt minutenlang zu haengen.
TIMEOUT_SEKUNDEN = 30.0

# Standard-Ablage des Berichts: im Benutzerverzeichnis, niemals im Repo.
STANDARD_BERICHT = "~/foto_sortierung/duplikate.json"
UMGEBUNG_BERICHT = "PCLOUD_DUPLIKATE_ZIEL"

# Nur dieser Baum traegt Kandidaten. Die Sammlung ist tabu (CLAUDE.md,
# "Sicherheit: Duplikate"): geloescht wird immer die Kopie im Stapel.
BAUM_UPLOAD = "upload"

# Die erlaubten Berichts-Arten fuer --art.
ARTEN = ("ueber_baeume", "innerhalb_upload", "alle")
ART_STANDARD = "alle"

# Grenze je Lauf: hart geklemmt, damit ein vergessener Schalter keinen
# 2.133-Kandidaten-Lauf ausloest.
GRENZE_STANDARD = 25
GRENZE_MIN = 1
GRENZE_MAX = 200

# Wie viele Kandidaten die Konsole nennt.
BEISPIELE_STANDARD = 5

# Die Manifest-Art der Loeschungen.
MANIFEST_ART = "loeschen"

# Positivliste der API-Methoden: lesen, in den Papierkorb legen, Papierkorb
# anzeigen. Waere hier ein anderer Aufruf dabei (z. B. das Entfernen ganzer
# Ordner), waere das Sicherheitsnetz kaputt — Aenderungen an dieser Liste
# sind eine bewusste Entscheidung, kein Versehen.
ERLAUBTE_METHODEN = ("listfolder", "deletefile", "trash_list")

# Wurzelkennung der pCloud (fuer den Ersatzweg, den Baum-Ordner zu finden).
WURZEL_ID = 0

# Die Manifest-Art ``loeschen`` steht in ``pcloud_bewegungen.ERLAUBTE_ARTEN``
# (dort ausdruecklich ergaenzt, samt Docstring) — dieses Werkzeug bucht seine
# Loeschungen ueber ``manifest_anhaengen`` und baut bewusst KEINE zweite
# Manifest-Logik (Auftrag N18, Regel 4). Hier wird nichts an fremden Modulen
# veraendert.


class DuplikateLoeschFehler(Exception):
    """Fehler beim Loesch-Lauf — Klartext fuer den Nutzer.

    Enthaelt nie den Token (siehe ``bewegen._ohne_geheimnis``).
    """


# ── Kleine Helfer ──────────────────────────────────────────────────────────

def _jetzt_iso() -> str:
    """Aktuelle Zeit als ISO-Text MIT Zonenversatz (z. B. 2026-09-28T05:12:34+02:00)."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _als_int_oder_none(wert: Any) -> Optional[int]:
    """Zahl tolerant lesen — fehlende/unbrauchbare Werte werden ehrlich None.

    Ein kaputter Wert aus dem Bericht oder aus einer API-Antwort darf keinen
    Absturz ausloesen; ``None`` ist die sichtbar harmlose Variante.
    """
    if wert is None or isinstance(wert, bool):
        return None
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


def _als_id(wert: Any, feld: str) -> int:
    """Pflicht-Kennung als int — unbrauchbare Werte werden zum Klartextfehler."""
    zahl = _als_int_oder_none(wert)
    if zahl is None:
        raise DuplikateLoeschFehler(f"{feld} fehlt oder ist keine Zahl: {wert!r}")
    return zahl


def _hash_text(wert: Any) -> Optional[str]:
    """Pruefsumme als Vergleichstext (``None``, wenn keine brauchbare da ist).

    pCloud liefert den Hash als ZAHL; fuer den Vergleich wird er als Text
    behandelt — so ist dieselbe Pruefsumme auch dann gleich, wenn ein Server
    sie einmal als Text liefert (gleiche Logik wie im Duplikate-Bericht).
    """
    if wert is None:
        return None
    text = str(wert).strip()
    return text or None


def _zahl_de(wert: Any) -> str:
    """Ganzzahl deutsch mit Tausenderpunkt (1234 -> "1.234")."""
    zahl = _als_int_oder_none(wert)
    return f"{zahl:,}".replace(",", ".") if zahl is not None else "0"


def _mb_text(mb_wert: Any) -> str:
    """MB-Zahl deutsch mit zwei Nachkommastellen (157.5 -> "157,50 MB")."""
    try:
        return f"{float(mb_wert):.2f}".replace(".", ",") + " MB"
    except (TypeError, ValueError):
        return "0,00 MB"


# ── Die reinen, ohne Netz pruefbaren Funktionen (Namen sind Vorgabe) ──────

def rueckweg_text() -> str:
    """Der Rueckweg im Klartext — pCloud-Papierkorb statt endgueltig.

    Wird VOR der Operation genannt (Konsole und Changelog): Geloeschtes liegt
    im Papierkorb, ``trash_list`` zeigt es an, ``trash_restore`` legt es
    zurueck. Beide Aufrufe macht dieses Werkzeug nicht selbst.
    """
    return (
        "Rueckweg: pCloud legt geloeschte Dateien in den Papierkorb — sie sind "
        "nicht endgueltig weg. Anzeigen mit 'trash_list', zuruecklegen mit "
        "'trash_restore' (beides von Hand; dieses Werkzeug ruft 'trash_restore' nie auf)."
    )


def freigabe_mb(kandidaten: Sequence[Dict[str, Any]]) -> float:
    """Was die gegebenen Kandidaten zusammen freigeben — in MB, zwei Nachkommastellen.

    1 MB = 1e6 Byte (wie die pCloud-Anzeige). Kandidaten ohne brauchbare
    Groesse zaehlen als 0 — es wird nicht geschaetzt.
    """
    summe = 0
    for kandidat in kandidaten if isinstance(kandidaten, (list, tuple)) else []:
        if isinstance(kandidat, dict):
            summe += _als_int_oder_none(kandidat.get("size")) or 0
    return round(summe / 1_000_000, 2)


def manifest_zeile(kandidat: Dict[str, Any], zeit: str) -> Dict[str, Any]:
    """Die Manifest-Zeile einer Loeschung — genau die Felder aus dem Auftrag.

    ``art``, ``fileid``, ``name``, ``pfad``, ``size``, ``hash``, ``zeit``.
    Gebucht wird sie mit ``bewegen.manifest_anhaengen`` (keine zweite Logik);
    ``zeit`` kommt von aussen, damit die Zeile pruefbar ist.
    """
    kandidat = kandidat if isinstance(kandidat, dict) else {}
    return {
        "art": MANIFEST_ART,
        "fileid": _als_int_oder_none(kandidat.get("fileid")),
        "name": str(kandidat.get("name") or ""),
        "pfad": str(kandidat.get("pfad") or ""),
        "size": _als_int_oder_none(kandidat.get("size")),
        "hash": _hash_text(kandidat.get("hash")),
        "zeit": str(zeit or ""),
    }


def pruefe_kandidat(kandidat: Dict[str, Any], bericht_seite: Any) -> Dict[str, Any]:
    """Frische Gegenprobe: stimmen Groesse UND Pruefsumme noch?

    ``kandidat`` ist der Eintrag aus dem Bericht, ``bericht_seite`` die
    unmittelbar vorher live gelesenen Metadaten derselben Datei (aus einer
    ``listfolder``-Antwort). Verglichen werden **beide** Werte — ohne
    Pruefsumme gibt es keinen Inhaltsbeweis, ohne Groesse keinen zweiten
    Anker. Fehlt eine Seite oder passt etwas nicht, kommt ``ok: False`` mit
    deutschem Grund zurueck; geraten wird nichts.

    Rueckgabe: ``{"ok": bool, "grund": str}``.
    """
    if not isinstance(kandidat, dict):
        return {"ok": False, "grund": "Kandidat ist kein Bericht-Eintrag (kein Objekt)."}
    soll_size = _als_int_oder_none(kandidat.get("size"))
    soll_hash = _hash_text(kandidat.get("hash"))
    if soll_size is None:
        return {"ok": False, "grund": "Im Bericht fehlt die Groesse — ohne Groesse wird nicht geloescht."}
    if soll_hash is None:
        return {"ok": False, "grund": "Im Bericht fehlt die Pruefsumme (hash) — ohne Pruefsumme wird nicht geloescht."}
    if not isinstance(bericht_seite, dict):
        return {"ok": False, "grund": "Datei ist nicht mehr auffindbar — es wird nichts geloescht."}
    jetzt_size = _als_int_oder_none(bericht_seite.get("size"))
    jetzt_hash = _hash_text(bericht_seite.get("hash"))
    if jetzt_size is None:
        return {"ok": False, "grund": f"Die Groesse liest sich nicht ({bericht_seite.get('size')!r}) — Abbruch."}
    if jetzt_size != soll_size:
        return {
            "ok": False,
            "grund": f"Groesse weicht ab (Bericht {soll_size}, jetzt {jetzt_size}) — nichts geloescht.",
        }
    if jetzt_hash is None:
        return {"ok": False, "grund": "Die Pruefsumme (hash) liest sich nicht — Abbruch."}
    if jetzt_hash != soll_hash:
        return {
            "ok": False,
            "grund": f"Pruefsumme weicht ab (Bericht {soll_hash}, jetzt {jetzt_hash}) — nichts geloescht.",
        }
    return {"ok": True, "grund": "Groesse und Pruefsumme stimmen mit dem Bericht ueberein."}


def grenze_klemmen(wert: Any) -> int:
    """``--grenze`` hart auf 1…200 klemmen (Standard 25 bei unbrauchbarem Wert)."""
    zahl = _als_int_oder_none(wert)
    if zahl is None:
        return GRENZE_STANDARD
    return max(GRENZE_MIN, min(GRENZE_MAX, zahl))


# ── Den Bericht lesen und Kandidaten waehlen ──────────────────────────────

def _bericht_kandidaten(bericht: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Die Kandidatenliste des Berichts — robust, nie ein Absturz.

    Akzeptiert die Form von ``pcloud_duplikate.py``
    (``loesch_kandidaten.liste``) und als Notnagel eine blanke Liste.
    Nicht-Objekte werden still uebersprungen (sie sind keine Kandidaten).
    """
    if not isinstance(bericht, dict):
        return []
    block = bericht.get("loesch_kandidaten")
    if isinstance(block, dict):
        liste = block.get("liste")
    elif isinstance(block, list):
        liste = block
    else:
        liste = None
    ergebnis: List[Dict[str, Any]] = []
    for roh in liste if isinstance(liste, list) else []:
        if isinstance(roh, dict):
            ergebnis.append(dict(roh))
    return ergebnis


def _art_je_kennung(bericht: Dict[str, Any]) -> Dict[Any, str]:
    """Je Datei-Kennung die Art der Duplikatgruppe (fuer ``--art``)."""
    arten: Dict[int, str] = {}
    gruppen = bericht.get("gruppen") if isinstance(bericht, dict) else None
    for gruppe in gruppen if isinstance(gruppen, list) else []:
        if not isinstance(gruppe, dict):
            continue
        art = str(gruppe.get("art") or "")
        for kandidat in gruppe.get("loesch_kandidaten") or []:
            if not isinstance(kandidat, dict):
                continue
            kennung = _als_int_oder_none(kandidat.get("fileid"))
            if kennung is not None:
                arten[kennung] = art
    return arten


def _alle_dateien_je_kennung(bericht: Dict[str, Any]) -> Dict[Any, Dict[str, Any]]:
    """Jede im Bericht genannte Datei nach Kennung (Kandidat UND Mitglied).

    Damit laesst sich eine ueber ``--nur-dateien`` genannte Kennung einordnen:
    steht sie ueberhaupt im Bericht, und wenn ja in welchem Baum?
    """
    dateien: Dict[int, Dict[str, Any]] = {}
    for eintrag in _bericht_kandidaten(bericht):
        kennung = _als_int_oder_none(eintrag.get("fileid"))
        if kennung is not None:
            dateien.setdefault(kennung, eintrag)
    gruppen = bericht.get("gruppen") if isinstance(bericht, dict) else None
    for gruppe in gruppen if isinstance(gruppen, list) else []:
        if not isinstance(gruppe, dict):
            continue
        fuer_mitglieder = list(gruppe.get("mitglieder") or []) + list(gruppe.get("loesch_kandidaten") or [])
        for mitglied in fuer_mitglieder:
            if not isinstance(mitglied, dict):
                continue
            kennung = _als_int_oder_none(mitglied.get("fileid"))
            if kennung is not None:
                dateien.setdefault(kennung, mitglied)
    return dateien


def _brauchbar(kandidat: Dict[str, Any]) -> Optional[str]:
    """Grund, warum ein Kandidat NICHT loeschbar ist — oder ``None`` (brauchbar)."""
    if _als_int_oder_none(kandidat.get("fileid")) is None:
        return "ohne Dateikennung (fileid) im Bericht"
    if _als_int_oder_none(kandidat.get("size")) is None:
        return "ohne Groesse (size) im Bericht"
    if _hash_text(kandidat.get("hash")) is None:
        return "ohne Pruefsumme (hash) im Bericht"
    if str(kandidat.get("baum") or "") != BAUM_UPLOAD:
        return f"nicht im Upload-Baum (baum={kandidat.get('baum')!r}) — die Sammlung ist tabu"
    return None


def _nur_kennungen(nur_dateien: Any) -> List[int]:
    """``nur_dateien`` als Liste von Kennungen lesen (Zahl, Liste, ``None``)."""
    if nur_dateien is None:
        return []
    if isinstance(nur_dateien, (int, str)) and not isinstance(nur_dateien, bool):
        roh: Sequence[Any] = [nur_dateien]
    elif isinstance(nur_dateien, (list, tuple, set)):
        roh = list(nur_dateien)
    else:
        raise DuplikateLoeschFehler(
            "nur_dateien muss eine Liste von Dateikennungen sein (oder None)."
        )
    kennungen: List[int] = []
    for eintrag in roh:
        kennung = _als_int_oder_none(eintrag)
        if kennung is None:
            raise DuplikateLoeschFehler(f"nur_dateien enthaelt keine Zahl: {eintrag!r}")
        if kennung not in kennungen:
            kennungen.append(kennung)
    return kennungen


def kandidaten_waehlen(
    bericht: Dict[str, Any],
    art: str = ART_STANDARD,
    nur_dateien: Any = None,
    grenze: Any = GRENZE_STANDARD,
) -> Dict[str, Any]:
    """Die Loesch-Kandidaten eines Berichts waehlen — rein, ohne Netz.

    * ``art``: ``ueber_baeume`` | ``innerhalb_upload`` | ``alle`` (alles
      andere wird abgewiesen).
    * ``nur_dateien``: Liste von Dateikennungen (oder ``None``). Ist sie
      gesetzt, kommen **nur** diese Kennungen in Frage; Kennungen, die nicht
      im Bericht stehen ODER dort zur Sammlung gehoeren, landen in
      ``verweigert`` (der Aufrufer bricht dann ab).
    * ``grenze``: hoechstens so viele Kandidaten (hart geklemmt 1…200).

    Kandidaten aus der Sammlung werden **nie** gewaehlt, Kandidaten ohne
    Groesse/Pruefsumme ebenfalls nicht (letztere als ``uebersprungen``).

    Rueckgabe: ``{"kandidaten": [...], "uebersprungen": [...],
    "verweigert": [...], "rest": n}`` — ``rest`` ist die Zahl der
    brauchbaren Kandidaten, die die Grenze nicht mehr erreicht.
    """
    art = str(art or ART_STANDARD).strip() or ART_STANDARD
    if art not in ARTEN:
        raise DuplikateLoeschFehler(
            f"--art kennt {art!r} nicht — erlaubt sind: " + ", ".join(ARTEN) + "."
        )
    grenze = grenze_klemmen(grenze)
    bericht = bericht if isinstance(bericht, dict) else {}
    alle_liste = _bericht_kandidaten(bericht)
    nach_kennung = {
        _als_int_oder_none(k.get("fileid")): k
        for k in alle_liste
        if _als_int_oder_none(k.get("fileid")) is not None
    }
    bekannte = _alle_dateien_je_kennung(bericht)
    gruppen_art = _art_je_kennung(bericht)

    ausgewaehlt: List[Dict[str, Any]] = []
    uebersprungen: List[Dict[str, Any]] = []
    verweigert: List[Dict[str, Any]] = []

    def _grund_eintrag(kandidat: Dict[str, Any], grund: str) -> Dict[str, Any]:
        """Ein Eintrag fuer uebersprungen/verweigert — mit Kennung, Name, Grund."""
        return {
            "fileid": _als_int_oder_none(kandidat.get("fileid")),
            "name": str(kandidat.get("name") or ""),
            "pfad": str(kandidat.get("pfad") or ""),
            "baum": kandidat.get("baum"),
            "grund": grund,
        }

    kennungen = _nur_kennungen(nur_dateien)
    if kennungen:
        for kennung in kennungen:
            kandidat = nach_kennung.get(kennung)
            if kandidat is None:
                if kennung in bekannte:
                    verweigert.append(
                        {
                            "fileid": kennung,
                            "name": str(bekannte[kennung].get("name") or ""),
                            "pfad": str(bekannte[kennung].get("pfad") or ""),
                            "baum": bekannte[kennung].get("baum"),
                            "grund": "steht im Bericht, ist aber kein Loesch-Kandidat "
                                     "(nur Kopien im Upload-Baum sind Kandidaten — die Sammlung bleibt).",
                        }
                    )
                else:
                    verweigert.append(
                        {
                            "fileid": kennung,
                            "name": "",
                            "pfad": "",
                            "baum": None,
                            "grund": "Kennung steht nicht im Bericht — ohne Bericht kein Loeschen.",
                        }
                    )
                continue
            makel = _brauchbar(kandidat)
            if makel is not None:
                verweigert.append(_grund_eintrag(kandidat, f"verweigert: {makel}."))
                continue
            if art != ART_STANDARD and gruppen_art.get(kennung) != art:
                uebersprungen.append(
                    _grund_eintrag(
                        kandidat,
                        f"Gruppe ist {gruppen_art.get(kennung) or 'unbekannt'}, --art ist {art}.",
                    )
                )
                continue
            ausgewaehlt.append(dict(kandidat))
    else:
        for kandidat in alle_liste:
            kennung = _als_int_oder_none(kandidat.get("fileid"))
            if str(kandidat.get("baum") or "") != BAUM_UPLOAD:
                verweigert.append(
                    _grund_eintrag(
                        kandidat,
                        "Kandidat steht nicht im Upload-Baum — die Sammlung ist tabu.",
                    )
                )
                continue
            makel = _brauchbar(kandidat)
            if makel is not None:
                uebersprungen.append(_grund_eintrag(kandidat, makel))
                continue
            if art != ART_STANDARD and gruppen_art.get(kennung) != art:
                uebersprungen.append(
                    _grund_eintrag(
                        kandidat,
                        f"Gruppe ist {gruppen_art.get(kennung) or 'unbekannt'}, --art ist {art}.",
                    )
                )
                continue
            ausgewaehlt.append(dict(kandidat))

    rest = max(0, len(ausgewaehlt) - grenze)
    return {
        "kandidaten": ausgewaehlt[:grenze],
        "uebersprungen": uebersprungen,
        "verweigert": verweigert,
        "rest": rest,
    }


# ── Bericht laden ─────────────────────────────────────────────────────────

def bericht_laden(pfad: str) -> Tuple[Dict[str, Any], str]:
    """Den Bericht lesen. Rueckgabe: (Bericht, ausgeschriebener Pfad).

    Fehlt die Datei, ist sie unlesbar oder steht kein Objekt darin, gibt es
    eine deutsche Klartextmeldung (der Aufrufer beendet dann mit Exit 2) —
    es wird nie ein halber/geratener Bericht benutzt.
    """
    ausgeschrieben = os.path.abspath(os.path.expanduser(str(pfad)))
    if not os.path.exists(ausgeschrieben):
        raise DuplikateLoeschFehler(
            f"Bericht nicht gefunden: {pfad}\n"
            "Erst den Bericht bauen (nur lesend): "
            ".venv/Scripts/python ../tools/pcloud/pcloud_duplikate.py"
        )
    try:
        text = Path(ausgeschrieben).read_text(encoding="utf-8")
    except OSError as e:
        raise DuplikateLoeschFehler(
            f"Bericht nicht lesbar ({pfad}): {e.__class__.__name__}."
        ) from None
    try:
        daten = json.loads(text)
    except ValueError:
        raise DuplikateLoeschFehler(
            f"Bericht ist kein gueltiges JSON ({pfad}) — es wird nichts geloescht."
        ) from None
    if not isinstance(daten, dict):
        raise DuplikateLoeschFehler(
            f"Bericht ist kein Objekt ({pfad}) — es wird nichts geloescht."
        )
    return daten, ausgeschrieben


def kennungen_aus_datei(pfad: str) -> List[int]:
    """Eine Textdatei mit einer Dateikennung je Zeile lesen (``#`` = Kommentar).

    Jede unbrauchbare Zeile bricht mit Klartext ab (mit Zeilennummer) — eine
    halb gelesene Freigabeliste waere gefaehrlicher als keine.
    """
    ausgeschrieben = os.path.abspath(os.path.expanduser(str(pfad)))
    try:
        text = Path(ausgeschrieben).read_text(encoding="utf-8")
    except OSError as e:
        raise DuplikateLoeschFehler(
            f"--nur-dateien nicht lesbar ({pfad}): {e.__class__.__name__}."
        ) from None
    kennungen: List[int] = []
    for nummer, roh in enumerate(text.splitlines(), start=1):
        zeile = roh.split("#", 1)[0].strip()
        if not zeile:
            continue
        kennung = _als_int_oder_none(zeile)
        if kennung is None:
            raise DuplikateLoeschFehler(
                f"--nur-dateien: Zeile {nummer} ist keine Dateikennung: {roh.strip()!r} "
                "(eine Kennung je Zeile, Zahlen, '#'-Kommentar erlaubt)."
            )
        if kennung not in kennungen:
            kennungen.append(kennung)
    if not kennungen:
        raise DuplikateLoeschFehler(
            f"--nur-dateien enthaelt keine Kennung ({pfad}) — es wird nichts geloescht."
        )
    return kennungen


# ── Der eine abgesicherte API-Aufruf ──────────────────────────────────────

def _api_senden(
    methode: str,
    felder: Dict[str, Any],
    *,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> Dict[str, Any]:
    """Genau EIN pCloud-Aufruf — abgesichert durch die Positivliste.

    Erlaubt sind nur ``listfolder``, ``deletefile`` und ``trash_list``; alles
    andere wird abgewiesen, BEVOR etwas gesendet wird.
    """
    if methode not in ERLAUBTE_METHODEN:
        raise DuplikateLoeschFehler(
            f"Abgewiesen: '{methode}' steht nicht auf der Positivliste dieses "
            "Werkzeugs (" + ", ".join(ERLAUBTE_METHODEN) + ")."
        )
    geheimnis = bewegen._token_aus_quellen(token)
    if not geheimnis:
        raise DuplikateLoeschFehler(
            "pCloud ist nicht konfiguriert: PCLOUD_TOKEN fehlt "
            "(weder in der Umgebung noch in backend/.env)."
        )
    ziel_host = bewegen._host_aus_quellen(host)
    parameter = {name: wert for name, wert in felder.items() if wert is not None}
    parameter["auth"] = geheimnis
    url = f"https://{ziel_host}/{methode}"
    try:
        antwort = httpx.get(url, params=parameter, timeout=timeout)
    except Exception as e:
        # Nur der Klassenname — fremde Meldungen koennen die volle URL samt
        # Token enthalten.
        raise DuplikateLoeschFehler(f"pCloud nicht erreichbar ({e.__class__.__name__}).") from None
    if antwort.status_code != 200:
        raise DuplikateLoeschFehler(f"pCloud antwortete mit HTTP {antwort.status_code}.")
    try:
        daten = antwort.json()
    except Exception:
        raise DuplikateLoeschFehler("pCloud lieferte keine lesbare JSON-Antwort.") from None
    if not isinstance(daten, dict):
        raise DuplikateLoeschFehler("pCloud lieferte eine unerwartete Antwort.")
    if daten.get("result") != 0:
        klartext = bewegen._ohne_geheimnis(str(daten.get("error") or "ohne Fehlertext"), geheimnis)
        raise DuplikateLoeschFehler(f"pCloud meldet Fehler {daten.get('result')}: {klartext}")
    return daten


def _eintraege(daten: Dict[str, Any]) -> List[Dict[str, Any]]:
    """``metadata.contents`` robust auswerten — nie ein Absturz.

    Fehlt ``metadata``/``contents`` (leerer Ordner), ist das eine gueltige
    leere Liste; Nicht-Objekte werden still uebersprungen.
    """
    metadata = daten.get("metadata") if isinstance(daten, dict) else None
    inhalte = metadata.get("contents") if isinstance(metadata, dict) else None
    ergebnis: List[Dict[str, Any]] = []
    for roh in inhalte if isinstance(inhalte, list) else []:
        if not isinstance(roh, dict):
            continue
        ergebnis.append(
            {
                "name": str(roh.get("name") or ""),
                "ist_ordner": bool(roh.get("isfolder")),
                "fileid": _als_int_oder_none(roh.get("fileid")),
                "folderid": _als_int_oder_none(roh.get("folderid")),
                "size": _als_int_oder_none(roh.get("size")),
                "hash": _hash_text(roh.get("hash")),
            }
        )
    return ergebnis


def ordner_eintraege(
    folderid: Any,
    *,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> List[Dict[str, Any]]:
    """Eintraege EINES Ordners lesen (nur ``listfolder``) — Metadaten, keine Inhalte.

    Gebraucht wird das fuer die frische Gegenprobe vor jedem Loeschen: Name,
    Kennung, Groesse und Pruefsumme der Datei. Genau EIN Aufruf, kein
    tieferer Lauf.
    """
    ordner = _als_id(folderid, "folderid")
    daten = _api_senden(
        "listfolder", {"folderid": ordner}, token=token, host=host, timeout=timeout
    )
    return _eintraege(daten)


def papierkorb_zahl(
    *,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> int:
    """Wie viele Eintraege im pCloud-Papierkorb liegen — nur LESEND.

    Bewusst der einzige Papierkorb-Aufruf dieses Werkzeugs: ``trash_list``
    zeigt an, es holt nichts zurueck und loescht nichts.
    """
    daten = _api_senden("trash_list", {}, token=token, host=host, timeout=timeout)
    return len(_eintraege(daten))


class LivePruefer:
    """Liest den aktuellen Stand einer Datei frisch aus der pCloud.

    Nur ``listfolder``: Der Weg des Berichts (``Automatic Upload/Ordner/...``)
    wird vom Baum-Ordner aus nach unten gegangen; die Datei wird ueber ihre
    Kennung (``fileid``) gesucht. **Es wird nichts zwischengespeichert:** jede
    Gegenprobe liest die Ordner frisch, damit ``stand()`` unmittelbar vor dem
    Loeschen wirklich den aktuellen Stand der pCloud zeigt — auch fuer zwei
    Kandidaten im selben Ordner (ein Zwischenspeicher waere billiger, aber die
    Zusage „frische Gegenprobe vor JEDER Loeschung“ waere dann unwahr).
    """

    def __init__(
        self,
        bericht: Dict[str, Any],
        *,
        token: Optional[str] = None,
        host: Optional[str] = None,
        timeout: float = TIMEOUT_SEKUNDEN,
    ) -> None:
        self._bericht = bericht if isinstance(bericht, dict) else {}
        self._token = token
        self._host = host
        self._timeout = timeout

    def _inhalt(self, folderid: int) -> List[Dict[str, Any]]:
        """Ordnerinhalt — bei jeder Frage neu gelesen (kein Zwischenspeicher)."""
        return ordner_eintraege(
            folderid, token=self._token, host=self._host, timeout=self._timeout
        )

    def start_id(self, baum: str, erster_teil: str) -> Optional[int]:
        """Kennung des Baum-Ordners: aus dem Bericht, sonst per Name aus der Wurzel."""
        baeume = self._bericht.get("baeume")
        eintrag = baeume.get(baum) if isinstance(baeume, dict) else None
        kennung = _als_int_oder_none(eintrag.get("folderid") if isinstance(eintrag, dict) else None)
        if kennung is not None:
            return kennung
        gesucht = str(erster_teil or "").casefold()
        for vorhanden in self._inhalt(WURZEL_ID):
            if vorhanden["ist_ordner"] and vorhanden["name"].casefold() == gesucht:
                return vorhanden["folderid"]
        return None

    def stand(self, kandidat: Dict[str, Any]) -> Dict[str, Any]:
        """Aktuelle Metadaten der Datei — oder ``gefunden: False`` mit Grund.

        Rueckgabe bei Erfolg: ``{"gefunden": True, "size":…, "hash":…, "name":…}``.
        Es wird nichts angefasst und nichts geschrieben.
        """
        if not isinstance(kandidat, dict):
            return {"gefunden": False, "grund": "Kandidat ist kein Objekt."}
        kennung = _als_int_oder_none(kandidat.get("fileid"))
        if kennung is None:
            return {"gefunden": False, "grund": "Der Kandidat hat keine Dateikennung (fileid)."}
        pfad = str(kandidat.get("pfad") or "")
        teile = [teil for teil in pfad.split("/") if teil]
        if len(teile) < 2:
            return {
                "gefunden": False,
                "grund": f"Pfad {pfad!r} ist unbrauchbar (Baum-Ordner und Dateiname fehlen).",
            }
        aktuell = self.start_id(str(kandidat.get("baum") or ""), teile[0])
        if aktuell is None:
            return {
                "gefunden": False,
                "grund": f"Der Baum-Ordner {teile[0]!r} wurde nicht gefunden — Abbruch.",
            }
        for teil in teile[1:-1]:
            naechste = None
            for vorhanden in self._inhalt(aktuell):
                if vorhanden["ist_ordner"] and vorhanden["name"].casefold() == teil.casefold():
                    naechste = vorhanden["folderid"]
                    break
            if naechste is None:
                return {
                    "gefunden": False,
                    "grund": f"Ordner {teil!r} auf dem Weg zur Datei fehlt — Abbruch.",
                }
            aktuell = naechste
        for vorhanden in self._inhalt(aktuell):
            if not vorhanden["ist_ordner"] and vorhanden["fileid"] == kennung:
                return {
                    "gefunden": True,
                    "size": vorhanden["size"],
                    "hash": vorhanden["hash"],
                    "name": vorhanden["name"],
                }
        return {
            "gefunden": False,
            "grund": f"Datei {kennung} liegt nicht mehr in ihrem Ordner (oder wurde ersetzt) — Abbruch.",
        }


# ── Manifest: nur lesen (Idempotenz) und anhaengen (ueber das Nachbarmodul) ─

def _manifest_pfad(pfad: Any = None) -> Path:
    """Der Manifest-Pfad — Argument schlaegt Umgebung schlaegt Standard."""
    return bewegen.manifest_datei(pfad)


def manifest_ort_pruefen(pfad: Any = None) -> Path:
    """Der Manifest-Ort wird VOR allem anderen geprueft (nie ins Repo).

    Ohne diese Vorpruefung koennte der erste Loeschbefehl schon unterwegs
    sein, bevor die Buchung am Ort scheitert — genau das darf nicht passieren.
    Ein Fehler kommt als Klartext zurueck (der Aufrufer beendet mit Exit 2).
    """
    ziel = _manifest_pfad(pfad)
    try:
        bewegen._pruefe_manifest_ort(ziel)
    except bewegen.PCloudBewegungsFehler as problem:
        raise DuplikateLoeschFehler(str(problem)) from None
    return ziel


def schon_geloescht(pfad: Any = None) -> Set[int]:
    """Kennungen, die laut Manifest bereits als ``loeschen`` gebucht sind.

    Damit ist ein zweiter Lauf am selben Stand harmlos (idempotent): was schon
    im Papierkorb liegt, wird nicht noch einmal angefasst.
    """
    try:
        eintraege = bewegen.manifest_lesen(pfad)
    except bewegen.PCloudBewegungsFehler as problem:
        raise DuplikateLoeschFehler(str(problem)) from None
    kennungen: Set[int] = set()
    for eintrag in eintraege:
        if not isinstance(eintrag, dict) or str(eintrag.get("art") or "") != MANIFEST_ART:
            continue
        kennung = _als_int_oder_none(eintrag.get("fileid"))
        if kennung is not None:
            kennungen.add(kennung)
    return kennungen


def manifest_buchen(kandidat: Dict[str, Any], *, zeit: str, pfad: Any = None) -> Dict[str, Any]:
    """EINE Loeschung ins Manifest buchen — ueber ``manifest_anhaengen``.

    Es gibt bewusst keine zweite Manifest-Logik: Zeilenaufbau, Feldreihenfolge,
    Flush/fsync und die Repo-Pruefung kommen aus ``pcloud_bewegungen.py``.
    """
    zeile = manifest_zeile(kandidat, zeit)
    try:
        return bewegen.manifest_anhaengen(zeile, pfad=pfad)
    except bewegen.PCloudBewegungsFehler as problem:
        raise DuplikateLoeschFehler(str(problem)) from None


# ── Der Lauf ──────────────────────────────────────────────────────────────

def fuehre_aus(
    bericht: Dict[str, Any],
    auswahl: Dict[str, Any],
    *,
    wirklich: bool = False,
    manifest_pfad: Any = None,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> Dict[str, Any]:
    """Die gewaehlten Kandidaten loeschen — nur mit ``wirklich=True``.

    Trockenlauf (``wirklich=False``): es wird **nichts** gesendet, nur
    gezaehlt (auch keine Leseprobe — der Bericht ist die Grundlage).

    Echt: je Kandidat erst frisch gegenpruefen (Groesse UND Pruefsumme), dann
    ``deletefile``, dann **sofort** die Manifest-Zeile — nicht am Ende
    gesammelt, damit ein Absturz keine geloeschte Datei ohne Buchung
    hinterlaesst. Bei der ersten Abweichung bricht der ganze Lauf ab
    (``abbruch`` in der Rueckgabe): es wird nicht geraten und nichts
    "trotzdem" geloescht.
    """
    kandidaten = auswahl.get("kandidaten") if isinstance(auswahl, dict) else None
    kandidaten = list(kandidaten) if isinstance(kandidaten, list) else []
    rest = _als_int_oder_none(auswahl.get("rest")) if isinstance(auswahl, dict) else None
    ziel = _manifest_pfad(manifest_pfad)
    ergebnis: Dict[str, Any] = {
        "modus": "WIRKLICH" if wirklich else "TROCKENLAUF",
        "geprueft": 0,
        "geloescht": 0,
        "uebersprungen": 0,
        "fehler": 0,
        "mb": 0.0,
        "rest": rest or 0,
        "manifest": str(ziel),
        "abbruch": None,
        "zeilen": [],
    }
    if not kandidaten:
        return ergebnis
    if not wirklich:
        # Trockenlauf: nur rechnen, NICHTS senden.
        ergebnis["geprueft"] = len(kandidaten)
        ergebnis["mb"] = freigabe_mb(kandidaten)
        return ergebnis

    # Erst den Ort pruefen, dann die erste Datei anfassen: keine Loeschung
    # ohne moegliche Buchung.
    manifest_ort_pruefen(manifest_pfad)
    try:
        bereits = schon_geloescht(manifest_pfad)
    except DuplikateLoeschFehler as problem:
        # Ein unlesbares Manifest ist Grund zum Anhalten, nicht zum Weiterlaufen.
        ergebnis["fehler"] += 1
        ergebnis["abbruch"] = {"kandidat": None, "grund": str(problem)}
        return ergebnis
    pruefer = LivePruefer(bericht, token=token, host=host, timeout=timeout)
    for kandidat in kandidaten:
        kennung = _als_int_oder_none(kandidat.get("fileid"))
        if kennung in bereits:
            ergebnis["uebersprungen"] += 1
            ergebnis["zeilen"].append(f"  UEBERSPRUNGEN  {kandidat.get('name')} — steht schon als 'loeschen' im Manifest.")
            continue
        ergebnis["geprueft"] += 1
        try:
            lage = pruefer.stand(kandidat)
        except DuplikateLoeschFehler as problem:
            # Auch der Leseweg braucht einen Token und eine erreichbare pCloud:
            # fehlt eines davon, wird nichts geloescht und nichts gebucht.
            ergebnis["fehler"] += 1
            ergebnis["abbruch"] = {
                "kandidat": kandidat,
                "grund": f"Gegenprobe nicht moeglich: {problem}",
            }
            return ergebnis
        if not lage.get("gefunden"):
            ergebnis["abbruch"] = {
                "kandidat": kandidat,
                "grund": str(lage.get("grund") or "Datei nicht auffindbar — Abbruch."),
            }
            return ergebnis
        urteil = pruefe_kandidat(kandidat, lage)
        if not urteil["ok"]:
            ergebnis["abbruch"] = {"kandidat": kandidat, "grund": urteil["grund"]}
            return ergebnis
        try:
            _api_senden("deletefile", {"fileid": kennung}, token=token, host=host, timeout=timeout)
        except DuplikateLoeschFehler as problem:
            ergebnis["fehler"] += 1
            ergebnis["abbruch"] = {
                "kandidat": kandidat,
                "grund": f"pCloud hat das Loeschen abgelehnt: {problem}",
            }
            return ergebnis
        try:
            manifest_buchen(kandidat, zeit=_jetzt_iso(), pfad=manifest_pfad)
        except DuplikateLoeschFehler as problem:
            # Die Datei liegt im Papierkorb, die Buchung fehlt: laut melden und
            # anhalten. Ein bis zwei Haende voll solcher Zeilen sind von Hand
            # nachtragbar — stiller Weiterlauf waere es nicht.
            ergebnis["fehler"] += 1
            ergebnis["abbruch"] = {
                "kandidat": kandidat,
                "grund": "Datei geloescht, aber die Manifest-Zeile scheiterte: " + str(problem),
            }
            return ergebnis
        ergebnis["geloescht"] += 1
        ergebnis["mb"] = round(ergebnis["mb"] + (_als_int_oder_none(kandidat.get("size")) or 0) / 1_000_000, 2)
        ergebnis["zeilen"].append(
            f"  GELOESCHT (Papierkorb)  {kandidat.get('name')}  [fileid {kennung}]"
        )
    return ergebnis


def _kandidat_zeile(nummer: int, kandidat: Dict[str, Any]) -> str:
    """Eine Kandidatenzeile: Nummer, Name, Pfad, Kennung, Groesse."""
    size = _als_int_oder_none(kandidat.get("size"))
    return (
        f"  {nummer}. {kandidat.get('name')}  [{kandidat.get('pfad')}]"
        f"  (fileid {kandidat.get('fileid')}, {_mb_text(round((size or 0) / 1_000_000, 2))})"
    )


def _modus_zeile(wirklich: bool) -> str:
    """Der Modus unuebersehbar — auf der Konsole und in der Doku derselbe Wortlaut."""
    if wirklich:
        return "Modus: WIRKLICH — es wird geloescht (Papierkorb-Rueckweg moeglich)."
    return "Modus: TROCKENLAUF — es wird NICHTS gesendet (Loeschen erst mit --wirklich)."


def trocken_zeilen(
    berechnung: Dict[str, Any],
    *,
    bericht_pfad: str = "",
    stand: str = "",
    art: str = ART_STANDARD,
    grenze: int = GRENZE_STANDARD,
    auswahl: Optional[Dict[str, Any]] = None,
    papierkorb: Optional[int] = None,
    beispiele: int = BEISPIELE_STANDARD,
) -> List[str]:
    """Die Trockenlauf-Ausgabe als reine Zeilenliste (ohne Drucken, pruefbar).

    Zahlen zuerst: geprueft, geloescht, freigegebene MB, Rest — danach die
    ersten ``beispiele`` Kandidaten (Name + Pfad), der Modus und der Rueckweg.
    """
    auswahl = auswahl if isinstance(auswahl, dict) else {}
    kandidaten = auswahl.get("kandidaten") if isinstance(auswahl.get("kandidaten"), list) else []
    zeilen = [
        "pCloud-Duplikate loeschen — Papierkorb statt endgueltig, Trockenlauf ist der Standard",
        _modus_zeile(False),
        f"Bericht: {bericht_pfad} | Stand: {stand or 'unbekannt'} | Art: {art} | Grenze: {grenze}",
        (
            f"Geprueft (gewaehlte Kandidaten): {_zahl_de(berechnung.get('geprueft'))} | "
            f"Geloescht: {_zahl_de(berechnung.get('geloescht'))} | "
            f"Freigabe: {_mb_text(berechnung.get('mb'))} | Rest: {_zahl_de(berechnung.get('rest'))}"
        ),
    ]
    if papierkorb is not None:
        zeilen.append(f"Papierkorb: {_zahl_de(papierkorb)} Eintraege (nur gelesen, nichts zurueckgelegt).")
    anzeigen = max(0, int(beispiele or 0))
    if kandidaten:
        zeilen.append(f"Erste {min(anzeigen, len(kandidaten))} Kandidaten von {_zahl_de(len(kandidaten))}:")
        for nummer, kandidat in enumerate(kandidaten[:anzeigen], start=1):
            zeilen.append(_kandidat_zeile(nummer, kandidat))
        if len(kandidaten) > anzeigen:
            zeilen.append(f"  ... und {_zahl_de(len(kandidaten) - anzeigen)} weitere.")
    elif berechnung.get("geprueft"):
        zeilen.append("Keine Kandidaten ausgewaehlt — nichts zu tun.")
    zeilen.append(rueckweg_text())
    return zeilen


def ergebnis_zeilen(
    ergebnis: Dict[str, Any],
    *,
    art: str = ART_STANDARD,
    grenze: int = GRENZE_STANDARD,
    papierkorb: Optional[int] = None,
) -> List[str]:
    """Die Abschlusszeilen eines Laufs (rein, pruefbar)."""
    ergebnis = ergebnis if isinstance(ergebnis, dict) else {}
    wirklich = ergebnis.get("modus") == "WIRKLICH"
    zeilen = [
        (
            f"Ergebnis: geprueft {_zahl_de(ergebnis.get('geprueft'))}, "
            f"geloescht {_zahl_de(ergebnis.get('geloescht'))}, "
            f"uebersprungen {_zahl_de(ergebnis.get('uebersprungen'))}, "
            f"freigegeben {_mb_text(ergebnis.get('mb'))}, "
            f"Fehler {_zahl_de(ergebnis.get('fehler'))}, Rest {_zahl_de(ergebnis.get('rest'))}."
        ),
        f"Art: {art} | Grenze: {grenze}",
        _modus_zeile(wirklich),
    ]
    if papierkorb is not None:
        zeilen.append(f"Papierkorb: {_zahl_de(papierkorb)} Eintraege (nur gelesen).")
    if wirklich:
        zeilen.append(f"Manifest: {ergebnis.get('manifest')}")
    for zeile in ergebnis.get("zeilen") if isinstance(ergebnis.get("zeilen"), list) else []:
        zeilen.append(zeile)
    abbruch = ergebnis.get("abbruch")
    if isinstance(abbruch, dict):
        kandidat = abbruch.get("kandidat") if isinstance(abbruch.get("kandidat"), dict) else {}
        zeilen.append("ABBRUCH: " + str(abbruch.get("grund") or "unbekannter Grund") + _datei_hinweis(kandidat))
        zeilen.append("Es wird nichts weiter geloescht.")
    zeilen.append(rueckweg_text())
    return zeilen


def _datei_hinweis(kandidat: Any) -> str:
    """' (Datei ...)' anhaengen — nur wenn wirklich eine Datei benannt ist."""
    if not isinstance(kandidat, dict) or (kandidat.get("fileid") is None and not kandidat.get("name")):
        return ""
    return f" (Datei {kandidat.get('name')!r}, fileid {kandidat.get('fileid')})"


# ── Kommandozeile ─────────────────────────────────────────────────────────

def _zerleger_bauen() -> argparse.ArgumentParser:
    """Die Kommandozeile — Trockenlauf ist der Standard, ``--wirklich`` schaltet frei."""
    zerleger = argparse.ArgumentParser(
        prog="pcloud_duplikate_loeschen.py",
        description=(
            "Loescht die Loesch-Kandidaten aus dem Duplikate-Bericht (nur Kopien "
            "im Upload-Baum) in den pCloud-Papierkorb. TROCKENLAUF ist der "
            "Standard; ohne --wirklich wird nichts gesendet."
        ),
    )
    zerleger.add_argument(
        "--bericht",
        dest="bericht",
        default=os.environ.get(UMGEBUNG_BERICHT, "") or STANDARD_BERICHT,
        help=f"Berichtsdatei aus pcloud_duplikate.py (Standard {STANDARD_BERICHT}, "
        f"auch per Umgebungsvariable {UMGEBUNG_BERICHT})",
    )
    zerleger.add_argument(
        "--wirklich",
        dest="wirklich",
        action="store_true",
        help="schaltet das Loeschen frei; ohne diesen Schalter reiner Trockenlauf",
    )
    zerleger.add_argument(
        "--nur-dateien",
        dest="nur_dateien",
        default=None,
        help="Textdatei mit einer Dateikennung je Zeile ('#'-Kommentar erlaubt) — "
        "engt den Lauf auf genau diese Kennungen ein",
    )
    zerleger.add_argument(
        "--art",
        dest="art",
        default=ART_STANDARD,
        help="ueber_baeume | innerhalb_upload | alle (Standard " + ART_STANDARD + ")",
    )
    zerleger.add_argument(
        "--grenze",
        dest="grenze",
        type=int,
        default=GRENZE_STANDARD,
        help=f"hoechstens so viele Loeschungen (Standard {GRENZE_STANDARD}, geklemmt "
        f"{GRENZE_MIN}…{GRENZE_MAX})",
    )
    zerleger.add_argument(
        "--manifest",
        dest="manifest",
        default=None,
        help=f"Manifestdatei (Standard {bewegen.STANDARD_MANIFEST}, nie im Repo)",
    )
    zerleger.add_argument(
        "--papierkorb",
        dest="papierkorb",
        action="store_true",
        help="im Trockenlauf zusaetzlich 'trash_list' LESEND aufrufen und die Zahl "
        "der Papierkorb-Eintraege nennen",
    )
    zerleger.add_argument(
        "--beispiele",
        dest="beispiele",
        type=int,
        default=BEISPIELE_STANDARD,
        help=f"wie viele Kandidaten die Konsole nennt (Standard {BEISPIELE_STANDARD})",
    )
    return zerleger


def main(argv: Optional[List[str]] = None) -> int:
    """Kommandozeilen-Teil: Bericht lesen, Kandidaten waehlen, Trockenlauf oder echt."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = _zerleger_bauen().parse_args(argv)
    art = str(args.art or "").strip() or ART_STANDARD
    grenze = grenze_klemmen(args.grenze)
    try:
        if art not in ARTEN:
            raise DuplikateLoeschFehler(
                f"--art kennt {art!r} nicht — erlaubt sind: " + ", ".join(ARTEN) + "."
            )
        # Der Manifest-Ort wird VOR allem anderen geprueft — auch im Trockenlauf.
        bewegen_ziel = manifest_ort_pruefen(args.manifest)
        bericht, bericht_pfad = bericht_laden(args.bericht)
        nur_dateien = (
            kennungen_aus_datei(args.nur_dateien) if args.nur_dateien not in (None, "") else None
        )
        auswahl = kandidaten_waehlen(bericht, art=art, nur_dateien=nur_dateien, grenze=grenze)
    except DuplikateLoeschFehler as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    if auswahl["verweigert"]:
        print("VERWEIGERT — es wird nichts geloescht:", file=sys.stderr)
        for eintrag in auswahl["verweigert"]:
            print(
                f"  fileid {eintrag.get('fileid')} ({eintrag.get('name')!r}): {eintrag.get('grund')}",
                file=sys.stderr,
            )
        print(rueckweg_text(), file=sys.stderr)
        return 2

    papierkorb_zahl_wert: Optional[int] = None
    if args.papierkorb:
        try:
            papierkorb_zahl_wert = papierkorb_zahl()
        except DuplikateLoeschFehler as problem:
            print(f"Fehler: {problem}", file=sys.stderr)
            return 2

    stand = str(bericht.get("stand") or "") if isinstance(bericht, dict) else ""
    if not auswahl["kandidaten"]:
        print("pCloud-Duplikate loeschen — Trockenlauf ist der Standard")
        print(_modus_zeile(bool(args.wirklich)))
        print(f"Bericht: {bericht_pfad} | Stand: {stand or 'unbekannt'} | Art: {art} | Grenze: {grenze}")
        if args.papierkorb:
            print(f"Papierkorb: {_zahl_de(papierkorb_zahl_wert)} Eintraege (nur gelesen).")
        print(
            "Keine Kandidaten zu loeschen — nichts zu tun "
            f"(geloescht: 0, Freigabe: {_mb_text(0)})."
        )
        print(rueckweg_text())
        return 0

    if not args.wirklich:
        ergebnis = fuehre_aus(bericht, auswahl, wirklich=False)
        for zeile in trocken_zeilen(
            ergebnis,
            bericht_pfad=bericht_pfad,
            stand=stand,
            art=art,
            grenze=grenze,
            auswahl=auswahl,
            papierkorb=papierkorb_zahl_wert,
            beispiele=args.beispiele,
        ):
            print(zeile)
        if auswahl["uebersprungen"]:
            print(f"(uebersprungen: {_zahl_de(len(auswahl['uebersprungen']))} — siehe --art/--nur-dateien)")
        print("Trockenlauf beendet — es wurde nichts gesendet und nichts gebucht.")
        return 0

    print(f"Manifest: {bewegen_ziel}")
    print(_modus_zeile(True))
    ergebnis = fuehre_aus(
        bericht, auswahl, wirklich=True, manifest_pfad=args.manifest
    )
    for zeile in ergebnis_zeilen(ergebnis, art=art, grenze=grenze, papierkorb=papierkorb_zahl_wert):
        print(zeile)
    return 2 if isinstance(ergebnis.get("abbruch"), dict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
