"""Offline-Tests für die Erwähnungssuche (N19, 2026-09-29).

Was hier geprüft wird
=====================

Sebastians Frage „was habe ich mit X gemacht?" fand bisher nichts, obwohl das
Archiv die Person mehrfach enthält — weil gesucht wurde nur nach dem
*Gegenüber* eines Gesprächs, nicht nach **Erwähnungen**. Diese Datei prüft die
neue Erwähnungssuche:

  - ``ArchivSuche.erwaehnung_treffer`` (Dienst, rein lesend),
  - ``erwaehnungs_text`` (reine Funktion, baut die Notiz für das Modell),
  - die Verdrahtung in ``app.router.chat._archiv_tool`` samt ``_erwaehnung_name``.

Alles **offline**: Der Index wird hier winzig selbst gebaut (Tabellen
``nachrichten``, ``chunks``, ``chunks_fts``, ``gespraeche``, ``meta``) und
enthält ausschliesslich **erfundene** Namen und Titel. Kein Netz, kein
Einbettungs-Aufruf, kein Zugriff auf das echte Archiv. Die Testdatei zählt ihre
Einzelprüfungen selbst (siehe ``_pruefe``) — die Zahl steht im Bericht.
"""

import hashlib
import inspect
import os
import re
import sqlite3
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router.chat import _archiv_tool, _erwaehnung_name  # noqa: E402
from app.services.archiv_suche import (  # noqa: E402
    ArchivSuche,
    erwaehnungs_text,
)

# Zähler der Einzelprüfungen dieser Datei (steht im Bericht).
PRUEFUNGEN = []


def _pruefe(bedingung, text: str) -> None:
    """Eine Einzelprüfung zählen und sofort hart prüfen."""
    PRUEFUNGEN.append((bool(bedingung), text))
    assert bedingung, text


@pytest.fixture(scope="session", autouse=True)
def _pruefbericht():
    yield
    bestanden = sum(1 for ok, _ in PRUEFUNGEN if ok)
    print(f"\n[Erwaehnungssuche] {bestanden}/{len(PRUEFUNGEN)} Einzelpruefungen bestanden.")


# ── Ein winziger Index mit erfundenen Namen ────────────────────────────────
# Erwin: nur Erwähnungen in fremden Gesprächen (kein eigener Chat).
# Marga: eigene Gesprächsttitel tragen den Namen.
# Norbert: kommt nirgends vor.
GESPRAECHE = [
    {
        "conversation_id": "gespraech-grill",
        "source": "whatsapp",
        "title": "Wochenendplanung",
        "datum": "2024-05-02T18:00:00+00:00",
        "chunks": [
            (0, "Am Samstag kommt Erwin vorbei und bringt den Grill mit."),
            (1, "Erwin hat abgesagt, wir grillen ohne ihn."),
        ],
    },
    {
        "conversation_id": "gespraech-belege",
        "source": "chatgpt",
        "title": "Steuerunterlagen sortieren",
        "datum": "2023-11-10T09:00:00+00:00",
        "chunks": [
            (2, "Kurze Frage zu Erwin und der alten Rechnung von damals."),
        ],
    },
    {
        "conversation_id": "gespraech-marga",
        "source": "google-kalender",
        "title": "Termin mit Marga",
        "datum": "2024-01-05T12:00:00+00:00",
        "chunks": [
            (3, "Marga bringt Kuchen mit."),
            (4, "Marga hat zugesagt."),
        ],
    },
]

SCHEMA = """
CREATE TABLE meta (schluessel TEXT PRIMARY KEY, wert TEXT);
CREATE TABLE gespraeche (
    conversation_id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT,
    quelldatei TEXT, von TEXT, bis TEXT,
    anzahl_nachrichten INTEGER NOT NULL DEFAULT 0,
    anzahl_chunks INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE nachrichten (
    id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
    timestamp TEXT, role TEXT NOT NULL, text TEXT NOT NULL, title TEXT, project TEXT
);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
    text TEXT NOT NULL, nachricht_ids TEXT NOT NULL, beginn TEXT, ende TEXT,
    title TEXT, project TEXT, teil INTEGER NOT NULL DEFAULT 0,
    quelldatei TEXT, hat_vektor INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    text, content='chunks', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
"""


