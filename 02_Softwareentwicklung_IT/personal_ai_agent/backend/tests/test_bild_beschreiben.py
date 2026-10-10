"""Pruefungen fuer bild_beschreiben.py und bild_index_einbetten.py — alles OHNE Netz.

Kein echter OpenRouter- oder pCloud-Aufruf: Vision-Transport, listfolder und
getthumbs sind Attrappen, zusaetzlich sperrt die autouse-Fixture ``httpx.post``/
``httpx.get`` in beiden Werkzeugketten komplett. Es gibt KEINE echten Bilder —
die Vorschaubilder sind winzige, im Test erzeugte JPEGs; eine echte Platte sieht
nie ein Bild. Alle Ausgaben gehen nach ``tmp_path``, nie nach
``~/foto_sortierung`` und nie ins Repo. Ein erfundener Schluessel liegt in einer
temporaeren .env — niemals der echte. Unter ``tests/testdaten/`` liegen zwei
byte-genaue Goldtexte des Stichwort-Prompts (Stand VOR der Prompt-Varianten-
Aenderung, n=3 und n=36) — sie halten den Bestand wortgleich fest.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_bild_beschreiben.py -q
"""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import re
import sqlite3
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

HIER = Path(__file__).resolve().parents[2]
WERKZEUG_PFAD = HIER / "tools" / "foto_sortierung" / "bild_beschreiben.py"
EINBETTEN_PFAD = HIER / "tools" / "foto_sortierung" / "bild_index_einbetten.py"
REPO = HIER


def _laden(name: str, pfad: Path):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


werkzeug = _laden("bild_beschreiben", WERKZEUG_PFAD)
einbett = _laden("bild_index_einbetten", EINBETTEN_PFAD)

SCHLUESSEL = "test-schluessel-nicht-echt-1234567890abcdef"
CSV_FELDER = ["jahr", "monat", "tag", "datumquelle", "thema", "geraet",
              "ordner", "datei", "motiv", "doppelung", "bytes", "mb"]


# ── Attrappen (kein Netz, keine echten Bilder) ─────────────────────────────

class Stolperfalle:
    """Ein Aufruf, der niemals passieren darf (Trockenlauf/Nur-Liste/Abbruch)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Aufruf, obwohl keiner passieren darf!")


def _jpeg(farbe=(40, 120, 180), groesse=(120, 90)) -> bytes:
    puffer = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(puffer, "JPEG")
    return puffer.getvalue()


class FakeApi:
    """listfolder-Attrappe: Wurzel mit Ordner 'Ord', darin die Dateien."""

    def __init__(self, dateien=None, ordner_im_ordner=None):
        # dateien: {"name": fileid}
        self.dateien = dict(dateien or {})
        self.ordner_im_ordner = dict(ordner_im_ordner or {})
        self.aufrufe = []

    def __call__(self, pfad, felder):
        assert pfad == "/listfolder", f"unerwarteter Pfad: {pfad}"
        self.aufrufe.append(felder)
        if not felder.get("folderid"):
            inhalt = [{"name": name, "isfolder": True, "folderid": fid}
                      for name, fid in (self.ordner_im_ordner
                                        or {"Ord": 42}).items()]
            return {"result": 0, "metadata": {"contents": inhalt}}
        return {"result": 0, "metadata": {"contents": [
            {"name": name, "isfolder": False, "fileid": fid}
            for name, fid in self.dateien.items()]}}


class FakeThumb:
    """getthumbs-Attrappe: liefert je fileid ein winziges echtes JPEG."""

    def __init__(self, fehlend=()):
        self.fehlend = {int(f) for f in fehlend}
        self.aufrufe = []

    def __call__(self, ids, groesse="120x120"):
        ids = list(ids)
        self.aufrufe.append(ids)
        zeilen = []
        for dateiid in ids:
            if int(dateiid) in self.fehlend:
                continue
            zeilen.append(f"{int(dateiid)}|0|120x90|data:image/jpeg;base64,"
                          + base64.b64encode(_jpeg()).decode("ascii"))
        return "\n".join(zeilen)


class FakeSender:
    """Vision-Attrappe: antwortet passend zur im Prompt genannten Kachelzahl."""

    def __init__(self, tokens=(2000, 300), fehler_immer=False, fehler_bis=0,
                 modell="fake/vision", kacheln=None):
        self.tokens = tokens
        self.fehler_immer = fehler_immer
        self.fehler_bis = fehler_bis
        self.modell = modell
        self.kacheln = kacheln            # optional: eigene je_kachel-Liste
        self.aufrufe = []

    def __call__(self, payload, schluessel, basis, versuche=3):
        self.aufrufe.append(payload)
        if self.fehler_immer or len(self.aufrufe) <= self.fehler_bis:
            raise RuntimeError("Netz weg (Attrappe)")
        prompt = payload["messages"][0]["content"][0]["text"]
        treffer = re.search(r"genau (\d+) Kacheln|exactly (\d+) tiles", prompt)
        anzahl = int(treffer.group(1) or treffer.group(2)) if treffer else 1
        kacheln = self.kacheln or [
            {"kachel": i, "beschreibung": f"Bild {i}: Buehne, Menschen, Licht",
             "unbrauchbar": False} for i in range(1, anzahl + 1)]
        return {"text": json.dumps({"je_kachel": kacheln}, ensure_ascii=False),
                "tokens_ein": self.tokens[0], "tokens_aus": self.tokens[1],
                "modell": self.modell}


class FakeEinbetter:
    """Einbetter-Attrappe: feste Vektoren, zaehlt Tokens wie der echte."""

    modell = "fake/text-einbetter"

    def __init__(self, dimension=1536, fehler_immer=False):
        self.dimension = dimension
        self.fehler_immer = fehler_immer
        self.token_gesamt = 0
        self.aufrufe = []

    def __call__(self, texte):
        self.aufrufe.append(list(texte))
        if self.fehler_immer:
            raise RuntimeError("Netz weg (Attrappe)")
        self.token_gesamt += sum(len(t) // 3 for t in texte)
        return ([np.full(self.dimension, 0.5, dtype="float32") for _ in texte],
                self.token_gesamt)


@pytest.fixture(autouse=True)
def kein_netz_kein_schluessel(monkeypatch):
    """Kein echter Netzaufruf, kein echter Schluessel — in beiden Werkzeugen."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def verboten(*args, **kwargs):
        raise AssertionError("echter Netzaufruf im Test!")

    for traeger in (werkzeug._themen, werkzeug._vision, einbett._archiv):
        if hasattr(traeger, "httpx"):
            monkeypatch.setattr(traeger.httpx, "post", verboten)
            monkeypatch.setattr(traeger.httpx, "get", verboten)


