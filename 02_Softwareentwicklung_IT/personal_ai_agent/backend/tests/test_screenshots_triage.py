"""Pruefungen fuer screenshots_triage.py (Screenshot-Vorsortierung) — alles OHNE Netz.

Kein echter OpenRouter-Aufruf und keine echte pCloud: der pCloud-Dienst ist
eine Attrappe (``FakeDienst`` — liefert Ordnerlisten und winzige JPEG-Bytes
im Speicher), der Vision-Transport ist eine Attrappe (``FakeSender``); in der
autouse-Fixture ist ``httpx`` zusaetzlich komplett gesperrt. Ein erfundener
Schluessel liegt in einer temporaeren .env — niemals der echte. Alle Ausgaben
gehen nach tmp_path, nie nach ~/foto_sortierung und nie ins Repo. Es wird
keine Bilddatei geschrieben (Quelltext- UND Laufzeitpruefung).

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_screenshots_triage.py -q
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
from pathlib import Path

import pytest
from PIL import Image

WERKZEUG = (Path(__file__).resolve().parents[2]
            / "tools" / "foto_sortierung" / "screenshots_triage.py")
REPO = Path(__file__).resolve().parents[2]


def _laden():
    spez = importlib.util.spec_from_file_location("screenshots_triage", WERKZEUG)
    assert spez is not None and spez.loader is not None, (
        f"Werkzeug nicht gefunden: {WERKZEUG}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


triage = _laden()

SCHLUESSEL = "test-schluessel-nicht-echt-abcdef-1234567890"
MODELL = "google/gemini-2.5-flash"


# ── Attrappen (kein Netz) ──────────────────────────────────────────────────

class Stolperfalle:
    """Ein Aufruf, der niemals passieren darf (Trockenlauf)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Aufruf, obwohl keiner passieren darf!")


def _jpeg(farbe=(20, 80, 140), groesse=(120, 90)) -> bytes:
    puffer = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(puffer, "JPEG")
    return puffer.getvalue()


class FakeDienst:
    """pCloud-Attrappe: Ordnerlisten + Vorschaubilder, alles im Speicher."""

    def __init__(self, ordner=None, thumb_bytes=None):
        self.ordner = ordner if ordner is not None else standard_baum()
        self.thumb_bytes = thumb_bytes if thumb_bytes is not None else _jpeg()
        self.liste_aufrufe: list[int] = []
        self.thumb_aufrufe: list[tuple] = []
        self.thumb_fehler: Exception | None = None

    def liste(self, folderid: int = 0) -> list[dict]:
        self.liste_aufrufe.append(int(folderid))
        return [dict(e) for e in self.ordner.get(int(folderid), [])]

    def thumb(self, fileid: int, groesse: str = "120x120") -> bytes:
        self.thumb_aufrufe.append((int(fileid), groesse))
        if self.thumb_fehler is not None:
            raise self.thumb_fehler
        return self.thumb_bytes


def standard_baum() -> dict:
    """Kleiner Screenshot-Baum: Basisordner + Unterordner + Beiwerk.

    fileids 101..103 direkt im Ordner (plus desktop.ini), 201/202 im
    Unterordner 'Screenshots' — so sind Dateiname und Unterordner pruefbar.
    """
    return {
        0: [{"name": "Bilder & Videos", "ist_ordner": True, "folderid": 11}],
        11: [{"name": "Screenshots", "ist_ordner": True, "folderid": 21},
             {"name": "Anderes", "ist_ordner": True, "folderid": 99}],
        99: [{"name": "kein-screenshot.png", "ist_ordner": False,
              "fileid": 999, "groesse": 10}],
        21: [{"name": "Screenshots", "ist_ordner": True, "folderid": 22},
             {"name": "desktop.ini", "ist_ordner": False, "fileid": 100,
              "groesse": 92},
             {"name": "Screenshot_20221107_125719.png", "ist_ordner": False,
              "fileid": 101, "groesse": 405722},
             {"name": "Screenshot_20221107_132530.png", "ist_ordner": False,
              "fileid": 102, "groesse": 132825},
             {"name": "Screenshot_20221108_175920.png", "ist_ordner": False,
              "fileid": 103, "groesse": 109170}],
        22: [{"name": "Screenshot 2024-12-04 001501.png", "ist_ordner": False,
              "fileid": 201, "groesse": 61084},
             {"name": "Screenshot 2024-12-04 034309.png", "ist_ordner": False,
              "fileid": 202, "groesse": 75663}],
    }


