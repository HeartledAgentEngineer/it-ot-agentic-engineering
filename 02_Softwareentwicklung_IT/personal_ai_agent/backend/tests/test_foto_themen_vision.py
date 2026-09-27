"""Pruefungen fuer foto_themen_vision.py (Themen-Stufe Teil 2) — alles OHNE Netz.

Kein echter OpenRouter-Aufruf: der Transport ist entweder eine Attrappe
(``FakeSender`` fuer den ganzen Lauf, ``FakePost`` fuer ``sende_aufruf``) oder
in der autouse-Fixture komplett gesperrt (``httpx.post``/``httpx.get`` werfen).
Ein erfundener Schluessel liegt in einer temporaeren .env bzw. kommt ueber
``env_pfade`` herein — niemals der echte. Alle Ausgaben gehen nach tmp_path,
nie nach ~/foto_sortierung und nie ins Repo.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_foto_themen_vision.py -q
"""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path

import pytest
from PIL import Image

WERKZEUG = (Path(__file__).resolve().parents[2]
            / "tools" / "foto_sortierung" / "foto_themen_vision.py")
REPO = Path(__file__).resolve().parents[2]


def _laden():
    spez = importlib.util.spec_from_file_location("foto_themen_vision", WERKZEUG)
    assert spez is not None and spez.loader is not None, (
        f"Werkzeug nicht gefunden: {WERKZEUG}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


vision = _laden()

SCHLUESSEL = "test-schluessel-nicht-echt-abcdef-1234567890"
MODELL = "google/gemini-2.5-flash"
SCHLUESSEL_VARIABLE = "OPENROUTER_API_KEY"

CSV_FELDER = ["jahr", "monat", "tag", "datumquelle", "thema", "geraet",
              "ordner", "datei", "motiv", "doppelung", "bytes", "mb"]


# ── Attrappen (kein Netz) ──────────────────────────────────────────────────

class Stolperfalle:
    """Ein Aufruf, der niemals passieren darf (Trockenlauf/Nur-Liste)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Aufruf, obwohl keiner passieren darf!")


class FakeAntwort:
    """Winzige httpx-Antwort-Attrappe."""

    def __init__(self, status_code=200, daten=None, kaputt=False):
        self.status_code = status_code
        self._daten = daten
        self._kaputt = kaputt

    def json(self):
        if self._kaputt:
            raise ValueError("kein JSON")
        return self._daten


class FakePost:
    """httpx.post-Attrappe: kann N Aufrufe lang scheitern oder HTTP-Fehler geben."""

    def __init__(self, status_codes=None, text="{}", daten=None, fehler_bis=0):
        self.status_codes = list(status_codes or [200])
        self.text = text
        self.daten = daten
        self.fehler_bis = fehler_bis
        self.aufrufe = []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.aufrufe.append({"url": url, "json": json, "headers": headers})
        if len(self.aufrufe) <= self.fehler_bis:
            raise RuntimeError("Netz weg (Attrappe)")
        index = min(len(self.aufrufe), len(self.status_codes)) - 1
        status = self.status_codes[index]
        if status != 200:
            return FakeAntwort(status_code=status, daten={})
        if self.daten is not None:
            return FakeAntwort(status_code=200, daten=self.daten)
        return FakeAntwort(status_code=200, daten={
            "model": MODELL,
            "choices": [{"message": {"content": self.text}}],
            "usage": {"prompt_tokens": 111, "completion_tokens": 22},
        })


class FakeSender:
    """OpenRouter-Attrappe fuer ganze Laeufe: je Aufruf eine Antwort."""

    def __init__(self, text=None, tokens=(100, 20), fehler_bis=0,
                 fehlertext="Netz weg (Attrappe)"):
        self.text = text
        self.tokens = tokens
        self.fehler_bis = fehler_bis
        self.fehlertext = fehlertext
        self.aufrufe = []

    def __call__(self, payload, schluessel, basis, versuche=3):
        self.aufrufe.append(payload)
        if len(self.aufrufe) <= self.fehler_bis:
            raise vision.FotoVisionNetzfehler(self.fehlertext)
        text = self.text
        if text is None:
            prompt = payload["messages"][0]["content"][0]["text"]
            treffer = re.search(r"genau (\d+) Kacheln", prompt)
            text = _antwort_text("Familienspaziergang",
                                 int(treffer.group(1)) if treffer else 1)
        return {"text": text, "tokens_ein": self.tokens[0],
                "tokens_aus": self.tokens[1], "modell": MODELL}


@pytest.fixture(autouse=True)
def kein_netz_kein_schluessel(monkeypatch):
    """Kein Schlafen, kein echter Netzaufruf, kein echter Schluessel im Prozess."""
    monkeypatch.setattr(vision, "_warte", lambda sekunden: None)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv(vision.SCHLUESSEL_VARIABLE, raising=False)

    def verboten(*args, **kwargs):
        raise AssertionError("echter Netzaufruf im Test!")

    monkeypatch.setattr(vision.httpx, "post", verboten)
    monkeypatch.setattr(vision.httpx, "get", verboten)


# ── kleine Helfer ──────────────────────────────────────────────────────────

def _jpeg(farbe=(30, 90, 160), groesse=(120, 90)) -> bytes:
    puffer = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(puffer, "JPEG")
    return puffer.getvalue()


def _kachel(nummer, datei, ordner="P:/Geraet"):
    return {"kachel": nummer, "fileid": 900 + nummer, "datei": datei,
            "bytes": 1000 * nummer, "ist_video": False, "ordner": ordner}


def _bogen_daten(titel="2025-01-06_Anlass-01", anzahl=3, jahr=2025,
                 ordner="P:/Geraet"):
    kacheln = [_kachel(i, f"IMG20250106_1200{i:02d}.jpg", ordner)
               for i in range(1, anzahl + 1)]
    return {
        "titel": titel, "jahr": jahr, "datum": "2025-01-06",
        "von": "12:00", "bis": "12:30", "ohne_uhrzeit": False,
        "bogen": titel + ".jpg", "anzahl": anzahl, "anzahl_videos": 0,
        "bytes": sum(k["bytes"] for k in kacheln), "kacheln": kacheln,
    }


def _bogen_anlegen(boegen_dir: Path, titel="2025-01-06_Anlass-01", anzahl=3,
                   jahr=2025, ordner="P:/Geraet") -> dict:
    """Einen fertigen Kontaktbogen (JPEG + JSON) in tmp_path anlegen."""
    ziel_ordner = boegen_dir / str(jahr)
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    (ziel_ordner / f"{titel}.jpg").write_bytes(_jpeg())
    daten = _bogen_daten(titel, anzahl, jahr, ordner)
    (ziel_ordner / f"{titel}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    return daten


def _antwort_text(thema, anzahl, unbrauchbar=(), kurz="Szene im Freien am Tag"):
    return json.dumps({
        "thema": thema,
        "je_kachel": [{"kachel": i, "kurz": kurz,
                       "unbrauchbar": i in set(unbrauchbar)}
                      for i in range(1, anzahl + 1)],
    }, ensure_ascii=False)


def _csv_schreiben(pfad, zeilen) -> str:
    with open(pfad, "w", newline="", encoding="utf-8") as datei:
        schreiber = csv.DictWriter(datei, fieldnames=CSV_FELDER)
        schreiber.writeheader()
        for zeile in zeilen:
            schreiber.writerow(zeile)
    return str(pfad)


def _csv_zeile(datei, ordner="P:/Geraet", motiv=None, doppelung="",
               jahr="2025", monat="1", tag="6"):
    return {"jahr": jahr, "monat": monat, "tag": tag, "datumquelle": "namen",
            "thema": "", "geraet": "Geraet", "ordner": ordner, "datei": datei,
            "motiv": motiv if motiv is not None else datei.lower(),
            "doppelung": doppelung, "bytes": "1000", "mb": "0.01"}


def _env_schreiben(pfad: Path, wert=SCHLUESSEL) -> str:
    pfad.write_text(f'# Probe\n{SCHLUESSEL_VARIABLE}={wert}\n', encoding="utf-8")
    return str(pfad)


def _dateibaum(pfad: Path) -> dict:
    """Alle Dateien unter ``pfad`` mit Hash — fuer 'nichts angefasst'-Pruefungen."""
    ergebnis = {}
    for datei in sorted(pfad.rglob("*")):
        if datei.is_file():
            ergebnis[str(datei)] = hashlib.sha256(datei.read_bytes()).hexdigest()
    return ergebnis


# ── Prompt und Anfrage ─────────────────────────────────────────────────────

def test_prompt_nennt_alle_kachelnummern():
    """Der Prompt zaehlt die Kacheln 1..n ausdruecklich auf (kein Erfinden)."""
    prompt = vision.prompt_bauen(36)
    assert "36" in prompt
    for nummer in range(1, 37):
        assert f"{nummer}" in prompt
    assert "1, 2, 3" in prompt or "1, 2, 3," in prompt
    assert "1 bis 36" in prompt
    assert prompt.count("Kachel") >= 2


def test_prompt_verlangt_genau_das_json_schema():
    """Der Prompt verlangt das JSON-Objekt mit thema/je_kachel/unbrauchbar."""
    prompt = vision.prompt_bauen(4)
    assert "AUSSCHLIESSLICH" in prompt
    assert '"thema"' in prompt and '"je_kachel"' in prompt
    assert '"unbrauchbar"' in prompt and '"hinweis"' in prompt
    assert "Schraegstriche" in prompt
    assert "2 bis 4 deutsche Woerter" in prompt
    assert "keine" in prompt.lower() and "markdown" in prompt.lower()
    assert "1 bis 4" in prompt and "1, 2, 3, 4" in prompt


def test_anfrage_bau_hat_text_und_bild_als_datenurl():
    """Eine Anfrage: content-Array mit Text-Teil und base64-JPEG."""
    daten_uri = "data:image/jpeg;base64,QUJD"
    anfrage = vision.anfrage_bauen(MODELL, daten_uri, 3)
    assert anfrage["model"] == MODELL
    assert len(anfrage["messages"]) == 1
    teile = anfrage["messages"][0]["content"]
    assert [t["type"] for t in teile] == ["text", "image_url"]
    assert teile[0]["text"] == vision.prompt_bauen(3)
    assert teile[1]["image_url"]["url"] == daten_uri
    assert anfrage["temperature"] == 0


# ── Antwort zerlegen ───────────────────────────────────────────────────────

def test_antwort_zerlegen_mit_json_zaun():
    """```json-Zaeune werden entfernt, das Objekt bleibt."""
    text = "```json\n" + _antwort_text("Wintermarkt", 2) + "\n```"
    daten = vision.antwort_zerlegen(text)
    assert daten["thema"] == "Wintermarkt"
    assert len(daten["je_kachel"]) == 2
    assert vision.antwort_zerlegen("```\n{\"thema\": \"X\"}\n```")["thema"] == "X"


def test_antwort_zerlegen_mit_vor_und_nachtext():
    """Vor- und Nachtext wird abgeschnitten — erstes { bis letztes }."""
    text = ("Klar, hier ist das Ergebnis:\n"
            + _antwort_text("Kuchen backen", 1)
            + "\nIch hoffe, das hilft!")
    daten = vision.antwort_zerlegen(text)
    assert daten["thema"] == "Kuchen backen"
    # Auch verschachtelte Objekte bleiben heil:
    daten2 = vision.antwort_zerlegen('{"thema": "X", "je_kachel": [{"kachel": 1, '
                                     '"kurz": "a", "unbrauchbar": false}]}')
    assert daten2["je_kachel"][0]["kachel"] == 1


def test_antwort_zerlegen_kaputter_text_ist_fehler():
    """Unbrauchbarer Text ist ein Fehler — es wird nichts geraten."""
    for kaputt in ["", "   ", "kein JSON dabei", "{das ist kein json}",
                   '{"thema": }', "[1, 2, 3]", '{"thema": "X"']:
        with pytest.raises(vision.FotoVisionFehler):
            vision.antwort_zerlegen(kaputt)


def test_antwort_zerlegen_nicht_text():
    """None statt Text ist ebenfalls ein klarer Fehler."""
    with pytest.raises(vision.FotoVisionFehler):
        vision.antwort_zerlegen(None)


# ── Normalisieren ──────────────────────────────────────────────────────────

def test_thema_wird_normalisiert():
    """Schraegstriche, Mehrfach-Leerraum und Laenge werden bereinigt."""
    assert vision.thema_normalisieren("  Urlaub/Strand  ") == "Urlaub Strand"
    assert vision.thema_normalisieren("Oster\\brunch") == "Oster brunch"
    assert vision.thema_normalisieren("Wandern    im   Schnee") == "Wandern im Schnee"
    assert vision.thema_normalisieren("Bad:Spiegel|putzen?") == "Bad Spiegel putzen"
    assert vision.thema_normalisieren("Wintermarkt\n") == "Wintermarkt"
    assert vision.thema_normalisieren("///") == ""
    assert vision.thema_normalisieren(None) == ""
    lang = vision.thema_normalisieren("W" * 200)
    assert len(lang) == vision.THEMA_MAX_ZEICHEN
    assert vision.thema_normalisieren("  .Wintermarkt-  ") == "Wintermarkt"


def test_kurz_wird_auf_acht_woerter_gekuerzt():
    """Die Kachelbeschreibung bleibt eine Zeile mit hoechstens 8 Woertern."""
    lang = "eins zwei drei vier fuenf sechs sieben acht neun zehn"
    assert vision.kurz_normalisieren(lang) == \
        "eins zwei drei vier fuenf sechs sieben acht"
    assert vision.kurz_normalisieren("Zeile\numbruch") == "Zeile umbruch"
    assert vision.kurz_normalisieren(None) == ""


# ── Bild als Daten-URL ─────────────────────────────────────────────────────

def test_bild_daten_uri_liest_nur_im_speicher(tmp_path):
    """Das JPEG kommt als data-URL zurueck — ohne neue Datei daneben."""
    jpg = tmp_path / "bogen.jpg"
    roh = _jpeg((200, 10, 10))
    jpg.write_bytes(roh)
    vorher = _dateibaum(tmp_path)

    uri = vision.bild_daten_uri(str(jpg))

    assert uri.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == roh
    assert _dateibaum(tmp_path) == vorher, "es wurde eine Datei angelegt"


def test_bild_daten_uri_leeres_bild_ist_fehler(tmp_path):
    """Ein leerer Bogen ist ein Fehler, keine leere Anfrage."""
    jpg = tmp_path / "leer.jpg"
    jpg.write_bytes(b"")
    with pytest.raises(vision.FotoVisionFehler):
        vision.bild_daten_uri(str(jpg))


# ── Kacheln aus der Antwort ────────────────────────────────────────────────

def test_kacheln_uebernehmen_ergaenzt_dateinamen():
    """Die Kacheln tragen Nummer, Kurztext und den Dateinamen aus dem Bogen."""
    bogen = _bogen_daten(anzahl=3)
    daten = json.loads(_antwort_text("Wintermarkt", 3, unbrauchbar=[2]))
    kacheln = vision.kacheln_uebernehmen(daten, bogen)
    assert [k["kachel"] for k in kacheln] == [1, 2, 3]
    assert kacheln[1]["unbrauchbar"] is True
    assert kacheln[0]["unbrauchbar"] is False
    assert kacheln[2]["datei"] == bogen["kacheln"][2]["datei"]
    assert kacheln[0]["fileid"] == bogen["kacheln"][0]["fileid"]
    assert all(k["ordner"] == "P:/Geraet" for k in kacheln)


def test_kacheln_verwirft_erfundene_nummern():
    """Kachelnummern ausserhalb 1..n werden verworfen, gueltige bleiben."""
    bogen = _bogen_daten(anzahl=2)
    daten = {"thema": "X", "je_kachel": [
        {"kachel": 99, "kurz": "erfunden", "unbrauchbar": False},
        {"kachel": 1, "kurz": "echt", "unbrauchbar": False},
        {"kachel": 0, "kurz": "null", "unbrauchbar": False},
        "kein Objekt",
    ]}
    kacheln = vision.kacheln_uebernehmen(daten, bogen)
    assert [k["kachel"] for k in kacheln] == [1]
    assert kacheln[0]["verworfen"] == 3


def test_kacheln_ohne_gueltige_nummer_ist_fehler():
    """Nennt die Antwort keine gueltige Kachel, ist sie unbrauchbar."""
    bogen = _bogen_daten(anzahl=2)
    with pytest.raises(vision.FotoVisionFehler):
        vision.kacheln_uebernehmen({"thema": "X"}, bogen)
    with pytest.raises(vision.FotoVisionFehler):
        vision.kacheln_uebernehmen({"thema": "X", "je_kachel": []}, bogen)
    with pytest.raises(vision.FotoVisionFehler):
        vision.kacheln_uebernehmen(
            {"thema": "X", "je_kachel": [{"kachel": 7, "kurz": "a"}]}, bogen)


def test_kacheln_verwirft_doppelte_nummern_erster_bleibt():
    """Doppelte Kachelnummer: der ERSTE Eintrag bleibt, jede weitere = verworfen."""
    bogen = _bogen_daten(anzahl=2)
    daten = {"thema": "X", "je_kachel": [
        {"kachel": 1, "kurz": "erster", "unbrauchbar": False},
        {"kachel": 1, "kurz": "zweiter", "unbrauchbar": False},
        {"kachel": 2, "kurz": "echt", "unbrauchbar": False},
    ]}
    kacheln = vision.kacheln_uebernehmen(daten, bogen)
    assert [k["kachel"] for k in kacheln] == [1, 2]
    assert kacheln[0]["kurz"] == "erster"        # der erste Eintrag gewinnt
    assert kacheln[0]["verworfen"] == 1          # die Doppelung zaehlt als verworfen
    assert not any(k.get("kurz") == "zweiter" for k in kacheln)


def test_unsinnige_eintraege_je_art_getrennt_gezaehlt():
    """Nicht-Objekt, fehlende und erfundene Nummer: jede Art zaehlt als verworfen."""
    bogen = _bogen_daten(anzahl=2)
    kein_objekt = vision.kacheln_uebernehmen(
        {"thema": "X", "je_kachel": ["kein Objekt", {"kachel": 1}]}, bogen)
    assert kein_objekt[0]["verworfen"] == 1
    erfunden = vision.kacheln_uebernehmen(
        {"thema": "X", "je_kachel": [{"kachel": 99}, {"kachel": 1}]}, bogen)
    assert erfunden[0]["verworfen"] == 1
    ohne_nummer = vision.kacheln_uebernehmen(
        {"thema": "X", "je_kachel": [{"kurz": "ohne nummer"}, {"kachel": 1}]}, bogen)
    assert ohne_nummer[0]["verworfen"] == 1


def test_doppelte_kachel_ist_unvollstaendig_aber_fehlende_null(tmp_path):
    """Doppelung -> verworfen gezaehlt, unvollstaendig true (fehlende bleibt 0)."""
    jpg = tmp_path / "bogen.jpg"
    jpg.write_bytes(_jpeg())
    bogen = _bogen_daten(anzahl=2)
    text = json.dumps({"thema": "Wintermarkt am See", "je_kachel": [
        {"kachel": 1, "kurz": "Szene", "unbrauchbar": False},
        {"kachel": 1, "kurz": "Szene", "unbrauchbar": False},
        {"kachel": 2, "kurz": "Szene", "unbrauchbar": False}]},
        ensure_ascii=False)
    ergebnis = vision.anlass_verarbeiten(bogen, str(jpg), SCHLUESSEL,
                                         FakeSender(text=text))
    assert [k["kachel"] for k in ergebnis["kacheln"]] == [1, 2]
    assert ergebnis["fehlende_kacheln"] == 0     # beide Bogenkacheln sind da
    assert ergebnis["unvollstaendig"] is True    # aber ein Eintrag war unsinnig
    assert ergebnis["unbrauchbare_kacheln"] == 0


def test_unbrauchbare_kachel_bleibt_und_wird_getrennt_gezaehlt(tmp_path):
    """unbrauchbar: true bleibt erhalten, zaehlt NICHT als fehlend, Zaehler steht."""
    jpg = tmp_path / "bogen.jpg"
    jpg.write_bytes(_jpeg())
    bogen = _bogen_daten(anzahl=3)
    ergebnis = vision.anlass_verarbeiten(
        bogen, str(jpg), SCHLUESSEL,
        FakeSender(text=_antwort_text("Wintermarkt am See", 3, unbrauchbar=[2])))
    assert len(ergebnis["kacheln"]) == 3
    assert ergebnis["kacheln"][1]["unbrauchbar"] is True     # behalten, markiert
    assert ergebnis["unbrauchbare_kacheln"] == 1
    assert ergebnis["fehlende_kacheln"] == 0                 # Kachel ist da
    assert ergebnis["unvollstaendig"] is False               # alles gueltig vorhanden


def test_zaehler_unbrauchbare_kacheln_stehen_in_json_und_laufzeile(tmp_path, capsys):
    """unbrauchbare_kacheln steht in der Ausgabe-JSON UND in der Ausgabezeile."""
    um = _lauf_umgebung(tmp_path)                            # Bogen mit 3 Kacheln
    code = vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"],
                       sende=FakeSender(text=_antwort_text("Wintermarkt am See", 3,
                                                           unbrauchbar=[1, 3])),
                       env_pfade=[um["env"]])
    ausgabe = capsys.readouterr().out
    assert code == 0
    daten = json.loads((um["ausgabe"] / "themen" / "2025" /
                        "2025-01-06_Anlass-01.json").read_text(encoding="utf-8"))
    assert daten["unbrauchbare_kacheln"] == 2
    assert daten["fehlende_kacheln"] == 0
    assert daten["unvollstaendig"] is False
    assert "unbrauchbare_kacheln: 2" in ausgabe


