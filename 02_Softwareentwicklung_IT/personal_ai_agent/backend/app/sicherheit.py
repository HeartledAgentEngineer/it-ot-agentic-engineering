"""Schutz gegen Zugriff fremder Webseiten (P0, 12.10.2026).

Befund vor P0 (gemessen mit dem TestClient und einem Attrappen-Schlüssel):
Jede Webseite, die Sebastian im Browser öffnete, konnte über
``http://127.0.0.1:8080`` den API-Schlüssel abholen und danach alle Daten lesen.
CORS stand auf ``*`` mit Zugangsdaten, und kein Teil prüfte die Herkunft einer
Anfrage oder den Host-Namen (DNS-Rebinding).

Diese Middleware erledigt drei Dinge für JEDE Antwort:

1. **Host-Prüfung (alle Pfade):** Erlaubt sind ``localhost``/Loopback, private
   Heimnetz-IP-Adressen, ``100.64.0.0/10`` und ausdrücklich konfigurierte Namen
   aus ``ERLAUBTE_HOSTS``. Öffentliche IP-Adressen und andere Namen bekommen 400.
   Ein DNS-Rebinding braucht einen Domainnamen; beliebige Namen bleiben gesperrt.
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
    "anmelden.js", "app.js", "erzaehlen.js", "gruppen_quiz.js", "pcm-recorder.js", "sw.js",
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

#: Die Tailscale-Adresse wird explizit aufgeführt: 100.64.0.0/10 ist
#: „Shared Address Space“ und nicht in jeder Python-Version ``is_private``.
_TAILSCALE_NETZ = ipaddress.ip_network("100.64.0.0/10")
_LOKALE_NETZE = tuple(ipaddress.ip_network(netz) for netz in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "169.254.0.0/16", "fc00::/7", "fe80::/10",
))

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
    """Zusätzliche, exakt erlaubte Namen aus ``ERLAUBTE_HOSTS`` (Komma-Liste)."""
    roh = _einstellung("erlaubte_hosts")
    hosts = {"myagent"}
    hosts.update(
        n.strip().lower().rstrip(".")
        for n in roh.split(",")
        if n.strip() and not n.strip().startswith("*.")
    )
    return hosts


def erlaubte_tailnet_domaenen() -> Set[str]:
    """Explizit eingetragene Tailnet-Suffixe ``*.<tailnet>.ts.net``."""
    roh = _einstellung("erlaubte_hosts")
    suffixe: Set[str] = {"tailba05b5.ts.net"}
    for eintrag in roh.split(","):
        muster = eintrag.strip().lower().rstrip(".")
        if not muster.startswith("*."):
            continue
        suffix = muster[2:]
        labels = suffix.split(".")
        # Nie ``*.ts.net`` freigeben: Das würde alle Tailscale-Tailnets erfassen.
        # Die konkrete Tailnet-Domain muss ausdrücklich konfiguriert sein.
        if (len(labels) < 3 or labels[-2:] != ["ts", "net"]
                or any(not label or len(label) > 63 or not label.isascii()
                       or not label[0].isalnum() or not label[-1].isalnum()
                       or not label.replace("-", "").isalnum()
                       for label in labels)):
            continue
        suffixe.add(suffix)
    return suffixe


def cors_herkunft() -> Set[str]:
    """Fremde Seiten aus ``CORS_HERKUNFT``, die ausdrücklich lesen dürfen. ``*`` zählt nie."""
    roh = _einstellung("cors_herkunft")
    return {h.strip().lower().rstrip("/") for h in roh.split(",")
            if h.strip() and h.strip() != "*"}


def client_ist_loopback(scope: Scope) -> bool:
    """Kommt die Verbindung vom Gerät selbst (127.0.0.0/8, ::1)? (HTTPS-Plan H1, 14.10.2026)

    Gelesen wird nur die Gegenstelle der Verbindung (``scope["client"]``), nie ein
    Header wie ``X-Forwarded-For`` — den kann jeder Client im WLAN frei setzen.
    Unbekannt oder kein IP-Literal gilt als NICHT Loopback.
    """
    client = scope.get("client")
    host = client[0] if isinstance(client, (tuple, list)) and client else ""
    try:
        adresse = ipaddress.ip_address(str(host))
    except ValueError:
        return False
    abgebildet = getattr(adresse, "ipv4_mapped", None)
    return bool((abgebildet or adresse).is_loopback)


def schluessel_einsetzen(seite: str, schluessel: Optional[str]) -> str:
    """Setzt den Schlüssel maskiert in das leere Meta-Feld der Seite ein."""
    wert = html.escape(schluessel or "", quote=True)
    return seite.replace(SCHLUESSEL_PLATZHALTER,
                         f'<meta name="agent-schluessel" content="{wert}">', 1)


def host_erlaubt(name: Optional[str]) -> bool:
    """Loopback, lokale Netze, Tailscale und ausdrücklich erlaubte Namen prüfen."""
    if not name:
        return False
    if name == "localhost":
        return True
    try:
        adresse = ipaddress.ip_address(name)
    except ValueError:
        adresse = None
    if adresse is not None:
        # Private Heimnetz-Adressen bleiben für HTTPS erreichbar; dazu kommt
        # ausdrücklich Tailscales Shared Address Space. Beliebige öffentliche
        # IP-Hosts werden nicht benötigt und daher abgewiesen.
        adresse = getattr(adresse, "ipv4_mapped", None) or adresse
        try:
            return (
                adresse.is_loopback
                or (adresse.version == 4 and adresse in _TAILSCALE_NETZ)
                or any(adresse.version == netz.version and adresse in netz
                       for netz in _LOKALE_NETZE)
            )
        except (TypeError, ValueError):
            return False
    if name in erlaubte_hosts():
        return True
    # Hostnamen bleiben eine Positivliste: kurze Alias-Namen müssen exakt
    # genannt sein; ein Wildcard gilt nur für eine konkret eingetragene
    # ``*.<tailnet>.ts.net``-Domain, niemals für fremde DNS-Namen.
    return any(name.endswith("." + suffix) for suffix in erlaubte_tailnet_domaenen())


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


def _hostkopf(scope: Scope) -> str:
    """Liest den letzten Host-Kopf wie ``abweisungsgrund`` ihn bewertet."""
    host = ""
    for schluessel, wert in scope.get("headers") or []:
        try:
            if schluessel.decode("latin-1").lower() == "host":
                host = wert.decode("latin-1")
        except (AttributeError, UnicodeError):
            continue
    return host


def _host_anzeige(host_kopf: str) -> str:
    """Begrenzt Steuerzeichen/Länge, bevor ein ungeprüfter Host angezeigt wird."""
    roh = (host_kopf or "").strip()
    if not roh:
        return "(leer)"
    if any(not zeichen.isprintable() for zeichen in roh):
        roh = repr(roh)
    if len(roh) > 253:
        roh = roh[:253] + "…"
    return roh


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
            if grund == "host":
                host = _host_anzeige(_hostkopf(scope))
                logger.warning("Anfrage abgewiesen (Host=%r): %s %s", host,
                               scope.get("method"), scope.get("path"))
                inhalt = (
                    f"Abgewiesen.\nAbgelehnter Host: {host}\n"
                    "Erlaubt: localhost/Loopback, private Heimnetz-IP, "
                    "Tailscale-IP 100.64.0.0/10 und Namen aus ERLAUBTE_HOSTS "
                    "in backend/.env."
                )
            else:
                logger.warning("Anfrage abgewiesen (%s): %s %s", grund,
                               scope.get("method"), scope.get("path"))
                inhalt = "Abgewiesen."
            antwort = PlainTextResponse(inhalt, status_code=status,
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
