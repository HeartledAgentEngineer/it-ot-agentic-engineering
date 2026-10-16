"""Quiz-Fortschritt, "bestätigt"-Regel und Referenz-Nachbearbeitung.

Sichert die Fixes vom 15.09.2026 gegen den Befund Sebastian:

* "Beim Speichern geht er die Personen NOCHMAL von vorne durch; alle müssen
  erneut bestätigen, auch die schon zugeordneten." -> dieselbe Gesichts-Region
  für dieselbe Person darf nicht erneut eingelernt/gefragt werden
  (`beantworte_runde`, `ergaenze_person_mit_bbox`, `analysiere_bild`).
* "Im Katalog auf die Referenz klicken -> in der Referenz anpassen -> Rahmen
  verschieben -> speichern." -> deterministischer Roundtrip über die STABILE
  ref_id: Person bleibt dieselbe, andere Referenzen bleiben erhalten.
* Löschen einer Referenz entfernt auch ihre Vektoren (keine Geister-Vektoren).

Alle Tests arbeiten auf tmp_path: der ECHTE Katalog und der ECHTE Quiz-Fortschritt
(Sebastians Personendaten) werden nie angefasst.
"""

import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import pytest  # noqa: E402
from pathlib import Path  # noqa: E402

from app.services import chat_verlauf, face_service, gesicht_quiz, gesichter_service  # noqa: E402

# Kantenlängen des Testbildes: 100 breit x 200 hoch.
IW, IH = 100, 200
# Ein Gesicht links oben, normalisiert [0.10, 0.10, 0.30, 0.20].
BBOX = [10.0, 20.0, 30.0, 40.0]
REGION = "0.10,0.10,0.30,0.20"
BBOX2 = [60.0, 120.0, 20.0, 40.0]          # zweites Gesicht (andere Region)


@pytest.fixture(autouse=True)
def _isoliert(tmp_path, monkeypatch):
    """Eigener Katalog + eigener Fortschritt je Test; Chat-Verlauf stumm."""
    monkeypatch.setattr(
        gesichter_service, "KATALOG_DATEI",
        Path(tmp_path) / "gesichter_katalog.json",
    )
    monkeypatch.setattr(
        gesicht_quiz, "_FORTSCHRITT_OVERRIDE",
        str(Path(tmp_path) / "quiz_fortschritt.json"),
    )
    # Kein Schreiben in Sebastians echten Chat-Verlauf.
    monkeypatch.setattr(chat_verlauf, "verlauf_nachricht_anhaengen",
                        lambda *a, **k: None)
    yield


@pytest.fixture()
def bild(tmp_path):
    """Echtes JPEG (100x200) — _bbox_zu_norm braucht ein lesbares Bild."""
    from PIL import Image
    p = tmp_path / "lieblingsbild.jpg"
    Image.new("RGB", (IW, IH), (30, 30, 30)).save(p, "JPEG")
    return str(p)


@pytest.fixture()
def erkennung(monkeypatch):
    """Face-Engine-Ersatz: ZWEI Gesichter mit je eigenem Vektor.

    Wie in echt: `_gesicht_zu_bbox` waehlt anhand der (ggf. korrigierten) bbox
    das passende Gesicht — BBOX -> Vektor A, BBOX2 -> Vektor B.
    """
    monkeypatch.setattr(face_service, "verfuegbar", lambda: True)
    monkeypatch.setattr(
        gesicht_quiz, "_gesichter_robust",
        lambda pfad: [
            {"bbox": list(BBOX), "score": 0.9, "embedding": [1.0, 0.0, 0.0]},
            {"bbox": list(BBOX2), "score": 0.8, "embedding": [0.0, 1.0, 0.0]},
        ],
    )
    # Ausschnitt-Einbettung: liefert wie in echt fuer VERSCHIEDENE Rahmen
    # verschiedene Vektoren. Seit A3 (16.10.) ist dieser Weg der primaere, sobald
    # ein Rahmen mitgesendet wird — vorher gewann immer der Detektor-Vektor.
    def _emb_fuer_bbox(pfad, bbox):
        return [0.9, 0.1, 0.0] if list(bbox) == list(BBOX) else [0.1, 0.9, 0.0]

    monkeypatch.setattr(face_service, "embedding_fuer_bbox", _emb_fuer_bbox)
    yield


