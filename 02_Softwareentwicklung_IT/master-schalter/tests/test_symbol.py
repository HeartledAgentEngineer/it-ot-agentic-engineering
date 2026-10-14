"""Tests für das Taskleisten-Bild (zwei Balken)."""
from master_schalter import symbol


def _gefuellt(bild, x):
    """Anzahl Pixel einer Spalte, die die Füllfarbe eines Balkens haben (nicht transparent, nicht Rahmen)."""
    hoehe = bild.size[1]
    return sum(1 for y in range(hoehe) if bild.getpixel((x, y))[3] == 255 and bild.getpixel((x, y))[:3] != symbol.RAHMEN)


def test_bildgroesse_und_modus():
    bild = symbol.bild(50, 50, 97)
    assert bild.size == (64, 64)
    assert bild.mode == "RGBA"


def test_fuellhoehe_folgt_prozent():
    bild = symbol.bild(100, 10, 97)
    links, rechts = symbol.balken_mitte()
    assert _gefuellt(bild, links) > _gefuellt(bild, rechts) * 5


def test_farbe_ab_schwelle_rot():
    bild = symbol.bild(98, 20, 97)
    links, _ = symbol.balken_mitte()
    assert bild.getpixel((links, 55))[:3] == symbol.ROT


def test_unbekannt_zeigt_leeren_balken():
    bild = symbol.bild(None, None, 97)
    links, rechts = symbol.balken_mitte()
    assert _gefuellt(bild, links) == 0
    assert _gefuellt(bild, rechts) == 0
