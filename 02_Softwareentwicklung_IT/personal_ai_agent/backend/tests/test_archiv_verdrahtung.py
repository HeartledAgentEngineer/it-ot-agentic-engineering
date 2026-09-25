"""Verdrahtungs-Tests: Wissensspeicher im Betrieb (Router, Prompt, Setting, Schluessel).

Diese Datei sichert die drei Punkte ab, die den Wissensspeicher erst
wirksam machen (Sebastian, 25.09.2026 — „Er weiß, er hat eine
Wissensdatenbank — er müsste es wissen."):

  (a) `archiv_wissen.router` ist in `app.main` eingehaengt und antwortet;
      alter (`router/archiv.py`) und neuer Router liegen nebeneinander, ohne
      sich zu ueberschneiden (Pfade verglichen).
  (b) Der Bewusstseins-Baustein steht in den gebauten Messages — **auch ohne
      Suchtreffer**.
  (c) Er ist kurz (<= 600 Zeichen) und traegt ausschliesslich Metadaten
      (keine Gespraechsinhalte, keine Titel).
  (d) Ohne Einbettungs-Schluessel bleibt die Volltextsuche nutzbar und der
      Hinweis „Bedeutungssuche aus" ist sichtbar — kein stiller Ausfall.
  (e) `archiv_index_path` ist ein echtes Setting: gesetzt laedt die Suche;
      ein falscher Pfad degradiert ehrlich statt zu crashen.
  (f) Keine Doppel-Injektion: der Baustein steht genau einmal im Prompt.

**Wichtig:** Wie in `test_archiv_suche.py` wird das echte Archiv nie
angefasst. Jeder Test baut sich im `tmp_path` einen winzigen Index aus
kuenstlichen Gespraechen; die Einbettung ist eine Attrappe (kein Netz, kein
Schluessel, keine Kosten). Der einzige Test, der die *echten* Einstellungen
liest, liest ausschliesslich einen **Variablennamen** — nie einen Wert.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app import config as config_mod  # noqa: E402
from app.config import settings  # noqa: E402
from app.services import archiv_suche as archiv_suche_mod  # noqa: E402
from app.services import llm_service as llm_service_mod  # noqa: E402
from app.services.archiv_suche import ArchivSuche  # noqa: E402
from scripts.archiv_index_bauen import baue_index  # noqa: E402

# ── Kuenstliche Testdaten ──────────────────────────────────────────────────
# Bewusst harmlose Beispielsaetze MIT eigenen Markern: Was im Baustein nicht
# auftauchen darf, laesst sich damit eindeutig pruefen (sonst koennte ein
# zufaellig gleiches Wort aus dem echten Archiv den Test verfaelschen).

MARKER_TITEL = "TITELMARKER"
MARKER_INHALT = "INHALTSMARKER"

GESPRAECHE = [
    {
        "conversation_id": "chat-a",
        "source": "chatgpt",
        "title": f"{MARKER_TITEL}-A Gespraech",
        "datum": "2023-03-01T09:00:00+00:00",
        "nachrichten": [
            ("user", f"Ich suche eine Wohnung, {MARKER_INHALT}-A steht im Original."),
            ("assistant", "In Horn sind die Mieten guenstiger."),
        ],
        "chunk": f"Ich suche eine Wohnung, {MARKER_INHALT}-A steht im Original.",
    },
    {
        "conversation_id": "chat-b",
        "source": "gemini",
        "title": f"{MARKER_TITEL}-B Gespraech",
        "datum": "2024-05-02T14:30:00+00:00",
        "nachrichten": [
            ("user", f"Die EasyBank hat meine Ueberweisung abgelehnt, {MARKER_INHALT}-B."),
            ("assistant", "Pruefe zuerst das Limit."),
        ],
        "chunk": f"Die EasyBank hat meine Ueberweisung abgelehnt, {MARKER_INHALT}-B.",
    },
    {
        "conversation_id": "chat-c",
        "source": "claude-code",
        "title": f"{MARKER_TITEL}-C Gespraech",
        "datum": "2025-06-07T07:15:00+00:00",
        "nachrichten": [
            ("user", f"Mein TwinCAT Projekt baut nicht, {MARKER_INHALT}-C."),
        ],
        "chunk": f"Mein TwinCAT Projekt baut nicht, {MARKER_INHALT}-C.",
    },
]


def _attrappe_einbetter(texte):
    """Einbetter fuer den Indexbau: kein Netz, kein Schluessel, deterministisch."""
    return [[0.5, 0.5, 0.5, 0.5] for _ in texte], len(texte)


def _quell_db_bauen(pfad: str, gespraeche) -> None:
    """Ein winziges Quell-Archiv im Format des Schwesterprojekts."""
    con = sqlite3.connect(pfad)
    con.executescript(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
            timestamp TEXT, role TEXT NOT NULL, text TEXT NOT NULL, title TEXT, project TEXT
        );
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
            text TEXT NOT NULL, nachricht_ids TEXT NOT NULL, beginn TEXT, ende TEXT,
            title TEXT, project TEXT, teil INTEGER NOT NULL DEFAULT 0,
            hat_vektor INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    naechste = 0
    for nr, g in enumerate(gespraeche, start=1):
        anfang = naechste
        for rolle, text in g["nachrichten"]:
            con.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)",
                (naechste, g["conversation_id"], g["source"], g["datum"], rolle,
                 text, g["title"], None),
            )
            naechste += 1
        con.execute(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (nr, g["conversation_id"], g["source"], g["chunk"],
             json.dumps(list(range(anfang, naechste))), g["datum"], g["datum"],
             g["title"], None, 0, 0),
        )
    con.commit()
    con.close()


@pytest.fixture
def winz_index(tmp_path) -> str:
    """Pfad zu einem winzigen Index (3 Gespraeche, mit Vektoren)."""
    quelle = os.path.join(str(tmp_path), "quelle.db")
    ziel = os.path.join(str(tmp_path), "archiv_index.db")
    _quell_db_bauen(quelle, GESPRAECHE)
    bericht = baue_index(
        quelle_db=quelle,
        ausgabe=ziel,
        archiv_wurzel=None,
        einbetter=_attrappe_einbetter,
        ausgabe_strom=io.StringIO(),
    )
    assert bericht["chunks"] == len(GESPRAECHE)
    assert bericht["vektoren"] == len(GESPRAECHE)
    return ziel


@pytest.fixture
def winz_dienst(winz_index, monkeypatch) -> ArchivSuche:
    """Der winzige Index als Dienst — an BEIDEN Stellen eingetragen.

    Der Eintrag in ``archiv_suche.archiv_suche`` ist noetig, weil
    ``prompt_baustein(kurz=True)`` genau diesen globalen Dienst liest: nur so
    prueft der Test die *echte* Verdrahtung statt einer Attrappe. Der zweite
    Eintrag im Router-Modul ist noetig, weil ``router/archiv_wissen.py`` den
    Dienst beim Import in seinen eigenen Namensraum gebunden hat
    (``from ... import archiv_suche``) — ohne ihn antwortet der Endpunkt
    weiterhin aus dem echten Archiv.
    """
    from app.router import archiv_wissen as router_mod

    dienst = ArchivSuche(pfad=winz_index)
    monkeypatch.setattr(archiv_suche_mod, "archiv_suche", dienst)
    monkeypatch.setattr(router_mod, "archiv_suche", dienst)
    return dienst


def _ohne_schluessel(monkeypatch) -> None:
    """Kein Einbettungs-Schluessel — weder in den Settings noch in der Umgebung."""
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


# ── (a) Router: eingehaengt und ohne Ueberschneidung ───────────────────────
def _routen(app):
    """Alle (Pfad, Methode)-Paare einer FastAPI-App."""
    paare = []
    for route in app.routes:
        pfad = getattr(route, "path", None)
        methoden = getattr(route, "methods", None)
        if not pfad or not methoden:
            continue
        for methode in methoden:
            paare.append((pfad, methode))
    return sorted(paare)


def test_beide_archiv_router_sind_eingehaengt():
    """Alter und neuer Archiv-Router existieren nebeneinander."""
    from app.main import app

    pfade = {p for p, _ in _routen(app)}
    # Vorhanden (vorher schon): router/archiv.py
    assert "/api/archiv/status" in pfade
    assert "/api/archiv/suche" in pfade
    # Neu (25.09.2026): router/archiv_wissen.py
    for neu in (
        "/api/archiv/wissen/statistik",
        "/api/archiv/wissen/chronik",
        "/api/archiv/wissen/frage",
        "/api/archiv/wissen/original",
        "/api/archiv/wissen/ueberblick",
    ):
        assert neu in pfade, f"{neu} fehlt in app.main"


def test_archiv_router_ueberschneiden_sich_nicht():
    """Keine Route doppelt, kein Pfad des neuen Routers auf einem alten.

    Die beiden Router teilen sich nur den Anfang `/api/archiv`: der alte
    bedient `/status` und `/suche`, der neue alles unter `/wissen/`. Weil
    weder der alte noch der neue Router Pfad-Platzhalter benutzt (kein
    `{...}`), kann keine Route eine andere verdecken — auch nicht beim
    Matching in Registrierungsreihenfolge.
    """
    from app.main import app

    routen = _routen(app)
    assert len(routen) == len(set(routen)), "doppelte Route (Pfad+Methode)"

    alt = {p for p, _ in routen if p.startswith("/api/archiv/") and not p.startswith("/api/archiv/wissen")}
    neu = {p for p, _ in routen if p.startswith("/api/archiv/wissen")}
    assert alt == {"/api/archiv/status", "/api/archiv/suche"}, alt
    assert len(neu) == 5, neu
    assert alt & neu == set()
    assert not any("{" in p for p in (alt | neu)), "Platzhalter wuerden verdecken koennen"


def test_api_routen_stehen_vor_dem_frontend_mount():
    """Der Frontend-Mount (faengt alles unter / ab) kommt zuletzt."""
    from app.main import app

    positionen = {
        getattr(route, "path", ""): i for i, route in enumerate(app.routes)
    }
    mount = positionen.get("")
    if mount is None:
        pytest.skip("kein Frontend-Mount vorhanden (Frontend-Ordner fehlt)")
    for pfad in ("/api/archiv/status", "/api/archiv/wissen/statistik"):
        assert positionen[pfad] < mount, f"{pfad} liegt hinter dem Mount und waere verdeckt"


def test_router_antwortet_ueber_echtes_http(winz_dienst, monkeypatch):
    """Der eingehaengte Router antwortet (echter App, winziger Index)."""
    from fastapi.testclient import TestClient

    from app.main import app

    # Der API-Key-Schutz haengt an der .env des Nutzers; fuer den Test wird er
    # ausdruecklich ausgeschaltet, damit die Aussage nicht vom Rechner abhaengt.
    monkeypatch.setattr(settings, "api_key", None)

    client = TestClient(app)
    antwort = client.get("/api/archiv/wissen/statistik")
    assert antwort.status_code == 200
    assert antwort.json()["gesamt"]["gespraeche"] == len(GESPRAECHE)

    antwort = client.get("/api/archiv/wissen/chronik", params={"limit": 2})
    assert antwort.status_code == 200
    assert antwort.json()["verfuegbar"] is True

    # Und der ALTE Router antwortet weiterhin (nichts verdeckt).
    assert client.get("/api/archiv/status").status_code == 200


def test_router_antwortet_auch_mit_echtem_dienst():
    """Ohne Attrappe: der Endpunkt laeuft gegen die echten Einstellungen.

    Auf dem PC mit Index kommen Zahlen, ohne Index kommt ehrlich
    `verfuegbar: False` — beides ist ein 200 und kein Absturz.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    alt_key = settings.api_key
    settings.api_key = None
    try:
        antwort = TestClient(app).get("/api/archiv/wissen/statistik")
    finally:
        settings.api_key = alt_key
    assert antwort.status_code == 200
    assert "verfuegbar" in antwort.json()


