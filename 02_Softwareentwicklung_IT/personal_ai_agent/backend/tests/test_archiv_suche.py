"""Tests für die Wissensspeicher-Suche (Hybrid + Original nachlesen).

Diese Datei prüft den neuen Dienst ``app.services.archiv_suche`` und den
Router ``app.router.archiv_wissen``.

**Wichtig:** Hier wird NIE das echte Archiv geladen. Jeder Test baut sich im
``tmp_path`` ein winziges künstliches Archiv (drei bis vier Gespräche) und
einen Index daraus. Der Einbetter ist eine Attrappe — kein Netz, kein
Schlüssel, keine Kosten.

Was abgesichert wird (Sebastians Anforderungen, 25.09.2026):

  (a) Volltext findet einen Begriff
  (b) Vektorsuche findet eine sinngemäße Formulierung (Einbetter gemockt)
  (c) Treffer tragen Quelle + Datum + Kennung
  (d) Treffer sind zeitlich sortiert
  (e) „nichts gefunden" wird ehrlich gemeldet (Zeitraum wird genannt)
  (f) Statistik zählt korrekt
  (g) Der Wissensspeicher-Überblick nennt Quellen, Zeitraum, Anzahl
  (h) Ohne Vektor-Index fällt die Suche ehrlich auf Volltext zurück
  (i) Jeder Treffer trägt einen Zeiger (Datei + Chat-Kennung + Ordinal)
 (ii) Original-Nachlesen liefert den Originaltext unverändert + Kontext
(iii) Schwache/leere Treffer → sicher=false + Rückfrage, kein Behaupten
 (iv) Widersprüchliche Fundstellen → sicher=false
  (v) Eindeutiger Treffer → sicher=true
"""

from __future__ import annotations

import io
import json
import math
import os
import sqlite3
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.archiv_suche import (  # noqa: E402
    AEHNLICH_STARK,
    AEHNLICH_SCHWACH,
    WETTBEWERB_ABSTAND,
    ArchivSuche,
)
from scripts.archiv_index_bauen import QuelldateiFinder, baue_index  # noqa: E402

# ── Künstliche Testdaten ───────────────────────────────────────────────────
#
# Bewusst harmlose Beispielsätze — keine echten Archivinhalte.

GESPRAECHE = [
    {
        "conversation_id": "chat-umzug",
        "source": "chatgpt",
        "title": "Neue Wohnung Hamburg",
        "datum": "2023-03-01T09:00:00+00:00",
        "nachrichten": [
            ("user", "Ich suche eine neue Wohnung in Hamburg, die Mieten sind mir zu hoch."),
            ("assistant", "In Hamburg-Horn sind die Mieten deutlich günstiger."),
        ],
        "chunk": "Ich suche eine neue Wohnung in Hamburg, die Mieten sind mir zu hoch.",
    },
    {
        "conversation_id": "chat-easybank",
        "source": "gemini",
        "title": "EasyBank Überweisung",
        "datum": "2024-05-02T14:30:00+00:00",
        "nachrichten": [
            ("user", "Die EasyBank in Hamburg hat meine Überweisung abgelehnt."),
            ("assistant", "Prüfe zuerst das Limit deines Kontos bei der EasyBank."),
        ],
        "chunk": "Die EasyBank in Hamburg hat meine Überweisung abgelehnt.",
    },
    {
        "conversation_id": "chat-twincat",
        "source": "claude-code",
        "title": "TwinCAT Steuerung",
        "datum": "2025-06-07T07:15:00+00:00",
        "nachrichten": [
            ("user", "Mein TwinCAT Projekt für die SPS Steuerung baut nicht."),
            ("assistant", "Im TwinCAT Projekt fehlt die SPS Bibliothek."),
        ],
        "chunk": "Mein TwinCAT Projekt für die SPS Steuerung baut nicht.",
    },
]

