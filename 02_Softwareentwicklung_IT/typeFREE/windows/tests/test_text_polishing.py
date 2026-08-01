"""Die Glättung darf ein Diktat nie verstümmeln.

Zwei Gefahren:
  1. Groq schneidet bei erreichter Token-Grenze mitten im Satz ab. Seit der
     10-Minuten-Aufnahme (Entscheidung 12) ist das erreichbar.
  2. Das Modell *antwortet* auf den Text statt ihn zu bereinigen.
In beiden Fällen ist der Rohtext von Whisper besser als das Ergebnis — ein
Diktat darf nie stillschweigend verloren gehen.
"""
import types

import pytest
import typefree

ROHTEXT = (
    'Also ähm ich wollte gucken ob die zweite Prüfung jetzt durchläuft und '
    'wenn ja dann können wir den nächsten Slice angehen also den mit dem '
    'Autostart und der Aufgabenplanung.'
)


def groq_attrappe(antwort=None, fehler=None):
    """Nachbau des Groq-Clients, so weit polish_text ihn benutzt."""
    aufrufe = []

    def create(**kwargs):
        aufrufe.append(kwargs)
        if fehler:
            raise fehler
        nachricht = types.SimpleNamespace(content=antwort)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=nachricht)])

    attrappe = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create)),
        aufrufe=aufrufe)
    return attrappe


# ── Plausibilitätsprüfung ─────────────────────────────────────────────────────

def test_normale_bereinigung_ist_plausibel():
    geglaettet = ROHTEXT.replace('ähm ', '').replace('Also ', '')
    assert typefree._polished_is_plausible(ROHTEXT, geglaettet) is True


def test_abgeschnittene_antwort_ist_unplausibel():
    """Groq bricht bei der Token-Grenze mitten im Satz ab."""
    assert typefree._polished_is_plausible(ROHTEXT, ROHTEXT[:40]) is False


def test_leere_antwort_ist_unplausibel():
    assert typefree._polished_is_plausible(ROHTEXT, '') is False
    assert typefree._polished_is_plausible(ROHTEXT, None) is False


def test_kurzes_diktat_darf_stark_schrumpfen():
    """„ähm ja genau" → „ja" verliert über die Hälfte und ist trotzdem richtig."""
    assert typefree._polished_is_plausible('ähm ja genau', 'ja') is True


# ── Rückfall auf den Rohtext ──────────────────────────────────────────────────

def test_geglaetteter_text_wird_durchgelassen(monkeypatch):
    """Eine echte Bereinigung kürzt nur um wenige Prozent — „gucken" bleibt."""
    erwartet = (
        'Ich wollte gucken, ob die zweite Prüfung jetzt durchläuft, und wenn '
        'ja, dann können wir den nächsten Slice angehen, den mit dem Autostart '
        'und der Aufgabenplanung.'
    )
    monkeypatch.setattr(typefree, 'openrouter_client', groq_attrappe(antwort=erwartet))
    assert typefree.polish_text(ROHTEXT) == erwartet


def test_abgeschnittene_antwort_fuehrt_zum_rohtext(monkeypatch):
    monkeypatch.setattr(typefree, 'openrouter_client', groq_attrappe(antwort=ROHTEXT[:40]))
    assert typefree.polish_text(ROHTEXT) is None


def test_fehler_bei_groq_fuehrt_zum_rohtext(monkeypatch):
    monkeypatch.setattr(typefree, 'openrouter_client',
                        groq_attrappe(fehler=RuntimeError('401')))
    assert typefree.polish_text(ROHTEXT) is None


# ── Inhalt der Anweisung ──────────────────────────────────────────────────────

def test_anweisung_verlangt_verhoerer_korrektur_und_slang_schonung(monkeypatch):
    """Die zwei Kernanliegen aus Entscheidung 19 müssen in der Anweisung stehen."""
    attrappe = groq_attrappe(antwort=ROHTEXT)
    monkeypatch.setattr(typefree, 'openrouter_client', attrappe)
    typefree.polish_text(ROHTEXT)

    anweisung = attrappe.aufrufe[0]['messages'][0]['content'].lower()
    assert 'verhörer' in anweisung
    assert 'umgangssprache' in anweisung


def test_token_grenze_reicht_fuer_ein_langes_diktat(monkeypatch):
    """Zehn Minuten Sprache sind grob 1500 Wörter — 1000 Tokens genügen nicht."""
    attrappe = groq_attrappe(antwort=ROHTEXT)
    monkeypatch.setattr(typefree, 'openrouter_client', attrappe)
    typefree.polish_text(ROHTEXT)
    assert attrappe.aufrufe[0]['max_tokens'] >= 4000
