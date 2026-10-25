"""Tests für den Weg „assistent" der Limit-Automatik (P8, K7): Entscheidung und Wege sind getrennt.

Alle Tests laufen mit Attrappen (`uebergeber`, `sender`, Codex-Transport) und `tmp_path`.
"""
from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import (anzeige, assistent, assistent_vorgaenge as av, automatik, besitz, codex_senden, modi,
                             paare, protokoll, signale, vorgaenge, zustand)

THREAD = "01a12557-3bb3-7171-a021-53e6ac879534"
JETZT = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
ENDE = JETZT + timedelta(hours=3)
FULL_HEAD = "abcdef1234567890abcdef1234567890abcdef12"
KURZ = "abcdef1"
SCHWELLE = 90
KENNUNG = f"engineering@{int(ENDE.timestamp())}"


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_SESSIONS", str(tmp_path / "codex"))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX", "C:/werkzeuge/codex.exe")
    paare.setzen("engineering", THREAD, paare.laufend_bilden("engineering"), aktiv=True)
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


def _paar(thema="engineering", aktiv=True):
    return paare.Paar(thema, THREAD, f".hermes/uebergabe/laufend/{thema}.md", aktiv)


def _messung(claude_f=95):
    claude = signale.Kontingent("Claude", (signale.Fenster("5h", claude_f, ENDE),
                                           signale.Fenster("Woche", 50, ENDE)), stand=JETZT)
    codex = signale.Kontingent("Codex", (signale.Fenster("5h", 5, ENDE), signale.Fenster("Woche", 5, ENDE)),
                               stand=JETZT)
    return automatik.Messung(claude, codex)


def _laufend(repo, bereit="ja"):
    datei = repo / ".hermes" / "uebergabe" / "laufend" / "engineering.md"
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(f"Übergabebereit: {bereit} · {(JETZT - timedelta(minutes=5)).isoformat()} · {KURZ}\n# Inhalt\n",
                     encoding="utf-8")
    return datei


def _master(repo):
    return besitz.lesen(besitz.pfad(repo, ".hermes/uebergabe/laufend/engineering.md"))


def _vorgang(vorgang_id="wechsel-1", phase="gesendet"):
    return av.Vorgang(vorgang_id, "engineering", "codex", "claude", phase, JETZT.isoformat(),
                      {"master": "kontingent", "worker": "workflow", "modell": None}, "claude x")


class _Uebergeber:
    """Attrappe für `assistent.uebergeben`: sammelt Aufrufe und prüft Zustand zur Aufrufzeit."""

    def __init__(self, repo, ergebnis=None, fehler=None):
        self.repo = repo
        self.aufrufe = []
        self.ergebnis = ergebnis or _vorgang()
        self.fehler = fehler

    def __call__(self, thema, ziel, **kw):
        with zustand.thema_sperre(thema) as frei:
            sperre_frei = frei
        self.aufrufe.append({"thema": thema, "ziel": ziel, "kw": kw, "sperre_frei": sperre_frei,
                             "ausgeloest": automatik.ausgeloest_lesen(), "marke": _master(self.repo)})
        if self.fehler is not None:
            raise self.fehler
        return self.ergebnis


def _sender_verboten(*a, **k):
    raise AssertionError("der alte Weg darf nicht senden")


def _lauf(umgebung, *, weg, uebergeber=None, sender=None, warte=None, head=FULL_HEAD, messung=None,
          paare_liste=None):
    return automatik.lauf(jetzt=JETZT, repo=umgebung, sender=sender, warte=warte or (lambda s: None), head=head,
                          git=_git, paare_liste=paare_liste or [_paar()], messung=messung or _messung(),
                          schwelle=SCHWELLE, an=True, vorgangsliste=[], lauf_id="lauf-1", weg=weg,
                          uebergeber=uebergeber)


# --- Entscheidung: ausgelöste Kennungen zählen wie bekannte Vorgänge --------------------