# Zwei Gespräche zum selben Thema → konkurrierende Fundstellen.
GESPRAECHE_WIDERSPRUCH = [
    {
        "conversation_id": "streit-a",
        "source": "chatgpt",
        "title": "Umzug nach Hamburg",
        "datum": "2024-01-10T08:00:00+00:00",
        "nachrichten": [("user", "Ich bin nach Hamburg gezogen.")],
        "chunk": "Ich bin nach Hamburg gezogen, die Wohnung ist klein.",
    },
    {
        "conversation_id": "streit-b",
        "source": "gemini",
        "title": "Umzug nach München",
        "datum": "2024-02-20T08:00:00+00:00",
        "nachrichten": [("user", "Wir sind nach München gezogen.")],
        "chunk": "Wir sind nach München gezogen, die Wohnung ist gross.",
    },
]

GESPRAECH_SCHWACH = [
    {
        "conversation_id": "schwach-1",
        "source": "chatgpt",
        "title": "Ohne Schlagwörter",
        "datum": "2024-03-03T08:00:00+00:00",
        "nachrichten": [("user", "Ein ganz unspezifischer Satz.")],
        "chunk": "Ein ganz unspezifischer Satz ohne jedes Schlagwort.",
    },
]

# Attrappen-Themen: Wort → Achse. So tut der gemockte Einbetter so, als
# verstände er Bedeutung, ohne dass ein Modell befragt wird.
THEMEN = (
    ("umzug", "wohnung", "miete", "mieten", "hingezogen", "umgezogen", "gezogen", "horn"),
    ("easybank", "überweisung", "konto", "bank", "geld", "limit"),
    ("twincat", "sps", "steuerung", "bibliothek"),
)
ACHSEN = 6
ACHSONSTIGES = ACHSEN - 1


def vektor_aus_text(text: str):
    """Deterministische Attrappe: Schlagwort → Einheitsvektor einer Achse."""
    klein = (text or "").lower()
    for achse, woerter in enumerate(THEMEN):
        if any(w in klein for w in woerter):
            v = [0.0] * ACHSEN
            v[achse] = 1.0
            return v
    v = [0.0] * ACHSEN
    v[ACHSONSTIGES] = 1.0
    return v


def einbetter_attrappe(texte):
    """Einbetter für den Indexbau: (Vektoren, Token)."""
    return [vektor_aus_text(t) for t in texte], len(texte)


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
    naechste_nachricht = 0
    for nr, g in enumerate(gespraeche, start=1):
        anfang = naechste_nachricht
        for rolle, text in g["nachrichten"]:
            con.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)",
                (
                    naechste_nachricht, g["conversation_id"], g["source"], g["datum"],
                    rolle, text, g["title"], None,
                ),
            )
            naechste_nachricht += 1
        con.execute(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                nr, g["conversation_id"], g["source"], g["chunk"],
                json.dumps(list(range(anfang, naechste_nachricht))),
                g["datum"], g["datum"], g["title"], None, 0, 0,
            ),
        )
    con.commit()
    con.close()


def _index_bauen(tmp_path, gespraeche, mit_vektoren=True, name="archiv_index.db") -> str:
    quelle = os.path.join(str(tmp_path), f"quelle_{name}")
    ziel = os.path.join(str(tmp_path), name)
    _quell_db_bauen(quelle, gespraeche)
    bericht = baue_index(
        quelle_db=quelle,
        ausgabe=ziel,
        archiv_wurzel=None,
        einbetter=einbetter_attrappe if mit_vektoren else None,
        ausgabe_strom=io.StringIO(),
    )
    assert bericht["chunks"] == len(gespraeche)
    return ziel


@pytest.fixture
def archiv(tmp_path):
    """Index aus den drei Testgesprächen, mit Vektoren und Frage-Attrappe."""
    pfad = _index_bauen(tmp_path, GESPRAECHE)
    return ArchivSuche(pfad=pfad, frage_einbetter=vektor_aus_text)


# ── (a) Volltext ───────────────────────────────────────────────────────────
def test_volltext_findet_begriff(archiv):
    ergebnis = archiv.hybrid("EasyBank", modus="volltext")
    assert ergebnis["anzahl"] >= 1
    assert any(t["zeiger"]["chat_kennung"] == "chat-easybank" for t in ergebnis["treffer"])
    assert ergebnis["wege"]["volltext"] is True


