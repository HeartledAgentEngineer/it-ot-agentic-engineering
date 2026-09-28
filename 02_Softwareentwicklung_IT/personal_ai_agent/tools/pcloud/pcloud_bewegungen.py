"""pCloud-Bewegungen mit Manifest und Rueckholbarkeit — das Sicherheitsnetz.

Warum dieses Werkzeug (Sebastian, Nachtlauf 26./27.09.2026):
    Schritt N8 des Plans (``docs/plan-nachtlauf-2026-09-26.md``) verschiebt
    Fotos in der pCloud nach ``Agent/Fotos/<Jahr>/<Thema>/``. Jeder
    Schreibvorgang auf einem fremden System braucht Rueckholbarkeit
    (AGENTS.md, "Dauerlauf / Nachtarbeit": Manifest und Rueckholbarkeit sind
    Pflicht). Dieses Modul liefert dafuer genau DREI Schreibwege — mehr
    nicht — und schreibt JEDE erfolgreiche Aktion als eine Zeile ins
    Manifest, aus dem ``pcloud_rueckrollen.py`` sie zurueckfahren kann.

Was dieses Modul bewusst NICHT kann:
    Es gibt keinen Weg fuer Entfernen oder Umbenennen und keinen Datei-
    Upload. ``_api_senden`` laesst nur die Methoden aus ``ERLAUBTE_METHODEN``
    durch (Positivliste) — ein spaeterer Aufruf mit einer fremden Methode
    wird abgewiesen, BEVOR irgendetwas gesendet wird.

Die drei Schreibwege (die einzigen):
    * ``ordner_anlegen(ordner_id, name)``           -> createfolder
    * ``datei_verschieben(fileid, ziel_id)``        -> renamefile (verschieben)
    * ``ordner_verschieben(ordner_id, ziel_id)``    -> renamefolder (verschieben)
    Dazu ``zielordner_finden_oder_bauen(eltern_id, name)``: vorhandenen
    Ordner nehmen, sonst anlegen — nie doppelt (idempotent).

Trockenlauf ist STANDARD:
    Alle drei Schreibwege haben ``trocken=True`` als Standard. Ohne
    ausdrueckliches ``trocken=False`` wird NICHTS gesendet und NICHTS ins
    Manifest geschrieben — nur der geplante Eintrag kommt zurueck. Ein
    vergessener Schalter kann so keinen Schaden anrichten.

Sicherheitspruefungen vor jedem echten Verschieben (nur lesend):
    * Der Zielordner wird per ``listfolder`` GELESEN. Liegt dort schon ein
      gleichnamiges Element (andere Kennung), wird nichts verschoben:
      pCloud wuerde die Zieldatei laut Doku sonst atomar ersetzen.
    * ``von_folderid`` ist bei echten Verschiebungen Pflicht — ohne
      Quellordner-Id waere die Aktion nicht rueckholbar.
    * Schlaegt pCloud trotzdem zu (Wettlauf), steht das als Feld
      ``hinweis`` im Manifest-Eintrag und es gibt einen lauten Fehler.

Manifest (Standard ``~/foto_sortierung/manifest.jsonl``, NIE im Repo):
    Eine JSON-Zeile je Aktion mit den Feldern ``zeit`` (ISO mit Zonen-
    versatz), ``art`` (movefile|movefolder|createfolder|rueckroll|loeschen),
    ``name``, ``fileid``/``folderid``, ``von_folderid``, ``nach_folderid``,
    ``von_pfad``, ``nach_pfad``. Nur anhaengen, Flush (und fsync) nach
    jedem Eintrag. Pfad aenderbar per Argument ``manifest_pfad=...`` oder
    Umgebungsvariable ``PCLOUD_MANIFEST``; ein Pfad im Git-Repo wird
    abgelehnt.

Der Token (Umgebung ``PCLOUD_TOKEN``/``PCLOUD_HOST`` oder ``backend/.env``)
ist ein Geheimnis: Er wird gelesen, aber nie ausgegeben, nie geloggt und
steht in keiner Datei, die dieses Modul schreibt.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx

# EU-Rechenzentrum des Kontos. NICHT mit api.pcloud.com (US) verwechseln —
# dort gilt der Token nicht.
STANDARD_HOST = "eapi.pcloud.com"

# Ein Aufruf soll schnell scheitern, statt minutenlang zu haengen.
TIMEOUT_SEKUNDEN = 30.0

# Standard-Ablage des Manifests: im Benutzerverzeichnis, niemals im Repo.
STANDARD_MANIFEST = "~/foto_sortierung/manifest.jsonl"
UMGEBUNG_MANIFEST = "PCLOUD_MANIFEST"

# Nur diese Arten von Manifest-Eintraegen gibt es. ``loeschen`` gehoert dazu,
# seit es das Loesch-Werkzeug ``pcloud_duplikate_loeschen.py`` gibt (es bucht
# seine Loeschungen ueber ``manifest_anhaengen`` -> genau eine Manifest-Logik).
ERLAUBTE_ARTEN = ("movefile", "movefolder", "createfolder", "rueckroll", "loeschen")

# Positivliste der API-Methoden — nur Lesen (listfolder) und die drei
# Schreibwege. Waere hier ein Entfernungs-Aufruf dabei, waere das
# Sicherheitsnetz kaputt: Aenderungen an dieser Liste sind eine bewusste
# Entscheidung, kein Versehen.
ERLAUBTE_METHODEN = ("createfolder", "renamefile", "renamefolder", "listfolder")

# Diese Felder stehen in JEDER Manifest-Zeile (Reihenfolge = Leselogik).
MANIFEST_FELDER = (
    "zeit",
    "art",
    "name",
    "fileid",
    "folderid",
    "von_folderid",
    "nach_folderid",
    "von_pfad",
    "nach_pfad",
)

# backend/.env des Projekts — Fallback-Quelle fuer Token und Host.
ENV_DATEI = Path(__file__).resolve().parents[2] / "backend" / ".env"

PfadAngabe = Union[str, "os.PathLike[str]", None]


class PCloudBewegungsFehler(Exception):
    """Fehler beim Bewegen in der pCloud — Klartext fuer den Nutzer.

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


