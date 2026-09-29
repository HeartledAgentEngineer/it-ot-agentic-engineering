"""Tests: Selbsttest-Endpunkt GET /api/selbsttest.

Der Endpunkt soll den Zustand des Handys OHNE Kabel ablesbar machen. Diese
Tests prüfen über **echtes HTTP** gegen die echte App, dass

  * die Route existiert und wie die übrigen /api-Routen am API-Key-Schutz hängt,
  * IMMER dieselben Felder im JSON stehen,
  * fehlende Dateien einen ``error``-Text liefern statt eines Absturzes (nie 500),
  * die Protokoll-Auszüge bewusst gekürzt werden,
  * die SQLite-Zähler aus einer echten (temporären) Datenbank kommen,
  * keine Geheimnisse im JSON landen,
  * der pCloud-Block (seit 27.09.2026) nie 500er wirft: kein Schlüssel ->
    „nicht eingerichtet", vorhandener Schlüssel -> Konto (MASKIERT) + Quota,
    Fehler/Zeitüberschreitung -> ``error``-Text,
  * und beim Selbsttest **kein Netz-Call** passiert: Der pCloud-Dienst wird
    für jeden Test in diesem Modul durch eine Attrappe ersetzt (sonst würde
    der Testlauf auf Sebastians PC mit echtem Token wirklich ins Netz greifen).

Alle Pfade werden auf ein temporäres Verzeichnis umgebogen — nichts am echten
Gerät wird angefasst. Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_selbsttest.py -q
"""
import os
import sqlite3
import sys
import time
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.config import settings  # noqa: E402
from app.services.pcloud_service import PCloudFehler  # noqa: E402
import app.router.selbsttest as st  # noqa: E402

PFAD = "/api/selbsttest"

# Die Felder, die laut Auftrag IMMER vorhanden sein müssen.
PFLICHT_FELDER = {"commit", "index", "daemon", "letzte_antwort",
                  "gedaechtnis", "sprache", "uhrzeit", "pcloud", "fotos",
                  "beziehungen"}


class KeinNetz:
    """Stolperfalle: Jeder echte LLM-/Netz-Zugriff fliegt sofort auf."""

    def __getattr__(self, name):
        raise AssertionError(f"Echter Netz-Call versucht: {name}")


@pytest.fixture()
def client(monkeypatch):
    """TestClient gegen die echte App, ohne API-Key-Schutz der .env."""
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(settings, "api_key", None)
    return TestClient(app)


@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    """Leeres Ersatz-Zuhause: Postfach da, Dateien fehlen bewusst."""
    inbox = tmp_path / "hermes_inbox"
    inbox.mkdir()
    monkeypatch.setattr(st, "inbox_dir", lambda: str(inbox))
    monkeypatch.setattr(st, "index_pfad", lambda: str(tmp_path / "archiv_index.db"))
    return tmp_path


class FakePCloud:
    """Dienst-Attrappe: kein Netz, kein echter Token, nur die zwei Aufrufe.

    ``konfiguriert`` und ``ergebnis``/``fehler`` kann jeder Test direkt setzen
    (die Attrappe kommt über die autouse-Fixture herein). ``dauer`` lässt den
    Aufruf absichtlich schlafen — damit ist die Zeitüberschreitung prüfbar,
    ohne 8 Sekunden zu warten.
    """

    def __init__(self, konfiguriert=False, ergebnis=None, fehler=None,
                 host="eapi.test.example", token="test-token-nicht-echt"):
        self.konfiguriert = konfiguriert
        self.ergebnis = ergebnis
        self.fehler = fehler
        self.host = host
        self.token = token
        self.dauer = 0.0
        self.status_aufrufe = 0

    def ist_konfiguriert(self):
        return self.konfiguriert

    def status(self):
        self.status_aufrufe += 1
        if self.dauer:
            time.sleep(self.dauer)
        if self.fehler is not None:
            raise self.fehler
        return self.ergebnis


@pytest.fixture(autouse=True)
def fake_pcloud(monkeypatch) -> FakePCloud:
    """Jeder Test dieses Moduls bekommt die Attrappe statt des echten Dienstes.

    Wichtig: In ``backend/.env`` steht auf dem Entwicklungs-PC ein ECHTER
    pCloud-Schlüssel. Ohne diese Fixture würde der Selbsttest in vielen Tests
    wirklich ins Netz greifen — Tests dürfen das nie. Einzelne Tests setzen
    die Attrappe per eigenem ``monkeypatch`` um (läuft nach dieser Fixture).
    """
    dienst = FakePCloud()
    monkeypatch.setattr(st, "pcloud_service", dienst)
    return dienst


