"""Prueft, ob sich die Edge-Cookies entschluesseln lassen (ohne Werte auszugeben).

Chromium legt Cookie-Werte verschluesselt ab. Zwei Varianten:
  v10 = mit Windows-Benutzerschluessel (DPAPI) -> entschluesselbar
  v20 = zusaetzlich an den Browser-Prozess gebunden (App-Bound) -> nur im
        laufenden Browser lesbar, NICHT aus der Datei
Dieses Skript zaehlt nur: wie viele Cookies v10/v20 sind und ob DPAPI klappt.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import shutil
import sqlite3
import tempfile
from pathlib import Path

COOKIES = Path.home() / "AppData/Local/Microsoft/Edge/User Data/Default/Network/Cookies"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def dpapi(b: bytes) -> bytes:
    puffer = ctypes.create_string_buffer(b, len(b))
    rein = DATA_BLOB(len(b), ctypes.cast(puffer, ctypes.POINTER(ctypes.c_char)))
    raus = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(rein), None, None, None, None, 0, ctypes.byref(raus)
    )
    if not ok:
        raise OSError("DPAPI hat abgelehnt")
    return ctypes.string_at(raus.pbData, raus.cbData)


if not COOKIES.exists():
    raise SystemExit("Edge-Cookie-Datei nicht gefunden")

ziel = Path(tempfile.mkdtemp(prefix="edge_cookies_")) / "Cookies"
try:
    shutil.copy2(COOKIES, ziel)
    kopie = "kopiert"
except Exception as fehler:
    raise SystemExit(f"Datei nicht lesbar: {type(fehler).__name__}")

con = sqlite3.connect(f"file:{ziel}?mode=ro", uri=True)
zeilen = con.execute("SELECT host_key, name, encrypted_value FROM cookies").fetchall()
con.close()

zahlen = {"v10": 0, "v20": 0, "leer": 0, "anders": 0}
klappt = 0
scheitert = 0
google = 0
for host, name, wert in zeilen:
    if "google.com" in (host or ""):
        google += 1
    if not wert:
        zahlen["leer"] += 1
        continue
    kennung = wert[:3].decode("ascii", "ignore")
    if kennung not in ("v10", "v20"):
        zahlen["anders"] += 1
        continue
    zahlen[kennung] += 1
    if kennung == "v10":
        try:
            dpapi(wert[3:])
            klappt += 1
        except Exception:
            scheitert += 1

print(f"Kopie des Cookie-Speichers: {kopie}")
print(f"Cookies gesamt: {len(zeilen)}  (google.com: {google})")
print(f"  v10 (DPAPI):    {zahlen['v10']}   davon entschluesselt: {klappt}, fehlgeschlagen: {scheitert}")
print(f"  v20 (gebunden): {zahlen['v20']}")
print(f"  leer/anders:    {zahlen['leer']} / {zahlen['anders']}")
print()
if zahlen["v10"] and scheitert == 0 and zahlen["v20"] == 0:
    print("ERGEBNIS: aus der Datei lesbar -> Zugang kann direkt gelesen werden.")
elif zahlen["v20"]:
    print("ERGEBNIS: Cookie-Werte sind an den Browser gebunden (v20) -> nur ueber die")
    print("          laufende Steuerschnittstelle lesbar, nicht aus der Datei.")
else:
    print("ERGEBNIS: teils entschluesselbar - Details oben, bitte melden.")
