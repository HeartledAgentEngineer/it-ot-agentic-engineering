"""Zwischenablage schützen und wiederherstellen (Scheibe 2, 20.10.2026).

Diktate sollen nicht im Win+V-Verlauf und nicht in der Cloud-Zwischenablage
landen; was vorher kopiert war, kommt nach dem Einfügen zurück. Alle Prüfungen
laufen gegen eine Fake-API mit Zustand — die ECHTE Windows-Zwischenablage wird
nie berührt (sie gehört Sebastian, und ein Test würde ihren Inhalt überschreiben).
Die Verdrahtung in `typefree._verarbeite_audio` läuft über die Nähte
`zwischenablage_einfuegen` / `_zurueck` / `_kopieren`, die hier ersetzt werden.
"""
import ctypes
import threading

import numpy as np
import pytest

import typefree
import zwischenablage as zw

CF_TEXT, CF_BITMAP, CF_METAFILEPICT, CF_OEMTEXT = 1, 2, 3, 7
CF_DIB, CF_PALETTE, CF_UNICODETEXT, CF_ENHMETAFILE = 8, 9, 13, 14
CF_LOCALE, CF_DIBV5 = 16, 17
EIGENES_FORMAT = 0xC123      # registriertes Fremdformat (z. B. HTML einer Webseite)


class FakeApi:
    """Zwischenablage mit Zustand, Ereignisprotokoll und Fehlerschaltern.

    `inhalt` ist die geordnete Liste (Format, Bytes); Bytes `None` heißt „liegt
    nur als GDI-Handle vor" — `lese` wirft dann wie die echte Schicht. Die Fake
    erzwingt, dass jede Operation nur bei geöffneter Zwischenablage läuft.
    """

    def __init__(self, formate=(), belegt=0, lesefehler=(), setzfehler=None):
        self.inhalt = [(f, d) for f, d in formate]
        self.belegt = belegt                  # so viele Öffnen-Versuche schlagen fehl
        self.lesefehler = set(lesefehler)
        self.setzfehler = dict(setzfehler or {})   # Format -> Zahl fehlschlagender Aufrufe
        self.offen = False
        self.seq = 100
        self.open_versuche = 0
        self.ereignisse = []
        self.ids = {}

    # -- die API, die zwischenablage.py benutzt ---------------------------
    def OpenClipboard(self):
        self.open_versuche += 1
        if self.belegt > 0:
            self.belegt -= 1
            return False
        assert not self.offen, 'doppelt geöffnet'
        self.offen = True
        self.ereignisse.append(('open',))
        return True

    def CloseClipboard(self):
        assert self.offen, 'Close ohne Open'
        self.offen = False
        self.ereignisse.append(('close',))
        return True

    def EmptyClipboard(self):
        assert self.offen
        self.ereignisse.append(('empty',))
        self.inhalt = []
        self.seq += 1
        return True

    def EnumClipboardFormats(self, vorher):
        assert self.offen
        formate = [f for f, _ in self.inhalt]
        if vorher == 0:
            return formate[0] if formate else 0
        i = formate.index(vorher)
        return formate[i + 1] if i + 1 < len(formate) else 0

    def lese(self, fmt, limit):
        assert self.offen
        self.ereignisse.append(('lese', fmt))
        if fmt in self.lesefehler:
            raise OSError('Lesefehler')
        daten = dict(self.inhalt)[fmt]
        if daten is None:
            raise OSError('nur als Handle vorhanden')
        if len(daten) > limit:
            raise zw.ZuGross(fmt)
        return daten

    def setze(self, fmt, daten):
        assert self.offen
        if self.setzfehler.get(fmt, 0) > 0:
            self.setzfehler[fmt] -= 1
            self.ereignisse.append(('setzfehler', fmt))
            return False
        self.ereignisse.append(('set', fmt, bytes(daten)))
        self.inhalt.append((fmt, bytes(daten)))
        self.seq += 1
        return True

    def RegisterClipboardFormat(self, name):
        return self.ids.setdefault(name, 0xC000 + len(self.ids))

    def GetClipboardSequenceNumber(self):
        return self.seq

    # -- Hilfen für Tests -------------------------------------------------
    def fremd_kopieren(self, formate):
        """Eine andere App kopiert — nur bei geschlossener Zwischenablage möglich."""
        assert not self.offen
        self.inhalt = list(formate)
        self.seq += 1

    def als_dict(self):
        return dict(self.inhalt)

    def ids_der(self, name):
        return self.ids[name]

    def ereignis_namen(self):
        return [e[0] for e in self.ereignisse]


def utf16(text):
    return (text + '\0').encode('utf-16-le')


FREMD = [(CF_UNICODETEXT, utf16('vorher kopiert')), (EIGENES_FORMAT, b'<b>vorher</b>')]


@pytest.fixture(autouse=True)
def kein_offenes_einfuegen(monkeypatch):
    """Jeder Test startet ohne gemerktes, noch offenes Einfügen (Modulzustand)."""
    monkeypatch.setattr(zw, '_offen', None)


@pytest.fixture(autouse=True)
def kein_schlaf(monkeypatch):
    """Öffnen-Wiederholung und Rückgabe-Faden dürfen die Tests nicht ausbremsen."""
    monkeypatch.setattr(zw.time, 'sleep', lambda s: None)


# ══ sichern_und_schreiben ═══════════════════════════════════════════════════

def test_alles_in_einem_durchgang_ohne_close_dazwischen():
    """Sichern und Leeren liegen im selben OpenClipboard: dazwischen kann keine
    andere App kopieren — die Sicherung ist der Stand unmittelbar vor dem Leeren."""
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Hallo Welt', api)

    assert erg.geschrieben
    namen = api.ereignis_namen()
    assert namen.count('open') == 1 and namen.count('close') == 1
    assert namen[0] == 'open' and namen[-1] == 'close'
    letztes_lesen = max(i for i, n in enumerate(namen) if n == 'lese')
    leeren = namen.index('empty')
    assert letztes_lesen < leeren, 'erst alles lesen, dann leeren'
    assert all(n == 'set' for n in namen[leeren + 1:-1]), 'nach dem Leeren nur Setzen'