def _index_bauen(tmp_path) -> str:
    """Den winzigen Testindex anlegen — nur erfundene Personen und Titel."""
    pfad = os.path.join(str(tmp_path), "archiv_index.db")
    con = sqlite3.connect(pfad)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO meta VALUES ('gebaut', 'test')")
    nachricht_id = 0
    for g in GESPRAECHE:
        for _teil, _text in g["chunks"]:
            con.execute(
                "INSERT INTO nachrichten VALUES (?,?,?,?,?,?,?,?)",
                (nachricht_id, g["conversation_id"], g["source"], g["datum"],
                 "user", "Platzhalter.", g["title"], None),
            )
            nachricht_id += 1
        for chunk_id, text in g["chunks"]:
            con.execute(
                "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (chunk_id, g["conversation_id"], g["source"], text,
                 f"[{chunk_id}]", g["datum"], g["datum"], g["title"], None, 0,
                 "export/quelle.jsonl", 0),
            )
            con.execute(
                "INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)",
                (chunk_id, text),
            )
        con.execute(
            "INSERT INTO gespraeche VALUES (?,?,?,?,?,?,?,?)",
            (g["conversation_id"], g["source"], g["title"], "export/quelle.jsonl",
             g["datum"], g["datum"], len(g["chunks"]), len(g["chunks"])),
        )
    con.commit()
    con.close()
    return pfad


@pytest.fixture
def index_pfad(tmp_path) -> str:
    return _index_bauen(tmp_path)


@pytest.fixture
def dienst(index_pfad) -> ArchivSuche:
    return ArchivSuche(pfad=index_pfad)


class _FakeArchiv:
    """Minimaler Dienst-Stand-in: kennt Erwähnungssuche UND Hybridsuche."""

    def __init__(self):
        self.is_available = True
        self.erwaehnung_aufrufe = []
        self.hybrid_aufrufe = []

    def erwaehnung_treffer(self, name, top_k=8):
        self.erwaehnung_aufrufe.append(name)
        return {
            "name": name, "treffer": [], "je_quelle": {}, "anzahl": 0,
            "eigene_chats": 0, "eigene_chat_titel": [],
            "nur_erwaehnungen": False, "hinweis": "nichts dazu", "fehler": None,
        }

    def hybrid(self, frage):
        self.hybrid_aufrufe.append(frage)
        return [{
            "text": "Eine alte Stelle aus der Vergangenheit.",
            "source": "chatgpt", "beginn": "2023-01-01T00:00:00+00:00",
            "title": "Alt",
        }]


# ── 1. Person nur als Erwähnung in fremden Gesprächen ──────────────────────
def test_erwaehnung_nur_erwaehnungen(dienst):
    ergebnis = dienst.erwaehnung_treffer("Erwin")
    _pruefe(ergebnis["name"] == "Erwin", "name kommt zurück")
    _pruefe(ergebnis["anzahl"] > 0, "Erwin hat Fundstellen")
    _pruefe(ergebnis["eigene_chats"] == 0, "kein eigener Chat mit Erwin")
    _pruefe(ergebnis["nur_erwaehnungen"] is True, "nur Erwähnungen")
    _pruefe("Erwähnung" in ergebnis["hinweis"], "Hinweis nennt die Erwähnung")
    _pruefe(ergebnis["fehler"] is None, "kein Fehler")
    _pruefe(dienst.erwaehnung_treffer("Erwin").get("anzahl") == ergebnis["anzahl"],
            "Ergebnis ist wiederholbar")


# ── 2. Person mit eigenem Chat ─────────────────────────────────────────────
def test_erwaehnung_mit_eigenem_chat(dienst):
    ergebnis = dienst.erwaehnung_treffer("Marga")
    _pruefe(ergebnis["anzahl"] > 0, "Marga hat Fundstellen")
    _pruefe(ergebnis["eigene_chats"] > 0, "eigener Chat erkannt")
    _pruefe(ergebnis["nur_erwaehnungen"] is False, "nicht nur Erwähnungen")
    _pruefe(len(ergebnis["eigene_chat_titel"]) == 1, "ein eigener Titel")
    _pruefe(all(t["im_eigenen_chat"] for t in ergebnis["treffer"]),
            "Fundstellen liegen im eigenen Chat")


