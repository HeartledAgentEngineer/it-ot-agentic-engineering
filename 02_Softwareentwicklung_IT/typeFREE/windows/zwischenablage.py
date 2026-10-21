"""Zwischenablage schützen und wiederherstellen (Scheibe 2, 20.10.2026).

Idee nach cmagnussen/blitztext-app, `ClipboardPasteService.swift` (MIT) — hier
nur die Idee, die Umsetzung ist Win32 über `ctypes`.

Ziel: Ein Diktat landet weder im Win+V-Verlauf noch in der Cloud-Zwischenablage,
und was vorher kopiert war, kommt nach dem Einfügen zurück.

- `sichern_und_schreiben` sichert den Inhalt UND schreibt das Diktat in EINEM
  `OpenClipboard`-Durchgang. Solange die Zwischenablage offen ist, kann keine
  andere App dazwischen kopieren — die Sicherung ist damit garantiert der Stand
  unmittelbar vor dem Leeren. Ist sie nicht vollständig möglich (Grafik nur als
  GDI-Handle, Lesefehler, > 32 MB), wird NICHTS verändert und „nicht geschrieben"
  gemeldet; der Aufrufer tippt dann direkt (kein Rückfall auf eine Variante, die
  den Schutz aufhebt).
- `wiederherstellen` stellt den Inhalt nur zurück, wenn die Sequenznummer noch
  unsere ist — hat inzwischen jemand anders kopiert, bleibt dessen Inhalt.
- `privat_kopieren` schreibt Text mit den Privat-Formaten ohne Wiederherstellung
  (Tray: „Letztes Diktat kopieren").

Alle Win32-Aufrufe laufen über eine austauschbare API-Schicht (`api=`). Die echte
ctypes-Anbindung (`_WindowsApi`) wird nur über `standard_api()` geladen, nie beim
Import; Tests reichen eine Fake-API mit Zustand hinein und berühren die echte
Zwischenablage nie. Neue Logzeilen enthalten keinen Diktattext.
"""
import ctypes
import logging
import os
import threading
import time
from dataclasses import dataclass, field

log = logging.getLogger('typefree')

# ── Zwischenablage-Formate (winuser.h) ───────────────────────────────────────
CF_TEXT = 1
CF_BITMAP = 2
CF_METAFILEPICT = 3
CF_OEMTEXT = 7
CF_DIB = 8
CF_PALETTE = 9
CF_UNICODETEXT = 13
CF_ENHMETAFILE = 14
CF_LOCALE = 16
CF_DIBV5 = 17
CF_OWNERDISPLAY = 0x80
CF_DSPBITMAP = 0x82
CF_DSPMETAFILEPICT = 0x83
CF_DSPENHMETAFILE = 0x8E

# Formate, deren Handle KEIN Speicherblock (HGLOBAL) ist: GDI-Objekte und die
# Anzeige-Varianten. Sie lassen sich nicht als Bytes kopieren.
GDI_FORMATE = frozenset({
    CF_BITMAP, CF_METAFILEPICT, CF_PALETTE, CF_ENHMETAFILE, CF_OWNERDISPLAY,
    CF_DSPBITMAP, CF_DSPMETAFILEPICT, CF_DSPENHMETAFILE,
})
# Ganze Bereiche ohne Speicherblock-Garantie: CF_PRIVATEFIRST..LAST (0x200–0x2FF,
# der Handle ist anwendungsdefiniert) und CF_GDIOBJFIRST..LAST (0x300–0x3FF).
# Vorsichtshalber wie GDI behandelt: nicht kopieren, nicht synthetisierbar.
NICHT_KOPIERBAR_BEREICH = range(0x200, 0x400)

# Von Windows aus einem anderen Format synthetisierte Formate: gelten als
# gesichert, wenn mindestens eine ihrer Quellen gesichert wurde. CF_METAFILEPICT
# <-> CF_ENHMETAFILE zählt NICHT (beides GDI, nichts ist gesichert); ebenso nicht
# die Anzeige-Formate und CF_OWNERDISPLAY.
SYNTHESE_QUELLEN = {
    CF_BITMAP: (CF_DIB, CF_DIBV5),
    CF_PALETTE: (CF_DIB, CF_DIBV5),
}