def _als_id(wert: Any, feld: str) -> int:
    """Pflicht-Kennung als int — unbrauchbare Werte werden zum Klartextfehler."""
    try:
        return int(wert)
    except (TypeError, ValueError):
        raise PCloudBewegungsFehler(
            f"{feld} fehlt oder ist keine Zahl: {wert!r}"
        ) from None


def _als_optional_id(wert: Any, feld: str = "Kennung") -> Optional[int]:
    """Kennung als int oder None — unbrauchbare Werte werden zum Klartextfehler."""
    if wert is None or wert == "":
        return None
    try:
        return int(wert)
    except (TypeError, ValueError):
        raise PCloudBewegungsFehler(f"{feld} ist keine Zahl: {wert!r}") from None


# ── Manifest ───────────────────────────────────────────────────────────────

def manifest_datei(pfad: PfadAngabe = None) -> Path:
    """Die Manifest-Datei bestimmen: Argument schlaegt Umgebung schlaegt Standard."""
    wert = pfad if pfad is not None else os.environ.get(UMGEBUNG_MANIFEST, "")
    if wert:
        return Path(wert).expanduser()
    return Path(STANDARD_MANIFEST).expanduser()


def _im_repo(pfad: Path) -> bool:
    """True, wenn ueber dem Pfad irgendwo ein ``.git`` liegt (Repo-Bereich)."""
    kandidat = pfad
    if not kandidat.is_absolute():
        kandidat = Path.cwd() / kandidat
    for teil in [kandidat.parent, *kandidat.parent.parents]:
        if (teil / ".git").exists():
            return True
    return False


