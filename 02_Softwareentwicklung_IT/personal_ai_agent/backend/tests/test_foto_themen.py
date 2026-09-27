"""Pruefungen fuer die Themen-Stufe (foto_themen.py) — alles OHNE Netz.

Alle pCloud-Aufrufe laufen ueber Attrappen (``FakeApi`` fuer listfolder,
``FakeThumbs`` fuer getthumbs). Die echte pCloud wird nie beruehrt, der echte
Token nie gelesen (fuer den Geheimnis-Test dient ein erfundener Wert in einer
temporaeren .env). Ausgaben gehen in tmp_path-Ordner, nie nach ~/foto_sortierung.

Aufruf: cd backend && .venv/Scripts/python -m pytest tests/test_foto_themen.py -q
"""

from __future__ import annotations

import base64
import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest
from PIL import Image

WERKZEUG = (Path(__file__).resolve().parents[2]
            / "tools" / "foto_sortierung" / "foto_themen.py")


def _laden():
    spez = importlib.util.spec_from_file_location("foto_themen", WERKZEUG)
    assert spez is not None and spez.loader is not None, (
        f"Werkzeug nicht gefunden: {WERKZEUG}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


foto = _laden()

TOKEN = "test-token-nicht-echt-abcdef-1234567890"


# ── Attrappen (kein Netz) ──────────────────────────────────────────────────

class Stolperfalle:
    """Ein Aufruf, der niemals passieren darf (Trockenlauf/Nur-Liste)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("API-Aufruf, obwohl keiner passieren darf!")


class FakeApi:
    """listfolder-Attrappe mit kleinem Ordnerbaum {folderid: [Eintraege]}."""

    def __init__(self, baum):
        self.baum = baum
        self.aufrufe = []

    def __call__(self, pfad, felder):
        assert pfad == "/listfolder", f"unerwarteter Pfad: {pfad}"
        self.aufrufe.append(int(felder["folderid"]))
        return {"result": 0,
                "metadata": {"contents": self.baum[int(felder["folderid"])]}}


def _ordner(name, folderid):
    return {"name": name, "isfolder": True, "folderid": folderid}


def _datei(name, fileid, groesse=1234):
    return {"name": name, "isfolder": False, "fileid": fileid, "size": groesse}


class FakeThumbs:
    """getthumbs-Attrappe: liefert Textzeilen, kann N Aufrufe lang scheitern."""

    def __init__(self, bilder: dict, fehler_bis: int = 0, verkehrt: bool = False):
        self.bilder = bilder          # {fileid: bytes|None}
        self.fehler_bis = fehler_bis
        self.verkehrt = verkehrt
        self.aufrufe = []

    def __call__(self, dateiids, groesse):
        self.aufrufe.append(list(dateiids))
        if len(self.aufrufe) <= self.fehler_bis:
            raise RuntimeError("Netz weg (Attrappe)")
        zeilen = []
        for dateiid in dateiids:
            bild = self.bilder.get(int(dateiid))
            if bild is None:
                zeilen.append(f"{dateiid}|5002|0")
            else:
                zeilen.append(
                    f"{dateiid}|0|90x120|data:image/jpeg;base64,"
                    + base64.b64encode(bild).decode())
        if self.verkehrt:
            zeilen.reverse()
        return "\n".join(zeilen)


@pytest.fixture(autouse=True)
def keine_pause(monkeypatch):
    """Kein Schlafen in Tests und kein echter Netzaufruf."""
    monkeypatch.setattr(foto, "_warte", lambda sekunden: None)

    def verboten(*args, **kwargs):
        raise AssertionError("echter Netzaufruf im Test!")

    monkeypatch.setattr(foto.httpx, "get", verboten)


# ── kleine Helfer ──────────────────────────────────────────────────────────

def _jpeg(farbe, groesse=(90, 120)):
    puffer = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(puffer, "JPEG")
    return puffer.getvalue()


def _zeile(datei, jahr="2025", monat="6", tag="6",
           ordner="P:/Automatic Upload/Testgeraet", bytes_wert="1000"):
    return {"jahr": jahr, "monat": monat, "tag": tag, "datumquelle": "namen",
            "thema": "", "geraet": "Testgeraet", "ordner": ordner,
            "datei": datei, "motiv": datei.lower(), "doppelung": "",
            "bytes": bytes_wert, "mb": "0.01"}


def _csv_schreiben(pfad, zeilen):
    felder = ["jahr", "monat", "tag", "datumquelle", "thema", "geraet",
              "ordner", "datei", "motiv", "doppelung", "bytes", "mb"]
    with open(pfad, "w", newline="", encoding="utf-8") as datei:
        schreiber = csv.DictWriter(datei, fieldnames=felder)
        schreiber.writeheader()
        for zeile in zeilen:
            schreiber.writerow(zeile)
    return str(pfad)


def _testbaum():
    """Wurzel -> Automatic Upload -> Testgeraet mit drei Dateien."""
    return {
        0: [_ordner("Automatic Upload", 10)],
        10: [_ordner("Testgeraet", 11)],
        11: [_datei("IMG_20250606_185746027_BURST008.jpg", 901, 3507237),
             _datei("IMG_20250606_185759123_BURST009.jpg", 902, 3706794),
             _datei("VID_20250606_190500.mp4", 903, 5100000)],
    }


# ── Zeit aus dem Dateinamen ────────────────────────────────────────────────

def test_zeit_aus_name_formen():
    """Alle Namensschemata der Sammlung liefern die Uhrzeit."""
    assert foto.zeit_aus_name("IMG_20250606_185746027_BURST008.jpg") == (18, 57, 46)
    assert foto.zeit_aus_name("IMG20220804140219.jpg") == (14, 2, 19)
    assert foto.zeit_aus_name("VID20250225185258.mp4") == (18, 52, 58)
    assert foto.zeit_aus_name("VID_20241221_193523_175.mp4") == (19, 35, 23)
    assert foto.zeit_aus_name("20190209_161112_HDR.jpg") == (16, 11, 12)
    assert foto.zeit_aus_name("image_20220730_142043_438.jpg") == (14, 20, 43)
    assert foto.zeit_aus_name("059956_2024-08-09_17-14-43_96.jpg") == (17, 14, 43)
    assert foto.zeit_aus_name(
        "Screenshot_2024-06-09-02-49-36-81_1c3376.jpg") == (2, 49, 36)
    assert foto.zeit_aus_name("1768046027646.jpg") is not None  # Epoche (lokal)


def test_zeit_aus_name_kein_raten():
    """Zeitlose Namen bekommen keine erfundene Uhrzeit."""
    assert foto.zeit_aus_name("IMG-20230623-WA0000.jpg") is None
    assert foto.zeit_aus_name("VID-20220821-WA0062.mp4") is None
    assert foto.zeit_aus_name("Snapchat-1209338263.jpg") is None
    assert foto.zeit_aus_name("Oplus_0.mp4") is None
    assert foto.zeit_aus_name("ServicePW.jpg") is None
    # Unplausibler Monat wird verworfen, nicht geraten.
    assert foto.zeit_aus_name("IMG_20251332_120000.jpg") is None
    # Passt das Namensdatum nicht zur CSV-Zeile, gibt es keine Uhrzeit.
    assert foto.zeit_aus_name("IMG_20250606_185746027.jpg",
                              erwartetes_datum=(2025, 6, 7)) is None


# ── Anlass-Bildung ─────────────────────────────────────────────────────────

def test_anlass_gleiche_minute_ist_ein_anlass():
    """Mehrere Bilder derselben Minute sind EIN Anlass."""
    zeilen = [_zeile("IMG_20250606_185746027_BURST008.jpg"),
              _zeile("IMG_20250606_185759123_BURST009.jpg"),
              _zeile("IMG_20250606_185801000.jpg")]
    anlaesse = foto.anlaesse_bilden(zeilen)
    assert len(anlaesse) == 1
    assert anlaesse[0]["titel"] == "2025-06-06_Anlass-01"
    assert anlaesse[0]["anzahl"] == 3
    assert anlaesse[0]["von"] == "18:57" and anlaesse[0]["bis"] == "18:58"


def test_anlass_verschiedene_tage_getrennt():
    """Jeder Tag bekommt eigene Anlaesse, die Nummerierung startet neu."""
    zeilen = [_zeile("IMG_20250606_100000000.jpg", tag="6"),
              _zeile("IMG_20250607_100000000.jpg", tag="7")]
    anlaesse = foto.anlaesse_bilden(zeilen)
    assert [a["titel"] for a in anlaesse] == [
        "2025-06-06_Anlass-01", "2025-06-07_Anlass-01"]
    assert all(a["anzahl"] == 1 for a in anlaesse)


def test_anlass_luecke_beginnt_neuen_anlass():
    """Bis 30 Minuten Abstand = eine Sitzung, darueber ein neuer Anlass."""
    eine = foto.anlaesse_bilden([
        _zeile("IMG_20250606_100000000.jpg"),
        _zeile("IMG_20250606_100500000.jpg")])
    assert len(eine) == 1 and eine[0]["von"] == "10:00"

    zwei = foto.anlaesse_bilden([
        _zeile("IMG_20250606_100000000.jpg"),
        _zeile("IMG_20250606_110100000.jpg")])
    assert [a["titel"] for a in zwei] == [
        "2025-06-06_Anlass-01", "2025-06-06_Anlass-02"]
    assert zwei[0]["bis"] == "10:00" and zwei[1]["von"] == "11:01"


def test_anlass_nummerierung_je_tag():
    """Drei Sitzungen an einem Tag werden 01, 02, 03."""
    zeilen = [_zeile("IMG_20250606_080000000.jpg"),
              _zeile("IMG_20250606_120000000.jpg"),
              _zeile("IMG_20250606_200000000.jpg")]
    anlaesse = foto.anlaesse_bilden(zeilen)
    assert [a["nummer"] for a in anlaesse] == [1, 2, 3]
    assert [a["titel"] for a in anlaesse][-1] == "2025-06-06_Anlass-03"


def test_anlass_ohne_uhrzeit_ans_tagesende():
    """WhatsApp-Empfang (Datum ohne Uhrzeit) wird ein eigener Anlass."""
    zeilen = [_zeile("IMG_20250606_100000000.jpg"),
              _zeile("IMG-20250606-WA0001.jpg"),
              _zeile("IMG-20250606_100100000.jpg")]
    anlaesse = foto.anlaesse_bilden(zeilen)
    assert len(anlaesse) == 2
    letzter = anlaesse[-1]
    assert letzter["ohne_uhrzeit"] is True
    assert letzter["nummer"] == 2 and letzter["von"] == ""
    assert letzter["zeilen"][0]["datei"] == "IMG-20250606-WA0001.jpg"


def test_anlass_ohne_datum_uebersprungen():
    """Zeilen ohne Datum bilden keinen Anlass (und keine Luecke)."""
    zeilen = [_zeile("Oplus_0.mp4", jahr="", monat="", tag=""),
              _zeile("IMG_20250606_100000000.jpg")]
    anlaesse = foto.anlaesse_bilden(zeilen)
    assert len(anlaesse) == 1 and anlaesse[0]["anzahl"] == 1
    assert foto.datum_teile(zeilen[0]) is None


def test_anlass_summen_videos_bytes():
    """Anzahl, Video-Kennzeichen und Bytes summieren sich je Anlass."""
    zeilen = [_zeile("IMG_20250606_100000000.jpg", bytes_wert="2000"),
              _zeile("VID_20250606_100010.mp4", bytes_wert="5000"),
              _zeile("IMG-20250606-WA0002.jpg", bytes_wert="300")]
    anlaesse = foto.anlaesse_bilden(zeilen)
    gesamt = {a["titel"]: a for a in anlaesse}
    assert gesamt["2025-06-06_Anlass-01"]["anzahl"] == 2
    assert gesamt["2025-06-06_Anlass-01"]["videos"] == 1
    assert gesamt["2025-06-06_Anlass-01"]["bytes"] == 7000
    assert gesamt["2025-06-06_Anlass-02"]["bytes"] == 300
    assert foto.ist_video("VID_20250606_100010.mp4")
    assert not foto.ist_video("IMG_20250606_100000000.jpg")


def test_anlass_luecke_null_wird_abgelehnt():
    """Die Luecken-Regel braucht mindestens 1 Minute."""
    with pytest.raises(foto.FotoThemenFehler):
        foto.anlaesse_bilden([], luecke_minuten=0)


# ── Kontaktbogen (Bildpixel pruefen) ───────────────────────────────────────

def _anlass(zeilen):
    return {
        "titel": "2025-06-06_Anlass-01", "jahr": 2025, "datum": "2025-06-06",
        "von": "18:57", "bis": "19:05", "ohne_uhrzeit": False, "nummer": 1,
        "anzahl": len(zeilen),
        "videos": sum(1 for z in zeilen if foto.ist_video(z["datei"])),
        "bytes": sum(int(z.get("bytes") or 0) for z in zeilen),
        "zeilen": zeilen,
    }


def test_bogen_entsteht_mit_nummern():
    """Der Bogen entsteht, hat die erwartete Groesse und Nummern-Kaesten."""
    zeilen = [_zeile("IMG_20250606_185746027_BURST008.jpg"),
              _zeile("IMG_20250606_185759123_BURST009.jpg")]
    for nummer, zeile in enumerate(zeilen, start=1):
        zeile["fileid"] = 900 + nummer
    bogen = foto.bogen_bauen(_anlass(zeilen),
                             {901: _jpeg((10, 90, 200)),
                              902: _jpeg((200, 90, 10), (120, 68))},
                             spalten=2, kachel=160)
    assert len(bogen) > 0
    assert bogen[:3] == b"\xff\xd8\xff"          # JPEG-Anfang

    bild = Image.open(io.BytesIO(bogen))
    rand, abstand = 16, 10
    assert bild.size == (2 * rand + 2 * 160 + abstand, 2 * rand + 160)
    pixel = bild.load()
    for spalte in range(2):
        x = rand + spalte * (160 + abstand)
        hell = sum(1 for xx in range(x + 4, x + 50)
                   for yy in range(rand + 4, rand + 40)
                   if all(k > 200 for k in pixel[xx, yy]))
        dunkel = sum(1 for xx in range(x + 4, x + 50)
                     for yy in range(rand + 4, rand + 40)
                     if all(k < 30 for k in pixel[xx, yy]))
        assert hell > 20, f"Nummerntext fehlt in Kachel {spalte + 1}"
        assert dunkel > 100, f"Nummernkasten fehlt in Kachel {spalte + 1}"


def test_bogen_kachelgroesse_und_spalten_folgen_den_argumenten():
    """Andere Kachelgroesse/Spaltenzahl aendern die Bogengroesse exakt."""
    zeilen = [_zeile("IMG_20250606_100000000.jpg")]
    zeilen[0]["fileid"] = 901
    bogen = foto.bogen_bauen(_anlass(zeilen), {901: _jpeg((90, 90, 90))},
                             spalten=1, kachel=100)
    bild = Image.open(io.BytesIO(bogen))
    rand = 10                                   # max(8, kachel // 10)
    assert bild.size == (2 * rand + 100, 2 * rand + 100)


def test_bogen_platzhalter_und_video_kennzeichen():
    """Ohne Vorschaubild: Text-Platzhalter; Video mit Bild: Kennzeichen."""
    zeilen = [_zeile("IMG_20250606_100000000.jpg"),
              _zeile("VID_20250606_100010.mp4"),
              _zeile("IMG_20250606_100020.jpg")]
    for nummer, zeile in enumerate(zeilen, start=1):
        zeile["fileid"] = 900 + nummer
    bogen = foto.bogen_bauen(
        _anlass(zeilen),
        {901: _jpeg((10, 10, 200)), 902: _jpeg((30, 160, 60)), 903: None},
        spalten=3, kachel=160)
    bild = Image.open(io.BytesIO(bogen))
    pixel = bild.load()
    rand, abstand = 16, 10

    # Kachel 3 hat kein Vorschaubild -> heller Text "kein Bild" in der Mitte.
    x = rand + 2 * (160 + abstand)
    mitte = sum(1 for xx in range(x + 20, x + 140)
                for yy in range(rand + 60, rand + 100)
                if all(k > 200 for k in pixel[xx, yy]))
    assert mitte > 100, "Platzhaltertext fehlt"

    # Kachel 2 ist ein Video MIT Bild -> rotes VIDEO-Kennzeichen unten rechts.
    x = rand + 1 * (160 + abstand)
    rot = sum(1 for xx in range(x + 70, x + 160)
              for yy in range(rand + 110, rand + 160)
              if pixel[xx, yy][0] > 120 and pixel[xx, yy][1] < 90
              and pixel[xx, yy][2] < 90)
    assert rot > 50, "VIDEO-Kennzeichen fehlt"

    # Und die Nummern sind trotzdem auf allen Kacheln.
    for spalte in range(3):
        x = rand + spalte * (160 + abstand)
        dunkel = sum(1 for xx in range(x + 4, x + 50)
                     for yy in range(rand + 4, rand + 40)
                     if all(k < 30 for k in pixel[xx, yy]))
        assert dunkel > 100, f"Nummernkasten fehlt in Kachel {spalte + 1}"


# ── Zuordnungs-JSON ────────────────────────────────────────────────────────

def test_zuordnung_json_vollstaendig(tmp_path):
    """Das JSON traegt je Kachel Nummer, fileid, Name, Groesse, ist_video."""
    anlass = _anlass([_zeile("IMG_20250606_100000000.jpg"),
                      _zeile("VID_20250606_100010.mp4")])
    eintraege = [
        {"kachel": 1, "fileid": 901, "datei": "IMG_20250606_100000000.jpg",
         "bytes": 2000, "ist_video": False, "ordner": "P:/x"},
        {"kachel": 2, "fileid": 902, "datei": "VID_20250606_100010.mp4",
         "bytes": 5000, "ist_video": True, "ordner": "P:/x"},
    ]
    ziel = tmp_path / "2025-06-06_Anlass-01.json"
    daten = foto.zuordnung_schreiben(anlass, eintraege, str(ziel))
    gelesen = json.loads(ziel.read_text(encoding="utf-8"))
    assert gelesen == daten
    assert gelesen["titel"] == "2025-06-06_Anlass-01"
    assert gelesen["anzahl"] == 2 and gelesen["anzahl_videos"] == 1
    assert gelesen["bogen"] == "2025-06-06_Anlass-01.jpg"
    assert [k["kachel"] for k in gelesen["kacheln"]] == [1, 2]
    assert gelesen["kacheln"][1]["fileid"] == 902
    assert gelesen["kacheln"][1]["ist_video"] is True
    assert gelesen["kacheln"][0]["bytes"] == 2000
    assert all(k["datei"] for k in gelesen["kacheln"])


def test_zuordnung_lehnt_luecken_ab(tmp_path):
    """Eine unvollstaendige Nummerierung wird nicht geschrieben."""
    anlass = _anlass([_zeile("IMG_20250606_100000000.jpg")])
    ziel = tmp_path / "x.json"
    with pytest.raises(foto.FotoThemenFehler):
        foto.zuordnung_schreiben(
            anlass,
            [{"kachel": 2, "fileid": 1, "datei": "a.jpg", "bytes": 1,
              "ist_video": False, "ordner": ""}],
            str(ziel))
    assert not ziel.exists()


# ── Vorschaubilder holen ───────────────────────────────────────────────────

def test_vorschau_holen_wiederholt_bei_netzfehler():
    """Zwei Netzfehler, dritter Versuch klappt — Bytes kommen zurueck."""
    bild = _jpeg((1, 2, 3))
    attrappe = FakeThumbs({42: bild}, fehler_bis=2)
    ergebnis = foto.vorschau_holen(42, abruf=attrappe)
    assert ergebnis == bild
    assert len(attrappe.aufrufe) == 3


def test_vorschau_holen_gibt_nach_drei_versuchen_auf():
    """Nach drei Netzfehlern gibt es eine klare Meldung, keinen Absturz."""
    attrappe = FakeThumbs({}, fehler_bis=99)
    with pytest.raises(foto.FotoThemenFehler) as fehler:
        foto.vorschau_holen(42, abruf=attrappe)
    assert len(attrappe.aufrufe) == 3
    assert "nach 3 Versuchen" in str(fehler.value)
    assert "Netz weg" not in str(fehler.value)   # fremder Text wird nicht uebernommen


def test_vorschau_ohne_bild_wird_nicht_wiederholt():
    """Code 5002 ist eine definitive Antwort — kein zweiter Aufruf."""
    attrappe = FakeThumbs({42: None})
    with pytest.raises(foto.FotoThemenFehler) as fehler:
        foto.vorschau_holen(42, abruf=attrappe)
    assert len(attrappe.aufrufe) == 1
    assert "5002" in str(fehler.value)


def test_vorschau_stapel_stapelt_und_ordnet_ueber_die_fileid():
    """30 ids = zwei Aufrufe (25+5); Zuordnung ueber fileid, nicht Position."""
    bilder = {i: _jpeg((i % 250, 10, 10)) for i in range(1, 31)}
    bilder[7] = None                                  # ohne Vorschaubild
    attrappe = FakeThumbs(bilder, verkehrt=True)      # Antwortreihenfolge verdreht
    ergebnis = foto.vorschau_stapel(list(range(1, 31)), abruf=attrappe,
                                    max_pro_aufruf=25)
    assert [len(a) for a in attrappe.aufrufe] == [25, 5]
    assert ergebnis[7] is None
    for i in range(1, 31):
        if i != 7:
            assert ergebnis[i] == bilder[i], f"fileid {i} falsch zugeordnet"


def test_groesse_wird_geprueft():
    """Erlaubt sind nur die zwei pCloud-Groessen."""
    foto.pruefe_groesse("120x120")
    foto.pruefe_groesse("32x32")
    with pytest.raises(foto.FotoThemenFehler):
        foto.vorschau_holen(1, groesse="500x500", abruf=Stolperfalle())


# ── Datei-/Ordner-Aufloesung ueber die API ─────────────────────────────────

def test_dateien_im_ordner_ueber_fileid_baum():
    """Der CSV-Ordner P:/... wird im API-Baum aufgeloest, Namen -> fileid."""
    api = FakeApi(_testbaum())
    speicher = {}
    index = foto.dateien_im_ordner("P:/Automatic Upload/Testgeraet", api, speicher)
    assert index["IMG_20250606_185746027_BURST008.jpg"]["fileid"] == 901
    assert index["VID_20250606_190500.mp4"]["fileid"] == 903
    assert index["VID_20250606_190500.mp4"]["groesse"] == 5100000
    # Mit geteiltem Zwischenspeicher wird kein Ordner zweimal gelesen.
    vorher = list(api.aufrufe)
    foto.dateien_im_ordner("P:/Automatic Upload/Testgeraet", api, speicher)
    assert api.aufrufe == vorher

    # Unbekannter Pfad liefert ehrlich nichts (kein erfundenes fileid).
    assert foto.dateien_im_ordner("P:/Automatic Upload/Gibtsnicht", api) == {}


# ── Geheimnis: der Token taucht nirgends auf ───────────────────────────────

def test_token_taucht_in_fehlermeldung_nicht_auf(tmp_path, monkeypatch):
    """Auch wenn eine fremde Ausnahme den Token enthielte: geputzt."""
    env = tmp_path / "probe.env"
    env.write_text(f"PCLOUD_TOKEN={TOKEN}\nPCLOUD_HOST=eapi.example\n",
                   encoding="utf-8")

    def boese(*args, **kwargs):
        raise RuntimeError(f"kaputt bei https://x/?auth={TOKEN}")

    monkeypatch.setattr(foto.httpx, "get", boese)
    abruf = foto.echter_thumb_abruf(str(env))
    with pytest.raises(foto.FotoThemenFehler) as fehler:
        foto.vorschau_holen(42, abruf=abruf)
    assert TOKEN not in str(fehler.value)
    assert TOKEN not in repr(fehler.value)
    assert foto.ohne_token(f"leak {TOKEN} hier", TOKEN) == "leak *** hier"

    # Der API-Abruf (listfolder) verhaelt sich genauso.
    api = foto.echter_api_abruf(str(env))
    with pytest.raises(foto.FotoThemenFehler) as fehler2:
        api("/listfolder", {"folderid": 0})
    assert TOKEN not in str(fehler2.value)


# ── Kommandozeile: trocken, nur-liste, idempotent ──────────────────────────

def test_trockenlauf_holt_und_schreibt_nichts(tmp_path, capsys):
    """--trocken plant nur: kein API-Aufruf, keine Datei."""
    csv_pfad = _csv_schreiben(tmp_path / "s.csv", [
        _zeile("IMG_20250606_100000000.jpg"),
        _zeile("IMG_20250606_100100000.jpg")])
    boegen = tmp_path / "boegen"
    code = foto.main(["--csv", csv_pfad, "--boegen", str(boegen),
                      "--jahr", "2025", "--limit", "3", "--trocken"],
                     api_abruf=Stolperfalle(), thumb_abruf=Stolperfalle())
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "Trockenlauf" in ausgabe
    assert "2025-06-06_Anlass-01" in ausgabe
    assert not boegen.exists()


def test_nur_liste_ohne_netz(tmp_path, capsys):
    """--nur-liste zeigt die geplanten Anlaesse, ohne etwas anzufassen."""
    csv_pfad = _csv_schreiben(tmp_path / "s.csv", [
        _zeile("IMG_20250606_100000000.jpg"),
        _zeile("IMG_20250607_100000000.jpg", tag="7")])
    boegen = tmp_path / "boegen"
    code = foto.main(["--csv", csv_pfad, "--boegen", str(boegen),
                      "--jahr", "2025", "--nur-liste"],
                     api_abruf=Stolperfalle(), thumb_abruf=Stolperfalle())
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "Nur-Liste" in ausgabe
    assert "2025-06-06_Anlass-01" in ausgabe
    assert "2025-06-07_Anlass-01" in ausgabe
    assert "Anlaesse gesamt: 2" in ausgabe
    assert not boegen.exists()


def test_cli_baut_bogen_und_ueberspringt_beim_zweiten_lauf(tmp_path, capsys):
    """Erster Lauf baut Bogen + JSON; zweiter Lauf ueberspringt (idempotent)."""
    csv_pfad = _csv_schreiben(tmp_path / "s.csv", [
        _zeile("IMG_20250606_185746027_BURST008.jpg"),
        _zeile("IMG_20250606_185759123_BURST009.jpg"),
        _zeile("VID_20250606_190500.mp4")])
    boegen = tmp_path / "boegen"
    api = FakeApi(_testbaum())
    thumbs = FakeThumbs({901: _jpeg((10, 90, 200)),
                         902: _jpeg((200, 90, 10)),
                         903: _jpeg((30, 160, 60), (120, 68))})

    code = foto.main(["--csv", csv_pfad, "--boegen", str(boegen),
                      "--jahr", "2025"], api_abruf=api, thumb_abruf=thumbs)
    ausgabe = capsys.readouterr().out
    assert code == 0
    ziel = boegen / "2025" / "2025-06-06_Anlass-01.jpg"
    json_ziel = boegen / "2025" / "2025-06-06_Anlass-01.json"
    assert ziel.exists() and json_ziel.exists()
    assert "3 Vorschauen geholt" in ausgabe
    assert "gebaut: 1" in ausgabe

    zuordnung = json.loads(json_ziel.read_text(encoding="utf-8"))
    assert zuordnung["anzahl"] == 3
    assert [k["kachel"] for k in zuordnung["kacheln"]] == [1, 2, 3]
    assert zuordnung["kacheln"][2]["ist_video"] is True
    assert zuordnung["kacheln"][0]["fileid"] == 901

    vorher_aufrufe = len(thumbs.aufrufe)
    code = foto.main(["--csv", csv_pfad, "--boegen", str(boegen),
                      "--jahr", "2025"], api_abruf=api, thumb_abruf=thumbs)
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "uebersprungen (Bogen vorhanden)" in ausgabe
    assert "gebaut: 0" in ausgabe and "uebersprungen: 1" in ausgabe
    assert len(thumbs.aufrufe) == vorher_aufrufe      # kein zweiter Abruf
