"""Kontext-Bau für den Ein-Chat (Rolling-Summary + relevante Erinnerungen).

Strategie (nach Brainstorm + grillAnAgent, Option C Hybrid):
  1. Die letzten `LETZTE_ANZAHL` Nachrichten bleiben vollständig.
  2. Alles Ältere wird zu einem kompakten `summary` gerollt (einmal, selten).
  3. Relevante Erinnerungen werden ergänzt (semantisch zur Frage), wenn ein
     Embedding-Extraktor verfügbar ist; sonst Fallback ohne Erinnerungen.
  4. Zeitersparnis: `summary` nur neu gerollt, wenn seit dem letzten Roll
     >= ROLL_INTERVALL neue Nachrichten dazukamen (Rate-Limit → günstig).

Das Ergebnis ist ein kompakter Prompt-Kontext (Token-Budget ~KONTEXT_BUDGET),
der Kontext + Wissen nutzt, ohne den Chat unbegrenzt zu explodieren.
"""

from typing import Any, Callable, Dict, List, Optional

# Wie viele der neuesten Nachrichten immer vollständig mitgeschickt werden.
LETZTE_ANZAHL = 15
# Ab dieser Nachrichten-Anzahl wird gerollt (ältere → Summary).
ROLL_AB = 60
# Nach wie vielen neuen Nachrichten das Summary neu gerollt wird (Rate-Limit).
ROLL_INTERVALL = 50
# Grober Token-Budget für den gesamten Kontext-Prompt.
KONTEXT_BUDGET = 2000


def baue_kontext(
    historie: List[Dict[str, Any]],
    frage: str,
    memory_extractor: Optional[Callable[[str, int], List[Dict[str, Any]]]] = None,
    gespeichertes_summary: str = "",
    anzahl_seit_roll: int = 0,
) -> Dict[str, Any]:
    """Baut das Kontext-Paket für eine Conversation.

    Liefert { "kontext": str, "summary": str, "gerollt": bool }.
    - `kontext` ist das fertige Paket für den Prompt.
    - `summary` ist der neu erzeugte Rolling-Summary (falls gerollt), den der
      Aufrufer persistieren soll.
    - `gerollt` = True, wenn ein neuer Summary erzeugt wurde.
    """
    if not historie:
        return {"kontext": "", "summary": gespeichertes_summary, "gerollt": False}

    # 1) Kürzlichste zuletzt, ältere = davor.
    letzte = historie[-LETZTE_ANZAHL:]
    aeltere = historie[:-LETZTE_ANZAHL]

    # 2) Rolling-Summary: nur wenn genug Alt-Nachrichten + seit letztem Roll
    #    genug neue dazukamen (Rate-Limit spart Geld).
    summary = gespeichertes_summary or ""
    gerollt = False
    if len(historie) > ROLL_AB and anzahl_seit_roll >= ROLL_INTERVALL:
        # Kompakter Überblick der älteren Teile (wer/ was besprochen wurde).
        zeilen = []
        for m in aeltere[-60:]:  # höchstens die letzten 60 der älteren
            rolle = m.get("role", "?")
            inhalt = (m.get("content") or "").strip()
            if not inhalt:
                continue
            if len(inhalt) > 200:
                inhalt = inhalt[:200] + "…"
            zeilen.append(f"{rolle}: {inhalt}")
        if zeilen:
            # Bewusst deterministisch (verkürzter Verlauf statt LLM-Zusammen-
            # fassung im MVP): preiswert, kein Halluzinations-Risiko. Ein
            # echter verdichteter Summary kann später ergänzt werden.
            summary = (
                "[Zusammenfassung der älteren Unterhaltung:]\\n"
                + "\\n".join(zeilen[-40:])
            )
            gerollt = True

    # 3) Baue das Paket: [Summary falls vorhanden] + [letzte] + [Erinnerungen].
    teile: List[str] = []
    if summary:
        teile.append(summary)
    if letzte:
        teile.append("[Aktueller Verlauf:]")
        for m in letzte:
            rolle = m.get("role", "?")
            inhalt = (m.get("content") or "").strip()
            if inhalt:
                teile.append(f"{rolle}: {inhalt[:500]}")
    # 4) Relevante Erinnerungen (semantisch) — mit Fallback.
    if memory_extractor is not None:
        try:
            erinnerungen = memory_extractor(frage, 5) or []
            for e in erinnerungen:
                inhalt = (e.get("content") or e.get("text") or "").strip()
                if inhalt and len(inhalt) < 400:
                    teile.append(f"Erinnerung: {inhalt}")
        except Exception:
            pass  # Erinnerungen sind Bonus — nie die Anfrage deswegen brechen.

    kontext = "\\n".join(teile)
    # Grobes Token-Budget: einfache Abschätzung (~4 Zeichen/Token), kappen.
    max_zeichen = KONTEXT_BUDGET * 4
    if len(kontext) > max_zeichen:
        kontext = kontext[-max_zeichen:]

    return {"kontext": kontext, "summary": summary, "gerollt": gerollt}