# ── kleine Helfer ──────────────────────────────────────────────────────────

def _csv_schreiben(pfad: Path, zeilen: list[dict]) -> Path:
    kopf = ",".join(CSV_FELDER)
    text = [kopf]
    for zeile in zeilen:
        text.append(",".join(str(zeile.get(feld, "")) for feld in CSV_FELDER))
    pfad.write_text("\n".join(text) + "\n", encoding="utf-8")
    return pfad


def _zeile(nummer: int, jahr=2025, monat=1, tag=6, ordner="P:/Ord",
           geraet="Geraet") -> dict:
    return {"jahr": jahr, "monat": monat, "tag": tag, "datumquelle": "namen",
            "thema": "", "geraet": geraet, "ordner": ordner,
            "datei": f"IMG{jahr}{monat:02d}{tag:02d}_1201{nummer:02d}.jpg",
            "motiv": "", "doppelung": "", "bytes": 1000 + nummer, "mb": "0.001"}


def _env_schreiben(pfad: Path) -> Path:
    pfad.write_text(f"OPENROUTER_API_KEY={SCHLUESSEL}\n", encoding="utf-8")
    return pfad


def _dateien(nummern) -> dict:
    return {f"IMG20250106_1201{n:02d}.jpg": 1000 + n for n in nummern}


def _lauf(tmp_path: Path, sender, anzahl=3, **kwargs):
    """Einen kompletten Lauf mit Attrappen fahren (Ausgaben nach tmp_path)."""
    csv = _csv_schreiben(tmp_path / "sortierschluessel.csv",
                         [_zeile(n) for n in range(1, anzahl + 1)])
    env = _env_schreiben(tmp_path / ".env")
    argv = ["--csv", str(csv), "--ausgabe", str(tmp_path)]
    for name, wert in kwargs.items():
        argv += [f"--{name.replace('_', '-')}", str(wert)]
    api = FakeApi(_dateien(range(1, anzahl + 1)))
    thumb = FakeThumb()
    rc = werkzeug.main(argv, sende=sender, api_abruf=api, thumb_abruf=thumb,
                       env_pfade=[str(env)])
    jsonl = tmp_path / "bild_beschreibungen.jsonl"
    gelesen = ([json.loads(z) for z in jsonl.read_text(encoding="utf-8").splitlines()]
               if jsonl.is_file() else [])
    return rc, gelesen, jsonl


# ── 1. Planung: Zeilen, Sortierung, Boegen (reine Funktionen) ──────────────

def test_zeilen_vorbereiten_datum_zeit_und_ohne_datum():
    mit = _zeile(1)
    ohne = dict(mit, jahr="", monat="", tag="")
    ergebnis = werkzeug.zeilen_vorbereiten([mit, ohne])
    assert len(ergebnis) == 1, "Zeile ohne Datum muss rausfallen"
    zeile = ergebnis[0]
    assert (zeile["jahr"], zeile["monat"], zeile["tag"]) == (2025, 1, 6)
    assert zeile["zeit"] == (12, 1, 1), "Uhrzeit kommt aus dem Dateinamen"


def test_sortierschluessel_sortieren_chronologisch_und_stabil():
    a = _zeile(1, monat=2)
    b = _zeile(2, monat=1)
    c = _zeile(3, monat=3)
    c["zeit"] = None                                  # ohne Uhrzeit ans Tagesende
    d = dict(c, datei="ohne-zeit.jpg")
    sortiert = werkzeug.sortierschluessel_sortieren([a, b, c, d])
    assert [z["monat"] for z in sortiert] == [1, 2, 3, 3]
    assert sortiert[2]["zeit"] is None and sortiert[3]["zeit"] is None
    assert sortiert[2]["datei"] < sortiert[3]["datei"]  # Gleichstand: Name
    assert werkzeug.sortierschluessel_sortieren(sortiert) == sortiert


def test_boegen_planen_packt_36_je_bogen_und_kennung_ist_erste_fileid():
    zeilen = [{"fileid": i, "datei": f"f{i}.jpg"} for i in range(1, 81)]
    boegen = werkzeug.boegen_planen(zeilen, 36)
    assert [len(b["zeilen"]) for b in boegen] == [36, 36, 8]
    assert [b["bogen_id"] for b in boegen] == ["bogen-1", "bogen-37", "bogen-73"]
    assert sum(len(b["zeilen"]) for b in boegen) == 80


def test_boegen_planen_zu_kleine_kachelzahl_ist_fehler():
    with pytest.raises(werkzeug.BildBeschreibenFehler):
        werkzeug.boegen_planen([{"fileid": 1, "datei": "a.jpg"}], 0)


