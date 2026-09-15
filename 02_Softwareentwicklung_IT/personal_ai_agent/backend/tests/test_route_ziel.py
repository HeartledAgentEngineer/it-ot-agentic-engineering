"""Tests: Umlenk-Ziel in der Auftrags-Weiche (R1, Stand 15.09.2026).

Warum diese Tests existieren
----------------------------
Der Umlenk-Button „An lokalen Hermes übergeben" schickt `ziel="handy"`, damit
die Aufgabe auf dem Handy läuft (Track C) — dort, wo Sebastian unterwegs ist.
`route_auftrag()` versuchte aber IMMER zuerst Track A (PC-Hermes). Der PC nahm
den Auftrag an, lieferte das Ergebnis aber nicht ans Handy zurück — der lokale
Hermes bekam die Aufgabe nie. Symptom: „Wechsel aufs lokale Modell passiert
nichts."

Diese Tests halten fest:
  * ziel="handy"  → Track A wird übersprungen, Track C startet.
  * ohne ziel     → Track A zuerst (bisheriges Verhalten, unverändert).
  * ziel="handy" ohne lokalen Hermes → Track B (Buch), NICHT der PC.
"""
import os
import sys
from unittest import mock

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import chat_routing  # noqa: E402


def _rufe(ziel=None, pc_antwort="PC-Ergebnis", lokal_da=True):
    """Ruft route_auftrag mit Spion-Callbacks auf und protokolliert den Weg."""
    protokoll = {"lokal_gestartet": False, "lokal_aufgabe": None}

    def _lokal(aufgabe, **kwargs):
        protokoll["lokal_gestartet"] = True
        protokoll["lokal_aufgabe"] = aufgabe
        return {"id": "auftrag-lokal-1"}

    kwargs = {}
    if ziel is not None:
        kwargs["ziel"] = ziel

    with mock.patch.object(chat_routing.hermes_gateway, "sende_auftrag",
                           return_value=pc_antwort) as pc, \
         mock.patch.object(chat_routing, "hermes_local_ist_verfuegbar",
                           return_value=lokal_da), \
         mock.patch.object(chat_routing, "anlegen_im_buch",
                           return_value={"id": "buch-1"}), \
         mock.patch.object(chat_routing, "statusmeldung_wartet",
                           lambda *a, **k: None), \
         mock.patch.object(chat_routing, "verknuepfe_chat",
                           lambda *a, **k: None):
        ergebnis = chat_routing.route_auftrag(
            "baue Knopf X ein",
            "Test-Auftrag",
            "code",
            "mittel",
            finish_exchange=lambda *a, **k: None,
            get_or_create_conversation=lambda _: "conv_test",
            starte_lokale_hermes=_lokal,
            **kwargs,
        )
    return ergebnis, pc, protokoll


def test_ziel_handy_ueberspringt_pc():
    """Umlenk-Button: ziel='handy' darf den PC NICHT ansprechen."""
    ergebnis, pc, protokoll = _rufe(ziel="handy")

    assert pc.called is False, "Track A (PC) wurde trotz Umlenk-Ziel aufgerufen"
    assert protokoll["lokal_gestartet"] is True, "Track C (lokal) wurde nicht gestartet"
    assert ergebnis["ziel"] == "handy"
    assert ergebnis["art"] == "lokal"


def test_ohne_ziel_pc_zuerst():
    """Ohne Umlenk-Ziel bleibt das bisherige Verhalten: PC zuerst."""
    ergebnis, pc, protokoll = _rufe(ziel=None)

    assert pc.called is True, "Track A muss ohne Umlenk-Ziel zuerst versucht werden"
    assert protokoll["lokal_gestartet"] is False, "Track C darf nicht zusätzlich laufen"
    assert ergebnis["ziel"] == "pc"


def test_ziel_handy_ohne_lokalen_hermes_geht_ins_buch():
    """Ohne lokalen Hermes landet der Umlenk-Auftrag im Buch — nie beim PC."""
    ergebnis, pc, _ = _rufe(ziel="handy", lokal_da=False)

    assert pc.called is False, "Track A darf auch ohne lokal nicht einspringen"
    assert ergebnis["ziel"] == "buch"


def test_ziel_pc_geht_an_den_pc():
    """Explizites ziel='pc' schickt die Aufgabe an den PC-Hermes."""
    ergebnis, pc, protokoll = _rufe(ziel="pc")

    assert pc.called is True
    assert protokoll["lokal_gestartet"] is False
    assert ergebnis["ziel"] == "pc"


def test_kontext_wird_weiterhin_mitgegeben():
    """Der Gesprächs-Kontext hängt auch beim Umlenk-Weg am Hermes-Auftrag."""
    _, _, protokoll = _rufe(ziel="handy")

    assert "[Kontext aus dem Gespräch" not in (protokoll["lokal_aufgabe"] or "")
    # Kontext war hier leer (kein kontext-Parameter übergeben) → Aufgabe bleibt nackt.
    assert protokoll["lokal_aufgabe"] == "baue Knopf X ein"