def test_fremder_inhalt_vor_dem_durchgang_wird_mitgesichert():
    api = FakeApi([(CF_UNICODETEXT, utf16('alt'))])
    api.fremd_kopieren(FREMD)          # jemand kopiert, bevor wir öffnen
    erg = zw.sichern_und_schreiben('Diktat', api)

    assert erg.geschrieben
    assert dict(erg.snapshot.formate) == dict(FREMD)
    assert erg.snapshot.vollstaendig


def test_schreibt_text_und_die_drei_privatformate_mit_richtigen_werten():
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Grüße ✓', api)

    assert erg.geschrieben and erg.grund == ''
    inhalt = api.als_dict()
    assert inhalt[CF_UNICODETEXT] == utf16('Grüße ✓')
    assert inhalt[api.ids_der('ExcludeClipboardContentFromMonitorProcessing')] == b''
    assert inhalt[api.ids_der('CanIncludeInClipboardHistory')] == (0).to_bytes(4, 'little')
    assert inhalt[api.ids_der('CanUploadToCloudClipboard')] == (0).to_bytes(4, 'little')
    assert EIGENES_FORMAT not in inhalt, 'der fremde Inhalt ist geleert'


def test_nummer_ist_die_sequenznummer_nach_dem_schreiben():
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Text', api)
    assert erg.nummer == api.GetClipboardSequenceNumber()
    assert not api.offen


def test_nur_enhmetafile_ist_unvollstaendig_und_veraendert_nichts():
    """Grafik nur als GDI-Handle: nicht kopierbar → nicht anfassen."""
    api = FakeApi([(CF_ENHMETAFILE, None)])
    erg = zw.sichern_und_schreiben('Text', api)

    assert not erg.geschrieben and erg.grund == 'unvollstaendig'
    assert not erg.snapshot.vollstaendig
    assert api.inhalt == [(CF_ENHMETAFILE, None)]
    assert 'empty' not in api.ereignis_namen() and 'set' not in api.ereignis_namen()
    assert not api.offen


def test_lesefehler_ist_unvollstaendig_und_veraendert_nichts():
    api = FakeApi(FREMD, lesefehler={EIGENES_FORMAT})
    erg = zw.sichern_und_schreiben('Text', api)

    assert not erg.geschrieben and erg.grund == 'unvollstaendig'
    assert api.inhalt == list(FREMD)
    assert 'empty' not in api.ereignis_namen()


def test_ueber_32_mb_ist_unvollstaendig_und_veraendert_nichts():
    gross = b'\0' * (33 * 1024 * 1024)
    api = FakeApi([(CF_DIB, gross)])
    erg = zw.sichern_und_schreiben('Text', api)

    assert not erg.geschrieben and erg.grund == 'unvollstaendig'
    assert 'empty' not in api.ereignis_namen()


def test_gesamtgroesse_ueber_32_mb_ist_unvollstaendig():
    """Zwei Blöcke, einzeln erlaubt, zusammen zu groß."""
    block = b'\0' * (17 * 1024 * 1024)
    api = FakeApi([(CF_DIB, block), (EIGENES_FORMAT, block)])
    erg = zw.sichern_und_schreiben('Text', api)

    assert not erg.geschrieben and erg.grund == 'unvollstaendig'
    assert 'empty' not in api.ereignis_namen()


def test_bitmap_neben_dib_ist_synthetisiert_und_vollstaendig():
    api = FakeApi([(CF_DIB, b'dibdaten'), (CF_BITMAP, None)])
    erg = zw.sichern_und_schreiben('Text', api)

    assert erg.geschrieben and erg.snapshot.vollstaendig
    assert erg.snapshot.formate == [(CF_DIB, b'dibdaten')]


def test_bitmap_und_palette_neben_dibv5_sind_vollstaendig():
    api = FakeApi([(CF_DIBV5, b'v5'), (CF_BITMAP, None), (CF_PALETTE, None)])
    erg = zw.sichern_und_schreiben('Text', api)
    assert erg.geschrieben and erg.snapshot.vollstaendig


def test_bitmap_ohne_dib_ist_unvollstaendig():
    api = FakeApi([(CF_BITMAP, None)])
    erg = zw.sichern_und_schreiben('Text', api)
    assert not erg.geschrieben and erg.grund == 'unvollstaendig'


def test_enhmetafile_neben_dib_bleibt_unvollstaendig():
    """CF_ENHMETAFILE wird aus CF_DIB NICHT als gesichert gezählt."""
    api = FakeApi([(CF_DIB, b'dib'), (CF_ENHMETAFILE, None)])
    erg = zw.sichern_und_schreiben('Text', api)
    assert not erg.geschrieben and erg.grund == 'unvollstaendig'


def test_metafilepict_und_enhmetafile_gegenseitig_zaehlen_nicht():
    api = FakeApi([(CF_METAFILEPICT, None), (CF_ENHMETAFILE, None)])
    assert zw.sichern_und_schreiben('Text', api).grund == 'unvollstaendig'


def test_ownerdisplay_und_gdi_objekte_sind_unvollstaendig():
    for fmt in (0x80, 0x82, 0x83, 0x8E, 0x0305):
        api = FakeApi([(CF_UNICODETEXT, utf16('x')), (fmt, None)])
        assert zw.sichern_und_schreiben('Text', api).grund == 'unvollstaendig', hex(fmt)


def test_text_neben_unicodetext_wird_mitgesichert_und_ist_vollstaendig():
    api = FakeApi([(CF_UNICODETEXT, utf16('hallo')), (CF_TEXT, b'hallo\0'),
                   (CF_OEMTEXT, b'hallo\0'), (CF_LOCALE, b'\x07\x04\x00\x00')])
    erg = zw.sichern_und_schreiben('Text', api)

    assert erg.geschrieben and erg.snapshot.vollstaendig
    assert [f for f, _ in erg.snapshot.formate] == [CF_UNICODETEXT, CF_TEXT,
                                                    CF_OEMTEXT, CF_LOCALE]