def _route(pfad):
    from app.main import app

    for route in app.routes:
        if getattr(route, "path", None) == pfad and "GET" in getattr(route, "methods", set()):
            return route
    return None


# ── Verdrahtung ──────────────────────────────────────────────────────────────

def test_route_ist_eingehaengt():
    """Der Endpunkt existiert und nimmt GET an."""
    assert _route(PFAD) is not None, f"{PFAD} fehlt in der App"


def test_route_haengt_am_api_key_schutz():
    """Wie die übrigen /api-Routen: ohne gültigen Key kein Zugriff."""
    route = _route(PFAD)
    assert route is not None
    namen = [getattr(d.call, "__name__", "") for d in route.dependant.dependencies]
    assert "require_api_key" in namen, f"Key-Schutz fehlt (Abhängigkeiten: {namen})"


# ── Grundverhalten ───────────────────────────────────────────────────────────

def test_antwortet_200_und_alle_felder_sind_da(client, fake_home):
    """200, und JEDES geforderte Feld ist vorhanden — auch ohne Quellen."""
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    daten = antwort.json()
    assert PFLICHT_FELDER.issubset(set(daten.keys())), \
        f"fehlende Felder: {PFLICHT_FELDER - set(daten.keys())}"


def test_selbsttest_macht_keinen_netz_call(client, fake_home, fake_pcloud):
    """Der Endpunkt prüft nur lokal — kein LLM-/Netz-Zugriff.

    Auch der pCloud-Block greift hier nicht ins Netz: Ohne Schlüssel (Standard
    der Attrappe) wird der Dienst gar nicht erst gefragt.
    """
    from app.services import llm_service as llm_mod

    with mock.patch.object(llm_mod.llm_service, "client", KeinNetz()):
        antwort = client.get(PFAD)
    assert antwort.status_code == 200
    assert fake_pcloud.status_aufrufe == 0


# ── Fehlende Quellen: error-Text statt Absturz ───────────────────────────────

def test_fehlende_dateien_ergeben_error_text_statt_500(client, fake_home):
    """Weder Index noch Logs noch jsonl sind da — trotzdem 200 mit error-Texten."""
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    daten = antwort.json()

    assert daten["index"]["existiert"] is False
    assert daten["index"]["error"], "Index ohne Datei muss error-Text tragen"
    assert daten["daemon"]["log_groesse_bytes"] is None
    assert daten["daemon"]["error"], "fehlendes daemon.log muss gemeldet werden"
    assert daten["letzte_antwort"]["antworten"]["error"]
    assert daten["letzte_antwort"]["status"]["error"]
    # Auch die gekürzten Felder bleiben vorhanden (kein KeyError im Frontend).
    for schluessel in ("antworten", "status"):
        block = daten["letzte_antwort"][schluessel]
        for feld in ("pfad", "existiert", "zeilen", "laenge", "auszug", "error"):
            assert feld in block, f"{schluessel} ohne Feld {feld}"


def test_kaputtes_git_ergibt_error_statt_500(client, fake_home, monkeypatch):
    """Fehlt git (oder bricht es ab), steht das als Text drin — kein 500."""
    def platzt(*args, **kwargs):
        raise FileNotFoundError("git fehlt")

    monkeypatch.setattr(st.subprocess, "run", platzt)
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    commit = antwort.json()["commit"]
    assert commit["ok"] is False
    assert commit["zeile"] is None
    assert "git" in commit["error"]


def test_git_kette_wird_gekuerzt_und_gelesen(client, fake_home, monkeypatch):
    """Glücklicher Fall: die erste Zeile von `git log --oneline -1` wird gezeigt."""
    class Lauf:
        returncode = 0
        stdout = "abc1234 Letzter Commit im Repo\n"
        stderr = ""

    monkeypatch.setattr(st.subprocess, "run", lambda *a, **k: Lauf())
    commit = client.get(PFAD).json()["commit"]
    assert commit["ok"] is True
    assert commit["zeile"] == "abc1234 Letzter Commit im Repo"
    assert commit["error"] is None


# ── Längenbegrenzung der Protokoll-Auszüge ───────────────────────────────────