def test_faellige_ueberspringt_ausgeloeste_kennungen():
    auftraege = automatik.faellige([_paar()], _messung(), SCHWELLE, True, [], JETZT)
    assert [a.id for a in auftraege] == [KENNUNG]
    assert automatik.faellige([_paar()], _messung(), SCHWELLE, True, [], JETZT, ausgeloest={KENNUNG}) == []
    # ein neues Limitfenster ist ein neues Paar aus Thema und Reset
    neu = automatik.faellige([_paar()], _messung(), SCHWELLE, True, [], JETZT,
                             ausgeloest={f"engineering@{int(ENDE.timestamp()) - 1}"})
    assert len(neu) == 1


def test_ausgeloest_datei_ist_robust_gegen_kaputtes(umgebung):
    assert automatik.ausgeloest_lesen() == frozenset()
    for inhalt in ("kein json", "[]", '{"kennungen": []}', '{"kennungen": {"a": 1, "b": "x"}}'):
        automatik.ausgeloest_datei().write_text(inhalt, encoding="utf-8")
        assert automatik.ausgeloest_lesen() <= {"b"}


def test_ausgeloest_vermerken_ist_dauerhaft_und_ergaenzt(umgebung):
    automatik.ausgeloest_vermerken("a@1", JETZT)
    automatik.ausgeloest_vermerken("b@2", JETZT)
    automatik.ausgeloest_vermerken("a@1", JETZT)
    assert automatik.ausgeloest_lesen() == {"a@1", "b@2"}


# --- (a) der alte Weg bleibt der alte Weg -------------------------------------------------

