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
