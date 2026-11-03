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


def test_unterbrochene_nacht_wird_zusammengezaehlt():
    # Hermes S10: Zwei Abschnitte, die zum selben Tag gehören (23–03 und 04–07 Uhr), sind eine Nacht.
    # Vorher zählte nur der spätere (3 Std.); jetzt 4 + 3 = 7 Std. und die Lücke als Aufwachen.
    teil1 = {"quelle_kennung": "a", "beginn": "2026-11-02T23:00:00+01:00", "ende": "2026-11-03T03:00:00+01:00",
             "phasen": []}
    teil2 = {"quelle_kennung": "b", "beginn": "2026-11-03T04:00:00+01:00", "ende": "2026-11-03T07:00:00+01:00",
             "phasen": []}
    paare = aw._nacht_und_tag([teil1, teil2], [_stunde(stimmung=3)])
    assert len(paare) == 1
    nacht, _ = paare[0]
    assert nacht["schlaf_min"] == 420 and nacht["wach_phasen"] == 1


def test_doppelt_gemeldete_nacht_zaehlt_einmal():
    # Zwei Quellen (z. B. zwei Apps in Health Connect) melden dieselbe Nacht mit eigener Kennung.
    # Überlappende Abschnitte sind keine Unterbrechung: nur der längere zählt.
    uhr = {"quelle_kennung": "uhr", "beginn": "2026-11-02T23:00:00+01:00", "ende": "2026-11-03T07:00:00+01:00",
           "phasen": []}
    app = {"quelle_kennung": "app", "beginn": "2026-11-02T23:10:00+01:00", "ende": "2026-11-03T06:50:00+01:00",
           "phasen": []}
    for reihenfolge in ([uhr, app], [app, uhr]):
        nacht, _ = aw._nacht_und_tag(reihenfolge, [_stunde(stimmung=3)])[0]
        assert nacht["schlaf_min"] == 480 and nacht["wach_phasen"] == 0


def test_einzeltag_zeigt_doppelt_gemeldete_nacht_einmal():
    uhr = {"quelle_kennung": "uhr", "beginn": "2026-11-02T23:00:00+01:00", "ende": "2026-11-03T07:00:00+01:00",
           "phasen": []}
    app = {"quelle_kennung": "app", "beginn": "2026-11-02T23:10:00+01:00", "ende": "2026-11-03T06:50:00+01:00",
           "phasen": []}
    text = aw.protokoll_text([_stunde(stimmung=3)], [uhr, app], aw.schwaerzer(ERFUNDEN), einzeln=True)
    assert text.count("Nacht zum") == 1 and "23:00–07:00" in text


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


# ── S11: Wochentage und Gefühle nach Schlaf ────────────────────────────────

# 02.11. und 09.11.2026 sind Montage, 03.11. und 10.11. Dienstage, 07.11. ist ein Samstag.
WOCHE = [_stunde(tag="2026-11-02", stimmung=2), _stunde(tag="2026-11-02", von="18:00", bis="19:00", stimmung=4),
         _stunde(tag="2026-11-09", stimmung=2), _stunde(tag="2026-11-03", stimmung=4),
         _stunde(tag="2026-11-10", stimmung=5), _stunde(tag="2026-11-07", stimmung=1)]


def test_wochentage_profil():
    # Schnitt der Tagesschnitte; der Samstag kommt nur einmal vor und fehlt.
    assert aw.wochentag_text(WOCHE) == "Wochentage, Stimmung im Schnitt (Tage): Montag 2,5 (2) · Dienstag 4,5 (2)."


def test_wochentage_zu_wenig_schweigt():
    stunden = [_stunde(tag="2026-11-02", stimmung=2), _stunde(tag="2026-11-09", stimmung=3),
               _stunde(tag="2026-11-03", stimmung=4)]
    assert aw.wochentag_text(stunden) is None


def _vier_naechte(gefuehle_je_tag):
    naechte, stunden = [], []
    for (tag, vortag, ende), gefuehle in zip(
            [("2026-11-01", "2026-10-31", "04:00"), ("2026-11-02", "2026-11-01", "07:00"),
             ("2026-11-03", "2026-11-02", "04:00"), ("2026-11-04", "2026-11-03", "07:00")], gefuehle_je_tag):
        naechte.append(_nacht(tag, "23:00", ende, vortag))
        stunden.append(_stunde(tag=tag, stimmung=3, gefuehle=gefuehle))
    return naechte, stunden