def test_hybrid_vermerkt_beide_wege(archiv):
    """Ein Treffer, den beide Wege finden, nennt beide Wege."""
    ergebnis = archiv.hybrid("EasyBank", modus="hybrid")
    treffer = [t for t in ergebnis["treffer"] if t["zeiger"]["chat_kennung"] == "chat-easybank"]
    assert treffer, "EasyBank-Gespräch muss gefunden werden"
    assert "vektor" in treffer[0]["gefunden_ueber"]
    assert "volltext" in treffer[0]["gefunden_ueber"]


def test_ein_einzelnes_wort_von_mehreren_ist_nicht_belastbar(archiv):
    """FTS5 verknüpft mit OR — 1 von 4 Begriffen ist kein belastbarer Treffer.

    Ohne diese Zählung käme auf einem großen Bestand für jede sinnfreie
    Anfrage irgendein „Treffer" zurück, und der Agent hielte ihn für Beweis.
    """
    ergebnis = archiv.hybrid("EasyBank TwinCAT Wohnung Zebrastreifen", modus="volltext")
    assert ergebnis["anzahl"] >= 1
    for t in ergebnis["treffer"]:
        assert t["passende_begriffe"] is not None
        assert t["passende_begriffe"] <= 1
        assert t["stark"] is False
    assert ergebnis["sicher"] is False
    assert ergebnis["grund"] == "nur_schwache_aehnlichkeit"


def test_mehrere_passende_begriffe_sind_belastbar(archiv):
    """Drei Suchwörter im selben Chunk → belastbar (zeitliche Ordnung bleibt)."""
    ergebnis = archiv.hybrid("EasyBank Hamburg Überweisung", modus="volltext")
    treffer = [t for t in ergebnis["treffer"] if t["zeiger"]["chat_kennung"] == "chat-easybank"]
    assert treffer, "der Chunk mit drei passenden Begriffen muss dabei sein"
    assert treffer[0]["passende_begriffe"] == 3
    assert treffer[0]["stark"] is True
    assert ergebnis["sicher"] is True

    # Die Relevanz-Rangfolge liegt eine Ebene tiefer: in `volltext_suche`
    # steht der Treffer mit den meisten passenden Begriffen vorn. `hybrid`
    # sortiert danach bewusst nach Zeit (die Frage lautet „was war damals").
    direkt = archiv.volltext_suche("EasyBank Hamburg Überweisung")
    assert direkt[0]["zeiger"]["chat_kennung"] == "chat-easybank"


# ── (b) Sinngemäße Formulierung über Vektoren ──────────────────────────────
def test_semantik_findet_umschreibung(archiv):
    """'hingezogen' steht in keinem Chunk — nur die Bedeutung führt hin."""
    assert "hingezogen" not in " ".join(g["chunk"].lower() for g in GESPRAECHE)
    # Beweis, dass es wirklich der Vektorweg ist: der Wortlaut findet nichts.
    assert archiv.volltext_suche("hingezogen") == []

    ergebnis = archiv.hybrid("Wo bin ich damals hingezogen?", modus="vektor")
    assert ergebnis["anzahl"] >= 1
    treffer = ergebnis["treffer"][0]
    assert treffer["zeiger"]["chat_kennung"] == "chat-umzug"
    assert treffer["gefunden_ueber"] == "vektor"
    assert treffer["aehnlichkeit"] >= AEHNLICH_STARK
    assert ergebnis["wege"]["vektor"] is True


# ── (c) Quelle, Datum, Kennung am Treffer ──────────────────────────────────
def test_treffer_tragen_quelle_datum_kennung(archiv):
    ergebnis = archiv.hybrid("EasyBank", modus="volltext")
    treffer = ergebnis["treffer"][0]
    assert treffer["source"] == "gemini"
    assert treffer["datum"] == "2024-05-02"
    assert treffer["beginn"].startswith("2024-05-02")
    assert treffer["title"] == "EasyBank Überweisung"
    assert treffer["zeiger"]["chat_kennung"] == "chat-easybank"