# ── 3. Person ohne jede Fundstelle ─────────────────────────────────────────
def test_erwaehnung_ohne_fundstelle(dienst):
    ergebnis = dienst.erwaehnung_treffer("Norbert")
    _pruefe(ergebnis["anzahl"] == 0, "keine Fundstelle")
    _pruefe(ergebnis["treffer"] == [], "keine erfundenen Treffer")
    _pruefe(ergebnis["je_quelle"] == {}, "keine Quellen")
    _pruefe(ergebnis["nur_erwaehnungen"] is False, "nicht 'nur Erwähnungen'")
    _pruefe(bool(ergebnis["hinweis"]), "ehrlicher Hinweis vorhanden")
    text = erwaehnungs_text(ergebnis)
    _pruefe(bool(text.strip()), "Text ist nicht leer")
    _pruefe("nicht vor" in text, "Text sagt ehrlich: nicht vorhanden")
    _pruefe("[" not in text, "kein erfundener Fundstellen-Block")


# ── 4. Index fehlt / kein Pfad ─────────────────────────────────────────────
def test_erwaehnung_index_fehlt(tmp_path):
    dienst = ArchivSuche(pfad=os.path.join(str(tmp_path), "gibt-es-nicht.db"))
    ergebnis = dienst.erwaehnung_treffer("Erwin")   # darf nicht werfen
    _pruefe(ergebnis["fehler"] is not None, "Fehler ist gesetzt")
    _pruefe(ergebnis["anzahl"] == 0, "keine Fundstelle ohne Index")
    _pruefe(ergebnis["nur_erwaehnungen"] is False, "kein falsches Urteil")
    text = erwaehnungs_text(ergebnis)
    _pruefe(bool(text.strip()), "Text trotzdem benutzbar")
    _pruefe("nichts" in text or "nicht erreichbar" in text,
            "Text sagt ehrlich, dass nichts geht")
    # Auch ein leerer Name ist kein Wurf, sondern ein leeres Ergebnis.
    leer = dienst.erwaehnung_treffer("")
    _pruefe(leer["fehler"] is not None or leer["anzahl"] == 0,
            "leerer Name sauber abgefangen")


# ── 5. Jede Fundstelle trägt Quelle und Datum ──────────────────────────────
def test_erwaehnung_fundstellen_mit_quelle_und_datum(dienst):
    ergebnis = dienst.erwaehnung_treffer("Erwin", top_k=8)
    _pruefe(bool(ergebnis["treffer"]), "es gibt Fundstellen zum Prüfen")
    for t in ergebnis["treffer"]:
        _pruefe(bool(t["quelle"]), "Fundstelle hat eine Quelle")
        _pruefe(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", t["datum"] or "")),
                "Fundstelle hat ein Datum JJJJ-MM-TT")
        _pruefe(isinstance(t["im_eigenen_chat"], bool), "im_eigenen_chat ist bool")
        _pruefe(bool(t["conversation_id"]), "Fundstelle hat eine Gesprächskennung")
        _pruefe(isinstance(t["chunk_id"], int), "Fundstelle hat eine Chunk-Nummer")
        _pruefe("titel" in t and "text" in t, "Titel und Ausschnitt vorhanden")


