"""Ton aus während der Aufnahme: Musik und Podcasts schweigen, solange diktiert wird.

Beim Start einer Aufnahme wird das Standard-Wiedergabegerät stummgeschaltet, mit
dem Ende der Aufnahme sofort wieder eingeschaltet — und zwar genau das Gerät,
das typeFREE stummgeschaltet hat. War es schon stumm, fasst typeFREE nichts an.
Das Mikrofon bleibt unberührt, und es verlässt nichts den Rechner.

Aufbau:
  * `TonSperre` ist reine Logik. Das Backend (Lautsprecher-Zugriff) wird von
    außen gereicht — Tests geben ein Fake, die App das Windows-Backend.
  * Alle Backend-Aufrufe laufen in EINEM eigenen Arbeitsfaden, der eine
    Warteschlange abarbeitet. Gründe: Der Tastatur-Haken, aus dem die Aufnahme
    startet, darf nicht auf COM warten (Windows wirft Low-Level-Haken bei
    Zeitüberschreitung raus); `zurueck` darf nie vor `aus` laufen, auch wenn die
    Aufnahme nur Millisekunden dauert; und COM muss pro Faden initialisiert
    werden — das geschieht hier genau einmal.
  * Das Modul importiert beim Laden weder `pycaw` noch `comtypes`.
"""
import json
import logging
import os
import queue
import threading

log = logging.getLogger('typefree')


