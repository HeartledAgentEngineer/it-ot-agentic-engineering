"""Schutz gegen Zugriff fremder Webseiten (P0, 12.10.2026).

Befund vor P0 (gemessen mit dem TestClient und einem Attrappen-Schlüssel):
Jede Webseite, die Sebastian im Browser öffnete, konnte über
``http://127.0.0.1:8080`` den API-Schlüssel abholen und danach alle Daten lesen.
CORS stand auf ``*`` mit Zugangsdaten, und kein Teil prüfte die Herkunft einer
Anfrage oder den Host-Namen (DNS-Rebinding).

Diese Middleware erledigt drei Dinge für JEDE Antwort:

1. **Host-Prüfung (alle Pfade):** Erlaubt sind ``localhost``, jedes IP-Literal
   und die Namen aus ``ERLAUBTE_HOSTS``. Alles andere bekommt 400. Ein
   DNS-Rebinding braucht einen Domainnamen; mit einer IP-Adresse geht es nicht.
2. **Herkunftsprüfung (Programmrouten):** Für ``/api/…`` sowie ``/health``,
   ``/ping`` und ``/status`` gibt es 403 bei ``Sec-Fetch-Site: cross-site`` oder
   ``same-site`` und bei einem fremden ``Origin``. Anfragen ohne diese Köpfe
   (Werkzeuge, Termux-Skripte, Tests) gehen durch; für sie gelten weiter
   Schlüssel und Bindung.
3. **Sicherheitskopfzeilen** auf allen Antworten (CSP, nosniff, Referrer,
   Frame-Sperre, CORP).

Reine ASGI-Middleware statt ``BaseHTTPMiddleware``: Sie greift nur in den
Antwortkopf ein und lässt Streams (``/api/chat/stream``) ungepuffert durch.
"""
from __future__ import annotations

import html
import ipaddress
import logging
from collections import Counter
from typing import Dict, Optional, Set, Tuple
from urllib.parse import urlsplit

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

#: Positivliste: Nur diese Dateien liefert der Server aus dem Frontend-Ordner aus.
#: Alles andere (Tests, Sicherungskopien, wecken.js) bekommt 404.
FRONTEND_DATEIEN = frozenset({
    "index.html", "hermes_status.html", "hermes_status.js",
    "app.js", "erzaehlen.js", "gruppen_quiz.js", "pcm-recorder.js", "sw.js",
    "style.css", "manifest.json", "icon-192.png", "icon-512.png",
})

#: In diese zwei Seiten setzt der Server den API-Schlüssel ein (Meta-Feld).
SCHLUESSEL_SEITEN = frozenset({"index.html", "hermes_status.html"})
SCHLUESSEL_PLATZHALTER = '<meta name="agent-schluessel" content="">'

#: Pfade außerhalb von ``/api``, die ebenfalls nur von der eigenen Seite kommen dürfen.
GEPRUEFTE_PFADE = frozenset({"/api", "/health", "/ping", "/status"})

#: Inhaltsrichtlinie: nur eigene Skripte; ``blob:`` nur für Bilder und Ton.
CSP = "; ".join((
    "default-src 'self'",
    "script-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "img-src 'self' blob: data:",
    "media-src 'self' blob:",
    "connect-src 'self'",
    "style-src 'self' 'unsafe-inline'",
))

SICHERHEITS_KOEPFE: Dict[str, str] = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Resource-Policy": "same-origin",
}

_STANDARD_PORT = {"http": 80, "https": 443, "ws": 80, "wss": 443}

#: Abweisungen je Grund seit dem Start; ``/api/selbsttest`` zeigt sie an.
abgewiesen: Counter = Counter()


def host_zerlegen(host_kopf: str) -> Optional[Tuple[str, Optional[int]]]:
    """``Host``-Kopf → (Name, Port). Name klein, ohne Klammern und Schlusspunkt.

    ``"[::1]:8080"`` → ``("::1", 8080)``, ``"LocalHost.:80"`` → ``("localhost", 80)``.
    Unbrauchbares (leer, kaputte Klammer, Port keine Zahl) → ``None``.
    """
    h = (host_kopf or "").strip()
    if not h:
        return None
    port_text = ""
    if h.startswith("["):
        ende = h.find("]")
        if ende == -1:
            return None
        name, rest = h[1:ende], h[ende + 1:]
        if rest:
            if not rest.startswith(":"):
                return None
            port_text = rest[1:]
    elif h.count(":") == 1:
        name, port_text = h.split(":")
    else:
        name = h  # ohne Port; ein nacktes IPv6-Literal prüft host_erlaubt
    # Nur ASCII-Ziffern: isdigit() nimmt auch „²“ an, int() scheitert dann
    # (Codex-Einwand R2: 500 statt 400).
    if port_text and not (port_text.isascii() and port_text.isdigit()):
        return None
    name = name.lower().rstrip(".")
    if not name:
        return None
    return name, (int(port_text) if port_text else None)


def _einstellung(name: str) -> str:
    """Einstellung bei JEDER Anfrage frisch lesen (Tests ändern sie zur Laufzeit)."""
    from app.config import settings  # spät importiert: immer das aktuelle Modul

    return getattr(settings, name, "") or ""


def erlaubte_hosts() -> Set[str]:
    """Zusätzliche Namen aus ``ERLAUBTE_HOSTS`` (Komma-Liste)."""
    roh = _einstellung("erlaubte_hosts")
    return {n.strip().lower().rstrip(".") for n in roh.split(",") if n.strip()}