# ── 6. je_quelle-Summe == anzahl ───────────────────────────────────────────
def test_erwaehnung_je_quelle_summe(dienst):
    ergebnis = dienst.erwaehnung_treffer("Erwin", top_k=8)
    _pruefe(isinstance(ergebnis["je_quelle"], dict), "je_quelle ist ein Dict")
    _pruefe(sum(ergebnis["je_quelle"].values()) == ergebnis["anzahl"],
            "Quellen-Summe == anzahl")
    _pruefe(ergebnis["je_quelle"].get("whatsapp", 0) == 2,
            "zwei Fundstellen aus der einen Quelle")
    _pruefe(ergebnis["je_quelle"].get("chatgpt", 0) == 1,
            "eine Fundstelle aus der anderen Quelle")
    quellen = list(ergebnis["je_quelle"].keys())
    _pruefe(quellen == sorted(quellen, key=lambda q: -ergebnis["je_quelle"][q]),
            "Quellen absteigend sortiert")
    # top_k begrenzt nur die Anzeige, nicht die Zählung.
    knapp = dienst.erwaehnung_treffer("Erwin", top_k=1)
    _pruefe(len(knapp["treffer"]) == 1, "top_k begrenzt die Fundstellenliste")
    _pruefe(knapp["anzahl"] == ergebnis["anzahl"], "anzahl bleibt die Gesamtzahl")


# ── 7. _erwaehnung_name — Beispiele und Gross-/Kleinschreibung ─────────────
def test_erwaehnung_name_beispiele():
    _pruefe(_erwaehnung_name("was habe ich mit Erwin gemacht?") == "Erwin",
            "Erwin wird erkannt")
    _pruefe(_erwaehnung_name("Was habe ich mit Erwin gemacht?") == "Erwin",
            "Grossschreibung am Satzanfang stoert nicht")
    _pruefe(_erwaehnung_name("was habe ich mit erwin gemacht?") == "erwin",
            "Kleinschreibung kommt so zurueck, wie gefragt")
    _pruefe(_erwaehnung_name("mit wem war ich in Hamburg?") is None,
            "Ortsangabe ist kein Name")
    _pruefe(_erwaehnung_name("was habe ich mit gemacht?") is None,
            "ohne Name kein Treffer")
    _pruefe(_erwaehnung_name("was war mit Marga") == "Marga", "Signal 'was war mit'")
    _pruefe(_erwaehnung_name("wen kenne ich denn noch") is None, "kein Name übrig")
    _pruefe(_erwaehnung_name("wie ist das Wetter?") is None, "kein Signal → None")
    _pruefe(_erwaehnung_name("") is None, "leere Frage → None")
    _pruefe(_erwaehnung_name("was habe ich mit Jo gemacht?") is None,
            "unter drei Zeichen zaehlt nicht")


# ── 8. False-Positive-Schutz: Bild-/Foto-Frage ─────────────────────────────
def test_archiv_tool_foto_frage_geht_nicht_in_die_erwaehnungssuche():
    fake = _FakeArchiv()
    ausgabe = _archiv_tool("zeig mir Fotos mit Erwin", service=fake)
    _pruefe(ausgabe == "", "Bild-Tor greift: kein Archiv-Text")
    _pruefe(fake.erwaehnung_aufrufe == [], "Erwähnungssuche lief NICHT")
    _pruefe(fake.hybrid_aufrufe == [], "Archiv-Suche lief NICHT")
    _pruefe(_erwaehnung_name("zeig mir fotos mit erwin") is None,
            "kein Signal in der Foto-Frage")


# ── 9. Kein Signal ─────────────────────────────────────────────────────────
def test_archiv_tool_ohne_signal_leer():
    fake = _FakeArchiv()
    _pruefe(_archiv_tool("wie ist das Wetter?", service=fake) == "", "kein Signal → \"\"")
    _pruefe(_archiv_tool("", service=fake) == "", "leere Frage → \"\"")
    _pruefe(fake.erwaehnung_aufrufe == [], "nichts aufgerufen")
    _pruefe(fake.hybrid_aufrufe == [], "nichts aufgerufen")


# ── 10. Bestehende Archiv-Signale unverändert ──────────────────────────────
def test_archiv_tool_bestehende_signale_unveraendert():
    fake = _FakeArchiv()
    ausgabe = _archiv_tool("was weißt du über Erwin aus dem Archiv", service=fake)
    _pruefe("Aus dem Archiv" in ausgabe, "harter Archiv-Weg unverändert")
    _pruefe(fake.erwaehnung_aufrufe == [], "kein Umleiten in die Erwähnungssuche")
    _pruefe(len(fake.hybrid_aufrufe) == 1, "Hybridsuche lief genau einmal")

    zweite = _FakeArchiv()
    ausgabe2 = _archiv_tool("zeig mir alte chats zu Erwin", service=zweite)
    _pruefe("Aus dem Archiv" in ausgabe2, "'alte chats' unverändert")
    _pruefe(zweite.hybrid_aufrufe == ["erwin"], "Stichwort wie vorher extrahiert")
    _pruefe(zweite.erwaehnung_aufrufe == [], "kein Umleiten in die Erwähnungssuche")