# ── Kosten ─────────────────────────────────────────────────────────────────

def test_kosten_nur_mit_preisen():
    """Ohne Preise gibt es keine Kostenzahl (keine Erfindung)."""
    assert vision.kosten_berechnen(1000, 500, None, None) is None
    assert vision.kosten_berechnen(1000, 500, 0.1, None) is None
    assert vision.kosten_berechnen(1000, 500, None, 0.4) is None
    assert vision.kosten_berechnen(1_000_000, 2_000_000, 0.1, 0.4) == 0.9
    assert vision.kosten_berechnen(0, 0, 0.1, 0.4) == 0.0


# ── Transport (sende_aufruf) ───────────────────────────────────────────────

def test_sende_aufruf_liest_text_und_tokens():
    """Ein erfolgreicher Aufruf liefert Text, Tokens und Modell."""
    post = FakePost(text="hallo")
    ergebnis = vision.sende_aufruf({"model": MODELL}, SCHLUESSEL,
                                   basis="https://beispiel.test/api/v1",
                                   post=post)
    assert ergebnis["text"] == "hallo"
    assert ergebnis["tokens_ein"] == 111 and ergebnis["tokens_aus"] == 22
    assert ergebnis["modell"] == MODELL
    assert len(post.aufrufe) == 1
    assert post.aufrufe[0]["url"] == "https://beispiel.test/api/v1/chat/completions"
    assert post.aufrufe[0]["headers"]["Authorization"] == f"Bearer {SCHLUESSEL}"