def test_alt_ruft_weiter_den_sender_und_nie_den_assistenten(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    gesendet = []

    def sender(a, repo, master, reservierung, jetzt, git=None):
        gesendet.append(a.id)
        return codex_senden.Ergebnis("gesendet", None)

    staende = _lauf(umgebung, weg="alt", uebergeber=uebergeber, sender=sender)

    assert gesendet == [KENNUNG] and uebergeber.aufrufe == []
    assert staende[0].status == "gesendet"
    assert automatik.ausgeloest_lesen() == frozenset()     # der alte Weg vermerkt nichts


def test_unbekannter_weg_gilt_als_alt(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    gesendet = []

    def sender(a, repo, master, reservierung, jetzt, git=None):
        gesendet.append(a.id)
        return codex_senden.Ergebnis("gesendet", None)

    _lauf(umgebung, weg="quatsch", uebergeber=uebergeber, sender=sender)
    assert gesendet == [KENNUNG] and uebergeber.aufrufe == []


# --- (b) der Assistent wird einmal, außerhalb der Themensperre gerufen --------------------

def test_assistent_wird_genau_einmal_ausserhalb_der_themensperre_gerufen(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)

    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber, sender=_sender_verboten)

    assert len(uebergeber.aufrufe) == 1
    aufruf = uebergeber.aufrufe[0]
    assert aufruf["thema"] == "engineering" and aufruf["ziel"] == "codex"
    assert aufruf["sperre_frei"] is True                        # die Themensperre war frei
    assert aufruf["kw"]["von_chat"] is None
    assert aufruf["kw"]["nach_chat"] == assistent.ChatRef("codex", THREAD)
    assert aufruf["kw"]["repo"] == umgebung
    assert aufruf["marke"] == f"claude {JETZT.isoformat()}"     # Reservierung ist zurück auf claude
    assert [(s.thema, s.phase) for s in staende] == [("engineering", "gesendet")]
    assert staende[0].status.startswith("Wechselassistent: ")
    assert vorgaenge.lesen() == []                              # nichts im alten Vorgangsspeicher
    eintraege = [e for e in protokoll.lesen(50) if e["entscheidung"] == "automatik_ausgeloest"]
    assert [(e["vorgang"], e["thema"]) for e in eintraege] == [("wechsel-1", "engineering")]
    assert KENNUNG not in str(eintraege) and THREAD not in str(eintraege)


def test_einstellung_steuert_den_weg_wenn_keiner_uebergeben_wird(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    anzeige.automatik_weg_setzen("assistent")
    automatik.lauf(jetzt=JETZT, repo=umgebung, sender=_sender_verboten, warte=lambda s: None, head=FULL_HEAD,
                   git=_git, paare_liste=[_paar()], messung=_messung(), schwelle=SCHWELLE, an=True,
                   vorgangsliste=[], lauf_id="lauf-1", uebergeber=uebergeber)
    assert len(uebergeber.aufrufe) == 1


def test_standard_ohne_einstellung_sendet_ueber_den_alten_weg(umgebung, monkeypatch):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    aufrufe = []
    monkeypatch.setattr(codex_senden, "_transport", lambda liste, timeout: aufrufe.append(liste) or 0)
    staende = automatik.lauf(jetzt=JETZT, repo=umgebung, warte=lambda s: None, head=FULL_HEAD, git=_git,
                             paare_liste=[_paar()], messung=_messung(), schwelle=SCHWELLE, an=True,
                             vorgangsliste=[], lauf_id="lauf-1", uebergeber=uebergeber)
    assert staende[0].status == "gesendet", staende
    assert uebergeber.aufrufe == [] and len(aufrufe) == 1
    assert staende[0].status == "gesendet"


# --- (c) Kennung vor dem Aufruf vermerkt, im selben Fenster nur ein Versuch -----------------

def test_kennung_steht_vor_dem_aufruf_und_zweiter_lauf_ruft_nichts(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)

    _lauf(umgebung, weg="assistent", uebergeber=uebergeber, sender=_sender_verboten)
    assert uebergeber.aufrufe[0]["ausgeloest"] == {KENNUNG}      # schon zur Aufrufzeit vermerkt

    zweiter = _lauf(umgebung, weg="assistent", uebergeber=uebergeber, sender=_sender_verboten)
    assert len(uebergeber.aufrufe) == 1
    assert zweiter[0].status == "kein fälliges Paar"
    # auch der alte Weg sendet im selben Fenster nicht mehr
    dritter = _lauf(umgebung, weg="alt", sender=_sender_verboten)
    assert dritter[0].status == "kein fälliges Paar"


def test_neues_limitfenster_loest_erneut_aus(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    _lauf(umgebung, weg="assistent", uebergeber=uebergeber)
    neu = signale.Kontingent("Claude", (signale.Fenster("5h", 95, ENDE + timedelta(hours=5)),
                                        signale.Fenster("Woche", 50, ENDE + timedelta(hours=5))), stand=JETZT)
    messung = automatik.Messung(neu, _messung().codex)
    _lauf(umgebung, weg="assistent", uebergeber=uebergeber, messung=messung)
    assert len(uebergeber.aufrufe) == 2


def test_vermerk_nicht_moeglich_loest_nichts_aus_und_gibt_die_reservierung_frei(umgebung, monkeypatch):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)

    def kaputt(*a, **k):
        raise PermissionError("C:\\geheim\\pfad")

    monkeypatch.setattr(automatik, "ausgeloest_vermerken", kaputt)
    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber)

    assert staende[0].status == "Vermerk nicht möglich – kein Wechsel"
    assert "geheim" not in staende[0].status
    assert uebergeber.aufrufe == [] and automatik.ausgeloest_lesen() == frozenset()
    assert _master(umgebung).startswith("claude ") and "reserviert" not in _master(umgebung)


# --- (d) Fehler im Assistenten: fester Text, Kennung bleibt vermerkt --------------------------

@pytest.mark.parametrize("fehler,klasse", [
    (assistent.AssistentFehler("Wechsel läuft bereits C:\\geheim\\x"), "AssistentFehler"),
    (RuntimeError("Absturz in " + THREAD), "RuntimeError"),
])
def test_fehler_im_assistenten_ergibt_festen_text_und_haelt_die_kennung(umgebung, fehler, klasse):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung, fehler=fehler)

    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber)

    assert staende[0].status == f"Wechsel nicht gestartet ({klasse})" and staende[0].phase == "fehler"
    assert "geheim" not in staende[0].status and THREAD not in staende[0].status
    assert automatik.ausgeloest_lesen() == {KENNUNG}
    eintrag = [e for e in protokoll.lesen(50) if e["entscheidung"] == "automatik_nicht_gestartet"]
    assert [(e["vorgang"], e["grund"]) for e in eintrag] == [("", klasse)]
    # auch nach dem Fehler: im selben Fenster kein zweiter Versuch
    _lauf(umgebung, weg="assistent", uebergeber=uebergeber)
    assert len(uebergeber.aufrufe) == 1


