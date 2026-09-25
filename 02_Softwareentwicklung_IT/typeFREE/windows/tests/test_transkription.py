"""Die Transkription läuft über eine Anbieterkette, die Glättung über eine Modellkette.

Anlass (25.09.2026): Der OpenAI-Schlüssel ist ohne Guthaben, jeder Aufruf
scheiterte — das Diktat lief über OpenRouter und brauchte ein Vielfaches der
Zeit. Und die Glättung stand wochenlang auf einem abgekündigten Modell, jede
Anfrage endete im 404, der Filter war damit faktisch aus. Beides darf nicht
wieder unbemerkt passieren: Die Kette fängt einen toten Anbieter auf, und ein
Ausfall der Glättung wird gemeldet.
"""
import io
import types

import pytest
import typefree

ROHTEXT = (
    'Also ähm ich wollte gucken ob die zweite Prüfung jetzt durchläuft und '
    'wenn ja dann können wir den nächsten Slice angehen also den mit dem '
    'Autostart und der Aufgabenplanung.'
)
BEREINIGT = (
    'Ich wollte gucken, ob die zweite Prüfung jetzt durchläuft, und wenn ja, '
    'dann können wir den nächsten Slice angehen, den mit dem Autostart und '
    'der Aufgabenplanung.'
)


class TranskriptionsAttrappe:
    """Nachbau eines OpenAI-kompatiblen Clients, so weit transcribe_audio ihn nutzt."""

    def __init__(self, text=None, fehler=None):
        self.aufrufe = []
        self.puffer_positionen = []
        self._text = text
        self._fehler = fehler

        def create(**kwargs):
            self.aufrufe.append(kwargs)
            # Steht der Puffer nicht am Anfang, schickt der Upload eine leere Datei.
            self.puffer_positionen.append(kwargs['file'].tell())
            if self._fehler:
                raise self._fehler
            return types.SimpleNamespace(text=self._text)

        self.audio = types.SimpleNamespace(
            transcriptions=types.SimpleNamespace(create=create))


class GlattungsAttrappe:
    """Nachbau des OpenRouter-Clients, so weit polish_text ihn nutzt."""

    def __init__(self, antwort=None, fehler=None):
        self.aufrufe = []
        self._antwort = antwort
        self._fehler = fehler

        def create(**kwargs):
            self.aufrufe.append(kwargs)
            if self._fehler:
                raise self._fehler
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(
                    message=types.SimpleNamespace(content=self._antwort))])

        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create))


def puffer():
    """Ein Puffer, wie stop_and_transcribe ihn übergibt."""
    p = io.BytesIO(b'RIFF....WAV-Daten')
    p.name = 'audio.wav'
    return p


# ── Anbieterkette ─────────────────────────────────────────────────────────────

def test_kette_beginnt_bei_groq():
    """Groq war im Messlauf der schnellste Anbieter (0,7 s gegen 1,8 s)."""
    assert typefree.TRANSCRIPTION_KETTE[0][0] == 'groq'


def test_jeder_anbieter_hat_modell_und_adresse():
    for name, modell, adresse in typefree.TRANSCRIPTION_KETTE:
        assert modell and adresse.startswith('https://')


def test_preise_decken_die_ganze_kette():
    for name, _, _ in typefree.TRANSCRIPTION_KETTE:
        assert name in typefree.PREISE_JE_MINUTE


def test_groq_ist_billiger_als_openai():
    """0,111 $/Stunde gegen 0,006 $/Minute — der Regelfall ist der günstige."""
    assert typefree.PREISE_JE_MINUTE['groq'] < typefree.PREISE_JE_MINUTE['openai']


def test_verfuegbare_anbieter_haelt_die_kettenreihenfolge():
    umgebung = {'OPENROUTER_API_KEY': 'x', 'GROQ_API_KEY': 'y'}
    assert typefree.verfuegbare_anbieter(umgebung) == ('groq', 'openrouter')


def test_verfuegbare_anbieter_ignoriert_leere_schluessel():
    umgebung = {'GROQ_API_KEY': '', 'OPENROUTER_API_KEY': 'y'}
    assert typefree.verfuegbare_anbieter(umgebung) == ('openrouter',)