def test_leere_zwischenablage_ist_vollstaendig_mit_leerem_snapshot():
    api = FakeApi([])
    erg = zw.sichern_und_schreiben('Text', api)

    assert erg.geschrieben
    assert erg.snapshot.vollstaendig and erg.snapshot.formate == []
    assert api.als_dict()[CF_UNICODETEXT] == utf16('Text')


@pytest.mark.parametrize('kaputt', ['CanIncludeInClipboardHistory', CF_UNICODETEXT])
def test_setzfehler_nach_dem_leeren_schreibt_den_snapshot_zurueck(kaputt):
    """Scheitert ein Setzen, nachdem geleert wurde, stellt derselbe Durchgang
    den Inhalt wieder her — der Aufrufer tippt dann, die Zwischenablage ist heil."""
    api = FakeApi(FREMD)
    if isinstance(kaputt, str):
        api.RegisterClipboardFormat(kaputt)
        kaputt = api.ids_der(kaputt)
    api.setzfehler = {kaputt: 1}
    erg = zw.sichern_und_schreiben('Text', api)

    assert not erg.geschrieben and erg.grund == 'setzen'
    assert erg.zurueckgeschrieben
    assert api.inhalt == list(FREMD)
    namen = api.ereignis_namen()
    assert namen.count('open') == 1 and namen.count('close') == 1
    assert namen.count('empty') == 2, 'einmal fürs Schreiben, einmal vor dem Rückschreiben'
    assert not api.offen


def test_setzfehler_und_rueckschreiben_scheitert_wird_gemeldet():
    api = FakeApi(FREMD)
    api.RegisterClipboardFormat('CanUploadToCloudClipboard')
    api.setzfehler = {api.ids_der('CanUploadToCloudClipboard'): 1,
                      CF_UNICODETEXT: 99}      # das Zurückschreiben des Textes scheitert
    erg = zw.sichern_und_schreiben('Text', api)

    assert not erg.geschrieben and erg.grund == 'setzen'
    assert not erg.zurueckgeschrieben
    assert not api.offen


def test_oeffnen_wiederholt_bei_belegter_zwischenablage():
    api = FakeApi(FREMD, belegt=2)
    erg = zw.sichern_und_schreiben('Text', api)
    assert erg.geschrieben and api.open_versuche == 3


def test_oeffnen_gibt_nach_10_versuchen_auf_ohne_etwas_zu_veraendern():
    api = FakeApi(FREMD, belegt=10)
    erg = zw.sichern_und_schreiben('Text', api)

    assert not erg.geschrieben and erg.grund == 'oeffnen'
    assert api.open_versuche == 10
    assert api.inhalt == list(FREMD)


def test_zehnter_versuch_reicht_noch():
    api = FakeApi(FREMD, belegt=9)
    assert zw.sichern_und_schreiben('Text', api).geschrieben


def test_unerwartete_api_ausnahme_schliesst_und_meldet_fehler():
    class Platzt(FakeApi):
        def RegisterClipboardFormat(self, name):
            raise RuntimeError('kaputt')

    api = Platzt(FREMD)
    erg = zw.sichern_und_schreiben('Text', api)

    assert not erg.geschrieben and erg.grund == 'fehler'
    assert not api.offen
    assert api.inhalt == list(FREMD)


def test_aufzaehlfehler_ist_unvollstaendig_und_veraendert_nichts():
    """Codex R1/2: EnumClipboardFormats meldet Fehler und Ende beide mit 0. Eine
    abgebrochene Aufzählung darf nie als vollständige Sicherung gelten."""
    class BrichtAb(FakeApi):
        def EnumClipboardFormats(self, vorher):
            if vorher:                       # erstes Format kommt, dann Fehler
                raise OSError('EnumClipboardFormats schlug fehl')
            return super().EnumClipboardFormats(vorher)

    api = BrichtAb(FREMD)
    erg = zw.sichern_und_schreiben('Text', api)
    assert not erg.geschrieben and erg.grund == 'unvollstaendig'
    assert erg.snapshot.grund == 'aufzaehlfehler'
    assert 'empty' not in api.ereignis_namen()
    assert api.inhalt == list(FREMD) and not api.offen


# ══ wiederherstellen ════════════════════════════════════════════════════════

def test_wiederherstellen_nur_wenn_noch_unser_diktat_drinliegt():
    """Codex R1/1: Windows zählt die Nummer auch beim Schließen hoch; abgelesen
    wird sie danach. Kopiert in dieser Lücke jemand anders, hält typeFREE dessen
    Nummer für die eigene — die Inhaltsprüfung fängt das ab."""
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    fremd = [(CF_UNICODETEXT, utf16('in der Lücke kopiert'))]
    api.inhalt = list(fremd)                 # gleiche Nummer, anderer Inhalt
    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is False
    assert api.inhalt == fremd and not api.offen


def test_wiederherstellen_braucht_das_ausschluss_kennzeichen():
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    api.inhalt = [(CF_UNICODETEXT, utf16('Diktat'))]   # gleicher Text, aber ohne Kennzeichen
    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is False


def test_wiederherstellen_ohne_eigenen_text_stellt_nicht_zurueck():
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    erg.snapshot.eigener_text = None
    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is False


def test_snapshot_kennt_den_eigenen_text():
    erg = zw.sichern_und_schreiben('Diktat', FakeApi(FREMD))
    assert erg.snapshot.eigener_text == utf16('Diktat')


def test_wiederherstellen_bei_gleicher_nummer_stellt_alles_zurueck():
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is True

    assert api.inhalt == list(FREMD)
    assert not api.offen


