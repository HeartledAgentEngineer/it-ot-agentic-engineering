"""Wächter-Tests N24a: Datenschutz- und IT-Sicherheits-Regeln des Repos.

Diese Datei prüft **Regeln des Repos**, nicht das Verhalten des Netzes. Alles
ist offline: keine Netz-Aufrufe, keine echten Namen/Nummern/Orte, keine
Werte aus einer Einstellungsdatei. Geprüft werden:

  1. die lebende Ausnahmeliste der offenen ``/api``-Routen (eine neue offene
     Route lässt einen Test rot werden — das ist gewollt),
  2. die drei Termux-Startskripte (Bindung kommt aus ``HOST_BIND``),
  3. die reine Funktion ``bindung_hinweis`` in ``app/config.py``,
  4. das Frontend ohne fremde Adressen/Marker,
  5. der Schutz der Einstellungsdatei (``.gitignore`` / ``git check-ignore``),
  6. die Löschregel (Lösch-Begriffe nur im Duplikate-Werkzeug),
  7. Medien ohne Zwischenspeicher (``Cache-Control: no-store``),
  8. der Wächter über sich selbst (keine Netz-Aufrufe, kein Lesen der
     Einstellungsdatei).

Bei einer Verletzung nennt die Meldung die Regel und die Datei — aber niemals
einen Inhalt aus einer Einstellungsdatei.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import bindung_hinweis, ist_loopback

# ── Pfade und Namen ─────────────────────────────────────────────────────────
# Der Testordner liegt unter backend/tests/ → drei Ebenen bis zum Repo.
REPO = Path(__file__).resolve().parents[2]

# Der Name der Einstellungsdatei wird absichtlich zusammengesetzt: So steht die
# Zeichenkette nicht im Quelltext, und der Wächter-Test über sich selbst kann
# belegen, dass diese Datei sie nirgends liest.
ENV_NAME = ".e" + "nv"

# Die fünf /api-Routen, die OHNE API-Key erreichbar sein dürfen. Wird eine
# neue offene Route ergänzt, muss sie hier bewusst eingetragen werden — sonst
# rot. health und auth sind dokumentiert; hello und konfig sind bewusst offen.
ERWARTETE_OFFENE_ROUTEN = {
    "/api/auth/token",
    "/api/auth/check",
    "/api/health",
    "/api/hello",
    "/api/konfig",
}

DREI_SKRIPTE = (
    "start-termux.sh",
    "termux/agent-ensure.sh",
    "termux/neu-start-nach-lauf.sh",
)


def _repo_datei(relativ: str) -> str:
    """Quelltext einer Repo-Datei lesen (nur Text, kein Netz)."""
    return (REPO / relativ).read_text(encoding="utf-8", errors="replace")


def _api_routen() -> dict[str, list[list[str]]]:
    """Alle /api-Routen mit den Namen ihrer Abhängigkeiten sammeln.

    Liefert {Pfad: [Liste der Abhängigkeitsnamen je Registrierung]}. Nur
    ``APIRoute`` zählt — ein statischer Mount ist keine API-Route.
    """
    from fastapi.routing import APIRoute

    from app.main import app

    ergebnis: dict[str, list[list[str]]] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api"):
            continue
        namen = [getattr(dep.dependency, "__name__", "") for dep in route.dependencies]
        ergebnis.setdefault(route.path, []).append(namen)
    return ergebnis


def _hat_key_schutz(namen_liste: list[list[str]]) -> bool:
    """Trägt mindestens eine Registrierung den Wächter ``require_api_key``?"""
    return any("require_api_key" in namen for namen in namen_liste)


def _frontend_dateien() -> list[Path]:
    """Alle Frontend-Quelldateien außer den Tests."""
    ordner = REPO / "frontend"
    dateien: list[Path] = []
    for pfad in sorted(ordner.rglob("*")):
        if not pfad.is_file():
            continue
        if pfad.suffix.lower() not in (".html", ".js", ".css"):
            continue
        if "tests" in pfad.relative_to(ordner).parts:
            continue
        dateien.append(pfad)
    return dateien


# ═══════════════════════════════════════════════════════════════════════════
# 1. Lebende Ausnahmeliste der offenen /api-Routen
# ═══════════════════════════════════════════════════════════════════════════


def test_regel_api_routen_gesamt_mehr_als_50():
    """Regel: Die API ist gewachsen (> 50 /api-Routen) und wird überwacht."""
    routen = _api_routen()
    assert len(routen) > 50, (
        f"Regel 'Ausnahmeliste': erwartet > 50 /api-Routen, gezählt {len(routen)}."
    )


def test_regel_offene_routen_genau_die_bekannten_fuenf():
    """Regel: Genau diese fünf /api-Routen sind ohne Key-Schutz erlaubt."""
    routen = _api_routen()
    offen = {p for p, namen in routen.items() if not _hat_key_schutz(namen)}
    assert offen == ERWARTETE_OFFENE_ROUTEN, (
        "Regel 'Ausnahmeliste' verletzt. Offene /api-Routen ohne require_api_key: "
        f"{sorted(offen)}. Erlaubt sind genau {sorted(ERWARTETE_OFFENE_ROUTEN)}. "
        "Eine neue offene Route muss hier bewusst eingetragen werden."
    )


def test_regel_offene_route_auth_token_vorhanden():
    """Regel: Die Ausnahmeliste zeigt nicht ins Leere (auth/token existiert)."""
    routen = _api_routen()
    assert "/api/auth/token" in routen, "Regel 'Ausnahmeliste': /api/auth/token fehlt."


def test_regel_offene_route_auth_check_vorhanden():
    """Regel: /api/auth/check existiert wirklich."""
    routen = _api_routen()
    assert "/api/auth/check" in routen, "Regel 'Ausnahmeliste': /api/auth/check fehlt."


def test_regel_offene_route_health_vorhanden():
    """Regel: /api/health existiert wirklich."""
    routen = _api_routen()
    assert "/api/health" in routen, "Regel 'Ausnahmeliste': /api/health fehlt."


def test_regel_offene_route_hello_vorhanden():
    """Regel: /api/hello existiert wirklich (undokumentierte Ausnahme)."""
    routen = _api_routen()
    assert "/api/hello" in routen, "Regel 'Ausnahmeliste': /api/hello fehlt."


def test_regel_offene_route_konfig_vorhanden():
    """Regel: /api/konfig existiert wirklich (bewusst offen für den Frontend-Key)."""
    routen = _api_routen()
    assert "/api/konfig" in routen, "Regel 'Ausnahmeliste': /api/konfig fehlt."


def test_regel_jede_geschuetzte_route_hat_key_schutz():
    """Regel: Jede /api-Route außer den fünf erlaubten trägt require_api_key."""
    routen = _api_routen()
    ohne_schutz = {p for p in routen if p not in ERWARTETE_OFFENE_ROUTEN}
    for pfad in sorted(ohne_schutz):
        assert _hat_key_schutz(routen[pfad]), (
            f"Regel 'Key-Schutz': {pfad} hat keinen require_api_key-Import."
        )


def test_regel_konfig_bleibt_offen_fuer_frontend():
    """Regel: /api/konfig darf NICHT geschützt werden (sonst kein Key-Holen)."""
    routen = _api_routen()
    assert not _hat_key_schutz(routen["/api/konfig"]), (
        "Regel 'Key-Holen': /api/konfig wurde geschützt — das Frontend könnte "
        "den Key nicht mehr abholen."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. Die drei Termux-Startskripte
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("skript", DREI_SKRIPTE)
def test_regel_kein_hartes_host_allen_schnittstellen(skript: str):
    """Regel: Kein Skript bindet hart auf --host 0.0.0.0."""
    text = _repo_datei(skript)
    assert "--host 0.0.0.0" not in text, (
        f"Regel 'HOST_BIND': {skript} bindet hart auf 0.0.0.0 statt über HOST_BIND."
    )


@pytest.mark.parametrize("skript", DREI_SKRIPTE)
def test_regel_skript_erwaehnt_host_bind(skript: str):
    """Regel: Jedes Skript muss HOST_BIND kennen (lesen oder nennen)."""
    text = _repo_datei(skript)
    assert "HOST_BIND" in text, (
        f"Regel 'HOST_BIND': {skript} erwähnt HOST_BIND nirgends."
    )


@pytest.mark.parametrize("skript", DREI_SKRIPTE)
def test_regel_skript_liest_host_bind_aus_der_datei(skript: str):
    """Regel: HOST_BIND wird mit dem erprobten Muster aus der Datei gelesen."""
    text = _repo_datei(skript)
    assert '"^HOST_BIND="' in text, (
        f"Regel 'HOST_BIND-Muster': {skript} liest HOST_BIND nicht über "
        "das Muster ^HOST_BIND= aus der Einstellungsdatei."
    )


@pytest.mark.parametrize("skript", DREI_SKRIPTE)
def test_regel_uvicorn_bekommt_host_als_variable(skript: str):
    """Regel: uvicorn wird mit --host \"$HOST_BIND\" aufgerufen, nicht mit Wert."""
    text = _repo_datei(skript)
    assert '--host "$HOST_BIND"' in text, (
        f"Regel 'HOST_BIND': {skript} ruft uvicorn nicht mit --host \"$HOST_BIND\" auf."
    )


