"""Reine lokale Vorauswahl der Themenübersicht; ohne Tk, Dateien oder Transport."""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import arbeitsweise, modi
from . import uebersicht_modell as um

FELD_ATTRIBUT = {
    "master": "master_wert",
    "pruefer": "pruefer_wert",
    "ausfuehrer": "worker_wert",
    "modell": "modell_wert",
    "arbeitsweise": "arbeitsweise",
    "auto": "paar_aktiv",
}
FELDER = tuple(FELD_ATTRIBUT)


class EntwurfFehler(ValueError):
    """Ein gewünschter Wert kann in der aktuellen Aufnahme nicht vorgemerkt werden."""


@dataclass(frozen=True)
class Aenderung:
    thema: str
    feld: str
    alt: str | bool | None
    neu: str | bool | None
    konflikt: bool = False
    hinweis: str = ""


@dataclass
class _ThemaEntwurf:
    aktuell: um.ThemaZeile
    basis: dict[str, str | bool | None] = field(default_factory=dict)
    werte: dict[str, str | bool | None] = field(default_factory=dict)
    konflikte: set[str] = field(default_factory=set)
    entfernt: bool = False
    modell_basis_ausfuehrer: str | None = None


class EntwurfsVerwaltung:
    """Hält den einzigen Draft-Zustand für alle Themen und führt nur reine Prüfungen aus."""

    def __init__(self, snap: um.Uebersicht | None = None) -> None:
        self._snap: um.Uebersicht | None = None
        self._themen: dict[str, _ThemaEntwurf] = {}
        if snap is not None:
            self.aktualisieren(snap)

    def aktualisieren(self, snap: um.Uebersicht) -> None:
        self._snap = snap
        eingang = {z.thema: z for z in snap.themen}
        for thema, entwurf in self._themen.items():
            neu = eingang.get(thema)
            if neu is None:
                entwurf.entfernt = True
                entwurf.konflikte.update(entwurf.werte)
                continue
            entwurf.entfernt = False
            for feld, basis in entwurf.basis.items():
                basis_geaendert = getattr(neu, FELD_ATTRIBUT[feld]) != basis
                if feld == "modell" and entwurf.modell_basis_ausfuehrer is not None:
                    basis_geaendert |= neu.worker_wert != entwurf.modell_basis_ausfuehrer
                if basis_geaendert:
                    entwurf.konflikte.add(feld)
                else:
                    entwurf.konflikte.discard(feld)
            entwurf.aktuell = neu
        for thema, zeile in eingang.items():
            if thema not in self._themen:
                self._themen[thema] = _ThemaEntwurf(zeile)

    def _finden(self, thema: str) -> _ThemaEntwurf:
        try:
            return self._themen[thema]
        except KeyError as fehler:
            raise EntwurfFehler(f"Thema nicht bekannt: {thema}") from fehler

    def zeile(self, thema: str) -> um.ThemaZeile:
        entwurf = self._finden(thema)
        values = {FELD_ATTRIBUT[feld]: wert for feld, wert in entwurf.werte.items()}
        return replace(entwurf.aktuell, **values) if values else entwurf.aktuell

    def _wahl_pruefen(self, thema: str, feld: str, wert: str | bool | None) -> _ThemaEntwurf:
        if feld not in FELD_ATTRIBUT:
            raise EntwurfFehler(f"Unbekanntes Einstellungsfeld: {feld}")
        if self._snap is None:
            raise EntwurfFehler("Noch keine aktuelle Aufnahme vorhanden")
        if not self._snap.schreiben:
            raise EntwurfFehler(self._snap.schreib_hinweis or um.NUR_ANZEIGE)
        if not getattr(self._snap, "wechsel_pruefbar", False):
            raise EntwurfFehler("Wechselstatus nicht prüfbar – Auswahl vorübergehend gesperrt")
        entwurf = self._finden(thema)
        if entwurf.entfernt:
            raise EntwurfFehler(f"Thema {thema} wurde entfernt")
        if thema in getattr(self._snap, "wechsel_themen", ()):
            raise EntwurfFehler(f"Wechsel läuft – wartet auf Abschluss: {thema}")
        return entwurf

    def waehlen(self, thema: str, feld: str, wert: str | bool | None) -> None:
        entwurf = self._wahl_pruefen(thema, feld, wert)
        gewuenscht = self.zeile(thema)
        if feld == "master":
            erlaubt = isinstance(wert, str) and wert in um.MASTER_WERTE
        elif feld == "pruefer":
            erlaubt = isinstance(wert, str) and wert in um.PRUEFER_WERTE
        elif feld == "ausfuehrer":
            erlaubt = isinstance(wert, str) and wert in um.AUSFUEHRER_WERTE
        elif feld == "arbeitsweise":
            erlaubt = isinstance(wert, str) and wert in um.ARBEITSWEISE_WERTE
        elif feld == "auto":
            erlaubt = type(wert) is bool and gewuenscht.paar_aktiv is not None
        else:
            erlaubt = self._modell_wahl_erlaubt(gewuenscht, wert)
        if not erlaubt:
            raise EntwurfFehler(self._wert_fehler(thema, feld, gewuenscht))

        alt_gewünscht = getattr(gewuenscht, FELD_ATTRIBUT[feld])
        self._setzen(entwurf, feld, wert)
        if feld == "ausfuehrer" and wert != alt_gewünscht:
            modell = modi.HERMES_MODELL if wert == "hermes" else None
            self._setzen(entwurf, "modell", modell)

    @staticmethod
    def _setzen(entwurf: _ThemaEntwurf, feld: str, wert: str | bool | None) -> None:
        attribut = FELD_ATTRIBUT[feld]
        gespeichert = getattr(entwurf.aktuell, attribut)
        if wert == gespeichert:
            entwurf.werte.pop(feld, None)
            entwurf.basis.pop(feld, None)
            entwurf.konflikte.discard(feld)
            if feld == "modell":
                entwurf.modell_basis_ausfuehrer = None
        else:
            entwurf.werte[feld] = wert
            entwurf.basis[feld] = gespeichert
            entwurf.konflikte.discard(feld)
            if feld == "modell":
                entwurf.modell_basis_ausfuehrer = entwurf.aktuell.worker_wert

    def _modell_wahl_erlaubt(self, zeile: um.ThemaZeile, wert: str | bool | None) -> bool:
        if wert is not None and not isinstance(wert, str):
            return False
        if zeile.worker_wert not in ("claude", "codex"):
            return False
        if wert is None:
            return True
        if self._snap is None:
            return False
        katalog = next((k for k in self._snap.kataloge if k.anbieter == zeile.worker_wert), None)
        return katalog is not None and katalog.geprueft and any(kennung == wert for kennung, _ in katalog.modelle)

    def _wert_fehler(self, thema: str, feld: str, zeile: um.ThemaZeile) -> str:
        if feld == "modell":
            if zeile.worker_wert == "workflow":
                return f"{thema}: Workflow hat kein wählbares Modell"
            if zeile.worker_wert == "hermes":
                return f"{thema}: Hermes verwendet sein festes Modell"
            if zeile.worker_wert == "agy":
                return f"{thema}: Antigravity verwendet den Standard des Werkzeugs"
            return f"{thema}: Modell muss im aktuell geprüften {zeile.worker_wert.title()}-Katalog stehen"
        return f"{thema}: ungültiger Wert für {feld}"

    def aenderungen(self) -> tuple[Aenderung, ...]:
        ergebnis: list[Aenderung] = []
        for thema in sorted(self._themen):
            entwurf = self._themen[thema]
            gewuenscht = self.zeile(thema)
            hinweise = self._validierung(entwurf, gewuenscht)
            for feld in FELDER:
                if feld not in entwurf.werte:
                    continue
                hinweis = ""
                if entwurf.entfernt:
                    hinweis = f"Thema {thema} wurde entfernt; Entwurf kann nicht übernommen werden"
                elif feld in entwurf.konflikte:
                    basis = entwurf.basis.get(feld)
                    aktuell = getattr(entwurf.aktuell, FELD_ATTRIBUT[feld])
                    if feld == "modell" and entwurf.modell_basis_ausfuehrer is not None \
                            and entwurf.aktuell.worker_wert != entwurf.modell_basis_ausfuehrer:
                        hinweis = (f"Ausführer geändert: {entwurf.modell_basis_ausfuehrer} → "
                                   f"{entwurf.aktuell.worker_wert}; Modell bitte neu wählen")
                    else:
                        hinweis = f"Ausgangswert geändert: {basis!r} → {aktuell!r}; bitte neu abgleichen"
                elif feld in hinweise:
                    hinweis = hinweise[feld]
                ergebnis.append(Aenderung(thema, feld, entwurf.basis.get(feld), entwurf.werte[feld],
                                          entwurf.entfernt or feld in entwurf.konflikte, hinweis))
        return tuple(ergebnis)

    def _validierung(self, entwurf: _ThemaEntwurf, zeile: um.ThemaZeile) -> dict[str, str]:
        hinweise: dict[str, str] = {}
        if zeile.arbeitsweise == "vibe" and zeile.worker_wert != "claude":
            text = "Vibe ist nur mit Ausführer Claude gültig"
            hinweise["arbeitsweise"] = text
            hinweise["ausfuehrer"] = text
        if zeile.worker_wert in ("claude", "codex") and zeile.modell_wert is not None:
            if not self._modell_wahl_erlaubt(zeile, zeile.modell_wert):
                hinweise["modell"] = f"Modell {zeile.modell_wert} ist nicht im geprüften {zeile.worker_wert.title()}-Katalog"
        return hinweise

    def zuruecksetzen(self, thema: str | None = None) -> None:
        ziel = (thema,) if thema is not None else tuple(self._themen)
        for kennung in ziel:
            entwurf = self._finden(kennung)
            entwurf.werte.clear()
            entwurf.basis.clear()
            entwurf.konflikte.clear()
            entwurf.modell_basis_ausfuehrer = None
            if entwurf.entfernt:
                self._themen.pop(kennung, None)