def test_wiederherstellen_laesst_fremdes_kopieren_in_ruhe():
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    neu = [(CF_UNICODETEXT, utf16('zwischendurch kopiert'))]
    api.fremd_kopieren(neu)

    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is False
    assert api.inhalt == neu
    assert 'empty' not in api.ereignis_namen()[api.ereignis_namen().index('close'):]


def test_wiederherstellen_leerer_snapshot_leert_nur():
    api = FakeApi([])
    erg = zw.sichern_und_schreiben('Diktat', api)
    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is True
    assert api.inhalt == []


def test_wiederherstellen_unvollstaendiger_snapshot_macht_nichts():
    api = FakeApi([(CF_ENHMETAFILE, None)])
    erg = zw.sichern_und_schreiben('Diktat', api)       # unvollständig
    assert zw.wiederherstellen(erg.snapshot, api.GetClipboardSequenceNumber(), api) is False
    assert api.inhalt == [(CF_ENHMETAFILE, None)]


def test_wiederherstellen_bei_belegter_zwischenablage_gibt_auf():
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    api.belegt = 10
    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is False
    assert CF_UNICODETEXT in api.als_dict() and api.als_dict()[CF_UNICODETEXT] == utf16('Diktat')


def test_wiederherstellen_prueft_die_nummer_im_geoeffneten_zustand():
    """Zwischen Prüfung und Öffnen darf niemand kopiert haben können: die Nummer
    wird nach dem Öffnen (dann ist die Zwischenablage für andere gesperrt) geprüft."""
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    api.ereignisse.clear()
    zw.wiederherstellen(erg.snapshot, erg.nummer, api)
    assert api.ereignis_namen()[0] == 'open'


def test_wiederherstellen_oeffnet_gar_nicht_erst_wenn_die_nummer_schon_abweicht():
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    api.fremd_kopieren([(CF_UNICODETEXT, utf16('fremd'))])
    versuche = api.open_versuche
    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is False
    assert api.open_versuche == versuche


def test_wiederherstellen_erkennt_fremdes_kopieren_zwischen_pruefung_und_oeffnen():
    """Die Nummer stimmt bei der ersten Prüfung, aber eine andere App kopiert,
    bevor wir die Zwischenablage öffnen können: die Prüfung im geöffneten
    Zustand muss das auffangen, sonst überschreiben wir fremden Inhalt."""
    fremd = [(CF_UNICODETEXT, utf16('dazwischen kopiert'))]

    class KopiertBeimOeffnen(FakeApi):
        def OpenClipboard(self):
            if not getattr(self, 'schon', False):
                self.schon = True
                self.inhalt = list(fremd)
                self.seq += 1
            return super().OpenClipboard()

    api = KopiertBeimOeffnen(FREMD)
    api.schon = True                       # das Sichern selbst läuft normal
    erg = zw.sichern_und_schreiben('Diktat', api)
    api.schon = False                      # ab jetzt kopiert „jemand" beim Öffnen

    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is False
    assert api.inhalt == fremd
    assert not api.offen


# ══ privat_kopieren ═════════════════════════════════════════════════════════

def test_privat_kopieren_schreibt_text_und_privatformate_ohne_wiederherstellung():
    api = FakeApi(FREMD)
    zw.privat_kopieren('Letztes Diktat', api)

    inhalt = api.als_dict()
    assert inhalt[CF_UNICODETEXT] == utf16('Letztes Diktat')
    assert inhalt[api.ids_der('ExcludeClipboardContentFromMonitorProcessing')] == b''
    assert inhalt[api.ids_der('CanIncludeInClipboardHistory')] == (0).to_bytes(4, 'little')
    assert inhalt[api.ids_der('CanUploadToCloudClipboard')] == (0).to_bytes(4, 'little')
    assert EIGENES_FORMAT not in inhalt
    assert not api.offen


def test_privat_kopieren_wirft_bei_belegter_zwischenablage():
    api = FakeApi(FREMD, belegt=10)
    with pytest.raises(OSError):
        zw.privat_kopieren('Text', api)
    assert api.inhalt == list(FREMD)


def test_privat_kopieren_wirft_bei_setzfehler_und_schliesst():
    api = FakeApi(FREMD, setzfehler={CF_UNICODETEXT: 1})
    with pytest.raises(OSError):
        zw.privat_kopieren('Text', api)
    assert not api.offen


# ══ echte Win32-Schicht: nur die Speicherregel, mit ctypes-Attrappen ═════════

class _Dll:
    """Minimale Attrappe für user32/kernel32 — kein Aufruf erreicht Windows."""

    def __init__(self, set_ergebnis):
        self.freigegeben = []
        self.set_ergebnis = set_ergebnis
        self._puffer = {}
        self._naechste = 0x1000

    def GlobalAlloc(self, flags, groesse):
        self._naechste += 0x100
        self._puffer[self._naechste] = ctypes.create_string_buffer(max(groesse, 1))
        return self._naechste

    def GlobalLock(self, handle):
        return ctypes.addressof(self._puffer[handle])

    def GlobalUnlock(self, handle):
        return 1

    def GlobalFree(self, handle):
        self.freigegeben.append(handle)
        return 0

    def SetClipboardData(self, fmt, handle):
        return handle if self.set_ergebnis else None


class _FensterDll(_Dll):
    def __init__(self, hwnd):
        super().__init__(set_ergebnis=True)
        self.hwnd = hwnd
        self.geoeffnet = []
        self.aufzaehlung = []

    def CreateWindowExW(self, *args):
        return self.hwnd

    def OpenClipboard(self, hwnd):
        self.geoeffnet.append(hwnd)
        return 1

    def DestroyWindow(self, hwnd):
        return 1

    def EnumClipboardFormats(self, vorher):
        fehler, ergebnis = self.aufzaehlung.pop(0)
        ctypes.set_last_error(fehler)
        return ergebnis