# ── (b) Bewusstseins-Baustein steht im Prompt — auch ohne Treffer ──────────
def test_baustein_steht_im_prompt_ohne_treffer():
    """Der Kern der Verdrahtung: ohne jede Suche ist der Baustein da."""
    messages = llm_service_mod.llm_service._build_messages(
        "Was habe ich damals besprochen?"
    )
    system = messages[0]
    assert system["role"] == "system"
    assert "WISSENSSPEICHER" in system["content"]


def test_baustein_steht_auch_bei_leerer_trefferliste():
    """Auch wenn ausdruecklich KEINE Treffer uebergeben werden, bleibt er."""
    messages = llm_service_mod.llm_service._build_messages(
        "Was habe ich damals besprochen?", archiv=[]
    )
    assert "WISSENSSPEICHER" in messages[0]["content"]


def test_baustein_ist_der_aus_dem_dienst(winz_dienst):
    """Der Text im Prompt ist genau der, den der Dienst liefert (keine Kopie)."""
    erwartet = archiv_suche_mod.prompt_baustein(kurz=True)
    messages = llm_service_mod.llm_service._build_messages("Erzaehl mir von damals")
    assert erwartet in messages[0]["content"]


# ── (c) kurz und nur Metadaten ─────────────────────────────────────────────
def test_baustein_ist_kurz(winz_dienst, monkeypatch):
    """<= 600 Zeichen — mit und ohne Schluessel (die ehrliche Fassung ist laenger)."""
    monkeypatch.setattr(settings, "openrouter_api_key", "nur-ein-testwert")
    mit_schluessel = archiv_suche_mod.prompt_baustein(kurz=True)
    _ohne_schluessel(monkeypatch)
    ohne_schluessel = archiv_suche_mod.prompt_baustein(kurz=True)

    assert len(mit_schluessel) <= 600, len(mit_schluessel)
    assert len(ohne_schluessel) <= 600, len(ohne_schluessel)


