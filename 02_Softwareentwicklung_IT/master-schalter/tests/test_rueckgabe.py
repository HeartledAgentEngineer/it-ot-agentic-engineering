"""Tests für die Rückgabe an Codex (v0.3.2): fail-closed, Sperren, Besitz, Phasen, Trockenlauf."""
import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import automatik, besitz, codex_senden, paare, rueckgabe, vorgaenge, zustand

THREAD = "01a12557-3bb3-7171-a021-53e6ac879534"
THREAD2 = "01a0a68e-5041-7610-a528-38d42f66bed3"
JETZT = datetime(2026, 10, 16, 4, 0, tzinfo=timezone.utc)
FULL_HEAD = "abcdef1234567890abcdef1234567890abcdef12"
KURZ = "abcdef1"
LAUFEND = ".hermes/uebergabe/laufend/engineering.md"


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_SESSIONS", str(tmp_path / "codex"))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX", "C:/werkzeuge/codex.exe")
    return repo


def _git(repo, args):
    if args[:2] == ["rev-parse", "--short"]:
        return KURZ + "\n"
    if args[:2] == ["rev-parse", "HEAD"]:
        return FULL_HEAD + "\n"
    if args[:2] == ["rev-list", "--count"]:
        return "42\n"
    if args[0] == "status":
        return ""
    raise AssertionError(args)


@pytest.fixture
def transport(monkeypatch):
    """Attrappe statt `codex.exe`; sammelt die Aufrufe."""
    aufrufe = []

    def setzen(verhalten):
        def t(liste, timeout):
            aufrufe.append(liste)
            if isinstance(verhalten, Exception):
                raise verhalten
            return verhalten

        monkeypatch.setattr(codex_senden, "_transport", t)
        return aufrufe

    return setzen


def _master_setzen(wert="codex"):
    zustand.aendern(lambda z: replace(z, master=wert))


def _laufend(repo, thema="engineering", bereit="ja", zeit=None, kurz=KURZ):
    datei = repo / ".hermes" / "uebergabe" / "laufend" / f"{thema}.md"
    datei.parent.mkdir(parents=True, exist_ok=True)
    zeile = f"Übergabebereit: {bereit} · {(zeit or JETZT - timedelta(minutes=5)).isoformat()} · {kurz}"
    datei.write_text(zeile + "\n# Technischer Inhalt\n", encoding="utf-8")
    return datei


def _paar(thema="engineering", relax=None):
    paare.setzen(thema, THREAD, f".hermes/uebergabe/laufend/{thema}.md", aktiv=True)
    return paare


def _lauf(repo, **kw):
    return rueckgabe.rueckgabe(jetzt=JETZT, repo=repo, git=_git, **kw)


def _master(repo, thema="engineering"):
    return besitz.lesen(besitz.pfad(repo, f".hermes/uebergabe/laufend/{thema}.md"))


def _bestanden():
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "engineering@1", "engineering", "l1", "bestaetigt",
        (JETZT - timedelta(minutes=5)).isoformat())])


# --- Kennungen -----------------------------------------------------------------

def test_kennung_hat_festen_aufbau_und_ist_praefixfrei(umgebung):
    a = rueckgabe.neue_id("engineering", JETZT)
    b = rueckgabe.neue_id("engineering", JETZT)
    assert re.fullmatch(r"rueckgabe-engineering-\d{14}-[0-9a-f]{4}", a)
    assert a != b                                   # Zufallsfeld je Versuch
    assert not a.startswith(b) and not b.startswith(a)   # gleich lang ⇒ präfixfrei


# --- Kopfzeilen-Regeln (fail-closed, schreibfrei) -------------------------------

