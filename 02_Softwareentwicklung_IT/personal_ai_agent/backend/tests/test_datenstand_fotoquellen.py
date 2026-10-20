"""Datenstand in der App (T0): Weg, Anzeige und Zwischenspeicher.

Auftrag: ``.hermes/plans/gesamtplan-foto-erinnerungen-2026-10-11.md``, Abschnitt
T0 — „Ergebnis für den Nutzer: **unter „Datenstand" eine Statuszeile pro
Quelle**: entpackt → Bildindex → Gesichtserkennung → Gruppenbestand → auf diesem
Handy". Die Messung selbst ist fertig und hat eigene Tests
(``test_import_status.py``); hier wird der WEG in die Oberfläche geprüft:

1. **Zwischenspeicher** (``import_status.status_gecacht``) — ein Stand gilt für
   eine Weile, ``neu`` misst frisch, verschiedene Basen teilen sich nichts.
   Grund: eine volle Messung liest auf dem Gerät rund 250 MB.
2. **Route** ``GET /api/datenstand/fotoquellen`` — Schutz wie beim Protokoll
   (Gerät selbst immer, fremde Geräte nur über HTTPS), derselbe
   Berichtsvertrag, ehrliche ``null``-Werte, kein Pfad/Name/Vektor im Bericht.
3. **Oberfläche** — Knopf, Bereich, reine Textfunktionen; Klartext ohne Symbole
   (Sebastians Regel), geschrieben mit ``textContent`` (nie ``innerHTML``).

Alles offline: erfundene Dateien in ``tmp_path``, gestellte Antworten, kein
Netz, kein Gerät, keine echten Personendaten.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.router import auth
from app.services import import_status
from app.services.import_status import VERTRAGSFELDER

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"
API_KEY = "Attrappe-Datenstand-Schluessel-0815"
QUELLEN = (("fotos", ("sortierplan.json",), ("personen_vektoren_voll.jsonl",)),
           ("papas_album", ("sortierplan_papa.json",), ("personen_vektoren_papa.jsonl",)))


# ── Hilfen ──────────────────────────────────────────────────────────────────

def _von_herkunft(herkunft: str):
    """ASGI-Hülle: setzt die Gegenstelle der Verbindung (wie in test_system_update)."""
    async def app_mit_client(scope, receive, send):
        neuer_scope = dict(scope)
        neuer_scope["client"] = (herkunft, 45321)
        await app(neuer_scope, receive, send)

    return app_mit_client


def _basis_bauen(ordner: Path) -> Path:
    """Eine winzige, erfundene Quelle: Plan, Vektordatei, Bildindex."""
    (ordner / "personen_gruppen").mkdir(parents=True, exist_ok=True)
    (ordner / "sortierplan.json").write_text(
        json.dumps({"zuege": [{"fileid": 11}, {"fileid": 12}]}), encoding="utf-8")
    (ordner / "personen_vektoren_voll.jsonl").write_text(
        json.dumps({"bild_id": 11, "gesichter": [{}, {}]}) + "\n", encoding="utf-8")
    return ordner


@pytest.fixture(autouse=True)
def _sauber():
    """Zwischenspeicher und Sitzungszustand vor und nach jedem Test räumen."""
    import_status.cache_leeren()
    auth._SITZUNGEN.clear()
    auth._FEHLVERSUCHE.clear()
    yield
    import_status.cache_leeren()
    auth._SITZUNGEN.clear()
    auth._FEHLVERSUCHE.clear()


# ── 1. Zwischenspeicher ─────────────────────────────────────────────────────

def test_erster_aufruf_misst_zweiter_liefert_aus_dem_speicher(tmp_path):
    basis = str(_basis_bauen(tmp_path))
    erst = import_status.status_gecacht(basis=basis, quellen=QUELLEN)
    zweit = import_status.status_gecacht(basis=basis, quellen=QUELLEN)

    assert erst["aus_cache"] is False
    assert zweit["aus_cache"] is True
    assert zweit["bericht"] == erst["bericht"]
    assert isinstance(zweit["dauer_sekunden"], float)
    assert zweit["gemessen_sekunden"] < 1.0


def test_neu_misst_frisch_und_ttl_null_schaltet_den_speicher_ab(tmp_path):
    basis = str(_basis_bauen(tmp_path))
    import_status.status_gecacht(basis=basis, quellen=QUELLEN)

    frisch = import_status.status_gecacht(basis=basis, quellen=QUELLEN, neu=True)
    ohne_speicher = import_status.status_gecacht(basis=basis, quellen=QUELLEN,
                                                 ttl_sekunden=0)

    assert frisch["aus_cache"] is False
    assert ohne_speicher["aus_cache"] is False


def test_verschiedene_basen_teilen_sich_nichts(tmp_path):
    eine = str(_basis_bauen(tmp_path / "a"))
    andere = str(_basis_bauen(tmp_path / "b"))
    import_status.status_gecacht(basis=eine, quellen=QUELLEN)

    zweite = import_status.status_gecacht(basis=andere, quellen=QUELLEN)

    assert zweite["aus_cache"] is False


def test_handy_stand_geprueft_geht_in_den_speicher_schluessel(tmp_path):
    """Ein anderer Wert für „auf diesem Handy geprüft" ist ein anderer Stand."""
    basis = str(_basis_bauen(tmp_path))
    import_status.status_gecacht(basis=basis, quellen=QUELLEN, handy_geprueft=True)

    anders = import_status.status_gecacht(basis=basis, quellen=QUELLEN,
                                          handy_geprueft=None)

    assert anders["aus_cache"] is False
    assert anders["bericht"]["handy_stand_geprueft"] is None


