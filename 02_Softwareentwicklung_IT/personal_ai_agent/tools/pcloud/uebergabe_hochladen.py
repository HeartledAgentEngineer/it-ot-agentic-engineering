"""Ergebnisse kabellos ans Handy geben: Dateien in die pCloud hochladen (10.10.2026).

Anlass (Sebastians ausdrueckliche Entscheidung, 10.10.2026):
    Bisher kamen die Ergebnisdateien nur ueber das Kabel aufs Handy (der PC legt
    sie in den freigegebenen Download-Ordner, ``tools/handy/uebergabe_uebernehmen.py``
    holt sie beim Start). Ohne Kabel blieb das Handy also auf dem alten Stand.
    Jetzt geht derselbe Weg wahlweise KABELLOS: Der PC laedt die Dateien in einen
    festen pCloud-Ordner (Standard ``/Agent/uebergabe``), das Handy holt sie beim
    Start (``termux/pcloud-uebernehmen.sh``). Ausdruecklich freigegeben sind auch
    die Gesichts-Vektoren und der Gesichtskatalog — das eigene Geraet, das eigene
    pCloud-Konto, kein fremder Anbieter (siehe Projekt-CLAUDE.md, Datenschutz).

Was dieses Werkzeug tut:
    * Es nimmt eine Liste von Dateien ODER einen Ordner (``--ordner``),
    * laedt jede Datei nach ``/Agent/uebergabe`` in der pCloud
      (``createfolderifnotexists`` fuer den Ordner, ``uploadfile`` je Datei),
    * ist **idempotent**: gleiche Groesse UND gleiche Pruefsumme wie beim letzten
      Lauf (steht im Manifest) heisst ueberspringen — es wird nichts doppelt
      hochgeladen,
    * schreibt JE uebertragener Datei eine Manifest-Zeile (Zeit, Quelle, Ziel,
      Groesse, Pruefsumme) in eine Datei **AUSSERHALB des Repos**
      (Standard ``~/foto_sortierung/uebergabe_manifest.jsonl``).

Regeln als Code:
    * **Trockenlauf ist Standard.** Geschrieben wird nur mit ``--schreiben``.
    * **Schreiben nur unter ``/Agent/``** (Projektregel; pCloud kennt keinen
      Nur-Schreiben-Scope, also prueft der Code es). Ein Ziel ausserhalb wird
      abgewiesen, BEVOR etwas gesendet wird.
    * **Nie Zugangsdaten ausgeben.** Der Token wird gelesen, aber nie gedruckt,
      nie geloggt und steht in keiner Datei, die dieses Modul schreibt.
    * **Kein Loeschen, nirgends.** Es gibt keine Entfernungs-Funktion und keinen
      Schalter dafuer.
    * **Ueberschreiben nur bei geaendertem Inhalt.** Ist die Datei neu oder hat
      sie eine andere Pruefsumme, ersetzt ``uploadfile`` die gleichnamige Datei am
      Ziel (genau das ist gewollt — der neue Stand soll gelten). pCloud bricht
      einen abgebrochenen Upload selbst ab (``nopartial=1``).

Rueckholbarkeit:
    Jede uebertragene Datei steht als Manifest-Zeile (Quelle -> Ziel, Zeit,
    Kennung/Groesse/Pruefsumme). Zuruecknehmen heisst: die Datei im pCloud-Ordner
    von Hand entfernen (Loeschen ist bewusst nicht Teil dieses Werkzeugs). Welche
    Dateien entstanden sind, steht im Manifest und auf der Konsole.

Aufruf (aus dem Projektordner ``personal_ai_agent``):
    backend/.venv/Scripts/python.exe tools/pcloud/uebergabe_hochladen.py --ordner ~/foto_sortierung --schreiben
    backend/.venv/Scripts/python.exe tools/pcloud/uebergabe_hochladen.py --dateien a.json b.jsonl --schreiben
    backend/.venv/Scripts/python.exe tools/pcloud/uebergabe_hochladen.py --ordner ~/x            # Trockenlauf

Exit: 0 = sauber; 1 = mindestens eine Datei scheiterte; 2 = Aufruf-/Schutzfehler.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# EU-Rechenzentrum des Kontos. NICHT mit api.pcloud.com (US) verwechseln.
STANDARD_HOST = "eapi.pcloud.com"

# Hochladen grosser Dateien braucht mehr Zeit als ein kurzer Ordneraufruf.
TIMEOUT_HOCHLADEN = 120.0
TIMEOUT_STANDARD = 30.0

# Der Zielordner in der pCloud. Schreiben ist nur unter /Agent/ erlaubt.
STANDARD_ZIEL = "/Agent/uebergabe"
ERLAUBTE_WURZEL = "/Agent/"

# Manifest und Umgebung: die Buchung liegt IMMER ausserhalb des Repos.
STANDARD_MANIFEST = "~/foto_sortierung/uebergabe_manifest.jsonl"
UMGEBUNG_MANIFEST = "PCLOUD_UEBERGABE_MANIFEST"

# Nur diese zwei Methoden spricht dieses Werkzeug an: Ordner holen/anlegen
# (createfolderifnotexists) und Dateien hochladen (uploadfile). Waere ein
# weiterer Schreibweg dabei, waere die Rueckhol-Zusage gebrochen.
ERLAUBTE_METHODEN = ("createfolderifnotexists", "uploadfile")

# Zustand einer Datei im Plan.
ZUSTAND_NEU = "neu"
ZUSTAND_GLEICH = "gleich"

# backend/.env des Projekts — Fallback-Quelle fuer Token und Host.
ENV_DATEI = Path(__file__).resolve().parents[2] / "backend" / ".env"


class UebergabeFehler(Exception):
    """Fehler beim kabellosen Uebergeben — Klartext fuer den Nutzer.

    Enthaelt nie den Token (siehe ``_ohne_geheimnis``).
    """


# ── Kleine Helfer ──────────────────────────────────────────────────────────

def _ohne_geheimnis(text: str, token: str) -> str:
    """Den Token aus einem Text entfernen, falls er hineingeraten ist."""
    if token and token in text:
        return text.replace(token, "***")
    return text


def _jetzt_iso() -> str:
    """Aktuelle Zeit als ISO-Text MIT Zonenversatz (z. B. 2026-10-10T09:15:02+02:00)."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _zahl_de(wert: Any) -> str:
    """Ganzzahl deutsch mit Tausenderpunkt (1234 -> "1.234")."""
    try:
        return f"{int(wert):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(wert)


