"""Pruefungen fuer W0: WhatsApp-Bilder zaehlen + Voraussetzungen (21.10.2026).

Plan: ``.hermes/plans/2026-10-21_whatsapp-bilder.md`` (Fassung 5, Schritt W0).

Nur erfundene Daten in ``tmp_path``. Die pCloud-API ist die Attrappe aus
``test_whatsapp_bilder_hochladen.py`` (zaehlt jeden Aufruf je Methode). Erfundene
"sensible" Namen und ein erfundener Token duerfen nie in der Ausgabe erscheinen.

Abgedeckt:
  * Zaehlung je Unterordner (empfangen/gesendet), Jahr und Dateityp; keine Namen.
  * Zugriff ist eine eigene Pruefung: Ordner fehlt / nicht lesbar -> Exit 3, nie 0.
  * ``--voraussetzungen``: httpx, Token (Umgebung oder .env), Host nur eapi.pcloud.com
    (sonst Exit 3 ohne Netzanfrage), eine lesende ``userinfo``-Abfrage.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_whatsapp_bilder_zaehlen.py -q
"""

from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_whatsapp_bilder_hochladen import (  # noqa: F401  (Attrappe + Konstanten)
    HANDY, SENSIBEL, TOKEN, PCloudAttrappe, baue_medien)

MELDUNG = ("kein Zugriff auf den WhatsApp-Medienordner "
           "(Termux-Speicherrecht: termux-setup-storage)")


def _alt(pfad: Path, jahr: int = 2018):
    zeit = datetime.datetime(jahr, 3, 1, 12, 0).timestamp()
    os.utime(pfad, (zeit, zeit))


@pytest.fixture
def z(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(HANDY))
    import whatsapp_bilder_gemeinsam as gemeinsam
    import whatsapp_bilder_zaehlen as zaehlen
    for name in ("PCLOUD_TOKEN", "PCLOUD_HOST"):
        monkeypatch.delenv(name, raising=False)
    ug = gemeinsam.uebergabe_laden()
    monkeypatch.setattr(ug, "ENV_DATEI", tmp_path / "keine.env")
    monkeypatch.setenv("PCLOUD_TOKEN", TOKEN)
    att = PCloudAttrappe().installieren(monkeypatch)
    wurzel = baue_medien(tmp_path, voll=True)
    (wurzel / "Scan.zaunstein").write_bytes(b"12345")
    _alt(wurzel / "Passwort.txt")
    _alt(wurzel / "Scan.zaunstein")
    return SimpleNamespace(
        zaehlen=zaehlen, gemeinsam=gemeinsam, ug=ug, att=att, wurzel=wurzel, tmp=tmp_path,
        lauf=lambda *zusatz: zaehlen.main(["--ordner", str(wurzel), *zusatz]))


# ═══════════════════════════════════════════════════════════════════════════
# 1. Zaehlen
# ═══════════════════════════════════════════════════════════════════════════

def test_zaehlt_je_unterordner_jahr_und_typ(z):
    medien = z.gemeinsam.medien_lesen(str(z.wurzel))
    bericht = z.zaehlen.zaehlen(medien)
    emp, ges = bericht["empfangen"], bericht["gesendet"]
    assert emp["dateien"] == 5 and emp["bilder"] == 3
    assert ges["dateien"] == 2 and ges["bilder"] == 2
    assert emp["bytes"] == sum(p.stat().st_size for p in z.wurzel.iterdir()
                               if p.is_file() and not p.name.startswith("."))
    assert {j: v["dateien"] for j, v in emp["jahre"].items()} == {2020: 1, 2021: 1, 2019: 1, 2018: 2}
    assert {j: v["dateien"] for j, v in ges["jahre"].items()} == {2022: 2}
    assert emp["typen"] == {".jpg": 1, ".jpeg": 1, ".png": 1, ".txt": 1, "andere": 1}
    assert ges["typen"] == {".jpg": 1, ".webp": 1}
    assert bericht["uebersprungen"] == {
        "versteckt": 2, "private": 1, "unterordner": 1, "nicht_lesbar": 0}