def test_sende_aufruf_wiederholt_429():
    """429 (zu viele Anfragen) wird wiederholt und bricht nichts ab."""
    post = FakePost(status_codes=[429, 200], text="endlich")
    ergebnis = vision.sende_aufruf({"model": MODELL}, SCHLUESSEL, post=post)
    assert ergebnis["text"] == "endlich"
    assert len(post.aufrufe) == 2


def test_sende_aufruf_wiederholt_netzausfall_und_gibt_dann_auf():
    """Nach drei Netzfehlern: klare Meldung, kein fremder Fehlertext."""
    post = FakePost(fehler_bis=99)
    with pytest.raises(vision.FotoVisionNetzfehler) as fehler:
        vision.sende_aufruf({"model": MODELL}, SCHLUESSEL, post=post)
    assert len(post.aufrufe) == 3
    assert "nach 3 Versuchen" in str(fehler.value)
    assert "Netz weg" not in str(fehler.value)


def test_sende_aufruf_http_fehler_drei_versuche():
    """Auch ein dauerhafter HTTP-Fehler endet nach drei Versuchen."""
    post = FakePost(status_codes=[500, 500, 500])
    with pytest.raises(vision.FotoVisionNetzfehler) as fehler:
        vision.sende_aufruf({"model": MODELL}, SCHLUESSEL, post=post)
    assert len(post.aufrufe) == 3
    assert "HTTP 500" in str(fehler.value)


