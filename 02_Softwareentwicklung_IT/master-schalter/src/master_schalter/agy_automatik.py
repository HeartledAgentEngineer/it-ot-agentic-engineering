"""Automatische Übergabe Codex → Antigravity (`agy`) bei Codex-Limit samt Chat-Neuanlage.

Erreicht Codex sein Nutzungslimit (`5h` oder `Woche` ≥ Schwelle bei frischer Messung), während Claude
ebenfalls nicht frei ist (z. B. im Wochenlimit), können aktive Themen, die aktuell von Codex als Master
geführt werden (`<thema>.master` hat Besitzer `codex` und `profil.master` ist `kontingent` oder `codex`),
nicht mehr von Codex weiterbearbeitet werden.

Ablauf je fälligem Thema (`lauf`):
1. Prüfen, ob in `zuordnung.json` bereits ein bestätigtes Antigravity-Gespräch (`agy:<kennung>`) für das
   Thema hinterlegt ist.
2. Falls noch kein Antigravity-Gespräch zugeordnet ist, legt `agy_senden.neues_gespraech(thema, laufend)`
   über `language_server.exe agentapi new-conversation` automatisch ein neues Gespräch in Antigravity mit
   dem Titel `Thema: <thema>` an und speichert die Zuordnung (`chat_zuordnung.bestaetigen`).
3. Danach wird die Auslösekennung `<thema>@codex:<reset>` dauerhaft in `automatik_ausgeloest.json`
   vermerkt (höchstens ein automatischer Wechsel je Thema und Codex-Limitfenster) und die Übergabe über
   `assistent.uebergeben(thema, "agy", von_chat=None, nach_chat=ChatRef("agy", kennung), repo=repo)`
   ausgeführt.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import (agy_senden, anzeige, assistent, assistent_vorgaenge as av, automatik, besitz,
               chat_zuordnung, modi, paare, protokoll, rollen, signale, uebergabe)


def codex_im_limit(codex: signale.Kontingent, schwelle: int,
                   jetzt: datetime) -> tuple[bool, signale.Fenster | None]:
    """`(im Limit?, auslösendes Fenster)` für Codex bei frischer Messung."""
    if codex.fehler or not automatik._messung_frisch(codex.stand, jetzt):
        return False, None
    fuenf = automatik._gueltiges_fenster(codex.fenster_nach_name("5h"), jetzt)
    woche = automatik._gueltiges_fenster(codex.fenster_nach_name("Woche"), jetzt)
    if fuenf is not None and fuenf.prozent >= schwelle:
        return True, fuenf
    if woche is not None and woche.prozent >= schwelle:
        return True, woche
    return False, None


def claude_nicht_frei(claude: signale.Kontingent, schwelle: int, jetzt: datetime) -> bool:
    """`True`, wenn Claude im Limit ist oder keine frische freie Messung vorliegt."""
    zustand_claude, _ = rollen._bewerten(claude, schwelle)
    if zustand_claude == rollen.LIMIT:
        return True
    if not automatik._messung_frisch(claude.stand, jetzt):
        return True
    return zustand_claude != rollen.FREI


def agy_chat_fuer_thema(thema: str, zuordnung: Mapping[str, str] | None = None) -> str | None:
    """Bestätigte Antigravity-Sitzungskennung für `thema` aus `zuordnung.json`, sonst `None`."""
    daten = chat_zuordnung.zuordnung_lesen() if zuordnung is None else zuordnung
    for schluessel, zugeordnet in sorted(daten.items()):
        werkzeug, _, kennung = schluessel.partition(":")
        if werkzeug == "agy" and zugeordnet == thema and kennung:
            return kennung
    return None


def faellige_themen(paare_liste: list[paare.Paar], messung: automatik.Messung, schwelle: int, an: bool,
                    jetzt: datetime, *, repo: Path,
                    modus_mapping: Mapping[str, modi.Profil | str] | None = None,
                    ausgeloest: Collection[str] = (),
                    offene_themen: Collection[str] = ()) -> list[tuple[paare.Paar, str]]:
    """Reine Entscheidung: welche aktiven Codex-Themen jetzt an Antigravity (`agy`) übergeben werden."""
    if not an:
        return []
    im_limit, ausloeser = codex_im_limit(messung.codex, schwelle, jetzt)
    if not im_limit or ausloeser is None or ausloeser.reset is None:
        return []
    if not claude_nicht_frei(messung.claude, schwelle, jetzt):
        return []
    modus_mapping = modus_mapping or {}
    bekannt = set(ausgeloest)
    offen = set(offene_themen)
    ergebnis: list[tuple[paare.Paar, str]] = []
    for paar in paare_liste:
        if not paar.aktiv or paar.thema in offen:
            continue
        profil = modi.als_profil(modus_mapping.get(paar.thema, modi.KONTINGENT))
        if profil.master not in (modi.KONTINGENT, "codex"):
            continue
        marke = besitz.lesen(besitz.pfad(repo, paar.laufend))
        if modi.ist_zwischenmarke(marke, paar.thema) or besitz.besitzer(marke) != besitz.CODEX:
            continue
        kennung = f"{paar.thema}@codex:{int(ausloeser.reset.timestamp())}"
        if kennung in bekannt:
            continue
        ergebnis.append((paar, kennung))
    return ergebnis


def lauf(jetzt: datetime | None = None, *, repo: Path | None = None,
         trocken: bool = False, paare_liste: list[paare.Paar] | None = None,
         messung: automatik.Messung | None = None, schwelle: int | None = None,
         an: bool | None = None,
         modus_mapping: Mapping[str, modi.Profil | str] | None = None,
         ausgeloest: Collection[str] | None = None,
         chat_anlegen: Callable[[str, str], str | None] | None = None,
         uebergeber: Callable[..., av.Vorgang] | None = None) -> list[automatik.Stand]:
    """Prüft Codex-Limit und übergibt aktive Codex-Themen automatisch an Antigravity (ggf. mit neuem Chat)."""
    jetzt = jetzt or datetime.now(timezone.utc)
    schwelle = anzeige.schwelle() if schwelle is None else schwelle
    an = anzeige.automatik_an() if an is None else an
    if not an:
        return []
    if messung is None:
        messung = automatik.Messung(signale.claude_lesen(jetzt=jetzt), signale.codex_lesen(jetzt=jetzt))
    im_limit, _ = codex_im_limit(messung.codex, schwelle, jetzt)
    if not im_limit:
        return []
    if repo is None:
        try:
            repo = uebergabe.haupt_wurzel(uebergabe.repo_wurzel())
        except uebergabe.UebergabeFehler:
            return [automatik.Stand("", "Repo nicht bestimmbar – keine Antigravity-Übergabe", "fehler")]
    liste = paare.aktive() if paare_liste is None else paare_liste
    if modus_mapping is None:
        try:
            modus_mapping = modi.lesen()
        except modi.ModusFehler as fehler:
            return [automatik.Stand("", f"Modusstatus fehlerhaft – kein Versand ({fehler})", "fehler")]
    try:
        offene_themen = {v.thema for v in av.lesen_geprueft() if v.phase not in av.ENDGUELTIG}
    except av.AssistentFehler:
        return [automatik.Stand("", "Wechselregister nicht prüfbar – keine Antigravity-Übergabe", "fehler")]
    bereits = automatik.ausgeloest_lesen() if ausgeloest is None else frozenset(ausgeloest)
    faellige = faellige_themen(
        liste, messung, schwelle, an, jetzt, repo=repo,
        modus_mapping=modus_mapping, ausgeloest=bereits, offene_themen=offene_themen,
    )
    if not faellige:
        return []
    if trocken:
        return [automatik.Stand(p.thema, "bereit (Codex-Limit → Antigravity)", k) for p, k in faellige]

    anlegen = chat_anlegen or agy_senden.neues_gespraech
    uebergeben_fn = uebergeber or assistent.uebergeben
    staende: list[automatik.Stand] = []
    from .fenster_modell import phase_kurz

    for paar, trigger_kennung in faellige:
        chat_id = agy_chat_fuer_thema(paar.thema)
        if chat_id is None:
            chat_id = anlegen(paar.thema, paar.laufend)
            if chat_id is None:
                protokoll.schreiben("", paar.thema, "agy_chat_fehler", "codex_limit")
                staende.append(automatik.Stand(
                    paar.thema, "Antigravity-Chat konnte nicht angelegt werden", "fehler"
                ))
                continue
            try:
                chat_zuordnung.bestaetigen("agy", chat_id, paar.thema)
                protokoll.schreiben("", paar.thema, "agy_chat_angelegt", "codex_limit")
            except Exception as fehler:  # noqa: BLE001
                klasse = type(fehler).__name__
                protokoll.schreiben("", paar.thema, "agy_zuordnung_fehler", klasse)
                staende.append(automatik.Stand(
                    paar.thema, f"Antigravity-Zuordnung fehlgeschlagen ({klasse})", "fehler"
                ))
                continue
        try:
            automatik.ausgeloest_vermerken(trigger_kennung, jetzt)
        except Exception as fehler:  # noqa: BLE001
            klasse = type(fehler).__name__
            staende.append(automatik.Stand(
                paar.thema, f"Vermerk nicht möglich ({klasse})", "fehler"
            ))
            continue
        try:
            nach = assistent.ChatRef("agy", chat_id)
            vorgang = uebergeben_fn(paar.thema, "agy", von_chat=None, nach_chat=nach, repo=repo)
        except Exception as fehler:  # noqa: BLE001
            klasse = type(fehler.__cause__ or fehler).__name__
            protokoll.schreiben("", paar.thema, "automatik_nicht_gestartet", klasse)
            staende.append(automatik.Stand(
                paar.thema, f"Wechsel zu Antigravity nicht gestartet ({klasse})", "fehler"
            ))
            continue
        protokoll.schreiben(vorgang.id, paar.thema, "automatik_ausgeloest", "codex_limit_agy")
        staende.append(automatik.Stand(
            paar.thema, f"Antigravity übernimmt: {phase_kurz(vorgang.phase)}", vorgang.phase
        ))
    return staende
