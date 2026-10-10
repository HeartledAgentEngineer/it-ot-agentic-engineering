"""Kabellose Uebergabe (Handy-Seite): Dateien aus dem pCloud-Ordner holen (10.10.2026).

Dieses Werkzeug ist der Netz-Teil der kabellosen Uebergabe. Es laeuft AUF DEM
HANDY (Termux) und holt die Dateien, die der PC mit
``tools/pcloud/uebergabe_hochladen.py`` in den pCloud-Ordner gelegt hat
(Standard ``/Agent/uebergabe``), in einen Staging-Ordner. Die eigentliche
Uebernahme an ihren Platz (Sicherung, ``.teil``, Pruefsumme, Protokoll) macht
das Shell-Skript ``termux/pcloud-uebernehmen.sh`` — dieselbe Trennung wie
ueberall sonst: Shell steuert, Python spricht mit pCloud.

Verhalten:
    * ``listfolder`` auf den Quellordner (ein Aufruf). Fehlt der Ordner oder ist
      er leer, gibt es eine klare Zeile und Exit 0 (kein Fehler).
    * Je Datei ``getfilelink`` -> Download in ``<ziel>/<name>.teil``, Laenge
      gegen die von pCloud gemeldete Groesse pruefen, dann erst umbenennen: es
      entsteht nie eine halbe Datei im Staging.
    * Die erfolgreich geholten Namen werden EINE je Zeile in ``--liste``
      geschrieben, damit die Shell genau diese uebernimmt.

Grenzen:
    * **Kein Loeschen** (auch nicht im Staging — alte Dateien bleiben liegen).
    * **Kein Schreiben in die pCloud** (nur ``listfolder`` und ``getfilelink``).
    * **Token nie ausgeben.** Er wird aus ``backend/.env`` oder der Umgebung
      gelesen und steht in keiner Ausgabe und keiner Datei.

Exit: IMMER 0 — dieses Werkzeug darf den Start NIEMALS abbrechen. Fehlende
Konfiguration, Netzausfall, leerer Ordner und kaputte Einzeldateien werden als
klare Zeile gemeldet und mit Exit 0 beendet.

Aufruf (auf dem Handy):
    python tools/handy/pcloud_dateien_holen.py --ziel "$HOME/.cache/pcloud_uebergabe" \\
        --liste "$HOME/.cache/pcloud_uebergabe/liste.txt"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

STANDARD_HOST = "eapi.pcloud.com"
STANDARD_ORDNER = "/Agent/uebergabe"
TIMEOUT_STANDARD = 30.0
TIMEOUT_DOWNLOAD = 300.0

# Nur diese zwei Methoden spricht dieses Werkzeug an — beide nur lesend.
ERLAUBTE_METHODEN = ("listfolder", "getfilelink")

ENV_DATEI = Path(__file__).resolve().parents[2] / "backend" / ".env"


def _ohne_geheimnis(text: str, token: str) -> str:
    """Den Token aus einem Text entfernen, falls er hineingeraten ist."""
    if token and token in text:
        return text.replace(token, "***")
    return text


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


def _token_aus_quellen(token: Optional[str], env_pfad: Path) -> str:
    if token is not None:
        return token.strip()
    wert = (os.environ.get("PCLOUD_TOKEN") or "").strip()
    if wert:
        return wert
    return _werte_aus_env_datei(env_pfad).get("PCLOUD_TOKEN", "").strip()


def _host_aus_quellen(host: Optional[str], env_pfad: Path) -> str:
    if host is not None:
        roh = host
    else:
        roh = (
            (os.environ.get("PCLOUD_HOST") or "").strip()
            or _werte_aus_env_datei(env_pfad).get("PCLOUD_HOST", "").strip()
            or STANDARD_HOST
        )
    return roh.split("://")[-1].strip().strip("/") or STANDARD_HOST


def _api(
    methode: str,
    felder: Dict[str, Any],
    *,
    token: str,
    host: str,
    timeout: float = TIMEOUT_STANDARD,
) -> Dict[str, Any]:
    """Ein pCloud-GET-Aufruf (``listfolder``/``getfilelink``) mit Positivliste."""
    if methode not in ERLAUBTE_METHODEN:
        raise RuntimeError(f"Abgewiesen: '{methode}' steht nicht auf der Positivliste.")
    parameter = {name: wert for name, wert in felder.items() if wert is not None}
    parameter["auth"] = token
    url = f"https://{host}/{methode}"
    antwort = httpx.get(url, params=parameter, timeout=timeout)
    if antwort.status_code != 200:
        raise RuntimeError(f"pCloud antwortete mit HTTP {antwort.status_code}.")
    daten = antwort.json()
    if not isinstance(daten, dict):
        raise RuntimeError("pCloud lieferte eine unerwartete Antwort.")
    if daten.get("result") != 0:
        klartext = _ohne_geheimnis(str(daten.get("error") or "ohne Fehlertext"), token)
        raise RuntimeError(f"pCloud meldet Fehler {daten.get('result')}: {klartext}")
    return daten


def _dateien_im_ordner(daten: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Die Dateien (keine Ordner) aus einer listfolder-Antwort."""
    meta = daten.get("metadata") if isinstance(daten.get("metadata"), dict) else {}
    inhalte = meta.get("contents") if isinstance(meta, dict) else None
    ergebnis: List[Dict[str, Any]] = []
    for roh in inhalte if isinstance(inhalte, list) else []:
        if not isinstance(roh, dict) or roh.get("isfolder"):
            continue
        name = str(roh.get("name") or "")
        fileid = roh.get("fileid")
        if not name or not isinstance(fileid, int):
            continue
        ergebnis.append({"name": name, "fileid": fileid, "size": roh.get("size")})
    return sorted(ergebnis, key=lambda e: e["name"])


