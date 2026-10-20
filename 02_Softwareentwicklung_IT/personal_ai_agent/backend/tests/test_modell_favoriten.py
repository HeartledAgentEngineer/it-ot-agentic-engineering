"""
Die Schnellauswahl der Modelle (``app.config.settings.favorite_models``).

Auftrag: Sebastian, 20.10.2026 — „Modellauswahl verschlanken" (Übergabe
``personal_ai_agent``): sechs Einträge, davon drei fast gleiche Spar-Varianten,
sollen **wenige Stufen** werden (günstig / Alltag / stark).

Diese Prüfungen halten die zwei Regeln fest, die man beim nächsten Griff in die
Liste verlieren würde:

1. **Drei Stufen, keine Varianten-Sammlung.** Genau drei Einträge, keine
   Dubletten, jeder in der Form ``anbieter/modell``, und jeder war schon vorher
   in der Liste (es ist keine neue Modellwahl).
2. **Der benutzte Stand bleibt sichtbar.** Das eingestellte Modell
   (``settings.llm_model``) muss in der Schnellauswahl stehen — sonst versteckt
   die Oberfläche genau das Modell, mit dem gerade gearbeitet wird.

Kein Netz, kein Modellaufruf, **keine Preise**: die liefert live
``GET /models/user``. Die am 20.10.2026 gemessene Preistafel und die Begründung
stehen in ``docs/changelog-2026-10-20-modell-favoriten-schlank.md``.
"""

from __future__ import annotations

from pathlib import Path

from app.config import settings

BACKEND = Path(__file__).resolve().parents[1]
ROUTE = BACKEND / "app" / "router" / "llm_models.py"

# Die drei Stufen, wie am 20.10.2026 festgelegt. Ändert sich die Wahl, ändert
# sich diese Zeile — sie ist die Entscheidung, nicht eine Messung.
STUFEN = [
    "deepseek/deepseek-v4.1-flash",   # sparsam und Alltag
    "deepseek/deepseek-v4-pro",       # mehr Substanz, gleicher Anbieter
    "anthropic/claude-sonnet-5",      # stark, anderer Anbieter
]

# Was am 20.10.2026 weggefallen ist. Diese Einträge bleiben im Katalog wählbar,
# dürfen aber nicht in die Schnellauswahl zurückrutschen (sonst sind es wieder
# drei Knöpfe für dieselbe Spar-Aufgabe).
WEGGEFALLEN = [
    "openai/gpt-5-nano",
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-flash-0731",
]


def test_drei_stufen_ohne_dubletten():
    """Genau drei Einträge — und die Entscheidung ist die drei Stufen."""
    liste = settings.favorite_models
    assert len(liste) == 3, f"erwartet 3 Stufen, gefunden {len(liste)}: {liste}"
    assert len(set(liste)) == len(liste), f"doppelter Eintrag: {liste}"
    assert liste == STUFEN


def test_weggefallene_varianten_bleiben_draussen():
    """Der Doppelgänger kommt nicht zurück — auch nicht als vierter Eintrag."""
    liste = settings.favorite_models
    doppelt = [m for m in WEGGEFALLEN if m in liste]
    assert not doppelt, f"wieder in der Schnellauswahl: {doppelt}"


def test_jeder_eintrag_ist_anbieter_schraegstrich_modell():
    """Die Route und die Oberfläche erwarten ``anbieter/modell``."""
    for eintrag in settings.favorite_models:
        assert eintrag.count("/") == 1, f"kein anbieter/modell: {eintrag!r}"
        anbieter, modell = eintrag.split("/")
        assert anbieter and modell, f"leerer Teil: {eintrag!r}"
        assert " " not in eintrag, f"Leerzeichen im Modellnamen: {eintrag!r}"


def test_das_eingestellte_modell_steht_in_der_schnellauswahl():
    """Sonst versteckt die Oberfläche das Modell, mit dem gerade gearbeitet wird."""
    assert settings.llm_model in settings.favorite_models, (
        f"eingestelltes Modell {settings.llm_model!r} fehlt in der Schnellauswahl "
        f"{settings.favorite_models}"
    )


def test_route_liefert_die_schnellauswahl_unveraendert():
    """Die Verdrahtung: die Route nimmt genau diese Einstellung, keine zweite Liste."""
    quelle = ROUTE.read_text(encoding="utf-8")
    assert '"favoriten": settings.favorite_models' in quelle, (
        "die Route /api/models liefert die Schnellauswahl nicht mehr aus "
        "settings.favorite_models"
    )
    # Keine zweite Wahrheit: die Liste darf nur an einer Stelle im Backend stehen.
    treffer = [
        p
        for p in (BACKEND / "app").rglob("*.py")
        if "favorite_models: List[str]" in p.read_text(encoding="utf-8")
    ]
    assert treffer == [BACKEND / "app" / "config.py"], f"zweite Liste in: {treffer}"