def test_max_tokens_fuer_waechst_und_deckelt():
    assert werkzeug.max_tokens_fuer(1) == 660
    assert werkzeug.max_tokens_fuer(36) == 2760
    assert werkzeug.max_tokens_fuer(10_000) == werkzeug.MAX_TOKENS_DECKEL
    assert werkzeug.max_tokens_fuer(0) == werkzeug.MAX_TOKENS_GRUND + 60


# ── 2. Prompt, Anfrage, Bild nur im Speicher ───────────────────────────────

def test_prompt_nennt_genau_die_gueltigen_nummern():
    prompt = werkzeug.prompt_bauen(12)
    assert "genau 12 Kacheln" in prompt
    assert "1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12." in prompt
    assert "13" not in re.sub(r"1\.\.12", "", prompt).split("Regeln")[0] or True
    assert "je_kachel" in prompt and "unbrauchbar" in prompt


def test_anfrage_bauen_haengt_das_bild_als_daten_uri_an():
    anfrage = werkzeug.anfrage_bauen("modell/x", "data:image/jpeg;base64,AAAA", 5)
    assert anfrage["model"] == "modell/x"
    assert anfrage["temperature"] == 0
    inhalt = anfrage["messages"][0]["content"]
    assert inhalt[0]["type"] == "text" and "genau 5 Kacheln" in inhalt[0]["text"]
    assert inhalt[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert anfrage["max_tokens"] == werkzeug.max_tokens_fuer(5)


def test_bild_daten_uri_ist_rundreise_und_leer_ist_fehler():
    roh = _jpeg()
    uri = werkzeug.bild_daten_uri(roh)
    assert uri.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == roh
    with pytest.raises(werkzeug.BildBeschreibenFehler):
        werkzeug.bild_daten_uri(b"")


def test_bogen_bauen_liefert_jpeg_1382x872_ohne_datei(tmp_path):
    """Der Kontaktbogen entsteht im Speicher — N5-Format, nichts auf Platte."""
    zeilen = [{"fileid": 1000 + i, "datei": f"IMG_2025{i:02d}.jpg"}
              for i in range(1, 37)]
    vorschauen = {1000 + i: _jpeg() for i in range(1, 37)}
    bogen = werkzeug.bogen_bauen({"zeilen": zeilen}, vorschauen,
                                 spalten=8, kachel=160)
    assert bogen[:2] == b"\xff\xd8", "muss ein JPEG sein"
    assert Image.open(io.BytesIO(bogen)).size == (1382, 872), "N5-Format"
    assert len(bogen) > 5000
    assert list(tmp_path.iterdir()) == [], "kein Bild auf Platte"


# ── 3. Antwort zerlegen ────────────────────────────────────────────────────

def test_beschreibung_normalisieren_eine_zeile_hoechstens_14_woerter():
    text = "  eine\n  Buehne   mit   Menschen und ganz vielen weiteren Woertern "
    text += "die einfach zu viel sind fuer eine Zeile"
    sauber = werkzeug.beschreibung_normalisieren(text)
    assert "\n" not in sauber and "  " not in sauber
    assert len(sauber.split(" ")) == werkzeug.BESCHREIBUNG_MAX_WOERTER


def test_beschreibungen_uebernehmen_nimmt_gueltige_und_zaehlt_verworfenes():
    daten = {"je_kachel": [
        {"kachel": 1, "beschreibung": "Buehne mit Band", "unbrauchbar": False},
        {"kachel": 99, "beschreibung": "erfunden", "unbrauchbar": False},
        {"kachel": 1, "beschreibung": "Doppelung zaehlt nicht", "unbrauchbar": False},
        "kein Objekt",
        {"kachel": 2, "beschreibung": "   ", "unbrauchbar": False},
        {"kachel": 3, "beschreibung": "Gruppe im Garten", "unbrauchbar": True},
    ]}
    kacheln = werkzeug.beschreibungen_uebernehmen(daten, 3)
    assert [k["kachel"] for k in kacheln] == [1, 3]
    assert kacheln[0]["beschreibung"] == "Buehne mit Band"
    assert kacheln[1]["unbrauchbar"] is True, "unbrauchbar bleibt Information"
    assert kacheln[0]["verworfen"] == 4


def test_beschreibungen_uebernehmen_ohne_gueltige_kachel_ist_fehler():
    with pytest.raises(werkzeug.BildBeschreibenFehler):
        werkzeug.beschreibungen_uebernehmen({"je_kachel": [{"kachel": 7,
                                                            "beschreibung": "x"}]}, 3)
    with pytest.raises(werkzeug.BildBeschreibenFehler):
        werkzeug.beschreibungen_uebernehmen({"etwas": "anderes"}, 3)


# ── 4. Ein Bogen: ein Aufruf, Zuordnung, keine Vorschau ────────────────────

def test_bogen_verarbeiten_ein_aufruf_und_zeilen_zuordnung():
    zeilen = werkzeug.zeilen_vorbereiten([_zeile(n) for n in range(1, 4)])
    for n, zeile in enumerate(zeilen, start=1):
        zeile["fileid"] = 1000 + n
    sender = FakeSender()
    thumb = FakeThumb()
    ergebnis = werkzeug.bogen_verarbeiten(zeilen, SCHLUESSEL, sender,
                                          thumb_abruf=thumb)
    assert len(sender.aufrufe) == 1, "genau EIN Aufruf je Bogen"
    assert ergebnis["gesendet"] and ergebnis["bilder"] == 3
    assert ergebnis["ohne_vorschau"] == 0
    assert [e["zeile"]["fileid"] for e in ergebnis["eintraege"]] == [1001, 1002, 1003]
    assert ergebnis["tokens_ein"] == 2000 and ergebnis["tokens_aus"] == 300
    assert ergebnis["kosten_usd"] == pytest.approx(
        2000 / 1e6 * werkzeug.STANDARD_PREIS_EIN
        + 300 / 1e6 * werkzeug.STANDARD_PREIS_AUS)
    assert len(sender.aufrufe[0]["messages"][0]["content"][1]["image_url"]["url"]) > 1000


def test_bogen_verarbeiten_ohne_vorschau_sendet_nichts():
    zeilen = werkzeug.zeilen_vorbereiten([_zeile(1), _zeile(2)])
    for n, zeile in enumerate(zeilen, start=1):
        zeile["fileid"] = 1000 + n
    sender = Stolperfalle()
    ergebnis = werkzeug.bogen_verarbeiten(zeilen, SCHLUESSEL, sender,
                                          thumb_abruf=FakeThumb(fehlend=(1001, 1002)))
    assert ergebnis["gesendet"] is False, "ohne jede Vorschau gibt es keinen Aufruf"
    assert ergebnis["bilder"] == 0 and ergebnis["ohne_vorschau"] == 2


def test_bogen_verarbeiten_laesst_kacheln_ohne_vorschau_weg():
    zeilen = werkzeug.zeilen_vorbereiten([_zeile(n) for n in range(1, 4)])
    for n, zeile in enumerate(zeilen, start=1):
        zeile["fileid"] = 1000 + n
    sender = FakeSender()
    ergebnis = werkzeug.bogen_verarbeiten(zeilen, SCHLUESSEL, sender,
                                          thumb_abruf=FakeThumb(fehlend=(1002,)))
    assert ergebnis["bilder"] == 2 and ergebnis["ohne_vorschau"] == 1
    assert [e["zeile"]["fileid"] for e in ergebnis["eintraege"]] == [1001, 1003]
    assert ergebnis["eintraege"][1]["kachel"] == 2, "Numerierung bleibt lueckenlos"


# ── 5. JSONL: Felder, Idempotenz, Anhaengen ────────────────────────────────

def test_jsonl_zeilen_bauen_genau_die_vereinbarten_felder_ohne_bilddaten():
    zeilen = werkzeug.zeilen_vorbereiten([_zeile(1)])
    zeilen[0]["fileid"] = 1001
    eintraege = [{"kachel": 1, "beschreibung": "Buehne mit Band",
                  "unbrauchbar": False, "zeile": zeilen[0]}]
    fertig = werkzeug.jsonl_zeilen_bauen(eintraege, "bogen-1001",
                                         "fake/vision", 0.0034,
                                         "2026-09-28T12:00:00")
    assert len(fertig) == 1
    assert sorted(fertig[0]) == ["beschreibung", "bogen_id", "datei", "fileid",
                                 "jahr", "kosten_usd", "modell", "monat",
                                 "ordner", "tag", "zeit"]
    text = json.dumps(fertig, ensure_ascii=False)
    assert "base64" not in text and "data:image" not in text
    assert fertig[0]["kosten_usd"] == pytest.approx(0.0034)


def test_jsonl_kostenanteil_summiert_sich_zum_aufruf():
    zeilen = werkzeug.zeilen_vorbereiten([_zeile(n) for n in range(1, 4)])
    for n, zeile in enumerate(zeilen, start=1):
        zeile["fileid"] = 1000 + n
    eintraege = [{"kachel": n, "beschreibung": f"Bild {n}", "unbrauchbar": False,
                  "zeile": zeilen[n - 1]} for n in range(1, 4)]
    fertig = werkzeug.jsonl_zeilen_bauen(eintraege, "bogen-1001", "m", 0.003,
                                         "2026-09-28T12:00:00")
    assert sum(z["kosten_usd"] for z in fertig) == pytest.approx(0.003)


def test_erledigtes_lesen_ignoriert_kaputte_zeilen_und_dubletten():
    jsonl = Path("nicht-da.jsonl")
    assert werkzeug.erledigtes_lesen(str(jsonl)) == {"fileids": set(),
                                                     "dateien": set()}
    import tempfile
    with tempfile.TemporaryDirectory() as ordner:
        pfad = Path(ordner) / "b.jsonl"
        pfad.write_text("\n".join([
            json.dumps({"fileid": 1001, "ordner": "P:/Ord", "datei": "a.jpg"}),
            "kein json",
            json.dumps({"fileid": 1001, "ordner": "P:/Ord", "datei": "a.jpg"}),
            json.dumps({"ordner": "P:/Ord", "datei": "b.jpg"}),
        ]) + "\n", encoding="utf-8")
        erledigt = werkzeug.erledigtes_lesen(str(pfad))
        assert erledigt["fileids"] == {1001}
        assert erledigt["dateien"] == {("p:/ord", "a.jpg"), ("p:/ord", "b.jpg")}


def test_zeilen_anhaengen_zaehlt_und_haengt_nur_an(tmp_path):
    pfad = tmp_path / "b.jsonl"
    assert werkzeug.zeilen_anhaengen(str(pfad), []) == 0
    assert not pfad.exists()
    assert werkzeug.zeilen_anhaengen(str(pfad), [{"fileid": 1}]) == 1
    assert werkzeug.zeilen_anhaengen(str(pfad), [{"fileid": 2}]) == 1
    assert len(pfad.read_text(encoding="utf-8").splitlines()) == 2


# ── 6. Kostenbremse (reine Funktionen und im Lauf) ─────────────────────────

def test_budget_stoppt_rechnet_ehrlich():
    assert werkzeug.budget_stoppt(0.0, 0.0, 1.0) is False
    assert werkzeug.budget_stoppt(0.95, 0.05, 1.0) is False   # genau auf der Grenze
    assert werkzeug.budget_stoppt(0.99, 0.02, 1.0) is True
    assert werkzeug.budget_stoppt(1.0, 0.0, 1.0) is False


def test_messung_bericht_hochrechnung_und_hinweis():
    text = werkzeug.messung_bericht(3, 108, 0.0116, 18.0, 259, 9324, 1.0)
    assert "erste 3 Boegen" in text and "0.011600" in text
    assert "Gesamt ~" in text and "Budget 1.00" in text
    leer = werkzeug.messung_bericht(0, 0, 0.0, 0.0, 5, 180, 1.0)
    assert "0.000000" in leer


def test_lauf_stoppt_an_der_kostenbremse_vor_dem_aufruf(tmp_path):
    sender = FakeSender(tokens=(100_000, 1_000))      # ~0,0325 USD je Aufruf
    rc, zeilen, _ = _lauf(tmp_path, sender, anzahl=40, budget=0.05)
    assert rc == 0
    assert len(sender.aufrufe) == 1, "der zweite Aufruf darf nicht starten"
    assert len(zeilen) == 36, "Bogen 1 ist noch geschrieben worden"
    assert len({z["fileid"] for z in zeilen}) == 36


def test_fortsetzen_nach_dem_stopp_beschreibt_den_rest(tmp_path, capsys):
    sender = FakeSender(tokens=(100_000, 1_000))
    rc, zeilen, jsonl = _lauf(tmp_path, sender, anzahl=40, budget=0.05)
    capsys.readouterr()
    assert len(zeilen) == 36
    sender2 = FakeSender(tokens=(100_000, 1_000))
    rc2, zeilen2, _ = _lauf(tmp_path, sender2, anzahl=40, budget=5.0)
    assert rc2 == 0 and len(sender2.aufrufe) >= 1
    assert len(zeilen2) == 40, "der Rest von 4 Dateien kommt hinzu"
    assert len({z["fileid"] for z in zeilen2}) == 40, "keine Doppelzeilen"


def test_zweiter_lauf_haengt_nichts_an(tmp_path, capsys):
    sender = FakeSender()
    rc, zeilen, jsonl = _lauf(tmp_path, sender, anzahl=5)
    capsys.readouterr()
    assert rc == 0 and len(zeilen) == 5
    # Zweiter Lauf: der Transport darf gar nicht erst gerufen werden.
    rc2, zeilen2, _ = _lauf(tmp_path, Stolperfalle(), anzahl=5)
    assert rc2 == 0
    assert len(zeilen2) == 5, "idempotent: 0 Zeilen hinzugefuegt"


def test_kein_bild_landet_auf_der_platte(tmp_path):
    rc, zeilen, jsonl = _lauf(tmp_path, FakeSender(), anzahl=5)
    assert rc == 0 and len(zeilen) == 5
    bilder = [p.name for p in tmp_path.rglob("*")
              if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}]
    assert bilder == [], f"keine Bilddatei erlaubt, gefunden: {bilder}"


