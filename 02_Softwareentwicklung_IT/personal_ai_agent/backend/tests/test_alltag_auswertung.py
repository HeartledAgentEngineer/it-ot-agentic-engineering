"""Alltagsprotokoll S8: Auswertung fürs Chat-Werkzeug (03.11.2026). Nur erfundene Einträge und Namen."""
from __future__ import annotations

from app.services import alltag_auswertung as aw


def _stunde(tag="2026-11-03", von="14:40", bis="15:40", **felder):
    return {"art": "stunde", "von": f"{tag}T{von}:00+01:00", "bis": f"{tag}T{bis}:00+01:00", **felder}


def _nacht(tag: str, beginn_vortag: str, ende: str, vortag: str):
    return {"quelle_kennung": tag, "beginn": f"{vortag}T{beginn_vortag}:00+01:00",
            "ende": f"{tag}T{ende}:00+01:00", "phasen": []}


ERFUNDEN = ["Testperson Erfunden"]


def test_zeile_mit_allen_feldern():
    e = _stunde(aktivitaet="Wäsche gemacht", stimmung=4, anspannung=30, gefuehle=["Ärger"])
    zeile = aw.stunden_zeile(e, aw.schwaerzer(ERFUNDEN))
    assert zeile == "03.11. 14:40–15:40 · Wäsche gemacht · Stimmung gut (4) · Anspannung 30 · Ärger"


def test_namen_in_der_taetigkeit_werden_geschwaerzt():
    e = _stunde(aktivitaet="Kaffee mit testperson und Erfunden", stimmung=5)
    zeile = aw.stunden_zeile(e, aw.schwaerzer(ERFUNDEN))
    assert "Kaffee mit [Name] und [Name]" in zeile
    assert "testperson" not in zeile.lower() and "erfunden" not in zeile.lower()


def test_ohne_namensliste_keine_freitexte():
    assert aw.schwaerzer(None) is None and aw.schwaerzer([]) is None
    e = _stunde(aktivitaet="Kaffee mit Testperson", stimmung=3, gefuehle=["Freude", "verliebt in Testperson"])
    zeile = aw.stunden_zeile(e, None)
    assert "Kaffee" not in zeile and "Testperson" not in zeile
    assert "Stimmung mittel (3)" in zeile and "Freude" in zeile


def test_eigene_gefuehlsworte_werden_geschwaerzt():
    e = _stunde(gefuehle=["Freude", "stolz auf Erfunden"])
    zeile = aw.stunden_zeile(e, aw.schwaerzer(ERFUNDEN))
    assert "Freude" in zeile and "stolz auf [Name]" in zeile


def test_originalworte_gehen_nie_raus():
    e = _stunde(originalworte="Ganz geheimer Satz", stimmung=2)
    assert "geheimer" not in aw.stunden_zeile(e, aw.schwaerzer(ERFUNDEN))
    text = aw.protokoll_text([e], [], aw.schwaerzer(ERFUNDEN), einzeln=True)
    assert "geheimer" not in text


def test_tageskennzahlen():
    stunden = [_stunde(von="09:00", bis="10:00", stimmung=4, anspannung=20, gefuehle=["Freude"]),
               _stunde(von="14:00", bis="15:00", stimmung=2, anspannung=60, gefuehle=["Ärger", "Freude"]),
               _stunde(tag="2026-11-02", stimmung=5)]
    k = aw.tag_kennzahlen(stunden)
    assert k["2026-11-03"]["stimmung"] == 3.0 and k["2026-11-03"]["anspannung"] == 40.0
    assert k["2026-11-03"]["eintraege"] == 2 and k["2026-11-03"]["gefuehle"][0] == ("Freude", 2)
    assert k["2026-11-02"]["anspannung"] is None


