"""Tests für das Postfach des Wechselassistenten (G5/G6)."""
from __future__ import annotations

import json
import os

import pytest

from master_schalter import assistent_vorgaenge as av
from master_schalter import modi, paare, postfach

THEMA = "engineering"
LAUFEND = paare.laufend_bilden(THEMA)
SITZUNG = "sitzung-a"


def _wechsel(umgebung, vorgang_id, ziel="hermes", von="claude"):
    """Vorgang vermerken, Rolle setzen und beide Nachrichten einlegen (wie der Assistent)."""
    umgebung.vorbereiten(vorgang_id, ziel=ziel, von=von)
    umgebung.uebergeben(vorgang_id, ziel)
    av.aktualisieren(vorgang_id, phase="im_postfach")
    postfach.einlegen(ziel, "neu-sitzung", vorgang_id, THEMA, "neu", LAUFEND)
    postfach.einlegen(von, "alt-sitzung", vorgang_id, THEMA, "abgabe", LAUFEND)


def _dateien(umgebung, ziel="hermes", kennung="neu-sitzung"):
    ordner = postfach.ordner(ziel, kennung)
    return sorted(p.name for p in ordner.glob("*.json")) if ordner.is_dir() else []


# --- Einlegen ---------------------------------------------------------------------

def test_einlegen_schreibt_nur_die_erlaubten_felder_unter_der_festen_wurzel(umgebung):
    pfad = postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)

    assert pfad == umgebung.daten / "postfach" / "claude" / SITZUNG / "v-1.json"
    inhalt = json.loads(pfad.read_text(encoding="utf-8"))
    assert set(inhalt) == {"vorgang", "thema", "rolle", "laufend", "zeit"}
    assert (inhalt["vorgang"], inhalt["thema"], inhalt["rolle"], inhalt["laufend"]) == (
        "v-1", THEMA, "neu", LAUFEND)
    assert pfad.stat().st_size <= postfach.MAX_BYTES


def test_doppelt_einlegen_ergibt_genau_eine_unveraenderte_datei(umgebung):
    pfad = postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)
    erster_inhalt = pfad.read_text(encoding="utf-8")

    zweiter = postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)

    assert zweiter == pfad
    assert _dateien(umgebung, "claude", SITZUNG) == ["v-1.json"]
    assert pfad.read_text(encoding="utf-8") == erster_inhalt
    assert [p.name for p in pfad.parent.iterdir()] == ["v-1.json"]      # keine tmp-Reste


def test_abbruch_zwischen_tmp_und_replace_hinterlaesst_keine_nachricht_und_ist_wiederholbar(
        umgebung, monkeypatch):
    def kaputt(quelle, ziel):
        raise OSError("synthetischer Abbruch vor dem Ersetzen")

    with monkeypatch.context() as m:
        m.setattr(os, "replace", kaputt)
        with pytest.raises(OSError):
            postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)

    assert _dateien(umgebung, "claude", SITZUNG) == []
    assert [p for p in postfach.ordner("claude", SITZUNG).iterdir()] == []   # tmp aufgeräumt
    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []
    postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)        # Wiederholung klappt
    assert _dateien(umgebung, "claude", SITZUNG) == ["v-1.json"]


def test_liegengebliebene_tmp_datei_wird_beim_abholen_ignoriert(umgebung):
    ordner = postfach.ordner("claude", SITZUNG)
    ordner.mkdir(parents=True)
    (ordner / "v-1.json.abc123.tmp").write_text("{halb", encoding="utf-8")
    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []
    assert (ordner / "v-1.json.abc123.tmp").exists()
    assert not (ordner / "verworfen").exists()


@pytest.mark.parametrize("kennung", ["..", "../x", "a/b", "a\\b", "/abs", "C:\\x", "", ".", "x\n", "a" * 81,
                                     "sitz ung", "ä", "..\\..\\x"])
def test_unzulaessige_kennung_wird_abgelehnt(umgebung, kennung):
    with pytest.raises(postfach.PostfachFehler):
        postfach.einlegen("claude", kennung, "v-1", THEMA, "neu", LAUFEND)
    with pytest.raises(postfach.PostfachFehler):
        postfach.abholen("claude", kennung, umgebung.repo)
    assert not (umgebung.daten / "postfach").exists()


@pytest.mark.parametrize("ziel", ["codex", "../claude", "", "Claude", "claude/x", "x"])
def test_unzulaessiges_ziel_wird_abgelehnt(umgebung, ziel):
    with pytest.raises(postfach.PostfachFehler):
        postfach.einlegen(ziel, SITZUNG, "v-1", THEMA, "neu", LAUFEND)


