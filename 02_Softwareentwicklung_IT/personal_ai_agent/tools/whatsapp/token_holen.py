#!/usr/bin/env python3
"""Holt das Google-Cookie `oauth_token` ueber die CDP-Debug-Schnittstelle eines
laufenden Edge-Browsers (Profil mit angemeldeter Google-Sitzung) und legt den
Wert NUR in token.txt ab.

Warum: ``wabdd token <email>`` braucht den oauth_token von
https://accounts.google.com/EmbeddedSetup (wabdd/commands/token.py). Das Skript
spricht CDP direkt:

  1. http://127.0.0.1:9222/json/version   -> webSocketDebuggerUrl
  2. Target.createTarget(EmbeddedSetup-URL)
  3. Target.attachToTarget(flatten)       -> sessionId
  4. Storage.getCookies                   -> Cookie name=='oauth_token', domain~google

Verhalten bei fehlendem Cookie (wie beauftragt):
  Phase 1: 15 s lang alle 3 s lesen
  Phase 2: 20 s warten, erneut lesen
  Phase 3: https://accounts.google.com/ laden, erneut lesen; sonst rc=2

Geheimnis-Regel: Der Cookie-Wert wird NIE auf stdout/stderr/Logs ausgegeben.
Ausgabe ausschliesslich: gefunden ja/nein, Laenge, Maske (erste 3 + letzte 3
Zeichen) und Zielpfad. Geschrieben wird nur der Wert, eine Zeile, UTF-8.

Offline pruefbar ohne Browser (reine Funktionen):
    from token_holen import filtere_token, waehle_token, maskiere

Exitcodes: 0 = Token gefunden & geschrieben, 2 = kein oauth_token,
           1 = technischer Fehler (Port/Antwort/Datei).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

# --- reine, offline testbare Funktionen -----------------------------------


def maskiere(wert: str) -> str:
    """Maske fuer die Ausgabe: erste 3 + letzte 3 Zeichen, nie der volle Wert."""
    wert = wert or ""
    if len(wert) < 7:
        return "***"
    return f"{wert[:3]}\u2026{wert[-3:]}"


def filtere_token(cookies):
    """Alle Cookies mit name=='oauth_token' und 'google' im Host, mit Wert."""
    treffer = []
    for c in cookies or []:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "")
        domain = str(c.get("domain") or "")
        wert = str(c.get("value") or "")
        if name == "oauth_token" and "google" in domain.lower() and wert:
            treffer.append(c)
    return treffer


def waehle_token(treffer):
    """Aus mehreren oauth_token-Cookies das plausibelste waehlen.

    Rangfolge: accounts.google.com vor .google.com vor sonstigen google-Hosts,
    bei Gleichstand das laengste Cookie. Ohne Treffer: None.
    """
    if not treffer:
        return None

    def rang(c):
        domain = str(c.get("domain") or "").lower().lstrip(".")
        if domain.startswith("accounts.google.com"):
            return 0
        if domain == "google.com":
            return 1
        return 2

    return sorted(treffer, key=lambda c: (rang(c), -len(str(c.get("value") or ""))))[0]


# --- CDP-Anbindung ---------------------------------------------------------


class CdpVerbindung:
    """Minimaler CDP-Client (websocket-client, synchron, ohne Origin-Header)."""

    def __init__(self, ws_url: str, timeout: float = 15.0):
        import websocket  # websocket-client

        self._ws = websocket.create_connection(
            ws_url, timeout=timeout, suppress_origin=True
        )
        self._nr = 0

    def sende(self, method: str, params=None, session_id=None, timeout: float = 15.0):
        import websocket

        self._nr += 1
        nachricht = {"id": self._nr, "method": method}
        if params:
            nachricht["params"] = params
        if session_id:
            nachricht["sessionId"] = session_id
        self._ws.send(json.dumps(nachricht))

        ende = time.time() + timeout
        while True:
            rest = ende - time.time()
            if rest <= 0:
                raise TimeoutError(f"Keine CDP-Antwort fuer {method}")
            self._ws.settimeout(max(0.5, min(rest, 5.0)))
            try:
                roh = self._ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            if not roh:
                continue
            daten = json.loads(roh)
            if daten.get("id") != self._nr:
                continue  # Event oder fremde Antwort -> ignorieren
            if "error" in daten:
                fehler = daten["error"]
                raise RuntimeError(
                    f"CDP-Fehler in {method}: {fehler.get('message', fehler)}"
                )
            return daten.get("result", {})

    def schliesse(self):
        try:
            self._ws.close()
        except Exception:
            pass


def hole_ws_url(port: int) -> str:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/json/version", timeout=6
    ) as antwort:
        daten = json.loads(antwort.read().decode("utf-8"))
    url = daten.get("webSocketDebuggerUrl")
    if not url:
        raise RuntimeError("webSocketDebuggerUrl fehlt in /json/version")
    return url


def lese_cookies(verb: CdpVerbindung, session_id: str):
    """Storage.getCookies – bevorzugt in der (flattened) Tab-Session."""
    try:
        ergebnis = verb.sende("Storage.getCookies", session_id=session_id)
    except RuntimeError:
        ergebnis = verb.sende("Storage.getCookies")
    return ergebnis.get("cookies", [])


def google_diagnose(cookies) -> str:
    """Klartext-Diagnose ohne Geheimnisse: Anzahl + Namen der Google-Cookies."""
    namen = sorted(
        {
            str(c.get("name") or "")
            for c in cookies or []
            if isinstance(c, dict) and "google" in str(c.get("domain") or "").lower()
        }
    )
    sitzung = [n for n in namen if n in ("SID", "HSID", "SSID", "SAPISID")]
    return (
        f"google-cookies: {len(namen)} namen: {', '.join(namen) if namen else '(keine)'} "
        f"| kontositzung (SID/HSID/SSID/SAPISID): {'ja' if sitzung else 'nein'}"
    )


# --- Hauptlauf -------------------------------------------------------------


def standard_ziel() -> Path:
    """token.txt im WhatsApp-Ordner (aus der Skriptposition abgeleitet)."""
    workspace = Path(__file__).resolve().parents[4]
    return (
        workspace
        / "Chats von GPT, GEMINI, Claude"
        / "whatsapp_uebertragung"
        / "token.txt"
    )


def hauptlauf(port: int, ziel: Path) -> int:
    ws_url = hole_ws_url(port)
    print(f"CDP verbunden: port {port}")

    verb = CdpVerbindung(ws_url)
    try:
        probe = verb.sende("Target.createTarget", {
            "url": "https://accounts.google.com/EmbeddedSetup",
            "background": True,
        }, timeout=20)
        target_id = probe.get("targetId")
        if not target_id:
            raise RuntimeError("Target.createTarget lieferte keine targetId")
        print("EmbeddedSetup-Tab geoeffnet (Hintergrund)")

        anhang = verb.sende(
            "Target.attachToTarget", {"targetId": target_id, "flatten": True}
        )
        session_id = anhang.get("sessionId")
        if not session_id:
            raise RuntimeError("attachToTarget lieferte keine sessionId")

        def versuch():
            treffer = filtere_token(lese_cookies(verb, session_id))
            return waehle_token(treffer)

        # Phase 1: 15 s beobachten (EmbeddedSetup setzt das Cookie beim Laden)
        token = None
        for nr in range(6):
            token = versuch()
            if token:
                break
            if nr < 5:
                time.sleep(3)
        if not token:
            print("oauth_token noch nicht da - Phase 1 (15 s) erschoepft")

        # Phase 2: 20 s warten, erneut lesen
        if not token:
            time.sleep(20)
            token = versuch()
            if not token:
                print("oauth_token auch nach 20 s Wartezeit nicht da")

        # Phase 3: accounts.google.com laden, erneut lesen
        if not token:
            try:
                verb.sende("Page.enable", session_id=session_id)
                verb.sende(
                    "Page.navigate",
                    {"url": "https://accounts.google.com/"},
                    session_id=session_id,
                )
                print("accounts.google.com geladen - letzter Leseversuch")
            except (RuntimeError, TimeoutError) as fehler:
                print(f"Hinweis: Navigation nicht moeglich ({fehler})")
            for _ in range(4):
                time.sleep(4)
                token = versuch()
                if token:
                    break

        if not token:
            cookies = lese_cookies(verb, session_id)
            print(f"gefunden: nein rc=2 ({google_diagnose(cookies)})")
            return 2

        wert = str(token.get("value") or "").strip()
        if not wert:
            print("gefunden: nein rc=2 (Cookie ohne Wert)")
            return 2

        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(wert + "\n", encoding="utf-8")

        print("gefunden: ja")
        print(f"laenge: {len(wert)}")
        print(f"maske: {maskiere(wert)}")
        print(f"geschrieben nach: {ziel}")
        return 0
    finally:
        verb.schliesse()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Google-oauth_token per CDP aus dem Edge-Profil holen -> token.txt"
    )
    parser.add_argument("--port", type=int, default=9222, help="CDP-Port (default 9222)")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Zieldatei fuer den Cookie-Wert (default: whatsapp_uebertragung/token.txt)",
    )
    args = parser.parse_args(argv)

    ziel = args.out if args.out else standard_ziel()
    try:
        return hauptlauf(args.port, ziel)
    except Exception as fehler:  # noqa: BLE001 - sauberer technischer Fehler
        print(f"technischer Fehler rc=1: {type(fehler).__name__}: {fehler}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
