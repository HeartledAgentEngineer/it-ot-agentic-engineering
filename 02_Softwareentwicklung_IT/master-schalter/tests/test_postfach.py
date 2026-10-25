"""Tests für das Postfach des Wechselassistenten (G5/G6/G8): Einlegen, Abholen mit drei Ausgängen."""
from __future__ import annotations

import contextlib
import json
import os

import pytest

from master_schalter import assistent_vorgaenge as av
from master_schalter import modi, paare, postfach, zustand

THEMA = "engineering"
LAUFEND = paare.laufend_bilden(THEMA)
SITZUNG = "sitzung-a"


def _neu_einlegen(umgebung, vorgang_id, ziel="hermes", von="claude", phase="im_postfach"):
    """Rolle gesetzt (Marke trägt den Vorgang), Phase wie nach dem Einlegen, `neu` liegt im Postfach."""
    umgebung.vorbereiten(vorgang_id, ziel=ziel, von=von)
    umgebung.uebergeben(vorgang_id, ziel)
    av.aktualisieren(vorgang_id, phase=phase)
    postfach.einlegen(ziel, "neu-sitzung", vorgang_id, THEMA, "neu", LAUFEND)


def _abgabe_einlegen(umgebung, vorgang_id, ziel="hermes", von="claude", phase="abgabe_sende"):
    """Abgabe läuft: Marke ist noch der Vorzustand (alter Master), der Auftrag liegt für den alten Master bereit."""
    umgebung.vorbereiten(vorgang_id, ziel=ziel, von=von)
    if phase != "vorbereitet":
        av.abgabe_beginnen(vorgang_id)
        av.aktualisieren(vorgang_id, phase=phase)
    postfach.einlegen(von, "alt-sitzung", vorgang_id, THEMA, "abgabe_auftrag", LAUFEND)


def _dateien(umgebung, ziel="hermes", kennung="neu-sitzung"):
    ordner = postfach.ordner(ziel, kennung)
    return sorted(p.name for p in ordner.glob("*.json")) if ordner.is_dir() else []


def _grund(ziel, kennung, name):
    pfad = postfach.ordner(ziel, kennung) / "verworfen" / name
    return json.loads(pfad.read_text("utf-8"))["grund"]


# --- Einlegen ---------------------------------------------------------------------

def test_einlegen_schreibt_nur_die_erlaubten_felder_unter_der_festen_wurzel(umgebung):
    pfad = postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)

    assert pfad == umgebung.daten / "postfach" / "claude" / SITZUNG / "v-1_neu.json"
    inhalt = json.loads(pfad.read_text(encoding="utf-8"))
    assert set(inhalt) == {"vorgang", "thema", "rolle", "laufend", "zeit"}
    assert (inhalt["vorgang"], inhalt["thema"], inhalt["rolle"], inhalt["laufend"]) == (
        "v-1", THEMA, "neu", LAUFEND)
    assert pfad.stat().st_size <= postfach.MAX_BYTES


def test_dateiname_traegt_die_art_auftrag_und_info_liegen_nebeneinander(umgebung):
    auftrag = postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "abgabe_auftrag", LAUFEND)
    info = postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "abgabe_info", LAUFEND)

    assert (auftrag.name, info.name) == ("v-1_abgabe_auftrag.json", "v-1_abgabe_info.json")
    assert _dateien(umgebung, "claude", SITZUNG) == ["v-1_abgabe_auftrag.json", "v-1_abgabe_info.json"]
    assert json.loads(info.read_text("utf-8"))["rolle"] == "abgabe_info"


def test_doppelt_einlegen_ergibt_genau_eine_unveraenderte_datei(umgebung):
    pfad = postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)
    erster_inhalt = pfad.read_text(encoding="utf-8")

    zweiter = postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)

    assert zweiter == pfad
    assert _dateien(umgebung, "claude", SITZUNG) == ["v-1_neu.json"]
    assert pfad.read_text(encoding="utf-8") == erster_inhalt
    assert [p.name for p in pfad.parent.iterdir()] == ["v-1_neu.json"]      # keine tmp-Reste


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
    assert _dateien(umgebung, "claude", SITZUNG) == ["v-1_neu.json"]