def _refs(name):
    p = gesichter_service.person_finden(name)
    return gesichter_service._refs_of(p) if p else []


# ---------------------------------------------------------------------------
# (1) Fortschritts-Markierung "bestätigt" — deterministisch je Region
# ---------------------------------------------------------------------------

def test_beantworte_runde_merkt_region_als_bestaetigt(bild, erkennung):
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=BBOX)
    assert r["ok"] is True
    assert r["bereits_bestaetigt"] == ["Anna"]

    regionen = gesicht_quiz._bestaetigte_regionen(bild)
    assert {"person": "Anna", "region": REGION} == {
        "person": regionen[0]["person"], "region": regionen[0]["region"]}
    assert gesicht_quiz._ist_bestaetigt(bild, "anna", REGION) is True
    # Referenz traegt Bild + normalisierte bbox (Anzeige-Anker im Frontend).
    refs = _refs("Anna")
    assert len(refs) == 1
    assert refs[0]["bild_pfad"] == bild
    assert refs[0]["bbox_norm"] == [0.1, 0.1, 0.3, 0.2]
    # Bild ist persistent "gesehen" -> erscheint nicht erneut als Frage.
    assert bild in gesicht_quiz._fortschritt_laden()


def test_zweite_antwort_derselben_region_wird_uebersprungen(bild, erkennung):
    """DER KERNBUG: Speichern darf bereits Bestätigtes nicht erneut einlernen."""
    erst = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=BBOX)
    assert erst["referenzen"] == 1

    nochmal = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=BBOX)
    assert nochmal["ok"] is True
    assert nochmal["uebersprungen"] is True
    assert nochmal["bereits_bestaetigt"] is True
    assert nochmal["hinzugefuegt"] is False
    assert nochmal["referenzen"] == 1          # KEIN zweiter Vektor
    assert len(_refs("Anna")) == 1             # keine Dublette


def test_andere_region_gleicher_person_lernt_weiter(bild, erkennung):
    """Ein ZWEITES Gesicht derselben Person ist kein Duplikat."""
    gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=BBOX)
    zweites = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=BBOX2)
    assert zweites.get("uebersprungen") is not True
    assert len(_refs("Anna")) == 2


def test_gleiche_region_andere_person_wird_nicht_uebersprungen(bild, erkennung):
    """Die Regel gilt je (Region, Person) — nicht je Region allein."""
    gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=BBOX)
    r = gesicht_quiz.beantworte_runde(bild, "Ben", False, bbox=BBOX)
    assert r["ok"] is True
    assert r.get("uebersprungen") is not True
    assert len(_refs("Ben")) == 1


def test_ergaenze_person_mit_bbox_ist_idempotent(bild, erkennung):
    erst = gesicht_quiz.ergaenze_person_mit_bbox(bild, "Anna", False, bbox=BBOX)
    assert erst["ok"] is True and erst["referenzen"] == 1
    nochmal = gesicht_quiz.ergaenze_person_mit_bbox(bild, "Anna", False, bbox=BBOX)
    assert nochmal["uebersprungen"] is True
    assert len(_refs("Anna")) == 1


def test_alte_bestaetigung_ohne_region_zaehlt_weiter(bild, monkeypatch):
    """Abwärtskompatibilität: alte Einträge sind reine Namens-Strings."""
    with open(gesicht_quiz._fortschritt_pfad(), "w", encoding="utf-8") as f:
        json.dump({"gesehen": [], "bestaetigt": {bild: ["Anna"]}}, f)
    assert gesicht_quiz._bestaetigte_gesichter(bild) == ["Anna"]
    assert gesicht_quiz._ist_bestaetigt(bild, "ANNA") is True
    assert gesicht_quiz._region_schluessel(None) == ""