def _pruefe_manifest_ort(pfad: Path) -> None:
    """Das Manifest gehoert NIE ins Git-Repo (Arbeitsregel des Nutzers)."""
    if _im_repo(pfad):
        raise PCloudBewegungsFehler(
            f"Manifest-Pfad liegt in einem Git-Repo ({pfad}) — erlaubt sind nur "
            "Orte ausserhalb. Standard: ~/foto_sortierung/manifest.jsonl "
            f"(per Argument oder Umgebungsvariable {UMGEBUNG_MANIFEST} aenderbar)."
        )


def manifest_anhaengen(eintrag: Dict[str, Any], pfad: PfadAngabe = None) -> Dict[str, Any]:
    """EINE Zeile an das Manifest anhaengen — nie ueberschreiben.

    Fuellt fehlende Pflichtfelder ehrlich mit None und ``zeit`` mit jetzt,
    behaelt Zusatzfelder (z. B. ``hinweis``) und schreibt sofort auf die
    Platte (flush + fsync), damit ein Absturz die Buchung nicht verschluckt.
    """
    if not isinstance(eintrag, dict):
        raise PCloudBewegungsFehler("Manifest-Eintrag muss ein JSON-Objekt (dict) sein.")
    art = str(eintrag.get("art") or "").strip()
    if art not in ERLAUBTE_ARTEN:
        raise PCloudBewegungsFehler(
            f"Unbekannte Manifest-Art {art!r} — erlaubt sind: "
            + ", ".join(ERLAUBTE_ARTEN)
            + "."
        )
    ziel = manifest_datei(pfad)
    _pruefe_manifest_ort(ziel)
    zeile: Dict[str, Any] = {feld: eintrag.get(feld) for feld in MANIFEST_FELDER}
    for schluessel, wert in eintrag.items():
        if schluessel not in zeile:
            zeile[schluessel] = wert
    if not zeile["zeit"]:
        zeile["zeit"] = _jetzt_iso()
    zeile["art"] = art
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("a", encoding="utf-8", newline="\n") as datei:
        datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
        datei.flush()
        try:
            os.fsync(datei.fileno())
        except OSError:
            # Flush ist gelungen; fsync scheitert auf exotischen Dateisystemen.
            pass
    return zeile