def test_liegengebliebene_tmp_datei_wird_beim_abholen_ignoriert(umgebung):
    ordner = postfach.ordner("claude", SITZUNG)
    ordner.mkdir(parents=True)
    (ordner / "v-1_neu.json.abc123.tmp").write_text("{halb", encoding="utf-8")
    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []
    assert (ordner / "v-1_neu.json.abc123.tmp").exists()
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
                                        ("rolle", "abgabe"), ("rolle", "abgabe_auftrag/x"),
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


# --- Abholen: neu -------------------------------------------------------------------

def test_gueltige_neu_nachricht_wird_zugestellt_der_vorgang_ist_im_chat_aber_nicht_bestaetigt(umgebung):
    _neu_einlegen(umgebung, "v-1")

    erg = postfach.abholen("hermes", "neu-sitzung", umgebung.repo)

    assert len(erg) == 1 and erg[0].rolle == "neu" and erg[0].vorgang == "v-1"
    assert erg[0].text == (f"Du führst jetzt das Thema {THEMA}. Lies zuerst {LAUFEND}, "
                           "dann führe `masterwechsel quittieren v-1 neu` aus. "
                           "Schlägt die Quittung fehl, beginne keinen Schritt – die Nachricht gilt dann nicht mehr.")
    assert av.finden("v-1").phase == "im_chat"                        # Abholung ≠ Übernahme
    assert _dateien(umgebung) == []
    assert (postfach.ordner("hermes", "neu-sitzung") / "erledigt" / "v-1_neu.json").exists()
    assert postfach.abholen("hermes", "neu-sitzung", umgebung.repo) == []   # nur einmal


def test_fremde_kennung_wird_nicht_gelesen(umgebung):
    _neu_einlegen(umgebung, "v-1")

    assert postfach.abholen("hermes", "andere-sitzung", umgebung.repo) == []
    assert postfach.abholen("claude", "neu-sitzung", umgebung.repo) == []   # richtige Kennung, falsches Ziel
    assert _dateien(umgebung) == ["v-1_neu.json"]                            # unberührt
    assert av.finden("v-1").phase == "im_postfach"


def test_neu_nachricht_an_die_falsche_rolle_wird_verworfen(umgebung):
    umgebung.vorbereiten("v-1", ziel="hermes")
    umgebung.uebergeben("v-1", "hermes")
    av.aktualisieren("v-1", phase="rolle_gesetzt")
    postfach.einlegen("claude", SITZUNG, "v-1", THEMA, "neu", LAUFEND)       # Marke nennt hermes, nicht claude

    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []
    assert "hermes" in _grund("claude", SITZUNG, "v-1_neu.json")
    assert av.finden("v-1").phase == "rolle_gesetzt"                           # nicht im Chat


@pytest.mark.parametrize("phase", ["vorbereitet", "abgabe_sende", "abgabe_angefragt", "abgabe_unklar",
                                   "abgegeben", "abgabe_uebersprungen", "abgabe_fehler"])
def test_neu_vor_rolle_gesetzt_bleibt_liegen(umgebung, phase):
    umgebung.vorbereiten("v-1", ziel="hermes")
    av.aktualisieren("v-1", phase=phase)
    postfach.einlegen("hermes", SITZUNG, "v-1", THEMA, "neu", LAUFEND)

    assert postfach.abholen("hermes", SITZUNG, umgebung.repo) == []

    assert _dateien(umgebung, "hermes", SITZUNG) == ["v-1_neu.json"]          # weder verworfen noch zugestellt
    assert not (postfach.ordner("hermes", SITZUNG) / "verworfen").exists()
    assert av.finden("v-1").phase == phase