def test_ursache_des_assistentenfehlers_gibt_die_klasse(umgebung):
    _laufend(umgebung)
    try:
        try:
            raise PermissionError("C:\\geheim")
        except PermissionError as ursache:
            raise assistent.AssistentFehler("Wechsel nicht gestartet: Besitz- oder Datendatei nicht lesbar") \
                from ursache
    except assistent.AssistentFehler as fehler:
        uebergeber = _Uebergeber(umgebung, fehler=fehler)
    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber)
    assert staende[0].status == "Wechsel nicht gestartet (PermissionError)"


# --- (e) jeder Schutzschritt greift weiter und ruft den Assistenten nie -----------------------

def _ohne_aufruf(umgebung, uebergeber):
    assert uebergeber.aufrufe == []
    assert automatik.ausgeloest_lesen() == frozenset()


def test_schutz_kopfzeile_nein(umgebung):
    _laufend(umgebung, bereit="nein")
    uebergeber = _Uebergeber(umgebung)
    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber)
    assert staende[0].status == automatik.STATUS_UEBERGABEPUNKT
    _ohne_aufruf(umgebung, uebergeber)


def test_schutz_kopfzeile_wird_waehrend_der_wartezeit_nein(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber, warte=lambda s: _laufend(umgebung, "nein"))
    assert staende[0].status == automatik.STATUS_CLAUDE_HOERT
    _ohne_aufruf(umgebung, uebergeber)
    assert _master(umgebung).startswith("claude ")


def test_schutz_head_aendert_sich_waehrend_der_wartezeit(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    head = {"wert": FULL_HEAD}

    def warte(sekunden):
        head["wert"] = "1234567" + FULL_HEAD[7:]

    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber, warte=warte, head=lambda: head["wert"])
    assert staende[0].status == automatik.STATUS_VERALTET
    _ohne_aufruf(umgebung, uebergeber)


def test_schutz_fremder_head_vor_der_reservierung(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber, head="9999999" + FULL_HEAD[7:])
    assert staende[0].status == automatik.STATUS_VERALTET
    _ohne_aufruf(umgebung, uebergeber)


def test_schutz_reservierung_wird_ersetzt(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    master = besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md")
    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber,
                    warte=lambda s: besitz.schreiben(master, f"reserviert fremd {JETZT.isoformat()}"))
    assert staende[0].status == "Reservierung ersetzt – kein Versand"
    _ohne_aufruf(umgebung, uebergeber)
    assert _master(umgebung).startswith("reserviert fremd")


def test_schutz_codex_ist_schon_master(umgebung):
    _laufend(umgebung)
    besitz.schreiben(besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md"),
                     f"codex fremd@1 {JETZT.isoformat()}")
    uebergeber = _Uebergeber(umgebung)
    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber)
    assert staende[0].status == automatik.STATUS_CODEX_MASTER
    _ohne_aufruf(umgebung, uebergeber)