class TonSperre:
    """Schaltet das Standard-Wiedergabegerät für die Dauer einer Aufnahme stumm."""

    def __init__(self, backend_fabrik, merker_pfad):
        """`backend_fabrik()` liefert das Backend (oder None) und läuft im Arbeitsfaden.

        Das Backend braucht `standard_geraet() -> id|None`, `ist_stumm(id) -> bool`
        und `stumm_setzen(id, bool)`; optional `vorbereiten()`, das im Arbeitsfaden
        einmal vor dem ersten Befehl läuft (COM-Einstieg).
        """
        self._fabrik = backend_fabrik
        self._merker_pfad = merker_pfad
        self._schlange = queue.Queue()
        self._faden = None
        self._faden_lock = threading.Lock()
        # Ab hier gehört der Zustand allein dem Arbeitsfaden — kein weiterer Lock nötig.
        self._backend = None
        self._backend_geholt = False
        self._geraet = None      # Kennung des Geräts, das WIR stummgeschaltet haben
        self._besitzer = None    # Sitzung, die zuletzt „aus" gemeldet hat
        # Geräte aus dem Merker eines harten Abbruchs, die sich beim Start nicht
        # entstummen ließen (z. B. getrennt). Sie bleiben im Merker, bis es gelingt.
        self._offen = set()

    # ── Öffentliche Befehle (kehren sofort zurück) ───────────────────────────
    def aus(self, sitzung):
        """Aufnahme `sitzung` beginnt: Ton stumm."""
        self._einreihen(('aus', sitzung))

    def zurueck(self, sitzung):
        """Aufnahme `sitzung` endet: Ton zurück — aber nur, wenn sie der Besitzer ist."""
        self._einreihen(('zurueck', sitzung))

    def zurueck_alles(self):
        """Beenden oder Notfall: Ton zurück, egal welche Sitzung ihn hielt."""
        self._einreihen(('alles',))

    def rueckstand_aufraeumen(self):
        """Beim Start: Ton wiederherstellen, den ein harter Abbruch stumm ließ."""
        self._einreihen(('rueckstand',))

    def warten(self, hoechstens=2.0):
        """Blockiert, bis alles bisher Eingereihte erledigt ist. True = rechtzeitig."""
        with self._faden_lock:
            if self._faden is None:
                return True      # nie etwas eingereiht, nichts zu erledigen
        fertig = threading.Event()
        self._schlange.put(('marke', fertig))
        return fertig.wait(hoechstens)

    # ── Arbeitsfaden ─────────────────────────────────────────────────────────
    def _einreihen(self, befehl):
        with self._faden_lock:
            if self._faden is None:
                self._faden = threading.Thread(target=self._arbeiten,
                                               name='ton-aus', daemon=True)
                self._faden.start()
        self._schlange.put(befehl)

    def _arbeiten(self):
        # Läuft bis zum Prozessende (Daemon-Faden); COM wird mit dem Prozess frei.
        while True:
            befehl = self._schlange.get()
            try:
                self._ausfuehren(befehl)
            except Exception:
                # Ein Fehler beim Ton darf nie das Diktat oder diesen Faden treffen.
                log.exception('Ton-aus: Befehl %s fehlgeschlagen', befehl[0])

    def _ausfuehren(self, befehl):
        art = befehl[0]
        if art == 'marke':
            befehl[1].set()
            return
        backend = self._backend_holen()
        if backend is None:
            return
        if art == 'aus':
            self._aus(backend, befehl[1])
        elif art == 'zurueck':
            self._zurueck(backend, befehl[1])
        elif art == 'alles':
            self._alles_freigeben(backend)
        elif art == 'rueckstand':
            self._rueckstand(backend)

    def _backend_holen(self):
        """Baut das Backend beim ersten Befehl — im Arbeitsfaden, mit COM-Einstieg."""
        if self._backend_geholt:
            return self._backend
        self._backend_geholt = True
        try:
            self._backend = self._fabrik()
            vorbereiten = getattr(self._backend, 'vorbereiten', None)
            if self._backend is not None and vorbereiten:
                vorbereiten()
        except Exception:
            log.warning('Ton-aus nicht verfügbar — Diktat läuft ohne Stummschaltung',
                        exc_info=True)
            self._backend = None
        if self._backend is None:
            log.warning('Ton-aus: kein Audio-Backend — Stummschaltung wird übersprungen')
        return self._backend

    # ── Logik (nur im Arbeitsfaden) ──────────────────────────────────────────
    def _aus(self, backend, sitzung):
        if self._geraet is not None:
            # Wir halten den Ton schon stumm (überlappende Aufnahme): nicht noch
            # einmal schalten, nur den Besitz übernehmen. Sonst würde das Zurück der
            # älteren Aufnahme den Ton mitten unter der neueren einschalten.
            self._besitzer = sitzung
            return
        try:
            geraet = backend.standard_geraet()
            if geraet is None:
                log.warning('Ton-aus: kein Standard-Wiedergabegerät gefunden')
                return
            stumm = backend.ist_stumm(geraet)
            if geraet in self._offen:
                self._offen.discard(geraet)
                if stumm:
                    # Rückstand, jetzt wieder erreichbar und noch stumm: diese
                    # Stummschaltung stammt von uns — mit dem Aufnahmeende zurückstellen.
                    self._geraet = geraet
                    self._besitzer = sitzung
                    log.info('Ton-aus: Gerät aus einem Abbruch übernommen (Sitzung %s)',
                             sitzung)
                    return
                # Inzwischen von Hand wieder laut: Rückstand erledigt, normal weiter.
            if stumm:
                log.info('Ton-aus: Gerät war schon stumm — nichts zu tun')
                return
        except Exception:
            log.warning('Ton-aus: Stummschalten fehlgeschlagen', exc_info=True)
            return
        # Erst den Merker, dann der Ton: Ohne gesicherten Merker würde ein harter
        # Abbruch den Ton für immer stumm lassen — dann lieber gar nicht schalten.
        if not self._merker_schreiben(self._offen | {geraet}):
            log.warning('Ton-aus: Merker nicht schreibbar — Ton bleibt an')
            return
        try:
            backend.stumm_setzen(geraet, True)
        except Exception:
            log.warning('Ton-aus: Stummschalten fehlgeschlagen', exc_info=True)
            self._merker_aktualisieren()
            return
        self._geraet = geraet
        self._besitzer = sitzung
        log.info('Ton aus für die Aufnahme (Sitzung %s)', sitzung)

    def _zurueck(self, backend, sitzung):
        if self._geraet is None:
            return
        if sitzung != self._besitzer:
            log.info('Ton-aus: Sitzung %s ist nicht mehr Besitzerin — Ton bleibt '
                     'aus für Sitzung %s', sitzung, self._besitzer)
            return
        self._freigeben(backend)

    def _freigeben(self, backend):
        """Stellt GENAU das Gerät zurück, das wir stummgeschaltet haben."""
        if self._geraet is None:
            return
        try:
            backend.stumm_setzen(self._geraet, False)
            log.info('Ton wieder an')
        except Exception:
            # Z. B. Kopfhörer während des Diktats getrennt: als offenen Rückstand
            # führen (Merker bleibt) — und die nächste Aufnahme auf einem anderen
            # Gerät nicht blockieren. Beenden, nächster Start oder das nächste
            # Diktat auf diesem Gerät holen es nach.
            log.warning('Ton-aus: Zurückstellen fehlgeschlagen — Merker bleibt',
                        exc_info=True)
            self._offen.add(self._geraet)
        self._geraet = None
        self._besitzer = None
        self._merker_aktualisieren()

    def _alles_freigeben(self, backend):
        """Beenden: das laufende Gerät und alle offenen Rückstände zurückstellen."""
        self._freigeben(backend)
        for geraet in sorted(self._offen):
            try:
                backend.stumm_setzen(geraet, False)
                self._offen.discard(geraet)
                log.info('Ton-aus: offener Rückstand behoben — Ton wieder an')
            except Exception:
                log.warning('Ton-aus: offener Rückstand weiter nicht erreichbar',
                            exc_info=True)
        self._merker_aktualisieren()

    def _rueckstand(self, backend):
        """Merker aus einem harten Abbruch (z. B. EXE-Tausch mitten im Diktat) abarbeiten."""
        if self._geraet is not None or not os.path.exists(self._merker_pfad):
            return
        geraete = []
        try:
            with open(self._merker_pfad, 'r', encoding='utf-8') as f:
                inhalt = json.load(f)
            geraete = inhalt.get('geraete') or []
            if inhalt.get('geraet'):          # Format der ersten Fassung
                geraete = geraete + [inhalt['geraet']]
        except Exception:
            log.warning('Ton-aus: Merker unlesbar — wird entfernt', exc_info=True)
        for geraet in geraete:
            try:
                backend.stumm_setzen(geraet, False)
                log.info('Ton-aus: Rückstand eines Abbruchs behoben — Ton wieder an')
            except Exception:
                # Z. B. Kopfhörer getrennt: im Merker lassen, beim nächsten Start
                # oder wenn das Gerät wieder Standard ist, erneut versuchen.
                log.warning('Ton-aus: Rückstand konnte nicht behoben werden — '
                            'Merker bleibt', exc_info=True)
                self._offen.add(geraet)
        self._merker_aktualisieren()

    # ── Merker-Datei ─────────────────────────────────────────────────────────
    def _merker_schreiben(self, geraete):
        """Schreibt alle von uns stumm gehaltenen Geräte. True = gesichert.

        Erst in eine Zwischendatei, dann per `os.replace` ausgetauscht: Ein
        Schreibfehler oder Abbruch mittendrin lässt den bisherigen Merker heil.
        """
        zwischen = self._merker_pfad + '.neu'
        try:
            with open(zwischen, 'w', encoding='utf-8') as f:
                json.dump({'geraete': sorted(geraete)}, f)
            os.replace(zwischen, self._merker_pfad)
            return True
        except Exception:
            log.warning('Ton-aus: Merker konnte nicht geschrieben werden', exc_info=True)
            try:
                os.remove(zwischen)
            except OSError:
                pass
            return False

    def _merker_aktualisieren(self):
        """Merker auf den aktuellen Stand: offene Rückstände plus das laufende Gerät."""
        geraete = set(self._offen)
        if self._geraet is not None:
            geraete.add(self._geraet)
        if geraete:
            self._merker_schreiben(geraete)
        else:
            self._merker_loeschen()

    def _merker_loeschen(self):
        try:
            os.remove(self._merker_pfad)
        except FileNotFoundError:
            pass
        except Exception:
            log.warning('Ton-aus: Merker konnte nicht gelöscht werden', exc_info=True)