def test_neu_bei_unbekanntem_vorgang_bleibt_liegen_und_kommt_nach_dem_vermerk(umgebung):
    umgebung.uebergeben("v-ohne-eintrag", "hermes")
    postfach.einlegen("hermes", SITZUNG, "v-ohne-eintrag", THEMA, "neu", LAUFEND)

    assert postfach.abholen("hermes", SITZUNG, umgebung.repo) == []
    assert _dateien(umgebung, "hermes", SITZUNG) == ["v-ohne-eintrag_neu.json"]

    umgebung.vorbereiten("v-ohne-eintrag", phase="im_postfach")               # Vermerk kommt nach
    assert [n.vorgang for n in postfach.abholen("hermes", SITZUNG, umgebung.repo)] == ["v-ohne-eintrag"]


def test_neu_bei_verworfenem_vorgang_wird_verworfen(umgebung):
    umgebung.vorbereiten("v-1", phase="verworfen")
    postfach.einlegen("hermes", SITZUNG, "v-1", THEMA, "neu", LAUFEND)

    assert postfach.abholen("hermes", SITZUNG, umgebung.repo) == []
    assert _grund("hermes", SITZUNG, "v-1_neu.json") == "Vorgang wurde verworfen"


def test_a_b_a_alte_nachricht_wird_verworfen(umgebung):
    _neu_einlegen(umgebung, "v-1", ziel="hermes", von="claude")
    _neu_einlegen(umgebung, "v-2", ziel="claude", von="hermes")               # zurück an Claude

    assert postfach.abholen("hermes", "neu-sitzung", umgebung.repo) == []     # B bekommt `neu` v-1 nicht mehr
    assert [n.vorgang for n in postfach.abholen("claude", "neu-sitzung", umgebung.repo)] == ["v-2"]
    assert "anderen Vorgang" in _grund("hermes", "neu-sitzung", "v-1_neu.json")
    assert av.finden("v-1").phase != "im_chat"


def test_menuewechsel_nach_der_uebergabe_macht_neu_ungueltig(umgebung):
    _neu_einlegen(umgebung, "v-1")
    modi.master_setzen(THEMA, "codex", repo=umgebung.repo)

    assert postfach.abholen("hermes", "neu-sitzung", umgebung.repo) == []
    assert (postfach.ordner("hermes", "neu-sitzung") / "verworfen" / "v-1_neu.json").exists()


def test_erreichte_bestaetigung_wird_durch_spaete_abholung_nicht_zurueckgesetzt(umgebung):
    _neu_einlegen(umgebung, "v-1")
    av.quittieren("v-1", "neu", umgebung.repo)

    assert len(postfach.abholen("hermes", "neu-sitzung", umgebung.repo)) == 1
    assert av.finden("v-1").phase == "bestaetigt"


def test_nicht_lesbare_marke_laesst_die_datei_liegen(umgebung, monkeypatch):
    _neu_einlegen(umgebung, "v-1")
    _abgabe_einlegen(umgebung, "v-2")

    def unlesbar(datei):
        raise modi.ModusFehler("Besitzstatus nicht lesbar")

    monkeypatch.setattr(modi, "_besitz_text_lesen", unlesbar)
    assert postfach.abholen("hermes", "neu-sitzung", umgebung.repo) == []
    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []
    assert _dateien(umgebung) == ["v-1_neu.json"]
    assert _dateien(umgebung, "claude", "alt-sitzung") == ["v-2_abgabe_auftrag.json"]


def test_nach_der_abholung_wird_nicht_erneut_eingelegt(umgebung):
    _neu_einlegen(umgebung, "v-1")
    postfach.abholen("hermes", "neu-sitzung", umgebung.repo)

    postfach.einlegen("hermes", "neu-sitzung", "v-1", THEMA, "neu", LAUFEND)

    assert _dateien(umgebung) == []