def test_antwort_auszug_ist_bewusst_gekuerzt(client, fake_home):
    """Lange Zeilen werden geliefert, aber der Auszug bleibt bei 200 Zeichen."""
    zeile = "A" * 500
    (fake_home / "hermes_inbox" / "antworten.jsonl").write_text(
        '{"a": 1}\n' + zeile + "\n", encoding="utf-8")

    block = client.get(PFAD).json()["letzte_antwort"]["antworten"]
    assert block["existiert"] is True
    assert block["zeilen"] == 2          # beide Zeilen werden gezählt
    assert block["laenge"] == 500        # die volle Länge ist bekannt
    assert len(block["auszug"]) == st.AUSZUG_LAENGE == 200
    assert block["auszug"] == "A" * 200


def test_status_auszug_und_fehlende_zeilen(client, fake_home):
    """status.jsonl mit einem Eintrag; leere Datei wird ehrlich gemeldet."""
    (fake_home / "hermes_inbox" / "status.jsonl").write_text(
        '{"status": "laeuft"}\n', encoding="utf-8")
    (fake_home / "hermes_inbox" / "antworten.jsonl").write_text(
        "\n\n", encoding="utf-8")

    daten = client.get(PFAD).json()["letzte_antwort"]
    assert daten["status"]["zeilen"] == 1
    assert "laeuft" in daten["status"]["auszug"]
    assert daten["antworten"]["zeilen"] == 0
    assert daten["antworten"]["error"] == "keine Zeilen"


# ── Daemon ───────────────────────────────────────────────────────────────────

def test_daemon_log_groesse_alter_und_letzte_drei_zeilen(client, fake_home, monkeypatch):
    """Aus daemon.log kommen Größe, Alter und genau die letzten 3 Zeilen."""
    monkeypatch.setattr(st, "_daemon_laeuft", lambda: True)
    log = fake_home / "hermes_inbox" / "daemon.log"
    log.write_text("\n".join(f"Zeile {i}" for i in range(1, 8)) + "\n", encoding="utf-8")

    daemon = client.get(PFAD).json()["daemon"]
    assert daemon["laeuft"] is True
    assert daemon["log_groesse_bytes"] == log.stat().st_size
    assert daemon["log_alter_s"] is not None and daemon["log_alter_s"] >= 0
    assert daemon["log_letzte_zeilen"] == ["Zeile 5", "Zeile 6", "Zeile 7"]


def test_daemon_laeuft_unklar_wird_als_null_gemeldet(client, fake_home, monkeypatch):
    """Lässt sich der Daemon nicht feststellen, steht null da — keine Behauptung."""
    monkeypatch.setattr(st, "_daemon_laeuft", lambda: None)
    daemon = client.get(PFAD).json()["daemon"]
    assert daemon["laeuft"] is None


def test_daemon_pruefung_darf_nicht_crashen(client, fake_home, monkeypatch):
    """Wirft die Prozessprüfung, bleibt der Endpunkt bei 200 mit error-Text."""
    def platzt():
        raise RuntimeError("kaputt")

    monkeypatch.setattr(st, "_daemon_laeuft", platzt)
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    assert antwort.json()["daemon"]["error"]


# ── Archiv-Index (SQLite) ────────────────────────────────────────────────────

def test_index_zaehlt_nachrichten_und_chunks(client, fake_home):
    """Echte temporäre Datenbank: Größe und Zähler kommen aus der SQLite."""
    db = fake_home / "archiv_index.db"
    verbindung = sqlite3.connect(str(db))
    verbindung.execute("CREATE TABLE nachrichten(id INTEGER)")
    verbindung.execute("CREATE TABLE chunks(id INTEGER)")
    verbindung.executemany("INSERT INTO nachrichten VALUES (?)", [(i,) for i in range(5)])
    verbindung.executemany("INSERT INTO chunks VALUES (?)", [(i,) for i in range(7)])
    verbindung.commit()
    verbindung.close()

    info = client.get(PFAD).json()["index"]
    assert info["existiert"] is True
    assert info["nachrichten"] == 5
    assert info["chunks"] == 7
    assert info["groesse_mb"] is not None and info["groesse_mb"] >= 0
    assert info["error"] is None


def test_index_ohne_tabellen_bleibt_groesse_gueltig(client, fake_home):
    """Datei da, aber keine dieser Tabellen — Größe bleibt, Zähler fehlen."""
    db = fake_home / "archiv_index.db"
    verbindung = sqlite3.connect(str(db))
    verbindung.execute("CREATE TABLE irgendwas(id INTEGER)")
    verbindung.commit()
    verbindung.close()

    info = client.get(PFAD).json()["index"]
    assert info["existiert"] is True
    assert info["nachrichten"] is None
    assert info["chunks"] is None
    assert info["error"], "fehlende Tabellen müssen als error-Text erscheinen"