def test_sende_aufruf_ohne_schluessel():
    """Ohne Schluessel wird gar nicht erst gesendet."""
    post = FakePost()
    with pytest.raises(vision.FotoVisionFehler):
        vision.sende_aufruf({"model": MODELL}, "", post=post)
    assert post.aufrufe == []


def test_schluessel_taucht_in_keiner_fehlermeldung_auf():
    """Selbst wenn ein fremder Fehler den Schluessel traegt: entschaerft."""
    def boese(*args, **kwargs):
        raise RuntimeError(f"kaputt bei /chat/completions?token={SCHLUESSEL}")

    with pytest.raises(vision.FotoVisionFehler) as fehler:
        vision.sende_aufruf({"model": MODELL}, SCHLUESSEL, post=boese)
    assert SCHLUESSEL not in str(fehler.value)
    assert SCHLUESSEL not in repr(fehler.value)
    assert vision.ohne_schluessel(f"leak {SCHLUESSEL} hier", SCHLUESSEL) == \
        "leak *** hier"


# ── Schluessel auffinden ───────────────────────────────────────────────────

def test_schluessel_finden_liest_env_und_faellt_nicht_aus(tmp_path):
    """Der Schluessel kommt aus der .env — fehlend heisst leer, nicht Absturz."""
    env = tmp_path / "probe.env"
    env.write_text(f'{SCHLUESSEL_VARIABLE}="{SCHLUESSEL}"\n', encoding="utf-8")
    assert vision.schluessel_finden([str(env)]) == SCHLUESSEL
    assert vision.schluessel_finden([str(tmp_path / "gibtsnicht.env")]) == ""
    assert vision.env_variable_lesen(str(env), "ANDERE_VARIABLE") == ""
    # Die Suchreihenfolge nennt backend/.env und die Workspace-Wurzel als Rueckfall.
    orte = vision.schluessel_pfade()
    assert any(o.endswith("backend\\.env") or o.endswith("backend/.env") for o in orte)
    assert vision.WORKSPACE_ENV.endswith(".env")


# ── Fortsetzungspunkt (themen.jsonl) ──────────────────────────────────────

def test_erledigthemen_liest_und_ueberspringt_kaputte_zeilen(tmp_path):
    """themen.jsonl ist der Fortsetzungspunkt; kaputte Zeilen stören nicht."""
    jsonl = tmp_path / "themen.jsonl"
    jsonl.write_text(
        '{"titel": "A", "thema": "Wintermarkt"}\n'
        "keine json zeile\n"
        "\n"
        '{"titel": "B", "fehler": "HTTP 500"}\n'
        '{"titel": "A", "thema": "Neuer Markt"}\n',
        encoding="utf-8")
    erledigt = vision.erledigthemen(str(jsonl))
    assert set(erledigt) == {"A", "B"}
    assert erledigt["A"]["thema"] == "Neuer Markt"      # letzte Zeile gewinnt
    assert vision.ist_erledigt(erledigt["A"]) is True
    assert vision.ist_erledigt(erledigt["B"]) is False   # Fehler wird wiederholt
    assert vision.ist_erledigt(None) is False
    assert vision.erledigthemen(str(tmp_path / "gibtsnicht.jsonl")) == {}


# ── Ein Anlass komplett (ohne Netz) ────────────────────────────────────────

def test_anlass_verarbeiten_liefert_ausgabeform(tmp_path):
    """Ein Anlass = ein Aufruf; das Ergebnis traegt alles fuer die Ausgabedatei."""
    jpg = tmp_path / "2025-01-06_Anlass-01.jpg"
    jpg.write_bytes(_jpeg())
    bogen = _bogen_daten(anzahl=3)
    sender = FakeSender(text=_antwort_text("Wintermarkt am See", 3,
                                           unbrauchbar=[2]))
    ergebnis = vision.anlass_verarbeiten(bogen, str(jpg), SCHLUESSEL, sender,
                                        modell=MODELL)
    assert len(sender.aufrufe) == 1
    assert ergebnis["thema"] == "Wintermarkt am See"
    assert ergebnis["modell"] == MODELL
    assert ergebnis["tokens_ein"] == 100 and ergebnis["tokens_aus"] == 20
    assert ergebnis["kosten_usd"] is None              # keine Preise gesetzt
    assert ergebnis["dauer_s"] >= 0
    assert ergebnis["anzahl"] == 3
    assert len(ergebnis["kacheln"]) == 3
    assert ergebnis["kacheln"][2]["datei"] == bogen["kacheln"][2]["datei"]
    assert "Wintermarkt" in ergebnis["rohtext"]        # Rohtext wird aufbewahrt
    # Das Bild steckt nur in der Anfrage, nie in der Ausgabe:
    assert "data:image" not in json.dumps(ergebnis)


def test_anlass_verarbeiten_thema_fehlt_ist_fehler(tmp_path):
    """Ohne brauchbares thema wird nichts ausgegeben — klarer Fehler."""
    jpg = tmp_path / "bogen.jpg"
    jpg.write_bytes(_jpeg())
    with pytest.raises(vision.FotoVisionFehler):
        vision.anlass_verarbeiten(
            _bogen_daten(), str(jpg), SCHLUESSEL,
            FakeSender(text=_antwort_text("///", 3)))


def test_anlass_verarbeiten_fehlender_bogen_ist_fehler(tmp_path):
    """Ein nicht lesbarer Bogen ist ein Fehler, keine leere Anfrage."""
    with pytest.raises(vision.FotoVisionFehler):
        vision.anlass_verarbeiten(_bogen_daten(), str(tmp_path / "weg.jpg"),
                                  SCHLUESSEL, Stolperfalle())


# ── Kommandozeile: ganz ohne Netz ─────────────────────────────────────────

def _lauf_umgebung(tmp_path):
    """Boegen + CSV + Ausgabe in tmp_path — ein Anlass mit drei Kacheln."""
    boegen = tmp_path / "boegen"
    bogen = _bogen_anlegen(boegen, "2025-01-06_Anlass-01", anzahl=3)
    zeilen = [_csv_zeile(k["datei"], ordner=k["ordner"]) for k in bogen["kacheln"]]
    csv_pfad = _csv_schreiben(tmp_path / "sortierschluessel.csv", zeilen)
    return {"boegen": boegen, "csv": csv_pfad, "ausgabe": tmp_path / "ausgabe",
            "bogen": bogen, "env": _env_schreiben(tmp_path / "probe.env")}


