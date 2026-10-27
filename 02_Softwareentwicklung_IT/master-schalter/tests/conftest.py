"""Gemeinsame Hilfen für die Tests des Wechselassistenten (synthetisches Thema, Repo und Datenordner)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from master_schalter import assistent_vorgaenge, besitz, modi, paare, zustand

THEMA = "engineering"
THREAD = "00000000-0000-4000-8000-0000000000a1"


class Umgebung:
    """Datenordner und Repo unter `tmp_path`; echte Daten unter `%USERPROFILE%` werden nie berührt."""

    thema = THEMA

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.daten = tmp_path / "daten"
        self.daten.mkdir()
        monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(self.daten))
        self.repo = tmp_path / "repo"
        (self.repo / ".git").mkdir(parents=True)
        monkeypatch.setenv("MASTER_SCHALTER_REPO", str(self.repo))
        paare.setzen(THEMA, THREAD, paare.laufend_bilden(THEMA), aktiv=True)

    def master_datei(self, thema: str = THEMA) -> Path:
        return besitz.pfad(self.repo, paare.laufend_bilden(thema))

    def marke(self, thema: str = THEMA) -> str:
        return besitz.lesen(self.master_datei(thema))

    def marke_setzen(self, text: str, thema: str = THEMA) -> None:
        besitz.schreiben(self.master_datei(thema), text)

    def vorbereiten(self, vorgang_id: str, ziel: str = "hermes", von: str = "claude",
                    phase: str = "vorbereitet", thema: str = THEMA) -> assistent_vorgaenge.Vorgang:
        """Vorgang wie vor dem Wechsel vermerken (Vorzustand = aktuelles Profil und wörtliche Marke)."""
        profil = modi.profil(thema)
        vorgang = assistent_vorgaenge.Vorgang(
            vorgang_id, thema, ziel, von, phase, datetime.now(timezone.utc).isoformat(),
            {"master": profil.master, "worker": profil.worker, "modell": profil.modell},
            self.marke(thema))
        assistent_vorgaenge.aendern(lambda alt: [*alt, vorgang])
        return vorgang

    def uebergeben(self, vorgang_id: str, ziel: str = "hermes", thema: str = THEMA) -> modi.Profil:
        """Rolle wie der Assistent setzen: Themensperre halten, dann die gesperrte Kapsel aufrufen."""
        with zustand.thema_sperre(thema, blockierend=True, frist=1.0) as frei:
            assert frei
            return modi.master_uebergeben_gesperrt(thema, ziel, vorgang_id=vorgang_id, repo=self.repo)


@pytest.fixture
def umgebung(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Umgebung:
    return Umgebung(tmp_path, monkeypatch)


@pytest.fixture(autouse=True)
def _keine_echten_chatquellen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Das Chat-Register liest in KEINEM Test echte Quellen: alle vier Pfade zeigen auf Nichtvorhandenes."""
    leer = tmp_path / "keine-chatquellen"
    monkeypatch.setenv("MASTER_SCHALTER_CLAUDE_DESKTOP", str(leer / "claude-data"))
    monkeypatch.setenv("MASTER_SCHALTER_CLAUDE_PROJEKTE", str(leer / "claude-projects"))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_STATE", str(leer / "codex.sqlite"))
    monkeypatch.setenv("MASTER_SCHALTER_HERMES_STATE", str(leer / "hermes.db"))
    monkeypatch.delenv("HERMES_HOME", raising=False)


@pytest.fixture(autouse=True)
def _kein_echtes_codex_und_keine_echten_daten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kein Test startet je ein echtes `codex.exe` oder liest den echten Datenordner (`~/.master-schalter`)
    bzw. die echten Codex-Sitzungen (`~/.codex`).

    Beides zeigt auf Nichtvorhandenes unter `tmp_path`; Tests, die etwas Eigenes brauchen, setzen es selbst neu.
    """
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "keine-echten-daten"))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX", str(tmp_path / "kein-codex" / "codex.exe"))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_SESSIONS", str(tmp_path / "keine-codex-sitzungen"))