def test_jahr_kommt_aus_dem_namen_sonst_aus_mtime(z):
    jahr = z.gemeinsam.jahr_bestimmen
    zeit_2015 = datetime.datetime(2015, 6, 1).timestamp()
    assert jahr("IMG-20200101-WA0001.jpg", zeit_2015) == 2020
    assert jahr("WhatsApp Image 2021-03-04 at 10.11.12.jpeg", zeit_2015) == 2021
    assert jahr("Foto ohne Datum.jpg", zeit_2015) == 2015
    assert jahr("IMG-20201340-WA0001.jpg", zeit_2015) == 2015      # Monat 13: kein Datum


def test_ausgabe_nur_zahlen_ohne_namen(z, capsys):
    assert z.lauf() == 0
    aus = capsys.readouterr()
    text = aus.out + aus.err
    assert "empfangen: 5 Dateien" in text and "gesendet: 2 Dateien" in text
    assert "2020: 1" in text and "2022: 2" in text and "andere 1" in text
    for wort in SENSIBEL + ("IMG-", "WA0001", ".zaunstein", str(z.tmp)):
        assert wort not in text, f"{wort!r} in der Ausgabe"
    assert z.att.gesamt == 0                      # ohne --voraussetzungen kein Netz


def test_leerer_lesbarer_ordner_darf_null_melden(z, tmp_path, capsys):
    leer = tmp_path / "leer"
    leer.mkdir()
    assert z.zaehlen.main(["--ordner", str(leer)]) == 0
    assert "empfangen: 0 Dateien" in capsys.readouterr().out


def test_fehlender_gesendet_ordner_ist_null_aber_kein_fehler(z, tmp_path, capsys):
    nur = tmp_path / "nur"
    nur.mkdir()
    (nur / "IMG-20200101-WA0001.jpg").write_bytes(b"x")
    assert z.zaehlen.main(["--ordner", str(nur)]) == 0
    assert "gesendet: 0 Dateien" in capsys.readouterr().out


# ═══════════════════════════════════════════════════════════════════════════
# 2. Zugriff ist eine eigene Pruefung (Exit 3, nie eine Nullzaehlung)
# ═══════════════════════════════════════════════════════════════════════════

def test_ordner_fehlt_ist_exit_3(z, tmp_path, capsys):
    assert z.zaehlen.main(["--ordner", str(tmp_path / "gibtsnicht")]) == 3
    aus = capsys.readouterr()
    assert MELDUNG in aus.err and "Dateien" not in aus.out
    assert str(tmp_path) not in aus.err


def test_pfad_ist_eine_datei_ist_exit_3(z, tmp_path):
    datei = tmp_path / "datei.txt"
    datei.write_text("x", encoding="utf-8")
    assert z.zaehlen.main(["--ordner", str(datei)]) == 3


def test_zugriff_verweigert_os_access_ist_exit_3(z, monkeypatch, capsys):
    monkeypatch.setattr(os, "access", lambda *a, **k: False)
    assert z.lauf() == 3
    aus = capsys.readouterr()
    assert aus.err.strip() == MELDUNG and "Dateien" not in aus.out


def test_listdir_wirft_ist_exit_3(z, monkeypatch, capsys):
    echt = os.listdir

    def verweigert(pfad="."):
        if str(pfad) == str(z.wurzel):
            raise PermissionError(13, f"Zugriff verweigert: {pfad}")
        return echt(pfad)

    monkeypatch.setattr(os, "listdir", verweigert)
    assert z.lauf() == 3
    aus = capsys.readouterr()
    assert aus.err.strip() == MELDUNG and "Dateien" not in aus.out


def test_gesendet_vorhanden_aber_nicht_lesbar_ist_exit_3(z, monkeypatch, capsys):
    echt = os.listdir
    sent = os.path.join(str(z.wurzel), "Sent")

    def verweigert(pfad="."):
        if str(pfad) == sent:
            raise PermissionError(13, "nein")
        return echt(pfad)

    monkeypatch.setattr(os, "listdir", verweigert)
    assert z.lauf() == 3
    assert capsys.readouterr().err.strip() == MELDUNG


# ═══════════════════════════════════════════════════════════════════════════
# 3. --voraussetzungen
# ═══════════════════════════════════════════════════════════════════════════

def test_voraussetzungen_alles_da_ist_exit_0_mit_genau_einer_lesenden_abfrage(z, capsys):
    assert z.lauf("--voraussetzungen") == 0
    aus = capsys.readouterr()
    assert dict(z.att.aufrufe) == {"userinfo": 1}
    assert z.att.schreibend == 0
    assert "Token ja" in aus.out and "pCloud ja" in aus.out
    assert TOKEN not in aus.out + aus.err


