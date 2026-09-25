"""Die Transkription läuft über eine wählbare Anbieterkette, die Glättung über eine Modellkette.

Anlass (25.09.2026): Zwei Betriebsfehler und eine Vorgabe.

1. Der OpenAI-Schlüssel ist ohne Guthaben, jeder Aufruf scheiterte — das Diktat
   lief über OpenRouter und brauchte ein Vielfaches der Zeit.
2. Die Glättung stand wochenlang auf einem abgekündigten Modell, jede Anfrage
   endete im 404, der Filter war damit faktisch aus. Und weil das nur im Log
   stand, blieb es unbemerkt.
3. Der Transkriptions-Endpunkt von OpenRouter liefert in rund der Hälfte der
   Läufe nur die letzten Sekunden des Audios (16 Messläufe). Er kommt deshalb
   nicht mehr in den Regelpfad.

Sebastians Vorgabe: Die Stimme soll nicht im Netz verschleudert werden — sie
geht nicht mehr an OpenAI und nicht ohne ausdrückliche Wahl an Groq. Regelfall
ist der EU-Weg über Mistral (Frankreich), umschaltbar in der config.json.
"""
import base64
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

# Eine Kette mit zwei Stufen, um das Nachrücken zu prüfen — die echten Ketten
# haben je Weg nur eine Stufe.
ZWEI_STUFEN = (
    ('groq',       'whisper-large-v3',        'https://api.groq.com/openai/v1', 'stt'),
    ('openrouter', 'openai/whisper-large-v3', 'https://openrouter.ai/api/v1',   'stt'),
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


class ChatAttrappe:
    """Nachbau des OpenRouter-Clients für den Audio-Chat-Weg (Voxtral)."""

    def __init__(self, text=None, fehler=None):
        self.aufrufe = []
        self._text = text
        self._fehler = fehler

        def create(**kwargs):
            self.aufrufe.append(kwargs)
            if self._fehler:
                raise self._fehler
            return types.SimpleNamespace(choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content=self._text))])

        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create))


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


@pytest.fixture
def leere_config(tmp_path, monkeypatch):
    """Eine config.json im Testordner — die echte im Projekt bleibt unberührt."""
    pfad = tmp_path / 'config.json'
    monkeypatch.setattr(typefree, 'CONFIG_PATH', str(pfad))
    return pfad


# ── Anbieterketten ────────────────────────────────────────────────────────────

def test_drei_wege_stehen_zur_wahl():
    assert set(typefree.KETTEN) == {'eu', 'beste', 'schnell'}


def test_jeder_weg_hat_eine_beschriftung():
    """Ohne Beschriftung hätte das Tray-Untermenü einen leeren Eintrag."""
    assert typefree.WEG_REIHENFOLGE == ('eu', 'beste', 'schnell')
    for wahl in typefree.WEG_REIHENFOLGE:
        assert typefree.WEG_BESCHRIFTUNG[wahl].strip()
    assert set(typefree.WEG_BESCHRIFTUNG) == set(typefree.KETTEN)


def test_regelweg_ist_der_eu_weg():
    """Vorgabe vom 25.09.2026: nicht OpenAI, nicht Groq ohne ausdrückliche Wahl."""
    assert typefree.STANDARD_WEG == 'eu'
    assert typefree.TRANSCRIPTION_KETTE == typefree.KETTEN['eu']
    assert typefree.TRANSCRIPTION_KETTE[0][0] == 'voxtral'


def test_eu_weg_laeuft_ueber_den_audio_chat():
    """Voxtral hat keinen Transkriptions-Endpunkt — das Audio geht in den Chat."""
    name, modell, adresse, weg = typefree.KETTEN['eu'][0]
    assert modell.startswith('mistralai/')
    assert adresse == 'https://openrouter.ai/api/v1'
    assert weg == 'chat'


def test_schneller_weg_nutzt_den_transkriptions_endpunkt():
    name, modell, adresse, weg = typefree.KETTEN['schnell'][0]
    assert (name, weg) == ('groq', 'stt')


def test_kein_anbieter_der_ketten_ist_openai():
    """OpenAI ist aus dem Regelpfad raus — das Konto hat kein Guthaben, und die
    Stimme soll dort nicht landen."""
    for kette in typefree.KETTEN.values():
        assert all(name != 'openai' for name, _, _, _ in kette)