# ── (i) Zeiger ins Original ────────────────────────────────────────────────
def test_jeder_treffer_traegt_zeiger(archiv):
    """Ein Treffer ohne Zeiger gälte als Fehler — hier zählt jeder Treffer."""
    ergebnis = archiv.hybrid("Hamburg Mieten EasyBank TwinCAT", modus="volltext")
    assert ergebnis["anzahl"] >= 1
    for t in ergebnis["treffer"]:
        zeiger = t["zeiger"]
        assert zeiger["quelldatei"], "Quelldatei im Archiv fehlt"
        assert zeiger["messages_jsonl"].endswith("messages.jsonl")
        assert zeiger["chat_kennung"], "Chat-Kennung fehlt"
        assert isinstance(zeiger["ordinal"], int) and zeiger["ordinal"] >= 0
        assert zeiger["ordinale"], "Nachrichten-Ordinale fehlen"
        assert zeiger["titel"] is not None
        assert zeiger["datum"]


def test_index_ist_eine_datei_mit_vektoren_drin(tmp_path):
    """Der Index ist EINE Datei — Text, Volltextindex und Vektoren zusammen."""
    pfad = _index_bauen(tmp_path, GESPRAECHE)
    assert os.path.isfile(pfad)
    con = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    try:
        tabellen = {z[0] for z in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"meta", "gespraeche", "nachrichten", "chunks", "vektoren"} <= tabellen
        assert con.execute("SELECT count(*) FROM vektoren").fetchone()[0] == len(GESPRAECHE)
        assert con.execute("SELECT count(*) FROM nachrichten").fetchone()[0] == sum(
            len(g["nachrichten"]) for g in GESPRAECHE
        )
    finally:
        con.close()
    # Keine Neben-Datei für Vektoren: die liegen im Index, nicht daneben.
    dateien = os.listdir(str(tmp_path))
    assert not [d for d in dateien if d.endswith(".f32")], "Vektoren gehören in den Index"
    assert not [d for d in dateien if d.endswith(".npy")]


def test_quelldatei_finder_findet_chatgpt_shard(tmp_path):
    """Der Zeiger findet die Originaldatei im Archiv, wenn sie da ist."""
    kennung = "068c253d-99a8-4f34-8ef4-f5413589bd0e"
    ordner = os.path.join(str(tmp_path), "raw", "chatgpt")
    os.makedirs(ordner, exist_ok=True)
    with open(os.path.join(ordner, "conversations-000.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": kennung, "title": "Beispiel"}], f)

    finder = QuelldateiFinder(str(tmp_path))
    assert finder.suchen("chatgpt", kennung) == "raw/chatgpt/conversations-000.json"
    # Unbekannte Quelle bleibt ehrlich leer statt zu raten.
    assert finder.suchen("claude-ai", "egal") is None
    assert finder.suchen("gemini", "egal") is None


def test_quelldatei_finder_findet_google_notiz(tmp_path):
    """Bei Google-Notizen ist die Kennung der Dateiname — der Zeiger wird genau."""
    import zipfile

    ordner = os.path.join(str(tmp_path), "raw")
    os.makedirs(ordner, exist_ok=True)
    zip_pfad = os.path.join(ordner, "takeout-20260812T203313Z-3-001.zip")
    with zipfile.ZipFile(zip_pfad, "w") as z:
        z.writestr("Takeout/Google Notizen/Einkaufsliste.html", "<html></html>")
        z.writestr("Takeout/Kalender/beispiel.ics", "BEGIN:VCALENDAR")

    finder = QuelldateiFinder(str(tmp_path))
    genau = finder.suchen("google-notizen", "Einkaufsliste")
    assert genau == (
        "raw/takeout-20260812T203313Z-3-001.zip::Takeout/Google Notizen/Einkaufsliste.html"
    )
    # Kalender: Kennung ist eine ICS-UID, deshalb greift die Bereichs-Ebene.
    grob = finder.suchen("google-kalender", "irgendeine-uid")
    assert grob is not None and grob.endswith("::Takeout/Kalender/beispiel.ics")


