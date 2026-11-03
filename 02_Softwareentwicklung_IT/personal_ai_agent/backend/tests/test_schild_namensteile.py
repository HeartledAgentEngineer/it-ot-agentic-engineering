"""Namensschild: Bindestrich-Namen und Namenszusätze (Hermes-Einwand S8, 03.11.2026). Namen erfunden."""
from __future__ import annotations

from app.services.pii_shield import schild_aus_namen


def test_teil_eines_bindestrich_vornamens_wird_maskiert():
    schild = schild_aus_namen(["Annalia-Brenda Quastmeier"])
    text = schild.encode("Heute mit Annalia telefoniert, später kam Brenda.")
    assert "Annalia" not in text and "Brenda" not in text


def test_ganzer_bindestrich_vorname_wird_maskiert():
    schild = schild_aus_namen(["Annalia-Brenda Quastmeier"])
    assert "Annalia-Brenda" not in schild.encode("Annalia-Brenda war da.")


def test_bindestrich_name_ohne_leerzeichen():
    schild = schild_aus_namen(["Ottokar-Wendelin"])
    assert "Ottokar" not in schild.encode("Ottokar rief an.")


def test_namenszusaetze_werden_nicht_zu_namen():
    schild = schild_aus_namen(["Wiebke von der Quastheide"])
    text = schild.encode("Der Hund von der Nachbarin und die Katze.")
    assert text == "Der Hund von der Nachbarin und die Katze."
    assert "Quastheide" not in schild.encode("Bei Quastheide gewesen.")


def test_grossgeschriebener_vorname_ist_kein_zusatz():
    # Hermes Runde 2: "Della"/"Ten" sind auch Vornamen; nur kleingeschriebene Zusätze fallen weg.
    schild = schild_aus_namen(["Della Quastmeier", "Ten Wobbeling"])
    text = schild.encode("Mit Della und Ten gesprochen.")
    assert "Della" not in text and "Ten" not in text


def test_grossgeschriebene_fuellwoerter_bleiben_woerter():
    # Hermes Runde 3: Kontakt "Die Quastoma" darf nicht jedes "die" im Text maskieren.
    schild = schild_aus_namen(["Die Quastoma", "Von Wobbelhof"])
    assert schild.encode("Die Katze von der Nachbarin und das Haus.") == "Die Katze von der Nachbarin und das Haus."
    text = schild.encode("Die Katze von nebenan und Quastoma.")
    assert text.startswith("Die Katze von nebenan und ") and "Quastoma" not in text


def test_teil_nach_apostroph_wird_maskiert():
    schild = schild_aus_namen(["Fiona O'Quastrien"])
    assert "Quastrien" not in schild.encode("Quastrien kam vorbei.")


def test_genitiv_und_endung_n_werden_maskiert():
    # Hermes Runde 4: "mit Annalias Hund" ging im Klartext hinaus.
    schild = schild_aus_namen(["Annalia Quastmeier", "Wiebke"])
    text = schild.encode("Mit Annalias Hund bei Quastmeiers, dann zu Wiebken.")
    assert "Annalia" not in text and "Quastmeier" not in text and "Wiebke" not in text


def test_genitiv_kommt_exakt_zurueck():
    schild = schild_aus_namen(["Annalia Quastmeier"], "Mit Annalias Hund")
    assert schild.decode(schild.encode("Mit Annalias Hund")) == "Mit Annalias Hund"


def test_kurze_namensteile_bekommen_keine_endung():
    # "Tim" + s = "Tims" ist selten, aber "Bens"/"Ins" wären Wörter: erst ab 4 Zeichen.
    schild = schild_aus_namen(["Ida Quastmeier"])
    assert schild.encode("Idas Garten.") == "Idas Garten."


def test_umschrift_rueckwaerts():
    # Hermes Runde 4: gespeichert "Juergen", im Text "Jürgen".
    schild = schild_aus_namen(["Juergen Quastmeier", "Tessa Grossling", "Ruth Hoefling"])
    text = schild.encode("Jürgen, Großling und Höfling waren da.")
    assert "Jürgen" not in text and "Großling" not in text and "Höfling" not in text


def test_rueckuebersetzung_bleibt_exakt():
    schild = schild_aus_namen(["Annalia-Brenda Quastmeier"], "Mit Annalia")
    assert schild.decode(schild.encode("Mit Annalia")) == "Mit Annalia"