def test_echte_schicht_oeffnet_nicht_ohne_besitzerfenster():
    """Codex R1/3: Ohne Fenster kann nach dem Leeren SetClipboardData scheitern —
    dann wäre der Vorinhalt weg. Also gar nicht erst öffnen."""
    dll = _FensterDll(hwnd=None)
    api = zw._WindowsApi(user32=dll, kernel32=dll)
    assert api.OpenClipboard() is False
    assert dll.geoeffnet == []


def test_echte_schicht_oeffnet_mit_besitzerfenster():
    dll = _FensterDll(hwnd=0x4242)
    api = zw._WindowsApi(user32=dll, kernel32=dll)
    assert api.OpenClipboard() is True
    assert dll.geoeffnet == [0x4242]


def test_echte_schicht_unterscheidet_ende_und_fehler_der_aufzaehlung():
    dll = _FensterDll(hwnd=0x4242)
    api = zw._WindowsApi(user32=dll, kernel32=dll)
    dll.aufzaehlung = [(0, 0)]                     # 0 + ERROR_SUCCESS = Ende
    assert api.EnumClipboardFormats(13) == 0
    dll.aufzaehlung = [(1418, 0)]                  # 0 + Fehler (z. B. nicht geöffnet)
    with pytest.raises(OSError):
        api.EnumClipboardFormats(13)


def test_echte_schicht_gibt_den_speicher_frei_wenn_setzen_scheitert():
    dll = _Dll(set_ergebnis=False)
    api = zw._WindowsApi(user32=dll, kernel32=dll)
    assert api.setze(CF_UNICODETEXT, b'abc') is False
    assert len(dll.freigegeben) == 1, 'SetClipboardData hat den Block nicht übernommen'


def test_echte_schicht_behaelt_den_speicher_wenn_windows_ihn_uebernimmt():
    dll = _Dll(set_ergebnis=True)
    api = zw._WindowsApi(user32=dll, kernel32=dll)
    assert api.setze(CF_UNICODETEXT, b'abc') is True
    assert dll.freigegeben == [], 'nach Erfolg gehört der Block der Zwischenablage'


# ══ Verdrahtung in typefree._verarbeite_audio ═══════════════════════════════

def sprache(sekunden):
    rng = np.random.default_rng(3)
    return rng.normal(0, 0.2, int(sekunden * typefree.SAMPLE_RATE)).astype(np.float32)


def stille(sekunden):
    return np.zeros(int(sekunden * typefree.SAMPLE_RATE), dtype=np.float32)


SNAP = zw.Snapshot(formate=[(CF_UNICODETEXT, utf16('vorher'))], vollstaendig=True)


@pytest.fixture
def ablauf(monkeypatch):
    """Ruhiggestellter Ablauf mit Aufzeichnung aller Nähte."""
    s = {'eingefuegt': [], 'zurueck': [], 'kopiert': [], 'hotkeys': [],
         'getippt': [], 'fehler': [], 'schlaf': [], 'ergebnis': None,
         'zurueck_da': threading.Event()}
    s['ergebnis'] = zw.Ergebnis(geschrieben=True, snapshot=SNAP, nummer=4711)

    def einfuegen(text):
        s['eingefuegt'].append(text)
        return s['ergebnis']

    def zurueck(snapshot, nummer):
        s['zurueck'].append((snapshot, nummer))
        s['zurueck_da'].set()
        return True

    monkeypatch.setattr(typefree, 'zwischenablage_einfuegen', einfuegen)
    monkeypatch.setattr(typefree, 'zwischenablage_zurueck', zurueck)
    monkeypatch.setattr(typefree, 'zwischenablage_kopieren', s['kopiert'].append)
    monkeypatch.setattr(typefree, 'unicode_tippen', s['getippt'].append)
    monkeypatch.setattr(typefree.pyautogui, 'hotkey',
                        lambda *a: s['hotkeys'].append(a))
    monkeypatch.setattr(typefree.time, 'sleep', s['schlaf'].append)
    monkeypatch.setattr(typefree, 'zwischenablage_zurueck_an', True)
    monkeypatch.setattr(typefree, 'letztes_diktat', None)
    monkeypatch.setattr(typefree, 'save_verbrauch', lambda *a, **k: None)
    monkeypatch.setattr(typefree, 'verbrauch_buchen',
                        lambda v, *a, **k: v)
    monkeypatch.setattr(typefree, '_status_transcribing', lambda: None)
    monkeypatch.setattr(typefree, '_status_polishing', lambda: None)
    monkeypatch.setattr(typefree, '_status_idle', lambda: None)
    monkeypatch.setattr(typefree, 'report_error', s['fehler'].append)
    monkeypatch.setattr(typefree, 'polish_text', lambda text: text)
    typefree.retry_verwerfen()
    yield s
    typefree.retry_verwerfen()


def diktat(monkeypatch, text):
    monkeypatch.setattr(typefree, 'transcribe_audio',
                        lambda puffer, clients, **_: (text, 'mai'))


def test_rueckgabe_sekunden_sind_anderthalb():
    assert typefree.ZWISCHENABLAGE_RUECKGABE_SEKUNDEN == 1.5


def test_geschrieben_strg_v_und_rueckgabe_mit_snapshot_und_nummer(monkeypatch, ablauf):
    diktat(monkeypatch, 'Hallo zusammen')
    typefree._verarbeite_audio(sprache(2.0))

    assert ablauf['eingefuegt'] == ['Hallo zusammen']
    assert ablauf['hotkeys'] == [('ctrl', 'v')]
    assert ablauf['getippt'] == []
    assert ablauf['zurueck_da'].wait(2), 'Rückgabe-Faden hat nicht gelaufen'
    assert ablauf['zurueck'] == [(SNAP, 4711)]
    assert 0.3 in ablauf['schlaf'] and typefree.ZWISCHENABLAGE_RUECKGABE_SEKUNDEN in ablauf['schlaf']
    assert ablauf['fehler'] == []