def test_analysiere_bild_flagged_bestaetigte_gesichter(bild, erkennung, monkeypatch):
    """Das Frontend braucht je Gesicht ein 'bestaetigt'-Flag, um zu überspringen."""
    monkeypatch.setattr(face_service, "verfuegbar", lambda: True)
    monkeypatch.setattr(face_service, "embeddings_fuer_pfad",
                        lambda pfad: [{"bbox": list(BBOX), "score": 0.9,
                                       "embedding": [1.0, 0.0, 0.0]}])
    monkeypatch.setattr(face_service, "erkenne_personen", lambda emb: [])

    vorher = gesicht_quiz.analysiere_bild(bild)
    assert vorher["engine_verfuegbar"] is True
    assert vorher["gesichter"][0]["region"] == REGION
    assert vorher["gesichter"][0]["bestaetigt"] == []

    gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=BBOX)

    nachher = gesicht_quiz.analysiere_bild(bild)
    assert nachher["gesichter"][0]["bestaetigt"] == ["Anna"]
    assert nachher["bestaetigte_personen"] == ["Anna"]
    assert nachher["bestaetigte_regionen"][0]["region"] == REGION


# ---------------------------------------------------------------------------
# (2) "keine Person vorhanden"-Pfad
# ---------------------------------------------------------------------------

def test_keine_person_legt_keine_person_an_und_markiert_gesehen(bild):
    r = gesicht_quiz.markiere_uebersprungen(bild)
    assert r["ok"] is True and r["uebersprungen"] is True
    assert gesichter_service.liste_personen() == []
    assert bild in gesicht_quiz._fortschritt_laden()
    assert gesicht_quiz._bestaetigte_gesichter(bild) == []


def test_keine_person_bei_fehlendem_bild(tmp_path):
    r = gesicht_quiz.markiere_uebersprungen(str(tmp_path / "weg.jpg"))
    assert r["ok"] is False
    assert "nicht gefunden" in r["fehler"]


def test_antwort_ohne_gesicht_und_ohne_bbox_veraendert_nichts(bild, monkeypatch):
    monkeypatch.setattr(gesicht_quiz, "_gesichter_robust", lambda pfad: [])
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False)
    assert r["ok"] is False
    assert "kein Gesicht" in r["fehler"]
    assert gesichter_service.liste_personen() == []
    # NICHT als gesehen markiert -> die Frage bleibt offen (kein stiller Verlust).
    assert bild not in gesicht_quiz._fortschritt_laden()


# ---------------------------------------------------------------------------
# (3) Referenz-Nachbearbeitung (Roundtrip über die stabile ref_id)
# ---------------------------------------------------------------------------

def _person_mit_zwei_referenzen(bild):
    gesichter_service.person_speichern(
        name="Anna",
        referenzen=[
            {"embedding": [1.0, 0.0, 0.0], "jahr": 2015, "bild_pfad": bild,
             "bbox": list(BBOX), "bbox_norm": [0.1, 0.1, 0.3, 0.2]},
            {"embedding": [0.0, 1.0, 0.0], "jahr": 2020, "bild_pfad": bild,
             "bbox": list(BBOX2), "bbox_norm": [0.6, 0.6, 0.2, 0.2]},
        ],
    )
    return gesicht_quiz._bestaetigte_regionen(bild)


def test_referenzen_zu_bild_beschreibt_bestaetigte_regionen(bild):
    _person_mit_zwei_referenzen(bild)
    eintraege = gesichter_service.referenzen_zu_bild(bild)
    assert len(eintraege) == 2
    assert {e["person"] for e in eintraege} == {"Anna"}
    assert all(e["ref_id"] for e in eintraege)
    assert gesichter_service.referenzen_zu_bild("/anderes/bild.jpg") == []


