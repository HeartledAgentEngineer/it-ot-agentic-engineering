"""To-do Punkt 13 (18.10.2026): Die Anmeldung ueberlebt den Server-Neustart.

Befund Sebastian (16.10.2026): „Anmeldung bitte ausblenden, erscheint bei jedem
Aktualisieren des Browsers." Ursache: die Sitzungen lagen **nur im Speicher**
des Prozesses (H2, 14.10.). Der Server startet aber oft neu (App-Knopf,
Update-Knopf, Dauerlauf) - danach war die Anmeldung wieder faellig, obwohl die
Sitzung 30 Tage gelten soll.

Gebaut: die Sitzungen liegen zusaetzlich in einer kleinen Datei
(`settings.sitzungen_datei`, Vorgabe `.sitzungen.json` neben dem Projekt). In der
Datei steht **nur** der sha256-Wert des Cookies samt Ablauf - nie das Cookie
selbst; wer die Datei liest, kann sich damit nicht anmelden.

Alle Tests hier laufen offline mit dem ``TestClient`` (kein Netz, kein Modell).
Ein „Neustart" wird nachgestellt, indem der Speicher geleert und der Lade-Merker
zurueckgesetzt wird (``_neustart()``) - genau das ist der Zustand eines frisch
gestarteten Servers. Die **Gegenprobe** (Test 2) zeigt, dass es wirklich die
Datei ist, die die Sitzung traegt: ohne sie ist dieselbe Sitzung nach dem
Neustart weg.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import BASE_DIR, settings
from app.main import app
from app.router import auth

ATTRAPPE = "Attrappe-Sitzungs-Schluessel-4711"
GESCHUETZT = "/api/auftraege"


@pytest.fixture(autouse=True)
def sauber():
    auth._SITZUNGEN.clear()
    auth._FEHLVERSUCHE.clear()
    yield
    auth._SITZUNGEN.clear()
    auth._FEHLVERSUCHE.clear()


@pytest.fixture
def mit_schluessel(monkeypatch):
    monkeypatch.setattr(settings, "api_key", ATTRAPPE)
    return ATTRAPPE


@pytest.fixture
def ablage(tmp_path, monkeypatch):
    """Eigener Ablageort je Test (die Vorrichtung in conftest setzt denselben)."""
    pfad = tmp_path / ".sitzungen.json"
    monkeypatch.setattr(settings, "sitzungen_datei", str(pfad))
    monkeypatch.setattr(auth, "_SITZUNGEN_GELADEN", None)
    return pfad


def _https():
    return TestClient(app, base_url="https://testserver")


def _anmelden(client, passwort=ATTRAPPE):
    return client.post("/api/auth/anmelden", json={"passwort": passwort})


def _neustart():
    """Frischer Prozess: nichts im Speicher, nichts geladen."""
    auth._SITZUNGEN.clear()
    auth._SITZUNGEN_GELADEN = None


def _ablage_holen():
    """Ein Aufruf auf einer geschuetzten Route holt die Ablage.

    Das Laden ist bedarfsgesteuert (erste Anfrage nach dem Start), deshalb
    genuegt kein reiner Speicher-Blick - dieser Aufruf loest es aus. Die
    Antwort ist hier Nebensache (ohne Cookie 401).
    """
    return _https().get(GESCHUETZT)


def _inhalt(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


def _token_schreiben(pfad: Path, token_hash: str, ablauf) -> None:
    pfad.write_text(json.dumps({"version": 1, "sitzungen": {token_hash: ablauf.isoformat()}}),
                    encoding="utf-8")


# ── Der Kern: die Sitzung ueberlebt den Neustart ───────────────────────────

def test_sitzung_ueberlebt_den_neustart(mit_schluessel, ablage):
    client = _https()
    assert _anmelden(client).status_code == 200
    assert client.get(GESCHUETZT).status_code != 401

    _neustart()                                     # Server neu gestartet
    assert auth._SITZUNGEN == {}                    # Speicher ist wirklich leer
    assert client.get(GESCHUETZT).status_code != 401   # ... und trotzdem angemeldet


def test_gegenprobe_ohne_ablage_ist_die_sitzung_weg(mit_schluessel, ablage):
    """Gegenprobe: ohne die Datei hilft der Neustart nicht - sie traegt die Sitzung."""
    client = _https()
    _anmelden(client)
    ablage.unlink()                                 # Ablage weg (z.B. nie geschrieben)
    _neustart()
    assert client.get(GESCHUETZT).status_code == 401


def test_in_der_ablage_steht_nur_der_hash(mit_schluessel, ablage):
    client = _https()
    _anmelden(client)
    token = client.cookies.get(auth.SITZUNG_COOKIE)
    text = ablage.read_text(encoding="utf-8")
    assert token and token not in text              # das Cookie selbst steht nirgends
    assert hashlib.sha256(token.encode("utf-8")).hexdigest() in text
    assert _inhalt(ablage)["sitzungen"]             # genau ein Eintrag


def test_zweiter_neustart_bleibt_angemeldet(mit_schluessel, ablage):
    """Idempotenz: die Sitzung wird beim Lesen nicht verbraucht."""
    client = _https()
    _anmelden(client)
    for _ in range(3):
        _neustart()
        assert client.get(GESCHUETZT).status_code != 401


# ── Abgelaufenes, Kaputtes, Grenzen ────────────────────────────────────────

def test_abgelaufene_sitzung_kommt_nicht_zurueck(mit_schluessel, ablage):
    client = _https()
    _anmelden(client)
    token = client.cookies.get(auth.SITZUNG_COOKIE) or ""
    assert token, "Anmelden hat kein Cookie gesetzt"
    _token_schreiben(ablage, auth._hash(token), auth._jetzt() - timedelta(minutes=1))
    _neustart()
    assert client.get(GESCHUETZT).status_code == 401
    assert auth._SITZUNGEN == {}
    assert _inhalt(ablage)["sitzungen"] == {}       # Abgelaufenes wurde ausgeraeumt


def test_kaputte_ablage_verhindert_anmelden_nicht(mit_schluessel, ablage):
    ablage.write_text("kein json {", encoding="utf-8")
    client = _https()
    assert _anmelden(client).status_code == 200     # kein Absturz, Anmelden geht
    assert client.get(GESCHUETZT).status_code != 401


def test_unerwartetes_format_wird_ignoriert(mit_schluessel, ablage):
    ablage.write_text(json.dumps({"version": 1, "sitzungen": ["quatsch"]}), encoding="utf-8")
    _neustart()
    assert _https().get("/api/auth/sitzung").json()["angemeldet"] is False
    assert auth._SITZUNGEN == {}


def test_kein_sha256_eintrag_wird_uebernommen(mit_schluessel, ablage):
    ablage.write_text(json.dumps({"version": 1, "sitzungen": {
        "zu-kurz": (auth._jetzt() + timedelta(days=1)).isoformat()}}), encoding="utf-8")
    _neustart()
    _ablage_holen()                                 # Laden ist bedarfsgesteuert
    assert auth._SITZUNGEN == {}
    assert _inhalt(ablage)["sitzungen"] == {}       # Unbrauchbares wurde ausgeraeumt


def test_lesen_der_ablage_schreibt_nichts_neu(mit_schluessel, ablage):
    """Lesen auf Vorrat darf die Datei nicht anfassen (Inhalt bleibt zeichengleich)."""
    client = _https()
    _anmelden(client)
    vorher = ablage.read_text(encoding="utf-8")
    _neustart()
    assert client.get(GESCHUETZT).status_code != 401
    assert ablage.read_text(encoding="utf-8") == vorher


def test_obergrenze_zaehlt_die_ablage_mit(mit_schluessel, ablage):
    """Nach dem Neustart gilt die Obergrenze weiter: der aelteste Eintrag faellt weg."""
    jetzt = auth._jetzt()
    eintraege = {}
    for i in range(auth.SITZUNGEN_MAX):
        # aeltester zuerst: Ablauf steigt mit i
        eintraege[hashlib.sha256(f"alt-{i}".encode()).hexdigest()] = (
            jetzt + timedelta(minutes=5 + i)).isoformat()
    ablage.write_text(json.dumps({"version": 1, "sitzungen": eintraege}), encoding="utf-8")
    _neustart()
    _ablage_holen()                                 # Laden ist bedarfsgesteuert
    assert len(auth._SITZUNGEN) == auth.SITZUNGEN_MAX
    aeltester = hashlib.sha256(b"alt-0").hexdigest()
    _anmelden(_https())
    assert len(auth._SITZUNGEN) == auth.SITZUNGEN_MAX and aeltester not in auth._SITZUNGEN


def test_abmelden_raeumt_die_ablage(mit_schluessel, ablage):
    client = _https()
    _anmelden(client)
    assert client.post("/api/auth/abmelden").status_code == 200
    assert _inhalt(ablage)["sitzungen"] == {}
    _neustart()
    assert client.get(GESCHUETZT).status_code == 401


def test_tempdatei_bleibt_nicht_liegen(mit_schluessel, ablage):
    client = _https()
    _anmelden(client)
    assert not (ablage.parent / (ablage.name + ".tmp")).exists()


# ── Vorgabe-Ort und Gitignore ──────────────────────────────────────────────

def test_vorgabe_ist_die_datei_neben_dem_projekt():
    vorgabe = type(settings).model_fields["sitzungen_datei"].default
    assert Path(vorgabe) == BASE_DIR / ".sitzungen.json"


def test_ablage_ist_per_gitignore_draussen():
    """Die Laufzeitdatei darf nie ins oeffentliche Repo (Sitzungs-Hashes)."""
    zeilen = (BASE_DIR / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".sitzungen.json" in [z.strip() for z in zeilen]