# ── 2. Die Route ────────────────────────────────────────────────────────────

def test_route_liefert_den_bericht_vom_geraet_selbst_ohne_anmeldung(tmp_path, monkeypatch):
    monkeypatch.setattr(import_status, "STANDARD_BASIS", str(_basis_bauen(tmp_path)))
    antwort = TestClient(_von_herkunft("127.0.0.1"), base_url="http://testserver").get(
        "/api/datenstand/fotoquellen")

    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["ok"] is True
    assert daten["handy_stand_geprueft"] is True          # auf dem Gerät gemessen
    assert daten["aus_cache"] is False
    assert isinstance(daten["dauer_sekunden"], float)
    assert [q["quelle_typ"] for q in daten["quellen"]] == [q[0] for q in import_status.QUELLEN]
    for zeile in daten["quellen"]:
        assert list(zeile.keys()) == list(VERTRAGSFELDER)


def test_route_ist_fuer_fremde_geraete_nur_ueber_https(monkeypatch):
    monkeypatch.setattr(settings, "api_key", API_KEY)

    fremd_ohne_schluessel = TestClient(app, base_url="https://testserver").get(
        "/api/datenstand/fotoquellen")
    fremd_ueber_http = TestClient(app, base_url="http://testserver").get(
        "/api/datenstand/fotoquellen", headers={"X-API-Key": API_KEY})
    fremd_ueber_https = TestClient(app, base_url="https://testserver").get(
        "/api/datenstand/fotoquellen", headers={"X-API-Key": API_KEY})

    assert fremd_ohne_schluessel.status_code == 401
    assert fremd_ueber_http.status_code == 403
    assert fremd_ueber_https.status_code == 200