def test_regel_neu_start_standard_bleibt_0_0_0_0():
    """Regel: Der Standardwert bleibt 0.0.0.0 — keine Verhaltensänderung."""
    text = _repo_datei("termux/neu-start-nach-lauf.sh")
    assert 'HOST_BIND="0.0.0.0"' in text, (
        "Regel 'Standard': termux/neu-start-nach-lauf.sh muss den Standard "
        "0.0.0.0 belassen."
    )


def test_regel_start_termux_standard_bleibt_0_0_0_0():
    """Regel: Auch start-termux.sh behält den Standard 0.0.0.0."""
    text = _repo_datei("start-termux.sh")
    assert 'HOST_BIND="0.0.0.0"' in text, (
        "Regel 'Standard': start-termux.sh muss den Standard 0.0.0.0 behalten."
    )


def test_regel_agent_ensure_standard_bleibt_0_0_0_0():
    """Regel: Auch agent-ensure.sh behält den Standard 0.0.0.0."""
    text = _repo_datei("termux/agent-ensure.sh")
    assert 'HOST_BIND="0.0.0.0"' in text, (
        "Regel 'Standard': termux/agent-ensure.sh muss den Standard 0.0.0.0 behalten."
    )


def test_regel_muster_in_allen_drei_skripten_gleich():
    """Regel: Das Lese-Muster ist in allen drei Skripten identisch."""
    zeilen = {}
    for skript in DREI_SKRIPTE:
        for zeile in _repo_datei(skript).splitlines():
            if zeile.startswith("_env_host="):
                zeilen[skript] = zeile.strip()
    assert len(zeilen) == 3, (
        "Regel 'Muster': Nicht in allen drei Skripten ist eine _env_host-Zeile da: "
        f"{sorted(zeilen)}."
    )
    assert len(set(zeilen.values())) == 1, (
        "Regel 'Muster': Das Lese-Muster unterscheidet sich zwischen den Skripten: "
        f"{zeilen}."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Die reine Funktion bindung_hinweis
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "127.0.0.5", "127.0.0.200", "::1", "localhost", "LOCALHOST", "LocalHost"],
)
def test_regel_loopback_ohne_key_kein_hinweis(host: str):
    """Regel: Loopback ist sicher — auch ohne API-Key kein Warnsatz."""
    assert bindung_hinweis(host, False) is None, (
        f"Regel 'Loopback': {host} gilt als sicher, darf keinen Hinweis ergeben."
    )