def test_bbox_roundtrip_haelt_person_und_andere_referenzen(bild):
    _person_mit_zwei_referenzen(bild)
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]
    neue_bbox = [12.0, 24.0, 34.0, 44.0]

    r = gesichter_service.referenz_bbox_aktualisieren(
        "Anna", ziel["ref_id"], neue_bbox,
        embedding=[0.5, 0.5, 0.0], bbox_norm=[0.12, 0.12, 0.34, 0.22])
    assert r["ok"] is True
    assert r["verbleibend"] == 2

    personen = gesichter_service.referenzen_auflisten()["personen"]
    assert len(personen) == 1                      # KEINE Dublette der Person
    refs = personen[0]["referenzen"]
    assert len(refs) == 2                          # andere Referenz bleibt
    nach = next(x for x in refs if x["ref_id"] == ziel["ref_id"])
    assert nach["bbox"] == neue_bbox               # Rahmen aktualisiert
    assert nach["bbox_norm"] == [0.12, 0.12, 0.34, 0.22]
    andere = next(x for x in refs if x["ref_id"] != ziel["ref_id"])
    assert andere["bbox"] == BBOX2                 # unangetastet
    gespeichert = gesichter_service.person_finden("Anna")["referenzen"]
    assert next(x for x in gespeichert if x["ref_id"] == ziel["ref_id"])["embedding"] == [0.5, 0.5, 0.0]


def test_bbox_roundtrip_unbekannte_referenz(bild):
    _person_mit_zwei_referenzen(bild)
    r = gesichter_service.referenz_bbox_aktualisieren(
        "Anna", "gibtsnicht", [1, 2, 3, 4])
    assert r["ok"] is False
    assert r["fehler"] == "referenz nicht gefunden"
    assert gesichter_service.referenz_bbox_aktualisieren("Zoe", "x", [1, 2, 3, 4])["ok"] is False
    assert gesichter_service.referenz_bbox_aktualisieren("Anna", "x", [])["ok"] is False


def test_router_bbox_endpoint_roundtrip(bild, monkeypatch):
    """Derselbe Weg, den das Frontend geht: POST /referenzen/{name}/{ref_id}/bbox."""
    from app.router import gesichter as router
    _person_mit_zwei_referenzen(bild)
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]
    monkeypatch.setattr(face_service, "verfuegbar", lambda: True)
    monkeypatch.setattr(face_service, "embedding_fuer_bbox",
                        lambda pfad, bbox: [0.25, 0.75, 0.0])

    body = router.ReferenzBboxBody(bbox=[12.0, 24.0, 34.0, 44.0],
                                  bbox_norm=[0.12, 0.12, 0.34, 0.22])
    r = router.referenz_bbox_aendern("Anna", ziel["ref_id"], body)
    assert r["ok"] is True and r["ref_id"] == ziel["ref_id"]
    assert r["bbox"] == [12.0, 24.0, 34.0, 44.0]

    personen = gesichter_service.referenzen_auflisten()["personen"]
    assert len(personen[0]["referenzen"]) == 2


def test_router_bbox_endpoint_ohne_rahmen_fehler(bild):
    from fastapi import HTTPException
    from app.router import gesichter as router
    _person_mit_zwei_referenzen(bild)
    with pytest.raises(HTTPException) as e:
        router.referenz_bbox_aendern("Anna", "x", router.ReferenzBboxBody(bbox=[]))
    assert e.value.status_code == 400