def test_rueckgabe_laeuft_nach_dem_einfuegen_nicht_davor(monkeypatch, ablauf):
    """Strg+V muss vor der Wiederherstellung laufen, sonst fügte Strg+V den alten Inhalt ein."""
    reihenfolge = []
    monkeypatch.setattr(typefree.pyautogui, 'hotkey', lambda *a: reihenfolge.append('strg+v'))

    def zurueck(snapshot, nummer):
        reihenfolge.append('zurueck')
        ablauf['zurueck_da'].set()
    monkeypatch.setattr(typefree, 'zwischenablage_zurueck', zurueck)
    diktat(monkeypatch, 'Hallo')
    typefree._verarbeite_audio(sprache(2.0))

    assert ablauf['zurueck_da'].wait(2)
    assert reihenfolge == ['strg+v', 'zurueck']


def test_fehler_in_der_rueckgabe_wird_nur_geloggt(monkeypatch, ablauf):
    def zurueck(snapshot, nummer):
        ablauf['zurueck_da'].set()
        raise OSError('Zwischenablage weg')
    monkeypatch.setattr(typefree, 'zwischenablage_zurueck', zurueck)
    diktat(monkeypatch, 'Hallo')
    typefree._verarbeite_audio(sprache(2.0))

    assert ablauf['zurueck_da'].wait(2)
    assert ablauf['fehler'] == [], 'ein Rückgabefehler ist kein Diktatfehler'


def test_nicht_geschrieben_tippt_direkt_mit_umbruechen_als_leerzeichen(monkeypatch, ablauf):
    ablauf['ergebnis'] = zw.Ergebnis(geschrieben=False, snapshot=SNAP, grund='unvollstaendig')
    diktat(monkeypatch, 'Erste Zeile\nZweite Zeile\r\n\r\nDritte')
    typefree._verarbeite_audio(sprache(2.0))

    assert ablauf['getippt'] == ['Erste Zeile Zweite Zeile Dritte']
    assert ablauf['hotkeys'] == [], 'kein Strg+V — die Zwischenablage bleibt unangetastet'
    assert not ablauf['zurueck_da'].wait(0.2), 'nichts wiederherzustellen'
    assert ablauf['fehler'] == []


def test_wirft_die_naht_selbst_wird_direkt_getippt(monkeypatch, ablauf):
    def platzt(text):
        raise OSError('Win32 weg')
    monkeypatch.setattr(typefree, 'zwischenablage_einfuegen', platzt)
    diktat(monkeypatch, 'Hallo Welt')
    typefree._verarbeite_audio(sprache(2.0))

    assert ablauf['getippt'] == ['Hallo Welt'] and ablauf['hotkeys'] == []


def test_schalter_aus_stellt_nichts_wieder_her(monkeypatch, ablauf):
    monkeypatch.setattr(typefree, 'zwischenablage_zurueck_an', False)
    diktat(monkeypatch, 'Hallo')
    typefree._verarbeite_audio(sprache(2.0))

    assert ablauf['hotkeys'] == [('ctrl', 'v')]
    assert not ablauf['zurueck_da'].wait(0.2)
    assert ablauf['zurueck'] == []


def test_letztes_diktat_ist_vor_dem_einfuegeversuch_gesetzt(monkeypatch, ablauf):
    gesehen = []

    def einfuegen(text):
        gesehen.append(typefree.letztes_diktat)
        raise RuntimeError('Einfügen kaputt')
    monkeypatch.setattr(typefree, 'zwischenablage_einfuegen', einfuegen)

    def tippen(text):
        gesehen.append(typefree.letztes_diktat)
        raise RuntimeError('Tippen auch kaputt')
    monkeypatch.setattr(typefree, 'unicode_tippen', tippen)
    diktat(monkeypatch, 'Wichtiges Diktat')
    typefree._verarbeite_audio(sprache(2.0))

    assert gesehen == ['Wichtiges Diktat', 'Wichtiges Diktat']
    assert typefree.letztes_diktat == 'Wichtiges Diktat', 'nie still verloren'
    assert len(ablauf['fehler']) == 1, 'der bestehende Fehlerweg meldet'
    assert typefree.retry_bereit(), 'die Aufnahme bleibt für „erneut versuchen"'
    assert typefree.diktat_kopierbar()


def test_erfolg_bucht_wie_vorher_und_verwirft_die_aufnahme(monkeypatch, ablauf):
    gebucht = []
    monkeypatch.setattr(typefree, 'verbrauch_buchen',
                        lambda v, sek, monat, anbieter=None, **k: gebucht.append(anbieter) or v)
    typefree.aufnahme_merken(sprache(1), 'alt')
    diktat(monkeypatch, 'Hallo')
    typefree._verarbeite_audio(sprache(2.0))

    assert gebucht == ['mai'] and not typefree.retry_bereit()


def test_verworfenes_diktat_beruehrt_die_zwischenablage_nicht(monkeypatch, ablauf):
    diktat(monkeypatch, 'Untertitel im Auftrag des ZDF, 2021.')
    typefree._verarbeite_audio(sprache(3.0))

    assert ablauf['eingefuegt'] == [] and ablauf['getippt'] == []
    assert ablauf['hotkeys'] == [] and typefree.letztes_diktat is None


def test_danke_auf_stille_beruehrt_die_zwischenablage_nicht(monkeypatch, ablauf):
    diktat(monkeypatch, 'Danke.')
    typefree._verarbeite_audio(stille(2.0))

    assert ablauf['eingefuegt'] == [] and ablauf['getippt'] == []
    assert typefree.letztes_diktat is None


def test_mindestdauer_beruehrt_die_zwischenablage_nicht(monkeypatch, ablauf):
    diktat(monkeypatch, 'Hallo')
    monkeypatch.setattr(typefree, 'audio_frames', [sprache(0.2).reshape(-1, 1)])
    monkeypatch.setattr(typefree, 'is_recording', True)
    monkeypatch.setattr(typefree, '_live_lief', False)
    monkeypatch.setattr(typefree, '_close_stream', lambda: None)
    monkeypatch.setattr(typefree, '_ton_zurueck_melden', lambda sitzung: None)
    typefree.stop_and_transcribe()

    assert ablauf['eingefuegt'] == [] and ablauf['getippt'] == []
    assert typefree.letztes_diktat is None