def _text(klasse="behalten-nuetzlich", thema="Sonstiges", befund="Tabelle mit Zahlen"):
    return json.dumps({"klasse": klasse, "thema": thema, "befund": befund},
                      ensure_ascii=False)


class FakeSender:
    """OpenRouter-Attrappe: je Aufruf eine Antwort (Text/Token einstellbar)."""

    def __init__(self, text=None, texte=None, tokens=(381, 54), fehler_bis=0,
                 fehlertext="Netz weg (Attrappe)"):
        self.text = text if text is not None else _text()
        self.texte = list(texte) if texte else None
        self.tokens = tokens
        self.fehler_bis = fehler_bis
        self.fehlertext = fehlertext
        self.aufrufe: list[dict] = []

    def __call__(self, payload, schluessel, basis, versuche=3):
        self.aufrufe.append(payload)
        if len(self.aufrufe) <= self.fehler_bis:
            raise triage.FotoVisionNetzfehler(self.fehlertext)
        text = (self.texte.pop(0) if self.texte else self.text)
        return {"text": text, "tokens_ein": self.tokens[0],
                "tokens_aus": self.tokens[1], "modell": MODELL}


@pytest.fixture(autouse=True)
def kein_netz_kein_schluessel(monkeypatch):
    """Kein echter Netzaufruf, kein echter Schluessel im Prozess."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def verboten(*args, **kwargs):
        raise AssertionError("echter Netzaufruf im Test!")

    monkeypatch.setattr(triage._vision.httpx, "post", verboten)
    monkeypatch.setattr(triage._vision.httpx, "get", verboten)


# ── kleine Helfer ──────────────────────────────────────────────────────────

def _env_datei(tmp_datei: Path, schluessel: str = SCHLUESSEL) -> Path:
    tmp_datei.write_text(f"OPENROUTER_API_KEY={schluessel}\n", encoding="utf-8")
    return tmp_datei


def _zeilen(pfad: Path) -> list[dict]:
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines()
            if z.strip()]


def _lauf(tmp_path, argv=None, dienst=None, sende=None, schluessel=True):
    """Einen Lauf mit Attrappen fahren; Ausgabe liegt immer in tmp_path."""
    argumente = ["--ausgabe", str(tmp_path / "triage.jsonl")] + list(argv or [])
    env_pfade = [_env_datei(tmp_path / ".env")] if schluessel else []
    return triage.main(argumente, dienst=dienst or FakeDienst(),
                       sende=sende if sende is not None else FakeSender(),
                       env_pfade=env_pfade)


# ── Feste Listen, Prompt, Anfrage ──────────────────────────────────────────

def test_listen_sind_fest_und_klein():
    """Die Auswahl ist genau die vier Klassen und die dreizehn Themen."""
    assert triage.KLASSEN == ("muell", "behalten-nuetzlich",
                              "behalten-persoenlich", "unklar")
    assert triage.KLASSE_UNKLAR in triage.KLASSEN
    assert len(triage.THEMEN) == 13
    assert triage.THEMA_SONSTIGES in triage.THEMEN
    assert triage.BEFUND_MAX == 100


def test_prompt_enthaelt_alle_klassen_und_themen_wort_fuer_wort():
    """Jede Klasse und jedes Thema steht ausgeschrieben im Prompt."""
    prompt = triage.prompt_bauen()
    for klasse in triage.KLASSEN:
        assert klasse in prompt
    for thema in triage.THEMEN:
        assert thema in prompt
    assert f"hoechstens {triage.BEFUND_MAX} Zeichen" in prompt
    assert "KEINE Namen von" in prompt


def test_anfrage_bauen_hat_text_und_bild():
    """Die Anfrage traegt Prompt und Bild als data:-URL, Temperatur 0."""
    daten_uri = triage.bild_daten_uri(_jpeg())
    assert daten_uri.startswith("data:image/jpeg;base64,")
    anfrage = triage.anfrage_bauen(MODELL, daten_uri)
    assert anfrage["model"] == MODELL
    assert anfrage["temperature"] == 0
    teile = anfrage["messages"][0]["content"]
    assert teile[0]["type"] == "text" and triage.prompt_bauen() == teile[0]["text"]
    assert teile[1]["type"] == "image_url"
    assert teile[1]["image_url"]["url"] == daten_uri


def test_antwort_mit_zaeunen_wird_zerlegt():
    """Markdown-Zaeune und Vor-/Nachtext stoeren die Zerlegung nicht."""
    roh = "Hier die Antwort:\n```json\n" + _text("muell", "Systemdialog") + "\n```"
    daten = triage.antwort_zerlegen(roh)
    assert daten["klasse"] == "muell"
    einordnung = triage.einordnung_uebernehmen(daten)
    assert einordnung == {"klasse": "muell", "thema": "Systemdialog",
                          "befund": "Tabelle mit Zahlen"}


def test_kaputte_antwort_ist_ein_fehler_kein_raten():
    """Ohne JSON-Objekt gibt es einen Fehler — es wird nichts erfunden."""
    with pytest.raises(triage.FotoVisionFehler):
        triage.antwort_zerlegen("Ich sehe leider nichts.")


# ── Einordnung: Klassen, Themen, Befund ────────────────────────────────────

def test_klassifizierung_wird_uebernommen(tmp_path):
    """Eine gueltige Modellantwort landet Wort fuer Wort in der Ausgabe."""
    sende = FakeSender(text=_text("behalten-nuetzlich", "Ticket", "Bestellbestaetigung Bahn"))
    assert _lauf(tmp_path, ["--grenze", "3"], sende=sende) == 0
    zeilen = _zeilen(tmp_path / "triage.jsonl")
    assert len(zeilen) == 3
    assert zeilen[0]["klasse"] == "behalten-nuetzlich"
    assert zeilen[0]["thema"] == "Ticket"
    assert zeilen[0]["befund"] == "Bestellbestaetigung Bahn"
    assert zeilen[0]["datei"] == "Screenshot_20221107_125719.png"
    assert len(sende.aufrufe) == 3


def test_unbekannte_klasse_wird_unklar():
    assert triage.klasse_normalisieren("vielleicht-wichtig") == "unklar"
    assert triage.klasse_normalisieren(None) == "unklar"
    assert triage.klasse_normalisieren("") == "unklar"
    assert triage.klasse_normalisieren("behalten") == "unklar"


def test_klasse_ist_tolerant_bei_schreibweise():
    """Gross/Klein, Umlaut und Unterstrich statt Bindestrich sind erlaubt."""
    assert triage.klasse_normalisieren("Behalten-Nützlich") == "behalten-nuetzlich"
    assert triage.klasse_normalisieren("Müll") == "muell"
    assert triage.klasse_normalisieren(" behalten_persoenlich ") == "behalten-persoenlich"


def test_unbekanntes_thema_wird_sonstiges():
    assert triage.thema_normalisieren("Kryptowaehrung") == "Sonstiges"
    assert triage.thema_normalisieren(7) == "Sonstiges"
    assert triage.thema_normalisieren("chat") == "Chat"


def test_fehlende_felder_ergeben_leeren_befund():
    """Eine Antwort ohne die drei Felder bleibt eine gueltige Zeile."""
    einordnung = triage.einordnung_uebernehmen({})
    assert einordnung == {"klasse": "unklar", "thema": "Sonstiges", "befund": ""}


def test_befund_wird_eine_zeile_und_gekuerzt():
    lang = "Zeile eins\n" + ("x" * 300)
    befund = triage.befund_normalisieren(lang)
    assert "\n" not in befund
    assert len(befund) <= triage.BEFUND_MAX


def test_schluessel_wird_aus_dem_befund_entfernt():
    """Ein Modell, das einen Schluessel wiederholt, bringt ihn nicht in die Datei."""
    fremd = "sk-or-v1-" + "a" * 30
    einordnung = triage.einordnung_uebernehmen(
        {"klasse": "muell", "thema": "Chat", "befund": f"Text mit {fremd} darin"})
    assert "sk-or-v1-" not in einordnung["befund"]
    assert "<schluessel-entfernt>" in einordnung["befund"]


# ── Kostenbremse ───────────────────────────────────────────────────────────

def test_bremse_erreicht_ist_rein():
    assert triage.bremse_erreicht(0.2, 0.1) is True
    assert triage.bremse_erreicht(0.05, 0.1) is False
    assert triage.bremse_erreicht(5.0, 0) is False        # 0 = Bremse aus
    assert triage.bremse_erreicht(5.0, None) is False
    assert triage.bremse_erreicht("kaputt", 0.1) is False


def test_kosten_werden_aus_tokens_und_preis_gerechnet():
    assert triage.kosten_berechnen(1_000_000, 0, 0.30, 2.50) == 0.3
    assert triage.kosten_berechnen(0, 1_000_000, 0.30, 2.50) == 2.5
    assert triage.kosten_berechnen(10, 10, None, None) is None


def test_kostenbremse_bricht_vor_dem_naechsten_bild_ab(tmp_path, capsys):
    """Obergrenze erreicht -> kein weiterer Aufruf, bereits Bearbeitetes bleibt."""
    sende = FakeSender(tokens=(1_000_000, 0))            # 1.0 USD je Bild
    assert _lauf(tmp_path, ["--grenze", "5", "--kosten-obergrenze", "1.5",
                            "--preis-ein", "1.0", "--preis-aus", "0"],
                 sende=sende) == 0
    assert len(sende.aufrufe) == 2                       # 3. Aufruf: Bremse
    zeilen = _zeilen(tmp_path / "triage.jsonl")
    assert len(zeilen) == 2
    assert all(z["kosten_usd"] == 1.0 for z in zeilen)
    ausgabe = capsys.readouterr().out
    assert "Kostenbremse" in ausgabe and "sauberer Abbruch" in ausgabe


def test_kostenbremse_aus_bearbeitet_alle(tmp_path):
    sende = FakeSender(tokens=(1_000_000, 0))
    assert _lauf(tmp_path, ["--grenze", "5", "--kosten-obergrenze", "0",
                            "--preis-ein", "1.0", "--preis-aus", "0"],
                 sende=sende) == 0
    assert len(sende.aufrufe) == 5


# ── Ausgabe: JSONL anhangend, Pflichtfelder ────────────────────────────────

def test_jsonl_wird_angehaengt_nicht_ueberschrieben(tmp_path):
    """Ein zweiter Lauf haengt an — die alten Zeilen bleiben erhalten."""
    jsonl = tmp_path / "triage.jsonl"
    jsonl.write_text('{"fileid": 999, "klasse": "muell", "alt": true}\n',
                     encoding="utf-8")
    assert _lauf(tmp_path, ["--grenze", "2"]) == 0
    zeilen = _zeilen(jsonl)
    assert len(zeilen) == 3
    assert zeilen[0]["alt"] is True


def test_zeile_traegt_alle_pflichtfelder(tmp_path):
    assert _lauf(tmp_path, ["--grenze", "1"]) == 0
    zeile = _zeilen(tmp_path / "triage.jsonl")[0]
    for feld in ("datei", "fileid", "klasse", "thema", "befund", "tokens",
                 "kosten_usd", "zeit"):
        assert feld in zeile, f"Pflichtfeld fehlt: {feld}"
    assert zeile["datei"] == "Screenshot_20221107_125719.png"     # nur Dateiname
    assert isinstance(zeile["fileid"], int)
    assert zeile["tokens"] == zeile["tokens_ein"] + zeile["tokens_aus"]
    assert zeile["kosten_usd"] == triage.kosten_berechnen(
        zeile["tokens_ein"], zeile["tokens_aus"],
        triage.PREIS_EIN_STANDARD, triage.PREIS_AUS_STANDARD)
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", zeile["zeit"])


def test_nicht_bilder_werden_uebergangen_unterordner_kommen_mit(tmp_path):
    """desktop.ini fliegt raus, der Unterordner 'Screenshots' zaehlt mit."""
    dienst = FakeDienst()
    gesammelt = triage.screenshots_sammeln(dienst, ["Bilder & Videos", "Screenshots"])
    namen = [e["name"] for e in gesammelt]
    assert "desktop.ini" not in namen
    assert len(gesammelt) == 5                          # 3 direkt + 2 im Unterordner
    assert namen[0].startswith("Screenshot_2022")       # Basisordner zuerst
    assert gesammelt[-1]["ordner"] == "Screenshots"
    assert 999 not in [e["fileid"] for e in gesammelt]  # Nachbarordner zaehlt nicht


def test_erledigte_werden_uebersprungen_wiederholen_erzwingt(tmp_path, capsys):
    sende1 = FakeSender()
    assert _lauf(tmp_path, ["--grenze", "3"], sende=sende1) == 0
    sende2 = FakeSender()
    assert _lauf(tmp_path, ["--grenze", "3"], sende=sende2) == 0
    assert len(sende2.aufrufe) == 0                     # nichts doppelt bezahlt
    assert "uebersprungen" in capsys.readouterr().out
    sende3 = FakeSender()
    assert _lauf(tmp_path, ["--grenze", "3", "--wiederholen"], sende=sende3) == 0
    assert len(sende3.aufrufe) == 3
    assert len(_zeilen(tmp_path / "triage.jsonl")) == 6


def test_fehler_zeile_wird_geschrieben_und_wiederholt(tmp_path):
    """Ein Netzfehler landet als Zeile mit 'fehler' und wird erneut versucht."""
    sende = FakeSender(fehler_bis=99)
    assert _lauf(tmp_path, ["--grenze", "1"], sende=sende) == 0
    zeilen = _zeilen(tmp_path / "triage.jsonl")
    assert len(zeilen) == 1 and "fehler" in zeilen[0]
    assert "klasse" not in zeilen[0]
    sende2 = FakeSender()
    assert _lauf(tmp_path, ["--grenze", "1"], sende=sende2) == 0
    assert len(sende2.aufrufe) == 1                     # Fehler zaehlt nicht als erledigt


def test_pcloud_fehler_beim_thumb_wird_zur_zeile(tmp_path):
    """Scheitert das Vorschaubild, gibt es eine Fehlerzeile statt eines Absturzes."""
    dienst = FakeDienst()
    dienst.thumb_fehler = triage.ScreenshotFehler("kein Vorschaubild (Code 5002)")
    assert _lauf(tmp_path, ["--grenze", "1"], dienst=dienst) == 0
    zeilen = _zeilen(tmp_path / "triage.jsonl")
    assert "Code 5002" in zeilen[0]["fehler"]
    assert "klasse" not in zeilen[0]


# ── Trockenlauf, Schluessel, Schutzpruefungen ──────────────────────────────

def test_trocken_holt_und_sendet_nichts(tmp_path, capsys):
    dienst = FakeDienst()
    dienst.thumb = Stolperfalle()
    assert _lauf(tmp_path, ["--trocken"], dienst=dienst, sende=Stolperfalle(),
                 schluessel=False) == 0
    assert dienst.thumb_aufrufe == []
    assert dienst.liste_aufrufe                      # nur Ordnerlisten gelesen
    assert not (tmp_path / "triage.jsonl").exists()
    assert "Trockenlauf" in capsys.readouterr().out


def test_ohne_schluessel_wird_nichts_gesendet(tmp_path, capsys):
    sende = FakeSender()
    assert _lauf(tmp_path, ["--grenze", "1"], sende=sende, schluessel=False) == 2
    assert sende.aufrufe == []
    assert not (tmp_path / "triage.jsonl").exists()
    assert "OPENROUTER_API_KEY" in capsys.readouterr().out


def test_ausgabe_im_repo_wird_abgelehnt(tmp_path, capsys):
    """Ausgaben gehoeren ausserhalb des Repos — auch im Trockenlauf."""
    ziel = str(REPO / "tmp_screenshots_triage.jsonl")
    sende = FakeSender()
    with pytest.raises(SystemExit) as fehler:
        triage.main(["--ausgabe", ziel, "--trocken"],
                    dienst=FakeDienst(), sende=sende, env_pfade=[])
    assert fehler.value.code == 2
    assert not Path(ziel).exists()
    assert "IM Repo" in capsys.readouterr().out


def test_unbekannte_vorschaugroesse_wird_abgelehnt(tmp_path, capsys):
    sende = FakeSender()
    assert _lauf(tmp_path, ["--groesse", "9999x9999"], sende=sende) == 2
    assert sende.aufrufe == []
    ausgabe = capsys.readouterr().out
    assert "Vorschaugroesse" in ausgabe
    assert "800x800" in ausgabe          # die erlaubten Groessen stehen im Text


def test_groessen_deckeln_sich_mit_dem_dienst():
    """Die erlaubten Groessen dieses Werkzeugs sind genau die des Dienstes.

    800x800 ist der Standard: bei 120x120 blieben Screenshots "unklar", weil
    Text nicht lesbar war (gemessen 27.09.2026).
    """
    quelle = (REPO / "backend" / "app" / "services" / "pcloud_service.py").read_text(
        encoding="utf-8")
    assert 'ERLAUBTE_THUMB_GROESSEN = ("32x32", "120x120", "480x480", "800x800")' in quelle
    assert triage.ERLAUBTE_GROESSEN == ("32x32", "120x120", "480x480", "800x800")
    assert triage.STANDARD_GROESSE == "800x800"


def test_fehlender_ordner_meldet_klartext(tmp_path, capsys):
    leer = FakeDienst(ordner={})
    assert _lauf(tmp_path, ["--grenze", "1"], dienst=leer) == 2
    assert "Screenshot-Ordner nicht gefunden" in capsys.readouterr().out


# ── Die harten Zusicherungen: kein Loeschen, keine Bilddatei ───────────────

def test_kein_loesch_oder_verschiebe_befehl_im_quelltext():
    """Es gibt im Werkzeug keinen Befehl zum Loeschen oder Verschieben."""
    quelle = WERKZEUG.read_text(encoding="utf-8")
    verboten = ("deletefile", "deletefolder", "unlinkdupe", "movefile",
                "renamefile", "renamefolder", "os.remove", "os.unlink",
                "os.rmdir", "shutil.rmtree")
    for wort in verboten:
        assert wort not in quelle, f"verbotener Befehl im Quelltext: {wort}"


def test_keine_bilddatei_wird_geschrieben(tmp_path):
    """Weder im Quelltext noch im Lauf entsteht eine Bilddatei."""
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert not re.search(r"open\([^)]*[\"'](wb|ab|w\+b)[\"']", quelle)
    assert _lauf(tmp_path, ["--grenze", "2"]) == 0
    geschrieben = [p.name for p in tmp_path.iterdir()]
    assert "triage.jsonl" in geschrieben
    assert not [n for n in geschrieben
                if n.lower().endswith(triage.BILD_ENDUNGEN)]


def test_zaehlung_und_beispiele_sind_rein():
    """Zusammenfassung und Beispiele kommen ohne I/O aus."""
    ergebnisse = [{"klasse": "muell", "thema": "Systemdialog", "datei": "a.png",
                   "ordner": "", "befund": "Dialog"},
                  {"klasse": "behalten-persoenlich", "thema": "Chat",
                   "datei": "b.png", "ordner": "", "befund": "Chatverlauf"}]
    zahlen = triage.zusammenfassung_zaehlen(ergebnisse)
    assert zahlen["je_klasse"]["muell"] == 1
    assert zahlen["je_klasse"]["unklar"] == 0
    assert zahlen["je_thema"]["Chat"] == 1
    assert sum(zahlen["je_klasse"].values()) == 2
    beispiele = triage.beispiele_je_klasse(ergebnisse, anzahl=5)
    assert beispiele["muell"][0]["datei"] == "a.png"
    assert beispiele["unklar"] == []