def _kurz(pruefsumme: Any) -> str:
    """Die ersten Stellen einer Pruefsumme fuer den Bericht (nie der ganze Wert)."""
    return pruefsumme[:12] if isinstance(pruefsumme, str) and pruefsumme else "-"


def sha256_datei(pfad: str) -> str:
    """Die ``sha256``-Pruefsumme einer Datei bilden (nur lesend, blockweise)."""
    pruefer = hashlib.sha256()
    with open(pfad, "rb") as datei:
        while True:
            stueck = datei.read(65536)
            if not stueck:
                break
            pruefer.update(stueck)
    return pruefer.hexdigest()


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


# ── Zielpfad pruefen (Schreiben nur unter /Agent/) ────────────────────────

def ziel_pfad_pruefen(pfad: Any) -> str:
    """Den pCloud-Zielordner pruefen — nur unter ``/Agent/`` erlaubt."""
    if not isinstance(pfad, str) or not pfad.strip():
        raise UebergabeFehler("Zielordner fehlt.")
    p = "/" + pfad.strip().strip("/")
    if (not p.startswith(ERLAUBTE_WURZEL) or len(p) <= len(ERLAUBTE_WURZEL)
            or ".." in p or "\\" in p or "//" in p):
        raise UebergabeFehler(
            f"Schreiben ist nur unter {ERLAUBTE_WURZEL} erlaubt: {pfad!r}")
    return p


# ── Der eine abgesicherte Lese-Aufruf (GET) ───────────────────────────────