def test_cli_schreibt_thema_json_jsonl_und_csv(tmp_path, capsys):
    """Ein Lauf schreibt Einzeldatei, Fortsetzungspunkt und CSV-Kopie."""
    um = _lauf_umgebung(tmp_path)
    sender = FakeSender(text=_antwort_text("Wintermarkt am See", 3))
    code = vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"],
                       sende=sender, env_pfade=[um["env"]])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert len(sender.aufrufe) == 1                     # EIN Aufruf je Anlass
    ziel = um["ausgabe"] / "themen" / "2025" / "2025-01-06_Anlass-01.json"
    assert ziel.exists()
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert daten["thema"] == "Wintermarkt am See"
    assert daten["titel"] == "2025-01-06_Anlass-01"
    assert daten["rohtext"]
    assert len(daten["kacheln"]) == 3
    assert daten["kacheln"][1]["datei"] == um["bogen"]["kacheln"][1]["datei"]

    jsonl = um["ausgabe"] / "themen.jsonl"
    zeilen = [json.loads(z) for z in jsonl.read_text(encoding="utf-8").splitlines()]
    assert len(zeilen) == 1 and zeilen[0]["titel"] == "2025-01-06_Anlass-01"
    assert zeilen[0]["thema"] == "Wintermarkt am See"
    assert "Wintermarkt am See" in ausgabe
    assert "angesehen: 1" in ausgabe

    csv_ziel = um["ausgabe"] / "sortierschluessel_themen.csv"
    assert csv_ziel.exists()
    gelesen = list(csv.DictReader(csv_ziel.open(encoding="utf-8")))
    assert len(gelesen) == 3
    assert {z["thema"] for z in gelesen} == {"Wintermarkt am See"}
    assert {z["thema_quelle"] for z in gelesen} == {"2025-01-06_Anlass-01"}
    assert "thema_quelle" in csv_ziel.read_text(encoding="utf-8").splitlines()[0]


def test_zweiter_lauf_ueberspringt_und_wiederholen_erzwingt(tmp_path, capsys):
    """Idempotent: zweiter Lauf sendet nichts; --wiederholen erzwingt es."""
    um = _lauf_umgebung(tmp_path)
    sender = FakeSender(text=_antwort_text("Wintermarkt am See", 3))
    args = ["--boegen", str(um["boegen"]), "--csv", um["csv"],
            "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"]

    assert vision.main(args, sende=sender, env_pfade=[um["env"]]) == 0
    capsys.readouterr()
    assert vision.main(args, sende=sender, env_pfade=[um["env"]]) == 0
    ausgabe = capsys.readouterr().out
    assert len(sender.aufrufe) == 1                     # kein zweiter Aufruf
    assert "uebersprungen: 1" in ausgabe
    jsonl = um["ausgabe"] / "themen.jsonl"
    assert len(jsonl.read_text(encoding="utf-8").splitlines()) == 1

    assert vision.main(args + ["--wiederholen"], sende=sender,
                       env_pfade=[um["env"]]) == 0
    capsys.readouterr()
    assert len(sender.aufrufe) == 2
    assert len(jsonl.read_text(encoding="utf-8").splitlines()) == 2


def test_trockenlauf_sendet_nichts(tmp_path, capsys):
    """--trocken: kein Aufruf, keine Datei — und ohne Schluessel benutzbar."""
    um = _lauf_umgebung(tmp_path)
    code = vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025",
                        "--trocken"], sende=Stolperfalle(),
                       env_pfade=[str(tmp_path / "leer.env")])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "Trockenlauf" in ausgabe
    assert "2025-01-06_Anlass-01" in ausgabe
    assert "wuerde gesendet" in ausgabe
    assert not um["ausgabe"].exists()


def test_nur_liste_sendet_nichts(tmp_path, capsys):
    """--nur-liste zeigt die Boegen und ihre Ziele, sonst nichts."""
    um = _lauf_umgebung(tmp_path)
    code = vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025",
                        "--nur-liste"], sende=Stolperfalle(),
                       env_pfade=[str(tmp_path / "leer.env")])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "Nur-Liste" in ausgabe
    assert "2025-01-06_Anlass-01" in ausgabe
    assert "themen" in ausgabe and ".json" in ausgabe
    assert not um["ausgabe"].exists()


def test_ohne_schluessel_exit_2_und_nichts_gesendet(tmp_path, capsys):
    """Kein Schluessel auffindbar: klare Meldung, Exit 2, kein Aufruf."""
    um = _lauf_umgebung(tmp_path)
    leeres_env = tmp_path / "probe-leer.env"
    leeres_env.write_text("ANDERE=1\n", encoding="utf-8")
    code = vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"],
                       sende=Stolperfalle(), env_pfade=[str(leeres_env)])
    ausgabe = capsys.readouterr().out
    assert code == 2
    assert SCHLUESSEL_VARIABLE in ausgabe
    assert "NICHTS gesendet" in ausgabe
    assert not um["ausgabe"].exists()


def test_fehlgeschlagener_anlass_wird_festgehalten_und_lauf_geht_weiter(tmp_path, capsys):
    """Nach drei Versuchen: Anlass als fehlerhaft in themen.jsonl, weiter."""
    boegen = tmp_path / "boegen"
    _bogen_anlegen(boegen, "2025-01-06_Anlass-01", anzahl=2)
    _bogen_anlegen(boegen, "2025-01-07_Anlass-01", anzahl=2, ordner="P:/Zweitgeraet")
    csv_pfad = _csv_schreiben(tmp_path / "s.csv", [
        _csv_zeile("IMG20250106_120001.jpg", ordner="P:/Geraet"),
        _csv_zeile("IMG20250107_120001.jpg", ordner="P:/Zweitgeraet")])
    sender = FakeSender(fehler_bis=1,
                        text=_antwort_text("Wintermarkt am See", 2))
    code = vision.main(["--boegen", str(boegen), "--csv", csv_pfad,
                        "--ausgabe", str(tmp_path / "ausgabe"), "--jahr", "2025"],
                       sende=sender, env_pfade=[_env_schreiben(tmp_path / "e.env", "k")])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert len(sender.aufrufe) == 2                     # erster scheitert, zweiter laeuft
    assert "FEHLER" in ausgabe
    zeilen = [json.loads(z) for z in
              (tmp_path / "ausgabe" / "themen.jsonl").read_text(
                  encoding="utf-8").splitlines()]
    assert len(zeilen) == 2
    assert zeilen[0]["fehler"] and zeilen[0]["titel"] == "2025-01-06_Anlass-01"
    assert zeilen[1]["thema"] == "Wintermarkt am See"
    assert "fehlgeschlagen: 1" in ausgabe and "angesehen: 1" in ausgabe
    # Der Fehler-Anlass bleibt offen: naechster Lauf versucht ihn erneut.
    erledigt = vision.erledigthemen(str(tmp_path / "ausgabe" / "themen.jsonl"))
    assert vision.ist_erledigt(erledigt["2025-01-06_Anlass-01"]) is False


def test_unbrauchbare_antwort_wird_als_fehler_festgehalten(tmp_path, capsys):
    """Unsinn statt JSON: kein Absturz, sondern eine Fehlerzeile."""
    um = _lauf_umgebung(tmp_path)
    code = vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"],
                       sende=FakeSender(text="Ich sehe leider nichts."),
                       env_pfade=[um["env"]])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "FEHLER" in ausgabe
    ziel = um["ausgabe"] / "themen" / "2025" / "2025-01-06_Anlass-01.json"
    assert not ziel.exists()
    zeile = json.loads((um["ausgabe"] / "themen.jsonl").read_text(
        encoding="utf-8").splitlines()[0])
    assert "JSON" in zeile["fehler"]