def test_vektoren_verschwinden_mit_der_referenz(bild):
    """Löschen einer Referenz entfernt AUCH ihren Vektor (keine Geister)."""
    _person_mit_zwei_referenzen(bild)
    p = gesichter_service.person_finden("Anna")
    assert len(p["embedding"]) == 2
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]

    r = gesichter_service.referenz_entfernen("Anna", ziel["ref_id"])
    assert r["ok"] is True and r["verbleibend"] == 1

    p2 = gesichter_service.person_finden("Anna")
    assert len(p2["embedding"]) == 1
    assert p2["embedding"][0] == [0.0, 1.0, 0.0]          # nur der Rest
    assert len(p2["referenzen"]) == 1
    assert gesichter_service.referenz_entfernen("Anna", ziel["ref_id"])["ok"] is False
    assert gesichter_service.referenz_entfernen("Zoe", "x")["ok"] is False


def test_router_loeschen_entfernt_referenz(bild):
    from app.router import gesichter as router
    _person_mit_zwei_referenzen(bild)
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]
    r = router.referenz_loeschen("Anna", ziel["ref_id"])
    assert r["ok"] is True and r["verbleibend"] == 1
    assert gesichter_service.person_finden("Anna") is not None   # Person bleibt


# ---------------------------------------------------------------------------
# (4) Punkt 0 (16.10.2026): „vektor_erneuert" ehrlich melden
#     Der Befundlauf hat drei Wege belegt, auf denen der Aufruf ok meldete,
#     waehrend der ALTE Vektor gueltig blieb: A (Engine antwortet nicht),
#     B (Ausschnitt-Einbettung scheitert), D (Referenz ohne Bildpfad).
# ---------------------------------------------------------------------------

def _roh_vektoren(name):
    """Vektoren der Referenzen, wie sie in der GESPEICHERTEN Datei stehen."""
    with open(gesichter_service.KATALOG_DATEI, "r", encoding="utf-8") as f:
        roh = json.load(f)
    for p in roh.get("personen", []):
        if (p.get("name") or "").strip().lower() == name.strip().lower():
            return [r.get("embedding") for r in (p.get("referenzen") or [])]
    return []


def _body(router):
    return router.ReferenzBboxBody(bbox=[12.0, 24.0, 34.0, 44.0],
                                   bbox_norm=[0.12, 0.12, 0.34, 0.22])


def test_bbox_fall_c_normalfall_meldet_und_schreibt_neuen_vektor(bild, monkeypatch):
    """Fall C: neuer Vektor wird gemeldet UND liegt danach in der Katalogdatei."""
    from app.router import gesichter as router
    _person_mit_zwei_referenzen(bild)
    assert [1.0, 0.0, 0.0] in _roh_vektoren("Anna")        # Ausgangsstand
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]
    monkeypatch.setattr(face_service, "verfuegbar", lambda: True)
    monkeypatch.setattr(face_service, "embedding_fuer_bbox",
                        lambda pfad, bbox: [0.4, 0.4, 0.2])

    r = router.referenz_bbox_aendern("Anna", ziel["ref_id"], _body(router))
    assert r["ok"] is True
    assert r["vektor_erneuert"] is True
    assert r["vektor_grund"] == ""
    # Wirkungsnachweis: die GESPEICHERTE Datei traegt den neuen Vektor, der
    # alte ist weg (nicht nur "Aufruf hat geklappt").
    vektoren = _roh_vektoren("Anna")
    assert [0.4, 0.4, 0.2] in vektoren
    assert [1.0, 0.0, 0.0] not in vektoren


def test_bbox_fall_a_engine_antwortet_nicht(bild, monkeypatch):
    """Fall A: ohne Engine bleibt der alte Vektor — der Server sagt das auch."""
    from app.router import gesichter as router
    _person_mit_zwei_referenzen(bild)
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]
    monkeypatch.setattr(face_service, "verfuegbar", lambda: False)
    monkeypatch.setattr(face_service, "embedding_fuer_bbox",
                        lambda *a, **k: pytest.fail("ohne Engine darf nicht eingebettet werden"))

    r = router.referenz_bbox_aendern("Anna", ziel["ref_id"], _body(router))
    assert r["ok"] is True                     # Rahmen selbst wurde gespeichert
    assert r["vektor_erneuert"] is False
    assert "Engine" in r["vektor_grund"]
    assert [1.0, 0.0, 0.0] in _roh_vektoren("Anna")        # alter Vektor bleibt