def test_ohne_jeden_schluessel_gibt_es_keine_anbieter():
    assert typefree.verfuegbare_anbieter({}) == ()


def test_baue_client_ohne_schluessel_gibt_none():
    """Ohne Schlüssel darf kein Client entstehen — OpenAI() würde werfen."""
    assert typefree.baue_client('https://api.groq.com/openai/v1', '') is None
    assert typefree.baue_client('https://api.groq.com/openai/v1', None) is None


# ── Transkription über die Kette ──────────────────────────────────────────────

def test_erster_anbieter_wird_genommen_wenn_er_liefert():
    groq = TranskriptionsAttrappe(text='  Hallo Welt  ')
    openrouter = TranskriptionsAttrappe(text='sollte nicht benutzt werden')
    text, anbieter = typefree.transcribe_audio(
        puffer(), {'groq': groq, 'openrouter': openrouter})
    assert (text, anbieter) == ('Hallo Welt', 'groq')
    assert len(openrouter.aufrufe) == 0


def test_toter_anbieter_faellt_aus_ohne_das_diktat_zu_kosten():
    groq = TranskriptionsAttrappe(fehler=RuntimeError('401 Konto ohne Guthaben'))
    openrouter = TranskriptionsAttrappe(text='Text vom Ausweichweg')
    text, anbieter = typefree.transcribe_audio(
        puffer(), {'groq': groq, 'openrouter': openrouter})
    assert (text, anbieter) == ('Text vom Ausweichweg', 'openrouter')


def test_puffer_steht_vor_jedem_versuch_wieder_am_anfang():
    """Nach einem Fehlversuch steht der Dateizeiger am Ende — sonst leere Datei."""
    groq = TranskriptionsAttrappe(fehler=RuntimeError('500'))
    openrouter = TranskriptionsAttrappe(text='ok')
    typefree.transcribe_audio(puffer(), {'groq': groq, 'openrouter': openrouter})
    assert groq.puffer_positionen == [0]
    assert openrouter.puffer_positionen == [0]


def test_anbieter_ohne_client_wird_uebersprungen():
    openrouter = TranskriptionsAttrappe(text='nur OpenRouter da')
    text, anbieter = typefree.transcribe_audio(
        puffer(), {'groq': None, 'openrouter': openrouter})
    assert (text, anbieter) == ('nur OpenRouter da', 'openrouter')


def test_leere_antwort_gilt_als_fehlschlag():
    groq = TranskriptionsAttrappe(text='   ')
    openrouter = TranskriptionsAttrappe(text='richtiger Text')
    text, anbieter = typefree.transcribe_audio(
        puffer(), {'groq': groq, 'openrouter': openrouter})
    assert (text, anbieter) == ('richtiger Text', 'openrouter')


def test_erst_wenn_alle_scheitern_gibt_es_einen_fehler():
    clients = {name: TranskriptionsAttrappe(fehler=RuntimeError('kaputt'))
               for name in ('groq', 'openrouter', 'openai')}
    with pytest.raises(RuntimeError) as fehler:
        typefree.transcribe_audio(puffer(), clients)
    for name in ('groq', 'openrouter', 'openai'):
        assert name in str(fehler.value)


def test_sprache_und_vokabular_gehen_mit():
    groq = TranskriptionsAttrappe(text='ok')
    typefree.transcribe_audio(puffer(), {'groq': groq})
    assert groq.aufrufe[0]['language'] == 'de'
    assert 'Scancode' in groq.aufrufe[0]['prompt']


def test_modellname_kommt_aus_der_kette():
    groq = TranskriptionsAttrappe(text='ok')
    typefree.transcribe_audio(puffer(), {'groq': groq})
    assert groq.aufrufe[0]['model'] == 'whisper-large-v3'


# ── Glättung über die Modellkette ─────────────────────────────────────────────