def test_anlass_und_limit_waehlen_aus(tmp_path, capsys):
    """--anlass greift genau einen Bogen; --limit begrenzt die Auswahl."""
    boegen = tmp_path / "boegen"
    _bogen_anlegen(boegen, "2025-01-06_Anlass-01", anzahl=1)
    _bogen_anlegen(boegen, "2025-02-21_Anlass-01", anzahl=1)
    csv_pfad = _csv_schreiben(tmp_path / "s.csv", [
        _csv_zeile("IMG20250106_120001.jpg"),
        _csv_zeile("IMG20250221_120001.jpg")])
    sender = FakeSender(text=_antwort_text("Wintermarkt am See", 1))
    args = ["--boegen", str(boegen), "--csv", csv_pfad,
            "--ausgabe", str(tmp_path / "ausgabe")]

    assert vision.main(args + ["--limit", "1"], sende=sender,
                       env_pfade=[_env_schreiben(tmp_path / "e.env", "k")]) == 0
    capsys.readouterr()
    assert len(sender.aufrufe) == 1
    assert (tmp_path / "ausgabe" / "themen" / "2025" /
            "2025-01-06_Anlass-01.json").exists()

    assert vision.main(args + ["--anlass", "2025-02-21_Anlass-01"], sende=sender,
                       env_pfade=[str(tmp_path / "e.env")]) == 0
    capsys.readouterr()
    assert len(sender.aufrufe) == 2
    assert (tmp_path / "ausgabe" / "themen" / "2025" /
            "2025-02-21_Anlass-01.json").exists()


def test_fehlende_csv_und_fehlende_boegen_exit_2(tmp_path, capsys):
    """Fehlende Eingaben werden klar gemeldet, nicht ueberfahren."""
    boegen = tmp_path / "boegen"
    _bogen_anlegen(boegen, "2025-01-06_Anlass-01", anzahl=1)
    code = vision.main(["--boegen", str(boegen),
                        "--csv", str(tmp_path / "gibtsnicht.csv"),
                        "--ausgabe", str(tmp_path / "ausgabe")],
                       sende=Stolperfalle())
    assert code == 2
    assert "Sortierschluessel nicht gefunden" in capsys.readouterr().out

    csv_pfad = _csv_schreiben(tmp_path / "s.csv", [_csv_zeile("a.jpg")])
    code = vision.main(["--boegen", str(tmp_path / "keine-boegen"),
                        "--csv", csv_pfad, "--ausgabe", str(tmp_path / "ausgabe")],
                       sende=Stolperfalle())
    assert code == 2
    assert "Kontaktboegen nicht gefunden" in capsys.readouterr().out


def test_halb_fertiger_bogen_wird_nicht_angesehen(tmp_path, capsys):
    """Ohne JPEG gehört der Bogen nicht zur Auswahl (kein halber Blick)."""
    boegen = tmp_path / "boegen"
    _bogen_anlegen(boegen, "2025-01-06_Anlass-01", anzahl=1)
    (boegen / "2025" / "2025-01-07_Anlass-01.json").write_text(
        json.dumps(_bogen_daten("2025-01-07_Anlass-01", 1)), encoding="utf-8")
    csv_pfad = _csv_schreiben(tmp_path / "s.csv", [_csv_zeile("a.jpg")])
    sender = FakeSender(text=_antwort_text("Wintermarkt am See", 1))
    code = vision.main(["--boegen", str(boegen), "--csv", csv_pfad,
                        "--ausgabe", str(tmp_path / "ausgabe"), "--limit", "0"],
                       sende=sender, env_pfade=[_env_schreiben(tmp_path / "e.env", "k")])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert len(sender.aufrufe) == 1
    assert "2025-01-07_Anlass-01" not in ausgabe


# ── CSV-Kopie: Anlass-Thema und Doppelungen ───────────────────────────────

def test_themen_csv_fuellt_anlass_und_zieht_doppelungen_mit(tmp_path):
    """Der Join laeuft ueber (ordner, datei) — Doppelungen ueber motiv."""
    zeilen = [
        _csv_zeile("IMG20250106_120001.jpg", ordner="P:/Geraet"),
        _csv_zeile("IMG20250106_120002.jpg", ordner="P:/Geraet"),
        # Kopie derselben Datei auf einem zweiten Geraet (Spalte doppelung):
        _csv_zeile("IMG20250106_120001.jpg", ordner="P:/Zweitgeraet",
                   doppelung="IMG20250106_120001 (2).jpg"),
        # Zeile ohne Bezug: bleibt leer (kein erfundenes Thema).
        _csv_zeile("Unbekannt_1.jpg", ordner="P:/Geraet"),
    ]
    csv_pfad = _csv_schreiben(tmp_path / "s.csv", zeilen)
    ziel = tmp_path / "sortierschluessel_themen.csv"
    zuordnungen = [
        {"thema": "Wintermarkt am See", "titel": "2025-01-06_Anlass-01",
         "ordner": "P:/Geraet", "datei": "IMG20250106_120001.jpg"},
        {"thema": "Wintermarkt am See", "titel": "2025-01-06_Anlass-01",
         "ordner": "P:/Geraet", "datei": "IMG20250106_120002.jpg"},
    ]
    bericht = vision.themen_csv_schreiben(csv_pfad, str(ziel), zuordnungen)
    assert bericht == {"zeilen": 4, "gefuellt": 2, "vererbt": 1}

    gelesen = list(csv.DictReader(ziel.open(encoding="utf-8")))
    assert [z["thema"] for z in gelesen] == [
        "Wintermarkt am See", "Wintermarkt am See", "Wintermarkt am See", ""]
    assert gelesen[2]["thema_quelle"] == "2025-01-06_Anlass-01"   # geerbt
    assert gelesen[3]["thema_quelle"] == ""
    assert list(gelesen[0].keys()) == CSV_FELDER + ["thema_quelle"]


def test_themen_csv_join_auch_ohne_gross_klein_schreibung(tmp_path):
    """Der Join ueber (ordner, datei) vertraegt abweichende Schreibweise."""
    csv_pfad = _csv_schreiben(tmp_path / "s.csv", [
        _csv_zeile("IMG20250106_120001.JPG", ordner="P:/Geraet")])
    ziel = tmp_path / "themen.csv"
    bericht = vision.themen_csv_schreiben(str(csv_pfad), str(ziel), [
        {"thema": "Wintermarkt am See", "titel": "2025-01-06_Anlass-01",
         "ordner": "p:/geraet", "datei": "img20250106_120001.jpg"}])
    assert bericht["gefuellt"] == 1
    assert next(csv.DictReader(ziel.open(encoding="utf-8")))["thema"] == \
        "Wintermarkt am See"


def test_original_csv_bleibt_byteweise_unveraendert(tmp_path, capsys):
    """Die Eingabe-CSV wird nur gelesen — Byte-Vergleich vor/nach dem Lauf."""
    um = _lauf_umgebung(tmp_path)
    vorher = Path(um["csv"]).read_bytes()
    sender = FakeSender(text=_antwort_text("Wintermarkt am See", 3))
    assert vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"],
                       sende=sender, env_pfade=[um["env"]]) == 0
    capsys.readouterr()
    assert Path(um["csv"]).read_bytes() == vorher
    assert (um["ausgabe"] / "sortierschluessel_themen.csv").exists()


# ── Geheimnis und Repo-Hygiene ────────────────────────────────────────────

def test_schluessel_taucht_in_keiner_ausgabe_auf(tmp_path, capsys):
    """Der Schluessel steht weder auf der Konsole noch in einer Ausgabedatei."""
    um = _lauf_umgebung(tmp_path)
    sender = FakeSender(text=_antwort_text("Wintermarkt am See", 3))
    assert vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"],
                       sende=sender, env_pfade=[um["env"]]) == 0
    konsole = capsys.readouterr().out
    assert SCHLUESSEL not in konsole
    for datei in um["ausgabe"].rglob("*"):
        if datei.is_file():
            assert SCHLUESSEL not in datei.read_text(encoding="utf-8")