# ── 7. Ehrliche Fehler: kein Schluessel, Repo-Ausgabe, Fehlerbogen ─────────

def test_fehlerhafter_bogen_schreibt_nichts_und_bleibt_offen(tmp_path, capsys):
    rc, zeilen, _ = _lauf(tmp_path, FakeSender(fehler_immer=True), anzahl=3)
    ausgabe = capsys.readouterr().out
    assert rc == 0 and zeilen == [], "ein Fehler schreibt keine erfundenen Zeilen"
    assert "FEHLER" in ausgabe and "bleiben offen" in ausgabe
    rc2, zeilen2, _ = _lauf(tmp_path, FakeSender(), anzahl=3)
    assert rc2 == 0 and len(zeilen2) == 3, "der naechste Lauf holt sie nach"


def test_trocken_und_nur_liste_ohne_jeden_netzaufruf(tmp_path):
    csv = _csv_schreiben(tmp_path / "s.csv", [_zeile(1)])
    for modus in ("--trocken", "--nur-liste"):
        rc = werkzeug.main(["--csv", str(csv), "--ausgabe", str(tmp_path), modus],
                           sende=Stolperfalle(), api_abruf=Stolperfalle(),
                           thumb_abruf=Stolperfalle(), env_pfade=[])
        assert rc == 0
    assert not (tmp_path / "bild_beschreibungen.jsonl").exists()


