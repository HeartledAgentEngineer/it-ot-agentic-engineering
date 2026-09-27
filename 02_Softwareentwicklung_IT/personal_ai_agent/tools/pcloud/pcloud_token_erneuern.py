"""Holt den pCloud-Zugang neu und prueft ihn — Selbstheilung fuer den Token.

Warum es dieses Werkzeug gibt (Sebastian, 26.09.2026):
  „Wir muessen diese Token-Generierung / Authentifizierung so einrichten, wenn
  das nun abgelaufen ist." Der Token laeuft laut pCloud-Doku nicht ab, ist aber
  WIDERRUFLICH: Abmelden im pCloud-Client, Passwortaenderung oder Sitzungen
  beenden machen ihn ungueltig. Dann hilft genau ein Befehl — statt neuer
  Anmeldung, App-Registrierung oder Google-Umweg.

Zwei Betriebsarten:
  --pruefen   prüft NUR den Token aus backend/.env (kein Lesen des Client-Speichers)
  (ohne)     liest den Anmelde-Wert aus dem pCloud-Client-Speicher, prüft ihn und
             schreibt ihn nach backend/.env

Der Token wird NIEMALS ausgegeben — weder ganz noch gekuerzt.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request

STANDARD_CLIENT_DB = os.path.join(
    os.environ.get("LOCALAPPDATA", ""), "pCloud", "data.db")
STANDARD_ENV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "backend", ".env")
EU_HOST = "eapi.pcloud.com"


def aus_env(env_pfad: str) -> tuple[str | None, str]:
    """Liest PCLOUD_TOKEN/PCLOUD_HOST aus der .env — ohne etwas auszugeben."""
    token, host = None, EU_HOST
    if not os.path.exists(env_pfad):
        return None, host
    with open(env_pfad, "r", encoding="utf-8") as datei:
        for zeile in datei:
            zeile = zeile.strip()
            if zeile.startswith("PCLOUD_TOKEN="):
                token = zeile.split("=", 1)[1]
            elif zeile.startswith("PCLOUD_HOST="):
                host = zeile.split("=", 1)[1] or EU_HOST
    return token, host


def in_env_schreiben(env_pfad: str, token: str, host: str) -> None:
    zeilen: list[str] = []
    if os.path.exists(env_pfad):
        with open(env_pfad, "r", encoding="utf-8") as datei:
            zeilen = [z.rstrip("\n") for z in datei
                      if not z.startswith(("PCLOUD_TOKEN=", "PCLOUD_HOST="))]
    zeilen += [f"PCLOUD_TOKEN={token}", f"PCLOUD_HOST={host}"]
    with open(env_pfad, "w", encoding="utf-8") as datei:
        datei.write("\n".join(zeilen) + "\n")


def aus_client(client_db: str) -> dict:
    """Liest auth/location_id/userid aus dem Client-Speicher — nur lesend.

    ``immutable=1``: der laufende Client haelt die Datei gesperrt; so wird sie
    gelesen, ohne ihn zu stoeren oder zu warten.
    """
    if not os.path.exists(client_db):
        raise FileNotFoundError(f"pCloud-Client-Speicher nicht gefunden: {client_db}")
    con = sqlite3.connect(f"file:{client_db}?immutable=1", uri=True)
    try:
        def hole(schluessel: str):
            zeile = con.execute("select value from setting where id=?",
                                (schluessel,)).fetchone()
            return zeile[0] if zeile else None
        return {
            "auth": hole("auth"),
            "location_id": hole("location_id"),
            "userid": hole("userid"),
        }
    finally:
        con.close()


def maske(text: str | None) -> str:
    if not text:
        return "(leer)"
    if len(text) <= 6:
        return text[0] + "***"
    return text[:2] + "*" * (len(text) - 6) + text[-4:]


def api(host: str, pfad: str, **felder) -> dict:
    url = f"https://{host}/{pfad}?" + urllib.parse.urlencode(felder)
    with urllib.request.urlopen(url, timeout=30) as antwort:
        return json.load(antwort)


def berichte(daten: dict) -> bool:
    """Gibt Kontodaten MASKIERT aus. Rueckgabe: Token gueltig?"""
    if daten.get("result") != 0:
        print(f"  ABGELEHNT: result={daten.get('result')} error={daten.get('error')}")
        return False
    print(f"  E-Mail: {maske(daten.get('email'))}   userid: {daten.get('userid')}")
    print(f"  Quota:  {round((daten.get('quota') or 0) / 1e9, 1)} GB, belegt "
          f"{round((daten.get('usedquota') or 0) / 1e9, 1)} GB")
    print(f"  Konto:  premium={daten.get('premium')} "
          f"emailverified={daten.get('emailverified')}")
    return True


def main(argv: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--pruefen", action="store_true",
                          help="nur den Token aus der .env prüfen, nichts ändern")
    zerleger.add_argument("--client-db", default=STANDARD_CLIENT_DB)
    zerleger.add_argument("--env", default=STANDARD_ENV)
    args = zerleger.parse_args(argv)

    if args.pruefen:
        token, host = aus_env(args.env)
        if not token:
            print(f"Kein PCLOUD_TOKEN in {args.env} gefunden.")
            return 2
        print(f"Prüfe vorhandenen Token gegen https://{host} ...")
        gueltig = berichte(api(host, "userinfo", auth=token))
        print("Ergebnis:", "gültig" if gueltig else "UNGÜLTIG — neu holen")
        return 0 if gueltig else 3

    print(f"Lese Anmelde-Wert aus dem pCloud-Client-Speicher: {args.client_db}")
    try:
        aus = aus_client(args.client_db)
    except (FileNotFoundError, sqlite3.Error) as problem:
        print(f"Fehlgeschlagen: {problem}")
        print("Ist der pCloud-Client installiert und angemeldet?")
        return 4

    token = aus.get("auth")
    if not token:
        print("Kein 'auth'-Eintrag gefunden — der Client ist wohl nicht angemeldet.")
        return 5
    print(f"Gefunden: {len(token)} Zeichen im Feld 'auth' "
          f"(Konto-Nr. {aus.get('userid')}, location_id {aus.get('location_id')})")

    host = EU_HOST if str(aus.get("location_id")) == "2" else "api.pcloud.com"
    print(f"Probe gegen https://{host}/userinfo ...")
    if not berichte(api(host, "userinfo", auth=token)):
        return 6

    in_env_schreiben(args.env, token, host)
    print(f"\nIn {args.env} eingetragen (PCLOUD_TOKEN, PCLOUD_HOST={host}).")
    print("Der Wert wurde nirgends ausgegeben.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