def test_jeder_eintrag_hat_modell_adresse_und_weg():
    for kette in typefree.KETTEN.values():
        for name, modell, adresse, weg in kette:
            assert modell and adresse.startswith('https://')
            assert weg in ('stt', 'chat', 'elevenlabs')


def test_jeder_weg_hat_einen_schluessel_eintrag():
    for kette in typefree.KETTEN.values():
        for name, _, _, _ in kette:
            assert typefree.SCHLUESSEL_JE_ANBIETER[name].endswith('_API_KEY')


# ── Beste Qualität: ElevenLabs Scribe ─────────────────────────────────────────

def test_scribe_ist_der_weg_fuer_beste_qualitaet():
    name, modell, adresse, weg = typefree.KETTEN['beste'][0]
    assert (name, modell, weg) == ('scribe', 'scribe_v2', 'elevenlabs')
    assert adresse == 'https://api.elevenlabs.io/v1'
    assert typefree.SCHLUESSEL_JE_ANBIETER['scribe'] == 'ELEVENLABS_API_KEY'


def test_keyterms_werden_aus_dem_vokabelhinweis_geschnitten():
    """Scribe erwartet eine Begriffsliste — der Hinweis ist eine Zeile."""
    assert typefree._keyterms('TwinCAT, SPS , Scancode') == ['TwinCAT', 'SPS', 'Scancode']
    assert typefree._keyterms('') == []
    assert len(typefree._keyterms(','.join(f'Begriff{i}' for i in range(300)))) == 100


def test_multipart_ist_wohlgeformt():
    """Der Upload muss die Grenze, den Dateinamen und die Audiodaten enthalten."""
    koerper, inhaltstyp = typefree._multipart(
        [('model_id', 'scribe_v2'), ('language_code', 'deu')], 'audio.wav', b'RIFF-audio')
    grenze = inhaltstyp.split('boundary=')[1]
    crlf = (chr(13) + chr(10)).encode()
    assert koerper.startswith(f'--{grenze}'.encode() + crlf)
    assert koerper.endswith(f'--{grenze}--'.encode() + crlf)
    assert b'name="model_id"' in koerper and b'scribe_v2' in koerper
    assert b'filename="audio.wav"' in koerper
    assert b'RIFF-audio' in koerper


def test_preise_decken_alle_ketten():
    for kette in typefree.KETTEN.values():
        for name, _, _, _ in kette:
            assert name in typefree.PREISE_JE_MINUTE


def test_der_schnelle_weg_ist_billiger_als_der_eu_weg():
    """0,111 $/Stunde gegen rund 0,36 $/Stunde."""
    assert (typefree.PREISE_JE_MINUTE['groq']
            < typefree.PREISE_JE_MINUTE['voxtral'])


def test_verfuegbare_anbieter_haelt_die_kettenreihenfolge():
    umgebung = {'OPENROUTER_API_KEY': 'x', 'GROQ_API_KEY': 'y'}
    assert typefree.verfuegbare_anbieter(umgebung, typefree.KETTEN['eu']) == ('voxtral',)
    assert typefree.verfuegbare_anbieter(umgebung, typefree.KETTEN['schnell']) == ('groq',)


def test_verfuegbare_anbieter_ignoriert_leere_schluessel():
    umgebung = {'GROQ_API_KEY': '', 'OPENROUTER_API_KEY': 'y'}
    assert typefree.verfuegbare_anbieter(umgebung, ZWEI_STUFEN) == ('openrouter',)


def test_ohne_jeden_schluessel_gibt_es_keine_anbieter():
    assert typefree.verfuegbare_anbieter({}) == ()


def test_baue_client_ohne_schluessel_gibt_none():
    """Ohne Schlüssel darf kein Client entstehen — OpenAI() würde werfen."""
    assert typefree.baue_client('https://api.groq.com/openai/v1', '') is None
    assert typefree.baue_client('https://api.groq.com/openai/v1', None) is None


# ── Wahl des Weges über die config.json ──────────────────────────────────────

def test_ohne_konfiguration_gilt_der_eu_weg(leere_config):
    assert typefree.transkription_wahl() == 'eu'


def test_gewaehlter_weg_wird_gelesen(leere_config):
    typefree.setze_transkription('schnell')
    assert typefree.transkription_wahl() == 'schnell'
    assert 'schnell' in leere_config.read_text(encoding='utf-8')