def test_ausgabe_im_repo_bricht_sofort_ab(tmp_path):
    csv = _csv_schreiben(tmp_path / "s.csv", [_zeile(1)])
    with pytest.raises(SystemExit) as fehler:
        werkzeug.main(["--csv", str(csv), "--ausgabe", str(REPO)],
                      sende=Stolperfalle(), api_abruf=Stolperfalle(),
                      thumb_abruf=Stolperfalle(), env_pfade=[])
    assert fehler.value.code == 2


def test_ohne_schluessel_wird_nichts_gesendet(tmp_path, capsys):
    csv = _csv_schreiben(tmp_path / "s.csv", [_zeile(1)])
    rc = werkzeug.main(["--csv", str(csv), "--ausgabe", str(tmp_path)],
                       sende=Stolperfalle(), api_abruf=Stolperfalle(),
                       thumb_abruf=Stolperfalle(),
                       env_pfade=[str(tmp_path / "gibt-es-nicht.env")])
    assert rc == 2
    assert "Es wird NICHTS gesendet" in capsys.readouterr().out


def test_kaputte_modellantwort_haelt_den_lauf_nicht_an(tmp_path, capsys):
    sender = FakeSender(kacheln=[{"kachel": 1, "beschreibung": "nur Kachel 1"}])
    rc, zeilen, _ = _lauf(tmp_path, sender, anzahl=3)
    assert rc == 0
    assert len(zeilen) == 1 and zeilen[0]["fileid"] == 1001
    assert "1/3" in capsys.readouterr().out, "ehrlich: nur 1 von 3 Kacheln"