# ══ Tray: „Letztes Diktat kopieren" ═════════════════════════════════════════

def test_tray_eintrag_ist_ohne_diktat_inaktiv(monkeypatch, ablauf):
    assert not typefree.diktat_kopierbar()
    typefree._on_diktat_kopieren(None, None)
    assert ablauf['kopiert'] == []


def test_tray_eintrag_kopiert_privat_das_letzte_diktat(monkeypatch, ablauf):
    diktat(monkeypatch, 'Das letzte Diktat')
    typefree._verarbeite_audio(sprache(2.0))
    assert typefree.diktat_kopierbar()

    typefree._on_diktat_kopieren(None, None)
    assert ablauf['kopiert'] == ['Das letzte Diktat']
    assert ablauf['fehler'] == []


def test_tray_eintrag_meldet_fehler_beim_kopieren(monkeypatch, ablauf):
    monkeypatch.setattr(typefree, 'letztes_diktat', 'Text')

    def platzt(text):
        raise OSError('belegt')
    monkeypatch.setattr(typefree, 'zwischenablage_kopieren', platzt)
    typefree._on_diktat_kopieren(None, None)

    assert len(ablauf['fehler']) == 1 and 'Text' not in ablauf['fehler'][0]


# ══ Schalter in der config.json ═════════════════════════════════════════════

def _konfig(tmp_path, monkeypatch):
    pfad = tmp_path / 'config.json'
    monkeypatch.setattr(typefree, 'CONFIG_PATH', str(pfad))
    return pfad