# Privat-Formate (Microsoft: „Clipboard formats for Windows Clipboard history").
FORMAT_AUSSCHLUSS = 'ExcludeClipboardContentFromMonitorProcessing'   # leerer Block
FORMAT_VERLAUF = 'CanIncludeInClipboardHistory'                      # DWORD 0
FORMAT_CLOUD = 'CanUploadToCloudClipboard'                           # DWORD 0
# Eigenes Format: 16 Zufallsbytes je Einfügen — woran `wiederherstellen` genau
# dieses Einfügen wiedererkennt (nicht bei „Letztes Diktat kopieren").
FORMAT_MARKE = 'typeFREE.Einfuegemarke'
DWORD_NULL = (0).to_bytes(4, 'little')

MAX_GESAMT_BYTES = 32 * 1024 * 1024    # größere Zwischenablagen werden nicht gesichert
OEFFNEN_VERSUCHE = 10
OEFFNEN_PAUSE = 0.02                   # Sekunden zwischen zwei Versuchen


class ZuGross(Exception):
    """Ein Format passt nicht mehr in die 32-MB-Grenze."""


class ZwischenablageFehler(OSError):
    """Die Zwischenablage ließ sich nicht öffnen oder beschreiben."""


@dataclass
class Snapshot:
    """Sicherung der Zwischenablage: (Format, Bytes) in Originalreihenfolge."""
    formate: list = field(default_factory=list)
    vollstaendig: bool = True
    grund: str = ''
    # Was WIR danach geschrieben haben (CF_UNICODETEXT-Bytes). `wiederherstellen`
    # stellt nur zurück, wenn genau das noch drinliegt — die Sequenznummer allein
    # reicht nicht: Windows zählt sie auch beim Schließen hoch, ablesbar ist sie
    # erst danach, und in dieser Lücke könnte jemand anders kopieren (Codex R1/1).
    eigener_text: bytes = None
    eigene_marke: bytes = None      # Zufallsbytes dieses Einfügens (Codex R2)


@dataclass
class Ergebnis:
    """Ausgang von `sichern_und_schreiben`.

    `geschrieben`: Das Diktat liegt privat in der Zwischenablage (Strg+V darf
    folgen). Sonst wurde nichts verändert — oder, bei `grund == 'setzen'`, der
    Inhalt im selben Durchgang zurückgeschrieben (`zurueckgeschrieben`).
    `nummer`: Sequenznummer nach dem Schreiben (nur bei `geschrieben`).
    """
    geschrieben: bool
    snapshot: Snapshot = None
    nummer: int = 0
    grund: str = ''            # '', 'oeffnen', 'unvollstaendig', 'leeren', 'setzen', 'fehler'
    zurueckgeschrieben: bool = False


# ── Echte Win32-Schicht ──────────────────────────────────────────────────────
_GMEM_MOVEABLE = 0x0002
_GMEM_ZEROINIT = 0x0040
_DLLS = None