def test_mehrere_tage_als_tageszeilen():
    stunden = [_stunde(tag="2026-11-02", stimmung=4, anspannung=20),
               _stunde(tag="2026-11-03", stimmung=2, anspannung=70, aktivitaet="Geheim")]
    text = aw.protokoll_text(stunden, [], aw.schwaerzer(ERFUNDEN), einzeln=False)
    assert "02.11.2026: 1 Eintrag · Stimmung im Schnitt 4,0 · Anspannung 20" in text
    assert "03.11.2026: 1 Eintrag · Stimmung im Schnitt 2,0 · Anspannung 70" in text


def test_ein_tag_mit_der_nacht_davor():
    stunden = [_stunde(aktivitaet="Gelesen", stimmung=4)]
    naechte = [_nacht("2026-11-03", "23:10", "06:50", "2026-11-02")]
    text = aw.protokoll_text(stunden, naechte, aw.schwaerzer(ERFUNDEN), einzeln=True)
    assert "Nacht zum 03.11.2026: 23:10–06:50" in text and "Gelesen" in text


def test_ohne_eintraege_ehrlicher_hinweis():
    assert "Keine Einträge" in aw.protokoll_text([], [], None, einzeln=True)


def test_ohne_namensliste_hinweis_im_text():
    text = aw.protokoll_text([_stunde(aktivitaet="Gelesen", stimmung=4)], [], None, einzeln=True)
    assert "Gelesen" not in text and "ausgeblendet" in text


def test_verknuepfung_schlaf_und_stimmung():
    naechte, stunden = [], []
    # vier Tage: zwei kurze Nächte (5 Std.), zwei lange (8 Std.)
    for tag, vortag, ende, stimmung, spannung in [
            ("2026-11-01", "2026-10-31", "04:00", 2, 70), ("2026-11-02", "2026-11-01", "07:00", 4, 20),
            ("2026-11-03", "2026-11-02", "04:00", 3, 50), ("2026-11-04", "2026-11-03", "07:00", 5, 10)]:
        naechte.append(_nacht(tag, "23:00", ende, vortag))
        stunden.append(_stunde(tag=tag, stimmung=stimmung, anspannung=spannung))
    text = aw.verknuepfung_text(naechte, stunden)
    assert "4 Tage" in text
    assert "kürzeren Nächten (bis 5 Std.)" in text
    assert "2,5" in text and "4,5" in text
    assert "Anspannung im Schnitt 60 gegenüber 15" in text
    assert "kein Beweis" in text


def test_verknuepfung_braucht_vier_tage():
    naechte = [_nacht("2026-11-03", "23:00", "07:00", "2026-11-02")]
    stunden = [_stunde(stimmung=4)]
    assert "Zu wenige Tage" in aw.verknuepfung_text(naechte, stunden)


def test_kaputte_eintraege_brechen_nichts():
    kaputt = [_stunde(gefuehle="Ärger", stimmung="4", anspannung=300),
              {"art": "stunde", "von": "gestern"}, {"art": "stunde"}, "kein dict"]
    zeile = aw.stunden_zeile(kaputt[0], aw.schwaerzer(ERFUNDEN))
    assert zeile == "03.11. 14:40–15:40"
    assert aw.tag_kennzahlen(kaputt)["2026-11-03"]["stimmung"] is None
    assert "Keine Einträge" not in aw.protokoll_text(kaputt, [], None, einzeln=True)
    assert "Zu wenige Tage" in aw.protokoll_text(kaputt, [], None, einzeln=False)


# ── S10: Tageszeiten und Schlafqualität ────────────────────────────────────

def test_tageszeiten_profil():
    stunden = [_stunde(von="08:00", bis="09:00", stimmung=2, anspannung=60),
               _stunde(von="09:00", bis="10:00", stimmung=3, anspannung=50),
               _stunde(von="14:00", bis="15:00", stimmung=4, anspannung=30),
               _stunde(von="15:00", bis="16:00", stimmung=4, anspannung=20),
               _stunde(von="19:00", bis="20:00", stimmung=5),
               _stunde(von="20:00", bis="21:00", stimmung=5, anspannung=10)]
    text = aw.tageszeit_text(stunden)
    assert text == ("Tageszeiten, Stimmung im Schnitt (Einträge): morgens 2,5 (2) · nachmittags 4,0 (2) · "
                    "abends 5,0 (2). Anspannung: morgens 55 · nachmittags 25 · abends 10.")