# ── (d) Zeitliche Sortierung ───────────────────────────────────────────────
def test_treffer_sind_zeitlich_sortiert(archiv):
    ergebnis = archiv.hybrid("Hamburg", modus="volltext")
    assert ergebnis["anzahl"] >= 2, "Hamburg kommt in zwei Gesprächen vor"
    daten = [t["beginn"] for t in ergebnis["treffer"]]
    assert daten == sorted(daten)
    assert daten[0].startswith("2023-03-01")
    assert ergebnis["sortierung"] == "zeit"


# ── (e) Nichts gefunden → ehrlich ──────────────────────────────────────────
def test_nichts_gefunden_wird_ehrlich_gemeldet(archiv):
    ergebnis = archiv.hybrid("Quantenverschränkung Kryptografie", modus="hybrid")
    assert ergebnis["anzahl"] == 0
    assert ergebnis["sicher"] is False
    assert ergebnis["grund"] == "keine_treffer"
    assert ergebnis["treffer"] == []
    # Die ehrliche Antwort nennt den durchsuchten Zeitraum und Umfang.
    assert ergebnis["zeitraum"]["von"].startswith("2023-03-01")
    assert ergebnis["zeitraum"]["bis"].startswith("2025-06-07")
    assert ergebnis["durchsucht"]["chunks"] == len(GESPRAECHE)
    assert ergebnis["durchsucht"]["gespraeche"] == len(GESPRAECHE)
    assert "nichts" in ergebnis["rueckfrage"].lower()


def test_ohne_index_keine_behauptung(tmp_path):
    """Ein gar nicht erreichbarer Index wird als solcher gemeldet."""
    dienst = ArchivSuche(pfad=os.path.join(str(tmp_path), "gibt-es-nicht.db"))
    assert dienst.is_available is False
    ergebnis = dienst.hybrid("irgendwas")
    assert ergebnis["sicher"] is False
    assert ergebnis["grund"] == "kein_index"
    assert ergebnis["treffer"] == []
    assert ergebnis["hinweis"]


# ── (f) Statistik ──────────────────────────────────────────────────────────
def test_statistik_zaehlt_korrekt(archiv):
    st = archiv.statistik()
    assert st["verfuegbar"] is True
    assert st["gesamt"]["gespraeche"] == len(GESPRAECHE)
    assert st["gesamt"]["nachrichten"] == sum(len(g["nachrichten"]) for g in GESPRAECHE)
    assert st["gesamt"]["chunks"] == len(GESPRAECHE)
    assert st["gesamt"]["vektoren"] == len(GESPRAECHE)

    quellen = {q["source"]: q for q in st["quellen"]}
    assert quellen["chatgpt"]["gespraeche"] == 1
    assert quellen["gemini"]["gespraeche"] == 1
    assert quellen["claude-code"]["gespraeche"] == 1
    assert quellen["chatgpt"]["nachrichten"] == 2

    assert st["zeitraum"]["von"].startswith("2023-03-01")
    assert st["zeitraum"]["bis"].startswith("2025-06-07")
    assert [j["jahr"] for j in st["je_jahr"]] == ["2023", "2024", "2025"]
    # Themen-Häufigkeit kommt aus den Titeln.
    themen = {t["thema"] for t in st["themen_haeufigkeit"]}
    assert "wohnung" in themen or "hamburg" in themen