def _dlls_laden():
    """user32/kernel32 mit eigenen Bindungen (nicht `ctypes.windll`, dessen
    Funktionsobjekte sich der ganze Prozess teilt — typefree nutzt sie für
    SendInput). Auf 64-bit MÜSSEN Handles `c_void_p` sein: ohne argtypes/restype
    schneidet ctypes sie auf 32 Bit ab."""
    global _DLLS
    if _DLLS is not None:
        return _DLLS
    from ctypes import c_int, c_size_t, c_uint, c_ulong, c_void_p, c_wchar_p
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    def binde(dll, name, argtypes, restype):
        funktion = getattr(dll, name)
        funktion.argtypes = argtypes
        funktion.restype = restype

    binde(user32, 'OpenClipboard', [c_void_p], c_int)
    binde(user32, 'CloseClipboard', [], c_int)
    binde(user32, 'EmptyClipboard', [], c_int)
    binde(user32, 'EnumClipboardFormats', [c_uint], c_uint)
    binde(user32, 'GetClipboardData', [c_uint], c_void_p)
    binde(user32, 'SetClipboardData', [c_uint, c_void_p], c_void_p)
    binde(user32, 'RegisterClipboardFormatW', [c_wchar_p], c_uint)
    binde(user32, 'GetClipboardSequenceNumber', [], c_ulong)
    binde(user32, 'CreateWindowExW',
          [c_ulong, c_wchar_p, c_wchar_p, c_ulong, c_int, c_int, c_int, c_int,
           c_void_p, c_void_p, c_void_p, c_void_p], c_void_p)
    binde(user32, 'DestroyWindow', [c_void_p], c_int)
    binde(kernel32, 'GlobalAlloc', [c_uint, c_size_t], c_void_p)
    binde(kernel32, 'GlobalLock', [c_void_p], c_void_p)
    binde(kernel32, 'GlobalUnlock', [c_void_p], c_int)
    binde(kernel32, 'GlobalSize', [c_void_p], c_size_t)
    binde(kernel32, 'GlobalFree', [c_void_p], c_void_p)
    _DLLS = (user32, kernel32)
    return _DLLS


class _WindowsApi:
    """Die echte Anbindung. Eine Instanz gehört zu EINEM Durchgang/Faden.

    Öffnen mit eigenem, unsichtbarem STATIC-Fenster als Besitzer: Mit
    `OpenClipboard(NULL)` wird der Besitzer nach dem Leeren NULL, und
    `SetClipboardData` kann scheitern (Microsoft-Doku zu `EmptyClipboard`).
    Das Fenster entsteht je Öffnen und wird beim Schließen zerstört — ein Fenster
    gehört dem Faden, der es anlegt, und die Diktat-Fäden kommen und gehen.
    Die gesetzten Daten bleiben nach dem Zerstören erhalten (sie liegen im
    Speicher der Zwischenablage, nicht beim Besitzer).
    """

    def __init__(self, user32=None, kernel32=None):
        if user32 is None or kernel32 is None:
            user32, kernel32 = _dlls_laden()
        self._u = user32
        self._k = kernel32
        self._hwnd = None

    def OpenClipboard(self):
        hwnd = self._u.CreateWindowExW(0, 'STATIC', None, 0, 0, 0, 0, 0,
                                       None, None, None, None)
        if not hwnd:
            # Ohne Besitzerfenster könnte nach dem Leeren `SetClipboardData`
            # scheitern — dann wäre auch das Zurückschreiben verloren. Lieber
            # gar nicht öffnen: der Aufrufer tippt direkt (Codex R1/3).
            return False
        if self._u.OpenClipboard(hwnd):
            self._hwnd = hwnd
            return True
        if hwnd:
            self._u.DestroyWindow(hwnd)
        return False

    def CloseClipboard(self):
        ok = self._u.CloseClipboard()
        if self._hwnd:
            self._u.DestroyWindow(self._hwnd)
            self._hwnd = None
        return bool(ok)

    def EmptyClipboard(self):
        return bool(self._u.EmptyClipboard())

    def EnumClipboardFormats(self, vorher):
        """0 heißt Ende ODER Fehler — unterschieden nur über GetLastError
        (Codex R1/2). Ein Fehler wirft, damit die Sicherung unvollständig wird."""
        ctypes.set_last_error(0)
        fmt = int(self._u.EnumClipboardFormats(vorher))
        if fmt == 0 and ctypes.get_last_error() != 0:
            raise OSError('EnumClipboardFormats schlug fehl (Fehler %d)'
                          % ctypes.get_last_error())
        return fmt

    def RegisterClipboardFormat(self, name):
        return int(self._u.RegisterClipboardFormatW(name))

    def GetClipboardSequenceNumber(self):
        return int(self._u.GetClipboardSequenceNumber())

    def lese(self, fmt, limit):
        """Bytes des Formats. Wirft `ZuGross` über `limit`, sonst `OSError`."""
        handle = self._u.GetClipboardData(fmt)
        if not handle:
            raise OSError('GetClipboardData lieferte kein Handle (Format 0x%X)' % fmt)
        ctypes.set_last_error(0)
        groesse = self._k.GlobalSize(handle)
        if groesse == 0 and ctypes.get_last_error() != 0:
            raise OSError('GlobalSize schlug fehl (Format 0x%X)' % fmt)
        if groesse > limit:
            raise ZuGross(fmt)
        if groesse == 0:
            return b''
        zeiger = self._k.GlobalLock(handle)
        if not zeiger:
            raise OSError('GlobalLock schlug fehl (Format 0x%X)' % fmt)
        try:
            return ctypes.string_at(zeiger, groesse)
        finally:
            self._k.GlobalUnlock(handle)

    def setze(self, fmt, daten):
        """Legt `daten` als Speicherblock an und übergibt ihn der Zwischenablage.

        `SetClipboardData` übernimmt den Block nur bei Erfolg; bei Misserfolg
        gehört er weiter uns und wird hier freigegeben (sonst Speicherleck).
        Ein leerer Inhalt bekommt einen 1-Byte-Block (Nullgröße ist ungültig).
        """
        handle = self._k.GlobalAlloc(_GMEM_MOVEABLE | _GMEM_ZEROINIT,
                                     max(len(daten), 1))
        if not handle:
            return False
        zeiger = self._k.GlobalLock(handle)
        if not zeiger:
            self._k.GlobalFree(handle)
            return False
        try:
            if daten:
                ctypes.memmove(zeiger, daten, len(daten))
        finally:
            self._k.GlobalUnlock(handle)
        if not self._u.SetClipboardData(fmt, handle):
            self._k.GlobalFree(handle)
            return False
        return True


