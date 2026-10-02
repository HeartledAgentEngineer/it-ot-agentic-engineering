"""Tests: digitales Fotobuch (CEWE .mcf) -> Seiten der Erzaehl-Diashow (02.10.2026).

Erfundenes Mini-Buch, keine echten Daten.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJEKT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

from app.services import erzaehl_service  # noqa: E402

_spez = importlib.util.spec_from_file_location(
    "fotobuch_lesen", os.path.join(PROJEKT, "tools", "foto_sortierung", "fotobuch_lesen.py"))
fb = importlib.util.module_from_spec(_spez)
_spez.loader.exec_module(fb)

MCF = r"""<?xml version="1.0" encoding="UTF-8"?>
<fotobook>
 <page pagenr="0" type="FULLCOVER"><area top="5" left="5"><image filename="cover.jpg"/></area></page>
 <page pagenr="1" type="CONTENT">
  <area top="200" left="10"><image filename="unten.jpg"/></area>
  <area top="10" left="300"><image filename="Ordner\rechts.JPG"/></area>
  <area top="10" left="10"><image filename="links.jpg"/></area>
  <area top="0" left="0"><text>&lt;html&gt;&lt;body&gt;&lt;p&gt;Sommer 2005 &amp;amp; Ostsee&lt;/p&gt;&lt;p&gt;zweite&amp;nbsp;Zeile&lt;/p&gt;&lt;/body&gt;&lt;/html&gt;</text></area>
 </page>
 <page type="EMPTY"/>
 <page type="SPINE"><area><text>Ruecken</text></area></page>
 <page pagenr="2" type="CONTENT"><area top="1" left="1"><image filename="fehlt.jpg"/></area></page>
 <page pagenr="3" type="FULLCOVER"><area top="1" left="1"><image filename="hinten.jpg"/></area></page>
</fotobook>"""
NAMEN = {"cover.jpg": 10, "unten.jpg": 11, "rechts.jpg": 12, "links.jpg": 13, "hinten.jpg": 14}


def _buch(tmp_path):
    ordner = tmp_path / "buch"
    ordner.mkdir()
    (ordner / "Buddy_Jule.mcf").write_text(MCF, encoding="utf-8")
    return ordner


def test_seiten_in_buchreihenfolge_bilder_nach_position_texte_als_klartext(tmp_path):
    seiten = fb.seiten_lesen(str(_buch(tmp_path) / "Buddy_Jule.mcf"))
    assert [(s["typ"], s["seite"]) for s in seiten] == [("FULLCOVER", 0), ("CONTENT", 1), ("CONTENT", 2), ("FULLCOVER", 0)]
    assert seiten[1]["bilder"] == ["links.jpg", "rechts.JPG", "unten.jpg"]      # oben->unten, links->rechts
    assert seiten[1]["texte"] == ["Sommer 2005 & Ostsee\nzweite Zeile"]


def test_ereignisse_im_format_der_diashow(tmp_path):
    seiten = fb.seiten_lesen(str(_buch(tmp_path) / "Buddy_Jule.mcf"))
    ereignisse, z = fb.ereignisse_bauen(seiten, NAMEN, "Fotobuch Buddy Jule", "fotobuch-buddy-jule")
    assert z == {"seiten": 4, "mit_bildern": 3, "bilder": 6, "gefunden": 5, "texte": 1}
    kennungen = [e["kennung"] for e in ereignisse]
    assert len(set(kennungen)) == len(kennungen)                              # zwei Umschlaege, eindeutig
    s1 = next(e for e in ereignisse if e["seite"] == 1)
    assert s1["datei_kennungen"] == [13, 12, 11] and s1["anzahl_dateien"] == 3
    assert s1["titel"] == "Fotobuch Buddy Jule · S. 1 – Sommer 2005 & Ostsee"
    assert ereignisse[0]["titel"] == "Fotobuch Buddy Jule · Umschlag"
    assert all(e["kategorie"] == "Fotobuch" for e in ereignisse)
    assert not any(e["seite"] == 2 for e in ereignisse)                      # nur fehlendes Bild, kein Text


def test_trockenlauf_nur_zahlen_und_schreiben_ausserhalb(tmp_path, capsys, monkeypatch):
    ordner = _buch(tmp_path)
    monkeypatch.setattr(fb, "fileids_holen", lambda ordner, abruf=None: dict(NAMEN))
    ziel = tmp_path / "aus" / "fotobuch_ereignisse.jsonl"
    assert fb.main(["--ordner", str(ordner), "--ausgabe", str(ziel)]) == 0
    aus = capsys.readouterr().out
    assert "Seiten: 4" in aus and "Sommer" not in aus and ".jpg" not in aus
    assert not ziel.exists()
    assert fb.main(["--ordner", str(ordner), "--ausgabe", str(ziel), "--schreiben"]) == 0
    zeilen = [json.loads(z) for z in ziel.read_text(encoding="utf-8").splitlines()]
    assert len(zeilen) == 3 and zeilen[1]["texte"][0].startswith("Sommer 2005")


def test_schutz_repo_ziel_und_fehlende_mcf(tmp_path, monkeypatch):
    monkeypatch.setattr(fb, "fileids_holen", lambda ordner, abruf=None: {})
    assert fb.main(["--ordner", str(_buch(tmp_path)), "--ausgabe", os.path.join(PROJEKT, "x.jsonl"), "--schreiben"]) == 2
    leer = tmp_path / "leer"
    leer.mkdir()
    assert fb.main(["--ordner", str(leer), "--ausgabe", str(tmp_path / "o.jsonl")]) == 3


def test_html_zu_text():
    assert fb.html_zu_text("<p>A&amp;B</p><p>  C <b>D</b> </p><br/>E") == "A&B\nC D\nE"
    assert fb.html_zu_text("") == ""


def test_diashow_zeigt_fotobuch_seiten_zuerst(tmp_path, monkeypatch):
    ereignisse = tmp_path / "ereignisse.jsonl"
    ereignisse.write_text(json.dumps({"kennung": "e1", "event": "Urlaub", "datei_kennungen": [1]}) + "\n",
                          encoding="utf-8")
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ereignisse))
    monkeypatch.delenv("ERZAEHL_FOTOBUCH_PFAD", raising=False)
    seiten = fb.seiten_lesen(str(_buch(tmp_path) / "Buddy_Jule.mcf"))
    buch, _ = fb.ereignisse_bauen(seiten, NAMEN, "Fotobuch Buddy Jule", "fbj")
    (tmp_path / "fotobuch_ereignisse.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in buch) + "\n", encoding="utf-8")
    liste = erzaehl_service.ereignisse_liste()
    titel = [e["titel"] for e in liste["eintraege"]]
    assert titel[0] == "Fotobuch Buddy Jule · Umschlag" and titel[-1] == "Urlaub"
    detail = erzaehl_service.ereignis_detail(buch[1]["kennung"])
    assert detail["datei_kennungen"] == [13, 12, 11]
