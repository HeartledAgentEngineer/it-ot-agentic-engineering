"""pCloud-Anbindung des Agenten — ausschliesslich LESEND.

Warum dieser Dienst:
    Sebastians pCloud haengt auf dem PC als Laufwerk ``P:\\``. Die App soll
    Dateien aber ueber die API sehen (Kontostand, Ordnerliste, Namenssuche,
    Vorschaubilder, einzelne Dateien) — ohne den pCloud-Client und ohne
    rekursives Scannen des Laufwerks (ein ``P:\\``-Scan lief nach 180 s in
    ein Timeout, siehe docs/changelog-2026-09-26-pcloud-zugang.md).

Regeln des Nutzers, die hier als Code gelten (pCloud kennt keinen
Nur-Lesen-Scope — der Token duerfte technisch alles):
    * Einziger Zweck ist LESEN. Fuer Schreiben (nur in den Ordner ``Agent/``)
      gibt es hier bewusst KEINE Methode, ebenso wenig fuer Umbenennen,
      Verschieben oder Loeschen.
    * ``Crypto Folder`` wird nicht geoeffnet und nicht durchsucht.
    * Kein rekursiver Lauf: ``suche`` sieht genau EINEN Ordner durch.
    * Der Token ist ein Geheimnis: Er steht nur im Request und taucht in
      keiner Fehlermeldung und keinem Log auf (siehe ``_ohne_geheimnis``).

Konfiguration kommt aus ``app.config.settings`` (per .env: ``PCLOUD_TOKEN``,
``PCLOUD_HOST``) mit Umgebungs-Fallback. Standard-Host ist das
EU-Rechenzentrum ``eapi.pcloud.com`` (US waere ``api.pcloud.com``; der Token
gilt nur in der Region des Kontos).
"""

import base64
import json as _json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# EU-Rechenzentrum des Kontos (location_id 2). NICHT mit api.pcloud.com (US)
# verwechseln — dort gilt der Token nicht.
STANDARD_HOST = "eapi.pcloud.com"

# Ein Aufruf soll schnell scheitern, statt einen Endpunkt minutenlang haengen
# zu lassen. 20 s reichen fuer Liste und Kontostand deutlich aus.
TIMEOUT_SEKUNDEN = 20.0

# Obergrenze fuer einen Einzel-Download. Groessere Dateien werden gar nicht
# erst geholt — klare Meldung statt volllaufender Speicher.
MAX_DATEI_BYTES = 25 * 1024 * 1024  # 25 MB

# Mehr Treffer als diese liefert die Namenssuche nicht.
MAX_TREFFER = 50

# Erlaubte Vorschaugroessen (getthumbs). 32x32/120x120 stehen in der
# pCloud-Doku; 480x480 und 800x800 wurden am 27.09.2026 LIVE geprueft und
# kommen vom selben Endpunkt in derselben Textzeile (fileid|0|masse|data:...)
# zurueck — noetig, weil 120x120 fuer Screenshots zu klein zum Lesen ist.
ERLAUBTE_THUMB_GROESSEN = ("32x32", "120x120", "480x480", "800x800")


class PCloudFehler(Exception):
    """Fehler beim Zugriff auf die pCloud — Text fuer den Nutzer.

    Enthaelt nie den Token (siehe ``_ohne_geheimnis``). Der Router
    uebersetzt diese Ausnahme in HTTP 502.
    """


class PCloudNichtKonfiguriert(PCloudFehler):
    """Kein Token vorhanden — der Router antwortet damit als HTTP 503."""


class PCloudZuGross(PCloudFehler):
    """Datei ueberschreitet die Download-Obergrenze — HTTP 413 im Router."""


# ── Kleine Helfer ──────────────────────────────────────────────────────────

def _ohne_geheimnis(text: str, token: str) -> str:
    """Den Token aus einem Text entfernen, falls er hineingeraten ist.

    Letzte Verteidigungslinie: Selbst wenn eine fremde Fehlermeldung (z. B.
    eine httpx-Meldung mit voller URL) den Token enthielte, wird er hier
    durch ``***`` ersetzt, bevor der Text irgendwo sichtbar wird.
    """
    if token and token in text:
        return text.replace(token, "***")
    return text