def test_abgekuendigtes_modell_legt_den_filter_nicht_still(monkeypatch):
    """Genau der Fehler aus dem Betrieb: 404 auf Modell 1 — Modell 2 liefert."""
    kette = ('google/gemini-2.0-flash-001', 'google/gemini-2.5-flash')
    monkeypatch.setattr(typefree, 'POLISH_MODELLE', kette)

    class NurZweitesModell:
        """Antwortet nur auf das zweite Modell — wie ein 404 auf das erste."""

        def __init__(self):
            self.aufrufe = []

            def create(**kwargs):
                self.aufrufe.append(kwargs)
                if kwargs['model'] == kette[0]:
                    raise RuntimeError('404 No endpoints found for '
                                       'google/gemini-2.0-flash-001')
                return types.SimpleNamespace(choices=[types.SimpleNamespace(
                    message=types.SimpleNamespace(content=BEREINIGT))])

            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create))

    attrappe = NurZweitesModell()
    monkeypatch.setattr(typefree, 'openrouter_client', attrappe)
    assert typefree.polish_text(ROHTEXT) == BEREINIGT
    assert [a['model'] for a in attrappe.aufrufe] == list(kette)


def test_unplausible_antwort_laesst_das_naechste_modell_ran(monkeypatch):
    monkeypatch.setattr(typefree, 'POLISH_MODELLE',
                        ('google/gemini-2.5-flash', 'google/gemini-3.5-flash-lite'))
    # Erste Antwort ist abgeschnitten — Modell 2 wird gefragt.
    abgeschnitten = GlattungsAttrappe(antwort=ROHTEXT[:40])
    monkeypatch.setattr(typefree, 'openrouter_client', abgeschnitten)
    assert typefree.polish_text(ROHTEXT) is None
    assert len(abgeschnitten.aufrufe) == 2


def test_glaettung_nutzt_das_erste_modell_wenn_es_liefert(monkeypatch):
    attrappe = GlattungsAttrappe(antwort=BEREINIGT)
    monkeypatch.setattr(typefree, 'openrouter_client', attrappe)
    assert typefree.polish_text(ROHTEXT) == BEREINIGT
    assert attrappe.aufrufe[0]['model'] == typefree.POLISH_MODELLE[0]
    assert len(attrappe.aufrufe) == 1


def test_modellkette_hat_mehrere_modelle():
    assert len(typefree.POLISH_MODELLE) >= 2
    assert len(set(typefree.POLISH_MODELLE)) == len(typefree.POLISH_MODELLE)


# ── Ausfall der Glättung wird gemeldet ────────────────────────────────────────

def test_ausfaelle_zaehlen_hoch_und_erfolg_setzt_zurueck():
    assert typefree.ausfall_zaehlen(0, False) == 1
    assert typefree.ausfall_zaehlen(2, False) == 3
    assert typefree.ausfall_zaehlen(5, True) == 0


def test_gemeldet_wird_genau_einmal():
    grenze = typefree.GLATTUNG_AUSFALL_GRENZE
    assert typefree.ausfall_melden(grenze - 1) is False
    assert typefree.ausfall_melden(grenze) is True
    assert typefree.ausfall_melden(grenze + 1) is False


class TrayAttrappe:
    """Sammelt Sprechblasen und das zuletzt gesetzte Icon."""

    def __init__(self):
        self.icon = None
        self.gemeldet = []

    def notify(self, text, titel=None):
        self.gemeldet.append((text, titel))


def test_hinweis_kommt_ohne_rotes_icon(monkeypatch):
    """Die Glättung darf fehlen — das Diktat nicht. Also Hinweis, kein Fehler."""
    tray = TrayAttrappe()
    monkeypatch.setattr(typefree, 'tray_icon', tray)
    typefree._melde_glattung_ausfall()
    assert tray.gemeldet and 'Rohtext' in tray.gemeldet[0][0]
    assert tray.icon is None          # kein rotes Icon


# ── Zeitprotokoll ─────────────────────────────────────────────────────────────

def test_zeiten_werden_deutsch_mit_komma_geschrieben():
    text = typefree.zeiten_text([('Transkription (groq)', 0.72), ('gesamt', 1.94)])
    assert text == 'Transkription (groq) 0,7 s · gesamt 1,9 s'


def test_kosten_je_anbieter_unterscheiden_sich():
    groq = typefree.kosten_fuer(600, 'groq')
    openai = typefree.kosten_fuer(600, 'openai')
    assert groq < openai
    assert abs(groq - 0.0185) < 1e-9          # 10 Minuten bei 0,111 $/Stunde
