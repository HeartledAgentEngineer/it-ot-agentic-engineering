"""Tests für das Ansichtsmodell des Wechselfensters (`fenster_modell.py`) – ohne Oberfläche, nur Attrappen.

Die auffälligen Kennungen/Titel dienen dem Nachweis, dass sie nur in den Texten für das lokale Fenster vorkommen
(Chat-Auswahl, Bestätigung), nie in Protokoll-Klartext, Hinweisen oder Fehlermeldungen (G9).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import (assistent, besitz, chat_register, chat_zuordnung, fenster_modell as fm, paare,
                             postfach, protokoll, status)
from master_schalter import assistent_vorgaenge as av
from master_schalter.fenster_modell import Auswahl, ChatEintrag, ChatInfo

THEMA = "engineering"
K_ALT = "GEHEIM-ALT-4711"
K_NEU = "00000000-0000-4000-8000-0000000000b2"        # gültige UUID: taugt auch als Codex-Paar
TITEL_ALT = "Streng geheimer Titel Alt"
JETZT = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _codex_attrappe(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_CODEX", str(tmp_path / "codex-attrappe.exe"))


def _v(phase, ziel="hermes", von="claude", ident="v-1", zeit=JETZT, thema=THEMA, **extra):
    return av.Vorgang(ident, thema, ziel, von, phase, zeit.isoformat(),
                      {"master": "kontingent", "worker": "workflow", "modell": None}, "", **extra)


def _chat(werkzeug, kennung, titel, minuten=0, ordner=""):
    return chat_register.Chat(werkzeug, kennung, titel, ordner, JETZT - timedelta(minutes=minuten), "claude-desktop")


def _info(chat, vorschlag=None, grund="unbekannt", zustand="unbekannt"):
    return ChatInfo(chat, vorschlag, grund, zustand)


# --- Tabellen ------------------------------------------------------------------------------------

def test_jede_phase_hat_kurz_und_klartext():
    assert set(fm.PHASE_KURZ) == set(av.PHASEN) == set(fm.PHASE_TEXT)


def test_alter_text_stufen():
    assert fm.alter_text(JETZT - timedelta(seconds=30), JETZT) == "gerade eben"
    assert fm.alter_text(JETZT - timedelta(minutes=5), JETZT) == "vor 5 min"
    assert fm.alter_text(JETZT - timedelta(hours=3), JETZT) == "vor 3 h"
    assert fm.alter_text(JETZT - timedelta(days=4), JETZT) == "vor 4 d"
    assert fm.alter_text(None, JETZT) == "Alter unbekannt"


# --- Zustellhinweis nach E8 --------------------------------------------------------------------

def test_hinweis_codex_gesendet_ist_zugestellt_queue():
    assert fm.zustellhinweis(_v("gesendet", ziel="codex"), JETZT) == "Codex: zugestellt (Queue)"


def test_hinweis_claude_im_postfach_sagt_wann_es_ankommt():
    text = fm.zustellhinweis(_v("im_postfach", ziel="claude"), JETZT)
    assert text == ("Claude: liegt im Postfach, kommt mit der nächsten Eingabe/dem nächsten Werkzeugschritt "
                    "in diesem Chat")
    assert "zugestellt" not in text


def test_hinweis_hermes_im_postfach_nennt_manuellen_weg_und_nie_zugestellt():
    text = fm.zustellhinweis(_v("im_postfach", ziel="hermes"), JETZT)
    assert text == "Hermes: noch kein automatischer Empfang – Text unten kopieren und im Hermes-Chat einfügen"
    assert "zugestellt" not in text


def test_hinweis_abgabe_offen_zeigt_restfrist_minuten_sekunden():
    vorgang = _v("abgabe_angefragt", abgabe_seit=(JETZT - timedelta(minutes=3)).isoformat())
    assert fm.zustellhinweis(vorgang, JETZT) == "wartet auf Abgabe des alten Chats (Frist läuft noch 7:00)"
    spaeter = JETZT + timedelta(minutes=6, seconds=55)
    assert "Frist läuft noch 0:05" in fm.zustellhinweis(vorgang, spaeter)


def test_hinweis_abgabe_offen_nach_ablauf_und_bei_unlesbarer_zeit():
    alt = _v("abgabe_unklar", abgabe_seit=(JETZT - timedelta(minutes=11)).isoformat())
    assert "Frist abgelaufen" in fm.zustellhinweis(alt, JETZT)
    kaputt = _v("abgabe_angefragt", abgabe_seit="keine-zeit")
    assert fm.zustellhinweis(kaputt, JETZT) == "wartet auf Abgabe des alten Chats (Frist läuft)"


def test_hinweis_abgabe_fehler_sagt_dass_nichts_gesendet_wurde():
    vorgang = _v("abgabe_fehler", abgabe_seit=(JETZT - timedelta(minutes=1)).isoformat())
    text = fm.zustellhinweis(vorgang, JETZT)
    assert text.startswith("Abgabe-Auftrag nicht gestartet") and "9:00" in text


def test_hinweis_abgabe_mit_hermes_als_altem_chat_verweist_auf_kopieren():
    vorgang = _v("abgabe_angefragt", von="hermes", von_chat={"werkzeug": "hermes", "kennung": K_ALT},
                 abgabe_seit=JETZT.isoformat())
    assert "Hermes: noch kein automatischer Empfang" in fm.zustellhinweis(vorgang, JETZT)
    assert K_ALT not in fm.zustellhinweis(vorgang, JETZT)


def test_hinweis_im_chat_bestaetigt_und_gruende():
    assert fm.zustellhinweis(_v("im_chat"), JETZT) == "im Chat angekommen, Quittung offen"
    assert fm.zustellhinweis(_v("bestaetigt"), JETZT) == "übernommen ✓"
    assert fm.zustellhinweis(_v("verworfen", fehler="Stand geändert"), JETZT) == "verworfen: Stand geändert"
    assert fm.zustellhinweis(_v("fehler", fehler="Zustellung nicht gestartet"), JETZT) == \
        "Zustellung fehlgeschlagen: Zustellung nicht gestartet"
    assert fm.zustellhinweis(_v("unklar", fehler="Zustellung unklar – nicht erneut gesendet"), JETZT).startswith(
        "Zustellung unklar: ")
    assert fm.zustellhinweis(_v("verworfen"), JETZT) == "verworfen"


def test_hinweis_rolle_gesetzt_ohne_neuen_chat_sagt_nichts_zugestellt():
    text = fm.zustellhinweis(_v("rolle_gesetzt", ziel="codex"), JETZT)
    assert "kein neuer Chat gewählt" in text and "nichts zugestellt" in text
    mit = fm.zustellhinweis(_v("rolle_gesetzt", ziel="codex", nach_chat={"werkzeug": "codex", "kennung": K_NEU}),
                            JETZT)
    assert "Zustellung folgt" in mit and K_NEU not in mit


def test_jede_phase_liefert_einen_nichtleeren_hinweis():
    for phase in av.PHASEN:
        assert fm.zustellhinweis(_v(phase), JETZT)


# --- Kopiertext (Hermes) ---------------------------------------------------------------------------

def test_kopiertext_hermes_im_postfach_ist_der_feste_text(umgebung):
    vorgang = _v("im_postfach", ziel="hermes")
    assert fm.nachrichtentext(vorgang) == postfach.text("neu", THEMA, paare.laufend_bilden(THEMA), "v-1", False)
    uebersprungen = _v("im_postfach", ziel="hermes", abgabe="uebersprungen")
    assert postfach.ZUSATZ_ABGABE_FEHLTE in fm.nachrichtentext(uebersprungen)


def test_kopiertext_nur_fuer_hermes_und_nie_mit_kennung(umgebung):
    assert fm.nachrichtentext(_v("im_postfach", ziel="claude")) is None
    assert fm.nachrichtentext(_v("gesendet", ziel="codex")) is None
    abgabe = _v("abgabe_angefragt", von="hermes", von_chat={"werkzeug": "hermes", "kennung": K_ALT})
    text = fm.nachrichtentext(abgabe)
    assert text == postfach.text("abgabe_auftrag", THEMA, paare.laufend_bilden(THEMA), "v-1")
    assert K_ALT not in text
    assert fm.nachrichtentext(_v("abgabe_angefragt", von="claude")) is None


# --- Vorgangsliste ----------------------------------------------------------------------------------

def test_vorgang_zeilen_offene_zuerst_dann_hoechstens_zehn_abgeschlossene():
    liste = [_v("bestaetigt", ident=f"a{n:02d}") for n in range(15)]
    liste += [_v("abgabe_angefragt", ident="o1"), _v("im_postfach", ident="o2")]
    zeilen = fm.vorgang_zeilen(liste, JETZT)
    assert [z.id for z in zeilen[:2]] == ["o2", "o1"]
    assert [z.id for z in zeilen[2:]] == [f"a{n:02d}" for n in range(14, 4, -1)]
    assert len(zeilen) == 12
    assert zeilen[0].offen and not zeilen[-1].offen


def test_vorgang_zeile_richtung_phase_und_knoepfe():
    abbrechbar = fm.vorgang_zeile(_v("abgabe_angefragt", von="codex", ziel="claude"), JETZT)
    assert abbrechbar.richtung == "Codex → Claude" and abbrechbar.phase == "Abgabe angefragt"
    assert abbrechbar.offen and abbrechbar.kann_abbrechen
    spaeter = fm.vorgang_zeile(_v("im_postfach", ziel="claude"), JETZT)
    assert spaeter.offen and not spaeter.kann_abbrechen
    fertig = fm.vorgang_zeile(_v("bestaetigt"), JETZT)
    assert not fertig.offen and not fertig.kann_abbrechen


# --- Protokoll in Klartext --------------------------------------------------------------------------

def test_protokoll_klartext_uebersetzt_ablauf_ohne_kennungen(umgebung):
    protokoll.schreiben("GEHEIM-VORGANG-9", THEMA, "angelegt", "claude -> hermes")
    protokoll.schreiben("GEHEIM-VORGANG-9", THEMA, "abgabe_zustellweg", "claude")
    protokoll.schreiben("GEHEIM-VORGANG-9", THEMA, "abgabe_uebersprungen", "Frist abgelaufen")
    protokoll.schreiben("GEHEIM-VORGANG-9", THEMA, "rolle_gesetzt", "hermes")
    protokoll.schreiben("GEHEIM-VORGANG-9", THEMA, "neu_ergebnis", "im_postfach")
    protokoll.schreiben("GEHEIM-VORGANG-9", THEMA, "verworfen", "von Hand abgebrochen")

    zeilen = fm.protokoll_zeilen(protokoll.lesen(), JETZT)

    assert len(zeilen) == 6
    assert zeilen[-1].endswith("engineering: Wechsel angelegt: Claude → Hermes")      # ältester Eintrag unten
    text = "\n".join(zeilen)
    for erwartet in ("Abgabe-Auftrag an Claude unterwegs", "Abgabe übersprungen: Frist abgelaufen",
                     "Rolle gesetzt: Hermes führt das Thema", "Nachricht liegt im Postfach des neuen Chats",
                     "Wechsel verworfen: von Hand abgebrochen"):
        assert erwartet in text
    assert "GEHEIM-VORGANG-9" not in text


def test_protokoll_klartext_uebernimmt_keine_freien_gruende_und_ids():
    eintrag = {"zeit": JETZT.isoformat(), "vorgang": "GEHEIM-VORGANG-9", "thema": THEMA,
               "entscheidung": "verworfen", "grund": "C:/Users/sebas/geheim/Titel Streng"}
    text = fm.protokoll_klartext(eintrag, JETZT)
    assert text.endswith("engineering: Wechsel verworfen")
    for fremd in ({"entscheidung": "unbekannte_art", "grund": "Streng geheimer Titel"},
                  {"entscheidung": 5, "grund": ["x"]}, {}, {"thema": "../x", "entscheidung": "angelegt"}):
        satz = fm.protokoll_klartext({"zeit": "kaputt", **fremd}, JETZT)
        assert "Streng" not in satz and "../x" not in satz
        assert "Eintrag im Protokoll" in satz or "Wechsel angelegt" in satz


def test_protokoll_klartext_fortsetzen_fehler_nur_klasse():
    satz = fm.protokoll_klartext({"zeit": JETZT.isoformat(), "thema": THEMA,
                                  "entscheidung": "fortsetzen_fehlgeschlagen", "grund": "SperrFehler"}, JETZT)
    assert "(SperrFehler)" in satz
    satz = fm.protokoll_klartext({"zeit": JETZT.isoformat(), "thema": THEMA,
                                  "entscheidung": "fortsetzen_fehlgeschlagen", "grund": "C:\\x y"}, JETZT)
    assert "C:" not in satz and "(Fehler)" in satz


def test_echter_ablauf_ergibt_protokoll_klartext_ohne_titel_und_kennungen(umgebung):
    assistent.uebergeben(THEMA, "hermes", von_chat=assistent.ChatRef("claude", K_ALT), repo=umgebung.repo)
    text = "\n".join(fm.protokoll_zeilen(protokoll.lesen(), JETZT))
    assert "Wechsel angelegt: Claude → Hermes" in text
    assert K_ALT not in text and TITEL_ALT not in text
    assert av.lesen()[0].id not in text


# --- Chat-Auswahl ----------------------------------------------------------------------------------

def test_chat_optionen_filtert_werkzeug_sortiert_und_haengt_leer_an():
    chats = [_info(_chat("claude", "alt", "Alt", minuten=90)), _info(_chat("claude", "neu", "Neu", minuten=5)),
             _info(_chat("codex", "cx", "Codex-Chat", minuten=1))]
    eintraege, vorbelegt = fm.chat_optionen(chats, "claude", THEMA, alt=True, jetzt=JETZT)
    assert [e.kennung for e in eintraege] == ["neu", "alt", None]
    assert eintraege[-1].text == "ohne alten Chat (Abgabe überspringen)" == fm.ALT_CHAT_LEER
    assert vorbelegt is None
    ziel, _ = fm.chat_optionen(chats, "codex", THEMA, alt=False, jetzt=JETZT)
    assert [e.kennung for e in ziel] == ["cx", None] and ziel[-1].text == "ohne (nur Rolle setzen)"


def test_chat_optionen_belegt_mit_dem_juengsten_vorschlag_vor():
    chats = [_info(_chat("claude", "a", "Anderes", minuten=1), vorschlag="anderes", grund="Ordner"),
             _info(_chat("claude", "b", "Passt alt", minuten=60), vorschlag=THEMA, grund="Ordner"),
             _info(_chat("claude", "c", "Passt neu", minuten=20), vorschlag=THEMA, grund="Stichwort")]
    eintraege, vorbelegt = fm.chat_optionen(chats, "claude", THEMA, alt=True, jetzt=JETZT)
    assert [e.kennung for e in eintraege][:3] == ["a", "c", "b"]
    assert vorbelegt == 1 and eintraege[vorbelegt].kennung == "c"
    assert "Vorschlag (Stichwort)" in eintraege[1].text and "Vorschlag" not in eintraege[0].text


def test_chat_optionen_ohne_vorschlag_bleibt_leer_und_ohne_werkzeug_nur_der_leereintrag():
    chats = [_info(_chat("claude", "a", "A", minuten=1))]
    assert fm.chat_optionen(chats, "claude", THEMA, alt=True)[1] is None
    assert fm.chat_optionen(chats, "claude", None, alt=True)[1] is None
    eintraege, vorbelegt = fm.chat_optionen(chats, None, THEMA, alt=True)
    assert [e.text for e in eintraege] == [fm.ALT_CHAT_LEER] and vorbelegt is None


def test_chat_text_titel_zeit_und_zustand():
    info = _info(_chat("claude", "k1234567890", "Mein Titel", minuten=0), zustand="arbeitet")
    lokal = JETZT.astimezone().strftime("%H:%M")
    assert fm.chat_text(info, THEMA, JETZT) == f"Mein Titel · zuletzt {lokal} · arbeitet"
    ohne = _info(_chat("claude", "k1234567890", ""), zustand="ruht")
    assert fm.chat_text(ohne, THEMA, JETZT).startswith("(ohne Titel) k1234567 · zuletzt ")
    assert fm.chat_text(ohne, THEMA, JETZT).endswith(" · ruht")
    alt = _info(_chat("claude", "k", "Von gestern", minuten=60 * 24 * 2))
    assert (JETZT - timedelta(days=2)).astimezone().strftime("%d.%m. %H:%M") in fm.chat_text(alt, THEMA, JETZT)


# --- Momentaufnahme ---------------------------------------------------------------------------------

def test_aufnehmen_themen_master_kopfzeile_und_automatik(umgebung):
    umgebung.marke_setzen("hermes 2026-10-25T10:00:00+00:00 modus abc")
    kopf = umgebung.repo / paare.laufend_bilden(THEMA)
    kopf.parent.mkdir(parents=True, exist_ok=True)
    kopf.write_text(f"Übergabebereit: ja · {(JETZT - timedelta(minutes=5)).isoformat()} · abcdef1\n",
                    encoding="utf-8")
    paare.setzen("anderes-thema", "00000000-0000-4000-8000-0000000000c3", paare.laufend_bilden("anderes-thema"),
                 aktiv=False)

    snap = fm.aufnehmen(JETZT)

    zeilen = {t.thema: t for t in snap.themen}
    assert zeilen[THEMA].master == "Hermes" and zeilen[THEMA].master_rolle == "hermes"
    assert zeilen[THEMA].kopf == "ja · vor 5 min" and zeilen[THEMA].automatik is True
    assert zeilen["anderes-thema"].master == "Claude"            # fehlende Marke = Claude
    assert zeilen["anderes-thema"].kopf == "fehlt" and zeilen["anderes-thema"].automatik is False
    assert snap.hinweise == ()


def test_aufnehmen_besitz_reserviert_oder_unlesbar_ist_nicht_uebergebbar(umgebung):
    umgebung.marke_setzen(f"reserviert lauf-1 {JETZT.isoformat()}")
    zeile = fm.aufnehmen(JETZT).themen[0]
    assert zeile.master == "reserviert (Umschaltung läuft)" and zeile.master_rolle is None
    umgebung.marke_setzen("seltsam 1 2")
    zeile = fm.aufnehmen(JETZT).themen[0]
    assert zeile.master == "unbekannt" and zeile.master_rolle is None


def test_aufnehmen_chats_mit_status_und_quellenhinweis(umgebung, monkeypatch):
    chat = _chat("claude", "sitzung-1", TITEL_ALT, minuten=3)
    ergebnis = chat_register.Ergebnis((chat,), {"claude-desktop": "ok", "codex": "fehlt", "hermes": "gesperrt",
                                                 "claude-cli": "nicht lesbar: OSError"})
    monkeypatch.setattr(chat_zuordnung, "uebersicht_mit_quellen",
                        lambda jetzt=None: (ergebnis, [(chat, THEMA, "Ordner")]))
    status.schreiben("claude", "sitzung-1", "arbeitet", "PostToolUse", JETZT)

    snap = fm.aufnehmen(JETZT)

    assert [(c.vorschlag, c.grund, c.zustand) for c in snap.chats] == [(THEMA, "Ordner", "arbeitet")]
    assert set(snap.hinweise) == {"Chatquelle hermes: gesperrt", "Chatquelle claude-cli: nicht lesbar: OSError"}


def test_aufnehmen_chat_ohne_statusdatei_ist_unbekannt_nie_ruht(umgebung, monkeypatch):
    chat = _chat("claude", "ohne-status", "Titel")
    monkeypatch.setattr(chat_zuordnung, "uebersicht_mit_quellen",
                        lambda jetzt=None: (chat_register.Ergebnis((chat,), {}), [(chat, None, "unbekannt")]))
    assert fm.aufnehmen(JETZT).chats[0].zustand == "unbekannt"


def test_aufnehmen_wirft_nie_und_meldet_nur_fehlerklassen(umgebung, monkeypatch):
    def kaputt(*_args, **_kwargs):
        raise OSError("C:/Users/sebas/geheimer Pfad/Titel")

    monkeypatch.setattr(chat_zuordnung, "uebersicht_mit_quellen", kaputt)
    monkeypatch.setattr(fm.av, "lesen_geprueft", kaputt)
    monkeypatch.setattr(fm.protokoll, "lesen", kaputt)
    monkeypatch.setattr(fm.paare, "lesen", kaputt)

    snap = fm.aufnehmen(JETZT)

    assert snap.themen == snap.chats == snap.vorgaenge == snap.protokoll == ()
    assert set(snap.hinweise) == {"Themen nicht lesbar (OSError)", "Chatliste nicht lesbar (OSError)",
                                  "Vorgänge nicht lesbar (OSError)", "Protokoll nicht lesbar (OSError)"}
    assert not any("geheim" in h for h in snap.hinweise)


def test_aufnehmen_vorgaenge_und_protokoll_neueste_oben(umgebung):
    umgebung.vorbereiten("v-1", phase="abgabe_angefragt")
    protokoll.schreiben("v-1", THEMA, "angelegt", "claude -> hermes")
    protokoll.schreiben("v-1", THEMA, "rolle_gesetzt", "hermes")

    snap = fm.aufnehmen(JETZT)

    assert [v.id for v in snap.vorgaenge] == ["v-1"] and snap.vorgaenge[0].offen
    assert "Rolle gesetzt" in snap.protokoll[0] and "Wechsel angelegt" in snap.protokoll[1]


# --- Prüfung der Auswahl ------------------------------------------------------------------------------

def _wahl(thema=THEMA, ziel="hermes", master="claude", von=None, nach=None):
    return Auswahl(thema, ziel, master, von, nach)


ALT_CLAUDE = ChatEintrag("Titel Alt", "claude", K_ALT, None)
NEU_HERMES = ChatEintrag("Titel Neu", "hermes", "sitzung-h", None)
OHNE_ALT = ChatEintrag(fm.ALT_CHAT_LEER)
OHNE_NEU = ChatEintrag(fm.NEU_CHAT_LEER)


@pytest.mark.parametrize("auswahl, teil", [
    (_wahl(thema=None, von=ALT_CLAUDE, nach=NEU_HERMES), "Thema"),
    (_wahl(ziel=None, von=ALT_CLAUDE, nach=NEU_HERMES), "Ziel"),
    (_wahl(ziel="gemini", von=ALT_CLAUDE, nach=NEU_HERMES), "Ziel"),
    (_wahl(master=None, von=ALT_CLAUDE, nach=NEU_HERMES), "nicht übergebbar"),
    (_wahl(von=None, nach=NEU_HERMES), "alten Chat wählen"),
    (_wahl(von=ALT_CLAUDE, nach=None), "neuen Chat wählen"),
    (_wahl(master="codex", von=ALT_CLAUDE, nach=NEU_HERMES), "nicht zum aktuellen Master"),
    (_wahl(ziel="codex", von=ALT_CLAUDE, nach=NEU_HERMES), "nicht zum gewählten Ziel"),
    (_wahl(master="hermes", ziel="hermes", von=ChatEintrag("x", "hermes", "s", None),
           nach=ChatEintrag("y", "hermes", "s", None)), "derselbe"),
])
def test_auswahl_pruefen_meldet_klare_texte(auswahl, teil):
    assert teil in fm.auswahl_pruefen(auswahl)


def test_auswahl_pruefen_erlaubt_ohne_eintraege_und_vollstaendige_auswahl():
    assert fm.auswahl_pruefen(_wahl(von=OHNE_ALT, nach=OHNE_NEU)) is None
    assert fm.auswahl_pruefen(_wahl(von=ALT_CLAUDE, nach=NEU_HERMES)) is None


def test_zusammenfassung_ist_eine_zeile():
    text = fm.zusammenfassung(_wahl(von=ALT_CLAUDE, nach=OHNE_NEU))
    assert "\n" not in text
    assert text == ("Thema engineering: Claude → Hermes · alter Chat: Titel Alt · "
                    "neuer Chat: ohne neuen Chat (nur Rolle)")
    assert "ohne alten Chat" in fm.zusammenfassung(_wahl(von=OHNE_ALT, nach=NEU_HERMES))


# --- Aktionen -------------------------------------------------------------------------------------

def test_uebergabe_ausfuehren_legt_vorgang_an_ohne_kennung_im_text(umgebung):
    auswahl = _wahl(von=ALT_CLAUDE, nach=NEU_HERMES)

    erg = fm.uebergabe_ausfuehren(auswahl)

    assert erg.ok and erg.text == "Wechsel engineering: wartet auf Abgabe"
    vorgang = av.lesen()[0]
    assert vorgang.von_chat == {"werkzeug": "claude", "kennung": K_ALT}
    assert vorgang.nach_chat == {"werkzeug": "hermes", "kennung": "sitzung-h"}
    assert K_ALT not in erg.text


def test_uebergabe_ausfuehren_ohne_chats_setzt_nur_die_rolle(umgebung):
    erg = fm.uebergabe_ausfuehren(_wahl(von=OHNE_ALT, nach=OHNE_NEU))
    assert erg.ok and erg.text == "Wechsel engineering: Rolle gesetzt"
    assert av.lesen()[0].phase == "rolle_gesetzt" and av.lesen()[0].abgabe == "uebersprungen"


def test_uebergabe_ausfuehren_unvollstaendige_auswahl_startet_nichts(umgebung):
    erg = fm.uebergabe_ausfuehren(_wahl(von=None, nach=OHNE_NEU))
    assert not erg.ok and "alten Chat" in erg.text
    assert av.lesen() == []


def test_uebergabe_ausfuehren_fehler_bereinigt_ohne_kennung(umgebung):
    erg = fm.uebergabe_ausfuehren(_wahl(thema="gibtsnicht", von=ALT_CLAUDE, nach=NEU_HERMES))
    assert not erg.ok and erg.text.startswith("Nicht übergeben: Thema unbekannt")
    assert K_ALT not in erg.text
    schlecht = ChatEintrag("x", "claude", "../PRIVAT_4711", None)
    erg = fm.uebergabe_ausfuehren(_wahl(von=schlecht, nach=NEU_HERMES))
    assert not erg.ok and "PRIVAT_4711" not in erg.text and "Chat-Kennung unzulässig" in erg.text


def test_uebergabe_ausfuehren_unerwartete_ausnahme_nur_klasse(umgebung, monkeypatch):
    def kaputt(*_args, **_kwargs):
        raise RuntimeError("C:/Users/sebas/geheim/Titel")

    monkeypatch.setattr(fm.assistent, "uebergeben", kaputt)
    erg = fm.uebergabe_ausfuehren(_wahl(von=ALT_CLAUDE, nach=NEU_HERMES))
    assert erg == fm.Ergebnis(False, "Nicht übergeben (RuntimeError)")


def test_codex_chat_abweichend_vom_vorschlag_wird_als_paar_gemerkt(umgebung):
    nach = ChatEintrag("Neuer Codex-Chat", "codex", K_NEU, vorschlag_thema=None)

    erg = fm.uebergabe_ausfuehren(_wahl(ziel="codex", von=ALT_CLAUDE, nach=nach))

    assert erg.ok and erg.text.endswith("Codex-Chat als Paar gemerkt")
    paar = next(p for p in paare.lesen() if p.thema == THEMA)
    assert paar.codex_thread == K_NEU and paar.aktiv is True


def test_codex_chat_gemäss_vorschlag_wird_nicht_erneut_gemerkt(umgebung, monkeypatch):
    gemerkt = []
    monkeypatch.setattr(fm.chat_zuordnung, "bestaetigen", lambda *a: gemerkt.append(a))
    nach = ChatEintrag("Codex", "codex", K_NEU, vorschlag_thema=THEMA)

    erg = fm.uebergabe_ausfuehren(_wahl(ziel="codex", von=ALT_CLAUDE, nach=nach))

    assert erg.ok and gemerkt == []
    assert "gemerkt" not in erg.text


def test_nicht_gemerktes_paar_meldet_nur_klasse_und_wechsel_bleibt_ok(umgebung):
    nach = ChatEintrag("Codex", "codex", "kein-uuid-format", vorschlag_thema=None)

    erg = fm.uebergabe_ausfuehren(_wahl(ziel="codex", von=ALT_CLAUDE, nach=nach))

    assert erg.ok and "Paar nicht gemerkt (ZuordnungFehler)" in erg.text
    assert "kein-uuid-format" not in erg.text


def test_weiter_und_abbrechen_melden_phase_oder_bereinigten_fehler(umgebung):
    umgebung.marke_setzen("claude 2026-10-20T10:00:00+00:00")
    umgebung.vorbereiten("v-1", phase="abgabe_angefragt")

    ok = fm.weiter("v-1")
    assert ok == fm.Ergebnis(True, "Wechsel engineering: wartet auf Abgabe")
    unbekannt = fm.weiter("v-9")
    assert not unbekannt.ok and unbekannt.text == "Nicht fortgesetzt: Vorgang unbekannt: v-9"
    schlecht = fm.weiter("../PRIVAT_4711")
    assert "PRIVAT_4711" not in schlecht.text

    weg = fm.abbrechen("v-1")
    assert weg == fm.Ergebnis(True, "Wechsel engineering: verworfen (von Hand abgebrochen)")
    nochmal = fm.abbrechen("v-1")
    assert not nochmal.ok and "Abbrechen nicht mehr möglich (Phase verworfen)" in nochmal.text


def test_weiter_unerwartete_ausnahme_nur_klasse(umgebung, monkeypatch):
    monkeypatch.setattr(fm.assistent, "fortsetzen", lambda *_a: (_ for _ in ()).throw(ValueError("C:/geheim")))
    assert fm.weiter("v-1") == fm.Ergebnis(False, "Nicht fortgesetzt (ValueError)")
    monkeypatch.setattr(fm.av, "abbrechen", lambda *_a: (_ for _ in ()).throw(OSError("C:/geheim")))
    assert fm.abbrechen("v-1") == fm.Ergebnis(False, "Nicht abgebrochen (OSError)")


# --- Windows-Hinweise ---------------------------------------------------------------------------------

def test_hinweis_abgabe_offen_erst_nach_zwei_minuten_mit_fristende():
    vorgang = _v("abgabe_angefragt", zeit=JETZT - timedelta(minutes=2), abgabe_seit=(JETZT - timedelta(minutes=2)).isoformat())
    assert fm.hinweis_fuer(vorgang, JETZT - timedelta(seconds=1)) is None
    ereignis, text = fm.hinweis_fuer(vorgang, JETZT)
    ende = (JETZT + timedelta(minutes=8)).astimezone().strftime("%H:%M")
    assert ereignis == "abgabe_offen"
    assert text == f"engineering: alter Chat hat noch nicht abgegeben – bitte kurz anstoßen (Frist bis {ende})"


def test_hinweise_rolle_uebernommen_und_blick():
    assert fm.hinweis_fuer(_v("rolle_gesetzt", ziel="codex"), JETZT) == ("rolle", "engineering: Rolle jetzt bei Codex")
    assert fm.hinweis_fuer(_v("im_postfach", ziel="claude"), JETZT)[0] == "rolle"
    assert fm.hinweis_fuer(_v("bestaetigt", ziel="hermes"), JETZT) == \
        ("uebernommen", "engineering: Hermes hat übernommen ✓")
    for phase in ("fehler", "unklar", "verworfen"):
        assert fm.hinweis_fuer(_v(phase), JETZT) == ("blick", "engineering: Wechsel braucht Blick ins Fenster")


def test_kein_hinweis_in_stillen_phasen_bei_abbruch_und_alten_vorgaengen():
    for phase in ("vorbereitet", "abgabe_sende", "abgegeben", "abgabe_uebersprungen", "abgabe_fehler"):
        assert fm.hinweis_fuer(_v(phase), JETZT) is None
    assert fm.hinweis_fuer(_v("verworfen", fehler=av.ABBRUCH_GRUND), JETZT) is None
    alt = _v("bestaetigt", zeit=JETZT - fm.HINWEIS_ALTER - timedelta(seconds=1))
    assert fm.hinweis_fuer(alt, JETZT) is None
    kaputt = av.Vorgang("v-1", THEMA, "hermes", "claude", "bestaetigt", "keine-zeit", {}, "")
    assert fm.hinweis_fuer(kaputt, JETZT) is None


def test_hinweistexte_enthalten_nie_kennungen_oder_titel():
    vorgang = _v("bestaetigt", von_chat={"werkzeug": "claude", "kennung": K_ALT},
                 nach_chat={"werkzeug": "hermes", "kennung": "sitzung-h"})
    _, text = fm.hinweis_fuer(vorgang, JETZT)
    assert K_ALT not in text and "sitzung-h" not in text
