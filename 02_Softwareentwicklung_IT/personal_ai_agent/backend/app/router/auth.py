"""Authentication API routes (prepared for future use)."""

import hashlib
import hmac
import logging
import secrets
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.sicherheit import client_ist_loopback

logger = logging.getLogger(__name__)


def _schluessel_passt(gesendet: Optional[str]) -> bool:
    """Vergleicht in konstanter Zeit (P0, 12.10.2026) statt mit ``!=``.

    Sonst verrät die Antwortzeit, wie viele Zeichen am Anfang schon stimmen.
    """
    erwartet = settings.api_key or ""
    return hmac.compare_digest((gesendet or "").encode("utf-8"), erwartet.encode("utf-8"))

# python-jose ist optional – wird erst bei Bedarf installiert
try:
    from jose import JWTError, jwt
    JWT_AVAILABLE = True
except ImportError:
    JWTError = None
    jwt = None
    JWT_AVAILABLE = False
    logger.warning("python-jose nicht installiert. Auth-Endpunkte deaktiviert.")

router = APIRouter(prefix="/api/auth", tags=["auth"])


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """Verify API key from header (MVP simple auth)."""
    if settings.api_key:
        if not _schluessel_passt(x_api_key):
            raise HTTPException(
                status_code=401,
                detail="Ungültiger API-Key. Prüfe den Header 'X-API-Key'.",
            )
    return True


# Routen-Präfixe, die auch ohne API-Key erreichbar sein müssen:
# - "/api/health": Liveness-/Health-Check, darf nicht durch Auth blockieren
# - "/api/auth":   Login-Endpunkt (tauscht Key gegen JWT aus) muss offen sein
OPEN_API_PFIXE = ("/api/health", "/api/auth")

#: Zusätzlich ohne Schlüssel/Sitzung erreichbar — aber NUR vom Gerät selbst
#: (Loopback, Gegenstelle der Verbindung in 127.0.0.0/8 oder ::1). Grund
#: (Sebastian, 16.10.2026): Er bedient den Server am Handy über HTTP ohne
#: Anmeldung; der Update-/Neustart-Knopf war damit tot. Der Schutz nach außen
#: bleibt das Tailscale-Netz plus HTTPS für fremde Geräte, und fremde Clients
#: bekommen hier weiterhin 401.
LOOPBACK_FREI_PFIXE = ("/api/system/",)


# ── Sitzungen für PC und Tablet im Heim-WLAN (HTTPS-Plan H2, 14.10.2026) ──────
#
# Seit H1 bekommen nur Loopback-Clients den Schlüssel in der Startseite. Andere
# Geräte melden sich an: Benutzer ``agent``, Passwort = API-Schlüssel aus der
# .env (kein zweites Geheimnis; Bitwarden füllt es aus). Der Server gibt ein
# zufälliges Sitzungs-Cookie aus und merkt sich nur dessen sha256 im Speicher
# des Prozesses — nach einem Neustart ist neu anmelden nötig.

SITZUNG_COOKIE = "agent_sitzung"
SITZUNG_DAUER = timedelta(days=30)
SITZUNGEN_MAX = 50
BREMSE_VERSUCHE = 5
BREMSE_FENSTER = timedelta(minutes=10)

_SITZUNGEN: Dict[str, datetime] = {}            # sha256(token) -> Ablauf
_FEHLVERSUCHE: Dict[str, Deque[datetime]] = {}   # Client-IP -> Zeiten der Fehlversuche
_SPERRE = threading.Lock()


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sitzung_gueltig(request: "Request") -> bool:
    """Trägt die Anfrage ein gültiges, nicht abgelaufenes Sitzungs-Cookie?"""
    token = request.cookies.get(SITZUNG_COOKIE)
    if not token or len(token) > 200:
        return False
    schluessel = _hash(token)
    with _SPERRE:
        ablauf = _SITZUNGEN.get(schluessel)
        if ablauf is None:
            return False
        if ablauf <= _jetzt():
            _SITZUNGEN.pop(schluessel, None)
            return False
        return True


def _ist_https(request: "Request") -> bool:
    """Nur das Schema der Verbindung selbst (uvicorn mit TLS), keine Kopfzeile."""
    return request.scope.get("scheme") == "https"


def _client_ip(request: "Request") -> str:
    client = request.scope.get("client")
    return str(client[0]) if isinstance(client, (tuple, list)) and client else "?"


def _gebremst(ip: str) -> bool:
    """Zu viele Fehlversuche dieser IP im Fenster? Räumt alte Einträge mit auf."""
    grenze = _jetzt() - BREMSE_FENSTER
    with _SPERRE:
        zeiten = _FEHLVERSUCHE.get(ip)
        if not zeiten:
            return False
        while zeiten and zeiten[0] <= grenze:
            zeiten.popleft()
        if not zeiten:
            _FEHLVERSUCHE.pop(ip, None)
            return False
        return len(zeiten) >= BREMSE_VERSUCHE


def _fehlversuch(ip: str) -> int:
    with _SPERRE:
        zeiten = _FEHLVERSUCHE.setdefault(ip, deque())
        zeiten.append(_jetzt())
        return len(zeiten)