def test_route_reicht_neu_durch_und_erfindet_keine_nullen(monkeypatch):
    """``?neu=true`` misst frisch; fehlende Werte bleiben ``null``, nie ``0``."""
    gesehen = {}

    def _attrappe(*, neu=False, handy_geprueft=None):
        gesehen["neu"] = neu
        gesehen["handy_geprueft"] = handy_geprueft
        leere = {feld: None for feld in VERTRAGSFELDER}
        leere["quelle_typ"] = "fotos"
        leere["gelesen_am"] = "2026-10-18T22:00:00+02:00"
        return {"bericht": {"gelesen_am": leere["gelesen_am"], "quellen": [leere],
                            "gruppenbestand": {"gruppen": None, "benannt": None,
                                               "offen": None, "spaeter": None,
                                               "gesichter": None},
                            "handy_stand_geprueft": handy_geprueft,
                            "fehlende_werte": ["fotos.bilder_im_plan"],
                            "hinweis": "Summen je Quelle."},
                "aus_cache": False, "dauer_sekunden": 1.234,
                "gemessen_sekunden": 1.234}

    monkeypatch.setattr(import_status, "status_gecacht", _attrappe)
    antwort = TestClient(_von_herkunft("::1"), base_url="http://testserver").get(
        "/api/datenstand/fotoquellen?neu=true")

    assert antwort.status_code == 200
    daten = antwort.json()
    assert gesehen == {"neu": True, "handy_geprueft": True}
    assert daten["quellen"][0]["bilder_im_plan"] is None
    assert daten["dauer_sekunden"] == 1.23
    assert daten["fehlende_werte"] == ["fotos.bilder_im_plan"]


def test_bericht_traegt_keinen_pfad_und_keinen_vektor(tmp_path, monkeypatch):
    """Nur Summen: kein Pfad, kein Dateiname, keine Kennung im Berichtstext."""
    monkeypatch.setattr(import_status, "STANDARD_BASIS", str(_basis_bauen(tmp_path)))
    antwort = TestClient(_von_herkunft("127.0.0.1"), base_url="http://testserver").get(
        "/api/datenstand/fotoquellen")
    rohtext = antwort.text

    assert str(tmp_path) not in rohtext
    assert "C:\\" not in rohtext and "/home/" not in rohtext
    assert not re.search(r'"gesichter"\s*:\s*\[', rohtext)          # keine Vektorlisten
    assert not re.search(r"\d+\.\d{4,}", rohtext)                   # keine Koordinaten
    daten = json.loads(rohtext)
    for zeile in daten["quellen"]:
        assert set(zeile).issubset(set(VERTRAGSFELDER))


# ── 3. Die Oberfläche (Knopf, Bereich, reine Textfunktionen) ────────────────

def _quelltext() -> tuple[str, str, str]:
    return ((FRONTEND / "app.js").read_text(encoding="utf-8"),
            (FRONTEND / "index.html").read_text(encoding="utf-8"),
            (FRONTEND / "style.css").read_text(encoding="utf-8"))


def test_oberflaeche_hat_knopf_und_bereich():
    js, html, css = _quelltext()

    assert 'id="datenstand-btn"' in html
    assert 'id="datenstand"' in html
    assert 'id="datenstand-stand"' in html
    assert 'id="datenstand-liste"' in html
    assert 'id="datenstand-neu"' in html
    assert ".datenstand" in css
    assert "/api/datenstand/fotoquellen" in js


def test_textfunktionen_sind_rein_und_schreiben_kein_html():
    js, _, _ = _quelltext()
    block = js[js.index("function datenstandZahl("):]
    block = block[:block.index("(function () {")]

    assert "function datenstandStand(" in block
    assert "function datenstandZeilen(" in block
    assert "document." not in block              # rein: kein DOM-Zugriff
    assert "innerHTML" not in block              # nur Text, nie HTML
    assert "nicht gemessen" in block             # ehrliche Meldung statt 0
    assert "/api/datenstand/fotoquellen" in js


def test_keine_häkchen_oder_statussymbole_in_den_neuen_texten():
    js, html, _ = _quelltext()
    block = js[js.index("function datenstandZahl("):]
    block = block[:block.index("(function () {")]
    verboten = re.compile("[\u2713\u2714\u2705\u274c\u26a0\U0001F300-\U0001FAFF"
                          "\u2600-\u26FF]")
    datenstand_html = html[html.index('id="datenstand"'):]
    datenstand_html = datenstand_html[:datenstand_html.index("</section>")]

    assert not verboten.search(block)
    assert not verboten.search(datenstand_html)