def test_kein_bild_und_keine_bogendatei_im_repo(tmp_path, capsys):
    """Ein Lauf legt NICHTS im Werkzeug-/Repo-Ordner an."""
    werkzeug_ordner = WERKZEUG.parent
    vorher = _dateibaum(werkzeug_ordner)
    um = _lauf_umgebung(tmp_path)
    sender = FakeSender(text=_antwort_text("Wintermarkt am See", 3))
    assert vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"],
                       sende=sender, env_pfade=[um["env"]]) == 0
    capsys.readouterr()
    assert _dateibaum(werkzeug_ordner) == vorher
    # Die Vorgabepfade liegen ausserhalb des Repos (private Namen!):
    for pfad in (vision.STANDARD_AUSGABE, vision.STANDARD_BOEGEN,
                 vision.STANDARD_CSV):
        assert not str(pfad).startswith(str(REPO))


def test_ausgaben_bleiben_ausserhalb_des_repos(tmp_path):
    """Zielordner der Ausgabe liegt nie unter dem Repo (Vorgabe geprueft)."""
    assert "foto_sortierung" in vision.STANDARD_AUSGABE
    assert not vision.STANDARD_AUSGABE.startswith(str(REPO))
    assert str(REPO) not in vision.STANDARD_BOEGEN


def test_boegen_auflisten_findet_nur_fertige_paare(tmp_path):
    """Nur JPEG+JSON zusammen zaehlen; Jahr/Anlass filtern sauber."""
    boegen = tmp_path / "boegen"
    _bogen_anlegen(boegen, "2025-01-06_Anlass-01", anzahl=2)
    _bogen_anlegen(boegen, "2024-05-01_Anlass-01", anzahl=1, jahr=2024)
    alle = vision.boegen_auflisten(str(boegen))
    assert [b["titel"] for b in alle] == ["2024-05-01_Anlass-01",
                                          "2025-01-06_Anlass-01"]
    assert [b["titel"] for b in vision.boegen_auflisten(str(boegen), "2025")] == \
        ["2025-01-06_Anlass-01"]
    assert vision.boegen_auflisten(str(boegen), "2025",
                                   "2025-01-06_Anlass-01")[0]["jahr"] == "2025"
    assert vision.boegen_auflisten(str(tmp_path / "nix")) == []


# ── Ausgabeschutz: Ausgaben nie ins Repo ──────────────────────────────────

def test_ausgabe_im_repo_bricht_ab_und_schreibt_nichts(tmp_path, capsys):
    """--ausgabe im Repo: Exit 2, deutsche Meldung, nichts gesendet/angelegt."""
    um = _lauf_umgebung(tmp_path)
    ziel = WERKZEUG.parent / "tmp-ausgabe"          # IM Repo (tools/...)
    assert not ziel.exists()
    with pytest.raises(SystemExit) as abbruch:
        vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                     "--ausgabe", str(ziel), "--jahr", "2025"],
                    sende=Stolperfalle(), env_pfade=[um["env"]])
    assert abbruch.value.code == 2
    ausgabe = capsys.readouterr().out
    assert "IM Repo" in ausgabe and "nicht erlaubt" in ausgabe
    assert "NICHTS" in ausgabe
    assert not ziel.exists(), "im Repo wurde trotz Abbruch etwas angelegt"


def test_ausgabe_im_repo_auch_bei_strich_mix_und_gross_klein(capsys):
    """Vertauschte Trenner und andere Schreibweise werden trotzdem erkannt."""
    verdreht = str(REPO).upper() + "\\tools/foto_sortierung\\TMP-AUSGABE"
    with pytest.raises(SystemExit) as abbruch:
        vision._pruefe_ausgabe(verdreht)
    assert abbruch.value.code == 2
    assert "IM Repo" in capsys.readouterr().out
    # Der Repo-Ordner selbst ist ebenso tabu:
    with pytest.raises(SystemExit) as abbruch:
        vision._pruefe_ausgabe(str(REPO))
    assert abbruch.value.code == 2
    capsys.readouterr()


def test_standard_ausgabe_ausserhalb_des_repos_wird_akzeptiert(tmp_path):
    """Der Standardpfad (und tmp_path) liegt ausserhalb — kein Abbruch."""
    assert vision._pruefe_ausgabe(vision.STANDARD_AUSGABE) == \
        vision.STANDARD_AUSGABE
    assert str(REPO).lower() not in vision.STANDARD_AUSGABE.lower()
    assert vision._pruefe_ausgabe(str(tmp_path / "ausgabe")) is not None


# ── Unvollstaendige Kachelliste + optionaler Hinweis ──────────────────────

def test_fehlende_kacheln_werden_gezaehlt_thema_bleibt(tmp_path, capsys):
    """Ein lückenhaftes je_kachel zaehlt Luecken, wirft das Thema aber nicht weg."""
    um = _lauf_umgebung(tmp_path)                    # Bogen mit 3 Kacheln
    text = json.dumps({"thema": "Wintermarkt am See", "je_kachel": [
        {"kachel": 1, "kurz": "Szene im Freien", "unbrauchbar": False},
        {"kachel": 3, "kurz": "Szene im Freien", "unbrauchbar": False}]},
        ensure_ascii=False)
    code = vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"],
                       sende=FakeSender(text=text), env_pfade=[um["env"]])
    ausgabe = capsys.readouterr().out
    assert code == 0                                 # kein Fehler, kein Abbruch
    daten = json.loads((um["ausgabe"] / "themen" / "2025" /
                        "2025-01-06_Anlass-01.json").read_text(encoding="utf-8"))
    assert daten["thema"] == "Wintermarkt am See"    # Thema trotzdem gesetzt
    assert daten["unvollstaendig"] is True
    assert daten["fehlende_kacheln"] == 1            # Kachel 2 fehlte
    assert [k["kachel"] for k in daten["kacheln"]] == [1, 3]
    assert "unvollstaendig" in ausgabe and "fehlende_kacheln" in ausgabe
    assert "fehlende_kacheln: 1" in ausgabe

    # Gegenprobe: vollstaendige Antwort -> unvollstaendig false, keine Luecke.
    jpg = tmp_path / "bogen.jpg"
    jpg.write_bytes(_jpeg())
    ergebnis = vision.anlass_verarbeiten(
        _bogen_daten(anzahl=3), str(jpg), SCHLUESSEL,
        FakeSender(text=_antwort_text("Vollstaendig", 3)))
    assert ergebnis["unvollstaendig"] is False
    assert ergebnis["fehlende_kacheln"] == 0


def test_hinweis_darf_fehlen_ohne_fehler(tmp_path):
    """Fehlt 'hinweis', bleibt das Feld leer — kein Fehler, Thema steht."""
    jpg = tmp_path / "bogen.jpg"
    jpg.write_bytes(_jpeg())
    bogen = _bogen_daten(anzahl=2)
    ohne = vision.anlass_verarbeiten(bogen, str(jpg), SCHLUESSEL,
                                     FakeSender(text=_antwort_text("Ruhetag", 2)))
    assert ohne["thema"] == "Ruhetag"
    assert ohne["hinweis"] == ""

    mit = json.dumps({"thema": "Ruhetag", "hinweis": "Kachel 2 unscharf",
                      "je_kachel": [{"kachel": i, "kurz": "Szene",
                                     "unbrauchbar": False} for i in (1, 2)]},
                     ensure_ascii=False)
    ergebnis = vision.anlass_verarbeiten(bogen, str(jpg), SCHLUESSEL,
                                         FakeSender(text=mit))
    assert ergebnis["hinweis"] == "Kachel 2 unscharf"


