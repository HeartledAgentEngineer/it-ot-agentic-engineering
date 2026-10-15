"""Tests für die Paare (`paare.json`): Prüfung von Thema, Kennung und laufendem Pfad."""
import pytest

from master_schalter import besitz, paare

THREAD_A = "01a12557-3bb3-7171-a021-53e6ac879534"
THREAD_B = "01a0a68e-5041-7610-a528-38d42f66bed3"


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    return tmp_path / "daten"


# --- Thema -------------------------------------------------------------------

def test_thema_gueltig():
    assert paare.thema_pruefen("engineering") == "engineering"
    assert paare.thema_pruefen("a") == "a"
    assert paare.thema_pruefen("a" + "b" * 79) == "a" + "b" * 79


@pytest.mark.parametrize("thema", ["", "Engineering", "-abc", "a b", "ä", "a/b", "a\\b",
                                   "a" * 81, "thema\n", "thema\nmehr", ".hermes"])
def test_thema_abgelehnt(thema):
    with pytest.raises(paare.PaarFehler):
        paare.thema_pruefen(thema)


def test_abschliessendes_zeilenende_wird_abgelehnt():
    """`re.fullmatch` – ein `match()`-Muster ließe ein abschließendes LF durch."""
    with pytest.raises(paare.PaarFehler):
        paare.thema_pruefen("engineering\n")


# --- Kennung -----------------------------------------------------------------

def test_kennung_wird_kanonisch_gespeichert():
    assert paare.thread_pruefen(THREAD_A.upper()) == THREAD_A


@pytest.mark.parametrize("wert", ["", "keine-uuid", "01a12557-3bb3-7171-a021", 42, None])
def test_ungueltige_kennung_abgelehnt(wert):
    with pytest.raises(paare.PaarFehler):
        paare.thread_pruefen(wert)


# --- Laufender Pfad ----------------------------------------------------------

def test_laufend_wird_aus_dem_thema_gebildet():
    assert paare.laufend_bilden("engineering") == ".hermes/uebergabe/laufend/engineering.md"


@pytest.mark.parametrize("pfad", [
    ".hermes/uebergabe/laufend/anderes.md",
    "laufend/engineering.md",
    ".hermes/uebergabe/laufend/engineering.txt",
    "../.hermes/uebergabe/laufend/engineering.md",
    ".hermes/uebergabe/engineering.md",
    "",
])
def test_pfad_ausserhalb_der_konvention_wird_abgelehnt(pfad):
    with pytest.raises(paare.PaarFehler):
        paare.laufend_pruefen("engineering", pfad)


def test_windows_schreibweise_wird_angenommen():
    assert paare.laufend_pruefen("engineering", ".hermes\\uebergabe\\laufend\\engineering.md") == \
        ".hermes/uebergabe/laufend/engineering.md"


# --- Datei -------------------------------------------------------------------

def test_setzen_prueft_pfad_gegen_das_thema(daten):
    with pytest.raises(paare.PaarFehler):
        paare.setzen("engineering", THREAD_A, ".hermes/uebergabe/laufend/anderes.md")
    assert paare.lesen() == []


def test_setzen_und_lesen_roundtrip(daten):
    paare.setzen("engineering", THREAD_A, paare.laufend_bilden("engineering"), aktiv=True)
    gelesen = paare.lesen()
    assert gelesen == [paare.Paar("engineering", THREAD_A,
                                  ".hermes/uebergabe/laufend/engineering.md", True)]


def test_doppelte_kennung_fuer_ein_zweites_thema_abgelehnt(daten):
    paare.setzen("engineering", THREAD_A, paare.laufend_bilden("engineering"))
    with pytest.raises(paare.PaarFehler):
        paare.setzen("weiterbildung", THREAD_A, paare.laufend_bilden("weiterbildung"))


def test_neustart_behaelt_auswahl(daten):
    paare.setzen("engineering", THREAD_A, paare.laufend_bilden("engineering"), aktiv=True)
    paare.setzen("weiterbildung", THREAD_B, paare.laufend_bilden("weiterbildung"), aktiv=False)
    neu = paare.lesen()   # frisch von der Platte
    assert [p.thema for p in neu] == ["engineering", "weiterbildung"]
    assert [p.aktiv for p in neu] == [True, False]


def test_erneutes_setzen_behaelt_aktiv(daten):
    paare.setzen("engineering", THREAD_A, paare.laufend_bilden("engineering"), aktiv=True)
    paare.setzen("engineering", THREAD_B, paare.laufend_bilden("engineering"))
    assert paare.lesen() == [paare.Paar("engineering", THREAD_B,
                                        ".hermes/uebergabe/laufend/engineering.md", True)]


def test_kaputte_datei_ergibt_leere_liste(daten):
    daten.mkdir(parents=True)
    (daten / "paare.json").write_text('{"kein": "Array"}', encoding="utf-8")
    assert paare.lesen() == []
    (daten / "paare.json").write_text("kein json", encoding="utf-8")
    assert paare.lesen() == []


def test_unbrauchbare_eintraege_werden_uebersprungen(daten):
    daten.mkdir(parents=True)
    (daten / "paare.json").write_text(
        '[{"thema": "Grob", "codex_thread": "%s", "laufend": "laufend/Grob.md"},'
        ' {"thema": "engineering", "codex_thread": "%s",'
        '  "laufend": ".hermes/uebergabe/laufend/engineering.md", "aktiv": true}]' % (THREAD_A, THREAD_B),
        encoding="utf-8")
    assert [p.thema for p in paare.lesen()] == ["engineering"]


# --- Aktiv -------------------------------------------------------------------

def test_aktiv_setzen_und_aktive(daten):
    paare.setzen("engineering", THREAD_A, paare.laufend_bilden("engineering"))
    paar = paare.aktiv_setzen("engineering", True)
    assert paar.aktiv is True
    assert [p.thema for p in paare.aktive()] == ["engineering"]
    paare.aktiv_setzen("engineering", False)
    assert paare.aktive() == []


def test_aktiv_setzen_unbekanntes_thema(daten):
    with pytest.raises(paare.PaarFehler):
        paare.aktiv_setzen("gibtsnicht", True)


def test_master_datei_liegt_neben_der_laufenden_uebergabe():
    paar = paare.Paar("engineering", THREAD_A, ".hermes/uebergabe/laufend/engineering.md", True)
    assert paar.master_datei == ".hermes/uebergabe/laufend/engineering.master"


def test_besitz_pfad_ist_idempotent(tmp_path):
    """Ein Pfad, der schon auf `.master` endet, darf nicht zu `.master.master` werden."""
    erwartet = tmp_path / ".hermes" / "uebergabe" / "laufend" / "engineering.master"

    assert besitz.pfad(tmp_path, ".hermes/uebergabe/laufend/engineering.md") == erwartet
    assert besitz.pfad(tmp_path, ".hermes/uebergabe/laufend/engineering.master") == erwartet
    assert besitz.pfad(tmp_path, ".hermes/uebergabe/laufend/engineering.master.master") != erwartet