def test_bbox_fall_b_einbettung_scheitert(bild, monkeypatch):
    """Fall B: Engine da, liefert aber keinen Vektor -> ehrlicher Grund."""
    from app.router import gesichter as router
    _person_mit_zwei_referenzen(bild)
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]
    monkeypatch.setattr(face_service, "verfuegbar", lambda: True)
    monkeypatch.setattr(face_service, "embedding_fuer_bbox", lambda pfad, bbox: None)

    r = router.referenz_bbox_aendern("Anna", ziel["ref_id"], _body(router))
    assert r["ok"] is True
    assert r["vektor_erneuert"] is False
    assert "Einbettung" in r["vektor_grund"]
    assert [1.0, 0.0, 0.0] in _roh_vektoren("Anna")


def test_bbox_fall_d_referenz_ohne_bildpfad(bild, monkeypatch):
    """Fall D: ohne Bildpfad ist kein Ausschnitt einbettbar — Grund statt Behauptung."""
    from app.router import gesichter as router
    gesichter_service.person_speichern(
        name="Bea",
        referenzen=[{"embedding": [0.1, 0.2, 0.3], "jahr": 2021, "bbox": list(BBOX)}],
    )
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]
    monkeypatch.setattr(face_service, "verfuegbar", lambda: True)
    monkeypatch.setattr(face_service, "embedding_fuer_bbox",
                        lambda *a, **k: pytest.fail("ohne Bildpfad darf nicht eingebettet werden"))

    r = router.referenz_bbox_aendern("Bea", ziel["ref_id"], _body(router))
    assert r["ok"] is True
    assert r["vektor_erneuert"] is False
    assert "Bildpfad" in r["vektor_grund"]
    assert [0.1, 0.2, 0.3] in _roh_vektoren("Bea")


def test_bbox_ohne_vektorwunsch_meldet_keinen_neuen_vektor(bild, monkeypatch):
    """Gegenprobe: `embedding_erneuern=False` schreibt keinen Vektor und sagt es."""
    from app.router import gesichter as router
    _person_mit_zwei_referenzen(bild)
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]
    monkeypatch.setattr(face_service, "verfuegbar", lambda: True)
    monkeypatch.setattr(face_service, "embedding_fuer_bbox",
                        lambda *a, **k: pytest.fail("ohne Wunsch darf nicht eingebettet werden"))

    body = router.ReferenzBboxBody(bbox=[12.0, 24.0, 34.0, 44.0],
                                   embedding_erneuern=False)
    r = router.referenz_bbox_aendern("Anna", ziel["ref_id"], body)
    assert r["vektor_erneuert"] is False
    assert "nicht angefordert" in r["vektor_grund"]
    assert [1.0, 0.0, 0.0] in _roh_vektoren("Anna")


def test_bbox_service_meldet_vektor_erneuert_aus_der_speicherung(bild):
    """Auch der Service allein sagt die Wahrheit (ohne Router)."""
    _person_mit_zwei_referenzen(bild)
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]

    ohne = gesichter_service.referenz_bbox_aktualisieren(
        "Anna", ziel["ref_id"], [12.0, 24.0, 34.0, 44.0])
    assert ohne["ok"] is True and ohne["vektor_erneuert"] is False
    assert [1.0, 0.0, 0.0] in _roh_vektoren("Anna")

    mit = gesichter_service.referenz_bbox_aktualisieren(
        "Anna", ziel["ref_id"], [12.0, 24.0, 34.0, 44.0],
        embedding=[0.7, 0.1, 0.2])
    assert mit["ok"] is True and mit["vektor_erneuert"] is True
    assert [0.7, 0.1, 0.2] in _roh_vektoren("Anna")
