"""S7: Kein „ewiges Warten" ohne Hermes — der Chat sagt, was wirklich ist.

Befund (Sebastian, 16.10.2026): Die Oberfläche behauptete „⏳ Hermes wurde
benachrichtigt – wartet auf Bearbeitung", obwohl weder der PC-Hermes noch der
lokale Hermes lief (Termux-Paket defekt, PC aus). Die Aufgabe landete in der
Warteliste, die niemand abarbeitete — der Nutzer wartete auf ein Ergebnis, das
nie kommt.

Prüfkriterium dieses Schritts: Ohne erreichbaren lokalen Hermes erscheint
innerhalb weniger Sekunden eine klare Meldung — nie ein ewiges „wartet".

Diese Tests fahren den ECHTEN Weg `route_auftrag` (nur Gateway und lokale
Verfügbarkeit sind gefakt) und prüfen:
  * die Antwort nennt den ehrlichen Grund und den sofortigen Ausweg,
  * sie behauptet keinen Lauf (kein „benachrichtigt", keine Übernahme),
  * die Statuszeile am Auftrag ist ehrlich (Gegenprobe: die alte Zeile),
  * Gegenprobe: mit lokalem Hermes bleibt alles beim Track-C-Verhalten.
"""
import os
import sys
import types
from unittest import mock

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import chat_routing  # noqa: E402


def _route(pc_antwort=None, lokal_da=False, pc_grund="Verbindung abgelehnt",
           ziel=""):
    """Fährt route_auftrag mit gefaktem Gateway und sammelt die Statuszeilen."""
    statuszeilen = []
    gebucht = {}

    def _anlegen(auftrag, begruendung, kategorie, komplexitaet):
        gebucht["auftrag"] = auftrag
        return {"id": "auftrag-s7-1"}

    def _status(eintrag_id, grund):
        statuszeilen.append({"id": eintrag_id, "grund": grund})

    gw = types.SimpleNamespace(sende_auftrag=lambda _a: pc_antwort,
                               letzter_fehler=pc_grund)

    kwargs = {"ziel": ziel} if ziel else {}
    with mock.patch.object(chat_routing, "hermes_gateway", gw), \
         mock.patch.object(chat_routing, "hermes_local_ist_verfuegbar",
                           return_value=lokal_da), \
         mock.patch.object(chat_routing, "anlegen_im_buch", side_effect=_anlegen), \
         mock.patch.object(chat_routing, "statusmeldung_bereit", side_effect=_status), \
         mock.patch.object(chat_routing, "verknuepfe_chat", return_value=None):
        ergebnis = chat_routing.route_auftrag(
            "Baue mir ein Skript",
            "Testbegründung", "feature", "mittel",
            finish_exchange=lambda *a, **k: None,
            get_or_create_conversation=lambda _: "conv-s7",
            starte_lokale_hermes=lambda *a, **k: {"id": "lokal-s7"},
            **kwargs,
        )
    return ergebnis, statuszeilen, gebucht


# ── Reine Funktion: der Klartext-Grund ────────────────────────────────────

def test_grund_nennt_beide_wege_wenn_keiner_erreichbar_ist():
    text = chat_routing.kein_helfer_text("Verbindung abgelehnt", False)
    assert "der lokale Hermes nicht einsatzbereit" in text
    assert "PC-Hermes ist nicht erreichbar (Verbindung abgelehnt)" in text


def test_grund_behauptet_den_pc_nicht_wenn_track_a_uebersprungen_wurde():
    """Umlenk-Ziel „handy": Track A lief nie — dann darf der PC nicht auftauchen."""
    text = chat_routing.kein_helfer_text("", False)
    assert "PC-Hermes" not in text
    assert text.endswith(".")


def test_grund_ist_klartext_ohne_zugangsdaten():
    text = chat_routing.kein_helfer_text("", True)
    assert "nicht gestartet" in text
    for verboten in ("api_key", "token", "Bearer", "sk-"):
        assert verboten not in text


# ── Der echte Weg: klare Meldung statt Dauer-Warten ───────────────────────

def test_ohne_hermes_kommt_sofort_eine_klare_meldung():
    ergebnis, statuszeilen, gebucht = _route()

    assert ergebnis["art"] == "buch"
    reply = ergebnis["reply"]
    assert "niemand daran" in reply            # ehrlicher Zustand
    assert "Grund:" in reply                   # warum
    assert "ohne Werkzeuge" in reply           # sofortiger Ausweg
    assert "benachrichtigt" not in reply       # alte Behauptung
    assert "wartet auf Bearbeitung" not in reply
    assert "wird übernommen" not in reply
    # Die Aufgabe wird weiterhin vorgemerkt (nichts geht verloren) ...
    assert "Baue mir ein Skript" in gebucht["auftrag"]
    # ... und die Statuszeile am Auftrag ist ehrlich, nicht die alte.
    assert len(statuszeilen) == 1
    assert statuszeilen[0]["id"] == "auftrag-s7-1"
    assert "PC-Hermes ist nicht erreichbar" in statuszeilen[0]["grund"]
    assert "wartet auf Bearbeitung" not in statuszeilen[0]["grund"]


def test_statuszeile_am_auftrag_ist_ehrlich():
    """Die Statuszeile selbst (statusmeldung_bereit) schreibt den Klartext."""
    geschrieben = []

    class _FakeService:
        @staticmethod
        def statusmeldung_hinzufuegen(eintrag_id, meldung):
            geschrieben.append((eintrag_id, meldung))

    fake_modul = types.SimpleNamespace(auftrag_service=_FakeService)
    with mock.patch.dict(sys.modules,
                         {"app.services.auftrag_service": fake_modul}):
        chat_routing.statusmeldung_bereit("id-1", "kein Hermes erreichbar.")

    assert geschrieben and geschrieben[0][0] == "id-1"
    text = geschrieben[0][1]
    assert "Liegt bereit" in text
    assert "kein Hermes erreichbar." in text
    assert "benachrichtigt" not in text
    assert "wartet auf Bearbeitung" not in text


def test_gegenprobe_mit_lokalem_hermes_bleibt_track_c():
    """Ist der lokale Hermes da, wird NICHT gebucht und NICHT gewarnt."""
    ergebnis, statuszeilen, gebucht = _route(lokal_da=True)

    assert ergebnis["art"] == "lokal"
    assert ergebnis["ziel"] == "handy"
    assert statuszeilen == []
    assert gebucht == {}


def test_alter_befund_ist_aus_dem_quelltext_verschwunden():
    """Quelltext-Wächter: die alte Statusbehauptung ist aus dem CODE verschwunden.

    Geprüft wird die ehemalige, wörtliche Statuszeile (mit Symbol und
    Fettdruck). Die reine Wortfolge steht weiterhin in einem Kommentar, der den
    Befund erklärt — Kommentare sind kein Verhalten.
    """
    quelle = open(chat_routing.__file__, "r", encoding="utf-8").read()
    assert "⏳ **Hermes wurde benachrichtigt**" not in quelle
    assert not hasattr(chat_routing, "statusmeldung_wartet")
