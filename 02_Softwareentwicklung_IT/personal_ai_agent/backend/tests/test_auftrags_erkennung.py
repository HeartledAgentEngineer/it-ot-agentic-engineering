"""Tests fuer die Auftragserkennung.

Die Beispiele sind keine erfundenen Saetze, sondern echte Eintraege aus dem
Auftragsbuch vom 17.08.2026 - einer davon der Fehlalarm, der den Umbau
ausgeloest hat.
"""
import pytest

from app.services import auftrags_erkennung as erk


# Der Fehlalarm vom 17.08.: landete als "feature, mittel" im Auftragsbuch.
KOCHFRAGE = (
    "Ich mache gerade Roggensteaks, die sind ungefähr zwischen 2,5 bis 3 "
    "Zentimeter dick. Wie viel brauche ich, wie lange muss ich die braten "
    "von jeder Seite? Ich möchte die medium rare haben und danach möchte "
    "ich die Kerntemperatur im Backofen messen. Bei welcher Temperatur "
    "soll ich den Backofen einstellen?"
)

# Echter Auftrag aus dem Buch (e1b0a530), frei diktiert.
DIKTIERTER_AUFTRAG = (
    "Noch eine weitere Programmieraufgabe, und zwar wenn ein Agent "
    "nachdenkt, sehe ich im Frontend eine kleine Blase und darunter noch "
    "eine Blase mit drei Punkten. Das soll geändert werden, das sieht vom "
    "Layout blöd aus. Achtet darauf, dass die Versionierung angepasst "
    "werden muss, sonst wird die Datei im Cache nicht überschrieben."
)


@pytest.fixture
def ohne_modell(monkeypatch):
    """Das Modell antwortet nicht - die Heuristik muss uebernehmen."""
    monkeypatch.setattr(erk, "_modell_entscheidet", lambda _: None)


class TestSignalpraefix:
    """Praefixe entscheiden allein, ohne das Modell zu fragen."""

    def test_auftrag_praefix_ohne_modellfrage(self, monkeypatch):
        def darf_nicht_gerufen_werden(_):
            raise AssertionError("Modell wurde trotz Signalpraefix gefragt")

        monkeypatch.setattr(erk, "_modell_entscheidet", darf_nicht_gerufen_werden)
        treffer, grund, kategorie, _ = erk.ist_auftrag("Auftrag: Tests ergaenzen")
        assert treffer is True
        assert "Signalpraefix" in grund
        assert kategorie == "feature"

    @pytest.mark.parametrize("praefix", ["Aufgabe:", "TODO:", "task:"])
    def test_weitere_praefixe(self, praefix, ohne_modell):
        treffer, _, _, _ = erk.ist_auftrag(f"{praefix} irgendwas tun")
        assert treffer is True


class TestHeuristikAlsNotnagel:
    """Faellt das Modell aus, entscheiden die Wortregeln."""

    def test_kochfrage_ist_kein_auftrag(self, ohne_modell):
        # Frueher True: "Seite" galt als System-Objekt, die Verbpruefung war
        # wirkungslos.
        treffer, _, _, _ = erk.ist_auftrag(KOCHFRAGE)
        assert treffer is False

    def test_verb_und_objekt_ergeben_auftrag(self, ohne_modell):
        treffer, grund, _, _ = erk.ist_auftrag("Baue bitte einen Test fuer die Route")
        assert treffer is True
        assert "Wortheuristik" in grund

    def test_verb_allein_reicht_nicht(self, ohne_modell):
        treffer, _, _, _ = erk.ist_auftrag("Baue mir bitte einen Schneemann")
        assert treffer is False

    def test_objekt_allein_reicht_nicht(self, ohne_modell):
        treffer, _, _, _ = erk.ist_auftrag("Was ist eigentlich ein Backend?")
        assert treffer is False

    def test_verb_nur_als_wort_nicht_als_teilstueck(self, ohne_modell):
        # "makellos" enthaelt "make", "Programmheft" enthaelt "programm".
        treffer, _, _, _ = erk.ist_auftrag("Das Programmheft war makellos")
        assert treffer is False

    def test_verbpruefung_ist_ueberhaupt_wirksam(self):
        # Der alte Code lieferte hier True, weil die Schleife ueber die
        # Verbliste statt ueber die Nachricht lief.
        assert erk.heuristik_ist_auftrag("Der Server steht im Keller") is False