def _api_get(
    methode: str,
    felder: Dict[str, Any],
    *,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_STANDARD,
) -> Dict[str, Any]:
    """Genau EIN pCloud-GET-Aufruf (createfolderifnotexists) — mit Positivliste."""
    if methode not in ERLAUBTE_METHODEN:
        raise UebergabeFehler(
            f"Abgewiesen: '{methode}' steht nicht auf der Positivliste dieses "
            "Werkzeugs (" + ", ".join(ERLAUBTE_METHODEN) + ").")
    geheimnis = _token_aus_quellen(token)
    if not geheimnis:
        raise UebergabeFehler(
            "pCloud ist nicht konfiguriert: PCLOUD_TOKEN fehlt "
            "(weder in der Umgebung noch in backend/.env).")
    ziel_host = _host_aus_quellen(host)
    parameter = {name: wert for name, wert in felder.items() if wert is not None}
    parameter["auth"] = geheimnis
    url = f"https://{ziel_host}/{methode}"
    try:
        antwort = httpx.get(url, params=parameter, timeout=timeout)
    except Exception as e:
        # Nur der Klassenname — fremde Meldungen koennen die volle URL samt
        # Token enthalten.
        raise UebergabeFehler(f"pCloud nicht erreichbar ({e.__class__.__name__}).") from None
    if antwort.status_code != 200:
        raise UebergabeFehler(f"pCloud antwortete mit HTTP {antwort.status_code}.")
    try:
        daten = antwort.json()
    except Exception:
        raise UebergabeFehler("pCloud lieferte keine lesbare JSON-Antwort.") from None
    if not isinstance(daten, dict):
        raise UebergabeFehler("pCloud lieferte eine unerwartete Antwort.")
    if daten.get("result") != 0:
        klartext = _ohne_geheimnis(str(daten.get("error") or "ohne Fehlertext"), geheimnis)
        raise UebergabeFehler(f"pCloud meldet Fehler {daten.get('result')}: {klartext}")
    return daten


def ordner_holen_oder_anlegen(
    pfad: str,
    *,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_STANDARD,
) -> int:
    """Den Zielordner idempotent holen/anlegen (``createfolderifnotexists``).

    Liefert die ``folderid``. Der Aufruf ist von pCloud her idempotent: ein
    vorhandener Ordner kommt zurueck, sonst wird er angelegt — nie doppelt.
    """
    ziel = ziel_pfad_pruefen(pfad)
    daten = _api_get(
        "createfolderifnotexists", {"path": ziel}, token=token, host=host, timeout=timeout)
    meta = daten.get("metadata") if isinstance(daten.get("metadata"), dict) else None
    folderid = meta.get("folderid") if meta else None
    if not isinstance(folderid, int) or isinstance(folderid, bool):
        raise UebergabeFehler(
            f"pCloud lieferte keine brauchbare Ordner-Kennung fuer {ziel}.")
    return folderid


# ── Der eine abgesicherte Schreib-Aufruf (POST uploadfile) ────────────────

def hochladen(
    name: str,
    daten: bytes,
    folderid: int,
    *,
    token: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = TIMEOUT_HOCHLADEN,
    senden: Any = None,
) -> Optional[int]:
    """Eine Datei in den Zielordner hochladen (``uploadfile``, multipart).

    ``senden`` ist ``httpx.post``-kompatibel und fuer Tests austauschbar. Gibt
    die ``fileid`` zurueck (falls pCloud eine liefert), sonst ``None``.
    """
    name = str(name or "").strip()
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise UebergabeFehler(f"Ungueltiger Dateiname: {name!r}")
    if not isinstance(daten, (bytes, bytearray)) or not daten:
        raise UebergabeFehler("Keine Daten zum Hochladen.")
    geheimnis = _token_aus_quellen(token)
    if not geheimnis:
        raise UebergabeFehler(
            "pCloud ist nicht konfiguriert: PCLOUD_TOKEN fehlt "
            "(weder in der Umgebung noch in backend/.env).")
    ziel_host = _host_aus_quellen(host)
    if senden is None:
        senden = httpx.post
    try:
        antwort = senden(
            f"https://{ziel_host}/uploadfile",
            params={"auth": geheimnis, "folderid": int(folderid), "nopartial": 1},
            files={"file": (name, bytes(daten), "application/octet-stream")},
            timeout=timeout,
        )
    except Exception as e:
        raise UebergabeFehler(f"Hochladen fehlgeschlagen ({e.__class__.__name__}).") from None
    if getattr(antwort, "status_code", 200) != 200:
        raise UebergabeFehler(f"pCloud antwortete beim Hochladen mit HTTP {antwort.status_code}.")
    try:
        ergebnis = antwort.json()
    except Exception:
        raise UebergabeFehler("pCloud lieferte beim Hochladen keine lesbare JSON-Antwort.") from None
    if not isinstance(ergebnis, dict) or ergebnis.get("result") != 0:
        fehler = _ohne_geheimnis(
            str((ergebnis or {}).get("error") or "ohne Fehlertext"), geheimnis)
        raise UebergabeFehler(f"pCloud lehnte das Hochladen ab: {fehler}")
    ids = ergebnis.get("fileids") or []
    if ids and isinstance(ids[0], int) and not isinstance(ids[0], bool):
        return ids[0]
    meta = ergebnis.get("metadata") or []
    if meta and isinstance(meta[0], dict) and isinstance(meta[0].get("fileid"), int):
        return meta[0]["fileid"]
    return None


