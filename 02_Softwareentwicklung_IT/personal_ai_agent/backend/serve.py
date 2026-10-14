"""Ein Prozess, zwei Zugänge (HTTPS-Plan H3, 14.10.2026).

Mit Zertifikat (``~/.agent_tls/server.crt``, ``server.key`` **und** ``ca.crt``):

* HTTP  ``127.0.0.1:8080`` — App-Hülle und Browser am Handy (Loopback, H1).
* HTTPS ``0.0.0.0:8443``   — PC und Tablet im Heim-WLAN (Anmelden, H2).

Fehlt eine der drei Dateien, startet nur HTTP auf ``HOST_BIND`` (wie bisher).
Dieselbe Drei-Dateien-Bedingung prüft ``termux/backend-starten.sh`` (``tls_bereit``).

Beide Zugänge teilen dasselbe ``app``-Objekt. Die ``lifespan`` der App (Start
und Stopp der Hintergrundarbeit) läuft nur im ersten Zugang; der zweite startet
erst, wenn der erste bereit ist. ``proxy_headers`` ist aus: Weder Adresse noch
Schema dürfen aus Kopfzeilen kommen (H1 prüft die echte Gegenstelle, H2 das
echte Schema). ``--reload`` gibt es in diesem Modus nicht.

Aufruf (aus ``backend/``):  ``python serve.py``
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import List

import uvicorn

TLS_DATEIEN = ("server.crt", "server.key", "ca.crt")
PORT_HTTP = 8080
PORT_HTTPS = 8443
APP = "app.main:app"


def tls_ordner() -> Path:
    return Path(os.environ.get("AGENT_TLS_ORDNER") or Path.home() / ".agent_tls")


def tls_bereit(ordner: Path) -> bool:
    """Alle drei Dateien vorhanden und nicht leer."""
    try:
        return all((ordner / name).is_file() and (ordner / name).stat().st_size > 0
                   for name in TLS_DATEIEN)
    except OSError:
        return False


def konfigurationen(ordner: Path, host_bind: str = "0.0.0.0", app: object = APP
                    ) -> List[uvicorn.Config]:
    """Die erste Konfiguration führt die lifespan aus, alle weiteren nicht."""
    gemeinsam = dict(proxy_headers=False, server_header=False, log_level="info")
    if not tls_bereit(ordner):
        return [uvicorn.Config(app, host=host_bind, port=PORT_HTTP, lifespan="on", **gemeinsam)]
    return [
        uvicorn.Config(app, host="127.0.0.1", port=PORT_HTTP, lifespan="on", **gemeinsam),
        uvicorn.Config(app, host="0.0.0.0", port=PORT_HTTPS, lifespan="off",
                       ssl_certfile=str(ordner / "server.crt"),
                       ssl_keyfile=str(ordner / "server.key"), **gemeinsam),
    ]


async def laufen(configs: List[uvicorn.Config]) -> None:
    server = [uvicorn.Server(c) for c in configs]
    aufgaben = [asyncio.create_task(server[0].serve())]
    while not server[0].started and not aufgaben[0].done():
        await asyncio.sleep(0.05)
    if aufgaben[0].done():                       # erster Zugang kam nicht hoch
        await aufgaben[0]
        return
    aufgaben += [asyncio.create_task(s.serve()) for s in server[1:]]
    _, offen = await asyncio.wait(aufgaben, return_when=asyncio.FIRST_COMPLETED)
    for s in server:                             # endet einer, enden alle
        s.should_exit = True
    if offen:
        await asyncio.wait(offen)


def host_bind_lesen() -> str:
    """``HOST_BIND`` aus der Umgebung (``backend-starten.sh`` liest die .env), sonst 0.0.0.0."""
    return (os.environ.get("HOST_BIND") or "").strip() or "0.0.0.0"


def main() -> int:
    ordner = tls_ordner()
    configs = konfigurationen(ordner, host_bind_lesen())
    if len(configs) == 2:
        print("Zugänge: HTTP 127.0.0.1:8080 (Gerät), HTTPS 0.0.0.0:8443 (Heimnetz)")
    else:
        print(f"Zugang: HTTP {configs[0].host}:{PORT_HTTP} (kein Zertifikat vollständig)")
    asyncio.run(laufen(configs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