def test_abholung_bei_belegter_themensperre_laesst_alles_liegen(umgebung, monkeypatch):
    _neu_einlegen(umgebung, "v-1")
    monkeypatch.setattr(av, "THEMENSPERRE_FRIST", 0.05)

    with zustand.thema_sperre(THEMA, blockierend=True, frist=1.0) as frei:
        assert frei
        assert postfach.abholen("hermes", "neu-sitzung", umgebung.repo) == []

    assert _dateien(umgebung) == ["v-1_neu.json"]
    assert av.finden("v-1").phase == "im_postfach"
    assert len(postfach.abholen("hermes", "neu-sitzung", umgebung.repo)) == 1   # danach klappt es


# --- Abholen: Abgabe-Auftrag --------------------------------------------------------

def test_abgabe_auftrag_wird_dem_alten_master_zugestellt_ohne_die_phase_zu_aendern(umgebung):
    _abgabe_einlegen(umgebung, "v-1")

    erg = postfach.abholen("claude", "alt-sitzung", umgebung.repo)

    assert len(erg) == 1 and erg[0].rolle == "abgabe_auftrag" and erg[0].vorgang == "v-1"
    assert erg[0].text == (f"Du gibst das Thema {THEMA} ab. Schließe den laufenden Schritt sauber ab, "
                           f"aktualisiere {LAUFEND} (Kopfzeile `Übergabebereit: ja`), beginne keinen neuen "
                           "Schritt und führe `masterwechsel quittieren v-1 abgabe` aus.")
    vorgang = av.finden("v-1")
    assert vorgang.phase == "abgabe_sende"                                    # Abholung ändert die Phase nie
    assert vorgang.abgabe_zugestellt is not None
    assert _dateien(umgebung, "claude", "alt-sitzung") == []
    assert (postfach.ordner("claude", "alt-sitzung") / "erledigt" / "v-1_abgabe_auftrag.json").exists()


@pytest.mark.parametrize("phase", ["abgabe_sende", "abgabe_angefragt", "abgabe_unklar"])
def test_abgabe_auftrag_wird_in_jeder_offenen_abgabephase_zugestellt(umgebung, phase):
    _abgabe_einlegen(umgebung, "v-1", phase=phase)

    assert [n.vorgang for n in postfach.abholen("claude", "alt-sitzung", umgebung.repo)] == ["v-1"]
    assert av.finden("v-1").phase == phase


def test_abholung_zwischen_dateischreiben_und_phasenwechsel_laesst_den_auftrag_liegen(umgebung):
    _abgabe_einlegen(umgebung, "v-1", phase="vorbereitet")                    # Datei liegt, Phase noch nicht

    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []

    assert _dateien(umgebung, "claude", "alt-sitzung") == ["v-1_abgabe_auftrag.json"]
    assert not (postfach.ordner("claude", "alt-sitzung") / "verworfen").exists()
    assert av.finden("v-1").abgabe_zugestellt is None

    av.abgabe_beginnen("v-1")                                                  # Phasenwechsel folgt
    erg = postfach.abholen("claude", "alt-sitzung", umgebung.repo)
    assert [n.vorgang for n in erg] == ["v-1"]
    assert av.finden("v-1").phase == "abgabe_sende" and av.finden("v-1").abgabe_zugestellt is not None


def test_abgabe_auftrag_bei_unbekanntem_vorgang_bleibt_liegen(umgebung):
    postfach.einlegen("claude", "alt-sitzung", "v-ohne-eintrag", THEMA, "abgabe_auftrag", LAUFEND)

    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []

    assert _dateien(umgebung, "claude", "alt-sitzung") == ["v-ohne-eintrag_abgabe_auftrag.json"]
    assert not (postfach.ordner("claude", "alt-sitzung") / "verworfen").exists()


@pytest.mark.parametrize("phase", ["abgabe_uebersprungen", "abgegeben", "abgabe_fehler", "rolle_gesetzt",
                                   "im_chat", "bestaetigt", "verworfen"])