def test_unbekannter_weg_wird_abgewiesen(leere_config):
    with pytest.raises(ValueError):
        typefree.setze_transkription('irgendwas')
    assert typefree.transkription_wahl() == 'eu'


def test_hotkey_speichern_loescht_die_wegwahl_nicht(leere_config):
    """Der Hotkey-Dialog schrieb die config.json vorher komplett neu."""
    typefree.setze_transkription('schnell')
    typefree.save_hotkey_config(3)
    assert typefree.transkription_wahl() == 'schnell'
    assert typefree.load_hotkey_config() == typefree.HOTKEY_OPTIONS[3]


def test_aktive_kette_folgt_der_wahl(leere_config):
    umgebung = {'OPENROUTER_API_KEY': 'x', 'GROQ_API_KEY': 'y'}
    assert typefree.aktive_kette(umgebung) == typefree.KETTEN['eu']
    typefree.setze_transkription('schnell')
    assert typefree.aktive_kette(umgebung) == typefree.KETTEN['schnell']


def test_fehlender_schluessel_kippt_auf_den_anderen_weg(leere_config):
    """Ohne OpenRouter-Schlüssel darf das Diktieren nicht unmöglich sein."""
    assert typefree.aktive_kette({'GROQ_API_KEY': 'y'}) == typefree.KETTEN['schnell']
    typefree.setze_transkription('schnell')
    assert typefree.aktive_kette({'OPENROUTER_API_KEY': 'x'}) == typefree.KETTEN['eu']


# ── Transkription über die Kette ──────────────────────────────────────────────

def test_erster_anbieter_wird_genommen_wenn_er_liefert():
    groq = TranskriptionsAttrappe(text='  Hallo Welt  ')
    openrouter = TranskriptionsAttrappe(text='sollte nicht benutzt werden')
    text, anbieter = typefree.transcribe_audio(
        puffer(), {'groq': groq, 'openrouter': openrouter}, kette=ZWEI_STUFEN)
    assert (text, anbieter) == ('Hallo Welt', 'groq')
    assert len(openrouter.aufrufe) == 0


def test_toter_anbieter_faellt_aus_ohne_das_diktat_zu_kosten():
    groq = TranskriptionsAttrappe(fehler=RuntimeError('401 Konto ohne Guthaben'))
    openrouter = TranskriptionsAttrappe(text='Text vom Ausweichweg')
    text, anbieter = typefree.transcribe_audio(
        puffer(), {'groq': groq, 'openrouter': openrouter}, kette=ZWEI_STUFEN)
    assert (text, anbieter) == ('Text vom Ausweichweg', 'openrouter')


def test_puffer_steht_vor_jedem_versuch_wieder_am_anfang():
    """Nach einem Fehlversuch steht der Dateizeiger am Ende — sonst leere Datei."""
    groq = TranskriptionsAttrappe(fehler=RuntimeError('500'))
    openrouter = TranskriptionsAttrappe(text='ok')
    typefree.transcribe_audio(puffer(), {'groq': groq, 'openrouter': openrouter},
                              kette=ZWEI_STUFEN)
    assert groq.puffer_positionen == [0]
    assert openrouter.puffer_positionen == [0]


def test_anbieter_ohne_client_wird_uebersprungen():
    openrouter = TranskriptionsAttrappe(text='nur OpenRouter da')
    text, anbieter = typefree.transcribe_audio(
        puffer(), {'groq': None, 'openrouter': openrouter}, kette=ZWEI_STUFEN)
    assert (text, anbieter) == ('nur OpenRouter da', 'openrouter')


def test_leere_antwort_gilt_als_fehlschlag():
    groq = TranskriptionsAttrappe(text='   ')
    openrouter = TranskriptionsAttrappe(text='richtiger Text')
    text, anbieter = typefree.transcribe_audio(
        puffer(), {'groq': groq, 'openrouter': openrouter}, kette=ZWEI_STUFEN)
    assert (text, anbieter) == ('richtiger Text', 'openrouter')


def test_erst_wenn_alle_scheitern_gibt_es_einen_fehler():
    clients = {name: TranskriptionsAttrappe(fehler=RuntimeError('kaputt'))
               for name in ('groq', 'openrouter')}
    with pytest.raises(RuntimeError) as fehler:
        typefree.transcribe_audio(puffer(), clients, kette=ZWEI_STUFEN)
    for name in ('groq', 'openrouter'):
        assert name in str(fehler.value)