def test_baustein_nennt_zahlen_quellen_zeitraum_und_regel(winz_dienst):
    """Inhalt: Anzahl, Quellen, Zeitraum, Nutzungsregel — maschinell geprueft."""
    text = archiv_suche_mod.prompt_baustein(kurz=True)

    assert "WISSENSSPEICHER" in text
    # Anzahl + Zeitraum aus dem winzigen Index
    assert str(len(GESPRAECHE)) in text
    assert "2023-03-01" in text and "2025-06-07" in text
    # Quellen (Metadaten, keine Inhalte)
    for quelle in ("chatgpt", "gemini", "claude-code"):
        assert quelle in text
    # Nutzungsregel: zuerst hier, Original nachlesen, nicht im Web, Rueckfrage
    assert "ZUERST hier" in text
    assert "Original nachlesen" in text
    assert "NICHT im Web" in text
    assert "Rückfrage" in text


def test_baustein_enthaelt_keine_archivinhalte(winz_dienst):
    """Nur Metadaten: kein Titel, kein Nachrichtentext, kein Chunktext."""
    text = archiv_suche_mod.prompt_baustein(kurz=True)

    assert MARKER_TITEL not in text
    assert MARKER_INHALT not in text
    for g in GESPRAECHE:
        assert g["title"] not in text
        assert g["chunk"] not in text
        assert g["conversation_id"] not in text
    # und auch kein Bruchstueck des Originaltextes
    assert "Wohnung" not in text
    assert "EasyBank" not in text