def test_tageszeiten_brauchen_genug_eintraege_und_zwei_zeiten():
    assert aw.tageszeit_text([_stunde(von="08:00", bis="09:00", stimmung=3)] * 3) is None
    assert aw.tageszeit_text([_stunde(von="08:00", bis="09:00", stimmung=3)] * 6) is None   # nur morgens
    assert aw.tageszeit_text([{"art": "stunde", "von": "kaputt", "stimmung": 3}] * 6) is None


def _nacht_mit_phasen(tag: str, vortag: str, tief_min: int, aufgewacht: bool):
    p = lambda b, e, s: {"beginn": b, "ende": e, "stufe": s}  # noqa: E731
    tief_ende = f"{tag}T00:{tief_min:02d}:00+01:00" if tief_min < 60 else f"{tag}T01:{tief_min - 60:02d}:00+01:00"
    phasen = [p(f"{vortag}T23:00:00+01:00", f"{tag}T00:00:00+01:00", "leicht"),
              p(f"{tag}T00:00:00+01:00", tief_ende, "tief"),
              p(tief_ende, f"{tag}T03:00:00+01:00", "leicht")]
    if aufgewacht:
        phasen.append(p(f"{tag}T03:00:00+01:00", f"{tag}T03:10:00+01:00", "wach"))
    phasen.append(p(f"{tag}T03:10:00+01:00" if aufgewacht else f"{tag}T03:00:00+01:00",
                    f"{tag}T07:00:00+01:00", "leicht"))
    return {"quelle_kennung": tag, "beginn": f"{vortag}T23:00:00+01:00", "ende": f"{tag}T07:00:00+01:00",
            "phasen": phasen}


def test_schlafqualitaet_tiefschlaf_und_aufwachen():
    naechte, stunden = [], []
    for tag, vortag, tief, wach, stimmung in [
            ("2026-11-01", "2026-10-31", 30, True, 2), ("2026-11-02", "2026-11-01", 90, False, 4),
            ("2026-11-03", "2026-11-02", 40, True, 3), ("2026-11-04", "2026-11-03", 100, False, 5)]:
        naechte.append(_nacht_mit_phasen(tag, vortag, tief, wach))
        stunden.append(_stunde(tag=tag, stimmung=stimmung))
    text = aw.schlafqualitaet_text(naechte, stunden)
    assert ("Tiefschlaf und Stimmung (4 Tage): Nach den Nächten mit weniger Tiefschlaf (bis 40 Min.) "
            "lag die Stimmung im Schnitt bei 2,5, nach denen mit mehr bei 4,5.") in text
    assert "Ohne nächtliches Aufwachen (2 Nächte) Stimmung im Schnitt 4,5, mit Aufwachen (2 Nächte) 2,5." in text
    assert text.endswith("kein Beweis.")
    # Zeitraum-Text des Werkzeugs enthält beides
    gesamt = aw.protokoll_text(stunden, naechte, None, einzeln=False)
    assert "Tiefschlaf und Stimmung" in gesamt


def test_schlafqualitaet_ohne_phasen_schweigt():
    naechte = [_nacht(t, "23:00", "07:00", v) for t, v in
               [("2026-11-01", "2026-10-31"), ("2026-11-02", "2026-11-01"),
                ("2026-11-03", "2026-11-02"), ("2026-11-04", "2026-11-03")]]
    stunden = [_stunde(tag=n["quelle_kennung"], stimmung=3) for n in naechte]
    assert aw.schlafqualitaet_text(naechte, stunden) is None


def test_nickerchen_zaehlt_nicht_als_nacht():
    naechte = [{"quelle_kennung": "n", "beginn": "2026-11-03T13:00:00+01:00",
                "ende": "2026-11-03T13:40:00+01:00", "phasen": []}]
    assert "Zu wenige Tage" in aw.verknuepfung_text(naechte, [_stunde(stimmung=3)])