# ── (g) Wissensspeicher-Überblick (Bewusstsein) ────────────────────────────
def test_ueberblick_enthaelt_quellen_zeitraum_anzahl(archiv):
    u = archiv.ueberblick()
    assert u["vorhanden"] is True
    assert u["gespraeche"] == len(GESPRAECHE)
    assert u["nachrichten"] == sum(len(g["nachrichten"]) for g in GESPRAECHE)
    assert u["zeitraum"]["von"].startswith("2023-03-01")
    assert u["zeitraum"]["bis"].startswith("2025-06-07")
    assert "chatgpt" in u["je_quelle"] and "gemini" in u["je_quelle"]
    assert u["themenbereiche"]

    # Der Prompt-Baustein sagt, was zu tun ist: erst hier, dann Web.
    assert "ZUERST hier suchen" in u["text"]
    assert "NICHT im Web" in u["text"]
    assert u["regeln"]["zuerst_archiv"]
    assert u["regeln"]["nie_erfinden"]
    # Schwellwerte stehen als Zahlen drin — nachprüfbar, kein Bauchgefühl.
    assert u["schwellwerte"]["stark_ab"] == AEHNLICH_STARK
    assert u["schwellwerte"]["schwach_ab"] == AEHNLICH_SCHWACH
    assert u["schwellwerte"]["wettbewerb_abstand"] == WETTBEWERB_ABSTAND

    # Bewusst KEINE Archivinhalte im Baustein.
    for g in GESPRAECHE:
        assert g["chunk"][:25] not in u["text"]


def test_ueberblick_ohne_index_sagt_dass_er_fehlt(tmp_path):
    dienst = ArchivSuche(pfad=os.path.join(str(tmp_path), "nichts.db"))
    u = dienst.ueberblick()
    assert u["vorhanden"] is False
    assert "nicht angebunden" in u["text"]
    assert "erfinde" in u["text"]


# ── (h) Ohne Vektoren: ehrlicher Rückfall auf Volltext ─────────────────────
def test_ohne_vektorindex_faellt_auf_volltext_zurueck(tmp_path):
    pfad = _index_bauen(tmp_path, GESPRAECHE, mit_vektoren=False, name="ohne_vektoren.db")
    dienst = ArchivSuche(pfad=pfad, frage_einbetter=vektor_aus_text)

    ergebnis = dienst.hybrid("EasyBank")
    assert ergebnis["wege"]["vektor"] is False
    assert ergebnis["wege"]["vektor_status"] == "kein_vektorindex"
    assert "hinweis" in ergebnis
    assert "Wortlaut" in ergebnis["hinweis"]
    # Der Volltext trägt weiter — die Suche ist schlechter, nicht leer.
    assert ergebnis["anzahl"] >= 1
    assert ergebnis["treffer"][0]["gefunden_ueber"] == "volltext"
    assert dienst.vektoren is None


# ── (ii) Original nachlesen ────────────────────────────────────────────────
def test_original_liefert_unveraenderten_text_mit_kontext(archiv):
    ergebnis = archiv.hybrid("EasyBank", modus="volltext")
    zeiger = ergebnis["treffer"][0]["zeiger"]

    original = archiv.original(zeiger["chat_kennung"], zeiger["ordinal"], kontext=1)
    assert original["gefunden"] is True
    assert original["unveraendert"] is True
    assert original["ordinal"] == zeiger["ordinal"]
    assert original["chat_kennung"] == zeiger["chat_kennung"]
    assert original["quelldatei"]

    # Der Originaltext kommt Zeichen für Zeichen so zurück, wie er abgelegt ist.
    echt = GESPRAECHE[1]["nachrichten"][0][1]
    assert original["fundstelle"]["text"] == echt
    assert original["fundstelle"]["ist_fundstelle"] is True

    # Kontextfenster: davor nichts, danach die Antwort.
    assert original["kontext_vor"] == []
    assert len(original["kontext_nach"]) == 1
    assert original["kontext_nach"][0]["role"] == "assistant"
    assert original["kontext_nach"][0]["ist_fundstelle"] is False
    assert original["titel"] == "EasyBank Überweisung"


def test_original_mit_kontext_davor(archiv):
    """Die zweite Nachricht eines Gesprächs hat die erste als Kontext davor."""
    original = archiv.original("chat-umzug", 1, kontext=1)
    assert original["gefunden"] is True
    assert [m["ordinal"] for m in original["kontext_vor"]] == [0]
    assert original["kontext_vor"][0]["role"] == "user"
    assert original["fundstelle"]["text"] == GESPRAECHE[0]["nachrichten"][1][1]


