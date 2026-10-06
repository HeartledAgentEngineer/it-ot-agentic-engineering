"""Direktes Tippen per Unicode — die Ereignisfolge ohne echte Tastatur prüfen."""
import typefree

UNICODE, KEYUP = 0x0004, 0x0002


def test_buchstaben_werden_als_unicode_gedrueckt_und_losgelassen():
    assert typefree.unicode_ereignisse('Aä') == [
        (0, ord('A'), UNICODE), (0, ord('A'), UNICODE | KEYUP),
        (0, ord('ä'), UNICODE), (0, ord('ä'), UNICODE | KEYUP),
    ]


def test_zeilenumbruch_wird_eingabetaste():
    """Ein Unicode-„\n" ignorieren viele Programme — Enter kommt immer an."""
    assert typefree.unicode_ereignisse('\n') == [(0x0D, 0, 0), (0x0D, 0, KEYUP)]


def test_wagenruecklauf_wird_uebersprungen():
    """Aus „\r\n" darf nur EIN Zeilenumbruch werden."""
    assert typefree.unicode_ereignisse('\r\n') == [(0x0D, 0, 0), (0x0D, 0, KEYUP)]


def test_zeichen_ausserhalb_der_grundebene_als_ersatzpaar():
    """Emoji & Co. braucht zwei UTF-16-Einheiten, sonst kommt Müll an."""
    ereignisse = typefree.unicode_ereignisse('😀')
    assert [e[1] for e in ereignisse] == [0xD83D, 0xD83D, 0xDE00, 0xDE00]


def test_leerer_text_ergibt_nichts():
    assert typefree.unicode_ereignisse('') == []
