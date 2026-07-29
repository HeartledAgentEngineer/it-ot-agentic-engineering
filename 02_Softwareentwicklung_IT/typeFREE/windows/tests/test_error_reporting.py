"""Die Fehlermeldung darf nie selbst scheitern.

Windows begrenzt die Felder des Tray-Symbols hart:
  Tooltip (szTip)              128 Zeichen
  Sprechblasen-Text (szInfo)   256 Zeichen
  Sprechblasen-Titel           64 Zeichen
Längere Werte lassen `Shell_NotifyIcon` mit ValueError scheitern — dann stirbt
die Fehlermeldung an ihrer eigenen Fehlermeldung. Eine 401-Antwort von OpenAI
ist rund 280 Zeichen lang, also weit über allen drei Grenzen.
"""
import pytest
import typefree

LANGE_MELDUNG = (
    "Text konnte nicht erzeugt werden: Error code: 401 - {'error': {'message': "
    "'Incorrect API key provided: YOUR_OPE*******_KEY. You can find your API key "
    "at https://platform.openai.com/account/api-keys.', 'type': "
    "'invalid_request_error', 'param': None, 'code': 'invalid_api_key'}}"
)


class TrayAttrappe:
    """Bildet die Längengrenzen von Windows nach."""

    TOOLTIP_MAX = 128
    TEXT_MAX    = 256
    TITEL_MAX   = 64

    def __init__(self):
        self.icon = None
        self._title = None
        self.sprechblasen = []

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, wert):
        if len(wert) > self.TOOLTIP_MAX:
            raise ValueError(f'string too long ({len(wert)}, '
                             f'maximum length {self.TOOLTIP_MAX})')
        self._title = wert

    def notify(self, message, title=None):
        if len(message) > self.TEXT_MAX:
            raise ValueError(f'string too long ({len(message)}, '
                             f'maximum length {self.TEXT_MAX})')
        if title and len(title) > self.TITEL_MAX:
            raise ValueError(f'string too long ({len(title)}, '
                             f'maximum length {self.TITEL_MAX})')
        self.sprechblasen.append((message, title))


@pytest.fixture
def tray(monkeypatch):
    attrappe = TrayAttrappe()
    monkeypatch.setattr(typefree, 'tray_icon', attrappe)
    return attrappe


def test_lange_meldung_faellt_nicht_um(tray):
    """Der eigentliche Fehler: report_error stirbt an einer 401-Antwort."""
    typefree.report_error(LANGE_MELDUNG)          # darf nicht werfen
    assert tray.icon is typefree.ICON_ERROR


def test_tooltip_bleibt_in_der_windows_grenze(tray):
    typefree.report_error(LANGE_MELDUNG)
    assert len(tray.title) <= TrayAttrappe.TOOLTIP_MAX


def test_sprechblase_erscheint_ueberhaupt(tray):
    typefree.report_error(LANGE_MELDUNG)
    assert len(tray.sprechblasen) == 1


def test_text_und_titel_sind_nicht_vertauscht(tray):
    """Die Meldung gehört in den Text, nicht in den Titel."""
    typefree.report_error(LANGE_MELDUNG)
    text, titel = tray.sprechblasen[0]
    assert 'API key' in text
    assert titel == 'typeFREE — Fehler'


def test_vollstaendige_meldung_steht_in_der_logdatei(tray, caplog):
    with caplog.at_level('ERROR', logger='typefree'):
        typefree.report_error(LANGE_MELDUNG)
    assert LANGE_MELDUNG in caplog.text


def test_meldung_ueberlebt_ein_kaputtes_tray_icon(monkeypatch, caplog):
    """Selbst wenn Windows ganz streikt, darf report_error nicht werfen."""

    class Kaputt:
        @property
        def icon(self):
            return None

        @icon.setter
        def icon(self, wert):
            raise RuntimeError('Shell_NotifyIcon streikt')

        def notify(self, *a, **k):
            raise RuntimeError('Shell_NotifyIcon streikt')

    monkeypatch.setattr(typefree, 'tray_icon', Kaputt())
    with caplog.at_level('ERROR', logger='typefree'):
        typefree.report_error('irgendwas ging schief')
    assert 'irgendwas ging schief' in caplog.text


def test_kuerzen_faltet_zeilenumbrueche_weg():
    """Ein Traceback im Tooltip wäre unlesbar — Umbrüche werden zu Leerzeichen."""
    ergebnis = typefree._kuerze('erste Zeile\nzweite Zeile', 100)
    assert ergebnis == 'erste Zeile zweite Zeile'


def test_kuerzen_haelt_die_grenze_genau_ein():
    ergebnis = typefree._kuerze('x' * 300, 128)
    assert len(ergebnis) == 128
    assert ergebnis.endswith('…')