class WindowsBackend:
    """Windows-Lautsprecher über pycaw/WASAPI — wird nur im Arbeitsfaden benutzt."""

    def __init__(self):
        # Faul importieren: Das Modul bleibt in jeder Umgebung importierbar, und
        # der teure Import (~1 s) trifft den Arbeitsfaden statt den Programmstart.
        import comtypes
        from pycaw.api.endpointvolume import IAudioEndpointVolume
        from pycaw.utils import AudioUtilities, EDataFlow, ERole
        self._comtypes = comtypes
        self._schnittstelle = IAudioEndpointVolume
        self._werkzeuge = AudioUtilities
        self._wiedergabe = EDataFlow.eRender.value
        self._rolle = ERole.eMultimedia.value

    def vorbereiten(self):
        """COM gilt pro Faden — einmal im Arbeitsfaden, nicht im Aufrufer."""
        self._comtypes.CoInitialize()

    def standard_geraet(self):
        # Direkt über den Enumerator statt `GetSpeakers()`: Letzteres liest den
        # ganzen Eigenschaftenspeicher des Geräts (~0,3 s), nur die Kennung genügt.
        aufzaehler = self._werkzeuge.GetDeviceEnumerator()
        geraet = aufzaehler.GetDefaultAudioEndpoint(self._wiedergabe, self._rolle)
        return geraet.GetId() if geraet is not None else None

    def _lautstaerke(self, geraet_id):
        # Per Kennung statt „aktuelles Standardgerät": zurückgestellt wird das
        # Gerät, das wir stummgeschaltet haben, auch wenn inzwischen ein anderes
        # Standard ist.
        geraet = self._werkzeuge.GetDeviceEnumerator().GetDevice(geraet_id)
        schnittstelle = geraet.Activate(self._schnittstelle._iid_,
                                        self._comtypes.CLSCTX_ALL, None)
        return schnittstelle.QueryInterface(self._schnittstelle)

    def ist_stumm(self, geraet_id):
        return bool(self._lautstaerke(geraet_id).GetMute())

    def stumm_setzen(self, geraet_id, stumm):
        self._lautstaerke(geraet_id).SetMute(bool(stumm), None)


def windows_backend():
    """Fabrik für `TonSperre`: das Windows-Backend, oder None wenn pycaw fehlt."""
    try:
        return WindowsBackend()
    except Exception:
        log.warning('Ton-aus: pycaw/comtypes nicht ladbar', exc_info=True)
        return None