class TestModellEntscheidet:
    """Das Modell hat das letzte Wort - solange es antwortet."""

    def test_modell_sagt_ja(self, monkeypatch):
        monkeypatch.setattr(erk, "_modell_entscheidet",
                            lambda _: (True, "will Frontend geaendert haben"))
        treffer, grund, _, _ = erk.ist_auftrag(DIKTIERTER_AUFTRAG)
        assert treffer is True
        assert grund.startswith("Modell:")

    def test_modell_sagt_nein_trotz_reizwoertern(self, monkeypatch):
        # Enthaelt "baue" und "test" - die Heuristik wuerde zugreifen.
        monkeypatch.setattr(erk, "_modell_entscheidet", lambda _: (False, "Wissensfrage"))
        treffer, _, kategorie, _ = erk.ist_auftrag(
            "Wie baue ich einen Test fuer meinen Kuchenteig?"
        )
        assert treffer is False
        assert kategorie is None

    def test_leere_nachricht(self):
        assert erk.ist_auftrag("") == (False, "", None, None)
        assert erk.ist_auftrag("   ") == (False, "", None, None)


class TestModellantwortLesen:
    """Was von OpenRouter zurueckkommt, ist nicht immer sauberes JSON."""

    def _mit_antwort(self, monkeypatch, inhalt):
        """Baut einen llm_service-Ersatz, der `inhalt` zurueckgibt."""
        class Nachricht:
            content = inhalt

        class Wahl:
            message = Nachricht()

        class Antwort:
            choices = [Wahl()]

        class Completions:
            @staticmethod
            def create(**_):
                return Antwort()

        class Chat:
            completions = Completions()

        class Client:
            chat = Chat()

        class Dienst:
            is_configured = True
            model = "test/modell"
            client = Client()

        import app.services.llm_service as llm_modul
        monkeypatch.setattr(llm_modul, "llm_service", Dienst())

    def test_sauberes_json(self, monkeypatch):
        self._mit_antwort(monkeypatch, '{"auftrag": true, "grund": "Codeaenderung"}')
        assert erk._modell_entscheidet("egal") == (True, "Codeaenderung")

    def test_json_im_codeblock(self, monkeypatch):
        self._mit_antwort(
            monkeypatch,
            '```json\n{"auftrag": false, "grund": "Wissensfrage"}\n```',
        )
        assert erk._modell_entscheidet("egal") == (False, "Wissensfrage")

    def test_leere_antwort_ergibt_none(self, monkeypatch):
        # Passiert echt: Reasoning-Modelle verbrauchen das Token-Budget im
        # Denken und liefern leeren Inhalt ohne Fehlermeldung.
        self._mit_antwort(monkeypatch, "")
        assert erk._modell_entscheidet("egal") is None

    def test_geschwaetz_ohne_json_ergibt_none(self, monkeypatch):
        self._mit_antwort(monkeypatch, "Das ist wohl eher ein Gespraech.")
        assert erk._modell_entscheidet("egal") is None

    def test_json_ohne_pflichtfeld_ergibt_none(self, monkeypatch):
        self._mit_antwort(monkeypatch, '{"grund": "keine Ahnung"}')
        assert erk._modell_entscheidet("egal") is None

    def test_nicht_konfiguriert_ergibt_none(self, monkeypatch):
        class Dienst:
            is_configured = False

        import app.services.llm_service as llm_modul
        monkeypatch.setattr(llm_modul, "llm_service", Dienst())
        assert erk._modell_entscheidet("egal") is None


class TestKategorieUndKomplexitaet:
    def test_bug_schlaegt_feature(self):
        assert erk.kategorisiere("Da ist ein Fehler drin") == "bug"

    def test_refactor(self):
        assert erk.kategorisiere("Bitte den Umbau der Klasse") == "refactor"

    def test_langer_text_wird_komplex(self):
        # Vorher unerreichbar: die 200er-Schwelle stand vor der 500er.
        assert erk.schaetze_komplexitaet("wort " * 150) == "komplex"

    def test_mittlerer_text(self):
        assert erk.schaetze_komplexitaet("wort " * 50) == "mittel"