def test_schutz_belegte_themensperre(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    with zustand.thema_sperre("engineering") as frei:
        assert frei is True
        staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber)
    assert "Sperre belegt" in staende[0].status
    _ohne_aufruf(umgebung, uebergeber)


@pytest.mark.parametrize("master", ["claude", "codex", "hermes"])
def test_schutz_feste_masterrolle(umgebung, master):
    _laufend(umgebung)
    modi.master_setzen("engineering", master, repo=umgebung)
    uebergeber = _Uebergeber(umgebung)
    staende = _lauf(umgebung, weg="assistent", uebergeber=uebergeber)
    assert staende[0].status == "kein fälliges Paar"
    _ohne_aufruf(umgebung, uebergeber)


def test_schutz_automatik_aus(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    staende = automatik.lauf(jetzt=JETZT, repo=umgebung, paare_liste=[_paar()], messung=_messung(),
                             schwelle=SCHWELLE, an=False, weg="assistent", uebergeber=uebergeber)
    assert [s.status for s in staende] == [automatik.STATUS_AUS]
    _ohne_aufruf(umgebung, uebergeber)


def test_trockenlauf_ruft_den_assistenten_nicht(umgebung):
    _laufend(umgebung)
    uebergeber = _Uebergeber(umgebung)
    staende = automatik.lauf(jetzt=JETZT, repo=umgebung, paare_liste=[_paar()], messung=_messung(),
                             schwelle=SCHWELLE, an=True, trocken=True, vorgangsliste=[], weg="assistent",
                             uebergeber=uebergeber)
    assert staende[0].status == "bereit (trocken)"
    _ohne_aufruf(umgebung, uebergeber)


# --- Zusammenspiel mit dem echten Assistenten (nur Attrappe für den Codex-Transport) ----------

def test_echter_assistent_uebernimmt_ueber_die_codex_queue(umgebung, monkeypatch):
    _laufend(umgebung)
    transporte = []

    def transport(liste, timeout):
        with zustand.thema_sperre("engineering") as frei:
            transporte.append((list(liste), frei))
        return 0

    monkeypatch.setattr(codex_senden, "_transport", transport)

    staende = _lauf(umgebung, weg="assistent", sender=_sender_verboten)

    assert len(transporte) == 1
    liste, sperre_frei = transporte[0]
    assert sperre_frei is True                                  # nie unter der Themensperre
    assert liste[1] == "queue" and liste[liste.index("--thread") + 1] == THREAD
    vorgangsliste = av.lesen()
    assert len(vorgangsliste) == 1
    v = vorgangsliste[0]
    assert (v.thema, v.ziel, v.von_chat, v.phase) == ("engineering", "codex", None, "gesendet")
    assert v.nach_chat == {"werkzeug": "codex", "kennung": THREAD}
    assert staende[0].phase == "gesendet"
    assert besitz.assistent_marke(_master(umgebung))[:2] == ("codex", "engineering")
    assert vorgaenge.lesen() == []
    entscheidungen = [e["entscheidung"] for e in protokoll.lesen(50)]
    assert "automatik_ausgeloest" in entscheidungen and "rolle_gesetzt" in entscheidungen
    # zweiter Lauf im selben Fenster: nichts mehr
    _lauf(umgebung, weg="assistent", sender=_sender_verboten)
    assert len(transporte) == 1 and len(av.lesen()) == 1


def test_echter_assistent_fehler_wird_zum_festen_text(umgebung, monkeypatch):
    _laufend(umgebung)
    monkeypatch.setattr(codex_senden, "_transport", lambda liste, timeout: 1)   # nach dem Start: unklar
    staende = _lauf(umgebung, weg="assistent", sender=_sender_verboten)
    # `uebergeben` liefert auch bei unklarer Zustellung einen Vorgang (Phase unklar), kein Wiederholen
    assert staende[0].phase == "unklar"
    assert automatik.ausgeloest_lesen() == {KENNUNG}
    _lauf(umgebung, weg="assistent", sender=_sender_verboten)
    assert len(av.lesen()) == 1


# --- Anzeige: der aktive Weg ist sichtbar ----------------------------------------------------

def test_status_zeile_und_menue_nennen_den_weg_nur_bei_assistent():
    assert automatik.status_zeile(_paar(), [], JETZT) == "bereit"
    assert automatik.status_zeile(_paar(), [], JETZT, anzeige.WEG_ALT) == "bereit"
    assert automatik.status_zeile(_paar(), [], JETZT, anzeige.WEG_ASSISTENT) == "bereit · über Wechselassistent"
    assert automatik.menue_zeilen([_paar()], [], JETZT) == ["engineering: bereit"]
    assert automatik.menue_zeilen([_paar()], [], JETZT, anzeige.WEG_ASSISTENT) == \
        ["engineering: bereit · über Wechselassistent"]


def test_protokoll_klartext_der_automatik():
    from master_schalter import fenster_modell as fm
    ok = fm.protokoll_klartext({"zeit": JETZT.isoformat(), "thema": "engineering",
                                "entscheidung": "automatik_ausgeloest", "grund": "wechselassistent",
                                "vorgang": "wechsel-1"}, JETZT)
    assert "Automatik" in ok and "wechsel-1" not in ok
    fehler = fm.protokoll_klartext({"zeit": JETZT.isoformat(), "thema": "engineering",
                                    "entscheidung": "automatik_nicht_gestartet", "grund": "PermissionError"}, JETZT)
    assert "nicht gestartet (PermissionError)" in fehler
    fremd = fm.protokoll_klartext({"zeit": JETZT.isoformat(), "thema": "engineering",
                                   "entscheidung": "automatik_nicht_gestartet", "grund": "C:\\x y"}, JETZT)
    assert "C:" not in fremd and "(Fehler)" in fremd


# --- (f) Einstellung ---------------------------------------------------------------------------

def test_einstellung_standard_und_kaputt_ergeben_alt(tmp_path):
    datei = tmp_path / "einstellungen.json"
    assert anzeige.automatik_weg(datei) == "alt"                 # Datei fehlt
    for inhalt in ("kein json", "[]", "{}", '{"automatik_weg": 1}', '{"automatik_weg": true}',
                   '{"automatik_weg": "ASSISTENT"}', '{"automatik_weg": "irgendwas"}', '{"automatik_weg": null}'):
        datei.write_text(inhalt, encoding="utf-8")
        assert anzeige.automatik_weg(datei) == "alt", inhalt


def test_einstellung_setzen_erhaelt_andere_felder(tmp_path):
    datei = tmp_path / "einstellungen.json"
    anzeige.schwelle_setzen(90, datei)
    anzeige.automatik_setzen(True, datei)
    anzeige.automatik_weg_setzen("assistent", datei)
    assert anzeige.automatik_weg(datei) == "assistent"
    assert anzeige.schwelle(datei) == 90 and anzeige.automatik_an(datei) is True
    anzeige.automatik_weg_setzen("alt", datei)
    assert anzeige.automatik_weg(datei) == "alt" and anzeige.schwelle(datei) == 90
    # die anderen Setzer lassen den Weg stehen
    anzeige.automatik_weg_setzen("assistent", datei)
    anzeige.schwelle_setzen(80, datei)
    anzeige.automatik_setzen(False, datei)
    assert anzeige.automatik_weg(datei) == "assistent"


@pytest.mark.parametrize("wert", ["", "ASSISTENT", "geheim-123", None, 1, True])
def test_einstellung_setzen_lehnt_ungueltiges_ab_ohne_echo(tmp_path, wert):
    datei = tmp_path / "einstellungen.json"
    with pytest.raises(ValueError) as fehler:
        anzeige.automatik_weg_setzen(wert, datei)
    assert "geheim-123" not in str(fehler.value)
    assert not datei.exists()
