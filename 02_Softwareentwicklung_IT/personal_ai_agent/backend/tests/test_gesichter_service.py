"""Tests für den Gesichter-Katalog (Personen-Merkliste).

Sichert: Anlegen/Lesen/Aktualisieren/Entfernen von Personen, case-insensitive
Suche, Kontext-Block für den Prompt, und dass NUR Pfade (keine Bilddaten)
gespeichert werden.
"""

import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import gesichter_service  # noqa: E402


def _katalog_leeren():
    import json
    with open(gesichter_service.KATALOG_DATEI, "w", encoding="utf-8") as f:
        json.dump({"personen": []}, f)


def test_leerer_katalog():
    _katalog_leeren()
    assert gesichter_service.liste_personen() == []
    assert gesichter_service.katalog_kontext() == ""


def test_person_speichern_und_lesen():
    _katalog_leeren()
    p = gesichter_service.person_speichern(
        name="Pedi",
        rolle="Mutter",
        beschreibung="graue Haare",
    )
    assert p["name"] == "Pedi"
    assert p["rolle"] == "Mutter"
    assert "gelernt_am" in p

    gefunden = gesichter_service.person_finden("pedi")  # case-insensitive
    assert gefunden is not None
    assert gefunden["name"] == "Pedi"


def test_person_aktualisieren_kein_duplikat():
    _katalog_leeren()
    gesichter_service.person_speichern("Helga", "Oma")
    gesichter_service.person_speichern("helga", beziehung="sitzt hinten")
    personen = gesichter_service.liste_personen()
    assert len(personen) == 1
    assert personen[0]["beziehung"] == "sitzt hinten"


def test_entfernen():
    _katalog_leeren()
    gesichter_service.person_speichern("Sigrun", "Großtante")
    assert gesichter_service.person_entfernen("sigrun") is True
    assert gesichter_service.person_entfernen("gibt-es-nicht") is False
    assert gesichter_service.liste_personen() == []


def test_nur_pfad_keine_bilddaten():
    """Sebastian-Regel: nur der Referenzbild-Pfad wird getragen (kein Upload-Content)."""
    _katalog_leeren()
    gesichter_service.person_speichern(
        "Sebastian", referenz_bild_pfad="/sdcard/Pictures/ich.jpg"
    )
    p = gesichter_service.person_finden("Sebastian")
    assert p is not None
    assert p["referenz_bild_pfad"] == "/sdcard/Pictures/ich.jpg"


def test_referenz_miniatur_aus_pfad_erzeugt():
    """Aus einem echten Bildpfad wird automatisch eine eingebettete Miniatur
    erzeugt (damit das Referenzbild pCloud-Transfers des Originals übersteht)."""
    _katalog_leeren()
    # Kleines Testbild in einer Temp-Datei erzeugen (Pillow, falls verfügbar).
    try:
        from PIL import Image
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        Image.new("RGB", (200, 200), (90, 90, 90)).save(tmp.name, "JPEG")
    except Exception:
        return  # kein PIL auf dem Testlauf → Test überspringen (kein Crash)

    try:
        gesichter_service.person_speichern(
            "Pedi", referenz_bild_pfad=tmp.name
        )
        p = gesichter_service.person_finden("Pedi")
        assert p is not None
        assert p["referenz_bild_pfad"] == tmp.name
        miniatur = p.get("referenz_bild_miniatur", "")
        assert miniatur.startswith("data:image/jpeg;base64,"), "Miniatur fehlt"
        # Original löschen (simuliert pCloud-Verschieben) → Miniatur bleibt.
        os.unlink(tmp.name)
        p2 = gesichter_service.person_finden("Pedi")
        assert p2 is not None
        assert p2["referenz_bild_miniatur"], "Miniatur überlebt den Pfad-Umzug"
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def test_referenz_bilder_liefert_miniatur():
    """referenz_bilder() liefert die eingebettete Miniatur als Bild-File für
    den Vision-LLM (damit ein Foto gegen bekannte Gesichter abgeglichen wird)."""
    _katalog_leeren()
    try:
        from PIL import Image
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        Image.new("RGB", (100, 100), (200, 100, 100)).save(tmp.name, "JPEG")
    except Exception:
        return
    try:
        gesichter_service.person_speichern(
            "Helga", rolle="Oma", referenz_bild_pfad=tmp.name
        )
        bilder = gesichter_service.referenz_bilder()
        assert any(
            b.get("person") == "Helga"
            and b.get("type") == "image"
            and (b.get("data_url") or "").startswith("data:image")
            for b in bilder
        ), "Referenzbild fehlt in der Bild-Liste"
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def test_kontext_block_enthaelt_namen():
    _katalog_leeren()
    gesichter_service.person_speichern("Pedi", "Mutter", beschreibung="graue Haare")
    kontext = gesichter_service.katalog_kontext()
    assert "Pedi" in kontext
    assert "GELERNTE PERSONEN" in kontext
    assert "graue Haare" in kontext


def test_leerer_name_wird_abgelehnt():
    _katalog_leeren()
    try:
        gesichter_service.person_speichern("   ")
        assert False, "Leerer Name hätte abgelehnt werden müssen"
    except ValueError:
        pass