def test_zurueck_schalter_ist_standardmaessig_an(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    assert typefree.load_zwischenablage_zurueck_config() is True


def test_zurueck_schalter_merkt_sich_die_wahl(tmp_path, monkeypatch):
    _konfig(tmp_path, monkeypatch)
    typefree.save_zwischenablage_zurueck_config(False)
    assert typefree.load_zwischenablage_zurueck_config() is False
    typefree.save_zwischenablage_zurueck_config(True)
    assert typefree.load_zwischenablage_zurueck_config() is True


def test_zurueck_schalter_ueberschreibt_andere_einstellungen_nicht(tmp_path, monkeypatch):
    pfad = _konfig(tmp_path, monkeypatch)
    typefree.save_ton_aus_config(False)
    typefree.save_zwischenablage_zurueck_config(False)
    assert typefree.load_ton_aus_config() is False
    assert '"zwischenablage_zurueck": false' in pfad.read_text(encoding='utf-8')


# ══ Schutz der Tests selbst ═════════════════════════════════════════════════

def test_conftest_sperrt_die_echte_zwischenablage():
    with pytest.raises(AssertionError):
        typefree.zwischenablage_einfuegen('x')
    with pytest.raises(AssertionError):
        zw.standard_api()


def test_wirft_strg_v_kommt_der_alte_inhalt_trotzdem_zurueck(monkeypatch, ablauf):
    """Codex R1/4: Scheitert Strg+V, darf das Diktat nicht in der Zwischenablage
    liegen bleiben — die Rückgabe startet trotzdem, der Fehler geht nach oben."""
    def platzt(*a):
        raise OSError('Eingabe blockiert')
    monkeypatch.setattr(typefree.pyautogui, 'hotkey', platzt)
    with pytest.raises(OSError):
        typefree._text_einfuegen('Hallo')
    assert ablauf['zurueck_da'].wait(2), 'Rückgabe wurde nicht gestartet'
    assert ablauf['zurueck'] == [(SNAP, 4711)]


def test_wiederherstellen_toleriert_aufgerundeten_speicherblock():
    """GlobalSize meldet u. U. einen aufgerundeten Block — Füll-Nullen sind kein fremder Inhalt."""
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    api.inhalt = [(f, d + b'\0\0\0\0' if f == CF_UNICODETEXT else d) for f, d in api.inhalt]
    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is True
    assert api.inhalt == list(FREMD)


def test_wiederherstellen_erkennt_laengeren_fremdtext_mit_gleichem_anfang():
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    api.inhalt = [(f, utf16('Diktat und mehr') if f == CF_UNICODETEXT else d) for f, d in api.inhalt]
    assert zw.wiederherstellen(erg.snapshot, erg.nummer, api) is False


# ── Einfügemarke (Codex-Ergebnisprüfung R2) ───────────────────────────────────

def test_jedes_einfuegen_traegt_eine_eigene_zufallsmarke():
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    marke = api.als_dict()[api.ids_der('typeFREE.Einfuegemarke')]
    assert len(marke) == 16 and marke == erg.snapshot.eigene_marke
    zweite = zw.sichern_und_schreiben('Diktat', FakeApi(FREMD)).snapshot.eigene_marke
    assert zweite != marke


def test_letztes_diktat_kopieren_in_der_luecke_wird_nicht_ueberschrieben():
    """Codex R2: „Letztes Diktat kopieren" schreibt denselben Text mit denselben
    Kennzeichen. Geschieht das, bevor typeFREE die Nummer abliest, hält es die
    neue Nummer für die eigene — die Marke verhindert, dass die Rückgabe den
    ausdrücklich neu kopierten Text überschreibt."""
    api = FakeApi(FREMD)
    erg = zw.sichern_und_schreiben('Diktat', api)
    zw.privat_kopieren('Diktat', api)                   # gleicher Text, keine Marke
    assert zw.wiederherstellen(erg.snapshot, api.GetClipboardSequenceNumber(), api) is False
    assert api.als_dict()[CF_UNICODETEXT] == utf16('Diktat')


def test_aelteres_einfuegen_stellt_ueber_ein_neueres_nicht_zurueck():
    api = FakeApi(FREMD)
    alt = zw.sichern_und_schreiben('Diktat', api)
    neu = zw.sichern_und_schreiben('Diktat', api)       # gleicher Text, neue Marke
    assert zw.wiederherstellen(alt.snapshot, api.GetClipboardSequenceNumber(), api) is False
    assert zw.wiederherstellen(neu.snapshot, neu.nummer, api) is True


def test_privat_kopieren_setzt_keine_einfuegemarke():
    api = FakeApi(FREMD)
    zw.privat_kopieren('Text', api)
    assert 'typeFREE.Einfuegemarke' not in api.ids or \
        api.ids_der('typeFREE.Einfuegemarke') not in api.als_dict()



# ── Zwei Diktate kurz hintereinander (Codex-Ergebnisprüfung R3) ───────────────

def test_zweites_diktat_vor_der_rueckgabe_stellt_den_echten_vorinhalt_zurueck():
    """A schreibt, B schreibt, bevor As Rückgabe lief: B fände sonst Diktat A als
    Vorinhalt vor, As Rückgabe entfiele — der echte Vorinhalt wäre weg."""
    api = FakeApi(FREMD)
    a = zw.sichern_und_schreiben('Diktat A', api)
    b = zw.sichern_und_schreiben('Diktat B', api)
    assert zw.wiederherstellen(a.snapshot, a.nummer, api) is False   # Nummer geändert
    assert zw.wiederherstellen(b.snapshot, b.nummer, api) is True
    assert api.inhalt == list(FREMD)


def test_kette_aus_drei_diktaten_reicht_den_vorinhalt_weiter():
    api = FakeApi(FREMD)
    zw.sichern_und_schreiben('A', api)
    zw.sichern_und_schreiben('B', api)
    c = zw.sichern_und_schreiben('C', api)
    assert zw.wiederherstellen(c.snapshot, c.nummer, api) is True
    assert api.inhalt == list(FREMD)


def test_nach_der_rueckgabe_wird_nichts_mehr_geerbt():
    api = FakeApi(FREMD)
    a = zw.sichern_und_schreiben('A', api)
    assert zw.wiederherstellen(a.snapshot, a.nummer, api) is True
    neu = [(CF_UNICODETEXT, utf16('danach kopiert'))]
    api.fremd_kopieren(neu)
    b = zw.sichern_und_schreiben('B', api)
    assert b.snapshot.formate == neu


def test_fremd_kopiert_zwischen_zwei_diktaten_wird_nicht_ueberschrieben_vom_erbe():
    """Liegt As Diktat nicht mehr drin (Nutzer hat kopiert), sichert B den
    neuen Inhalt — nicht den alten Vorinhalt von A."""
    api = FakeApi(FREMD)
    zw.sichern_und_schreiben('A', api)
    neu = [(CF_UNICODETEXT, utf16('vom Nutzer kopiert'))]
    api.fremd_kopieren(neu)
    b = zw.sichern_und_schreiben('B', api)
    assert b.snapshot.formate == neu
    assert zw.wiederherstellen(b.snapshot, b.nummer, api) is True
    assert api.inhalt == neu



def test_belegte_rueckgabe_vergisst_den_vorinhalt_nicht():
    """Codex R4: Ist die Zwischenablage bei As Rückgabe belegt, darf die
    Sicherung nicht verloren gehen — ein folgendes B erbt sie noch."""
    api = FakeApi(FREMD)
    a = zw.sichern_und_schreiben('A', api)
    api.belegt = 10
    assert zw.wiederherstellen(a.snapshot, a.nummer, api) is False
    b = zw.sichern_und_schreiben('B', api)
    assert b.snapshot.grund == 'geerbt'
    assert zw.wiederherstellen(b.snapshot, b.nummer, api) is True
    assert api.inhalt == list(FREMD)


def test_erfolgreiche_rueckgabe_vergisst_den_vorinhalt():
    api = FakeApi(FREMD)
    a = zw.sichern_und_schreiben('A', api)
    assert zw.wiederherstellen(a.snapshot, a.nummer, api) is True
    assert zw._offen is None



# ── Schreibfehler beim Zurückstellen (Codex-Ergebnisprüfung R5) ───────────────

def test_einmaliger_schreibfehler_beim_zurueckstellen_wird_wiederholt():
    api = FakeApi(FREMD)
    a = zw.sichern_und_schreiben('A', api)
    api.setzfehler = {CF_UNICODETEXT: 1}
    assert zw.wiederherstellen(a.snapshot, a.nummer, api) is True
    assert api.inhalt == list(FREMD)


def test_doppelter_schreibfehler_legt_das_diktat_zurueck_und_b_erbt():
    """Scheitert das Zurückstellen zweimal, liegt danach wieder Diktat A samt
    Marke drin — die Sicherung bleibt gemerkt, B erbt den echten Vorinhalt."""
    api = FakeApi(FREMD)
    a = zw.sichern_und_schreiben('A', api)
    api.setzfehler = {CF_UNICODETEXT: 2}
    assert zw.wiederherstellen(a.snapshot, a.nummer, api) is False
    assert api.als_dict()[CF_UNICODETEXT] == utf16('A')
    assert api.als_dict()[api.ids_der('typeFREE.Einfuegemarke')] == a.snapshot.eigene_marke
    b = zw.sichern_und_schreiben('B', api)
    assert b.snapshot.grund == 'geerbt'
    assert zw.wiederherstellen(b.snapshot, b.nummer, api) is True
    assert api.inhalt == list(FREMD)


def test_rueckschreiben_im_durchgang_wird_einmal_wiederholt():
    """Setzfehler beim Schreiben des Diktats, dann einmal beim Rückschreiben:
    der zweite Rückschreib-Versuch holt den Vorinhalt zurück."""
    api = FakeApi(FREMD, setzfehler={CF_UNICODETEXT: 2})
    erg = zw.sichern_und_schreiben('Text', api)
    assert not erg.geschrieben and erg.grund == 'setzen' and erg.zurueckgeschrieben
    assert api.inhalt == list(FREMD)