def test_original_unbekanntes_ordinal_ist_ehrlich(archiv):
    original = archiv.original("chat-umzug", 9999)
    assert original["gefunden"] is False
    assert original["grund"] == "ordinal_unbekannt"


# ── (iii) Unsicherheit → Rückfrage, kein behaupteter Inhalt ────────────────
def test_schwache_aehnlichkeit_gibt_rueckfrage_statt_antwort(tmp_path):
    """Ähnlichkeit zwischen schwach und stark → sicher=false plus Rückfrage."""
    v_chunk = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    cos = (AEHNLICH_SCHWACH + AEHNLICH_STARK) / 2  # mitten zwischen den Schwellen
    v_frage = [cos, math.sqrt(1 - cos * cos), 0.0, 0.0, 0.0, 0.0]

    quelle = os.path.join(str(tmp_path), "quelle_schwach.db")
    ziel = os.path.join(str(tmp_path), "schwach.db")
    _quell_db_bauen(quelle, GESPRAECH_SCHWACH)
    bericht = baue_index(
        quelle_db=quelle,
        ausgabe=ziel,
        archiv_wurzel=None,
        einbetter=lambda texte: ([v_chunk for _ in texte], len(texte)),
        ausgabe_strom=io.StringIO(),
    )
    assert bericht["vektoren"] == 1

    dienst = ArchivSuche(pfad=ziel, frage_einbetter=lambda _frage: v_frage)
    # Nur Füllwörter: der Volltext kann gar nicht treffen.
    ergebnis = dienst.hybrid("was war denn damals")

    assert ergebnis["anzahl"] == 1
    assert ergebnis["sicher"] is False
    assert ergebnis["grund"] == "nur_schwache_aehnlichkeit"
    assert ergebnis["beste_aehnlichkeit"] == pytest.approx(cos, abs=0.01)
    # Kein behaupteter Inhalt — sondern eine Rückfrage an Sebastian …
    assert ergebnis["rueckfrage"]
    assert "erinnern" in ergebnis["rueckfrage"]
    assert "antwort" not in ergebnis
    # … und die Kandidaten bleiben mit Zeiger sichtbar (nachlesbar).
    assert ergebnis["treffer"][0]["stark"] is False
    assert ergebnis["treffer"][0]["zeiger"]["chat_kennung"] == "schwach-1"


def test_leere_suche_gibt_rueckfrage_und_keine_antwort(archiv):
    ergebnis = archiv.hybrid("Quantenverschränkung Kryptografie")
    assert ergebnis["sicher"] is False
    assert ergebnis["rueckfrage"]
    assert "antwort" not in ergebnis


# ── (iv) Widersprüchliche Fundstellen ──────────────────────────────────────
def test_widerspruechliche_fundstellen_sind_unsicher(tmp_path):
    """Zwei gleich starke Fundstellen aus verschiedenen Gesprächen → Rückfrage."""
    pfad = _index_bauen(tmp_path, GESPRAECHE_WIDERSPRUCH, name="streit.db")
    dienst = ArchivSuche(pfad=pfad, frage_einbetter=vektor_aus_text)

    ergebnis = dienst.hybrid("Wo bin ich damals hingezogen?", modus="vektor")
    assert ergebnis["anzahl"] == 2
    assert ergebnis["sicher"] is False
    assert ergebnis["grund"] == "widerspruechliche_fundstellen"
    assert ergebnis["rueckfrage"]
    assert "antwort" not in ergebnis
    # Der Abstand der beiden Treffer liegt unter der Wettbewerbs-Schwelle.
    werte = sorted((t["aehnlichkeit"] for t in ergebnis["treffer"]), reverse=True)
    assert (werte[0] - werte[1]) < WETTBEWERB_ABSTAND
    assert {t["zeiger"]["chat_kennung"] for t in ergebnis["treffer"]} == {"streit-a", "streit-b"}