def test_fehlende_kopfzeile_sperrt_schreibfrei(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    (umgebung / ".hermes/uebergabe/laufend").mkdir(parents=True, exist_ok=True)
    staende = _lauf(umgebung)
    assert "fehlt" in staende[0].status
    assert aufrufe == [] and vorgaenge.lesen() == [] and _master(umgebung) == ""


def test_nein_beim_zweiten_blick_wird_nie_ueberstimmt(umgebung, transport):
    """Zwischen erstem Lesen und Ziehen auf `nein` gestellt → Fail-closed, kein Senden."""
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    datei = _laufend(umgebung)
    import master_schalter.automatik as am
    from unittest import mock
    with mock.patch.object(am, "uebergabepunkt",
                           return_value=(False, am.STATUS_UEBERGABEPUNKT)):
        staende = _lauf(umgebung)
    assert "nein" in staende[0].status
    assert aufrufe == [] and vorgaenge.lesen() == [] and _master(umgebung) == ""
    assert "Übergabebereit: ja" in datei.read_text(encoding="utf-8")   # Datei unberührt


def test_kopfzeile_ziehen_verweigert_nein_und_kaputte_zeilen(umgebung):
    from master_schalter import rueckgabe as rk
    datei = _laufend(umgebung, bereit="nein")
    vorher = datei.read_text(encoding="utf-8")
    assert rk.kopfzeile_ziehen(datei, "abcdef1", JETZT) is False
    assert datei.read_text(encoding="utf-8") == vorher
    kaputt = umgebung / ".hermes/uebergabe/laufend/kaputt.md"
    kaputt.write_text("keine Kopfzeile\n", encoding="utf-8")
    assert rk.kopfzeile_ziehen(kaputt, "abcdef1", JETZT) is False


def test_nein_sperrt_ohne_jeden_schreibzugriff(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    datei = _laufend(umgebung, bereit="nein")
    vorher = datei.read_text(encoding="utf-8")
    staende = _lauf(umgebung)
    assert "nein" in staende[0].status and aufrufe == []
    assert datei.read_text(encoding="utf-8") == vorher


def test_master_nicht_codex_ueberspringt(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen("hermes")
    _paar()
    _laufend(umgebung)
    staende = _lauf(umgebung)
    assert "nicht Codex" in staende[0].status and aufrufe == []


# --- Erfolgsweg ----------------------------------------------------------------

def test_gesendet_mit_besitzmarke_und_ack_zeile(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    datei = _laufend(umgebung)
    staende = _lauf(umgebung)
    assert staende[0].phase == "gesendet" and len(aufrufe) == 1
    liste = aufrufe[0]
    assert liste[0] == "C:/werkzeuge/codex.exe" and liste[1] == "queue"
    assert THREAD in liste and "ACK rueckgabe-engineering-" in liste[-1]
    assert "Desktop" not in liste[-1]                 # kein privater Pfad in der Nachricht
    v = vorgaenge.lesen()[0]
    assert v.phase == "gesendet" and v.id == v.lauf_id and v.id in liste[-1]
    assert _master(umgebung).startswith(f"codex {v.id} ")
    kopf = automatik.kopfzeile_lesen(datei)
    assert kopf[0] == "ja" and kopf[2] == KURZ[:7]
    assert kopf[1].astimezone(timezone.utc) == JETZT


def test_veraltete_kopfzeile_wird_gezogen_und_in_der_nachricht_genannt(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    datei = _laufend(umgebung, zeit=JETZT - timedelta(hours=11))
    staende = _lauf(umgebung)
    assert staende[0].phase == "gesendet"
    assert "Kopfzeile gezogen" in staende[0].status
    assert "gezogen" in aufrufe[0][-1]
    assert automatik.kopfzeile_lesen(datei)[1].astimezone(timezone.utc) == JETZT


def test_fremder_head_wird_beim_ziehen_beruecksichtigt(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    fremd = "9999999999" + FULL_HEAD[10:]

    def git_fremd(repo, args):
        if args[:2] == ["rev-parse", "HEAD"]:
            return fremd + "\n"
        return _git(repo, args)

    staende = rueckgabe.rueckgabe(jetzt=JETZT, repo=umgebung, git=git_fremd)
    assert staende[0].phase == "gesendet" and len(aufrufe) == 1
    assert automatik.kopfzeile_lesen(
        umgebung / LAUFEND)[2] == fremd[:7]


# --- bereits übergeben / erneut ------------------------------------------------

def test_juengster_vorgang_zaehlt_nach_zeit_nicht_nach_kennung(umgebung, transport):
    """Ein alter bestätigter Vorgang darf einen neueren Fehlversuch nicht blockieren."""
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    alt = (JETZT - timedelta(days=2)).isoformat()
    neu = (JETZT - timedelta(minutes=1)).isoformat()
    vorgaenge.aendern(lambda a: [*a,
                                 vorgaenge.Vorgang("zzz@alt", "engineering", "l", "bestaetigt", alt),
                                 vorgaenge.Vorgang("rueckgabe-engineering-20261016040000-aaaa",
                                                   "engineering", "l2", "fehler", neu)])
    staende = _lauf(umgebung)
    assert staende[0].phase == "gesendet" and len(aufrufe) == 1


def test_bereits_uebergeben_ohne_erneut_sendet_nicht(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    _bestanden()
    staende = _lauf(umgebung)
    assert "bereits übergeben" in staende[0].status and aufrufe == []


def test_erneut_sendet_mit_frischer_kennung_und_ersetzt_die_marke(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    besitz.schreiben(besitz.pfad(umgebung, LAUFEND),
                     f"codex alt@1 {(JETZT - timedelta(minutes=5)).isoformat()}")
    _bestanden()
    staende = _lauf(umgebung, erneut=True)
    assert staende[0].phase == "gesendet" and len(aufrufe) == 1
    neu = vorgaenge.lesen()[-1]
    assert neu.id.startswith("rueckgabe-engineering-") and neu.phase == "gesendet"
    assert _master(umgebung).startswith(f"codex {neu.id} ")


def test_codex_besitz_ohne_erneut_haelt_an(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    besitz.schreiben(besitz.pfad(umgebung, LAUFEND),
                     f"codex alt@1 {(JETZT - timedelta(minutes=5)).isoformat()}")
    staende = _lauf(umgebung)
    assert "schon übernommen" in staende[0].status and aufrufe == []


# --- Fehlerpfade ---------------------------------------------------------------

def test_transport_nicht_gestartet_stellt_vorzustand_wieder_her(umgebung, transport):
    aufrufe = transport(FileNotFoundError("kein codex.exe"))
    _master_setzen()
    _paar()
    _laufend(umgebung)
    vorher = f"claude {(JETZT - timedelta(minutes=5)).isoformat()} fehlgeschlagen x"
    besitz.schreiben(besitz.pfad(umgebung, LAUFEND), vorher)
    staende = _lauf(umgebung)
    assert staende[0].phase == "fehler"
    assert vorgaenge.lesen()[-1].phase == "fehler"
    assert _master(umgebung) == vorher                      # wörtlich wiederhergestellt
    assert "wiederhergestellt" in staende[0].status
    assert len(aufrufe) == 1


def test_fehlstart_stellt_den_codex_vorzustand_woertlich_her(umgebung, transport):
    """Wörtlich: die vollständige alte Zeile kommt unverändert zurück (kein neuer Zeitstempel)."""
    aufrufe = transport(FileNotFoundError("kein codex.exe"))
    _master_setzen()
    _paar()
    _laufend(umgebung)
    alt = f"codex alt@1 {(JETZT - timedelta(minutes=5)).isoformat()}"
    besitz.schreiben(besitz.pfad(umgebung, LAUFEND), alt)
    staende = _lauf(umgebung, erneut=True)
    assert staende[0].phase == "fehler"
    assert _master(umgebung) == alt
    assert len(aufrufe) == 1


def test_rueckgabewert_ungleich_null_bleibt_unklar(umgebung, transport):
    aufrufe = transport(3)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    staende = _lauf(umgebung)
    assert staende[0].phase == "unklar"
    assert _master(umgebung).startswith("codex ")           # Marke bleibt stehen (konservativ)
    assert vorgaenge.lesen()[-1].phase == "unklar"
    assert len(aufrufe) == 1


def test_aktive_fremde_reservierung_wird_nie_uebernommen(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    besitz.schreiben(besitz.pfad(umgebung, LAUFEND), f"reserviert fremd-lauf {JETZT.isoformat()}")
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "x@1", "engineering", "fremd-lauf", "gesendet", JETZT.isoformat())])
    staende = _lauf(umgebung)
    assert "Reservierung offen" in staende[0].status and aufrufe == []
    assert "fremd-lauf" in _master(umgebung)


def test_verwaiste_eigene_reservierung_ohne_erneut_laesst_den_stand_unberuehrt(umgebung, transport):
    """Skip-Pfad ist schreibfrei: die verwaiste Reservierung bleibt stehen, bis gesendet wird."""
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    alt = f"codex alt@1 {(JETZT - timedelta(minutes=5)).isoformat()}"
    besitz.schreiben(besitz.pfad(umgebung, LAUFEND),
                     f"reserviert alt-lauf {JETZT.isoformat()} vorzustand {alt}")
    staende = _lauf(umgebung)
    assert "schon übernommen" in staende[0].status
    assert "reserviert alt-lauf" in _master(umgebung)       # nichts angefasst
    assert aufrufe == []


def test_verwaiste_reservierung_wird_beim_senden_aufgeloest(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    alt = f"codex alt@1 {(JETZT - timedelta(minutes=5)).isoformat()}"
    besitz.schreiben(besitz.pfad(umgebung, LAUFEND),
                     f"reserviert alt-lauf {JETZT.isoformat()} vorzustand {alt}")
    staende = _lauf(umgebung, erneut=True)
    assert staende[0].phase == "gesendet" and len(aufrufe) == 1
    assert _master(umgebung).startswith("codex rueckgabe-engineering-")


def test_trockenlauf_loest_keine_waise_auf(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    besitz.schreiben(besitz.pfad(umgebung, LAUFEND),
                     f"reserviert alt-lauf {JETZT.isoformat()} vorzustand claude")
    staende = _lauf(umgebung, trocken=True)
    assert "würde senden" in staende[0].status and "würde aufgelöst" in staende[0].status
    assert "reserviert alt-lauf" in _master(umgebung)       # schreibfrei
    assert aufrufe == []


# --- Trockenlauf und Themenwahl --------------------------------------------------

def test_hinweis_wird_gekappt_und_einzeilig(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    _laufend(umgebung)
    _lauf(umgebung, hinweis="Zeile1\nZeile2 " + "x" * 400)
    nachricht = aufrufe[0][-1]
    assert "Zeile1 Zeile2" in nachricht and "\n" + "x" * 400 not in nachricht


def test_trockenlauf_schreibt_und_sendet_nichts(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar()
    datei = _laufend(umgebung)
    vorher = datei.read_text(encoding="utf-8")
    staende = _lauf(umgebung, trocken=True)
    assert staende[0].status.startswith("Trockenlauf")
    assert aufrufe == [] and vorgaenge.lesen() == [] and _master(umgebung) == ""
    assert datei.read_text(encoding="utf-8") == vorher


def test_nur_das_genannte_thema_wird_gesendet(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    _paar("engineering")
    paare.setzen("weiterbildung", THREAD2, ".hermes/uebergabe/laufend/weiterbildung.md", aktiv=True)
    _laufend(umgebung, thema="engineering")
    _laufend(umgebung, thema="weiterbildung")
    staende = _lauf(umgebung, themen=["engineering"])
    assert [s.thema for s in staende] == ["engineering"]
    assert len(aufrufe) == 1


def test_inaktives_paar_wird_gemeldet_aber_nicht_gesendet(umgebung, transport):
    aufrufe = transport(0)
    _master_setzen()
    paare.setzen("engineering", THREAD, LAUFEND, aktiv=False)
    _laufend(umgebung)
    staende = _lauf(umgebung)
    assert "aus" in staende[0].status and aufrufe == []