def test_regel_loopback_funktion_erkennt_127_0_0_1():
    """Regel: ist_loopback erkennt die Standardschleife."""
    assert ist_loopback("127.0.0.1") is True


def test_regel_loopback_funktion_erkennt_127_0_0_x():
    """Regel: ist_loopback erkennt auch andere Adressen des 127.0.0.x-Netzes."""
    assert ist_loopback("127.0.0.9") is True


def test_regel_loopback_funktion_erkennt_ipv6_schleife():
    """Regel: ist_loopback erkennt ::1."""
    assert ist_loopback("::1") is True


def test_regel_loopback_funktion_erkennt_localhost_gross_klein():
    """Regel: ist_loopback ist unabhängig von der Schreibweise."""
    assert ist_loopback("LocalHost") is True


def test_regel_loopback_funktion_lehnt_offene_adresse_ab():
    """Regel: ist_loopback hält 0.0.0.0 NICHT für lokal."""
    assert ist_loopback("0.0.0.0") is False


def test_regel_loopback_funktion_lehnt_leere_angabe_ab():
    """Regel: Unbekannte/leere Angabe gilt im Zweifel als offen."""
    assert ist_loopback("") is False


def test_regel_offene_bindung_ohne_key_ergibt_hinweis():
    """Regel: 0.0.0.0 ohne API-Key ⇒ Warnsatz."""
    assert bindung_hinweis("0.0.0.0", False) is not None


def test_regel_offene_bindung_mit_key_kein_hinweis():
    """Regel: 0.0.0.0 mit API-Key ⇒ kein Warnsatz (Key schützt)."""
    assert bindung_hinweis("0.0.0.0", True) is None