# ── Manifest (ausserhalb des Repos, nur anhaengen) ────────────────────────

def manifest_datei(pfad: Optional[str] = None) -> Path:
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
    """Das Manifest gehoert NIE ins Git-Repo."""
    if _im_repo(pfad):
        raise UebergabeFehler(
            f"Manifest-Pfad liegt in einem Git-Repo ({pfad}) — erlaubt sind nur "
            "Orte ausserhalb. Standard: ~/foto_sortierung/uebergabe_manifest.jsonl "
            f"(per Argument oder Umgebungsvariable {UMGEBUNG_MANIFEST} aenderbar).")


def manifest_anhaengen(eintrag: Dict[str, Any], pfad: Optional[str] = None) -> Dict[str, Any]:
    """EINE Zeile an das Manifest anhaengen — nie ueberschreiben."""
    ziel = manifest_datei(pfad)
    _pruefe_manifest_ort(ziel)
    zeile = {
        "zeit": eintrag.get("zeit") or _jetzt_iso(),
        "name": eintrag.get("name"),
        "quelle": eintrag.get("quelle"),
        "ziel": eintrag.get("ziel"),
        "groesse": eintrag.get("groesse"),
        "pruefsumme": eintrag.get("pruefsumme"),
    }
    for schluessel, wert in eintrag.items():
        if schluessel not in zeile:
            zeile[schluessel] = wert
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("a", encoding="utf-8", newline="\n") as datei:
        datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
        datei.flush()
        try:
            os.fsync(datei.fileno())
        except OSError:
            pass
    return zeile


def manifest_lesen(pfad: Optional[str] = None) -> List[Dict[str, Any]]:
    """Alle Manifest-Zeilen als Liste (leer, wenn es die Datei noch nicht gibt)."""
    ziel = manifest_datei(pfad)
    if not ziel.exists():
        return []
    eintraege: List[Dict[str, Any]] = []
    for roh in ziel.read_text(encoding="utf-8").splitlines():
        if not roh.strip():
            continue
        try:
            daten = json.loads(roh)
        except ValueError:
            continue                        # kaputte Zeile: uebergehen, nie abstuerzen
        if isinstance(daten, dict):
            eintraege.append(daten)
    return eintraege


# ── Dateien sammeln (Liste + Ordner) ──────────────────────────────────────

def dateien_sammeln(dateien: Optional[List[str]] = None,
                    ordner: Optional[str] = None) -> List[str]:
    """Die zu uebertragenden Dateien sammeln (explizite Namen + Ordnerinhalt).

    Ein ``--ordner`` wird NICHT rekursiv gelesen (eine Ebene, nur Dateien) —
    die Uebergabe betrifft flache Dateien. Doppelte Pfade werden zusammengefasst
    (in der Reihenfolge des ersten Auftretens).
    """
    gesammelt: List[str] = []
    for roh in dateien or []:
        pfad = os.path.abspath(os.path.expanduser(str(roh)))
        if not os.path.isfile(pfad):
            raise UebergabeFehler(f"Datei nicht gefunden: {roh}")
        gesammelt.append(pfad)
    for roh in [ordner] if ordner else []:
        basis = os.path.abspath(os.path.expanduser(str(roh)))
        if not os.path.isdir(basis):
            raise UebergabeFehler(f"Ordner nicht gefunden: {roh}")
        for name in sorted(os.listdir(basis)):
            pfad = os.path.join(basis, name)
            if os.path.isfile(pfad):
                gesammelt.append(pfad)
    # Duplikate entfernen, Reihenfolge erhalten.
    gesehen: set = set()
    ergebnis: List[str] = []
    for pfad in gesammelt:
        schluessel = os.path.normcase(pfad)
        if schluessel not in gesehen:
            gesehen.add(schluessel)
            ergebnis.append(pfad)
    return ergebnis