def test_abgabe_auftrag_ausserhalb_der_offenen_abgabe_wird_verworfen(umgebung, phase):
    _abgabe_einlegen(umgebung, "v-1")
    av.aktualisieren("v-1", phase=phase)

    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []

    assert _grund("claude", "alt-sitzung", "v-1_abgabe_auftrag.json") == "Abgabe nicht mehr offen"
    assert av.finden("v-1").phase == phase and av.finden("v-1").abgabe_zugestellt is None


def test_abgabe_auftrag_bei_geaenderter_marke_wird_verworfen(umgebung):
    _abgabe_einlegen(umgebung, "v-1")
    modi.master_setzen(THEMA, "codex", repo=umgebung.repo)                    # Marke weicht vom Vorzustand ab

    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []

    assert _grund("claude", "alt-sitzung", "v-1_abgabe_auftrag.json") == "Marke hat sich geändert"
    assert av.finden("v-1").abgabe_zugestellt is None


# --- Abholen: Abgabe-Info -----------------------------------------------------------

def test_abgabe_info_wird_zugestellt_ohne_die_phase_zu_aendern(umgebung):
    _abgabe_einlegen(umgebung, "v-1")
    av.abgabe_ueberspringen("v-1", "Frist abgelaufen")
    postfach.info_statt_auftrag("claude", "alt-sitzung", "v-1", THEMA, LAUFEND)
    umgebung.uebergeben("v-1", "hermes")                                       # Rolle gewechselt (G8a)

    erg = postfach.abholen("claude", "alt-sitzung", umgebung.repo)

    assert [(n.vorgang, n.rolle) for n in erg] == [("v-1", "abgabe_info")]
    assert erg[0].text == (f"Du führst das Thema {THEMA} nicht mehr (Vorgang v-1). Beginne dort keinen "
                           "neuen Schritt; die Übergabe übernimmt der neue Master. "
                           f"Maßgeblich ist die Besitzmarke; prüfe im Zweifel `masterwechsel profil {THEMA}`.")
    vorgang = av.finden("v-1")
    assert vorgang.phase == "abgabe_uebersprungen" and vorgang.abgabe_zugestellt is not None


def test_info_statt_auftrag_verwirft_den_liegenden_auftrag_mit_grund(umgebung):
    _abgabe_einlegen(umgebung, "v-1")
    av.abgabe_ueberspringen("v-1", "Frist abgelaufen")

    info = postfach.info_statt_auftrag("claude", "alt-sitzung", "v-1", THEMA, LAUFEND)

    assert info == postfach.ordner("claude", "alt-sitzung") / "v-1_abgabe_info.json"
    assert _dateien(umgebung, "claude", "alt-sitzung") == ["v-1_abgabe_info.json"]
    assert _grund("claude", "alt-sitzung", "v-1_abgabe_auftrag.json") == "durch Abgabe-Info ersetzt"
    postfach.abholen("claude", "alt-sitzung", umgebung.repo)
    assert av.finden("v-1").phase == "abgabe_uebersprungen"                    # Auftrag wurde nie zugestellt


def test_info_wird_auch_nach_bereits_abgeholtem_auftrag_zugestellt(umgebung):
    _abgabe_einlegen(umgebung, "v-1")
    assert len(postfach.abholen("claude", "alt-sitzung", umgebung.repo)) == 1  # Auftrag war schon weg
    av.abgabe_ueberspringen("v-1", "Frist abgelaufen")

    postfach.info_statt_auftrag("claude", "alt-sitzung", "v-1", THEMA, LAUFEND)
    umgebung.uebergeben("v-1", "hermes")                                       # Rolle gewechselt (G8a)
    erg = postfach.abholen("claude", "alt-sitzung", umgebung.repo)

    assert [(n.vorgang, n.rolle) for n in erg] == [("v-1", "abgabe_info")]
    assert (postfach.ordner("claude", "alt-sitzung") / "erledigt" / "v-1_abgabe_auftrag.json").exists()
    assert not (postfach.ordner("claude", "alt-sitzung") / "verworfen").exists()