# ── Gedächtnis ───────────────────────────────────────────────────────────────

def test_gedaechtnis_zaehlt_wie_memory_count(client, fake_home, monkeypatch):
    """Derselbe Zählweg wie /api/memory/count."""
    monkeypatch.setattr(st, "_gedaechtnis_anzahl", lambda: 42)
    assert client.get(PFAD).json()["gedaechtnis"]["anzahl"] == 42


def test_gedaechtnis_fehler_ergibt_error_text(client, fake_home, monkeypatch):
    """Ist das Gedächtnis nicht lesbar, kommt ein error-Text, kein 500."""
    def platzt():
        raise RuntimeError("kaputt")

    monkeypatch.setattr(st, "_gedaechtnis_anzahl", platzt)
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    assert antwort.json()["gedaechtnis"]["error"]


# ── Sprache ──────────────────────────────────────────────────────────────────

def test_sprache_zeigt_kette_und_registrierte_endpunkte(client, fake_home):
    """Die Erkennungsmodelle stammen aus TRANSCRIBE_MODELS; die Wege sind da."""
    from app.services.llm_service import TRANSCRIBE_MODELS

    sprache = client.get(PFAD).json()["sprache"]
    assert sprache["modelle"] == [e[0] for e in TRANSCRIBE_MODELS]
    assert sprache["transcribe_registriert"] is True
    assert sprache["speak_registriert"] is True


# ── Uhrzeit ──────────────────────────────────────────────────────────────────

def test_uhrzeit_ist_vorhanden_und_maschinenlesbar(client, fake_home):
    """Serverzeit für die Zeitstempel-Prüfung: ISO-Format vorhanden."""
    uhrzeit = client.get(PFAD).json()["uhrzeit"]
    assert uhrzeit["iso"] and "T" in uhrzeit["iso"]
    assert uhrzeit["lokal"]


# ── Keine Geheimnisse ────────────────────────────────────────────────────────

def test_kein_schluessel_im_json(client, fake_home, monkeypatch):
    """Ein gesetzter API-Schlüssel darf NIRGENDS in der Antwort auftauchen."""
    geheim = "sk-or-v1-TESTGEHEIMNIS-1234567890"
    monkeypatch.setattr(settings, "openrouter_api_key", geheim)
    monkeypatch.setenv("OPENROUTER_API_KEY", geheim)

    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    rohtext = antwort.text
    assert geheim not in rohtext
    assert "sk-or-v1-" not in rohtext


def test_ausgabe_enthaelt_keine_verbotenen_felder(client, fake_home):
    """Die Antwort trägt nur die vereinbarten Bereiche — nichts Unerwartetes."""
    daten = client.get(PFAD).json()
    assert set(daten.keys()) == PFLICHT_FELDER


# ── pCloud-Block ─────────────────────────────────────────────────────────────

# Erfundene Adresse: Die MASKE ist das Einzige, was der Endpunkt zeigen darf.
VOLLE_EMAIL = "sebastian@example.com"
MASK_EMAIL = "se" + "*" * (len(VOLLE_EMAIL) - 6) + ".com"


def _pcloud_ergebnis(**felder):
    """Antwort-Attrappe in der Form, die ``pcloud_service.status()`` liefert."""
    grundlage = {
        "verbunden": True,
        "host": "eapi.test.example",
        "email": MASK_EMAIL,
        "userid": 1,
        "premium": True,
        "email_verifiziert": True,
        "quota_gb": 2199.0,
        "belegt_gb": 390.5,
        "frei_gb": 1808.5,
    }
    grundlage.update(felder)
    return grundlage


def test_pcloud_ohne_schluessel_ist_kein_fehler(client, fake_home, fake_pcloud):
    """Kein Schlüssel = gültiger Zustand: „nicht eingerichtet", kein Netzaufruf."""
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    block = antwort.json()["pcloud"]
    assert block == {"konfiguriert": False, "host": "eapi.test.example",
                     "konto": None, "quota_gb": None, "belegt_gb": None,
                     "error": None}
    assert fake_pcloud.status_aufrufe == 0, \
        "ohne Schlüssel darf der Dienst gar nicht gefragt werden"