def test_baustein_ist_bei_fehlendem_index_ehrlich(tmp_path):
    """Ohne erreichbaren Index sagt der Baustein das — statt zu schweigen."""
    leer = ArchivSuche(pfad=str(tmp_path / "gibtsnicht.db"))
    text = leer.ueberblick_kurz()
    assert "WISSENSSPEICHER" in text
    assert "NICHT" in text and "angebunden" in text
    assert len(text) <= 600


# ── (d) ohne Schluessel: Volltext bleibt, Hinweis sichtbar ─────────────────
def test_ohne_schluessel_bleibt_volltext_und_hinweis_ist_sichtbar(
    winz_index, monkeypatch
):
    """Ehrliche Degradation: Wortlaut ja, Bedeutung nein, Hinweis sichtbar."""
    _ohne_schluessel(monkeypatch)
    dienst = ArchivSuche(pfad=winz_index)  # kein injizierter Einbetter

    ergebnis = dienst.hybrid("EasyBank", top_k=5)
    assert ergebnis["wege"]["volltext"] is True
    assert ergebnis["wege"]["vektor"] is False
    assert ergebnis["wege"]["vektor_status"] == "kein_schluessel"
    assert ergebnis["anzahl"] >= 1
    assert any(t["zeiger"]["chat_kennung"] == "chat-b" for t in ergebnis["treffer"])

    hinweis = ergebnis.get("hinweis") or ""
    assert "Einbettungs-Schlüssel" in hinweis
    assert "OPENROUTER_API_KEY" in hinweis

    # Derselbe Hinweis steht auch im Prompt-Baustein (dort „Bedeutungssuche aus").
    assert "Bedeutungssuche aus: kein Schlüssel" in dienst.ueberblick_kurz()