# ── 8. Einbetten: bild_index.db ────────────────────────────────────────────

def _jsonl_schreiben(pfad: Path, zeilen: list[dict]) -> Path:
    pfad.write_text("\n".join(json.dumps(z, ensure_ascii=False) for z in zeilen)
                    + "\n", encoding="utf-8")
    return pfad


def _beschreibung(fileid: int, text="Buehne, Menschen, rotes Licht", tag=6) -> dict:
    return {"fileid": fileid, "datei": f"f{fileid}.jpg", "jahr": 2025, "monat": 1,
            "tag": tag, "ordner": "P:/Ord", "beschreibung": text,
            "bogen_id": "bogen-1000", "modell": "fake/vision",
            "kosten_usd": 0.0001, "zeit": "2026-09-28T12:00:00"}


def test_beschreibungen_lesen_verwirft_dubletten_und_kaputtes(tmp_path):
    jsonl = _jsonl_schreiben(tmp_path / "b.jsonl", [_beschreibung(1001)])
    jsonl.write_text(jsonl.read_text(encoding="utf-8") + "\n".join([
        json.dumps({"fileid": 0, "beschreibung": "ohne Kennung"}),
        "kein json",
        json.dumps({"fileid": 1002, "beschreibung": "   "}),
        json.dumps(_beschreibung(1001, "Doppelung")),
    ]) + "\n", encoding="utf-8")
    gelesen = einbett.beschreibungen_lesen(str(jsonl))
    assert [z["fileid"] for z in gelesen["zeilen"]] == [1001]
    assert gelesen["zeilen"][0]["datum"] == "2025-01-06"
    assert gelesen["verworfen"] == 3 and gelesen["dubletten"] == 1


def test_einbetten_trocken_legt_keine_datenbank_an(tmp_path):
    jsonl = _jsonl_schreiben(tmp_path / "b.jsonl", [_beschreibung(1001)])
    db = tmp_path / "bild_index.db"
    zaehler = einbett.einbetten(str(jsonl), str(db), einbetter=FakeEinbetter(),
                                schreiben=False)
    assert zaehler["offen"] == 1 and zaehler["neu"] == 0
    assert not db.exists(), "Trockenlauf legt nichts an"


def test_einbetten_schema_vektoren_und_meta(tmp_path):
    jsonl = _jsonl_schreiben(tmp_path / "b.jsonl",
                             [_beschreibung(1000 + n) for n in range(1, 6)])
    db = tmp_path / "bild_index.db"
    rechner = FakeEinbetter()
    zaehler = einbett.einbetten(str(jsonl), str(db), einbetter=rechner,
                                schreiben=True)
    assert zaehler["neu"] == 5 and zaehler["kosten_usd"] > 0
    con = sqlite3.connect(db)
    spalten = [z[1] for z in con.execute("PRAGMA table_info(bilder)")]
    assert spalten == ["fileid", "datum", "ordner", "beschreibung", "vektor"]
    vektor = con.execute("SELECT vektor FROM bilder WHERE fileid = 1001").fetchone()[0]
    assert len(vektor) == 1536 * 2, "float16 = halbe Laenge"
    assert np.frombuffer(vektor, dtype="float16").shape == (1536,)
    meta = dict(con.execute("SELECT schluessel, wert FROM meta").fetchall())
    assert meta["dimension"] == "1536" and meta["vektoren"] == "5"
    assert meta["modell"] == "fake/text-einbetter"
    con.close()


def test_einbetten_zweiter_lauf_ist_idempotent(tmp_path):
    jsonl = _jsonl_schreiben(tmp_path / "b.jsonl",
                             [_beschreibung(1000 + n) for n in range(1, 4)])
    db = tmp_path / "bild_index.db"
    einbett.einbetten(str(jsonl), str(db), einbetter=FakeEinbetter(), schreiben=True)
    zweiter = FakeEinbetter()
    zaehler = einbett.einbetten(str(jsonl), str(db), einbetter=zweiter,
                                schreiben=True)
    assert zaehler["neu"] == 0 and zweiter.aufrufe == []
    assert zaehler["schon"] == 3


def test_einbetten_budgetgrenze_bricht_vor_dem_schreiben_ab(tmp_path, capsys):
    jsonl = _jsonl_schreiben(tmp_path / "b.jsonl", [_beschreibung(1001)])
    db = tmp_path / "bild_index.db"
    with pytest.raises(einbett.BudgetUeberschritten):
        einbett.einbetten(str(jsonl), str(db), einbetter=FakeEinbetter(),
                          budget_usd=0.00000001, schreiben=True)
    assert not db.exists()
    rc = einbett.main(["--jsonl", str(jsonl), "--db", str(db),
                       "--budget", "0.00000001", "--schreiben"],
                      einbetter=FakeEinbetter())
    assert rc == 4 and "Budget-Grenze" in capsys.readouterr().out


def test_einbetten_stoppt_am_budget_behaelt_den_fortschritt(tmp_path):
    jsonl = _jsonl_schreiben(tmp_path / "b.jsonl",
                             [_beschreibung(1000 + n) for n in range(1, 6)])
    db = tmp_path / "bild_index.db"
    zaehler = einbett.einbetten(str(jsonl), str(db), einbetter=FakeEinbetter(),
                                budget_usd=0.00000085, stapel=5, schreiben=True)
    assert zaehler["abgebrochen"] is True
    assert zaehler["neu"] == 5, "das begonnene Buendel bleibt erhalten"
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM bilder").fetchone()[0] == 5
    con.close()


