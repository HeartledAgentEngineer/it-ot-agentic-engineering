"""pCloud-Duplikate per Pruefsumme — Upload-Baum gegen Sebastians Sammlung.

Wozu dieses Werkzeug (Auftrag 27.09.2026):
    Der Ordner ``Automatic Upload`` sammelt die Handy-Uploads, die Sammlung
    ``Bilder & Videos`` ist Sebastians gewachsene, einsortierte Struktur.
    Enthalten sind sehr wahrscheinlich dieselben Fotos — einmal als
    Upload-Kopie, einmal als Original. Der NAME taugt dafuer nicht als Beweis
    (Handy-Namen wie ``059956_2024-08-09_17-14-43_96.jpg``, Umbenennungen,
    WhatsApp-Empfang); pCloud liefert zu jeder Datei eine eigene Pruefsumme
    (``hash``, live geprueft 27.09.2026: 19-stellige Zahl). Gleiche Groesse
    UND gleicher Hash heisst: gleicher Inhalt. Dieses Werkzeug stellt beide
    Baeume gegenueber und liefert eine belastbare Liste, damit Sebastian
    selbst entscheiden kann, was geloescht wird.

Was dieses Werkzeug bewusst NICHT tut:
    * **Kein Loeschen, nirgends.** Es gibt in dieser Datei keinen Entfernungs-
      Befehl, keinen Papierkorb-Weg und keinen Schalter dafuer.
    * **Kein Herunterladen von Dateiinhalten** — gelesen werden nur Metadaten
      (Name, Groesse, Hash, Zeitstempel). Kein Vorschaubild, kein Datei-Inhalt.
    * **Kein Schreiben in die pCloud**: einzige erlaubte API-Methode ist
      ``listfolder`` (Positivliste ``ERLAUBTE_METHODEN``); alles andere wird
      abgewiesen, BEVOR etwas gesendet wird.
    * **Kein rekursiver Lauf ueber die Wurzel**: die Wurzel wird EINMAL
      gelesen, um die Kennungen der zwei Zielordner zu finden. Gescannt
      werden ausschliesslich ``Automatic Upload`` und ``Bilder & Videos``.

Sparsamkeit (so gebaut, weil die pCloud ein fremdes System ist):
    * Jeder Ordner wird genau EINMAL gelesen (Warteschlange + ``gesehen``-
      Menge): keine Wiederholung, keine Retry-Schleife, kein Doppelaufruf.
    * **Tiefenbegrenzung** (``--tiefe``, Standard 8) und ein **Ordner-Budget**
      (``--ordner-max``, Standard 2000). Was nicht gelesen wurde, steht
      ehrlich als ``abgebrochen: true`` und ``offen_gelassen: n`` im Bericht —
      es wird nicht stillschweigend weggelassen.

Loesch-Regel (Kandidat):
    Vorgeschlagen werden **immer nur Kopien im Baum ``upload``**, **nie** die
    Sammlung. Ueber die Baeume hinweg ist jede Upload-Kopie ein Kandidat
    (das Sammlungs-Original bleibt). Innerhalb des Upload-Baums bleibt EINE
    Kopie stehen (der Kandidat sind die weiteren). Innerhalb der Sammlung
    gibt es **gar keine** Kandidaten — dort entscheidet Sebastian selbst.
    Geloescht wird von diesem Werkzeug nichts; es nennt nur Kandidaten.

Ausgabe (JSON, Standard ``~/foto_sortierung/duplikate.json``, NIE im Repo):
    ``stand`` (ISO mit Zonenversatz), ``trocken: true``, ``tiefe_grenze``,
    ``baeume`` (je Baum: Zahlen, erreichte Tiefe, Knotenzahl, Aufrufe,
    Abbrueche), ``gruppen`` (je Gruppe: ``size``, ``hash``, ``anzahl``,
    ``art`` = ``ueber_baeume`` | ``innerhalb_upload`` | ``innerhalb_sammlung``,
    ``mitglieder`` mit ``fileid, name, pfad, baum, created, modified`` und
    ``loesch_kandidaten``), ``loesch_kandidaten`` (vollstaendige Liste mit
    Groesse/Hash) und ``zusammenfassung``:
      * ``gescannte_dateien`` je Baum und gesamt,
      * ``duplikatgruppen``, ``betroffene_dateien``,
      * ``mb_alle_kopien`` (alle Kopien zusammen), ``mb_freigabe_kandidaten``
        (was frei wuerde, wenn nur die Kandidaten geloescht werden),
      * getrennt: ``ueber_baeume`` (Upload-Kopie gegen Sammlungs-Original)
        und ``innerhalb`` (``upload`` / ``sammlung``).

Konsole:
    Nur Zahlen und die ersten ``--beispiele`` (Standard 5) Gruppen mit Namen —
    die vollstaendige Liste steht in der JSON-Datei. Die Loesch-Kandidaten
    werden ausdruecklich gekennzeichnet (``LOESCH-KANDIDAT``), immer auf der
    Upload-Seite.

Aufruf (nur lesend; der Token kommt aus der Umgebung oder ``backend/.env``):
    cd backend
    .venv/Scripts/python ../tools/pcloud/pcloud_duplikate.py
    .venv/Scripts/python ../tools/pcloud/pcloud_duplikate.py --tiefe 8 --beispiele 5
    .venv/Scripts/python ../tools/pcloud/pcloud_duplikate.py --ohne-sammlung
    .venv/Scripts/python ../tools/pcloud/pcloud_duplikate.py --quelle ~/foto_sortierung/duplikate.json

Rueckgabewerte: 0 = Bericht geschrieben; 2 = Bedien-/Konfigurationsfehler
(fehlender Token, fehlende Zielordner, Ausgabepfad im Repo, pCloud-Fehler).

Der Token ist ein Geheimnis: Er wird gelesen, aber nie ausgegeben, nie
geloggt und steht in keiner Datei, die dieses Modul schreibt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# EU-Rechenzentrum des Kontos. NICHT mit api.pcloud.com (US) verwechseln —
# dort gilt der Token nicht.
STANDARD_HOST = "eapi.pcloud.com"

# Ein Aufruf soll schnell scheitern, statt minutenlang zu haengen. Eine
# listfolder-Antwort kann gross sein (live: 6.483 Eintraege in einem Ordner).
TIMEOUT_SEKUNDEN = 30.0

# Standard-Ablage des Berichts: im Benutzerverzeichnis, niemals im Repo.
STANDARD_AUSGABE = "~/foto_sortierung/duplikate.json"
UMGEBUNG_AUSGABE = "PCLOUD_DUPLIKATE_ZIEL"

# Die beiden Baeume, die verglichen werden. Der Upload-Baum traegt die Kopien,
# die Sammlung die Originale.
BAUM_UPLOAD = "upload"
BAUM_SAMMLUNG = "sammlung"
ORDNER_UPLOAD = "Automatic Upload"
ORDNER_SAMMLUNG = "Bilder & Videos"

# Grenzen gegen einen ungebremsten Lauf (Sparsamkeit, siehe Modul-Docstring).
MAX_TIEFE_STANDARD = 8
ORDNER_MAX_STANDARD = 2000

# Positivliste der API-Methoden: NUR listfolder (Metadaten lesen). Waere hier
# ein anderer Aufruf dabei, waere die Nur-Lesen-Zusage dieses Werkzeugs
# gebrochen — Aenderungen an dieser Liste sind eine bewusste Entscheidung,
# kein Versehen.
ERLAUBTE_METHODEN = ("listfolder",)

# backend/.env des Projekts — Fallback-Quelle fuer Token und Host.
ENV_DATEI = Path(__file__).resolve().parents[2] / "backend" / ".env"

# Wurzelkennung der pCloud.
WURZEL_ID = 0


class DuplikateFehler(Exception):
    """Fehler beim Duplikate-Lauf — Klartext fuer den Nutzer.

    Enthaelt nie den Token (siehe ``_ohne_geheimnis``).
    """


# ── Kleine Helfer ──────────────────────────────────────────────────────────

def _ohne_geheimnis(text: str, token: str) -> str:
    """Den Token aus einem Text entfernen, falls er hineingeraten ist.

    Letzte Verteidigungslinie: Selbst wenn eine fremde Meldung den Token
    enthielte, wird er durch ``***`` ersetzt, bevor der Text sichtbar wird.
    """
    if token and token in text:
        return text.replace(token, "***")
    return text


def _jetzt_iso() -> str:
    """Aktuelle Zeit als ISO-Text MIT Zonenversatz (z. B. 2026-09-27T05:12:34+02:00)."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _als_int_oder_none(wert: Any) -> Optional[int]:
    """Zahl tolerant lesen — fehlende/unbrauchbare Werte werden ehrlich None.

    Ein kaputter Wert aus einer API-Antwort darf keinen Absturz ausloesen;
    ``None`` ist die sichtbar harmlose Variante (und wird mitgezaehlt).
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
        raise DuplikateFehler(f"{feld} fehlt oder ist keine Zahl: {wert!r}")
    return zahl


def _hash_text(wert: Any) -> Optional[str]:
    """Pruefsumme als Vergleichstext (``None``, wenn keine brauchbare da ist).

    pCloud liefert den Hash live als 19-stellige ZAHL (z. B.
    6906308981406561991). Fuer den Vergleich wird er als Text behandelt —
    so ist dieselbe Pruefsumme auch dann gleich, wenn ein Server sie einmal
    als Text liefert.
    """
    if wert is None:
        return None
    text = str(wert).strip()
    return text or None


def _mb_de(bytes_wert: float) -> str:
    """Byte-Zahl deutsch als MB (1 MB = 1e6, wie die pCloud-Anzeige)."""
    return f"{bytes_wert / 1_000_000:.1f}".replace(".", ",") + " MB"


def _zahl_de(wert: Any) -> str:
    """Ganzzahl deutsch mit Tausenderpunkt (1234 -> "1.234")."""
    try:
        return f"{int(wert):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


# ── Token und Host (nie ausgeben!) ────────────────────────────────────────

def _werte_aus_env_datei(env_pfad: Path) -> Dict[str, str]:
    """PCLOUD_TOKEN/PCLOUD_HOST aus einer .env lesen — Werte NIE ausgeben."""
    werte: Dict[str, str] = {}
    if not env_pfad.exists():
        return werte
    try:
        for zeile in env_pfad.read_text(encoding="utf-8").splitlines():
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#") or "=" not in zeile:
                continue
            schluessel, wert = zeile.split("=", 1)
            if schluessel.strip() in ("PCLOUD_TOKEN", "PCLOUD_HOST"):
                werte[schluessel.strip()] = wert.strip().strip('"').strip("'")
    except OSError:
        return werte
    return werte


def _token_aus_quellen(token: Optional[str] = None) -> str:
    """Token aus Parameter, Umgebung oder backend/.env — in dieser Reihenfolge."""
    if token is not None:
        return token.strip()
    wert = (os.environ.get("PCLOUD_TOKEN") or "").strip()
    if wert:
        return wert
    return _werte_aus_env_datei(ENV_DATEI).get("PCLOUD_TOKEN", "").strip()


def _host_aus_quellen(host: Optional[str] = None) -> str:
    """Host aus Parameter, Umgebung oder backend/.env (Standard: EU-Host)."""
    if host is not None:
        roh = host
    else:
        roh = (
            (os.environ.get("PCLOUD_HOST") or "").strip()
            or _werte_aus_env_datei(ENV_DATEI).get("PCLOUD_HOST", "").strip()
            or STANDARD_HOST
        )
    return roh.split("://")[-1].strip().strip("/") or STANDARD_HOST


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

    Erlaubt ist nur ``listfolder``. Jede andere Methode wird abgewiesen,
    BEVOR etwas gesendet wird.
    """
    if methode not in ERLAUBTE_METHODEN:
        raise DuplikateFehler(
            f"Abgewiesen: '{methode}' steht nicht auf der Positivliste dieses "
            "Werkzeugs (" + ", ".join(ERLAUBTE_METHODEN) + ")."
        )
    geheimnis = _token_aus_quellen(token)
    if not geheimnis:
        raise DuplikateFehler(
            "pCloud ist nicht konfiguriert: PCLOUD_TOKEN fehlt "
            "(weder in der Umgebung noch in backend/.env)."
        )
    ziel_host = _host_aus_quellen(host)
    parameter = {name: wert for name, wert in felder.items() if wert is not None}
    parameter["auth"] = geheimnis
    url = f"https://{ziel_host}/{methode}"
    try:
        antwort = httpx.get(url, params=parameter, timeout=timeout)
    except Exception as e:
        # Nur der Klassenname — fremde Meldungen koennen die volle URL samt
        # Token enthalten.
        raise DuplikateFehler(
            f"pCloud nicht erreichbar ({e.__class__.__name__})."
        ) from None
    if antwort.status_code != 200:
        raise DuplikateFehler(f"pCloud antwortete mit HTTP {antwort.status_code}.")
    try:
        daten = antwort.json()
    except Exception:
        raise DuplikateFehler("pCloud lieferte keine lesbare JSON-Antwort.") from None
    if not isinstance(daten, dict):
        raise DuplikateFehler("pCloud lieferte eine unerwartete Antwort.")
    if daten.get("result") != 0:
        klartext = _ohne_geheimnis(str(daten.get("error") or "ohne Fehlertext"), geheimnis)
        raise DuplikateFehler(f"pCloud meldet Fehler {daten.get('result')}: {klartext}")
    return daten