def test_gefuehle_nach_kurzen_und_langen_naechten():
    naechte, stunden = _vier_naechte([["Ärger", "Angst", "Testperson vermisst"], ["Freude"],
                                      ["Ärger"], ["Freude", "Ärger"]])
    assert aw.gefuehle_nach_schlaf_text(naechte, stunden) == (
        "Gefühle nach kürzeren / längeren Nächten (Tage mit dem Gefühl, je 2 Tage): "
        "Freude 0 / 2 · Angst 1 / 0 · Ärger 2 / 1. Nur ein Zusammenhang, kein Beweis.")


def test_gefuehle_nach_schlaf_schweigt_ohne_gefuehle_oder_tage():
    naechte, stunden = _vier_naechte([[], [], [], ["eigenes Wort"]])
    assert aw.gefuehle_nach_schlaf_text(naechte, stunden) is None
    naechte, stunden = _vier_naechte([["Freude"]] * 3)
    assert aw.gefuehle_nach_schlaf_text(naechte, stunden) is None


def test_zeitraum_nennt_wochentage_und_gefuehle_nach_schlaf():
    naechte, stunden = _vier_naechte([["Ärger"], ["Freude"], ["Ärger"], ["Freude"]])
    assert "Gefühle nach kürzeren / längeren" in aw.protokoll_text(stunden, naechte, None, einzeln=False)
    assert "Wochentage" in aw.protokoll_text(WOCHE, [], None, einzeln=False)


# ── S12: Einschlafzeit und Stimmung ────────────────────────────────────────

def _nacht_ab(tag: str, vortag: str, einschlafen: str):
    """Nacht zum ``tag`` mit 7 Std. Dauer; vor Mitternacht beginnt sie am ``vortag``."""
    from datetime import datetime, timedelta
    std = int(einschlafen[:2])
    beginn = datetime.fromisoformat(f"{vortag if std >= 12 else tag}T{einschlafen}:00+01:00")
    return {"quelle_kennung": tag, "beginn": beginn.isoformat(),
            "ende": (beginn + timedelta(hours=7)).isoformat(), "phasen": []}


def _einschlaf_daten(anzahl=4):
    naechte, stunden = [], []
    for tag, vortag, einschlafen, stimmung, spannung in [
            ("2026-11-01", "2026-10-31", "22:30", 5, 10), ("2026-11-02", "2026-11-01", "01:00", 2, 70),
            ("2026-11-03", "2026-11-02", "23:00", 4, 20), ("2026-11-04", "2026-11-03", "00:30", 3, 50)][:anzahl]:
        naechte.append(_nacht_ab(tag, vortag, einschlafen))
        stunden.append(_stunde(tag=tag, von="14:00", bis="15:00", stimmung=stimmung, anspannung=spannung))
    return naechte, stunden


def test_einschlafzeit_und_stimmung():
    # Nach Mitternacht ist später als vor Mitternacht (00:30 nach 23:00).
    assert aw.einschlafzeit_text(*_einschlaf_daten()) == (
        "Einschlafzeit und Stimmung (4 Tage): Nach früherem Einschlafen (bis 23:00) lag die Stimmung "
        "im Schnitt bei 4,5, nach späterem bei 2,5. Anspannung im Schnitt 15 gegenüber 60. "
        "Nur ein Zusammenhang, kein Beweis.")


def test_einschlafzeit_zu_wenig_schweigt():
    assert aw.einschlafzeit_text(*_einschlaf_daten(3)) is None


def test_unterbrochene_nacht_behaelt_erste_einschlafzeit():
    teil1 = {"quelle_kennung": "a", "beginn": "2026-11-02T23:00:00+01:00", "ende": "2026-11-03T03:00:00+01:00",
             "phasen": []}
    teil2 = {"quelle_kennung": "b", "beginn": "2026-11-03T04:00:00+01:00", "ende": "2026-11-03T07:00:00+01:00",
             "phasen": []}
    nacht, _ = aw._nacht_und_tag([teil2, teil1], [_stunde(stimmung=3)])[0]
    assert nacht["einschlafen"] == "23:00" and nacht["aufwachen"] == "07:00"


def test_zeitraum_nennt_einschlafzeit():
    naechte, stunden = _einschlaf_daten()
    assert "Einschlafzeit und Stimmung" in aw.protokoll_text(stunden, naechte, None, einzeln=False)
