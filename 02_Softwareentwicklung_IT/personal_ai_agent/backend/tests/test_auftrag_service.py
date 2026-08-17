"""Tests fuer das Auftragsbuch.

Hintergrund: Sichtbar ist ueberall nur die achtstellige Kurzform der
Auftrags-ID - im Chat, in der Oberflaeche, in den Logzeilen. Hermes und der
Termux-Watcher melden genau damit zurueck. Die Schreiboperationen verglichen
aber exakt, sodass jede Rueckmeldung mit 404 ins Leere lief: der Auftrag blieb
fuer immer auf "laeuft", ohne dass irgendwo ein Fehler sichtbar wurde.

Diese Datei nagelt das fest.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.services.auftrag_service import (
    FEHLER,
    FERTIG,
    LAEUFT,
    OFFEN,
    AuftragService,
)


@pytest.fixture
def buch(tmp_path):
    """Ein Auftragsbuch auf einer Wegwerfdatei."""
    dienst = AuftragService()
    dienst._pfad = tmp_path / "auftraege.json"
    return dienst


def _schreibe_roh(dienst, eintraege):
    """Schreibt Eintraege mit selbst gewaehlten IDs ins Buch.

    Noetig, weil `anlegen()` UUIDs vergibt - fuer den Test auf mehrdeutige
    Praefixe brauchen wir aber zwei IDs mit gleichem Anfang.
    """
    dienst._pfad.write_text(
        json.dumps(eintraege, ensure_ascii=False), encoding="utf-8"
    )


def _grundgeruest(auftrag_id, status=OFFEN, **rest):
    eintrag = {
        "id": auftrag_id,
        "auftrag": "Testauftrag",
        "hinweis": None,
        "kategorie": "test",
        "komplexitaet": "klein",
        "status": status,
        "erstellt": "2026-08-17T10:00:00+00:00",
        "abgeholt": None,
        "beendet": None,
        "ergebnis": None,
        "status_meldungen": [],
        "rueckfragen": [],
    }
    eintrag.update(rest)
    return eintrag


# ---------------------------------------------------------------------------
# Der eigentliche Befund: Kurz-ID muss die Schreiboperationen treffen
# ---------------------------------------------------------------------------


def test_kurz_id_traegt_statusmeldung_ein(buch):
    angelegt = buch.anlegen("Baue Feature X")
    kurz = angelegt["id"][:8]

    ergebnis = buch.statusmeldung_hinzufuegen(kurz, "Arbeite dran")

    assert ergebnis is not None, "Kurz-ID muss die Statusmeldung treffen"
    assert len(ergebnis["status_meldungen"]) == 1
    assert "Arbeite dran" in ergebnis["status_meldungen"][0]


def test_kurz_id_traegt_ergebnis_ein(buch):
    angelegt = buch.anlegen("Baue Feature X")
    kurz = angelegt["id"][:8]

    ergebnis = buch.ergebnis_eintragen(kurz, "Fertig gebaut", erfolg=True)

    assert ergebnis is not None
    assert ergebnis["status"] == FERTIG
    assert ergebnis["ergebnis"] == "Fertig gebaut"
    assert ergebnis["beendet"] is not None


def test_kurz_id_meldet_fehlschlag(buch):
    angelegt = buch.anlegen("Baue Feature X")

    ergebnis = buch.ergebnis_eintragen(angelegt["id"][:8], "Kaputt", erfolg=False)

    assert ergebnis is not None
    assert ergebnis["status"] == FEHLER


def test_kurz_id_stellt_rueckfrage(buch):
    angelegt = buch.anlegen("Baue Feature X")

    ergebnis = buch.rueckfrage_stellen(angelegt["id"][:8], "Welche Farbe?")

    assert ergebnis is not None
    assert len(ergebnis["rueckfragen"]) == 1
    assert ergebnis["rueckfragen"][0]["frage"] == "Welche Farbe?"
    assert ergebnis["rueckfragen"][0]["antwort"] is None


def test_kurz_id_beantwortet_rueckfrage(buch):
    angelegt = buch.anlegen("Baue Feature X")
    kurz = angelegt["id"][:8]
    buch.rueckfrage_stellen(kurz, "Welche Farbe?")

    ergebnis = buch.rueckfrage_beantworten(kurz, 0, "Blau")

    assert ergebnis is not None
    assert ergebnis["rueckfragen"][0]["antwort"] == "Blau"
    assert buch.offene_rueckfragen(kurz) == []


def test_volle_id_funktioniert_weiterhin(buch):
    angelegt = buch.anlegen("Baue Feature X")

    ergebnis = buch.statusmeldung_hinzufuegen(angelegt["id"], "Mit voller ID")

    assert ergebnis is not None
    assert len(ergebnis["status_meldungen"]) == 1


def test_watcher_ablauf_von_anlage_bis_rueckmeldung(buch):
    """Der Weg, den der Termux-Watcher tatsaechlich geht.

    Er claimt ueber /naechster, kuerzt die ID auf acht Zeichen und meldet
    damit zurueck. Genau diese Kette war unterbrochen.
    """
    buch.anlegen("Baue Feature X")

    geclaimt = buch.naechster_offener()
    assert geclaimt is not None
    kurz_id = geclaimt["id"][:8]

    assert buch.statusmeldung_hinzufuegen(kurz_id, "uebernommen") is not None
    assert buch.ergebnis_eintragen(kurz_id, "erledigt") is not None
    assert buch.einzeln(kurz_id)["status"] == FERTIG


# ---------------------------------------------------------------------------
# Grenzfaelle der Suche
# ---------------------------------------------------------------------------


def test_mehrdeutige_kurz_id_trifft_nichts(buch):
    """Lieber keine Meldung als eine am falschen Auftrag."""
    _schreibe_roh(buch, [
        _grundgeruest("abc12345-1111-4111-8111-111111111111"),
        _grundgeruest("abc12345-2222-4222-8222-222222222222"),
    ])

    assert buch.einzeln("abc12345") is None
    assert buch.statusmeldung_hinzufuegen("abc12345", "Meldung") is None
    assert buch.ergebnis_eintragen("abc12345", "Ergebnis") is None

    # Kein Auftrag darf dabei veraendert worden sein.
    for eintrag in json.loads(buch._pfad.read_text(encoding="utf-8")):
        assert eintrag["status"] == OFFEN
        assert eintrag["status_meldungen"] == []


def test_eindeutiger_teil_einer_mehrdeutigen_gruppe_trifft(buch):
    _schreibe_roh(buch, [
        _grundgeruest("abc12345-1111-4111-8111-111111111111"),
        _grundgeruest("abc12345-2222-4222-8222-222222222222"),
    ])

    ergebnis = buch.statusmeldung_hinzufuegen("abc12345-1", "Meldung")

    assert ergebnis is not None
    assert ergebnis["id"].endswith("111111111111")


def test_unbekannte_id_gibt_none(buch):
    buch.anlegen("Baue Feature X")

    assert buch.einzeln("ffffffff") is None
    assert buch.statusmeldung_hinzufuegen("ffffffff", "Meldung") is None
    assert buch.ergebnis_eintragen("ffffffff", "Ergebnis") is None
    assert buch.rueckfrage_stellen("ffffffff", "Frage?") is None


def test_leere_id_trifft_nichts(buch):
    """Ein leerer String ist Praefix von allem - das darf nicht durchrutschen."""
    buch.anlegen("Baue Feature X")

    assert buch.einzeln("") is None
    assert buch.statusmeldung_hinzufuegen("", "Meldung") is None


def test_antwort_auf_nicht_vorhandene_rueckfrage(buch):
    angelegt = buch.anlegen("Baue Feature X")

    assert buch.rueckfrage_beantworten(angelegt["id"][:8], 0, "Blau") is None
    assert buch.rueckfrage_beantworten(angelegt["id"][:8], -1, "Blau") is None


# ---------------------------------------------------------------------------
# Abholen: darf nichts doppelt ausgeben
# ---------------------------------------------------------------------------


def test_naechster_offener_gibt_denselben_nicht_zweimal(buch):
    buch.anlegen("Einziger Auftrag")

    erster = buch.naechster_offener()
    zweiter = buch.naechster_offener()

    assert erster is not None
    assert erster["status"] == LAEUFT
    assert zweiter is None, "Ein laufender Auftrag darf nicht erneut ausgegeben werden"


def test_naechster_offener_nimmt_den_aeltesten(buch):
    _schreibe_roh(buch, [
        _grundgeruest("11111111-1111-4111-8111-111111111111",
                      erstellt="2026-08-17T12:00:00+00:00"),
        _grundgeruest("22222222-2222-4222-8222-222222222222",
                      erstellt="2026-08-17T09:00:00+00:00"),
    ])

    geholt = buch.naechster_offener()

    assert geholt["id"].startswith("22222222")


def test_aelterer_offener_auftrag_wird_gefunden_trotz_neuerem_fertigen(buch):
    """Befund B3: Der Watcher pruefte nur den neuesten Auftrag.

    Ist der neueste bereits fertig, darf ein aelterer offener trotzdem nicht
    unter den Tisch fallen.
    """
    _schreibe_roh(buch, [
        _grundgeruest("11111111-1111-4111-8111-111111111111",
                      status=FERTIG, erstellt="2026-08-17T12:00:00+00:00"),
        _grundgeruest("22222222-2222-4222-8222-222222222222",
                      status=OFFEN, erstellt="2026-08-17T09:00:00+00:00"),
    ])

    geholt = buch.naechster_offener()

    assert geholt is not None
    assert geholt["id"].startswith("22222222")


def test_alle_sortiert_neueste_zuerst(buch):
    _schreibe_roh(buch, [
        _grundgeruest("11111111-1111-4111-8111-111111111111",
                      erstellt="2026-08-17T09:00:00+00:00"),
        _grundgeruest("22222222-2222-4222-8222-222222222222",
                      erstellt="2026-08-17T12:00:00+00:00"),
    ])

    liste = buch.alle()

    assert liste[0]["id"].startswith("22222222")


# ---------------------------------------------------------------------------
# Verwaiste Auftraege
# ---------------------------------------------------------------------------


def test_verwaister_auftrag_wird_wieder_offen(buch, monkeypatch):
    monkeypatch.setattr(settings, "auftrag_timeout_minuten", 30)
    lange_her = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    _schreibe_roh(buch, [
        _grundgeruest("11111111-1111-4111-8111-111111111111",
                      status=LAEUFT, abgeholt=lange_her),
    ])

    geholt = buch.naechster_offener()

    assert geholt is not None, "Nach Ablauf der Frist muss der Auftrag zurueckkommen"
    assert geholt["id"].startswith("11111111")


def test_laufender_auftrag_bleibt_innerhalb_der_frist_gesperrt(buch, monkeypatch):
    monkeypatch.setattr(settings, "auftrag_timeout_minuten", 30)
    gerade_eben = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _schreibe_roh(buch, [
        _grundgeruest("11111111-1111-4111-8111-111111111111",
                      status=LAEUFT, abgeholt=gerade_eben),
    ])

    assert buch.naechster_offener() is None


def test_zeitstempel_ohne_zone_legt_das_buch_nicht_lahm(buch, monkeypatch):
    """Der Watcher laeuft alle 3 Sekunden hier durch.

    Ein einziger Eintrag mit zonenlosem Zeitstempel wuerde sonst einen
    TypeError werfen und die gesamte Auftragskette dauerhaft blockieren.
    """
    monkeypatch.setattr(settings, "auftrag_timeout_minuten", 30)
    naiv = (datetime.now(timezone.utc) - timedelta(minutes=45)).replace(
        tzinfo=None
    ).isoformat()
    _schreibe_roh(buch, [
        _grundgeruest("11111111-1111-4111-8111-111111111111",
                      status=LAEUFT, abgeholt=naiv),
    ])

    geholt = buch.naechster_offener()

    assert geholt is not None
    assert geholt["id"].startswith("11111111")


# ---------------------------------------------------------------------------
# Datei-Verhalten
# ---------------------------------------------------------------------------


def test_fehlende_datei_ist_kein_fehler(buch):
    assert buch.alle() == []
    assert buch.naechster_offener() is None
    assert buch.einzeln("abc12345") is None


def test_kaputte_datei_ist_kein_absturz(buch):
    buch._pfad.write_text("{kein gueltiges json", encoding="utf-8")

    assert buch.alle() == []
    assert buch.naechster_offener() is None