def standard_api():
    """Die echte API-Fabrik. Tests ersetzen sie durch einen Werfer (conftest)."""
    return _WindowsApi()


# ── Logik (nur über die API-Schicht) ─────────────────────────────────────────
def _oeffnen(api):
    """Öffnet die Zwischenablage; andere Apps halten sie kurz fest — bis zu
    `OEFFNEN_VERSUCHE` × `OEFFNEN_PAUSE` wiederholen."""
    for versuch in range(OEFFNEN_VERSUCHE):
        if api.OpenClipboard():
            return True
        if versuch < OEFFNEN_VERSUCHE - 1:
            time.sleep(OEFFNEN_PAUSE)
    return False


def _kopierbar(fmt):
    return fmt not in GDI_FORMATE and fmt not in NICHT_KOPIERBAR_BEREICH


def _sichern(api):
    """Liest alle Formate. Muss bei geöffneter Zwischenablage laufen."""
    vorhanden = []
    try:
        fmt = api.EnumClipboardFormats(0)
        while fmt:
            vorhanden.append(fmt)
            fmt = api.EnumClipboardFormats(fmt)
    except Exception:
        # Abgebrochene Aufzählung: eine leere oder halbe Liste darf nie als
        # vollständige Sicherung gelten — sonst würde danach geleert.
        return Snapshot([], False, 'aufzaehlfehler')

    formate, uebersprungen, gesamt = [], [], 0
    for fmt in vorhanden:
        if not _kopierbar(fmt):
            uebersprungen.append(fmt)
            continue
        try:
            daten = api.lese(fmt, MAX_GESAMT_BYTES - gesamt)
        except ZuGross:
            return Snapshot(formate, False, 'zu gross')
        except Exception:
            return Snapshot(formate, False, 'lesefehler')
        gesamt += len(daten)
        formate.append((fmt, daten))

    gesichert = {f for f, _ in formate}
    for fmt in uebersprungen:
        if not gesichert.intersection(SYNTHESE_QUELLEN.get(fmt, ())):
            return Snapshot(formate, False, 'nicht kopierbar: 0x%X' % fmt)
    return Snapshot(formate, True)


def _unicode_text(text):
    return (text + '\0').encode('utf-16-le')