def _lade_bytes(link: Dict[str, Any], token: str, *, timeout: float = TIMEOUT_DOWNLOAD) -> bytes:
    """Eine Datei ueber den getfilelink-Link herunterladen (ohne auth in der URL)."""
    hosts = [h for h in (link.get("hosts") or []) if h]
    pfad = str(link.get("path") or "")
    if not hosts or not pfad:
        raise RuntimeError("pCloud lieferte keinen Download-Link.")
    letzter = ""
    for host in hosts:
        try:
            antwort = httpx.get(f"https://{host}{pfad}", timeout=timeout)
            if antwort.status_code != 200:
                letzter = f"HTTP {antwort.status_code}"
                continue
            return antwort.content or b""
        except Exception as e:                       # Netzfehler dieses Hosts
            letzter = e.__class__.__name__
            continue
    raise RuntimeError(f"Download fehlgeschlagen ({letzter or 'kein Host erreichbar'}).")


def holen(
    *,
    ordner: str = STANDARD_ORDNER,
    ziel: str,
    liste: Optional[str] = None,
    token: Optional[str] = None,
    host: Optional[str] = None,
    env_pfad: Optional[Path] = None,
    protokoll: Any = None,
) -> Dict[str, Any]:
    """Alle Dateien aus ``ordner`` in den Staging-Ordner ``ziel`` holen.

    ``protokoll`` ist eine Funktion ``(zeile) -> None`` fuer Meldungen (Vorgabe:
    ``print``). Rueckgabe: ``{"geholt": [...], "fehler": [...], "ordner_leer": bool}``.
    """
    melden = protokoll if callable(protokoll) else print
    env_pfad = env_pfad or ENV_DATEI

    geheimnis = _token_aus_quellen(token, env_pfad)
    if not geheimnis:
        melden("PCLOUD-Uebergabe: kein PCLOUD_TOKEN (backend/.env fehlt oder leer) "
               "- nichts geholt, Start laeuft weiter.")
        return {"geholt": [], "fehler": [], "ordner_leer": False}
    ziel_host = _host_aus_quellen(host, env_pfad)

    try:
        daten = _api("listfolder", {"path": ordner}, token=geheimnis, host=ziel_host)
    except Exception as problem:
        melden(f"PCLOUD-Uebergabe: Quellordner {ordner} nicht lesbar "
               f"({problem.__class__.__name__}) - nichts geholt, Start laeuft weiter.")
        return {"geholt": [], "fehler": [], "ordner_leer": False}

    dateien = _dateien_im_ordner(daten)
    if not dateien:
        melden(f"PCLOUD-Uebergabe: Ordner {ordner} ist leer - nichts zu holen.")
        return {"geholt": [], "fehler": [], "ordner_leer": True}

    os.makedirs(ziel, exist_ok=True)
    geholt: List[str] = []
    fehler: List[str] = []
    for eintrag in dateien:
        name, fileid = eintrag["name"], eintrag["fileid"]
        try:
            link = _api("getfilelink", {"fileid": fileid}, token=geheimnis, host=ziel_host)
            rohdaten = _lade_bytes(link, geheimnis)
        except Exception as problem:
            fehler.append(name)
            melden(f"  {name}: FEHLER beim Download ({problem.__class__.__name__}) - uebersprungen")
            continue
        erwartet = eintrag.get("size")
        if isinstance(erwartet, int) and len(rohdaten) != erwartet:
            fehler.append(name)
            melden(f"  {name}: FEHLER Groesse weicht ab (erwartet {erwartet}, "
                   f"erhalten {len(rohdaten)}) - nicht uebernommen")
            continue
        teil = os.path.join(ziel, name + ".teil")
        try:
            with open(teil, "wb") as datei:
                datei.write(rohdaten)
            os.replace(teil, os.path.join(ziel, name))
        except OSError as problem:
            fehler.append(name)
            melden(f"  {name}: FEHLER beim Schreiben ({problem.__class__.__name__})")
            continue
        geholt.append(name)
        melden(f"  {name}: geholt ({len(rohdaten)} Bytes)")

    if liste:
        try:
            with open(liste, "w", encoding="utf-8", newline="\n") as datei:
                for name in geholt:
                    datei.write(name + "\n")
        except OSError as problem:
            melden(f"PCLOUD-Uebergabe: Liste konnte nicht geschrieben werden "
                   f"({problem.__class__.__name__}).")

    melden(f"PCLOUD-Uebergabe: {len(geholt)} geholt, {len(fehler)} Fehler.")
    return {"geholt": geholt, "fehler": fehler, "ordner_leer": False}


def _argumente(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Dateien aus dem pCloud-Ordner ins Staging holen (Handy-Seite).")
    p.add_argument("--ordner", default=STANDARD_ORDNER, help=f"Quellordner (Standard {STANDARD_ORDNER})")
    p.add_argument("--ziel", required=True, help="Staging-Ordner (wird angelegt)")
    p.add_argument("--liste", default=None, help="Datei, in die die geholten Namen kommen (eine je Zeile)")
    p.add_argument("--env", default=None, help="Pfad zu backend/.env (Token/Host); sonst Standard")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _argumente(argv)
    except SystemExit:
        # argparse beendet sich bei fehlenden Argumenten mit 2 — fuer den Start
        # ist aber IMMER 0 richtig ("darf den Start nie verhindern").
        print("PCLOUD-Uebergabe: Aufruf unvollstaendig (--ziel fehlt) - nichts geholt.")
        return 0
    try:
        holen(ordner=args.ordner, ziel=args.ziel, liste=args.liste,
              env_pfad=Path(args.env) if args.env else None)
    except Exception as problem:                     # letzte Absicherung
        print(f"PCLOUD-Uebergabe: unerwarteter Fehler ({problem.__class__.__name__}) "
              "- nichts uebernommen, Start laeuft weiter.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
