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


def test_rueckuebersetzung_bleibt_exakt():
    schild = schild_aus_namen(["Annalia-Brenda Quastmeier"], "Mit Annalia")
    assert schild.decode(schild.encode("Mit Annalia")) == "Mit Annalia"