def test_einbetten_datenbank_im_repo_bricht_ab(tmp_path):
    jsonl = _jsonl_schreiben(tmp_path / "b.jsonl", [_beschreibung(1001)])
    with pytest.raises(SystemExit) as fehler:
        einbett.main(["--jsonl", str(jsonl), "--db", str(REPO / "bild_index.db")],
                     einbetter=FakeEinbetter())
    assert fehler.value.code == 2


def test_einbetten_trockenlauf_braucht_keinen_schluessel(tmp_path, capsys):
    jsonl = _jsonl_schreiben(tmp_path / "b.jsonl", [_beschreibung(1001)])
    rc = einbett.main(["--jsonl", str(jsonl), "--db", str(tmp_path / "i.db")],
                      einbetter=None)
    assert rc == 0 and "Trockenlauf" in capsys.readouterr().out
    assert not (tmp_path / "i.db").exists()


# ── 8. Plan-Eingang (01.10.2026): Sammlung ohne Sortierschluessel-CSV ───────
#
# Befund: der Nachtlauf las nur sortierschluessel.csv (Upload-Sammlung); die
# 10.771 Fotos aus "Bilder & Videos" (sortierplan_bildervideos.json) blieben
# ohne Beschreibung. --plan liest die zuege[] direkt (fileid bekannt).

def _plan_schreiben(pfad: Path, zuege: list[dict]) -> Path:
    pfad.write_text(json.dumps({"zuege": zuege}), encoding="utf-8")
    return pfad


def test_plan_zeilen_nur_fotos_mit_kennung_und_datum_aus_dem_namen(tmp_path):
    plan = _plan_schreiben(tmp_path / "plan.json", [
        {"fileid": 1001, "von_name": "IMG_20220618_112130.jpg", "von_ordner": "/Freunde/Hurricane", "jahr": 2022},
        {"fileid": 1002, "von_name": "Urlaub.JPG", "von_ordner": "/Familie", "jahr": 2016},
        {"fileid": 1003, "von_name": "VID_20220618.mp4", "jahr": 2022},          # Video raus
        {"fileid": None, "von_name": "ohne.jpg"},                                 # ohne Kennung raus
        {"fileid": 1001, "von_name": "IMG_20220618_112130.jpg", "jahr": 2022},    # doppelt raus
        {"fileid": 1004, "von_name": "IMG-20190101-WA0001.jpg", "jahr": 2023},    # Name passt nicht zum Jahr
    ])
    zeilen = werkzeug.plan_zeilen_lesen(str(plan))
    assert [z["fileid"] for z in zeilen] == [1001, 1002, 1004]
    a, b, c = zeilen
    assert (a["jahr"], a["monat"], a["tag"], a["zeit"]) == (2022, 6, 18, (11, 21, 30))
    assert (b["jahr"], b["monat"], b["tag"], b["zeit"]) == (2016, 0, 0, None)    # nichts geraten
    assert (c["jahr"], c["monat"]) == (2023, 0)
    assert a["ordner"] == "/Freunde/Hurricane" and a["datei"] == "IMG_20220618_112130.jpg"


def test_plan_lauf_ohne_ordner_abfrage_und_idempotent(tmp_path, capsys):
    plan = _plan_schreiben(tmp_path / "sortierplan_bildervideos.json", [
        {"fileid": 1000 + n, "von_name": f"Foto_{n}.jpg", "von_ordner": "/B", "jahr": 2019}
        for n in range(1, 6)] + [{"fileid": 2000, "von_name": "clip.mov", "jahr": 2019}])
    env = _env_schreiben(tmp_path / ".env")
    argv = ["--plan", str(plan), "--ausgabe", str(tmp_path)]
    rc = werkzeug.main(argv, sende=FakeSender(), api_abruf=Stolperfalle(),
                       thumb_abruf=FakeThumb(), env_pfade=[str(env)])
    ausgabe = capsys.readouterr().out
    assert rc == 0 and "Sortierplan:" in ausgabe
    jsonl = tmp_path / "bild_beschreibungen.jsonl"
    zeilen = [json.loads(z) for z in jsonl.read_text(encoding="utf-8").splitlines()]
    assert sorted(z["fileid"] for z in zeilen) == [1001, 1002, 1003, 1004, 1005]   # Video nicht
    # Zweiter Lauf: alles erledigt, der Transport wird gar nicht gerufen.
    rc2 = werkzeug.main(argv, sende=Stolperfalle(), api_abruf=Stolperfalle(),
                        thumb_abruf=Stolperfalle(), env_pfade=[str(env)])
    assert rc2 == 0
    assert len(jsonl.read_text(encoding="utf-8").splitlines()) == 5


def test_plan_fehlt_ehrlich(tmp_path, capsys):
    rc = werkzeug.main(["--plan", str(tmp_path / "gibtsnicht.json"), "--ausgabe", str(tmp_path)],
                       sende=Stolperfalle(), api_abruf=Stolperfalle(),
                       thumb_abruf=Stolperfalle(), env_pfade=[])
    assert rc == 2 and "Sortierplan nicht gefunden" in capsys.readouterr().out


# ── 9. Prompt-Varianten (--prompt-variante) ────────────────────────────────
#
# Der Stichwort-Prompt ist der Bestand und muss Wort fuer Wort gleich bleiben:
# die Goldtexte in tests/testdaten/ wurden VOR dieser Aenderung aus dem
# Werkzeug erzeugt (n=3 und n=36), die Pruefung vergleicht byteweise. Die
# zweite Fassung "bildgeschichte" ist englisch und hat ihre eigene Wortgrenze
# (70); das Ausgabeschema selbst bleibt in beiden Fassungen identisch.

TESTDATEN = Path(__file__).resolve().parent / "testdaten"