def test_ohne_schluessel_kein_nicht_erklaerbarer_absturz(winz_index, monkeypatch):
    """Auch die Vektorsuche selbst bleibt benutzbar: sie liefert nur nichts."""
    _ohne_schluessel(monkeypatch)
    dienst = ArchivSuche(pfad=winz_index)
    treffer, status = dienst._semantisch_mit_status("EasyBank")
    assert treffer == []
    assert status == "kein_schluessel"


def test_config_meldet_fehlenden_schluessel_ehrlich(tmp_path, monkeypatch):
    """Kein Schluessel in Umgebung UND keiner in der Workspace-Wurzel-.env."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(config_mod, "WORKSPACE_ENV_FILE", tmp_path / "gibtsnicht.env")
    neu = config_mod.Settings()
    assert (neu.openrouter_api_key or "") == ""

    # Und der Dienst degradiert entsprechend (Volltext statt Absturz).
    dienst = ArchivSuche(pfad=str(tmp_path / "leer.db"))
    assert dienst.hybrid("egal")["grund"] == "kein_index"


# ── (e) archiv_index_path ist ein echtes Setting ───────────────────────────
def test_archiv_index_path_setting_laedt_den_index(winz_index, monkeypatch):
    """Gesetztes Setting gewinnt: die Suche laedt genau diese Datei."""
    monkeypatch.setattr(settings, "archiv_index_path", winz_index)
    monkeypatch.delenv("ARCHIV_INDEX_PATH", raising=False)

    dienst = ArchivSuche()
    assert dienst.is_available is True
    pfad = dienst.pfad
    assert pfad is not None and os.path.samefile(pfad, winz_index)
    assert dienst.statistik()["gesamt"]["gespraeche"] == len(GESPRAECHE)


def test_falscher_pfad_faellt_durch_statt_zu_crashen(tmp_path, winz_index, monkeypatch):
    """Kandidatenliste: ein nicht vorhandener erster Pfad blockiert nicht."""
    fehlt = str(tmp_path / "toter-pfad.db")
    monkeypatch.setattr(settings, "archiv_index_path", fehlt)
    monkeypatch.setenv("ARCHIV_INDEX_PATH", winz_index)

    kandidaten = ArchivSuche._pfad_kandidaten()
    assert kandidaten[0] == fehlt           # Setting zuerst
    assert kandidaten[1] == winz_index      # Umgebungsvariable danach
    gefunden = ArchivSuche().pfad            # erster ECHTER gewinnt
    assert gefunden is not None and os.path.samefile(gefunden, winz_index)


def test_umgebungsvariable_archiv_index_path_wird_gelesen(tmp_path, winz_index, monkeypatch):
    """Auch ohne Setting greift $ARCHIV_INDEX_PATH (dokumentierte Reihenfolge)."""
    monkeypatch.setattr(settings, "archiv_index_path", "")
    monkeypatch.setenv("ARCHIV_INDEX_PATH", winz_index)
    gefunden = ArchivSuche().pfad
    assert gefunden is not None and os.path.samefile(gefunden, winz_index)


def test_gar_kein_index_degradiert_ehrlich(tmp_path):
    """Nichts da: kein Crash, sondern klare Meldungen (auch im Baustein)."""
    dienst = ArchivSuche(pfad=str(tmp_path / "nichts.db"))
    assert dienst.is_available is False

    ergebnis = dienst.hybrid("irgendwas")
    assert ergebnis["grund"] == "kein_index"
    assert ergebnis["sicher"] is False
    assert ergebnis["treffer"] == []
    assert ergebnis["rueckfrage"]

    assert dienst.statistik()["verfuegbar"] is False
    assert dienst.chronik()["verfuegbar"] is False
    assert dienst.original("chat-a", 0)["gefunden"] is False
    assert dienst.ueberblick()["vorhanden"] is False
    assert "NICHT" in dienst.ueberblick_kurz()


# ── (f) keine Doppel-Injektion ─────────────────────────────────────────────
def test_baustein_steht_genau_einmal_im_prompt(winz_dienst):
    """Einmal, nicht zweimal — egal ob mit oder ohne Treffer."""
    ohne = llm_service_mod.llm_service._build_messages("Was war damals?")
    assert ohne[0]["content"].count("WISSENSSPEICHER") == 1

    treffer = winz_dienst.hybrid("EasyBank")["treffer"]
    assert treffer, "Testdaten muessen zu 'EasyBank' einen Treffer liefern"
    mit = llm_service_mod.llm_service._build_messages("Was war damals?", archiv=treffer)
    assert mit[0]["content"].count("WISSENSSPEICHER") == 1


def test_baustein_und_treffer_haben_klare_reihenfolge(winz_dienst):
    """Erst das Bewusstsein (Baustein), dann die Fundstellen — nichts doppelt."""
    treffer = winz_dienst.hybrid("EasyBank")["treffer"]
    prompt = llm_service_mod.llm_service._build_messages(
        "Was war damals?", archiv=treffer
    )[0]["content"]

    assert "WISSENSSPEICHER" in prompt
    assert "AUS DEINEN FRÜHEREN GESPRÄCHEN" in prompt
    assert prompt.index("WISSENSSPEICHER") < prompt.index("AUS DEINEN FRÜHEREN GESPRÄCHEN")
    # Die Fundstelle steht genau einmal (kein Treffer doppelt im Prompt).
    assert prompt.count("Die EasyBank hat meine Ueberweisung abgelehnt") == 1


# ── Schluessel-Fallback: genau EIN Variablenname aus der Workspace-Wurzel ──
def test_fallback_liest_genau_eine_variable(tmp_path, monkeypatch):
    """Fremde Variablen aus der Nachbar-.env duerfen die App NICHT umstellen."""
    fremd = tmp_path / ".env"
    fremd.write_text(
        "HOST=9.9.9.9\nPORT=1\nOPENROUTER_API_KEY=nur-ein-testwert\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_mod, "WORKSPACE_ENV_FILE", fremd)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    neu = config_mod.Settings()
    assert neu.openrouter_api_key == "nur-ein-testwert"   # genau dieser Name
    assert neu.host != "9.9.9.9"                          # HOST bleibt unberuehrt
    assert neu.port != 1                                  # PORT bleibt unberuehrt


def test_fallback_erkennt_export_schreibweise_und_anfuehrungszeichen(tmp_path):
    datei = tmp_path / ".env"
    datei.write_text(
        '# Kommentar\nexport OPENROUTER_API_KEY="nur-ein-testwert"\n',
        encoding="utf-8",
    )
    assert config_mod.variable_aus_env_datei(datei, "OPENROUTER_API_KEY") == "nur-ein-testwert"
    # Fehlende Datei / fehlender Name: leer, kein Fehler.
    assert config_mod.variable_aus_env_datei(tmp_path / "nix.env", "OPENROUTER_API_KEY") == ""
    assert config_mod.variable_aus_env_datei(datei, "ETWAS_ANDERES") == ""


def test_fallback_variablenname_ist_dokumentiert_und_eng():
    """Der Fallback ist auf genau einen Namen festgelegt (nichts anderes)."""
    assert config_mod.SCHLUESSEL_FALLBACK_VARIABLE == "OPENROUTER_API_KEY"
    assert config_mod.WORKSPACE_ENV_FILE.name == ".env"


def test_workspace_env_nennt_den_variablennamen():
    """Auf diesem Rechner: der Name steht in der Workspace-Wurzel-.env.

    Gelesen wird ausschliesslich der **Name** (alles vor dem '='), nie ein
    Wert. Fehlt die Datei (z. B. auf dem Handy), wird der Test uebersprungen.
    """
    datei = config_mod.WORKSPACE_ENV_FILE
    if not datei.is_file():
        pytest.skip(f"keine Workspace-Wurzel-.env auf diesem Rechner ({datei})")
    namen = set()
    for zeile in datei.read_text(encoding="utf-8", errors="replace").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        name = zeile.split("=", 1)[0].strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        namen.add(name)
    assert config_mod.SCHLUESSEL_FALLBACK_VARIABLE in namen