def test_sprache_und_vokabular_gehen_mit():
    """Der STT-Weg übergibt Sprache und Vokabular als Parameter."""
    groq = TranskriptionsAttrappe(text='ok')
    typefree.transcribe_audio(puffer(), {'groq': groq}, kette=typefree.KETTEN['schnell'])
    assert groq.aufrufe[0]['language'] == 'de'
    assert 'Scancode' in groq.aufrufe[0]['prompt']


def test_modellname_kommt_aus_der_kette():
    groq = TranskriptionsAttrappe(text='ok')
    typefree.transcribe_audio(puffer(), {'groq': groq}, kette=typefree.KETTEN['schnell'])
    assert groq.aufrufe[0]['model'] == 'whisper-large-v3'


# ── Der Audio-Chat-Weg (EU) ───────────────────────────────────────────────────

def test_chat_weg_schickt_das_audio_als_base64():
    attrappe = ChatAttrappe(text='  Text aus dem Chat  ')
    text, anbieter = typefree.transcribe_audio(
        puffer(), {'voxtral': attrappe}, kette=typefree.KETTEN['eu'])
    assert (text, anbieter) == ('Text aus dem Chat', 'voxtral')

    aufruf = attrappe.aufrufe[0]
    assert aufruf['model'] == 'mistralai/voxtral-small-24b-2507'
    auftrag, audio = aufruf['messages'][0]['content']
    assert auftrag['type'] == 'text'
    assert 'Scancode' in auftrag['text']            # Vokabular steht im Auftrag
    assert audio['type'] == 'input_audio'
    assert audio['input_audio']['format'] == 'wav'
    assert base64.b64decode(audio['input_audio']['data']) == b'RIFF....WAV-Daten'


def test_chat_weg_verlangt_zero_data_retention():
    """Das Audio darf beim Anbieter nicht gespeichert werden."""
    attrappe = ChatAttrappe(text='ok')
    typefree.transcribe_audio(puffer(), {'voxtral': attrappe},
                              kette=typefree.KETTEN['eu'])
    assert attrappe.aufrufe[0]['extra_body']['provider']['zdr'] is True


def test_chat_weg_scheitert_sauber_und_meldet_den_fehler():
    attrappe = ChatAttrappe(fehler=RuntimeError('404 Modell abgekündigt'))
    with pytest.raises(RuntimeError) as fehler:
        typefree.transcribe_audio(puffer(), {'voxtral': attrappe},
                                  kette=typefree.KETTEN['eu'])
    assert 'voxtral' in str(fehler.value)


class Drosselung(Exception):
    """Sieht aus wie die 429-Antwort der OpenAI-Bibliothek (trägt `status_code`)."""
    status_code = 429


class GedrosselterChat(ChatAttrappe):
    """Mistrals geteilter Pool: die ersten Aufrufe laufen in eine Drosselung (429)."""

    def __init__(self, text='Text nach der Drosselung', drosselungen=1):
        super().__init__(text=text)
        self._drosselungen = drosselungen

        def create(**kwargs):
            self.aufrufe.append(kwargs)
            if len(self.aufrufe) <= self._drosselungen:
                raise Drosselung('429 Provider returned error')
            return types.SimpleNamespace(choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content=f'  {self._text}  '))])

        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create))


def test_gedrosselter_chat_wird_wiederholt(monkeypatch):
    """429 vom geteilten Mistral-Pool darf das Diktat nicht kosten."""
    monkeypatch.setattr(typefree, 'CHAT_WARTEZEIT', 0.01)   # im Test nicht 1 s warten
    attrappe = GedrosselterChat()
    text, anbieter = typefree.transcribe_audio(puffer(), {'voxtral': attrappe},
                                               kette=typefree.KETTEN['eu'])
    assert (text, anbieter) == ('Text nach der Drosselung', 'voxtral')
    assert len(attrappe.aufrufe) == 2


def test_dauerhafte_drosselung_gibt_irgendwann_auf(monkeypatch):
    monkeypatch.setattr(typefree, 'CHAT_WARTEZEIT', 0.01)
    attrappe = GedrosselterChat(drosselungen=99)
    with pytest.raises(RuntimeError) as fehler:
        typefree.transcribe_audio(puffer(), {'voxtral': attrappe},
                                  kette=typefree.KETTEN['eu'])
    assert len(attrappe.aufrufe) == typefree.CHAT_WIEDERHOLUNGEN
    assert 'voxtral' in str(fehler.value)