@pytest.mark.parametrize("feld, wert", [("vorgang_id", "../v"), ("vorgang_id", "a\\b"), ("vorgang_id", "v\n"),
                                        ("thema", "Gross"), ("thema", "../x"), ("rolle", "beide"),
                                        ("laufend", "../../etc/passwd"), ("laufend", ".hermes/uebergabe/laufend/x.md")])
def test_unzulaessige_felder_werden_beim_einlegen_abgelehnt(umgebung, feld, wert):
    args = {"vorgang_id": "v-1", "thema": THEMA, "rolle": "neu", "laufend": LAUFEND, feld: wert}
    with pytest.raises(postfach.PostfachFehler):
        postfach.einlegen("claude", SITZUNG, args["vorgang_id"], args["thema"], args["rolle"], args["laufend"])
    assert not (umgebung.daten / "postfach").exists() or _dateien(umgebung, "claude", SITZUNG) == []


def test_ordner_muss_unter_der_wurzel_aufloesen(umgebung, monkeypatch):
    # Auch ein (z. B. per Verknüpfung) herausführender Ordner wird erkannt: resolve() entscheidet.
    from pathlib import Path
    echt = Path.resolve

    def umgeleitet(self, *args, **kwargs):
        if self.name == SITZUNG:
            return umgebung.daten.parent / "woanders"
        return echt(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", umgeleitet)
    with pytest.raises(postfach.PostfachFehler, match="außerhalb"):
        postfach.ordner("claude", SITZUNG)


def test_groessenlimit_beim_einlegen(umgebung, monkeypatch):
    monkeypatch.setattr(postfach, "MAX_BYTES", 40)
    with pytest.raises(postfach.PostfachFehler, match="größer"):
        postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)
    assert _dateien(umgebung, "claude", SITZUNG) == []


# --- Abholen: Gültigkeit (G5) ------------------------------------------------------

def test_gueltige_neu_nachricht_wird_zugestellt_der_vorgang_ist_im_chat_aber_nicht_bestaetigt(umgebung):
    _wechsel(umgebung, "v-1")

    erg = postfach.abholen("hermes", "neu-sitzung", umgebung.repo)

    assert len(erg) == 1 and erg[0].rolle == "neu" and erg[0].vorgang == "v-1"
    assert erg[0].text == (f"Du führst jetzt das Thema {THEMA}. Lies zuerst {LAUFEND}, "
                           "dann führe `masterwechsel quittieren v-1 neu` aus.")
    assert av.finden("v-1").phase == "im_chat"                        # Abholung ≠ Übernahme
    assert _dateien(umgebung) == []
    assert (postfach.ordner("hermes", "neu-sitzung") / "erledigt" / "v-1.json").exists()
    assert postfach.abholen("hermes", "neu-sitzung", umgebung.repo) == []   # nur einmal


def test_gueltige_abgabe_nachricht_geht_an_den_alten_master(umgebung):
    _wechsel(umgebung, "v-1")

    erg = postfach.abholen("claude", "alt-sitzung", umgebung.repo)

    assert len(erg) == 1 and erg[0].rolle == "abgabe"
    assert erg[0].text == (f"Du führst das Thema {THEMA} nicht mehr. Schließe den laufenden Schritt "
                           "sauber ab, beginne keinen neuen und führe "
                           "`masterwechsel quittieren v-1 abgabe` aus.")


def test_fremde_kennung_wird_nicht_gelesen(umgebung):
    _wechsel(umgebung, "v-1")

    assert postfach.abholen("hermes", "andere-sitzung", umgebung.repo) == []
    assert postfach.abholen("claude", "neu-sitzung", umgebung.repo) == []   # richtige Kennung, falsches Ziel
    assert _dateien(umgebung) == ["v-1.json"]                                # unberührt
    assert av.finden("v-1").phase == "im_postfach"


def test_neu_nachricht_an_die_falsche_rolle_wird_verworfen(umgebung):
    umgebung.vorbereiten("v-1", ziel="hermes")
    umgebung.uebergeben("v-1", "hermes")
    postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)       # Marke nennt hermes, nicht claude

    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []
    grund = json.loads((postfach.ordner("claude", SITZUNG) / "verworfen" / "v-1.json").read_text("utf-8"))["grund"]
    assert "hermes" in grund
    assert av.finden("v-1").phase == "vorbereitet"                            # nicht im Chat