def _maskiere_email(email: str) -> str:
    """E-Mail maskieren: nur die ersten 2 und die letzten 4 Zeichen bleiben.

    Die vollstaendige Adresse darf nie in einer Antwort, einem Log oder
    einer Doku auftauchen. Sehr kurze Werte werden komplett verdeckt.
    """
    wert = (email or "").strip()
    if not wert:
        return ""
    if len(wert) <= 6:
        return "*" * len(wert)
    return f"{wert[:2]}{'*' * (len(wert) - 6)}{wert[-4:]}"


def _in_gb(wert: Any) -> float:
    """Bytes in GB umrechnen, wie die Anzeige des Kontos es tut (1 GB = 1e9).

    pCloud liefert ``quota``/``usedquota`` in Bytes; der 2-TB-Plan des
    Kontos steht dort als 2199023255552 Bytes = 2199,0 GB (dezimal).
    Unbrauchbare Werte werden ehrlich zu 0.0 statt zu einem Absturz.
    """
    return round(_als_int(wert) / 1_000_000_000, 1)


def _als_int(wert: Any) -> int:
    """Zahl tolerant lesen — fehlende/unbrauchbare Werte werden ehrlich 0.

    Ein kaputter Zahlenwert aus einer API-Antwort darf keinen 500er
    ausloesen; 0 ist die sichtbar harmlose Variante.
    """
    try:
        return int(wert)
    except (TypeError, ValueError):
        return 0


def _eintraege_aus_antwort(daten: Dict[str, Any]) -> List[Dict[str, Any]]:
    """``contents`` aus einer listfolder-Antwort holen (leer, wenn keine).

    Ein leerer Ordner kommt ohne ``metadata`` zurueck — das ist gueltig und
    ergibt eine leere Liste, keinen Fehler.
    """
    metadata = daten.get("metadata")
    if not isinstance(metadata, dict):
        return []
    inhalte = metadata.get("contents")
    if not isinstance(inhalte, list):
        return []
    ergebnis: List[Dict[str, Any]] = []
    for eintrag in inhalte:
        if not isinstance(eintrag, dict):
            continue
        # pCloud setzt je nach Typ folderid (Ordner) oder fileid (Datei);
        # fehlende Felder werden ehrlich None statt 0.
        ergebnis.append(
            {
                "name": str(eintrag.get("name") or ""),
                "ist_ordner": bool(eintrag.get("isfolder")),
                "folderid": eintrag.get("folderid"),
                "fileid": eintrag.get("fileid"),
                "groesse": eintrag.get("size"),
                "geaendert": eintrag.get("modified"),
            }
        )
    return ergebnis


