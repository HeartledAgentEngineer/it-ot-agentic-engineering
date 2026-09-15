"""Tests: automatisches Aufräumen liegengebliebener tmux-Jobsessions.

Wunsch Sebastian (15.09.2026): Beim Start/Serverstart sollen tote, in Termux
rot durchgestrichene Job-Sessions von selbst verschwinden — nicht mehr einzeln
manuell geschlossen werden müssen.

Wichtig: Fremde Sessions (z. B. eine interaktive Session des Nutzers) und die
persistenten Andock-Ziele (hermes / hermes_code / konfigurierte Session) werden
NIE angefasst.
"""
import os
import sys
from unittest import mock

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import hermes_local  # noqa: E402


def test_soll_beendet_werden_nur_job_muster():
    """Nur eigene Job-Sessions ('hermes_agent_…') gelten als aufräumbar."""
    assert hermes_local._soll_beendet_werden("hermes_agent_1700000000000_1") is True
    # Fremde/persistente Sessions bleiben unberührt:
    assert hermes_local._soll_beendet_werden("hermes") is False
    assert hermes_local._soll_beendet_werden("hermes_code") is False
    assert hermes_local._soll_beendet_werden("meine_session") is False
    assert hermes_local._soll_beendet_werden("") is False


def test_geschuetzte_session_wird_nicht_beendet():
    """Auch eine Job-Session bleibt geschützt, wenn sie explizit geschützt ist."""
    assert hermes_local._soll_beendet_werden(
        "hermes_agent_123_1", {"hermes_agent_123_1"}
    ) is False


def test_aufraeumen_killt_nur_job_sessions():
    """Der Lauf beendet Job-Sessions und lässt alles andere stehen."""
    sessions = ["hermes_agent_1_1", "hermes", "hermes_code", "hermes_agent_2_3"]
    gekillt = []

    def _fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = "\n".join(sessions) if "list-sessions" in cmd else ""
        if "kill-session" in cmd:
            gekillt.append(cmd[cmd.index("-t") + 1])
        return R()

    with mock.patch.object(hermes_local, "ist_verfuegbar", return_value=True), \
         mock.patch.object(hermes_local.subprocess, "run", side_effect=_fake_run), \
         mock.patch("app.config.settings") as s:
        s.hermes_local_session = "hermes"
        anzahl = hermes_local.raeume_alte_job_sessions_auf()

    assert anzahl == 2
    assert sorted(gekillt) == ["hermes_agent_1_1", "hermes_agent_2_3"]


def test_aufraeumen_ohne_tmux_ist_harmlos():
    """Fehlt tmux (z. B. PC), passiert nichts und es kracht nicht."""
    with mock.patch.object(hermes_local, "ist_verfuegbar", return_value=False):
        assert hermes_local.raeume_alte_job_sessions_auf() == 0