def manifest_lesen(pfad: PfadAngabe = None) -> List[Dict[str, Any]]:
    """Alle Manifest-Zeilen als Liste (leer, wenn es die Datei noch nicht gibt).

    Eine kaputte Zeile ist ehrlicher Grund zum Anhalten (mit Zeilennummer):
    Wer zurueckrollt, muss dem Manifest vertrauen koennen.
    """
    ziel = manifest_datei(pfad)
    if not ziel.exists():
        return []
    try:
        text = ziel.read_text(encoding="utf-8")
    except OSError as e:
        raise PCloudBewegungsFehler(
            f"Manifest nicht lesbar ({ziel}): {e.__class__.__name__}."
        ) from None
    eintraege: List[Dict[str, Any]] = []
    for nummer, roh in enumerate(text.splitlines(), start=1):
        if not roh.strip():
            continue
        try:
            daten = json.loads(roh)
        except ValueError:
            raise PCloudBewegungsFehler(
                f"Manifest-Zeile {nummer} ({ziel}) ist kein gueltiges JSON — "
                "bitte die Datei pruefen; es wurde nichts veraendert."
            ) from None
        if not isinstance(daten, dict):
            raise PCloudBewegungsFehler(
                f"Manifest-Zeile {nummer} ({ziel}) ist kein Eintrag (JSON-Objekt)."
            )
        eintraege.append(daten)
    return eintraege


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

    ``listfolder`` (lesen) und die drei Schreibwege sind erlaubt; alles
    andere wird abgewiesen, BEVOR etwas gesendet wird.
    """
    if methode not in ERLAUBTE_METHODEN:
        raise PCloudBewegungsFehler(
            f"Abgewiesen: '{methode}' steht nicht auf der Positivliste dieses "
            "Moduls (" + ", ".join(ERLAUBTE_METHODEN) + ")."
        )
    geheimnis = _token_aus_quellen(token)
    if not geheimnis:
        raise PCloudBewegungsFehler(
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
        raise PCloudBewegungsFehler(
            f"pCloud nicht erreichbar ({e.__class__.__name__})."
        ) from None
    if antwort.status_code != 200:
        raise PCloudBewegungsFehler(f"pCloud antwortete mit HTTP {antwort.status_code}.")
    try:
        daten = antwort.json()
    except Exception:
        raise PCloudBewegungsFehler("pCloud lieferte keine lesbare JSON-Antwort.") from None
    if not isinstance(daten, dict):
        raise PCloudBewegungsFehler("pCloud lieferte eine unerwartete Antwort.")
    if daten.get("result") != 0:
        klartext = _ohne_geheimnis(str(daten.get("error") or "ohne Fehlertext"), geheimnis)
        raise PCloudBewegungsFehler(f"pCloud meldet Fehler {daten.get('result')}: {klartext}")
    return daten


# ── Lesen fuer die Vorpruefungen ──────────────────────────────────────────

def ordner_inhalt(
    folderid: Any,
    *,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> List[Dict[str, Any]]:
    """Eintraege EINES Ordners lesen (nur lesend — fuer die Vorpruefungen).

    Liefert je Eintrag ``name``, ``ist_ordner``, ``fileid``, ``folderid``,
    ``path``. Genau EIN ``listfolder``-Aufruf, kein tieferer Lauf.
    """
    ordner = _als_id(folderid, "folderid")
    daten = _api_senden(
        "listfolder", {"folderid": ordner}, token=token, host=host, timeout=timeout
    )
    metadata = daten.get("metadata")
    inhalte = metadata.get("contents") if isinstance(metadata, dict) else None
    ergebnis: List[Dict[str, Any]] = []
    for roh in inhalte if isinstance(inhalte, list) else []:
        if not isinstance(roh, dict):
            continue
        ergebnis.append(
            {
                "name": str(roh.get("name") or ""),
                "ist_ordner": bool(roh.get("isfolder")),
                "fileid": roh.get("fileid"),
                "folderid": roh.get("folderid"),
                "path": roh.get("path"),
            }
        )
    return ergebnis


def element_kennung(eintrag: Dict[str, Any]) -> Optional[int]:
    """fileid (Datei) bzw. folderid (Ordner) eines Ordner-Eintrags als int."""
    kennung = eintrag.get("folderid") if eintrag.get("ist_ordner") else eintrag.get("fileid")
    return _als_optional_id(kennung, "Kennung")


def _metadata(daten: Dict[str, Any]) -> Dict[str, Any]:
    """``metadata`` aus einer API-Antwort — leeres Objekt, wenn es fehlt."""
    metadata = daten.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _ziel_lage(
    ziel_id: int,
    name: str,
    eigene_id: int,
    *,
    token: Optional[str],
    host: Optional[str],
    timeout: float,
) -> str:
    """Liegt der Name schon im Zielordner? ``frei`` | ``schon_da`` | ``konflikt``.

    ``schon_da``: dasselbe Element (gleiche Kennung) liegt bereits am Ziel —
    die Aktion ist damit erledigt und wird uebersprungen.
    ``konflikt``: ein ANDERES Element traegt diesen Namen — es wird nicht
    verschoben, weil pCloud das Ziel sonst ersetzen wuerde.
    """
    for vorhanden in ordner_inhalt(ziel_id, token=token, host=host, timeout=timeout):
        if vorhanden["name"].casefold() != name.casefold():
            continue
        kennung = element_kennung(vorhanden)
        if kennung is not None and kennung == eigene_id:
            return "schon_da"
        return "konflikt"
    return "frei"


# ── Eintraege bauen ───────────────────────────────────────────────────────

def _eintrag(
    art: str,
    *,
    name: str = "",
    fileid: Any = None,
    folderid: Any = None,
    von_folderid: Any = None,
    nach_folderid: Any = None,
    von_pfad: Optional[str] = None,
    nach_pfad: Optional[str] = None,
) -> Dict[str, Any]:
    """Ein vollstaendiger Manifest-Eintrag (zeit = jetzt), alle Felder gesetzt."""
    return {
        "zeit": _jetzt_iso(),
        "art": art,
        "name": name,
        "fileid": _als_optional_id(fileid, "fileid"),
        "folderid": _als_optional_id(folderid, "folderid"),
        "von_folderid": _als_optional_id(von_folderid, "von_folderid"),
        "nach_folderid": _als_optional_id(nach_folderid, "nach_folderid"),
        "von_pfad": von_pfad,
        "nach_pfad": nach_pfad,
    }


def _geplant(eintrag: Dict[str, Any]) -> Dict[str, Any]:
    """Trockenlauf-Rueckgabe: der geplante Eintrag, ausdruecklich als solcher."""
    return {**eintrag, "trocken": True}


# ── Die drei Schreibwege ──────────────────────────────────────────────────

def ordner_anlegen(
    ordner_id: Any,
    name: str,
    *,
    trocken: bool = True,
    manifest_pfad: PfadAngabe = None,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> Dict[str, Any]:
    """Einen Ordner ``name`` im Ordner ``ordner_id`` anlegen (createfolder).

    ``trocken=True`` (Standard) sendet nichts — nur der geplante Eintrag
    kommt zurueck. Erst nach Erfolg wird der Manifest-Eintrag geschrieben.
    Idempotent anlegen: ``zielordner_finden_oder_bauen`` (prueft vorher).
    """
    eltern = _als_id(ordner_id, "ordner_id")
    name = str(name or "").strip()
    if not name:
        raise PCloudBewegungsFehler("ordner_anlegen ohne Namen ist nicht moeglich.")
    eintrag = _eintrag("createfolder", name=name, nach_folderid=eltern)
    if trocken:
        return _geplant(eintrag)
    daten = _api_senden(
        "createfolder", {"folderid": eltern, "name": name},
        token=token, host=host, timeout=timeout,
    )
    metadata = _metadata(daten)
    eintrag["folderid"] = _als_optional_id(metadata.get("folderid"), "folderid")
    if metadata.get("path"):
        eintrag["nach_pfad"] = str(metadata["path"])
    return manifest_anhaengen(eintrag, pfad=manifest_pfad)


def datei_verschieben(
    fileid: Any,
    ziel_id: Any,
    *,
    name: str = "",
    von_folderid: Any = None,
    von_pfad: Optional[str] = None,
    nach_pfad: Optional[str] = None,
    trocken: bool = True,
    art: str = "movefile",
    manifest_pfad: PfadAngabe = None,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> Dict[str, Any]:
    """Eine Datei in den Ordner ``ziel_id`` verschieben (renamefile).

    ``trocken=True`` (Standard): nichts senden, nichts buchen — nur den
    geplanten Eintrag zurueckgeben. Echtes Verschieben (``trocken=False``)
    braucht ``name`` (fuer die Namenskonflikt-Pruefung) und ``von_folderid``
    (fuer die Rueckholbarkeit); vorher wird der Zielordner gelesen.

    ``art="rueckroll"`` bucht die Aktion als Rueckrollung (fuer
    ``pcloud_rueckrollen.py``); sonst ``movefile``.
    """
    datei = _als_id(fileid, "fileid")
    ziel = _als_id(ziel_id, "ziel_id")
    name = str(name or "").strip()
    if art not in ("movefile", "rueckroll"):
        raise PCloudBewegungsFehler(
            f"datei_verschieben kennt art={art!r} nicht (movefile oder rueckroll)."
        )
    eintrag = _eintrag(
        art, name=name, fileid=datei, von_folderid=von_folderid,
        nach_folderid=ziel, von_pfad=von_pfad, nach_pfad=nach_pfad,
    )
    if trocken:
        return _geplant(eintrag)
    if not name:
        raise PCloudBewegungsFehler(
            "Ohne Namen kein echter Verschiebe-Lauf: der Namenskonflikt am Ziel "
            "waere nicht pruefbar — bitte name=... mitgeben."
        )
    if eintrag["von_folderid"] is None:
        raise PCloudBewegungsFehler(
            "von_folderid fehlt: ohne Quellordner-Id waere die Aktion nicht "
            "rueckholbar — es wird nichts verschoben."
        )
    if eintrag["von_folderid"] == ziel:
        raise PCloudBewegungsFehler(
            "Ziel und Quelle sind derselbe Ordner — nichts zu tun, nichts gesendet."
        )
    lage = _ziel_lage(ziel, name, datei, token=token, host=host, timeout=timeout)
    if lage == "schon_da":
        return {
            **eintrag,
            "uebersprungen": True,
            "grund": f"Datei {datei} liegt bereits als {name!r} in Ordner {ziel} — nichts getan.",
        }
    if lage == "konflikt":
        raise PCloudBewegungsFehler(
            f"Im Zielordner {ziel} liegt bereits ein Element mit dem Namen {name!r} — "
            "es wird NICHT verschoben (pCloud wuerde das Ziel sonst ersetzen). "
            "Nichts geaendert."
        )
    daten = _api_senden(
        "renamefile", {"fileid": datei, "tofolderid": ziel},
        token=token, host=host, timeout=timeout,
    )
    metadata = _metadata(daten)
    if not eintrag["nach_pfad"] and metadata.get("path"):
        eintrag["nach_pfad"] = str(metadata["path"])
    # "deletedfileid" ist ein ANTWORT-Feld der pCloud: Kennung der Datei, die
    # am Ziel ersetzt wurde. Hier dient es nur der Erkennung dieses Falls —
    # es ist kein Aufruf und es gibt hier keinen Weg, etwas zu entfernen.
    ersetzt = _als_optional_id(metadata.get("deletedfileid"), "deletedfileid")
    if ersetzt is not None:
        eintrag["hinweis"] = (
            f"ACHTUNG: am Ziel lag eine gleichnamige Datei; pCloud hat sie beim "
            f"Verschieben ersetzt (ersetzte Kennung {ersetzt})."
        )
    gebucht = manifest_anhaengen(eintrag, pfad=manifest_pfad)
    if ersetzt is not None:
        raise PCloudBewegungsFehler(
            gebucht["hinweis"] + " Das Verschieben war erfolgreich; der Fall steht so im Manifest."
        )
    return gebucht


def ordner_verschieben(
    ordner_id: Any,
    ziel_id: Any,
    *,
    name: str = "",
    von_folderid: Any = None,
    von_pfad: Optional[str] = None,
    nach_pfad: Optional[str] = None,
    trocken: bool = True,
    art: str = "movefolder",
    manifest_pfad: PfadAngabe = None,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> Dict[str, Any]:
    """Einen Ordner in den Ordner ``ziel_id`` verschieben (renamefolder).

    Gleiche Regeln wie ``datei_verschieben``: Trockenlauf ist Standard,
    Namenskonflikt am Ziel haelt den Lauf an, ``von_folderid`` ist Pflicht,
    ``art="rueckroll"`` bucht die Aktion als Rueckrollung.
    """
    ordner = _als_id(ordner_id, "ordner_id")
    ziel = _als_id(ziel_id, "ziel_id")
    name = str(name or "").strip()
    if art not in ("movefolder", "rueckroll"):
        raise PCloudBewegungsFehler(
            f"ordner_verschieben kennt art={art!r} nicht (movefolder oder rueckroll)."
        )
    eintrag = _eintrag(
        art, name=name, folderid=ordner, von_folderid=von_folderid,
        nach_folderid=ziel, von_pfad=von_pfad, nach_pfad=nach_pfad,
    )
    if trocken:
        return _geplant(eintrag)
    if not name:
        raise PCloudBewegungsFehler(
            "Ohne Namen kein echter Verschiebe-Lauf: der Namenskonflikt am Ziel "
            "waere nicht pruefbar — bitte name=... mitgeben."
        )
    if eintrag["von_folderid"] is None:
        raise PCloudBewegungsFehler(
            "von_folderid fehlt: ohne Quellordner-Id waere die Aktion nicht "
            "rueckholbar — es wird nichts verschoben."
        )
    if eintrag["von_folderid"] == ziel:
        raise PCloudBewegungsFehler(
            "Ziel und Quelle sind derselbe Ordner — nichts zu tun, nichts gesendet."
        )
    lage = _ziel_lage(ziel, name, ordner, token=token, host=host, timeout=timeout)
    if lage == "schon_da":
        return {
            **eintrag,
            "uebersprungen": True,
            "grund": f"Ordner {ordner} liegt bereits als {name!r} in Ordner {ziel} — nichts getan.",
        }
    if lage == "konflikt":
        raise PCloudBewegungsFehler(
            f"Im Zielordner {ziel} liegt bereits ein Element mit dem Namen {name!r} — "
            "es wird NICHT verschoben. Nichts geaendert."
        )
    daten = _api_senden(
        "renamefolder", {"folderid": ordner, "tofolderid": ziel},
        token=token, host=host, timeout=timeout,
    )
    metadata = _metadata(daten)
    if not eintrag["nach_pfad"] and metadata.get("path"):
        eintrag["nach_pfad"] = str(metadata["path"])
    return manifest_anhaengen(eintrag, pfad=manifest_pfad)


def zielordner_finden_oder_bauen(
    eltern_id: Any,
    name: str,
    *,
    trocken: bool = True,
    manifest_pfad: PfadAngabe = None,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_SEKUNDEN,
) -> Dict[str, Any]:
    """Zielordner idempotent: vorhandenen nehmen, sonst anlegen — nie doppelt.

    Namensvergleich ohne Gross-/Kleinschreibung. Liegt im Elternordner eine
    DATEI gleichen Namens, gibt es einen Klartextfehler statt eines Versuchs.

    Trockenlauf (Standard) sendet nichts — auch die Lesepruefung nicht, der
    Bestand ist ohne Abfrage nicht bekannt. Zurueck kommt dann der geplante
    ``createfolder``-Eintrag (``trocken: True``). Echt zurueck kommt
    ``{"folderid": …, "name": …, "angelegt": True|False, "eintrag": …}``.
    """
    eltern = _als_id(eltern_id, "eltern_id")
    name = str(name or "").strip()
    if not name:
        raise PCloudBewegungsFehler("zielordner_finden_oder_bauen ohne Namen ist nicht moeglich.")
    if trocken:
        return _geplant(_eintrag("createfolder", name=name, nach_folderid=eltern))
    for vorhanden in ordner_inhalt(eltern, token=token, host=host, timeout=timeout):
        if vorhanden["name"].casefold() != name.casefold():
            continue
        if not vorhanden["ist_ordner"]:
            raise PCloudBewegungsFehler(
                f"In Ordner {eltern} liegt bereits eine DATEI namens {name!r} — "
                "kein Ordner angelegt."
            )
        return {
            "folderid": _als_optional_id(vorhanden.get("folderid"), "folderid"),
            "name": vorhanden["name"],
            "angelegt": False,
            "eintrag": None,
        }
    angelegt = ordner_anlegen(
        eltern, name, trocken=False, manifest_pfad=manifest_pfad,
        token=token, host=host, timeout=timeout,
    )
    return {"folderid": angelegt["folderid"], "name": name, "angelegt": True, "eintrag": angelegt}
