"""Tests für den Bestätigungsdialog: nur Verdrahtung und Flag-Werte – nie ein echter Dialog."""
from master_schalter import dialog


def test_flags_sind_fail_closed():
    """Nein ist der Standardknopf; nur ein echtes Ja (`IDYES`) zählt."""
    assert dialog.MB_YESNO == 0x4
    assert dialog.MB_ICONQUESTION == 0x20
    assert dialog.MB_TOPMOST == 0x40000
    assert dialog.MB_DEFBUTTON2 == 0x100
    assert dialog.IDYES == 6


def test_frage_ist_aufrufbar_und_nie_teil_der_tests():
    """Der echte Dialog wird in Tests nie geöffnet – nur die Funktion wird verdrahtet."""
    assert callable(dialog.frage)


def test_frage_akzeptiert_nur_idyes_und_belaesst_nein_als_standard(monkeypatch):
    from types import SimpleNamespace

    aufrufe = []
    ergebnisse = iter([dialog.IDYES, 7, 0])

    def message_box(*args):
        aufrufe.append(args)
        return next(ergebnisse)

    monkeypatch.setattr(dialog.ctypes, "windll", SimpleNamespace(
        user32=SimpleNamespace(MessageBoxW=message_box)), raising=False)

    assert dialog.frage("Titel", "Text") is True
    assert dialog.frage("Titel", "Text") is False
    assert dialog.frage("Titel", "Text") is False
    assert all(args[3] & dialog.MB_DEFBUTTON2 for args in aufrufe)
    assert all(args[3] & dialog.MB_YESNO for args in aufrufe)