def cors_herkunft() -> Set[str]:
    """Fremde Seiten aus ``CORS_HERKUNFT``, die ausdrücklich lesen dürfen. ``*`` zählt nie."""
    roh = _einstellung("cors_herkunft")
    return {h.strip().lower().rstrip("/") for h in roh.split(",")
            if h.strip() and h.strip() != "*"}


def schluessel_einsetzen(seite: str, schluessel: Optional[str]) -> str:
    """Setzt den Schlüssel maskiert in das leere Meta-Feld der Seite ein."""
    wert = html.escape(schluessel or "", quote=True)
    return seite.replace(SCHLUESSEL_PLATZHALTER,
                         f'<meta name="agent-schluessel" content="{wert}">', 1)


def host_erlaubt(name: Optional[str]) -> bool:
    """``localhost``, IP-Literale und ``ERLAUBTE_HOSTS`` sind erlaubt."""
    if not name:
        return False
    if name == "localhost":
        return True
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        pass
    return name in erlaubte_hosts()


def origin_ist_eigen(origin: str, schema: str, host_kopf: str) -> bool:
    """Stimmt ``Origin`` mit der eigenen Herkunft (Schema + geprüfter Host) überein?"""
    eigen = host_zerlegen(host_kopf)
    if eigen is None:
        return False
    try:
        teile = urlsplit((origin or "").strip())
        o_port = teile.port
    except ValueError:
        return False
    o_schema = (teile.scheme or "").lower()
    o_name = (teile.hostname or "").lower().rstrip(".")
    if not o_schema or not o_name:
        return False  # auch "null" (Sandbox, Datei) ist fremd
    schema = (schema or "http").lower()
    eigen_name, eigen_port = eigen
    return (
        o_schema == schema
        and o_name == eigen_name
        and (o_port or _STANDARD_PORT.get(o_schema))
        == (eigen_port or _STANDARD_PORT.get(schema))
    )


def ist_geprueft(pfad: str) -> bool:
    """Gilt die Herkunftsprüfung für diesen Pfad?"""
    return pfad in GEPRUEFTE_PFADE or pfad.startswith("/api/")


def abweisungsgrund(scope: Scope) -> Optional[Tuple[str, int]]:
    """(Grund, Statuscode) oder ``None``, wenn die Anfrage durchdarf."""
    koepfe: Dict[str, str] = {}
    for k, v in scope.get("headers") or []:
        koepfe[k.decode("latin-1").lower()] = v.decode("latin-1")
    host_kopf = koepfe.get("host", "")
    teile = host_zerlegen(host_kopf)
    if teile is None or not host_erlaubt(teile[0]):
        return "host", 400
    if not ist_geprueft(scope.get("path") or ""):
        return None
    origin = koepfe.get("origin")
    if origin is not None and origin.strip().lower().rstrip("/") in cors_herkunft():
        return None  # von Sebastian ausdrücklich freigegebene fremde Seite
    herkunft = koepfe.get("sec-fetch-site", "").strip().lower()
    if herkunft in ("cross-site", "same-site"):
        return herkunft, 403
    if origin is not None and not origin_ist_eigen(
        origin, scope.get("scheme", "http"), host_kopf
    ):
        return "origin", 403
    return None


class SicherheitsMiddleware:
    """Host- und Herkunftsprüfung plus Sicherheitskopfzeilen (siehe Modulkopf)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Das Backend hat keine Websockets; lifespan und Co. laufen unverändert durch.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            befund = abweisungsgrund(scope)
        except Exception:
            # Ein unerwartet geformter Kopf darf nie zu einer 500 ohne
            # Kopfzeilen führen: dann gilt der Host als ungültig.
            logger.exception("Host-/Herkunftsprüfung gescheitert")
            befund = ("host", 400)
        if befund is not None:
            grund, status = befund
            abgewiesen[grund] += 1
            # Nur Grund, Methode und Pfad – nie Kopfwerte.
            logger.warning("Anfrage abgewiesen (%s): %s %s", grund,
                           scope.get("method"), scope.get("path"))
            antwort = PlainTextResponse("Abgewiesen.", status_code=status,
                                        headers=SICHERHEITS_KOEPFE)
            await antwort(scope, receive, send)
            return

        gestartet = False

        async def mit_koepfen(message: Message) -> None:
            nonlocal gestartet
            if message["type"] == "http.response.start":
                gestartet = True
                roh = list(message.get("headers") or [])
                vorhanden = {k.lower() for k, _ in roh}
                for name, wert in SICHERHEITS_KOEPFE.items():
                    schluessel = name.lower().encode("latin-1")
                    if schluessel not in vorhanden:
                        roh.append((schluessel, wert.encode("latin-1")))
                message = {**message, "headers": roh}
            await send(message)

        try:
            await self.app(scope, receive, mit_koepfen)
        except Exception:
            # Sonst beantwortet Starlettes äußere Fehlerbehandlung den Absturz
            # mit einer 500 ohne Sicherheitskopfzeilen. Die Antwort kommt deshalb
            # von hier; der Fehler geht weiter, damit der Server ihn loggt.
            if not gestartet:
                antwort = PlainTextResponse("Internal Server Error", status_code=500,
                                            headers=SICHERHEITS_KOEPFE)
                await antwort(scope, receive, send)
            raise
