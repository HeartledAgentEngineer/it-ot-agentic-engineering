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


def test_symbol_kennt_keinen_master_punkt_mehr():
    import inspect

    assert "master" not in inspect.signature(symbol.bild).parameters
    assert not any(name in vars(symbol) for name in ("WEISS", "PUNKT_Y", "PUNKT_RADIUS", "MASTER_BALKEN"))


def test_oberhalb_der_balken_bleibt_alles_transparent():
    """Ohne Punkt: über den Balken (y < 12) ist kein einziges Pixel gezeichnet."""
    bild = symbol.bild(50, 50, 97)
    obere_kante = min(b[1] for b in symbol.BALKEN)
    assert all(bild.getpixel((x, y))[3] == 0 for y in range(obere_kante) for x in range(symbol.GROESSE))


def test_statusfarbe_grundfarbe_gelb_rot():
    assert symbol.farbe(10, symbol.CLAUDE, 97) == symbol.CLAUDE
    assert symbol.farbe(79.9, symbol.CODEX, 97) == symbol.CODEX
    assert symbol.farbe(80, symbol.CLAUDE, 97) == symbol.GELB
    assert symbol.farbe(96, symbol.CLAUDE, 97) == symbol.GELB
    assert symbol.farbe(97, symbol.CLAUDE, 97) == symbol.ROT