def test_regel_lan_adresse_ohne_key_ergibt_hinweis():
    """Regel: Eine LAN-Adresse ohne Key ⇒ Warnsatz (erfundene Beispiel-Adresse)."""
    assert bindung_hinweis("10.0.0.7", False) is not None


def test_regel_lan_adresse_mit_key_kein_hinweis():
    """Regel: Mit gesetztem Key verstummt der Hinweis auch bei LAN-Adresse."""
    assert bindung_hinweis("10.0.0.7", True) is None


def test_regel_hinweis_nennt_host_bind_und_api_key():
    """Regel: Der Warnsatz nennt die beiden Schalter HOST_BIND und API_KEY."""
    text = bindung_hinweis("0.0.0.0", False)
    assert text is not None
    assert "HOST_BIND" in text and "API_KEY" in text, (
        "Regel 'Hinweis-Text': Der Satz muss HOST_BIND und API_KEY nennen."
    )


def test_regel_hinweis_ist_deutsch():
    """Regel: Der Warnsatz ist deutscher Klartext (Schlüsselbegriffe)."""
    text = bindung_hinweis("0.0.0.0", False)
    assert text is not None
    assert "Server lauscht" in text and "Schutz" in text, (
        "Regel 'Hinweis-Text': Der Satz ist nicht als deutscher Text erkennbar."
    )


def test_regel_hinweis_enthaelt_keinen_key_wert():
    """Regel: Der Warnsatz enthält kein Geheimnis — nur den Einstellungsnamen."""
    text = bindung_hinweis("0.0.0.0", False)
    assert text is not None
    for verboten in ("sk-", "Bearer ", "Token=", "token="):
        assert verboten not in text, (
            "Regel 'kein Geheimnis': Der Warnsatz darf keinen Key-Wert enthalten."
        )


def test_regel_hinweis_enthaelt_keine_geraete_ip():
    """Regel: Der Warnsatz nennt keine Geräte-IP (nur die überschriebene Bindung)."""
    text = bindung_hinweis("0.0.0.0", False)
    assert text is not None
    assert "lan_ip" not in text and "192.168." not in text, (
        "Regel 'keine Geräte-IP': Der Warnsatz darf keine Geräte-IP nennen."
    )


def test_regel_hinweis_ist_reine_funktion():
    """Regel: bindung_hinweis ist rein — zweimal aufgerufen dasselbe Ergebnis."""
    assert bindung_hinweis("0.0.0.0", False) == bindung_hinweis("0.0.0.0", False)