# ── Schluessel/Rohtext-Maskierung vor dem Speichern und Ausgeben ───────────

def test_geheimnis_entfernen_ersetzt_schluessel_und_muster():
    """Der benutzte Schluessel und generische sk_-Muster werden ersetzt."""
    assert vision.geheimnis_entfernen(f"anfang {SCHLUESSEL} ende", SCHLUESSEL) == \
        "anfang <schluessel-entfernt> ende"
    # Text ohne Schluessel bleibt unveraendert — kein Kuerzen, kein Umbau:
    sauber = "Wintermarkt am See, 6 Kacheln, 1 hinweis"
    assert vision.geheimnis_entfernen(sauber, SCHLUESSEL) == sauber
    # Generisches sk_or-…-Muster (>= 20 Zeichen) wird ersetzt:
    assert vision.geheimnis_entfernen(
        "sk-or-v1-0123456789abcdef0123456789abcdef", SCHLUESSEL) == \
        vision.GEHEIMNIS_PLATZHALTER
    assert vision.geheimnis_entfernen("sk-" + "a" * 30, "") == \
        vision.GEHEIMNIS_PLATZHALTER
    assert vision.geheimnis_entfernen(
        "sk_or-" + "b" * 20, "") == vision.GEHEIMNIS_PLATZHALTER
    # Zu kurze Muster (< 20 Zeichen) bleiben stehen:
    assert vision.geheimnis_entfernen("sk-kurz", SCHLUESSEL) == "sk-kurz"
    # Leerer/fehlender Schluessel und Nicht-Text stuerzen nicht ab:
    assert vision.geheimnis_entfernen("nichts zu tun", "") == "nichts zu tun"
    assert vision.geheimnis_entfernen("nichts zu tun", None) == "nichts zu tun"
    assert vision.geheimnis_entfernen(None, SCHLUESSEL) == ""
    assert vision.geheimnis_entfernen(12345, None) == "12345"


def test_anlass_verarbeiten_maskiert_rohtext_thema_und_kacheln(tmp_path):
    """Wiederholt das Modell den Schluessel, steht er nicht im Ergebnis."""
    jpg = tmp_path / "bogen.jpg"
    jpg.write_bytes(_jpeg())
    bogen = _bogen_daten(anzahl=2)
    text = (f"Kontrolle: {SCHLUESSEL}\n"
            + json.dumps({
                "thema": f"See {SCHLUESSEL}",
                "hinweis": f"Bitte {SCHLUESSEL} pruefen",
                "je_kachel": [{"kachel": i, "kurz": f"Bild {SCHLUESSEL}",
                               "unbrauchbar": False} for i in (1, 2)],
            }, ensure_ascii=False))
    ergebnis = vision.anlass_verarbeiten(bogen, str(jpg), SCHLUESSEL,
                                         FakeSender(text=text))
    assert SCHLUESSEL not in ergebnis["rohtext"]
    assert SCHLUESSEL not in ergebnis["thema"]
    assert SCHLUESSEL not in ergebnis["hinweis"]
    assert all(SCHLUESSEL not in k["kurz"] for k in ergebnis["kacheln"])
    assert vision.GEHEIMNIS_PLATZHALTER in ergebnis["rohtext"]


def test_rohtext_mit_schluessel_landet_in_keiner_datei(tmp_path, capsys):
    """Der Schluessel darf in KEINER geschriebenen Datei und nicht konsolen-sein."""
    um = _lauf_umgebung(tmp_path)
    fremd = "sk-or-v1-0123456789abcdef0123456789abcdef"
    rohtext = (f"Zur Kontrolle: {SCHLUESSEL}\n"
               + json.dumps({
                   "thema": "Wintermarkt am See",
                   "hinweis": f"Schluessel {SCHLUESSEL} bitte pruefen",
                   "je_kachel": [{"kachel": i, "kurz": f"Bild {fremd}",
                                  "unbrauchbar": False} for i in (1, 2, 3)],
               }, ensure_ascii=False))
    sender = FakeSender(text=rohtext)
    assert vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"],
                       sende=sender, env_pfade=[um["env"]]) == 0
    konsole = capsys.readouterr().out
    assert SCHLUESSEL not in konsole
    ziel = um["ausgabe"] / "themen" / "2025" / "2025-01-06_Anlass-01.json"
    assert ziel.exists()
    inhalt = ziel.read_text(encoding="utf-8")
    assert SCHLUESSEL not in inhalt
    assert fremd not in inhalt              # auch das generische Muster weg
    assert vision.GEHEIMNIS_PLATZHALTER in inhalt
    for datei in um["ausgabe"].rglob("*"):
        if datei.is_file():
            assert SCHLUESSEL not in datei.read_text(encoding="utf-8")


# ── Schutz der Original-CSV vor der Ausgabe-CSV ───────────────────────────

def test_csv_ziel_gleich_eingabe_exit_2_und_original_unveraendert(tmp_path, capsys):
    """--csv == Ausgabe-CSV: Exit 2, deutsche Meldung, Original byte-gleich."""
    boegen = tmp_path / "boegen"
    bogen = _bogen_anlegen(boegen, "2025-01-06_Anlass-01", anzahl=3)
    zeilen = [_csv_zeile(k["datei"], ordner=k["ordner"]) for k in bogen["kacheln"]]
    csv_pfad = _csv_schreiben(tmp_path / "sortierschluessel_themen.csv", zeilen)
    vorher = Path(csv_pfad).read_bytes()
    env = _env_schreiben(tmp_path / "probe.env")
    # Ausgabeordner = tmp_path -> Ausgabe-CSV ist genau die Eingabe-CSV.
    with pytest.raises(SystemExit) as abbruch:
        vision.main(["--boegen", str(boegen), "--csv", csv_pfad,
                     "--ausgabe", str(tmp_path), "--jahr", "2025"],
                    sende=Stolperfalle(), env_pfade=[env])
    assert abbruch.value.code == 2
    meldung = capsys.readouterr().out
    assert "dieselbe Datei" in meldung
    assert Path(csv_pfad).read_bytes() == vorher        # nichts geschrieben
    assert not (tmp_path / "themen.jsonl").exists()
    assert not (tmp_path / "themen").exists()


def test_csv_kollision_erkennt_schreibweise_und_striche(tmp_path):
    """Gleiche Datei trotz Gross-/Klein und /- statt \\ gilt als Kollision."""
    ziel = tmp_path / "sortierschluessel_themen.csv"
    variante = str(tmp_path).replace("\\", "/") + "/SORTIERSCHLUESSEL_THEMEN.CSV"
    with pytest.raises(SystemExit) as abbruch:
        vision._pruefe_csv_ziel(str(ziel), variante)
    assert abbruch.value.code == 2
    # Andere Dateien loesen nichts aus:
    vision._pruefe_csv_ziel(str(ziel), str(tmp_path / "andere.csv"))


def test_verschiedene_pfade_gehen_weiter_durch(tmp_path, capsys):
    """Standardfall (verschiedene Pfade): Lauf schreibt die CSV-Kopie wie bisher."""
    um = _lauf_umgebung(tmp_path)
    assert Path(um["csv"]).resolve() != \
        (um["ausgabe"] / "sortierschluessel_themen.csv").resolve()
    vorher = Path(um["csv"]).read_bytes()
    sender = FakeSender(text=_antwort_text("Wintermarkt am See", 3))
    assert vision.main(["--boegen", str(um["boegen"]), "--csv", um["csv"],
                        "--ausgabe", str(um["ausgabe"]), "--jahr", "2025"],
                       sende=sender, env_pfade=[um["env"]]) == 0
    capsys.readouterr()
    assert (um["ausgabe"] / "sortierschluessel_themen.csv").exists()
    assert Path(um["csv"]).read_bytes() == vorher