def test_archiv_tool_nutzt_neue_erwaehnungssuche(dienst):
    """Die neue Verdrahtung: Signal → Dienst → Notiz in der Form „\\n\\n[…]"."""
    fake = _FakeArchiv()
    fake.erwaehnung_treffer = dienst.erwaehnung_treffer   # echter Dienst
    ausgabe = _archiv_tool("was habe ich mit Erwin gemacht?", service=fake)
    _pruefe(ausgabe.startswith("\n\n["), "Notiz-Form bleibt erhalten")
    _pruefe("Erwähnungen in anderen Gesprächen" in ausgabe,
            "Klartextsatz steht in der Notiz")
    _pruefe("Wochenendplanung" in ausgabe, "Fundstelle mit Titel steht drin")
    _pruefe(fake.hybrid_aufrufe == [], "Hybridsuche wurde umgangen")


def test_archiv_tool_erwaehnung_dienst_fehlt_ehrlich(tmp_path):
    """Nicht erreichbarer Erwähnungsdienst → ehrlicher Hinweis, keine Erfindung."""
    kaputt = ArchivSuche(pfad=os.path.join(str(tmp_path), "nichts-da.db"))

    class _NurErwaehnung(_FakeArchiv):
        pass

    fake = _NurErwaehnung()
    fake.erwaehnung_treffer = kaputt.erwaehnung_treffer
    ausgabe = _archiv_tool("was habe ich mit Erwin gemacht?", service=fake)
    _pruefe("nicht erreichbar" in ausgabe, "ehrlicher Hinweis statt Null-Notiz")
    _pruefe("KEINE Archiv-Fundstellen" in ausgabe, "Erfinden ausdrücklich verboten")


# ── 11. Die Suche berührt den Index nicht ──────────────────────────────────
def _fingerabdruck(pfad: str):
    with open(pfad, "rb") as fh:
        inhalt = hashlib.sha256(fh.read()).hexdigest()
    return inhalt, os.stat(pfad).st_mtime_ns


def test_erwaehnungssuche_aendert_den_index_nicht(index_pfad):
    vorher = _fingerabdruck(index_pfad)
    dienst = ArchivSuche(pfad=index_pfad)
    ergebnis = dienst.erwaehnung_treffer("Erwin")
    erwaehnungs_text(ergebnis)
    dienst.erwaehnung_treffer("Marga")
    nachher = _fingerabdruck(index_pfad)
    _pruefe(vorher[0] == nachher[0], "Prüfsumme des Index unverändert")
    _pruefe(vorher[1] == nachher[1], "mtime des Index unverändert")
    _pruefe(not os.path.exists(index_pfad + "-journal"), "kein Journal angelegt")
    _pruefe(not os.path.exists(index_pfad + "-wal"), "kein WAL angelegt")


# ── 12. Kein Schreib- und kein Netzweg im neuen Code ───────────────────────
VERBOTEN = ("insert", "update", "delete", "requests", "httpx", "urlopen")


def test_erwaehnung_kein_schreib_oder_netzweg():
    quellen = {
        "erwaehnung_treffer": inspect.getsource(ArchivSuche.erwaehnung_treffer),
        "erwaehnungs_text": inspect.getsource(erwaehnungs_text),
        "_erwaehnung_name": inspect.getsource(_erwaehnung_name),
    }
    for name, quelle in quellen.items():
        klein = quelle.lower()
        for wort in VERBOTEN:
            _pruefe(wort not in klein, f"{name} enthält kein '{wort}'")
    _pruefe("mode=ro" in inspect.getsource(ArchivSuche._ro) or "mode=ro" in quellen["erwaehnung_treffer"],
            "der Lesemodus bleibt read-only")