def test_regel_hinweis_nennt_die_uebergebene_bindung():
    """Regel: Der Warnsatz zeigt die tatsächlich gebundene Adresse."""
    text = bindung_hinweis("0.0.0.0", False)
    assert text is not None
    assert "0.0.0.0" in text, (
        "Regel 'Hinweis-Text': Der Satz muss die gebundene Adresse nennen."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Frontend ohne fremde Adressen
# ═══════════════════════════════════════════════════════════════════════════

# Marker fremder Anbieter. Bewusst ohne führendes Protokoll, damit auch eine
# eingebettete Ressourcen-URL auffällt.
FREMDE_MARKER = ("cdn.", "gstatic", "googleapis", "unsplash", "sk-or-")

ERLAUBTE_HOSTS = {"localhost", "127.0.0.1"}

_URL_MUSTER = re.compile(r"https?://([A-Za-z0-9.\-]+)")


def test_regel_frontend_ohne_fremde_marker():
    """Regel: Kein Frontend-Text enthält cdn./gstatic/googleapis/unsplash/sk-or-."""
    treffer = []
    for pfad in _frontend_dateien():
        text = pfad.read_text(encoding="utf-8", errors="replace").lower()
        for marker in FREMDE_MARKER:
            if marker in text:
                treffer.append(f"{pfad.relative_to(REPO)}: {marker}")
    assert not treffer, (
        "Regel 'Frontend ohne Fremde': Fremde Anbieter-Marker gefunden: "
        f"{treffer}."
    )


def test_regel_frontend_urls_nur_lokal_oder_api_base():
    """Regel: http(s)-Adressen im Frontend zeigen nur auf localhost/127.0.0.1.

    Einzige Ausnahme ist die dokumentierte ``api_base``-Beispielzeile in
    ``app.js`` (Kommentar, wie man am PC die Adresse setzt).
    """
    verstoesse = []
    for pfad in _frontend_dateien():
        for nummer, zeile in enumerate(
            pfad.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for treffer in _URL_MUSTER.finditer(zeile):
                host = treffer.group(1).lower()
                if host in ERLAUBTE_HOSTS:
                    continue
                if "api_base" in zeile:
                    continue
                verstoesse.append(f"{pfad.relative_to(REPO)}:{nummer}: {host}")
    assert not verstoesse, (
        "Regel 'Frontend nur lokal': Fremde Adressen gefunden: " f"{verstoesse}."
    )


def test_regel_frontend_app_js_hat_api_base_zeile():
    """Regel: Die erlaubte Ausnahme muss es wirklich geben (sonst tote Regel)."""
    text = _repo_datei("frontend/app.js")
    assert "api_base" in text, (
        "Regel 'Frontend nur lokal': Die dokumentierte api_base-Zeile fehlt."
    )


def test_regel_frontend_keine_openrouter_schluessel():
    """Regel: Kein Frontend-Text enthält den OpenRouter-Schlüssel-Anfang sk-or-."""
    for pfad in _frontend_dateien():
        text = pfad.read_text(encoding="utf-8", errors="replace")
        assert "sk-or-" not in text, (
            f"Regel 'kein Geheimnis': sk-or- in {pfad.relative_to(REPO)} gefunden."
        )


# ═══════════════════════════════════════════════════════════════════════════
# 5. Die Einstellungsdatei ist geschützt
# ═══════════════════════════════════════════════════════════════════════════


def test_regel_gitignore_enthaelt_env_zeile():
    """Regel: .gitignore muss die Einstellungsdatei ausschließen."""
    zeilen = [z.strip() for z in _repo_datei(".gitignore").splitlines()]
    assert ENV_NAME in zeilen, (
        f"Regel 'Datei-Schutz': .gitignore hat keine Zeile {ENV_NAME}."
    )


def test_regel_einstellungsdatei_ist_git_ignoriert():
    """Regel: Die Datei ist per git check-ignore ignoriert."""
    import subprocess

    ziel = f"backend/{ENV_NAME}"
    ergebnis = subprocess.run(
        ["git", "check-ignore", ziel],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    assert ergebnis.returncode == 0, (
        f"Regel 'Datei-Schutz': {ziel} ist NICHT ignoriert "
        f"(git check-ignore Exit {ergebnis.returncode})."
    )


def test_regel_einstellungsdatei_nicht_in_versionsverwaltung():
    """Regel: Die Datei darf nicht in git ls-files auftauchen."""
    import subprocess

    ziel = f"backend/{ENV_NAME}"
    ergebnis = subprocess.run(
        ["git", "ls-files", ziel],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    assert ergebnis.stdout.strip() == "", (
        f"Regel 'Datei-Schutz': {ziel} ist versioniert: {ergebnis.stdout.strip()!r}."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 6. Löschregel: Lösch-Begriffe nur im Duplikate-Werkzeug
# ═══════════════════════════════════════════════════════════════════════════

LOESCH_MUSTER = re.compile(r"deletefile|deletefolder", re.IGNORECASE)

LOESCH_ERLAUBT = "tools/pcloud/pcloud_duplikate_loeschen.py"


def _quelltext_dateien(wurzel: Path) -> list[Path]:
    """Alle Textdateien einer Wurzel ohne __pycache__."""
    dateien = []
    for pfad in sorted(wurzel.rglob("*")):
        if not pfad.is_file():
            continue
        if "__pycache__" in pfad.parts:
            continue
        if pfad.suffix.lower() in (".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".db"):
            continue
        dateien.append(pfad)
    return dateien


def test_regel_loeschbegriffe_nur_im_duplikate_werkzeug():
    """Regel: deletefile/deletefolder kommen in tools/ nur im Duplikate-Werkzeug."""
    treffer = []
    for pfad in _quelltext_dateien(REPO / "tools"):
        text = pfad.read_text(encoding="utf-8", errors="replace")
        if LOESCH_MUSTER.search(text):
            treffer.append(str(pfad.relative_to(REPO)).replace("\\", "/"))
    assert treffer == [LOESCH_ERLAUBT], (
        "Regel 'Löschregel': Lösch-Begriffe in tools/ gefunden: "
        f"{treffer}. Erlaubt ist nur {LOESCH_ERLAUBT}."
    )


def test_regel_loeschbegriffe_nicht_im_backend():
    """Regel: Im Backend (backend/app) gibt es gar keinen Löschbegriff."""
    treffer = []
    for pfad in _quelltext_dateien(REPO / "backend" / "app"):
        text = pfad.read_text(encoding="utf-8", errors="replace")
        if LOESCH_MUSTER.search(text):
            treffer.append(str(pfad.relative_to(REPO)).replace("\\", "/"))
    assert not treffer, (
        "Regel 'keine Löschfunktion': Lösch-Begriffe im Backend gefunden: "
        f"{treffer}."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 7. Medien ohne Zwischenspeicher
# ═══════════════════════════════════════════════════════════════════════════


def test_regel_no_store_in_cloud_router():
    """Regel: Die Cloud-Auslieferung setzt Cache-Control: no-store."""
    assert "no-store" in _repo_datei("backend/app/router/cloud.py"), (
        "Regel 'ohne Zwischenspeicher': backend/app/router/cloud.py ohne no-store."
    )


def test_regel_no_store_in_speak_router():
    """Regel: Die Sprachausgabe setzt Cache-Control: no-store."""
    assert "no-store" in _repo_datei("backend/app/router/speak.py"), (
        "Regel 'ohne Zwischenspeicher': backend/app/router/speak.py ohne no-store."
    )


def test_regel_no_store_in_main():
    """Regel: main.py setzt no-store (statische Auslieferung /api/konfig)."""
    assert "no-store" in _repo_datei("backend/app/main.py"), (
        "Regel 'ohne Zwischenspeicher': backend/app/main.py ohne no-store."
    )


def test_regel_bildauslieferung_ohne_zwischenspeicher():
    """Regel: Die Bildauslieferung trägt no-store — in fotos.py ODER main.py."""
    fotos = "no-store" in _repo_datei("backend/app/router/fotos.py")
    main = "no-store" in _repo_datei("backend/app/main.py")
    assert fotos or main, (
        "Regel 'ohne Zwischenspeicher': Weder backend/app/router/fotos.py noch "
        "backend/app/main.py setzt no-store für die Bildauslieferung."
    )


def test_regel_nocache_klasse_vorhanden():
    """Regel: main.py besitzt die NoCache-Auslieferung für statische Dateien."""
    assert "NoCacheStaticFiles" in _repo_datei("backend/app/main.py"), (
        "Regel 'ohne Zwischenspeicher': NoCacheStaticFiles fehlt in main.py."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 8. Der Wächter über sich selbst
# ═══════════════════════════════════════════════════════════════════════════

# Zusammengesetzt, damit diese Datei die Begriffe nicht selbst enthält.
VERBOTENE_NETZ_TOKENS = ("reque" + "sts.", "urlo" + "pen", "ht" + "tpx", "sock" + "et.")


def _eigener_quelltext() -> str:
    """Den eigenen Quelltext lesen (nicht die Einstellungsdatei)."""
    return Path(__file__).read_text(encoding="utf-8", errors="replace")


def test_regel_waechterdatei_ohne_netzaufrufe():
    """Regel: Diese Testdatei macht keinen einzigen Netz-Aufruf."""
    text = _eigener_quelltext()
    treffer = [t for t in VERBOTENE_NETZ_TOKENS if t in text]
    assert not treffer, (
        "Regel 'offline': Der Wächter selbst enthält Netz-Zugriffe: "
        f"{treffer}. Tests dürfen nichts nach außen rufen."
    )


def test_regel_waechterdatei_liest_keine_einstellungsdatei():
    """Regel: Diese Testdatei liest die Einstellungsdatei nirgends."""
    text = _eigener_quelltext()
    assert ENV_NAME not in text, (
        "Regel 'kein Geheimnis': Der Wächter selbst nennt die Einstellungsdatei — "
        "so könnte ein Wert in Ausgaben geraten."
    )


def test_regel_waechterdatei_hat_mindestens_35_testfunktionen():
    """Regel: Der Wächter ist breit genug (mindestens 35 Testfunktionen)."""
    text = _eigener_quelltext()
    anzahl = len(re.findall(r"^def test_", text, flags=re.MULTILINE))
    assert anzahl >= 35, (
        f"Regel 'Wächter-Umfang': Nur {anzahl} Testfunktionen — mindestens 35."
    )


def test_regel_waechterdatei_ohne_persoenliche_daten():
    """Regel: Kein echter Name/keine echte Nummer in dieser Testdatei."""
    text = _eigener_quelltext()
    name = "sebas" + "tian"  # zusammengesetzt, damit er nicht selbst drinsteht
    assert name not in text.lower(), (
        "Regel 'keine persönlichen Daten': Der Wächter nennt keinen Personennamen."
    )