def test_gewoehnlicher_fehler_wird_nicht_wiederholt(monkeypatch):
    """Ohne Status (Aufruf-/Programmierfehler) wäre Wiederholen nur Zeitverlust."""
    monkeypatch.setattr(typefree, 'CHAT_WARTEZEIT', 0.01)
    attrappe = ChatAttrappe(fehler=ValueError('irgendwas am Aufruf'))
    with pytest.raises(RuntimeError):
        typefree.transcribe_audio(puffer(), {'voxtral': attrappe},
                                  kette=typefree.KETTEN['eu'])
    assert len(attrappe.aufrufe) == 1


def test_zurueckgegebener_auftragstext_gilt_als_fehler():
    """Voxtral gab im Betrieb den Prompt selbst zurück — der darf nicht ins Dokument."""
    attrappe = ChatAttrappe(text=typefree.CHAT_AUFTRAG + 'typeFREE, Hotkey, Tray')
    with pytest.raises(RuntimeError) as fehler:
        typefree.transcribe_audio(puffer(), {'voxtral': attrappe},
                                  kette=typefree.KETTEN['eu'])
    assert 'Auftragstext' in str(fehler.value)


def test_echter_diktattext_wird_nicht_fuer_den_auftrag_gehalten():
    assert not typefree._ist_auftragstext('Transkribiere bitte das Protokoll.')
    assert not typefree._ist_auftragstext('Und dann hätte ich gerne einen Dropdown.')
    assert typefree._ist_auftragstext(
        'Transkribiere diese deutsche Sprachaufnahme wörtlich und vollständig.')


# ── Rückfall auf den anderen Weg ──────────────────────────────────────────────

def test_ausgefallener_weg_faellt_auf_den_anderen_zurueck(monkeypatch):
    """Mistrals 429 darf ein Diktat nicht kosten — der andere Weg springt ein."""
    monkeypatch.setattr(typefree, 'CHAT_WARTEZEIT', 0.01)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'x')
    monkeypatch.setenv('GROQ_API_KEY', 'y')
    monkeypatch.delenv('ELEVENLABS_API_KEY', raising=False)
    klienten = {'voxtral': ChatAttrappe(fehler=Drosselung('429')),
                'groq': TranskriptionsAttrappe(text='  Text aus dem Rückfall  ')}
    text, anbieter = typefree.transcribe_audio(puffer(), klienten)
    assert (text, anbieter) == ('Text aus dem Rückfall', 'groq')


def test_rueckfall_laesst_sich_abschalten(monkeypatch):
    """Auf Wunsch strikt: nur der gewählte Weg, sonst Fehler."""
    monkeypatch.setattr(typefree, 'RUECKFALL', False)
    monkeypatch.setattr(typefree, 'CHAT_WARTEZEIT', 0.01)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'x')
    monkeypatch.setenv('GROQ_API_KEY', 'y')
    klienten = {'voxtral': ChatAttrappe(fehler=Drosselung('429')),
                'groq': TranskriptionsAttrappe(text='darf nicht benutzt werden')}
    with pytest.raises(RuntimeError):
        typefree.transcribe_audio(puffer(), klienten)


def test_mit_eigener_kette_gibt_es_keinen_rueckfall(monkeypatch):
    """Werkzeuge (Stimmvergleich) wollen genau ihre Kette messen — nichts anderes."""
    monkeypatch.setenv('GROQ_API_KEY', 'y')
    klienten = {'voxtral': ChatAttrappe(fehler=Drosselung('429')),
                'groq': TranskriptionsAttrappe(text='nicht benutzen')}
    with pytest.raises(RuntimeError):
        typefree.transcribe_audio(puffer(), klienten, kette=typefree.KETTEN['eu'])


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
    text = typefree.zeiten_text([('Transkription (voxtral)', 0.72), ('gesamt', 1.94)])
    assert text == 'Transkription (voxtral) 0,7 s · gesamt 1,9 s'


def test_kosten_je_anbieter_unterscheiden_sich():
    groq = typefree.kosten_fuer(600, 'groq')
    voxtral = typefree.kosten_fuer(600, 'voxtral')
    assert groq < voxtral
    assert abs(groq - 0.0185) < 1e-9          # 10 Minuten bei 0,111 $/Stunde