def test_info_statt_auftrag_ist_wiederholbar_und_legt_nichts_doppelt_ein(umgebung):
    _abgabe_einlegen(umgebung, "v-1")
    postfach.info_statt_auftrag("claude", "alt-sitzung", "v-1", THEMA, LAUFEND)
    postfach.info_statt_auftrag("claude", "alt-sitzung", "v-1", THEMA, LAUFEND)
    assert _dateien(umgebung, "claude", "alt-sitzung") == ["v-1_abgabe_info.json"]


def test_auftrag_nach_abgabe_uebersprungen_wird_beim_abholen_verworfen_auch_ohne_info_statt_auftrag(umgebung):
    _abgabe_einlegen(umgebung, "v-1")
    av.abgabe_ueberspringen("v-1", "Frist abgelaufen")                         # Absturz vor info_statt_auftrag

    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []
    assert _grund("claude", "alt-sitzung", "v-1_abgabe_auftrag.json") == "Abgabe nicht mehr offen"


def test_info_bei_unbekanntem_vorgang_bleibt_liegen_bei_verworfenem_wird_sie_verworfen(umgebung):
    postfach.einlegen("claude", "alt-sitzung", "v-9", THEMA, "abgabe_info", LAUFEND)
    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []
    assert _dateien(umgebung, "claude", "alt-sitzung") == ["v-9_abgabe_info.json"]

    umgebung.vorbereiten("v-9", phase="verworfen")
    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []
    assert _grund("claude", "alt-sitzung", "v-9_abgabe_info.json") == "Vorgang wurde verworfen"


def test_info_wird_verworfen_wenn_die_marke_wieder_dem_alten_master_gehoert(umgebung):
    _neu_einlegen(umgebung, "v-1", ziel="hermes", von="claude")                # Claude gibt ab, Hermes führt
    av.aktualisieren("v-1", abgabe="uebersprungen")
    postfach.einlegen("claude", "alt-sitzung", "v-1", THEMA, "abgabe_info", LAUFEND)
    _neu_einlegen(umgebung, "v-2", ziel="claude", von="hermes")                # späterer Wechsel zurück an Claude

    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []
    assert "alten Master" in _grund("claude", "alt-sitzung", "v-1_abgabe_info.json")


def test_info_bleibt_gueltig_solange_die_marke_nicht_zurueck_beim_alten_master_ist(umgebung):
    _neu_einlegen(umgebung, "v-1", ziel="hermes", von="claude")                # Marke gehört Hermes
    postfach.einlegen("claude", "alt-sitzung", "v-1", THEMA, "abgabe_info", LAUFEND)

    assert [n.rolle for n in postfach.abholen("claude", "alt-sitzung", umgebung.repo)] == ["abgabe_info"]


def test_info_bleibt_liegen_solange_die_marke_noch_dem_vorzustand_entspricht(umgebung):
    umgebung.marke_setzen("claude 2026-10-20T10:00:00+00:00")
    umgebung.vorbereiten("v-1", ziel="hermes", von="claude")
    av.aktualisieren("v-1", phase="abgabe_uebersprungen", abgabe="uebersprungen")
    postfach.einlegen("claude", "alt-sitzung", "v-1", THEMA, "abgabe_info", LAUFEND)

    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []       # der alte Master führt noch
    assert _dateien(umgebung, "claude", "alt-sitzung") == ["v-1_abgabe_info.json"]

    umgebung.uebergeben("v-1", "hermes")                                       # jetzt ist die Rolle gewechselt
    assert [n.rolle for n in postfach.abholen("claude", "alt-sitzung", umgebung.repo)] == ["abgabe_info"]


def test_info_bei_gleicher_rolle_wird_nach_dem_wechsel_zugestellt(umgebung):
    _neu_einlegen(umgebung, "v-1", ziel="claude", von="claude")                # Claude-Chat → anderer Claude-Chat
    postfach.einlegen("claude", "alt-sitzung", "v-1", THEMA, "abgabe_info", LAUFEND)

    assert [n.rolle for n in postfach.abholen("claude", "alt-sitzung", umgebung.repo)] == ["abgabe_info"]