def test_pcloud_konfiguriert_liefert_maske_quota_und_belegung(
        client, fake_home, fake_pcloud):
    """Vollständige Daten: nur die MASKE des Kontos, dazu Quota und Belegung."""
    fake_pcloud.konfiguriert = True
    fake_pcloud.ergebnis = _pcloud_ergebnis()

    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    block = antwort.json()["pcloud"]
    assert block["konfiguriert"] is True
    assert block["konto"] == MASK_EMAIL
    assert block["quota_gb"] == 2199.0
    assert block["belegt_gb"] == 390.5
    assert block["host"] == "eapi.test.example"
    assert block["error"] is None
    assert fake_pcloud.status_aufrufe == 1
    # Die VOLLE Adresse und der Token stehen nirgends in der Antwort.
    assert VOLLE_EMAIL not in antwort.text
    assert fake_pcloud.token not in antwort.text


def test_pcloud_dienstfehler_wird_zum_error_text_statt_500(
        client, fake_home, fake_pcloud):
    """Meldet pCloud einen Fehler, steht er als Text da — HTTP bleibt 200."""
    fake_pcloud.konfiguriert = True
    fake_pcloud.fehler = PCloudFehler("pCloud meldet Fehler 2001: Login failed.")

    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    block = antwort.json()["pcloud"]
    assert block["error"] == "pCloud meldet Fehler 2001: Login failed."
    assert block["konto"] is None and block["quota_gb"] is None


def test_pcloud_unerwarteter_fehler_ohne_token_im_text(client, fake_home, fake_pcloud):
    """Auch ein fremder Fehlertext (mit Token darin) wird entschärft — nie 500."""
    fake_pcloud.konfiguriert = True
    fake_pcloud.fehler = RuntimeError(f"kaputt bei auth={fake_pcloud.token}")

    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    text = antwort.json()["pcloud"]["error"]
    assert "kaputt bei auth=***" == text
    assert fake_pcloud.token not in antwort.text


def test_pcloud_token_taucht_in_keinem_log_auf(client, fake_home, fake_pcloud, caplog):
    """Der Schlüssel steht auch nicht im Log — dort wird nur die Fehlerklasse genannt."""
    fake_pcloud.konfiguriert = True
    fake_pcloud.fehler = RuntimeError(f"kaputt bei auth={fake_pcloud.token}")

    with caplog.at_level("DEBUG"):
        assert client.get(PFAD).status_code == 200
    assert fake_pcloud.token not in caplog.text
    assert fake_pcloud.token not in " ".join(r.getMessage() for r in caplog.records)


def test_pcloud_zeitueberschreitung_meldet_ehrlich(client, fake_home, fake_pcloud,
                                                   monkeypatch):
    """Der eigene Rahmen greift: Der Selbsttest hängt nicht am 20-s-Timeout.

    ``PCLOUD_TIMEOUT_S`` wird für den Test klein gestellt und der Aufruf
    schläft länger — gemeldet wird die Zeitüberschreitung, nicht gewartet.
    """
    fake_pcloud.konfiguriert = True
    fake_pcloud.dauer = 0.5
    monkeypatch.setattr(st, "PCLOUD_TIMEOUT_S", 0.05)

    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    assert antwort.json()["pcloud"]["error"] == \
        "pCloud nicht erreichbar (Zeitueberschreitung)"
    assert fake_pcloud.status_aufrufe == 1


def test_pcloud_unerwartete_antwort_wird_gemeldet(client, fake_home, fake_pcloud):
    """Liefert der Dienst etwas anderes als ein Dict: Klartext statt Absturz."""
    fake_pcloud.konfiguriert = True
    fake_pcloud.ergebnis = ["kein", "dict"]

    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    block = antwort.json()["pcloud"]
    assert block["error"] == "pCloud lieferte eine unerwartete Antwort"
    assert block["konto"] is None


def test_pcloud_kaputte_konfiguration_wird_gemeldet(client, fake_home, monkeypatch):
    """Wirft schon die Konfigurationsprüfung, bleibt es bei 200 mit error-Text."""
    class Kaputt:
        def ist_konfiguriert(self):
            raise RuntimeError("kaputt")

        @property
        def host(self):
            raise RuntimeError("kaputt")

        token = ""

    monkeypatch.setattr(st, "pcloud_service", Kaputt())
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    assert "pCloud-Konfiguration nicht lesbar" in antwort.json()["pcloud"]["error"]


# ── Der Kürzungs-Helfer selbst ───────────────────────────────────────────────

def test_kuerzen_ist_robust():
    """None -> '', Zeilenumbrüche werden zu Leerzeichen, Länge greift."""
    assert st._kuerzen(None) == ""
    assert st._kuerzen("a\nb") == "a b"
    assert st._kuerzen("x" * 300) == "x" * 200