# ── Ordner lesen und Eintraege robust auswerten ───────────────────────────

def _eintraege_aus_antwort(daten: Dict[str, Any]) -> List[Dict[str, Any]]:
    """``metadata.contents`` robust auswerten — nie ein Absturz.

    Fehlt ``metadata`` oder ``contents`` (leerer Ordner kommt ohne sie), ist
    das eine gueltige leere Liste. Nicht-Objekte in der Liste werden als
    ``unbrauchbar`` markiert und gezaehlt, nicht geworfen.
    """
    metadata = daten.get("metadata") if isinstance(daten, dict) else None
    inhalte = metadata.get("contents") if isinstance(metadata, dict) else None
    ergebnis: List[Dict[str, Any]] = []
    for roh in inhalte if isinstance(inhalte, list) else []:
        if not isinstance(roh, dict):
            ergebnis.append({"unbrauchbar": True})
            continue
        ergebnis.append(
            {
                "unbrauchbar": False,
                "name": str(roh.get("name") or ""),
                "ist_ordner": bool(roh.get("isfolder")),
                "fileid": _als_int_oder_none(roh.get("fileid")),
                "folderid": _als_int_oder_none(roh.get("folderid")),
                "size": _als_int_oder_none(roh.get("size")),
                "hash": roh.get("hash"),
                "created": roh.get("created"),
                "modified": roh.get("modified"),
                "parentfolderid": _als_int_oder_none(roh.get("parentfolderid")),
            }
        )
    return ergebnis


