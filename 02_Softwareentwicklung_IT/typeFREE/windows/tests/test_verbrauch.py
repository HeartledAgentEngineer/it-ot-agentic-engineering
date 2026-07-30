"""Kostenzählung für Whisper.

Sebastian bezahlt die Transkription nach Audiolänge — $0,006 je Minute,
sekundengenau abgerechnet. Die Audiolänge kennt das Programm exakt, also
lässt sich der Preis ohne Zusatzabfrage mitrechnen (Entscheidung 18).

Groq bleibt bewusst außen vor: dort gilt das kostenlose Tier.
"""
import typefree


def test_eine_minute_kostet_den_minutenpreis():
    assert typefree.whisper_kosten(60) == typefree.WHISPER_PREIS_JE_MINUTE


def test_abrechnung_ist_sekundengenau_nicht_aufgerundet():
    """Zehn Sekunden kosten ein Sechstel Minutenpreis, nicht einen ganzen."""
    assert abs(typefree.whisper_kosten(10) - 0.001) < 1e-9


def test_leere_aufnahme_kostet_nichts():
    assert typefree.whisper_kosten(0) == 0.0


def test_erste_buchung_legt_den_monat_an():
    neu = typefree.verbrauch_buchen({}, sekunden=30, monat='2026-07')
    assert neu['monat'] == '2026-07'
    assert neu['monat_sekunden'] == 30
    assert neu['monat_diktate'] == 1
    assert neu['gesamt_sekunden'] == 30
    assert neu['gesamt_diktate'] == 1


def test_buchungen_summieren_sich():
    v = typefree.verbrauch_buchen({}, sekunden=30, monat='2026-07')
    v = typefree.verbrauch_buchen(v, sekunden=15, monat='2026-07')
    assert v['monat_sekunden'] == 45
    assert v['monat_diktate'] == 2


def test_neuer_monat_setzt_nur_den_monatszaehler_zurueck():
    v = typefree.verbrauch_buchen({}, sekunden=600, monat='2026-07')
    v = typefree.verbrauch_buchen(v, sekunden=60, monat='2026-08')
    assert v['monat'] == '2026-08'
    assert v['monat_sekunden'] == 60           # Monat beginnt neu
    assert v['gesamt_sekunden'] == 660         # Gesamtsumme läuft weiter
    assert v['gesamt_diktate'] == 2


def test_buchen_verändert_die_uebergabe_nicht():
    """Reine Funktion — der alte Stand muss unberührt bleiben."""
    alt = typefree.verbrauch_buchen({}, sekunden=30, monat='2026-07')
    typefree.verbrauch_buchen(alt, sekunden=99, monat='2026-07')
    assert alt['monat_sekunden'] == 30


def test_anzeige_nennt_minuten_und_betrag():
    v = typefree.verbrauch_buchen({}, sekunden=744, monat='2026-07')
    text = typefree.verbrauch_text(v)
    assert '12,4 min' in text        # 744 s = 12,4 Minuten
    assert '0,07' in text            # 744/60 * 0,006 = 0,0744 $
    assert '$' in text


def test_anzeige_haelt_auch_leeren_stand_aus():
    text = typefree.verbrauch_text({})
    assert '0,0 min' in text