# ── (v) Eindeutiger Treffer → sicher ───────────────────────────────────────
def test_eindeutiger_treffer_ist_sicher(archiv):
    ergebnis = archiv.hybrid("Wo bin ich damals hingezogen?", modus="vektor")
    assert ergebnis["sicher"] is True
    assert ergebnis["grund"] == "eindeutig"
    assert ergebnis["rueckfrage"] is None
    assert ergebnis["kandidaten"] >= 1


def test_stichwort_treffer_ist_sicher(archiv):
    ergebnis = archiv.hybrid("EasyBank", modus="volltext")
    assert ergebnis["sicher"] is True
    assert ergebnis["grund"] == "eindeutig"


# ── Chronik ────────────────────────────────────────────────────────────────
def test_chronik_altersrichtung(archiv):
    alt = archiv.chronik(richtung="alt", limit=3)
    assert alt["verfuegbar"] is True
    assert [g["datum"] for g in alt["gespraeche"]] == ["2023-03-01", "2024-05-02", "2025-06-07"]
    assert alt["gespraeche"][0]["source"] == "chatgpt"
    assert alt["gespraeche"][0]["thema"] == "Neue Wohnung Hamburg"
    assert alt["gespraeche"][0]["zeiger"]["chat_kennung"] == "chat-umzug"
    assert alt["zeitraum"]["von"].startswith("2023-03-01")

    neu = archiv.chronik(richtung="neu", limit=2)
    assert [g["datum"] for g in neu["gespraeche"]] == ["2025-06-07", "2024-05-02"]


# ── Router ─────────────────────────────────────────────────────────────────
@pytest.fixture
def client(archiv, monkeypatch):
    """Testclient mit dem Archiv-Router und dem winzigen Index."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.router import archiv_wissen

    monkeypatch.setattr(archiv_wissen, "archiv_suche", archiv)
    app = FastAPI()
    app.include_router(archiv_wissen.router)
    return TestClient(app)


def test_router_statistik_und_chronik(client):
    antwort = client.get("/api/archiv/wissen/statistik")
    assert antwort.status_code == 200
    assert antwort.json()["gesamt"]["gespraeche"] == len(GESPRAECHE)

    antwort = client.get("/api/archiv/wissen/chronik", params={"richtung": "alt", "limit": 2})
    assert antwort.status_code == 200
    assert [g["datum"] for g in antwort.json()["gespraeche"]] == ["2023-03-01", "2024-05-02"]


def test_router_frage_original_ueberblick(client):
    antwort = client.get("/api/archiv/wissen/frage", params={"q": "EasyBank"})
    assert antwort.status_code == 200
    ergebnis = antwort.json()
    assert ergebnis["sicher"] is True
    assert ergebnis["sortierung"] == "zeit"
    zeiger = ergebnis["treffer"][0]["zeiger"]
    assert zeiger["chat_kennung"] and isinstance(zeiger["ordinal"], int)

    # Stufe 2 über denselben Zeiger: Original nachlesen.
    antwort = client.get(
        "/api/archiv/wissen/original",
        params={"chat_kennung": zeiger["chat_kennung"], "ordinal": zeiger["ordinal"]},
    )
    assert antwort.status_code == 200
    original = antwort.json()
    assert original["gefunden"] is True
    assert original["fundstelle"]["text"] == GESPRAECHE[1]["nachrichten"][0][1]

    antwort = client.get("/api/archiv/wissen/ueberblick")
    assert antwort.status_code == 200
    assert antwort.json()["vorhanden"] is True


def test_router_ohne_index_ist_ehrlich(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.router import archiv_wissen

    leer = ArchivSuche(pfad=os.path.join(str(tmp_path), "leer.db"))
    monkeypatch.setattr(archiv_wissen, "archiv_suche", leer)
    app = FastAPI()
    app.include_router(archiv_wissen.router)
    client = TestClient(app)

    antwort = client.get("/api/archiv/wissen/frage", params={"q": "irgendwas"})
    assert antwort.status_code == 200
    ergebnis = antwort.json()
    assert ergebnis["sicher"] is False
    assert ergebnis["grund"] == "kein_index"
    assert ergebnis["treffer"] == []
    assert ergebnis["rueckfrage"]