def test_a_b_a_beide_alten_nachrichten_werden_verworfen(umgebung):
    _wechsel(umgebung, "v-1", ziel="hermes", von="claude")
    _wechsel(umgebung, "v-2", ziel="claude", von="hermes")                    # zurück an Claude

    assert postfach.abholen("hermes", "neu-sitzung", umgebung.repo) == []     # B bekommt weder neu v-1 ...
    assert [n.vorgang for n in postfach.abholen("claude", "neu-sitzung", umgebung.repo)] == ["v-2"]
    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []     # ... noch A die Abgabe v-1
    verworfen = postfach.ordner("hermes", "neu-sitzung") / "verworfen"
    assert (verworfen / "v-1.json").exists()
    assert "anderen Vorgang" in json.loads((verworfen / "v-1.json").read_text("utf-8"))["grund"]
    assert av.finden("v-1").phase != "im_chat"


def test_menuewechsel_nach_der_uebergabe_macht_auftraege_ungueltig(umgebung):
    _wechsel(umgebung, "v-1")
    modi.master_setzen(THEMA, "codex", repo=umgebung.repo)

    assert postfach.abholen("hermes", "neu-sitzung", umgebung.repo) == []
    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []


def test_unbekannter_oder_verworfener_vorgang_wird_verworfen(umgebung):
    umgebung.uebergeben("v-ohne-eintrag", "hermes")
    postfach.einlegen("hermes", SITZUNG, "v-ohne-eintrag", THEMA, "neu", LAUFEND)
    assert postfach.abholen("hermes", SITZUNG, umgebung.repo) == []
    assert (postfach.ordner("hermes", SITZUNG) / "verworfen" / "v-ohne-eintrag.json").exists()


def test_erreichte_bestaetigung_wird_durch_spaete_abholung_nicht_zurueckgesetzt(umgebung):
    _wechsel(umgebung, "v-1")
    av.quittieren("v-1", "neu", umgebung.repo)

    assert len(postfach.abholen("claude", "alt-sitzung", umgebung.repo)) == 1
    assert av.finden("v-1").phase == "bestaetigt"


def test_nicht_lesbare_marke_laesst_die_datei_liegen(umgebung, monkeypatch):
    _wechsel(umgebung, "v-1")

    def unlesbar(datei):
        raise modi.ModusFehler("Besitzstatus nicht lesbar")

    monkeypatch.setattr(modi, "_besitz_text_lesen", unlesbar)
    assert postfach.abholen("hermes", "neu-sitzung", umgebung.repo) == []
    assert _dateien(umgebung) == ["v-1.json"]


def test_nach_der_abholung_wird_nicht_erneut_eingelegt(umgebung):
    _wechsel(umgebung, "v-1")
    postfach.abholen("hermes", "neu-sitzung", umgebung.repo)

    postfach.einlegen("hermes", "neu-sitzung", "v-1", THEMA, "neu", LAUFEND)

    assert _dateien(umgebung) == []


# --- Abholen: kaputte Dateien -------------------------------------------------------

def _roh_einlegen(umgebung, name, inhalt, ziel="claude"):
    ordner = postfach.ordner(ziel, SITZUNG)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / name).write_text(inhalt if isinstance(inhalt, str) else json.dumps(inhalt), encoding="utf-8")
    return ordner


def _gut(**aenderung):
    return {"vorgang": "v-1", "thema": THEMA, "rolle": "neu", "laufend": LAUFEND,
            "zeit": "2026-10-20T10:00:00+00:00", **aenderung}


def test_zu_grosse_datei_wird_nicht_gelesen_sondern_verworfen(umgebung):
    ordner = _roh_einlegen(umgebung, "v-1.json", _gut(zeit="x" * 5000))
    assert (ordner / "v-1.json").stat().st_size > postfach.MAX_BYTES

    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []

    assert not (ordner / "v-1.json").exists()
    assert "größer" in json.loads((ordner / "verworfen" / "v-1.json").read_text("utf-8"))["grund"]


@pytest.mark.parametrize("inhalt", [
    "{kein json", "[]", '"text"', _gut(extra="x"), {k: v for k, v in _gut().items() if k != "zeit"},
    _gut(vorgang="v-2"), _gut(thema="../x"), _gut(rolle="beide"), _gut(laufend="/etc/passwd"),
    _gut(zeit=5),
])
def test_ungueltiger_inhalt_wird_verworfen(umgebung, inhalt):
    ordner = _roh_einlegen(umgebung, "v-1.json", inhalt)

    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []

    assert not (ordner / "v-1.json").exists()
    assert (ordner / "verworfen" / "v-1.json").exists()


def test_dateien_mit_fremdem_namen_werden_nicht_angefasst(umgebung):
    ordner = _roh_einlegen(umgebung, "notizen.txt", "hallo")
    _roh_einlegen(umgebung, "..x.json", _gut())
    (ordner / "ordner.json").mkdir()
    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []
    assert sorted(p.name for p in ordner.iterdir()) == ["..x.json", "notizen.txt", "ordner.json"]