class PCloudService:
    """Lesender Zugriff auf die pCloud-API (HTTP, synchron).

    Bewusst synchron: Die Endpunkte sind ``def`` (nicht ``async``), damit
    FastAPI sie in den Threadpool schiebt und der Event-Loop (laufende
    Chat-Streams) nicht blockiert — dasselbe Muster wie ``router/archiv.py``.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        host: Optional[str] = None,
        timeout: float = TIMEOUT_SEKUNDEN,
    ) -> None:
        # None = "nicht gesetzt" -> aus settings/Umgebung lesen. Ein leerer
        # String ist dagegen ein gueltiger Zustand "kein Token" (Tests).
        self._token_aus_parameter = token
        self._host_aus_parameter = host
        self.timeout = timeout

    # ── Konfiguration ──────────────────────────────────────────────────
    @property
    def token(self) -> str:
        """Der API-Token — wird nie geloggt und nie ausgegeben."""
        if self._token_aus_parameter is not None:
            return self._token_aus_parameter.strip()
        wert = (getattr(settings, "pcloud_token", "") or "").strip()
        if wert:
            return wert
        return (os.environ.get("PCLOUD_TOKEN") or "").strip()

    @property
    def host(self) -> str:
        """API-Host ohne Schema, z. B. ``eapi.pcloud.com``."""
        if self._host_aus_parameter is not None:
            roh = self._host_aus_parameter
        else:
            roh = (
                (getattr(settings, "pcloud_host", "") or "").strip()
                or (os.environ.get("PCLOUD_HOST") or "").strip()
                or STANDARD_HOST
            )
        # Ein versehentlich mitgeschriebenes "https://" oder ein Slash am
        # Ende wuerde die URL zerstoeren — hier tolerant bereinigen.
        return roh.split("://")[-1].strip().strip("/")

    def ist_konfiguriert(self) -> bool:
        """True, sobald ein Token vorhanden ist (sonst 503 im Router)."""
        return bool(self.token)

    # ── Interner Aufruf-Helfer ─────────────────────────────────────────
    def _get(self, pfad: str, token: str, **felder: Any) -> "httpx.Response":
        """Roher GET mit ``auth`` — gemeinsame Basis von API-Aufruf und Bild.

        Wirft bei Netz-/Transportfehlern eine ``PCloudFehler`` mit dem
        Ausnahme-Namen; die Meldung des fremden Fehlers wird bewusst NICHT
        uebernommen (sie kann die volle URL samt Token enthalten).
        """
        parameter = {name: wert for name, wert in felder.items() if wert is not None}
        parameter["auth"] = token
        url = f"https://{self.host}/{pfad.lstrip('/')}"
        try:
            return httpx.get(url, params=parameter, timeout=self.timeout)
        except Exception as e:
            meldung = f"pCloud nicht erreichbar ({e.__class__.__name__})."
            logger.warning("%s Pfad=%s", meldung, pfad)
            raise PCloudFehler(meldung) from None

    def _api(self, pfad: str, **felder: Any) -> Dict[str, Any]:
        """Ein GET gegen die pCloud-API, ``auth`` wird ergaenzt.

        Prueft ``result``: Alles ausser 0 wird zur ``PCloudFehler`` mit dem
        Fehlertext der API (z. B. "Directory does not exist.").
        """
        token = self.token
        if not token:
            raise PCloudNichtKonfiguriert(
                "pCloud ist nicht konfiguriert: PCLOUD_TOKEN fehlt in der .env."
            )
        antwort = self._get(pfad, token, **felder)
        if antwort.status_code != 200:
            meldung = f"pCloud antwortete mit HTTP {antwort.status_code}."
            logger.warning("%s Pfad=%s", meldung, pfad)
            raise PCloudFehler(meldung)
        try:
            daten = antwort.json()
        except Exception:
            logger.warning("pCloud lieferte keine lesbare JSON-Antwort (Pfad=%s).", pfad)
            raise PCloudFehler(
                "pCloud lieferte keine lesbare JSON-Antwort."
            ) from None
        if not isinstance(daten, dict):
            raise PCloudFehler("pCloud lieferte eine unerwartete Antwort.")
        if daten.get("result") != 0:
            fehlertext = _ohne_geheimnis(
                str(daten.get("error") or "ohne Fehlertext"), token
            )
            meldung = f"pCloud meldet Fehler {daten.get('result')}: {fehlertext}"
            logger.warning("pCloud-Fehler (Pfad=%s): %s", pfad, fehlertext)
            raise PCloudFehler(meldung)
        return daten

    # ── Lesende Fachmethoden ───────────────────────────────────────────
    def status(self) -> Dict[str, Any]:
        """Kontozusammenfassung (userinfo): Quota, Belegung, Premium.

        Die E-Mail kommt MASKIERT zurueck (nur erste 2 und letzte 4
        Zeichen) — die vollstaendige Adresse verlaesst diese Methode nie.
        """
        daten = self._api("/userinfo")
        quota = _als_int(daten.get("quota"))
        belegt = _als_int(daten.get("usedquota"))
        return {
            "verbunden": True,
            "host": self.host,
            "email": _maskiere_email(str(daten.get("email") or "")),
            "userid": daten.get("userid"),
            "premium": bool(daten.get("premium")),
            "email_verifiziert": bool(daten.get("emailverified")),
            "quota_gb": _in_gb(quota),
            "belegt_gb": _in_gb(belegt),
            "frei_gb": _in_gb(max(quota - belegt, 0)),
        }

    def liste(self, folderid: int = 0) -> List[Dict[str, Any]]:
        """Eintraege EINES Ordners (Wurzel = 0), Ordner zuerst, dann Name.

        Kein rekursiver Lauf — genau eine ``listfolder``-Anfrage.
        """
        daten = self._api("/listfolder", folderid=int(folderid))
        eintraege = _eintraege_aus_antwort(daten)
        # Ordner zuerst, innerhalb der Gruppen alphabetisch (Gross-/
        # Kleinschreibung egal — casefold sortiert "apfel" richtig zu
        # "Banane", auch bei Umlauten).
        eintraege.sort(key=lambda e: (not e["ist_ordner"], e["name"].casefold()))
        return eintraege

    def suche(self, begriff: str, folderid: int = 0) -> List[Dict[str, Any]]:
        """Namenssuche in EINEM Ordner — Gross-/Kleinschreibung egal.

        Bewusst NICHT rekursiv: genau ein ``listfolder``, danach filtern.
        Ohne Begriff gibt es keine Treffer und keinen API-Aufruf.
        """
        gesucht = (begriff or "").strip().casefold()
        if not gesucht:
            return []
        treffer = [
            eintrag
            for eintrag in self.liste(folderid)
            if gesucht in eintrag["name"].casefold()
        ]
        return treffer[:MAX_TREFFER]

    def thumb(self, fileid: int, groesse: str = "120x120") -> bytes:
        """Vorschaubild eines Bildes als Bytes (live: JPEG).

        LIVE GEPRUEFT (27.09.2026, eapi.pcloud.com): pCloud liefert KEINE
        rohen Bildbytes und kein JSON, sondern eine Textzeile je Datei::

            fileid|0|86x120|data:image/jpeg;base64,/9j/4AAQ…

        Mit ``type=png`` antwortet der Server mit ``fileid|5002|0`` (kein
        PNG-Vorschaubild), deshalb wird ``type=jgp`` (JPEG) angefragt; das
        base64 wird hier zu Bytes dekodiert. Liefert ein Server doch rohe
        Bildbytes (andere pCloud-Version), kommen sie unveraendert zurueck.
        """
        if groesse not in ERLAUBTE_THUMB_GROESSEN:
            raise PCloudFehler(
                "Unbekannte Vorschaugroesse: erlaubt sind "
                + " und ".join(ERLAUBTE_THUMB_GROESSEN)
                + "."
            )
        token = self.token
        if not token:
            raise PCloudNichtKonfiguriert(
                "pCloud ist nicht konfiguriert: PCLOUD_TOKEN fehlt in der .env."
            )
        antwort = self._get(
            "/getthumbs", token, fileids=int(fileid), size=groesse, type="jgp"
        )
        if antwort.status_code != 200:
            raise PCloudFehler(f"pCloud antwortete mit HTTP {antwort.status_code}.")
        daten = antwort.content or b""
        if not daten:
            raise PCloudFehler(f"pCloud lieferte keine Bilddaten zu fileid {fileid}.")
        if media_typ_fuer_bild(daten) != "application/octet-stream":
            return daten
        kopf = str(antwort.headers.get("content-type") or "").lower()
        if "json" in kopf or daten.lstrip()[:1] == b"{":
            raise PCloudFehler(_bild_fehlertext(daten, int(fileid), token))
        return _vorschau_aus_zeile(daten, int(fileid))

    def datei_bytes(self, fileid: int, max_bytes: int = MAX_DATEI_BYTES) -> bytes:
        """Eine Datei herunterladen (getfilelink -> Link -> Bytes).

        Obergrenze ``max_bytes`` (Standard 25 MB): Ist die Datei laut
        Link-Angabe oder waehrend des Ladens groesser, bricht der Download
        mit einer klaren Meldung ab, statt Speicher voll laufen zu lassen.
        """
        link = self._api("/getfilelink", fileid=int(fileid))
        hosts = [h for h in (link.get("hosts") or []) if h]
        pfad = str(link.get("path") or "")
        if not hosts or not pfad:
            raise PCloudFehler(
                f"pCloud lieferte keinen Download-Link zu fileid {fileid}."
            )
        groesse = _als_int(link.get("size"))
        if groesse and groesse > max_bytes:
            raise PCloudZuGross(
                f"Datei ist {_mb(groesse)} gross und ueberschreitet die "
                f"Obergrenze von {_mb(max_bytes)}. Download abgebrochen."
            )

        letzter_fehler = ""
        for host in hosts:
            url = f"https://{host}{pfad}"
            try:
                with httpx.stream("GET", url, timeout=self.timeout) as antwort:
                    if antwort.status_code != 200:
                        letzter_fehler = f"HTTP {antwort.status_code}"
                        continue
                    teile = bytearray()
                    for stueck in antwort.iter_bytes():
                        teile.extend(stueck)
                        if len(teile) > max_bytes:
                            raise PCloudZuGross(
                                f"Datei ist groesser als {_mb(max_bytes)} "
                                f"(Obergrenze). Download abgebrochen."
                            )
                    return bytes(teile)
            except PCloudZuGross:
                raise
            except Exception as e:
                # Nur der Klassenname — fremde Meldungen koennen die volle
                # URL enthalten (der Link selbst traegt zwar kein auth, aber
                # das Muster bleibt hier einheitlich).
                letzter_fehler = e.__class__.__name__
                continue
        raise PCloudFehler(
            "Download von pCloud fehlgeschlagen ("
            + (letzter_fehler or "kein Host erreichbar")
            + ")."
        )


def _mb(bytes_wert: int) -> str:
    """Byte-Zahl lesbar als MB ausgeben (1 MB = 1e6, wie die Anzeige)."""
    return f"{bytes_wert / 1_000_000:.1f} MB"


def media_typ_fuer_bild(daten: bytes) -> str:
    """Medientyp aus den ersten Bytes ableiten.

    getthumbs liefert live JPEG (aus dem base64); rohe Bytes anderer Quellen
    werden hier ebenfalls korrekt erkannt. Unbekanntes bleibt ehrlich
    ``application/octet-stream`` — der Router gibt das dann so weiter.
    """
    if daten[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if daten[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if daten[:4] == b"GIF8":
        return "image/gif"
    return "application/octet-stream"


def _vorschau_aus_zeile(daten: bytes, fileid: int) -> bytes:
    """Die getthumbs-Textzeile auswerten und die Bildbytes dekodieren.

    Format (live geprueft): ``fileid|ergebnis|masse|data:image/jpeg;base64,…``
    Fehlerfall: ``fileid|5002|0`` — dann klare Meldung mit dem Code, statt
    den Text als "Bild" durchzureichen.
    """
    text = daten.decode("utf-8", errors="replace").strip()
    zeile = next((z for z in text.splitlines() if z.strip()), "")
    if not zeile:
        raise PCloudFehler(f"pCloud lieferte keine Bilddaten zu fileid {fileid}.")
    teile = zeile.split("|")
    if len(teile) < 2:
        raise PCloudFehler("pCloud lieferte keine lesbaren Vorschaubild-Daten.")
    ergebnis = teile[1]
    daten_uri = teile[3] if len(teile) > 3 else ""
    if ergebnis != "0" or "base64," not in daten_uri:
        raise PCloudFehler(
            f"pCloud liefert zu fileid {fileid} kein Vorschaubild (Code {ergebnis})."
        )
    try:
        return base64.b64decode(daten_uri.split("base64,", 1)[1])
    except Exception:
        raise PCloudFehler(
            f"Vorschaubild zu fileid {fileid} war nicht dekodierbar (base64)."
        ) from None


def _bild_fehlertext(daten: bytes, fileid: int, token: str) -> str:
    """Fehlertext aus einer JSON-Antwort, wo Bilddaten erwartet wurden."""
    try:
        geladen = _json.loads(daten.decode("utf-8", errors="replace"))
    except Exception:
        return "pCloud lieferte keine Bilddaten (JSON-Antwort nicht lesbar)."
    if isinstance(geladen, dict) and geladen.get("result") not in (0, None):
        fehlertext = _ohne_geheimnis(
            str(geladen.get("error") or "ohne Fehlertext"), token
        )
        return f"pCloud meldet Fehler {geladen.get('result')}: {fehlertext}"
    return (
        "pCloud lieferte keine Bilddaten zu fileid "
        f"{fileid} (kein Vorschaubild vorhanden?)."
    )


# Zentrale Instanz fuer den Router. Liest Token/Host bei JEDEM Zugriff aus
# settings/Umgebung — so wirkt eine geaenderte .env ohne Neustart der Tests.
pcloud_service = PCloudService()