def _privat_formate(api):
    """Registriert die drei Privat-Formate (vor dem Leeren, damit ein Fehler
    hier noch nichts verändert hat)."""
    ids = []
    for name, daten in ((FORMAT_AUSSCHLUSS, b''), (FORMAT_VERLAUF, DWORD_NULL),
                        (FORMAT_CLOUD, DWORD_NULL)):
        nummer = api.RegisterClipboardFormat(name)
        if not nummer:
            raise OSError('RegisterClipboardFormat schlug fehl (%s)' % name)
        ids.append((nummer, daten))
    return ids


def _privat_setzen(api, text_bytes, privat):
    """Text + Privat-Formate setzen (Zwischenablage ist offen und geleert)."""
    if not api.setze(CF_UNICODETEXT, text_bytes):
        return False
    return all(api.setze(nummer, daten) for nummer, daten in privat)


def _zurueckschreiben(api, snapshot):
    """Leert und schreibt alle gesicherten Formate zurück (offen vorausgesetzt).
    Leerer Snapshot → nur leeren. Gibt zurück, ob alles ankam."""
    if not api.EmptyClipboard():
        return False
    ok = True
    for fmt, daten in snapshot.formate:
        if not api.setze(fmt, daten):
            ok = False
    return ok


# Das zuletzt geschriebene, noch nicht zurückgestellte Einfügen: (Marke, Formate
# des ECHTEN Vorinhalts). Folgt ein zweites Diktat, bevor das erste seinen
# Vorinhalt zurückgestellt hat, liegt in der Zwischenablage noch Diktat A — B würde
# A als „Vorinhalt" sichern, As Rückgabe entfiele (Nummer geändert), und B stellte
# A zurück: der echte Vorinhalt wäre weg (Codex R3). Deshalb übernimmt B die
# Sicherung von A, wenn es As Marke vorfindet. Ein Platz genügt: eine Kette
# A → B → C reicht den Vorinhalt weiter.
_offen = None
_offen_lock = threading.Lock()


def _offen_merken(snapshot):
    global _offen
    with _offen_lock:
        _offen = (snapshot.eigene_marke, list(snapshot.formate))


def _offen_vergessen(marke):
    global _offen
    with _offen_lock:
        if _offen is not None and _offen[0] == marke:
            _offen = None


def _geerbter_vorinhalt(api, snapshot):
    """Liegt gerade ein noch offenes typeFREE-Einfügen in der Zwischenablage?
    Dann dessen gesicherten Vorinhalt zurückgeben, sonst None."""
    with _offen_lock:
        offen = _offen
    if offen is None:
        return None
    marke_id = api.RegisterClipboardFormat(FORMAT_MARKE)
    vorgefunden = dict(snapshot.formate).get(marke_id)
    if vorgefunden is None or not _gleich_bis_auf_fuellnullen(vorgefunden, offen[0]):
        return None
    return offen[1]


def _durchgang(api, text):
    """Sichern → (nur wenn vollständig) leeren → privat schreiben, alles in dem
    einen geöffneten Zustand. Rückgabe ohne Sequenznummer (kommt nach dem Close)."""
    snapshot = None
    geleert = False
    try:
        snapshot = _sichern(api)
        if not snapshot.vollstaendig:
            log.info('Zwischenablage nicht vollständig sicherbar (%s) — nichts '
                     'verändert', snapshot.grund)
            return Ergebnis(False, snapshot, grund='unvollstaendig')
        geerbt = _geerbter_vorinhalt(api, snapshot)
        if geerbt is not None:
            log.info('Zwischenablage: voriges Diktat noch drin — übernehme dessen Sicherung')
            snapshot = Snapshot(list(geerbt), True, 'geerbt')
        text_bytes = _unicode_text(text)
        snapshot.eigener_text = text_bytes
        privat = _privat_formate(api)
        snapshot.eigene_marke = os.urandom(16)
        marke = api.RegisterClipboardFormat(FORMAT_MARKE)
        if not marke:
            raise OSError('RegisterClipboardFormat schlug fehl (%s)' % FORMAT_MARKE)
        privat.append((marke, snapshot.eigene_marke))
        if not api.EmptyClipboard():
            return Ergebnis(False, snapshot, grund='leeren')
        geleert = True
        if _privat_setzen(api, text_bytes, privat):
            _offen_merken(snapshot)
            return Ergebnis(True, snapshot)
        grund = 'setzen'
    except Exception as e:
        log.warning('Zwischenablage: unerwarteter Fehler (%s)', type(e).__name__)
        grund = 'fehler'
        if not geleert:
            return Ergebnis(False, snapshot, grund=grund)
    # Nach dem Leeren gescheitert: im selben Durchgang den Inhalt zurückholen.
    zurueck = False
    for _ in range(2):          # ein zweiter Versuch, bevor der Vorinhalt verloren ist
        try:
            zurueck = _zurueckschreiben(api, snapshot)
        except Exception:
            zurueck = False
        if zurueck:
            break
    log.warning('Zwischenablage: Schreiben scheiterte (%s), Inhalt %s', grund,
                'zurückgeschrieben' if zurueck else 'NICHT vollständig zurückgeschrieben')
    return Ergebnis(False, snapshot, grund=grund, zurueckgeschrieben=zurueck)