def _sitzung_anlegen() -> str:
    token = secrets.token_urlsafe(32)
    jetzt = _jetzt()
    with _SPERRE:
        for k in [k for k, ablauf in _SITZUNGEN.items() if ablauf <= jetzt]:
            _SITZUNGEN.pop(k, None)
        while len(_SITZUNGEN) >= SITZUNGEN_MAX:      # älteste zuerst weg
            _SITZUNGEN.pop(min(_SITZUNGEN, key=_SITZUNGEN.get), None)
        _SITZUNGEN[_hash(token)] = jetzt + SITZUNG_DAUER
    return token


async def require_api_key(request: "Request") -> None:
    """Globale FastAPI-Abhängigkeit: schützt ALLE /api/*-Routen.

    Ist `settings.api_key` gesetzt (aus der .env), wird er von jedem
    Client über den Header `X-API-Key` verlangt — oder ein gültiges
    Sitzungs-Cookie (H2, 14.10.2026). Ausgenommen sind nur
    `/api/health` (Liveness) und `/api/auth` (Login). Frontend, Hermes-
    Gateway und Tests müssen den Key dann mitschicken.

    Ist kein `settings.api_key` gesetzt, bleibt alles ungeschützt/offen
    (Abwärtskompatibilität, lokale Entwicklung).
    """
    if not settings.api_key:
        return
    # Statische Frontend-Dateien unter "/" sind kein /api/-Endpunkt und
    # bleiben ohne Key erreichbar (nur HTML/JS/CSS, keine Daten).
    pfad = request.url.path
    if pfad.startswith(OPEN_API_PFIXE):
        return
    if pfad.startswith(LOOPBACK_FREI_PFIXE) and client_ist_loopback(request.scope):
        return
    key = request.headers.get("x-api-key")
    if _schluessel_passt(key) or sitzung_gueltig(request):
        return
    raise HTTPException(
        status_code=401,
        detail="Zugriff verweigert: gültiger X-API-Key erforderlich.",
    )


class Anmeldung(BaseModel):
    passwort: str = Field(default="", max_length=500)


@router.get("/sitzung")
async def sitzung(request: Request):
    """Für die Startseite: angemeldet? Läuft die Verbindung über HTTPS?

    Ohne API_KEY in der .env gibt es keinen Schutz und kein Login — die
    Oberfläche läuft dann ohnehin offen (``schutz: false``).
    """
    if not settings.api_key:
        return {"angemeldet": True, "https": _ist_https(request), "schutz": False}
    return {"angemeldet": sitzung_gueltig(request), "https": _ist_https(request), "schutz": True}


@router.post("/anmelden")
async def anmelden(daten: Anmeldung, request: Request):
    """Passwort (= API-Schlüssel) prüfen und ein Sitzungs-Cookie setzen. Nur über HTTPS."""
    if not settings.api_key:
        raise HTTPException(status_code=409,
                            detail="Zugang aus dem WLAN erst nach API_KEY in der .env.")
    if not _ist_https(request):
        raise HTTPException(status_code=403, detail="Anmelden nur über HTTPS.")
    ip = _client_ip(request)
    if _gebremst(ip):
        logger.warning("Anmelden gebremst: zu viele Fehlversuche (%d in %d min).",
                       BREMSE_VERSUCHE, int(BREMSE_FENSTER.total_seconds() // 60))
        raise HTTPException(status_code=429,
                            detail="Zu viele Fehlversuche – bitte 10 Minuten warten.")
    if not _schluessel_passt(daten.passwort):
        anzahl = _fehlversuch(ip)
        logger.warning("Anmelden fehlgeschlagen (Fehlversuch %d).", anzahl)
        raise HTTPException(status_code=401, detail="Passwort falsch.")
    token = _sitzung_anlegen()
    antwort = JSONResponse({"ok": True})
    antwort.set_cookie(SITZUNG_COOKIE, token, max_age=int(SITZUNG_DAUER.total_seconds()),
                       path="/", secure=True, httponly=True, samesite="strict")
    logger.info("Anmeldung erfolgreich (%d Sitzungen aktiv).", len(_SITZUNGEN))
    return antwort


@router.post("/abmelden")
async def abmelden(request: Request):
    """Die eigene Sitzung beenden und das Cookie löschen."""
    token = request.cookies.get(SITZUNG_COOKIE)
    if token:
        with _SPERRE:
            _SITZUNGEN.pop(_hash(token), None)
    antwort = JSONResponse({"ok": True})
    antwort.delete_cookie(SITZUNG_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
    return antwort


@router.post("/token")
async def get_token(x_api_key: Optional[str] = Header(None)):
    """Exchange API key for a JWT token."""
    if settings.api_key and not _schluessel_passt(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    token = create_access_token(subject="sebastian")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_minutes * 60,
    }


@router.get("/check")
async def auth_check(authenticated: bool = Depends(verify_api_key)):
    """Check if authentication is working."""
    return {"status": "authenticated", "user": "sebastian"}