def ordner_roh(
    folderid: Any,
    *,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> List[Dict[str, Any]]:
    """Eintraege EINES Ordners lesen — genau EIN ``listfolder``-Aufruf.

    Kein tieferer Lauf, kein zweiter Aufruf, keine Wiederholung.
    """
    ordner = _als_id(folderid, "folderid")
    daten = _api_senden(
        "listfolder", {"folderid": ordner}, token=token, host=host, timeout=timeout
    )
    return _eintraege_aus_antwort(daten)


def _finde_ordner(eintraege: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
    """Einen Ordner in der Wurzel per Name suchen — klare Meldung, wenn nicht.

    Namen werden ohne Gross-/Kleinschreibung verglichen (Umlaute/Leerzeichen
    muessen aber stimmen — geraten wird nichts).
    """
    gesucht = str(name or "").strip().casefold()
    for eintrag in eintraege:
        if eintrag.get("unbrauchbar") or not eintrag.get("ist_ordner"):
            continue
        if eintrag["name"].casefold() == gesucht:
            if eintrag.get("folderid") is None:
                raise DuplikateFehler(
                    f"Ordner '{name}' hat keine brauchbare Kennung (folderid) — "
                    "es wird nichts gelesen."
                )
            return eintrag
    raise DuplikateFehler(
        f"Ordner '{name}' wurde in der pCloud-Wurzel nicht gefunden — "
        "es wurde nur die Wurzel gelesen, sonst nichts."
    )


# ── Baum scannen (nur listfolder, jeder Ordner genau einmal) ──────────────

def baum_scannen(
    baum: str,
    start_id: Any,
    *,
    ordner_name: str = "",
    max_tiefe: int = MAX_TIEFE_STANDARD,
    ordner_max: int = ORDNER_MAX_STANDARD,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> Dict[str, Any]:
    """Einen Baum rekursiv per ``listfolder`` lesen — nur Metadaten.

    ``max_tiefe``: Der Startordner liegt auf Tiefe 0; gelesen werden Ordner
    bis einschliesslich Tiefe ``max_tiefe``. Unterordner darunter werden
    gezaehlt (``uebersprungen_tiefe``), aber nicht mehr gelesen.

    ``ordner_max``: Obergrenze der Ordner-Leseaufrufe fuer diesen Baum. Ist
    sie erschoepft, bricht der Lauf ehrlich ab (``abgebrochen: true``,
    ``offen_gelassen: n``) — statt endlos weiterzulesen.

    Rueckgabe: ``baum``, ``ordner_name``, ``folderid``, ``dateien`` (Liste von
    Mitgliedern mit ``fileid, name, pfad, baum, size, hash, created,
    modified``) und ``kennzahlen`` (Zahlen inkl. Knotenzahl und erreichte
    Tiefe).
    """
    start = _als_id(start_id, "folderid")
    grenze = max(0, int(max_tiefe))
    budget = max(1, int(ordner_max))
    wurzelname = str(ordner_name or "").strip() or baum

    gesehen: set = set()
    warteschlange: deque = deque([(start, 0, wurzelname)])
    dateien: List[Dict[str, Any]] = []
    zahlen: Dict[str, Any] = {
        "ordner_gelesen": 0,
        "ordner_gesehen": 0,
        "dateien": 0,
        "knoten": 0,
        "tiefe_erreicht": 0,
        "tiefe_grenze": grenze,
        "aufrufe": 0,
        "abgebrochen": False,
        "offen_gelassen": 0,
        "uebersprungen_tiefe": 0,
        "wiederholte_ordner": 0,
        "ohne_hash": 0,
        "ohne_groesse": 0,
        "ohne_kennung": 0,
        "kaputte_eintraege": 0,
    }

    while warteschlange:
        kennung, tiefe, pfad = warteschlange.popleft()
        if kennung in gesehen:
            # Sicherheitsnetz gegen einen Ordner, der zweimal auftaucht (oder
            # einen Zyklus): KEIN zweiter Leseaufruf.
            zahlen["wiederholte_ordner"] += 1
            continue
        if zahlen["ordner_gelesen"] >= budget:
            zahlen["abgebrochen"] = True
            zahlen["offen_gelassen"] = len(warteschlange) + 1
            break
        gesehen.add(kennung)
        zahlen["ordner_gelesen"] += 1
        zahlen["aufrufe"] += 1
        zahlen["tiefe_erreicht"] = max(zahlen["tiefe_erreicht"], tiefe)

        for eintrag in ordner_roh(kennung, token=token, host=host, timeout=timeout):
            if eintrag.get("unbrauchbar"):
                zahlen["kaputte_eintraege"] += 1
                continue
            teil = eintrag["name"]
            if eintrag["ist_ordner"]:
                if eintrag["folderid"] is None:
                    zahlen["kaputte_eintraege"] += 1
                    continue
                if tiefe + 1 > grenze:
                    zahlen["uebersprungen_tiefe"] += 1
                    continue
                warteschlange.append((eintrag["folderid"], tiefe + 1, f"{pfad}/{teil}"))
                zahlen["ordner_gesehen"] += 1
                continue
            # Datei: Metadaten uebernehmen, fehlende Felder ehrlich None+Zaehler.
            if eintrag["fileid"] is None:
                zahlen["ohne_kennung"] += 1
            if eintrag["size"] is None:
                zahlen["ohne_groesse"] += 1
            if _hash_text(eintrag["hash"]) is None:
                zahlen["ohne_hash"] += 1
            dateien.append(
                {
                    "fileid": eintrag["fileid"],
                    "name": teil,
                    "pfad": f"{pfad}/{teil}",
                    "baum": baum,
                    "size": eintrag["size"],
                    "hash": eintrag["hash"],
                    "created": eintrag["created"],
                    "modified": eintrag["modified"],
                }
            )
            zahlen["dateien"] += 1

    zahlen["knoten"] = zahlen["ordner_gelesen"] + zahlen["dateien"]
    return {
        "baum": baum,
        "ordner_name": wurzelname,
        "folderid": start,
        "dateien": dateien,
        "kennzahlen": zahlen,
    }


# ── Gruppieren und Kandidaten waehlen ─────────────────────────────────────

def gruppen_bilden(dateien: List[Dict[str, Any]]) -> Dict[Tuple[int, str], List[Dict[str, Any]]]:
    """Dateien nach ``(size, hash)`` gruppieren.

    Dateien ohne brauchbare Groesse oder ohne Pruefsumme werden NICHT
    gruppiert (sie werden im Bericht getrennt gezaehlt) — ohne Pruefsumme
    gibt es keinen Inhaltsbeweis.
    """
    gruppen: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
    for datei in dateien:
        groesse = _als_int_oder_none(datei.get("size"))
        hashwert = _hash_text(datei.get("hash"))
        if groesse is None or hashwert is None:
            continue
        gruppen.setdefault((groesse, hashwert), []).append(datei)
    return gruppen


def _mitglied_sortierschluessel(mitglied: Dict[str, Any]) -> Tuple[Any, ...]:
    """Feste Reihenfolge: Upload zuerst, dann Pfad, dann Kennung."""
    return (
        0 if mitglied.get("baum") == BAUM_UPLOAD else 1,
        str(mitglied.get("pfad") or "").casefold(),
        _als_int_oder_none(mitglied.get("fileid")) or 0,
    )


def kandidaten_waehlen(mitglieder: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Loesch-Kandidaten einer Gruppe: IMMER nur Kopien im Baum ``upload``.

    * Gruppe ueber die Baeume hinweg (Upload + Sammlung): jede Upload-Kopie
      ist Kandidat — das Sammlungs-Original bleibt.
    * Gruppe nur im Upload-Baum: die weiteren Kopien sind Kandidaten, EINE
      bleibt stehen (sonst waere die Datei ganz weg).
    * Gruppe nur in der Sammlung: KEINE Kandidaten — die Sammlung ist tabu.
    """
    upload = [m for m in mitglieder if m.get("baum") == BAUM_UPLOAD]
    sammlung = [m for m in mitglieder if m.get("baum") == BAUM_SAMMLUNG]
    if not upload:
        return []
    if sammlung:
        return list(upload)
    return list(upload[1:]) if len(upload) > 1 else []


def _gruppe_bauen(
    groesse: int, hashwert_text: str, mitglieder: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Eine Duplikatgruppe als Bericht-Eintrag (Mitglieder + Kandidaten)."""
    sortiert = sorted(mitglieder, key=_mitglied_sortierschluessel)
    baeume = sorted({str(m.get("baum") or "") for m in sortiert})
    if len(baeume) > 1:
        art = "ueber_baeume"
    elif baeume and baeume[0] == BAUM_UPLOAD:
        art = "innerhalb_upload"
    else:
        art = "innerhalb_sammlung"
    kandidaten = kandidaten_waehlen(sortiert)
    return {
        "size": groesse,
        "hash": sortiert[0].get("hash"),
        "hash_text": hashwert_text,
        "anzahl": len(sortiert),
        "baeume": baeume,
        "art": art,
        "mitglieder": [
            {
                "fileid": m.get("fileid"),
                "name": m.get("name"),
                "pfad": m.get("pfad"),
                "baum": m.get("baum"),
                "created": m.get("created"),
                "modified": m.get("modified"),
            }
            for m in sortiert
        ],
        "loesch_kandidaten": [
            {
                "fileid": m.get("fileid"),
                "name": m.get("name"),
                "pfad": m.get("pfad"),
                "baum": m.get("baum"),
            }
            for m in kandidaten
        ],
    }


def _teil_zahlen(gruppen: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Zahlen einer Teilmenge von Gruppen (Anzahl, Dateien, MB)."""
    mb_kopien = sum(g["size"] * g["anzahl"] for g in gruppen)
    mb_freigabe = sum(g["size"] * len(g["loesch_kandidaten"]) for g in gruppen)
    return {
        "gruppen": len(gruppen),
        "dateien": sum(g["anzahl"] for g in gruppen),
        "mb_alle_kopien": round(mb_kopien / 1_000_000, 1),
        "mb_freigabe_kandidaten": round(mb_freigabe / 1_000_000, 1),
    }


def bericht_bauen(
    scan_baeume: List[Dict[str, Any]],
    *,
    max_tiefe: int = MAX_TIEFE_STANDARD,
    ohne_sammlung: bool = False,
) -> Dict[str, Any]:
    """Bericht aus den Baum-Scans bauen (Gruppen, Kandidaten, Zusammenfassung).

    Reine Rechnung auf bereits gelesenen Daten — kein API-Aufruf, kein Netz.
    """
    alle_dateien: List[Dict[str, Any]] = []
    baeume: Dict[str, Any] = {}
    for scan in scan_baeume:
        baeume[scan["baum"]] = {
            "gelesen": True,
            "name": scan.get("ordner_name"),
            "folderid": scan.get("folderid"),
            **scan["kennzahlen"],
        }
        alle_dateien.extend(scan["dateien"])
    if not ohne_sammlung and BAUM_SAMMLUNG not in baeume:
        raise DuplikateFehler("Der Sammlungs-Baum wurde nicht gelesen — ohne ihn kein Vergleich.")
    if ohne_sammlung:
        baeume[BAUM_SAMMLUNG] = {
            "gelesen": False,
            "grund": "--ohne-sammlung: es wurde nur der Upload-Baum gelesen.",
        }

    gruppen_alle = gruppen_bilden(alle_dateien)
    duplikate = [
        _gruppe_bauen(groesse, hashwert, mitglieder)
        for (groesse, hashwert), mitglieder in gruppen_alle.items()
        if len(mitglieder) > 1
    ]
    duplikate.sort(key=lambda g: (-g["size"], str(g["hash_text"])))

    kandidaten_liste = [
        {
            "fileid": k.get("fileid"),
            "name": k.get("name"),
            "pfad": k.get("pfad"),
            "baum": k.get("baum"),
            "size": g["size"],
            "hash": g["hash"],
            "gruppe_hash_text": g["hash_text"],
        }
        for g in duplikate
        for k in g["loesch_kandidaten"]
    ]

    vergleichbar = sum(
        1
        for d in alle_dateien
        if _als_int_oder_none(d.get("size")) is not None and _hash_text(d.get("hash")) is not None
    )
    ueber_baeume = [g for g in duplikate if g["art"] == "ueber_baeume"]
    inner_upload = [g for g in duplikate if g["art"] == "innerhalb_upload"]
    inner_sammlung = [g for g in duplikate if g["art"] == "innerhalb_sammlung"]

    zusammenfassung: Dict[str, Any] = {
        "gescannte_dateien": sum(len(s["dateien"]) for s in scan_baeume),
        "vergleichbare_dateien": vergleichbar,
        "duplikatgruppen": len(duplikate),
        "betroffene_dateien": sum(g["anzahl"] for g in duplikate),
        "mb_alle_kopien": round(sum(g["size"] * g["anzahl"] for g in duplikate) / 1_000_000, 1),
        "mb_freigabe_kandidaten": round(
            sum(g["size"] * len(g["loesch_kandidaten"]) for g in duplikate) / 1_000_000, 1
        ),
        "ueber_baeume": _teil_zahlen(ueber_baeume),
        "innerhalb": {
            BAUM_UPLOAD: _teil_zahlen(inner_upload),
            BAUM_SAMMLUNG: _teil_zahlen(inner_sammlung),
        },
        "loesch_kandidaten": {
            "dateien": len(kandidaten_liste),
            "mb": round(sum(k["size"] for k in kandidaten_liste) / 1_000_000, 1),
        },
    }

    return {
        "stand": _jetzt_iso(),
        "trocken": True,
        "werkzeug": "tools/pcloud/pcloud_duplikate.py",
        "tiefe_grenze": int(max_tiefe),
        "ohne_sammlung": bool(ohne_sammlung),
        "regel_kandidat": (
            "Loesch-Kandidat ist immer die Kopie im Baum 'upload' — die "
            "Sammlung wird nie vorgeschlagen. Geloescht wird von diesem "
            "Werkzeug nichts."
        ),
        "baeume": baeume,
        "gruppen": duplikate,
        "loesch_kandidaten": {
            "dateien": zusammenfassung["loesch_kandidaten"]["dateien"],
            "mb": zusammenfassung["loesch_kandidaten"]["mb"],
            "liste": kandidaten_liste,
        },
        "zusammenfassung": zusammenfassung,
    }


def scan_und_bericht(
    *,
    max_tiefe: int = MAX_TIEFE_STANDARD,
    ohne_sammlung: bool = False,
    ordner_max: int = ORDNER_MAX_STANDARD,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> Dict[str, Any]:
    """Die zwei Baeume lesen und den Bericht bauen (nur lesend).

    Ablauf: EIN ``listfolder`` auf der Wurzel, um die Kennungen der zwei
    Ordner zu finden; danach je Baum ein Lauf ueber die Warteschlange.
    """
    wurzel_eintraege = ordner_roh(WURZEL_ID, token=token, host=host, timeout=timeout)
    upload_ordner = _finde_ordner(wurzel_eintraege, ORDNER_UPLOAD)
    scans = [
        baum_scannen(
            BAUM_UPLOAD,
            upload_ordner["folderid"],
            ordner_name=upload_ordner["name"],
            max_tiefe=max_tiefe,
            ordner_max=ordner_max,
            token=token,
            host=host,
            timeout=timeout,
        )
    ]
    if not ohne_sammlung:
        sammlung_ordner = _finde_ordner(wurzel_eintraege, ORDNER_SAMMLUNG)
        scans.append(
            baum_scannen(
                BAUM_SAMMLUNG,
                sammlung_ordner["folderid"],
                ordner_name=sammlung_ordner["name"],
                max_tiefe=max_tiefe,
                ordner_max=ordner_max,
                token=token,
                host=host,
                timeout=timeout,
            )
        )
    bericht = bericht_bauen(scans, max_tiefe=max_tiefe, ohne_sammlung=ohne_sammlung)
    bericht["aufrufe_gesamt"] = 1 + sum(s["kennzahlen"]["aufrufe"] for s in scans)
    return bericht


# ── Ausgabe: nur ausserhalb des Repos, atomar ─────────────────────────────

def _pruefe_ziel_ausserhalb_repo(pfad: str) -> str:
    """Sicherstellen, dass die Ausgabedatei AUSSERHALB des Repos liegt.

    Der Bericht enthaelt Sebastians eigene Dateinamen und Pfade — er gehoert
    nie ins (oeffentliche) Repo. ``~`` wird dabei ausgeschrieben (sonst
    landete der Standardpfad scheinbar im Arbeitsverzeichnis), und geprueft
    wird der absolut aufgeloeste Pfad (Gross-/Kleinschreibung und
    Schraegstriche egal). Liegt das Ziel im Repo, gibt es eine deutsche
    Klartext-Meldung und ``SystemExit(2)`` — es wird dann nichts geschrieben.
    Zurueck kommt der ausgeschriebene, absolute Pfad.
    """
    ausgeschrieben = os.path.abspath(os.path.expanduser(str(pfad)))
    ziel = os.path.normcase(ausgeschrieben)
    repo = os.path.normcase(os.path.abspath(str(Path(__file__).resolve().parents[2])))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                       # anderes Laufwerk: nie im Repo
        return ausgeschrieben
    if gemeinsam == repo:
        print(
            f"Zieldatei liegt IM Repo und ist nicht erlaubt: {pfad}\n"
            f"Der Bericht gehoert ausserhalb des Repos (Standard: "
            f"{STANDARD_AUSGABE}); es wird NICHTS geschrieben.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return ausgeschrieben


def _schreibe_json(ziel: str, inhalt: Dict[str, Any]) -> None:
    """JSON atomar schreiben (temp-Datei im Zielordner + ``os.replace``).

    Nie eine halbe Datei: erst vollstaendig in ``<ziel>.tmp`` schreiben, dann
    ersetzen. Bleibt ein tmp im Fehlerfall liegen, wird es gemeldet (eine
    Aufraeum-Loeschung gibt es in diesem Werkzeug bewusst nicht).
    """
    ordner = os.path.dirname(os.path.abspath(os.path.expanduser(str(ziel))))
    os.makedirs(ordner, exist_ok=True)
    temp = os.path.join(ordner, os.path.basename(ziel) + ".tmp")
    try:
        with open(temp, "w", encoding="utf-8") as datei:
            json.dump(inhalt, datei, ensure_ascii=False, indent=1)
            datei.write("\n")
        os.replace(temp, ziel)
    except OSError as e:
        raise DuplikateFehler(
            f"Ausgabe konnte nicht geschrieben werden ({ziel}): {e.__class__.__name__}"
            + (f" — Reste liegen in {temp}." if os.path.exists(temp) else ".")
        ) from None


# ── Konsole: nur Zahlen, Beispiele und die Kandidaten ─────────────────────

def _baum_zeile(baum: str, zahlen: Dict[str, Any]) -> str:
    """Eine Zahlenzeile je Baum — ohne Dateinamen."""
    return (
        f"  {baum:<8} {str(zahlen.get('name') or '')!r}: "
        f"{_zahl_de(zahlen.get('ordner_gelesen'))} Ordner gelesen, "
        f"{_zahl_de(zahlen.get('dateien'))} Dateien, "
        f"{_zahl_de(zahlen.get('knoten'))} Knoten, "
        f"Tiefe erreicht {zahlen.get('tiefe_erreicht')} (Grenze {zahlen.get('tiefe_grenze')}), "
        f"Aufrufe {_zahl_de(zahlen.get('aufrufe'))}"
        + (", ABGEBROCHEN (Ordner-Budget)" if zahlen.get("abgebrochen") else "")
    )


def _gruppe_zeigen(nummer: int, gruppe: Dict[str, Any]) -> None:
    """Eine Beispielgruppe mit Namen und dem ausdruecklichen Kandidaten."""
    print(
        f"Gruppe {nummer}: {_mb_de(gruppe['size'])}, {gruppe['anzahl']} Eintraege, "
        f"Pruefsumme {gruppe.get('hash_text')} ({gruppe['art']})"
    )
    kandidaten_ids = {k.get("fileid") for k in gruppe["loesch_kandidaten"]}
    for mitglied in gruppe["mitglieder"]:
        marke = (
            "  -> LOESCH-KANDIDAT (Upload-Kopie)"
            if mitglied.get("fileid") in kandidaten_ids and mitglied.get("baum") == BAUM_UPLOAD
            else ("  (Sammlung — bleibt)" if mitglied.get("baum") == BAUM_SAMMLUNG else "  (bleibt)")
        )
        print(
            f"  [{mitglied.get('baum')}] {mitglied.get('pfad')} "
            f"(fileid {mitglied.get('fileid')}){marke}"
        )


def konsole_zeigen(bericht: Dict[str, Any], beispiele: int = 5) -> None:
    """Den Bericht auf der Konsole zeigen: Zahlen, Beispiele, Kandidaten.

    Es werden NUR Zahlen und die ersten ``beispiele`` Gruppen mit Namen
    gezeigt — die vollstaendige Liste steht in der JSON-Datei.
    """
    zusammen = bericht["zusammenfassung"]
    print("pCloud-Duplikate per Pruefsumme (size+hash) — nur gelesen, kein Loeschen, kein Download")
    print(f"Stand: {bericht['stand']} | listfolder-Aufrufe gesamt: {_zahl_de(bericht.get('aufrufe_gesamt'))}")
    for baum in (BAUM_UPLOAD, BAUM_SAMMLUNG):
        zahlen = bericht["baeume"].get(baum)
        if not zahlen:
            continue
        if not zahlen.get("gelesen"):
            print(f"  {baum:<8} NICHT gelesen — {zahlen.get('grund')}")
            continue
        print(_baum_zeile(baum, zahlen))
    print(
        f"Gelesene Dateien: {_zahl_de(zusammen['gescannte_dateien'])} | "
        f"vergleichbar (size+hash): {_zahl_de(zusammen['vergleichbare_dateien'])}"
    )
    print()
    print(f"Duplikatgruppen (>1 Eintrag je size+hash): {_zahl_de(zusammen['duplikatgruppen'])}")
    print(
        f"betroffene Dateien: {_zahl_de(zusammen['betroffene_dateien'])} | "
        f"Summe alle Kopien: {_mb_de(zusammen['mb_alle_kopien'] * 1_000_000)} | "
        f"moegliche Freigabe (nur Kandidaten): {_mb_de(zusammen['mb_freigabe_kandidaten'] * 1_000_000)}"
    )
    ueber = zusammen["ueber_baeume"]
    print(
        f"  ueber die Baeume hinweg (Upload-Kopie vs. Sammlung-Original): "
        f"{_zahl_de(ueber['gruppen'])} Gruppen, {_zahl_de(ueber['dateien'])} Dateien, "
        f"{_mb_de(ueber['mb_alle_kopien'] * 1_000_000)}"
    )
    for baum in (BAUM_UPLOAD, BAUM_SAMMLUNG):
        teil = zusammen["innerhalb"][baum]
        print(
            f"  innerhalb '{baum}': {_zahl_de(teil['gruppen'])} Gruppen, "
            f"{_zahl_de(teil['dateien'])} Dateien, {_mb_de(teil['mb_alle_kopien'] * 1_000_000)}"
        )
    print()
    print(
        "Loesch-Kandidaten (immer die Kopie im Baum 'upload', nie die Sammlung): "
        f"{_zahl_de(zusammen['loesch_kandidaten']['dateien'])} Dateien, "
        f"{_mb_de(zusammen['loesch_kandidaten']['mb'] * 1_000_000)}"
    )
    if not zusammen["duplikatgruppen"]:
        print("Keine Duplikate gefunden — nichts zu entscheiden.")
        return
    anzeigen = max(0, int(beispiele))
    print()
    print(f"Erste {anzeigen} Beispielgruppen (vollstaendige Liste in der Ausgabedatei):")
    for nummer, gruppe in enumerate(bericht["gruppen"][:anzeigen], start=1):
        _gruppe_zeigen(nummer, gruppe)
    if len(bericht["gruppen"]) > anzeigen:
        print(f"... und {_zahl_de(len(bericht['gruppen']) - anzeigen)} weitere Gruppen (siehe JSON).")


# ── Kommandozeile ─────────────────────────────────────────────────────────

def _zerleger_bauen() -> argparse.ArgumentParser:
    """Die Kommandozeile — es gibt keinen Modus, der etwas loescht."""
    zerleger = argparse.ArgumentParser(
        prog="pcloud_duplikate.py",
        description=(
            "Findet doppelte Dateien in der pCloud ueber Groesse+Pruefsumme "
            "(hash) — Upload-Baum 'Automatic Upload' gegen die Sammlung "
            "'Bilder & Videos'. NUR LESEND: kein Loeschen, kein Download."
        ),
    )
    zerleger.add_argument(
        "--tiefe", dest="tiefe", type=int, default=MAX_TIEFE_STANDARD,
        help=f"maximale Ordnertiefe je Baum (Standard {MAX_TIEFE_STANDARD})",
    )
    zerleger.add_argument(
        "--quelle", dest="quelle",
        default=os.environ.get(UMGEBUNG_AUSGABE, "") or STANDARD_AUSGABE,
        help=f"Pfad der JSON-Ausgabe (Standard {STANDARD_AUSGABE}, nie im Repo)",
    )
    zerleger.add_argument(
        "--ohne-sammlung", dest="ohne_sammlung", action="store_true",
        help="nur den Upload-Baum lesen (dann keine Vergleiche ueber Baeume hinweg)",
    )
    zerleger.add_argument(
        "--trocken", dest="trocken", action="store_true", default=True,
        help="Standard und einziger Modus: nur zaehlen und die Datei schreiben "
             "(dieses Werkzeug loescht nie)",
    )
    zerleger.add_argument(
        "--ordner-max", dest="ordner_max", type=int, default=ORDNER_MAX_STANDARD,
        help=f"Obergrenze der Leseaufrufe je Baum (Standard {ORDNER_MAX_STANDARD}); "
             "danach bricht der Lauf ehrlich ab",
    )
    zerleger.add_argument(
        "--beispiele", dest="beispiele", type=int, default=5,
        help="wie viele Beispielgruppen auf der Konsole erscheinen (Standard 5)",
    )
    return zerleger


def main(argv: Optional[List[str]] = None) -> int:
    """Kommandozeilen-Teil: lesen, Bericht schreiben, Zahlen zeigen."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = _zerleger_bauen().parse_args(argv)
    try:
        ziel = _pruefe_ziel_ausserhalb_repo(args.quelle)
        bericht = scan_und_bericht(
            max_tiefe=args.tiefe,
            ohne_sammlung=args.ohne_sammlung,
            ordner_max=args.ordner_max,
        )
        _schreibe_json(ziel, bericht)
        konsole_zeigen(bericht, beispiele=args.beispiele)
        print()
        print(f"Ausgabe geschrieben: {os.path.abspath(ziel)}")
        return 0
    except DuplikateFehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