def sichern_und_schreiben(text, api=None):
    """Sichert die Zwischenablage und schreibt `text` privat hinein — ein Durchgang.

    Gibt ein `Ergebnis` zurück; `geschrieben` ist nur wahr, wenn der Inhalt
    vollständig gesichert und das Diktat samt Privat-Formaten gesetzt ist. In
    jedem anderen Fall liegt das Diktat NICHT in der Zwischenablage (der Aufrufer
    tippt direkt) und der Vorinhalt ist unverändert bzw. zurückgeschrieben.
    """
    api = api or standard_api()
    if not _oeffnen(api):
        log.info('Zwischenablage nicht zu öffnen — nichts verändert')
        return Ergebnis(False, grund='oeffnen')
    try:
        ergebnis = _durchgang(api, text)
    finally:
        try:
            api.CloseClipboard()
        except Exception:
            log.warning('Zwischenablage: Schließen schlug fehl')
    if ergebnis.geschrieben:
        ergebnis.nummer = api.GetClipboardSequenceNumber()
    return ergebnis


def _gleich_bis_auf_fuellnullen(daten, erwartet):
    """GlobalSize darf einen aufgerundeten Block melden: Füll-Nullen am Ende zulassen."""
    return (daten[:len(erwartet)] == erwartet
            and not daten[len(erwartet):].strip(b'\0'))


def _noch_unser_diktat(api, snapshot):
    """Liegt genau DIESES Einfügen noch in der (geöffneten) Zwischenablage?

    Entscheidend ist die Einfügemarke — 16 Zufallsbytes je `sichern_und_schreiben`.
    Text und Ausschluss-Kennzeichen allein reichen nicht: „Letztes Diktat
    kopieren" schreibt denselben Text mit denselben Kennzeichen, und das wäre
    ausdrücklich neu kopiert (Codex R2). Ohne Marke oder Text: nein (lieber
    nicht zurückstellen)."""
    if not snapshot.eigener_text or not snapshot.eigene_marke:
        return False
    try:
        vorhanden = set()
        fmt = api.EnumClipboardFormats(0)
        while fmt:
            vorhanden.add(fmt)
            fmt = api.EnumClipboardFormats(fmt)
        marke = api.RegisterClipboardFormat(FORMAT_MARKE)
        if CF_UNICODETEXT not in vorhanden or marke not in vorhanden:
            return False
        if not _gleich_bis_auf_fuellnullen(
                api.lese(marke, len(snapshot.eigene_marke) + 64), snapshot.eigene_marke):
            return False
        return _gleich_bis_auf_fuellnullen(
            api.lese(CF_UNICODETEXT, len(snapshot.eigener_text) + 64),
            snapshot.eigener_text)
    except Exception:
        return False