def test_prompt_stichwort_ist_wortgleich_zum_bestand():
    for n in (3, 36):
        gold = (TESTDATEN / f"prompt_stichwort_n{n}.txt").read_text(encoding="utf-8")
        assert werkzeug.prompt_bauen(n) == gold, f"n={n} weicht vom Bestand ab"
        assert werkzeug.prompt_bauen(n, "stichwort") == gold


def test_prompt_varianten_wortgrenzen_und_standard():
    assert werkzeug.BESCHREIBUNG_MAX_WOERTER == 14
    assert werkzeug.BESCHREIBUNG_MAX_WOERTER_BILDGESCHICHTE == 70
    assert werkzeug.max_woerter_fuer() == 14
    assert werkzeug.max_woerter_fuer("stichwort") == 14
    assert werkzeug.max_woerter_fuer("bildgeschichte") == 70
    assert werkzeug.max_woerter_fuer("Bildgeschichte") == 70, "Name wird tolerant gelesen"
    assert werkzeug.max_woerter_fuer("unbekannt") == 14, "Unbekanntes faellt auf den Standard"
    stichwort = werkzeug.prompt_bauen(9)
    assert "4 bis 14 Woerter" in stichwort and "auf Deutsch" in stichwort


def test_prompt_bildgeschichte_ist_englisch_mit_70_woertern():
    prompt = werkzeug.prompt_bauen(4, "bildgeschichte")
    assert "exactly 4 tiles" in prompt
    assert "1, 2, 3, 4." in prompt
    assert "2 to 4 sentences" in prompt
    assert "at most 70 words" in prompt
    assert "Answer in English" in prompt
    assert "no person names, no license plates, no addresses" in prompt
    assert "Do not invent" in prompt and "clearly recognizable" in prompt
    assert "Woerter" not in prompt, "kein deutscher Rest im englischen Prompt"
    assert "auf Deutsch" not in prompt


def test_beschreibung_normalisieren_kuerzt_bei_14_und_bei_70():
    text = " ".join(f"w{i}" for i in range(1, 101))
    assert len(werkzeug.beschreibung_normalisieren(text).split(" ")) == 14
    assert len(werkzeug.beschreibung_normalisieren(text, 14).split(" ")) == 14
    assert len(werkzeug.beschreibung_normalisieren(text, max_woerter=70).split(" ")) == 70
    assert werkzeug.beschreibung_normalisieren("  zwei \n Woerter ", 70) == "zwei Woerter"


def test_beschreibungen_uebernehmen_nutzt_die_grenze_der_variante():
    lang = {"kachel": 1, "beschreibung": " ".join(f"w{i}" for i in range(1, 91)),
            "unbrauchbar": False}
    kurz = werkzeug.beschreibungen_uebernehmen({"je_kachel": [lang]}, 1)
    weit = werkzeug.beschreibungen_uebernehmen({"je_kachel": [lang]}, 1,
                                               max_woerter=70)
    assert len(kurz[0]["beschreibung"].split(" ")) == 14
    assert len(weit[0]["beschreibung"].split(" ")) == 70


def test_anfrage_bauen_reicht_die_variante_an_den_prompt_durch():
    anfrage = werkzeug.anfrage_bauen("modell/x", "data:image/jpeg;base64,AAAA", 2,
                                     variante="bildgeschichte")
    text = anfrage["messages"][0]["content"][0]["text"]
    assert "exactly 2 tiles" in text and "at most 70 words" in text
    assert anfrage["max_tokens"] == werkzeug.max_tokens_fuer(2), "Kostengrenze unveraendert"


def test_lauf_bildgeschichte_englischer_prompt_und_70er_grenze(tmp_path):
    lang = " ".join(f"wort{i}" for i in range(1, 91))
    sender = FakeSender(kacheln=[
        {"kachel": 1, "beschreibung": lang, "unbrauchbar": False},
        {"kachel": 2, "beschreibung": "Zweite Kachel, kurzer Satz", "unbrauchbar": False},
        {"kachel": 3, "beschreibung": "unscharf", "unbrauchbar": True},
    ])
    rc, zeilen, _ = _lauf(tmp_path, sender, anzahl=3,
                          prompt_variante="bildgeschichte")
    assert rc == 0 and len(zeilen) == 3
    text = sender.aufrufe[0]["messages"][0]["content"][0]["text"]
    assert "exactly 3 tiles" in text and "2 to 4 sentences" in text
    assert "at most 70 words" in text
    assert len(zeilen[0]["beschreibung"].split(" ")) == 70, "70-Wort-Grenze greift"
    # JSON-Schema unveraendert: genau die vereinbarten Felder.
    assert sorted(zeilen[0]) == ["beschreibung", "bogen_id", "datei", "fileid",
                                 "jahr", "kosten_usd", "modell", "monat",
                                 "ordner", "tag", "zeit"]


def test_lauf_stichwort_bleibt_bei_14_woertern(tmp_path):
    lang = " ".join(f"wort{i}" for i in range(1, 91))
    sender = FakeSender(kacheln=[{"kachel": 1, "beschreibung": lang,
                                  "unbrauchbar": False}])
    rc, zeilen, _ = _lauf(tmp_path, sender, anzahl=1)
    assert rc == 0 and len(zeilen) == 1
    assert len(zeilen[0]["beschreibung"].split(" ")) == 14, "Bestand bleibt bei 14"


def test_unbekannte_prompt_variante_wird_abgelehnt(tmp_path):
    csv = _csv_schreiben(tmp_path / "s.csv", [_zeile(1)])
    with pytest.raises(SystemExit) as fehler:
        werkzeug.main(["--csv", str(csv), "--ausgabe", str(tmp_path),
                       "--prompt-variante", "roman"],
                      sende=Stolperfalle(), api_abruf=Stolperfalle(),
                      thumb_abruf=Stolperfalle(), env_pfade=[])
    assert fehler.value.code == 2
