"""Kosten-, Token- und Delegations-Schutz („Hamster-Einstellungen“) für OrbitDesk.

Schützt vor unkontrollierten API-Kosten und Token-Explosionen (wie 150 € in 2 Tagen durch
Volltext-Scans auf GPT-6 Sol). Erzwingt Delegation von Dokumenten-Scans und Routineprüfungen
an günstige Worker-Modelle (GPT-6 Luna, DeepSeek V4.1 Flash, Gemini Flash).

Verwaltet Budgetgrenzen je Projekt und Auftrag mit transparenter Kostenrechnung.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from . import paare, signale


class BudgetFehler(Exception):
    """Budget überschritten oder ungültige Konfiguration."""


class DelegationsPflichtFehler(BudgetFehler):
    """Verletzung der Delegationsregel für teure Modelle bei Routine-Scans."""


# Modellpreise in USD pro 1.000.000 Tokens (Input / Output / Zwischen-Tokens)
# Stand 2026 für Azure Foundry, OpenRouter und Anthropic/OpenAI
MODELL_PREISE: dict[str, dict[str, float]] = {
    # Teure Thinker-Modelle (nur für Synthese, Review und gezielte Planung)
    "gpt-6-sol": {"input": 10.00, "output": 30.00, "zwischen": 15.00, "teuer": 1.0},
    "gpt-6.1-sol": {"input": 12.00, "output": 36.00, "zwischen": 18.00, "teuer": 1.0},
    "claude-opus-5.5": {"input": 15.00, "output": 75.00, "zwischen": 37.50, "teuer": 1.0},
    "claude-3-opus": {"input": 15.00, "output": 75.00, "zwischen": 37.50, "teuer": 1.0},
    
    # Günstige Worker / Delegations-Modelle (für Durchsuchungen, Scans, Routine)
    "gpt-6-luna": {"input": 0.50, "output": 1.50, "zwischen": 0.75, "teuer": 0.0},
    "deepseek-v4.1-flash": {"input": 0.14, "output": 0.28, "zwischen": 0.14, "teuer": 0.0},
    "deepseek-chat": {"input": 0.14, "output": 0.28, "zwischen": 0.14, "teuer": 0.0},
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30, "zwischen": 0.075, "teuer": 0.0},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "zwischen": 0.075, "teuer": 0.0},
    
    # Standard-Coding Worker
    "claude-sonnet-5.5": {"input": 3.00, "output": 15.00, "zwischen": 7.50, "teuer": 0.5},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00, "zwischen": 7.50, "teuer": 0.5},
}

STANDARD_BUDGET_USD = 10.00
STANDARD_WARNSCHWELLE_PROZENT = 80.0
TOKEN_GRENZE_FUER_TEURE_MODELLE = 15_000  # Ab 15k Input-Tokens ist Sol verboten -> Delegation an Luna/Flash!
DELEGATION_AUFGABEN = ("dokumenten_scan", "datei_durchsuchung", "routine_pruefung", "grosser_code_scan")


@dataclass(frozen=True)
class KostenEintrag:
    zeit: str
    thema: str
    auftrag_id: str
    modell: str
    input_tokens: int
    output_tokens: int
    zwischen_tokens: int
    kosten_usd: float

    def als_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BudgetStatus:
    thema: str
    budget_limit_usd: float
    verbraucht_usd: float
    verbleibend_usd: float
    warnung_aktiv: bool
    stopp_aktiv: bool
    gesamte_input_tokens: int
    gesamte_output_tokens: int
    gesamte_zwischen_tokens: int
    letzte_aktualisierung: str

    def als_dict(self) -> dict:
        return asdict(self)


def kosten_ordner(basis: Path | None = None) -> Path:
    ordner = (basis or signale.daten_ordner()) / "kosten"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def kosten_datei(thema: str, basis: Path | None = None) -> Path:
    paare.thema_pruefen(thema)
    return kosten_ordner(basis) / f"{thema}.json"


def berechne_kosten_usd(modell: str, input_tokens: int, output_tokens: int, zwischen_tokens: int = 0) -> float:
    """Berechnet die Kosten in USD anhand der Modell-Preistabelle."""
    modell_key = modell.lower().strip()
    # Präfix-Matching für Versionsvarianten
    preise = None
    for k, v in MODELL_PREISE.items():
        if k in modell_key:
            preise = v
            break
    if preise is None:
        # Konservative Standardannahme (Sonnet-Niveau)
        preise = {"input": 3.00, "output": 15.00, "zwischen": 7.50}

    kosten = (
        (input_tokens / 1_000_000) * preise["input"]
        + (output_tokens / 1_000_000) * preise["output"]
        + (zwischen_tokens / 1_000_000) * preise["zwischen"]
    )
    return round(kosten, 6)


def pruefe_delegationspflicht(modell: str, aufgabe_art: str = "", geschaetzte_input_tokens: int = 0) -> None:
    """Prüft, ob für eine Aufgabe Delegation an günstige Modelle zwingend ist.

    Verhindert, dass GPT-6 Sol oder Claude Opus für Massenscans und Routineprüfungen eingesetzt werden.
    """
    modell_key = modell.lower().strip()
    ist_teuer = any(k in modell_key for k, v in MODELL_PREISE.items() if v.get("teuer", 0.0) >= 1.0)
    
    if not ist_teuer:
        return

    grund = None
    if aufgabe_art.lower().strip() in DELEGATION_AUFGABEN:
        grund = f"Aufgabenart '{aufgabe_art}' ist als Routine-/Massenscan eingestuft"
    elif geschaetzte_input_tokens > TOKEN_GRENZE_FUER_TEURE_MODELLE:
        grund = f"Geschätzte Tokenmenge ({geschaetzte_input_tokens}) übersteigt Grenze ({TOKEN_GRENZE_FUER_TEURE_MODELLE})"

    if grund is not None:
        raise DelegationsPflichtFehler(
            f"Delegationspflicht verletzt: {grund}. Modell '{modell}' gesperrt. "
            f"Zwingende Delegation an günstige Modelle (gpt-6-luna, deepseek-v4.1-flash, gemini-flash) erforderlich."
        )


def budget_status_lesen(thema: str, basis: Path | None = None) -> BudgetStatus:
    """Liest den aktuellen Budget- und Verbrauchsstatus für ein Thema."""
    pfad = kosten_datei(thema, basis)
    if not pfad.is_file():
        return BudgetStatus(
            thema=thema,
            budget_limit_usd=STANDARD_BUDGET_USD,
            verbraucht_usd=0.0,
            verbleibend_usd=STANDARD_BUDGET_USD,
            warnung_aktiv=False,
            stopp_aktiv=False,
            gesamte_input_tokens=0,
            gesamte_output_tokens=0,
            gesamte_zwischen_tokens=0,
            letzte_aktualisierung=datetime.now(timezone.utc).isoformat(),
        )
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        limit = float(daten.get("budget_limit_usd", STANDARD_BUDGET_USD))
        verbraucht = float(daten.get("verbraucht_usd", 0.0))
        verbleibend = max(0.0, limit - verbraucht)
        warnschwelle = float(daten.get("warnschwelle_prozent", STANDARD_WARNSCHWELLE_PROZENT))
        warnung = (verbraucht / limit * 100.0) >= warnschwelle if limit > 0 else True
        stopp = verbraucht >= limit if limit > 0 else True
        return BudgetStatus(
            thema=thema,
            budget_limit_usd=limit,
            verbraucht_usd=verbraucht,
            verbleibend_usd=verbleibend,
            warnung_aktiv=warnung,
            stopp_aktiv=stopp,
            gesamte_input_tokens=int(daten.get("gesamte_input_tokens", 0)),
            gesamte_output_tokens=int(daten.get("gesamte_output_tokens", 0)),
            gesamte_zwischen_tokens=int(daten.get("gesamte_zwischen_tokens", 0)),
            letzte_aktualisierung=str(daten.get("letzte_aktualisierung", "")),
        )
    except (OSError, ValueError):
        return BudgetStatus(
            thema=thema,
            budget_limit_usd=STANDARD_BUDGET_USD,
            verbraucht_usd=0.0,
            verbleibend_usd=STANDARD_BUDGET_USD,
            warnung_aktiv=False,
            stopp_aktiv=False,
            gesamte_input_tokens=0,
            gesamte_output_tokens=0,
            gesamte_zwischen_tokens=0,
            letzte_aktualisierung=datetime.now(timezone.utc).isoformat(),
        )


def budget_limit_setzen(
    thema: str, limit_usd: float, warnschwelle_prozent: float = STANDARD_WARNSCHWELLE_PROZENT, basis: Path | None = None
) -> BudgetStatus:
    """Konfiguriert die Budgetgrenze für ein Thema."""
    if limit_usd <= 0:
        raise BudgetFehler("Budget-Limit muss > 0 sein")
    pfad = kosten_datei(thema, basis)
    alt = budget_status_lesen(thema, basis)
    jetzt = datetime.now(timezone.utc).isoformat()
    neue_daten = {
        "thema": thema,
        "budget_limit_usd": limit_usd,
        "warnschwelle_prozent": warnschwelle_prozent,
        "verbraucht_usd": alt.verbraucht_usd,
        "gesamte_input_tokens": alt.gesamte_input_tokens,
        "gesamte_output_tokens": alt.gesamte_output_tokens,
        "gesamte_zwischen_tokens": alt.gesamte_zwischen_tokens,
        "letzte_aktualisierung": jetzt,
    }
    signale._atomar_schreiben(pfad, json.dumps(neue_daten, ensure_ascii=False, indent=2))
    return budget_status_lesen(thema, basis)


def verbrauch_buchen(
    thema: str,
    *,
    modell: str,
    input_tokens: int,
    output_tokens: int,
    zwischen_tokens: int = 0,
    auftrag_id: str = "",
    aufgabe_art: str = "",
    basis: Path | None = None,
) -> KostenEintrag:
    """Prüft Delegationsregeln und bucht verbrauchte Tokens und Kosten auf das Budget.

    Wirft `DelegationsPflichtFehler`, wenn ein teures Modell für Routine-Scans genutzt wird.
    Wirft `BudgetFehler`, wenn das Budgetlimit erreicht ist.
    """
    pruefe_delegationspflicht(modell, aufgabe_art=aufgabe_art, geschaetzte_input_tokens=input_tokens)

    status = budget_status_lesen(thema, basis)
    kosten = berechne_kosten_usd(modell, input_tokens, output_tokens, zwischen_tokens)

    if status.verbraucht_usd + kosten > status.budget_limit_usd:
        raise BudgetFehler(
            f"Budgetgrenze für '{thema}' überschritten: {status.verbraucht_usd:.4f} $ + {kosten:.4f} $ > "
            f"Limit {status.budget_limit_usd:.2f} $. Auftrag blockiert."
        )

    jetzt = datetime.now(timezone.utc).isoformat()
    eintrag = KostenEintrag(
        zeit=jetzt,
        thema=thema,
        auftrag_id=auftrag_id or "auftrag-1",
        modell=modell,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        zwischen_tokens=zwischen_tokens,
        kosten_usd=kosten,
    )

    pfad = kosten_datei(thema, basis)
    neue_daten = {
        "thema": thema,
        "budget_limit_usd": status.budget_limit_usd,
        "verbraucht_usd": round(status.verbraucht_usd + kosten, 6),
        "gesamte_input_tokens": status.gesamte_input_tokens + input_tokens,
        "gesamte_output_tokens": status.gesamte_output_tokens + output_tokens,
        "gesamte_zwischen_tokens": status.gesamte_zwischen_tokens + zwischen_tokens,
        "letzte_aktualisierung": jetzt,
    }
    signale._atomar_schreiben(pfad, json.dumps(neue_daten, ensure_ascii=False, indent=2))

    # Journal / Protokoll
    journal_pfad = kosten_ordner(basis) / f"{thema}_historie.jsonl"
    with open(journal_pfad, "a", encoding="utf-8") as f:
        f.write(json.dumps(eintrag.als_dict(), ensure_ascii=False) + "\n")

    return eintrag


def kosten_uebersicht(thema: str | None = None, basis: Path | None = None) -> str:
    """Formatierte Textübersicht für CLI und Logs."""
    ordner = kosten_ordner(basis)
    if not ordner.is_dir():
        return "OrbitDesk Budget- & Kostenstatus: Keine Verbrauchsdaten vorhanden."

    themen_dateien = [p for p in sorted(ordner.glob("*.json")) if not p.name.endswith("_historie.json")]
    if not themen_dateien:
        return "OrbitDesk Budget- & Kostenstatus: Keine Projektdaten vorhanden."

    zeilen = ["OrbitDesk Budget- & Kostenstatus:"]
    gesamt_usd = 0.0
    for pfad in themen_dateien:
        t_name = pfad.stem
        if thema and t_name != thema:
            continue
        try:
            st = budget_status_lesen(t_name, basis)
            gesamt_usd += st.verbraucht_usd
            auslastung = (st.verbraucht_usd / st.budget_limit_usd * 100.0) if st.budget_limit_usd > 0 else 0.0
            warnung = " ⚠ BUDGET-WARNUNG!" if st.warnung_aktiv else ""
            zeilen.append(
                f"  * {st.thema}: {st.verbraucht_usd:.4f} $ / {st.budget_limit_usd:.2f} $ "
                f"({auslastung:.1f} %){warnung} | Tokens: In {st.gesamte_input_tokens:,}, Out {st.gesamte_output_tokens:,}"
            )
        except Exception:
            continue
    zeilen.append(f"Gesamtkosten: {gesamt_usd:.4f} $")
    return "\n".join(zeilen)