def _eigenes_zuruecklegen(api, snapshot):
    """Leert und legt das eigene Diktat mit Privat-Formaten und Marke zurück
    (Zwischenablage offen). Gibt zurück, ob alles ankam."""
    try:
        privat = _privat_formate(api)
        marke = api.RegisterClipboardFormat(FORMAT_MARKE)
        if not marke:
            return False
        privat.append((marke, snapshot.eigene_marke))
        if not api.EmptyClipboard():
            return False
        return _privat_setzen(api, snapshot.eigener_text, privat)
    except Exception:
        return False


def wiederherstellen(snapshot, eigene_nummer, api=None):
    """Stellt den gesicherten Inhalt zurück — aber nur, wenn die Zwischenablage
    noch genau unser Diktat enthält (Sequenznummer unverändert). Hat inzwischen
    jemand anders kopiert, bleibt dessen Inhalt. Gibt zurück, ob zurückgestellt wurde.

    Die Nummer wird nach dem Öffnen noch einmal geprüft: ab dann ist die
    Zwischenablage für andere gesperrt, zwischen Prüfung und Leeren kann nichts
    mehr dazwischenkommen.
    """
    zurueck = _wiederherstellen(snapshot, eigene_nummer, api)
    # Vergessen nur nach erfolgreicher Rückgabe. Scheitert sie (Zwischenablage
    # belegt, Fehler), bleibt der echte Vorinhalt gemerkt: ein folgendes Diktat
    # erbt ihn, falls dieses Diktat dann noch drinliegt — geerbt wird ohnehin nur
    # bei vorgefundener Marke (Codex R4).
    if zurueck:
        _offen_vergessen(snapshot.eigene_marke)
    return zurueck


def _wiederherstellen(snapshot, eigene_nummer, api):
    if snapshot is None or not snapshot.vollstaendig:
        return False
    api = api or standard_api()
    if api.GetClipboardSequenceNumber() != eigene_nummer:
        return False
    if not _oeffnen(api):
        log.info('Zwischenablage nicht zu öffnen — Inhalt bleibt unverändert')
        return False
    try:
        if api.GetClipboardSequenceNumber() != eigene_nummer:
            return False
        if not _noch_unser_diktat(api, snapshot):
            log.info('Zwischenablage enthält nicht mehr das Diktat — bleibt unverändert')
            return False
        if _zurueckschreiben(api, snapshot) or _zurueckschreiben(api, snapshot):
            return True
        # Zweimal gescheitert: Das Diktat samt Marke wieder hineinlegen. Dann gilt
        # weiter „dieses Einfügen ist offen" — die Sicherung bleibt gemerkt, und
        # ein folgendes Diktat erbt den echten Vorinhalt (Codex R5).
        gelegt = _eigenes_zuruecklegen(api, snapshot)
        log.warning('Zwischenablage: Zurückstellen scheiterte zweimal — Diktat %s',
                    'wieder hineingelegt' if gelegt else 'NICHT wieder hineingelegt')
        return False
    finally:
        try:
            api.CloseClipboard()
        except Exception:
            log.warning('Zwischenablage: Schließen schlug fehl')


def privat_kopieren(text, api=None):
    """Schreibt `text` privat (ohne Verlauf/Cloud) in die Zwischenablage, ohne
    den Vorinhalt zu sichern — für „Letztes Diktat kopieren". Wirft
    `ZwischenablageFehler`, wenn es nicht klappt."""
    api = api or standard_api()
    if not _oeffnen(api):
        raise ZwischenablageFehler('Die Zwischenablage ist gerade von einer anderen '
                                   'Anwendung belegt.')
    try:
        text_bytes = _unicode_text(text)
        privat = _privat_formate(api)
        if not api.EmptyClipboard():
            raise ZwischenablageFehler('Die Zwischenablage ließ sich nicht leeren.')
        if not _privat_setzen(api, text_bytes, privat):
            raise ZwischenablageFehler('Der Text ließ sich nicht in die '
                                       'Zwischenablage schreiben.')
    finally:
        try:
            api.CloseClipboard()
        except Exception:
            log.warning('Zwischenablage: Schließen schlug fehl')
    return True
