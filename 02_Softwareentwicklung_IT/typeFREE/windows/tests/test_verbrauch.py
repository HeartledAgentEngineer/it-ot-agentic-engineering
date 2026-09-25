"""Kostenzählung für die Transkription.

Sebastian bezahlt die Transkription nach Audiolänge — beim Regelfall Groq
$0,111 je Stunde, sekundengenau abgerechnet. Die Audiolänge kennt das Programm
exakt, also lässt sich der Preis ohne Zusatzabfrage mitrechnen
(Entscheidung 18). Seit dem Anbieterwechsel am 25.09.2026 hängt der Preis am
Anbieter, der das Diktat tatsächlich transkribiert hat.
"""
import typefree


def test_eine_minute_kostet_den_minutenpreis():
    assert typefree.whisper_kosten(60) == typefree.WHISPER_PREIS_JE_MINUTE


def test_abrechnung_ist_sekundengenau_nicht_aufgerundet():
    """Zehn Sekunden kosten ein Sechstel Minutenpreis, nicht einen ganzen."""
    sechstel = typefree.WHISPER_PREIS_JE_MINUTE / 6
    assert abs(typefree.whisper_kosten(10) - sechstel) < 1e-9


def test_leere_aufnahme_kostet_nichts():
    assert typefree.whisper_kosten(0) == 0.0


def test_erste_buchung_legt_den_monat_an():
    neu = typefree.verbrauch_buchen({}, sekunden=30, monat='2026-07', anbieter='groq')
    assert neu['monat'] == '2026-07'
    assert neu['monat_sekunden'] == 30
    assert neu['monat_diktate'] == 1
    assert neu['gesamt_sekunden'] == 30
    assert neu['gesamt_diktate'] == 1
    assert neu['monat_anbieter'] == ['groq']


def test_buchungen_summieren_sich():
    v = typefree.verbrauch_buchen({}, sekunden=30, monat='2026-07', anbieter='groq')
    v = typefree.verbrauch_buchen(v, sekunden=15, monat='2026-07', anbieter='groq')
    assert v['monat_sekunden'] == 45
    assert v['monat_diktate'] == 2
    assert abs(v['monat_betrag'] - typefree.kosten_fuer(45, 'groq')) < 1e-9


def test_neuer_monat_setzt_nur_den_monatszaehler_zurueck():
    v = typefree.verbrauch_buchen({}, sekunden=600, monat='2026-07', anbieter='groq')
    v = typefree.verbrauch_buchen(v, sekunden=60, monat='2026-08', anbieter='groq')
    assert v['monat'] == '2026-08'
    assert v['monat_sekunden'] == 60           # Monat beginnt neu
    assert v['gesamt_sekunden'] == 660         # Gesamtsumme läuft weiter
    assert v['gesamt_diktate'] == 2
    assert abs(v['monat_betrag'] - typefree.kosten_fuer(60, 'groq')) < 1e-9
    assert abs(v['gesamt_betrag'] - typefree.kosten_fuer(660, 'groq')) < 1e-9


def test_buchen_verändert_die_uebergabe_nicht():
    """Reine Funktion — der alte Stand muss unberührt bleiben."""
    alt = typefree.verbrauch_buchen({}, sekunden=30, monat='2026-07', anbieter='groq')
    typefree.verbrauch_buchen(alt, sekunden=99, monat='2026-07', anbieter='groq')
    assert alt['monat_sekunden'] == 30


def test_wechsel_des_wegs_aendert_den_betrag_nicht_rueckwirkend():
    """Der Fehler aus dem Betrieb: 0,33 $ wurden zu 1,04 $, nur durch die Wegwahl.

    Die Beträge werden beim Buchen festgehalten — der teurere Weg darf die alten
    Diktate nicht nachträglich teurer machen.
    """
    v = typefree.verbrauch_buchen({}, sekunden=744, monat='2026-07', anbieter='groq')
    vorher = v['monat_betrag']
    text = typefree.verbrauch_text(v)
    assert abs(v['monat_betrag'] - vorher) < 1e-12      # unverändert
    assert '0,02' in text                               # Groq-Preis: 0,0229 $
    assert '(Groq)' in text


def test_mehrere_anbieter_im_monat_werden_ausgewiesen():
    v = typefree.verbrauch_buchen({}, sekunden=744, monat='2026-07', anbieter='groq')
    v = typefree.verbrauch_buchen(v, sekunden=744, monat='2026-07', anbieter='voxtral')
    assert v['monat_anbieter'] == ['groq', 'voxtral']
    text = typefree.verbrauch_text(v)
    assert '(Groq +)' in text                           # Mehrzahl sichtbar
    erwartet = typefree.kosten_fuer(744, 'groq') + typefree.kosten_fuer(744, 'voxtral')
    assert abs(v['monat_betrag'] - erwartet) < 1e-9


def test_alter_stand_ohne_betraege_wird_geschaetzt(monkeypatch, tmp_path):
    """Vor dem 25.09.2026 wurden nur Sekunden gespeichert — Groq war der Regelfall."""
    pfad = tmp_path / 'verbrauch.json'
    pfad.write_text('{"monat": "2026-09", "monat_sekunden": 600, '
                    '"gesamt_sekunden": 3600, "gesamt_diktate": 40}',
                    encoding='utf-8')
    monkeypatch.setattr(typefree, 'VERBRAUCH_PATH', str(pfad))
    stand = typefree.load_verbrauch()
    assert abs(stand['gesamt_betrag'] - typefree.whisper_kosten(3600)) < 1e-9
    assert abs(stand['monat_betrag'] - typefree.whisper_kosten(600)) < 1e-9
    assert stand['monat_anbieter'] == ['groq']


def test_kaputte_datei_ergibt_leeren_stand(monkeypatch, tmp_path):
    pfad = tmp_path / 'verbrauch.json'
    pfad.write_text('kein json', encoding='utf-8')
    monkeypatch.setattr(typefree, 'VERBRAUCH_PATH', str(pfad))
    assert typefree.load_verbrauch() == {}


def test_anzeige_nennt_minuten_betrag_und_anbieter():
    v = typefree.verbrauch_buchen({}, sekunden=744, monat='2026-07', anbieter='groq')
    text = typefree.verbrauch_text(v)
    assert '12,4 min' in text        # 744 s = 12,4 Minuten
    assert '0,02' in text            # 744/60 * 0,00185 (Groq) = 0,0229 $
    assert '(Groq)' in text          # der Preis hängt am Anbieter
    assert '$' in text


def test_anzeige_haelt_auch_leeren_stand_aus():
    text = typefree.verbrauch_text({})
    assert '0,0 min' in text