def test_httpx_fehlt_ist_exit_3_ohne_netz(z, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "httpx", None)           # Import-Attrappe
    assert z.lauf("--voraussetzungen") == 3
    aus = capsys.readouterr()
    assert "httpx" in aus.err and aus.err.strip().count("\n") == 0
    assert z.att.gesamt == 0


def test_httpx_wird_ohne_voraussetzungen_nicht_gebraucht(z, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "httpx", None)
    assert z.lauf() == 0


def test_token_fehlt_ist_exit_3(z, monkeypatch, capsys):
    monkeypatch.delenv("PCLOUD_TOKEN")
    assert z.lauf("--voraussetzungen") == 3
    aus = capsys.readouterr()
    assert "PCLOUD_TOKEN" in aus.err and aus.err.strip().count("\n") == 0
    assert z.att.gesamt == 0


def test_token_nur_in_umgebung_wird_gefunden(z):
    zugang = z.gemeinsam.zugang_aufloesen()
    assert zugang.token == TOKEN and zugang.host == "eapi.pcloud.com"


def test_token_nur_in_env_datei_wird_gefunden(z, monkeypatch, capsys):
    monkeypatch.delenv("PCLOUD_TOKEN")
    env = z.tmp / "erfunden.env"
    env.write_text('# Kommentar\nPCLOUD_TOKEN="tok-nur-in-der-datei-erfunden"\n', encoding="utf-8")
    monkeypatch.setattr(z.ug, "ENV_DATEI", env)
    assert z.gemeinsam.zugang_aufloesen().token == "tok-nur-in-der-datei-erfunden"
    assert z.lauf("--voraussetzungen") == 0
    aus = capsys.readouterr()
    assert "tok-nur-in-der-datei" not in aus.out + aus.err
    assert {p.get("auth") for _, p in z.att.parameter} == {"tok-nur-in-der-datei-erfunden"}


def test_umgebung_hat_vorrang_vor_env_datei(z, monkeypatch):
    env = z.tmp / "erfunden.env"
    env.write_text("PCLOUD_TOKEN=tok-aus-datei\n", encoding="utf-8")
    monkeypatch.setattr(z.ug, "ENV_DATEI", env)
    assert z.gemeinsam.zugang_aufloesen().token == TOKEN


@pytest.mark.parametrize("quelle,wert", [
    ("umgebung", "boesewicht.example"), ("umgebung", "api.pcloud.com"),
    ("umgebung", "eapi.pcloud.com:8443"), ("umgebung", "eapi.pcloud.com.boesewicht.example"),
    ("env_datei", "boesewicht.example"), ("env_datei", "http://boesewicht.example/")])
def test_abweichender_host_ist_exit_3_ohne_netzanfrage(z, monkeypatch, capsys, quelle, wert):
    if quelle == "umgebung":
        monkeypatch.setenv("PCLOUD_HOST", wert)
    else:
        env = z.tmp / "erfunden.env"
        env.write_text(f"PCLOUD_TOKEN={TOKEN}\nPCLOUD_HOST={wert}\n", encoding="utf-8")
        monkeypatch.delenv("PCLOUD_TOKEN")
        monkeypatch.setattr(z.ug, "ENV_DATEI", env)
    assert z.lauf("--voraussetzungen") == 3
    aus = capsys.readouterr()
    assert z.att.gesamt == 0                                # 0 Aufrufe fuer ALLE Methoden
    assert dict(z.att.hosts) == {}
    assert "boesewicht" not in aus.out + aus.err
    if wert not in z.gemeinsam.ERLAUBTER_HOST:        # "api.pcloud.com" steckt im erlaubten Namen
        assert wert not in aus.out + aus.err
    assert aus.err.strip().count("\n") == 0 and TOKEN not in aus.out + aus.err
    with pytest.raises(z.gemeinsam.Voraussetzung):
        z.gemeinsam.zugang_aufloesen()


def test_host_mit_schema_und_schraegstrich_wird_normalisiert(z, monkeypatch):
    monkeypatch.setenv("PCLOUD_HOST", "https://eapi.pcloud.com/")
    assert z.gemeinsam.zugang_aufloesen().host == "eapi.pcloud.com"


