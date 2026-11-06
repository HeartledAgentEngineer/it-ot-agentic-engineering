"""Versioniertes Goal- und Fortschritts-Datenmodell für Multi-Agentic Coding in OrbitDesk.

Verwaltet pro Projekt/Thema ein versioniertes Goal-Objekt mit:
- Abnahmekriterien, Entscheidungen, offenen Aufgaben, belegtem Fortschritt, nächstem Schritt
- Gewünschter Rollenbesetzung vs. tatsächlicher Zuständigkeit
- Laufender Arbeit und Wartegründen
- Getrennten Nachweisen für Zustellung (`zustellungs_nachweis`) und Übernahme (`annahme_ack`)
- Revisionsschutz (Optimistic Locking) zur Verhinderung doppelter oder widersprüchlicher Ausführung.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import modi, paare, signale


class ZielFehler(Exception):
    """Ungültiges Goal oder Zieloperation."""


class ZielKonfliktFehler(ZielFehler):
    """Revisionskonflikt bei nebenläufiger Aktualisierung."""


STATUS_IN_ARBEIT = "in_arbeit"
STATUS_ABGENOMMEN = "abgenommen"
STATUS_BLOCKIERT = "blockiert"
STATUS_PAUSIERT = "pausiert"
STATUS_OFFEN = "offen"
ERLAUBTE_STATUS = (STATUS_OFFEN, STATUS_IN_ARBEIT, STATUS_ABGENOMMEN, STATUS_BLOCKIERT, STATUS_PAUSIERT)


@dataclass(frozen=True)
class Goal:
    thema: str
    revision: int
    aktualisiert: str  # ISO-8601 UTC
    titel: str
    zieltext: str
    abnahmekriterien: list[str] = field(default_factory=list)
    entscheidungen: list[str] = field(default_factory=list)
    offene_aufgaben: list[str] = field(default_factory=list)
    belegter_fortschritt: list[str] = field(default_factory=list)
    naechster_schritt: str = ""
    status: str = STATUS_IN_ARBEIT
    gewuenschte_besetzung: dict[str, str] = field(default_factory=dict)
    tatsaechliche_zustaendigkeit: dict[str, str] = field(default_factory=dict)
    laufende_arbeit: str = ""
    wartegrung: str | None = None
    zustellungs_nachweis: dict[str, str] | None = None
    annahme_ack: dict[str, str] | None = None

    def als_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def aus_dict(cls, daten: dict) -> Goal:
        if not isinstance(daten, dict):
            raise ZielFehler("Goal-Daten müssen ein Dictionary sein")
        thema = daten.get("thema")
        if not isinstance(thema, str) or not thema.strip():
            raise ZielFehler("Goal benötigt ein gültiges Thema")
        try:
            paare.thema_pruefen(thema)
        except paare.PaarFehler as fehler:
            raise ZielFehler(f"Thema ungültig: {thema}") from fehler

        revision = daten.get("revision", 1)
        if not isinstance(revision, int) or revision < 1:
            raise ZielFehler(f"Revision muss >= 1 sein, erhalten: {revision}")

        status = daten.get("status", STATUS_IN_ARBEIT)
        if status not in ERLAUBTE_STATUS:
            raise ZielFehler(f"Unbekannter Status: {status}")

        return cls(
            thema=thema.strip(),
            revision=revision,
            aktualisiert=str(daten.get("aktualisiert") or datetime.now(timezone.utc).isoformat()),
            titel=str(daten.get("titel") or "").strip(),
            zieltext=str(daten.get("zieltext") or "").strip(),
            abnahmekriterien=[str(x).strip() for x in daten.get("abnahmekriterien", []) if str(x).strip()],
            entscheidungen=[str(x).strip() for x in daten.get("entscheidungen", []) if str(x).strip()],
            offene_aufgaben=[str(x).strip() for x in daten.get("offene_aufgaben", []) if str(x).strip()],
            belegter_fortschritt=[str(x).strip() for x in daten.get("belegter_fortschritt", []) if str(x).strip()],
            naechster_schritt=str(daten.get("naechster_schritt") or "").strip(),
            status=status,
            gewuenschte_besetzung=dict(daten.get("gewuenschte_besetzung") or {}),
            tatsaechliche_zustaendigkeit=dict(daten.get("tatsaechliche_zustaendigkeit") or {}),
            laufende_arbeit=str(daten.get("laufende_arbeit") or "").strip(),
            wartegrung=str(daten["wartegrung"]).strip() if daten.get("wartegrung") else None,
            zustellungs_nachweis=dict(daten["zustellungs_nachweis"]) if daten.get("zustellungs_nachweis") else None,
            annahme_ack=dict(daten["annahme_ack"]) if daten.get("annahme_ack") else None,
        )


def ziele_ordner(basis: Path | None = None) -> Path:
    ordner = (basis or signale.daten_ordner()) / "ziele"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def ziel_pfad(thema: str, basis: Path | None = None) -> Path:
    paare.thema_pruefen(thema)
    return ziele_ordner(basis) / f"{thema}.json"


def goal_lesen(thema: str, basis: Path | None = None) -> Goal | None:
    """Liest das Goal zu einem Thema. Liefert `None`, wenn noch kein Goal existiert."""
    pfad = ziel_pfad(thema, basis)
    if not pfad.is_file():
        return None
    try:
        inhalt = json.loads(pfad.read_text(encoding="utf-8"))
        return Goal.aus_dict(inhalt)
    except (OSError, ValueError, ZielFehler):
        return None


def goal_speichern(goal: Goal, basis: Path | None = None, erwartete_revision: int | None = None) -> Goal:
    """Speichert ein Goal atomar. Prüft bei `erwartete_revision` auf Revisionskonflikte (CAS)."""
    pfad = ziel_pfad(goal.thema, basis)
    jetzt = datetime.now(timezone.utc).isoformat()

    bestehend = goal_lesen(goal.thema, basis)
    if bestehend is not None:
        if erwartete_revision is not None and bestehend.revision != erwartete_revision:
            raise ZielKonfliktFehler(
                f"Revisionskonflikt für '{goal.thema}': erwartet {erwartete_revision}, "
                f"vorhanden ist Revision {bestehend.revision}"
            )
        neue_revision = bestehend.revision + 1
    else:
        if erwartete_revision is not None and erwartete_revision != 0:
            raise ZielKonfliktFehler(
                f"Revisionskonflikt für '{goal.thema}': erwartet {erwartete_revision}, "
                f"aber Datei existiert noch nicht"
            )
        neue_revision = 1

    aktualisiertes_goal = Goal(
        thema=goal.thema,
        revision=neue_revision,
        aktualisiert=jetzt,
        titel=goal.titel,
        zieltext=goal.zieltext,
        abnahmekriterien=list(goal.abnahmekriterien),
        entscheidungen=list(goal.entscheidungen),
        offene_aufgaben=list(goal.offene_aufgaben),
        belegter_fortschritt=list(goal.belegter_fortschritt),
        naechster_schritt=goal.naechster_schritt,
        status=goal.status,
        gewuenschte_besetzung=dict(goal.gewuenschte_besetzung),
        tatsaechliche_zustaendigkeit=dict(goal.tatsaechliche_zustaendigkeit),
        laufende_arbeit=goal.laufende_arbeit,
        wartegrung=goal.wartegrung,
        zustellungs_nachweis=dict(goal.zustellungs_nachweis) if goal.zustellungs_nachweis else None,
        annahme_ack=dict(goal.annahme_ack) if goal.annahme_ack else None,
    )

    roh = json.dumps(aktualisiertes_goal.als_dict(), ensure_ascii=False, indent=2)
    signale._atomar_schreiben(pfad, roh)
    return aktualisiertes_goal


def goal_anlegen_oder_aktualisieren(
    thema: str,
    *,
    titel: str,
    zieltext: str,
    abnahmekriterien: list[str] | None = None,
    entscheidungen: list[str] | None = None,
    offene_aufgaben: list[str] | None = None,
    belegter_fortschritt: list[str] | None = None,
    naechster_schritt: str = "",
    status: str = STATUS_IN_ARBEIT,
    gewuenschte_besetzung: dict[str, str] | None = None,
    tatsaechliche_zustaendigkeit: dict[str, str] | None = None,
    laufende_arbeit: str = "",
    wartegrung: str | None = None,
    basis: Path | None = None,
    erwartete_revision: int | None = None,
) -> Goal:
    """Bequeme Mutation: aktualisiert ein bestehendes Goal oder legt ein neues an."""
    bestehend = goal_lesen(thema, basis)
    kriterien = list(abnahmekriterien) if abnahmekriterien is not None else (list(bestehend.abnahmekriterien) if bestehend else [])
    entsch = list(entscheidungen) if entscheidungen is not None else (list(bestehend.entscheidungen) if bestehend else [])
    aufgaben = list(offene_aufgaben) if offene_aufgaben is not None else (list(bestehend.offene_aufgaben) if bestehend else [])
    fortschritt = list(belegter_fortschritt) if belegter_fortschritt is not None else (list(bestehend.belegter_fortschritt) if bestehend else [])
    besetzung = dict(gewuenschte_besetzung) if gewuenschte_besetzung is not None else (dict(bestehend.gewuenschte_besetzung) if bestehend else {})
    zustaendig = dict(tatsaechliche_zustaendigkeit) if tatsaechliche_zustaendigkeit is not None else (dict(bestehend.tatsaechliche_zustaendigkeit) if bestehend else {})

    ziel = Goal(
        thema=thema,
        revision=bestehend.revision if bestehend else 0,
        aktualisiert=datetime.now(timezone.utc).isoformat(),
        titel=titel or (bestehend.titel if bestehend else ""),
        zieltext=zieltext or (bestehend.zieltext if bestehend else ""),
        abnahmekriterien=kriterien,
        entscheidungen=entsch,
        offene_aufgaben=aufgaben,
        belegter_fortschritt=fortschritt,
        naechster_schritt=naechster_schritt if naechster_schritt is not None else (bestehend.naechster_schritt if bestehend else ""),
        status=status,
        gewuenschte_besetzung=besetzung,
        tatsaechliche_zustaendigkeit=zustaendig,
        laufende_arbeit=laufende_arbeit if laufende_arbeit is not None else (bestehend.laufende_arbeit if bestehend else ""),
        wartegrung=wartegrung if wartegrung is not None else (bestehend.wartegrung if bestehend else None),
        zustellungs_nachweis=bestehend.zustellungs_nachweis if bestehend else None,
        annahme_ack=bestehend.annahme_ack if bestehend else None,
    )
    return goal_speichern(ziel, basis=basis, erwartete_revision=erwartete_revision)


def zustellung_belegen(thema: str, vorgang_id: str, empfaenger: str, basis: Path | None = None) -> Goal:
    """Dokumentiert die Zustellung (delivered) eines Übergabe-Vorgangs."""
    ziel = goal_lesen(thema, basis)
    if ziel is None:
        ziel = goal_anlegen_oder_aktualisieren(thema, titel=f"Thema {thema}", zieltext="Automatisch angelegtes Goal", basis=basis)
    jetzt = datetime.now(timezone.utc).isoformat()
    nachweis = {"vorgang_id": vorgang_id, "zeit": jetzt, "empfaenger": empfaenger}
    neues_ziel = Goal(
        thema=ziel.thema,
        revision=ziel.revision,
        aktualisiert=jetzt,
        titel=ziel.titel,
        zieltext=ziel.zieltext,
        abnahmekriterien=list(ziel.abnahmekriterien),
        entscheidungen=list(ziel.entscheidungen),
        offene_aufgaben=list(ziel.offene_aufgaben),
        belegter_fortschritt=list(ziel.belegter_fortschritt),
        naechster_schritt=ziel.naechster_schritt,
        status=ziel.status,
        gewuenschte_besetzung=dict(ziel.gewuenschte_besetzung),
        tatsaechliche_zustaendigkeit=dict(ziel.tatsaechliche_zustaendigkeit),
        laufende_arbeit=f"Übergabe {vorgang_id} zugestellt an {empfaenger}",
        wartegrung="Wartet auf Übernahme-ACK des Empfängers",
        zustellungs_nachweis=nachweis,
        annahme_ack=None,  # Reset bei neuer Zustellung: Übernahme muss frisch erfolgen!
    )
    return goal_speichern(neues_ziel, basis=basis, erwartete_revision=ziel.revision)


def annahme_quittieren(thema: str, vorgang_id: str, agent: str, basis: Path | None = None) -> Goal:
    """Dokumentiert die Übernahme (accepted / ACK) durch den neuen Agenten."""
    ziel = goal_lesen(thema, basis)
    if ziel is None:
        raise ZielFehler(f"Kein Goal für Thema '{thema}' vorhanden, Quittierung nicht möglich")
    jetzt = datetime.now(timezone.utc).isoformat()
    ack = {"vorgang_id": vorgang_id, "zeit": jetzt, "quittiert_von": agent}
    
    # Zuständigkeit aktualisieren
    neue_zustaendigkeit = dict(ziel.tatsaechliche_zustaendigkeit)
    neue_zustaendigkeit["master"] = agent

    neues_ziel = Goal(
        thema=ziel.thema,
        revision=ziel.revision,
        aktualisiert=jetzt,
        titel=ziel.titel,
        zieltext=ziel.zieltext,
        abnahmekriterien=list(ziel.abnahmekriterien),
        entscheidungen=list(ziel.entscheidungen),
        offene_aufgaben=list(ziel.offene_aufgaben),
        belegter_fortschritt=list(ziel.belegter_fortschritt),
        naechster_schritt=ziel.naechster_schritt,
        status=STATUS_IN_ARBEIT,
        gewuenschte_besetzung=dict(ziel.gewuenschte_besetzung),
        tatsaechliche_zustaendigkeit=neue_zustaendigkeit,
        laufende_arbeit=f"Übernommen von {agent} (Vorgang {vorgang_id})",
        wartegrung=None,  # Nach ACK nicht mehr wartend!
        zustellungs_nachweis=ziel.zustellungs_nachweis,
        annahme_ack=ack,
    )
    return goal_speichern(neues_ziel, basis=basis, erwartete_revision=ziel.revision)


def goal_zu_markdown(goal: Goal) -> str:
    """Formatiert das Goal als strukturierte Markdown-Dokumentation für Übergaben."""
    zeilen = [
        f"### Goal & Fortschritt: {goal.titel} (Rev. {goal.revision})",
        f"- **Status:** `{goal.status}` · **Aktualisiert:** {goal.aktualisiert}",
    ]
    if goal.wartegrung:
        zeilen.append(f"- **Wartet:** ⚠️ {goal.wartegrung}")
    if goal.laufende_arbeit:
        zeilen.append(f"- **Laufende Arbeit:** {goal.laufende_arbeit}")
    if goal.naechster_schritt:
        zeilen.append(f"- **Nächster Schritt:** ➡️ {goal.naechster_schritt}")

    if goal.zieltext:
        zeilen.extend(["", "#### Zielbeschreibung", goal.zieltext])

    if goal.abnahmekriterien:
        zeilen.extend(["", "#### Abnahmekriterien"])
        for k in goal.abnahmekriterien:
            zeilen.append(f"- [ ] {k}")

    if goal.belegter_fortschritt:
        zeilen.extend(["", "#### Belegter Fortschritt"])
        for f in goal.belegter_fortschritt:
            zeilen.append(f"- [x] {f}")

    if goal.entscheidungen:
        zeilen.extend(["", "#### Dokumentierte Entscheidungen"])
        for e in goal.entscheidungen:
            zeilen.append(f"- ⚖️ {e}")

    if goal.offene_aufgaben:
        zeilen.extend(["", "#### Offene Aufgaben"])
        for a in goal.offene_aufgaben:
            zeilen.append(f"- ⏳ {a}")

    if goal.zustellungs_nachweis or goal.annahme_ack:
        zeilen.extend(["", "#### Übergabe-Nachweis"])
        if goal.zustellungs_nachweis:
            z = goal.zustellungs_nachweis
            zeilen.append(f"- **Zustellung:** Vorgang `{z.get('vorgang_id')}` an `{z.get('empfaenger')}` ({z.get('zeit')})")
        if goal.annahme_ack:
            a = goal.annahme_ack
            zeilen.append(f"- **Übernahme-ACK:** Bestätigt von `{a.get('quittiert_von')}` ({a.get('zeit')})")

    return "\n".join(zeilen)