# ── Planen (rein: liest nur, schreibt nichts) ─────────────────────────────

def _letzte_pruefsummen(eintraege: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """{Zielname: letzter Manifest-Eintrag} — der jüngste gilt."""
    bekannt: Dict[str, Dict[str, Any]] = {}
    for eintrag in eintraege:
        name = eintrag.get("name")
        if isinstance(name, str) and name:
            bekannt[name] = eintrag       # spaeterer Lauf ueberschreibt
    return bekannt


def planen(quelldateien: List[str], *, manifest_eintraege: Optional[List[Dict[str, Any]]] = None,
           alles: bool = False) -> List[Dict[str, Any]]:
    """Den Uebernahmeplan bauen — **rein**: es wird gelesen, nichts geschrieben.

    Je Datei ein Eintrag mit Name, Quelle, Groesse, Pruefsumme und Zustand
    (``neu`` = hochladen, ``gleich`` = ueberspringen). Uebersprungen wird, wenn
    das Manifest fuer DIESEN Namen dieselbe Groesse UND Pruefsumme kennt und
    nicht ``alles`` erzwungen wurde. Zweiter Aufruf = gleicher Plan.
    """
    bekannt = {} if alles else _letzte_pruefsummen(manifest_eintraege or [])
    plan: List[Dict[str, Any]] = []
    for pfad in quelldateien:
        name = os.path.basename(pfad)
        groesse = os.path.getsize(pfad)
        pruefsumme = sha256_datei(pfad)
        frueher = bekannt.get(name) or {}
        gleich = (
            not alles
            and frueher.get("groesse") == groesse
            and frueher.get("pruefsumme") == pruefsumme
        )
        plan.append({
            "name": name,
            "quelle": pfad,
            "groesse": groesse,
            "pruefsumme": pruefsumme,
            "zustand": ZUSTAND_GLEICH if gleich else ZUSTAND_NEU,
        })
    return plan


# ── Ausfuehren ────────────────────────────────────────────────────────────

def hochladen_lauf(
    plan: List[Dict[str, Any]],
    *,
    schreiben: bool = False,
    ziel_liste: Optional[List[Dict[str, Any]]] = None,
    ziel_ordner: str = STANDARD_ZIEL,
    manifest: Optional[str] = None,
    token: Optional[str] = None,
    host: Optional[str] = None,
    senden: Any = None,
) -> Dict[str, Any]:
    """Den Plan ausfuehren und Bericht, Zaehler und Fehlerlage zurueckgeben.

    ``schreiben=False`` (Standard) ist der Trockenlauf: es wird **nichts**
    gesendet, **nichts** gebucht — die Zaehler zeigen, was ein echter Lauf taete.
    ``ziel_liste`` sind die Manifest-Zeilen fuer die Idempotenz; fehlt sie,
    wird das Manifest gelesen. ``senden`` ist ``httpx.post``-kompatibel (Tests).
    """
    zaehler = {"hochgeladen": 0, "uebersprungen": 0, "fehler": 0}
    zeilen: List[str] = []
    fehler = False

    if ziel_liste is None:
        ziel_liste = manifest_lesen(manifest)
    bekannt = _letzte_pruefsummen(ziel_liste)

    zu_tun = [e for e in plan if e["zustand"] == ZUSTAND_NEU]
    for eintrag in plan:
        if eintrag["zustand"] == ZUSTAND_GLEICH:
            zaehler["uebersprungen"] += 1
            zeilen.append(
                f"{eintrag['name']}: uebersprungen (Pruefsumme gleich, "
                f"{_zahl_de(eintrag['groesse'])} Bytes, sha256 {_kurz(eintrag['pruefsumme'])})")

    if not zu_tun:
        return {"zaehler": zaehler, "zeilen": zeilen, "fehler": False, "trocken": not schreiben}

    if not schreiben:
        for eintrag in zu_tun:
            zaehler["hochgeladen"] += 1
            zeilen.append(
                f"{eintrag['name']}: wuerde hochgeladen ({_zahl_de(eintrag['groesse'])} Bytes, "
                f"sha256 {_kurz(eintrag['pruefsumme'])})")
        return {"zaehler": zaehler, "zeilen": zeilen, "fehler": False, "trocken": True}

    # Echter Lauf: erst den Ordner holen/anlegen (idempotent), dann hochladen.
    folderid = ordner_holen_oder_anlegen(ziel_ordner, token=token, host=host)
    for eintrag in zu_tun:
        try:
            with open(eintrag["quelle"], "rb") as datei:
                daten = datei.read()
            fileid = hochladen(eintrag["name"], daten, folderid,
                               token=token, host=host, senden=senden)
        except (OSError, UebergabeFehler) as problem:
            zaehler["fehler"] += 1
            fehler = True
            zeilen.append(
                f"{eintrag['name']}: FEHLER beim Hochladen: {problem} — nicht gebucht")
            continue
        zaehler["hochgeladen"] += 1
        manifest_anhaengen({
            "name": eintrag["name"],
            "quelle": eintrag["quelle"],
            "ziel": f"{STANDARD_ZIEL}/{eintrag['name']}",
            "groesse": eintrag["groesse"],
            "pruefsumme": eintrag["pruefsumme"],
            "fileid": fileid,
        }, pfad=manifest)
        zeilen.append(
            f"{eintrag['name']}: hochgeladen ({_zahl_de(eintrag['groesse'])} Bytes, "
            f"sha256 {_kurz(eintrag['pruefsumme'])}, fileid {fileid})")

    return {"zaehler": zaehler, "zeilen": zeilen, "fehler": fehler, "trocken": False}


# ── Kommandozeile ─────────────────────────────────────────────────────────

def _argumente(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Ergebnisse kabellos ans Handy geben: Dateien in die pCloud "
                    "laden (Trockenlauf ist Standard). Idempotent ueber Groesse + "
                    "Pruefsumme, Manifest ausserhalb des Repos, Schreiben nur "
                    "unter /Agent/.")
    p.add_argument("--dateien", nargs="*", default=None,
                   help="Dateien, die hochgeladen werden (mehrere moeglich)")
    p.add_argument("--ordner", default=None,
                   help="Ordner, dessen Dateien hochgeladen werden (eine Ebene, nicht rekursiv)")
    p.add_argument("--manifest", default=None,
                   help=f"Ablage des Manifests (Standard {STANDARD_MANIFEST}, nie im Repo)")
    p.add_argument("--alles", action="store_true",
                   help="den Idempotenz-Merker uebergehen und ALLE Dateien hochladen")
    p.add_argument("--schreiben", action="store_true",
                   help="WIRKLICH hochladen (ohne: Trockenlauf)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _argumente(argv)
    schreiben = bool(args.schreiben)

    try:
        quelldateien = dateien_sammeln(args.dateien, args.ordner)
    except UebergabeFehler as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2
    if not quelldateien:
        print("Keine Dateien angegeben (--dateien oder --ordner) — nichts zu tun.")
        return 0

    try:
        ziel_liste = manifest_lesen(args.manifest)
    except UebergabeFehler as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    plan = planen(quelldateien, manifest_eintraege=ziel_liste, alles=bool(args.alles))

    print("Kabellose Uebergabe — " +
          ("TROCKENLAUF (nichts wird geschrieben)" if not schreiben else "HOCHLADEN"))
    print(f"Ziel:   {STANDARD_ZIEL}/")
    print(f"Dateien: {len(plan)}")

    try:
        ergebnis = hochladen_lauf(plan, schreiben=schreiben, ziel_liste=ziel_liste,
                                  manifest=args.manifest)
    except UebergabeFehler as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    for zeile in ergebnis["zeilen"]:
        print("  " + zeile)
    z = ergebnis["zaehler"]
    print(f"hochgeladen {z['hochgeladen']} · uebersprungen {z['uebersprungen']} · Fehler {z['fehler']}")

    if not schreiben:
        print("Zum Ausfuehren: --schreiben anhaengen.")
        return 0
    return 1 if ergebnis["fehler"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