def test_userinfo_fehlgeschlagen_ist_exit_3(z, capsys):
    z.att.userinfo_result = 1000
    assert z.lauf("--voraussetzungen") == 3
    aus = capsys.readouterr()
    assert aus.err.strip().count("\n") == 0 and "userinfo" in aus.err
    assert TOKEN not in aus.out + aus.err
    assert dict(z.att.aufrufe) == {"userinfo": 1}


def test_userinfo_http_fehler_ist_exit_3(z, capsys):
    z.att.userinfo_status = 500
    assert z.lauf("--voraussetzungen") == 3
    assert capsys.readouterr().err.strip().count("\n") == 0


def test_voraussetzungen_ohne_medienzugriff_ist_exit_3_ohne_netz(z, monkeypatch, capsys):
    monkeypatch.setattr(os, "access", lambda *a, **k: False)
    assert z.lauf("--voraussetzungen") == 3
    assert capsys.readouterr().err.strip() == MELDUNG
    assert z.att.gesamt == 0


def test_env_wert_taucht_nie_in_der_ausgabe_auf(z, monkeypatch, capsys):
    env = z.tmp / "erfunden.env"
    env.write_text("PCLOUD_TOKEN=tok-env-geheim-erfunden\nPCLOUD_HOST=eapi.pcloud.com\n",
                   encoding="utf-8")
    monkeypatch.delenv("PCLOUD_TOKEN")
    monkeypatch.setattr(z.ug, "ENV_DATEI", env)
    for zusatz in ((), ("--voraussetzungen",)):
        z.lauf(*zusatz)
        aus = capsys.readouterr()
        assert "tok-env-geheim" not in aus.out + aus.err


def test_ungueltiger_aufruf_ist_exit_2_ohne_pfadecho(z, capsys):
    assert z.zaehlen.main(["--gibts-nicht", "/pfad/Zaunstein"]) == 2
    aus = capsys.readouterr()
    assert "Zaunstein" not in aus.out + aus.err


# ═══════════════════════════════════════════════════════════════════════════
# 4. Nachbesserung R11: "Sent" ist nie still leer
# ═══════════════════════════════════════════════════════════════════════════

def _sent(z):
    return os.path.join(str(z.wurzel), "Sent")


def test_sent_isdir_false_ist_exit_3_statt_still_null(z, monkeypatch, capsys):
    echt = os.path.isdir
    sent = _sent(z)
    monkeypatch.setattr(os.path, "isdir",
                        lambda pfad: False if str(pfad) == sent else echt(pfad))
    assert z.lauf() == 3
    aus = capsys.readouterr()
    assert aus.err.strip() == MELDUNG and "Dateien" not in aus.out


def test_sent_als_normale_datei_ist_exit_3(z, tmp_path, capsys):
    wurzel = tmp_path / "mit_sent_datei"
    wurzel.mkdir()
    (wurzel / "IMG-20200101-WA0001.jpg").write_bytes(b"x")
    (wurzel / "Sent").write_bytes(b"ich bin kein Ordner")
    assert z.zaehlen.main(["--ordner", str(wurzel)]) == 3
    aus = capsys.readouterr()
    assert aus.err.strip() == MELDUNG and "Dateien" not in aus.out


def test_sent_stat_wirft_ist_exit_3(z, monkeypatch, capsys):
    echt = os.stat
    sent = _sent(z)

    def stat(pfad, *a, **k):
        if str(pfad) == sent:
            raise PermissionError(13, f"Zugriff verweigert: {pfad}")
        return echt(pfad, *a, **k)

    monkeypatch.setattr(os, "stat", stat)
    assert z.lauf() == 3
    aus = capsys.readouterr()
    assert aus.err.strip() == MELDUNG and "Dateien" not in aus.out


def test_sent_fehlt_ganz_bleibt_exit_0_mit_gesendet_null(z, tmp_path, capsys):
    wurzel = tmp_path / "ohne_sent"
    wurzel.mkdir()
    (wurzel / "IMG-20200101-WA0001.jpg").write_bytes(b"x")
    assert z.zaehlen.main(["--ordner", str(wurzel)]) == 0
    assert "gesendet: 0 Dateien" in capsys.readouterr().out