@pytest.mark.parametrize("art", ["abgabe_auftrag", "abgabe_info"])
def test_abgabe_an_eine_andere_rolle_als_den_alten_master_wird_verworfen(umgebung, art):
    _abgabe_einlegen(umgebung, "v-1", ziel="codex", von="claude")
    postfach.einlegen("hermes", "alt-sitzung", "v-1", THEMA, art, LAUFEND)    # falsches Postfach

    assert postfach.abholen("hermes", "alt-sitzung", umgebung.repo) == []
    assert "nicht der alte Master" in _grund("hermes", "alt-sitzung", f"v-1_{art}.json")
    assert av.finden("v-1").abgabe_zugestellt is None


def test_zweiter_abholer_gibt_eine_schon_zugestellte_nachricht_nicht_erneut_zurueck(umgebung, monkeypatch):
    _abgabe_einlegen(umgebung, "v-1", ziel="hermes", von="claude")
    ordner = postfach.ordner("claude", "alt-sitzung")
    original = zustand.thema_sperre

    @contextlib.contextmanager
    def erster_war_schneller(*args, **kwargs):
        with original(*args, **kwargs) as frei:
            # Der erste Abholer hat die Datei gelesen, zugestellt und verschoben, bevor dieser die Sperre bekam.
            (ordner / "erledigt").mkdir(exist_ok=True)
            (ordner / "v-1_abgabe_auftrag.json").replace(ordner / "erledigt" / "v-1_abgabe_auftrag.json")
            yield frei

    monkeypatch.setattr(zustand, "thema_sperre", erster_war_schneller)

    assert postfach.abholen("claude", "alt-sitzung", umgebung.repo) == []
    assert av.finden("v-1").abgabe_zugestellt is None                          # kein zweiter Vermerk


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
    ordner = _roh_einlegen(umgebung, "v-1_neu.json", _gut(zeit="x" * 5000))
    assert (ordner / "v-1_neu.json").stat().st_size > postfach.MAX_BYTES

    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []

    assert not (ordner / "v-1_neu.json").exists()
    assert "größer" in json.loads((ordner / "verworfen" / "v-1_neu.json").read_text("utf-8"))["grund"]


@pytest.mark.parametrize("inhalt", [
    "{kein json", "[]", '"text"', _gut(extra="x"), {k: v for k, v in _gut().items() if k != "zeit"},
    _gut(vorgang="v-2"), _gut(thema="../x"), _gut(rolle="beide"), _gut(rolle="abgabe"),
    _gut(rolle="abgabe_info"), _gut(laufend="/etc/passwd"), _gut(zeit=5),
])
def test_ungueltiger_inhalt_wird_verworfen(umgebung, inhalt):
    ordner = _roh_einlegen(umgebung, "v-1_neu.json", inhalt)

    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []

    assert not (ordner / "v-1_neu.json").exists()
    assert (ordner / "verworfen" / "v-1_neu.json").exists()


def test_dateien_mit_fremdem_namen_werden_nicht_angefasst(umgebung):
    ordner = _roh_einlegen(umgebung, "notizen.txt", "hallo")
    _roh_einlegen(umgebung, "..x.json", _gut())
    _roh_einlegen(umgebung, "v-1.json", _gut())                                # alter Namensstil ohne Art
    _roh_einlegen(umgebung, "v-1_abgabe.json", _gut())                         # Art nicht vorgesehen
    _roh_einlegen(umgebung, "_neu.json", _gut())                               # leere Vorgangs-ID
    (ordner / "ordner_neu.json").mkdir()
    assert postfach.abholen("claude", SITZUNG, umgebung.repo) == []
    assert sorted(p.name for p in ordner.iterdir()) == [
        "..x.json", "_neu.json", "notizen.txt", "ordner_neu.json", "v-1.json", "v-1_abgabe.json"]
