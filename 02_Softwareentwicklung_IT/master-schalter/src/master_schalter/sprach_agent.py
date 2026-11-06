"""Autonomer Sprach- und Leitwarten-Agent („Jarvis-Modus“ / Klaus Voice Engine) für OrbitDesk.

Ermöglicht vollständige bidirektionale Echtzeit-Sprachsteuerung:
- Sprachausgabe mit der natürlichen „Klaus“-Stimme (Microsoft MAI-Voice-2-Flash / de-DE-Klaus:MAI-Voice-2 über OpenRouter)
  inklusive lokalem MP3-Cache und unterbrechbarem Abspielen (Barge-In).
- Fallback auf Windows-Sprachsynthese bei Offline-Betrieb.
- Sprachbefehle für ALLE Funktionen von OrbitDesk:
  * Navigation & Status: „Was läuft wo?“, „Blocker?“, „Fragen an mich?“, „Quoten?“
  * Rollenverteilung: Master, Prüfer, Ausführer (Worker), Modell, Arbeitsweise je Thema ändern.
  * Versionierte Goals: Ziele abfragen, neues Goal anlegen, nächsten Schritt diktieren.
  * Verbräuche & Quoten: Claude-, Codex-, Antigravity- (Argon, 5h, Woche) & Multi-Modell-Stand abfragen.
  * Budgets: Budget-Limits und aufgelaufene Kosten prüfen und anpassen.
  * Chat-Erkennung & -Übernahme: Neue Chats erkennen und auf Sprachbefehl direkt in OrbitDesk registrieren.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from . import (
    arbeitsweise,
    chat_discovery,
    kosten_budget,
    modi,
    paare,
    pruefer_wahl,
    signale,
    sprach_zentrale,
    ziele,
)

logger = logging.getLogger(__name__)

OPENROUTER_SPEECH_URL = "https://openrouter.ai/api/v1/audio/speech"
KLAUS_MODELL = "microsoft/mai-voice-2-flash"
KLAUS_STIMME = "de-DE-Klaus:MAI-Voice-2"


def audio_cache_ordner() -> Path:
    ordner = signale.daten_ordner() / "audio_cache"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


class KlausVoiceEngine:
    """Verwaltet Sprachausgabe mit der Klaus-Stimme und unterbrechbares Audio (Barge-In)."""

    def __init__(self) -> None:
        self._laufender_prozess: subprocess.Popen | None = None
        self._sperre = threading.Lock()
        self.letzter_fehler: str | None = None

    def stoppen(self) -> None:
        """Unterbricht sofort laufende Sprachausgaben (Barge-In)."""
        with self._sperre:
            if self._laufender_prozess and self._laufender_prozess.poll() is None:
                try:
                    self._laufender_prozess.terminate()
                except Exception:
                    pass
                self._laufender_prozess = None

    def mp3_erzeugen(self, text: str) -> Path | None:
        """Erzeugt eine MP3-Datei mit der Klaus-Stimme (oder nutzt den Cache)."""
        text = text.strip()
        if not text:
            return None

        # Hash für Cache ermitteln
        text_hash = hashlib.sha256(f"{KLAUS_MODELL}:{KLAUS_STIMME}:{text}".encode("utf-8")).hexdigest()[:16]
        mp3_pfad = audio_cache_ordner() / f"klaus_{text_hash}.mp3"
        if mp3_pfad.exists() and mp3_pfad.stat().st_size > 500:
            return mp3_pfad

        # API-Key prüfen (aus OPENROUTER_TTS_KEY oder OPENROUTER_API_KEY)
        api_key = os.environ.get("OPENROUTER_TTS_KEY") or os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            self.letzter_fehler = "Kein OpenRouter API-Schlüssel vorhanden"
            return None

        payload = json.dumps({
            "model": KLAUS_MODELL,
            "voice": KLAUS_STIMME,
            "input": text,
            "response_format": "mp3",
        }).encode("utf-8")

        req = urllib.request.Request(
            OPENROUTER_SPEECH_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=payload,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                daten = resp.read()
                if daten and len(daten) > 200:
                    mp3_pfad.write_bytes(daten)
                    self.letzter_fehler = None
                    return mp3_pfad
        except Exception as err:
            self.letzter_fehler = f"Klaus-TTS HTTP-Fehler: {err}"
            logger.warning("Klaus-TTS fehlgeschlagen: %s", err)

        return None

    def abspielen_mp3(self, mp3_pfad: Path, async_play: bool = True) -> bool:
        """Spielt eine MP3-Audiodatei via Windows Media Player (PowerShell) ab."""
        self.stoppen()
        pfad_str = str(mp3_pfad).replace("'", "''")
        ps_cmd = (
            f"Add-Type -AssemblyName presentationCore; "
            f"$p = New-Object System.Windows.Media.MediaPlayer; "
            f"$p.Open([System.Uri]'{pfad_str}'); "
            f"$p.Play(); "
            f"Start-Sleep -Milliseconds 300; "
            f"while ($p.NaturalDuration.HasTimeSpan -and $p.Position -lt $p.NaturalDuration.TimeSpan) {{ "
            f"  Start-Sleep -Milliseconds 150 "
            f"}}"
        )

        try:
            with self._sperre:
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._laufender_prozess = proc

            if not async_play:
                proc.wait()
            return True
        except Exception as err:
            self.letzter_fehler = f"Abspielfehler: {err}"
            return False

    def abspielen_sapi_fallback(self, text: str, async_play: bool = True) -> bool:
        """Fallback: Windows-Sprachsynthese (SAPI) wenn OpenRouter offline ist."""
        self.stoppen()
        text_sauber = text.replace("'", "''").replace("\n", " ")
        ps_cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"try {{ $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Male, [System.Speech.Synthesis.VoiceAge]::Adult, 0, [System.Globalization.CultureInfo]::GetCultureInfo('de-DE')) }} catch {{}}; "
            f"$s.Speak('{text_sauber}');"
        )
        try:
            with self._sperre:
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._laufender_prozess = proc
            if not async_play:
                proc.wait()
            return True
        except Exception:
            return False

    def sprechen(self, text: str, async_play: bool = True) -> bool:
        """Liest Text vor: bevorzugt Klaus-Stimme, sonst Windows-SAPI."""
        mp3 = self.mp3_erzeugen(text)
        if mp3:
            return self.abspielen_mp3(mp3, async_play=async_play)
        return self.abspielen_sapi_fallback(text, async_play=async_play)


# Globale Instanz der Voice Engine
klaus_engine = KlausVoiceEngine()


# ─────────────────────────────────────────────────────────────────────────────
# Chat-Übernahme in die OrbitDesk-Steuerzentrale
# ─────────────────────────────────────────────────────────────────────────────

def chat_in_orbitdesk_uebernehmen(thema_id: str, titel: str, quelle: str = "auto") -> tuple[bool, str]:
    """Registriert einen neu erkannten Chat verbindlich als Thema in OrbitDesk.

    1. Bereinigt die Thema-ID nach den Systemregeln (Kleinbuchstaben, Ziffern, Bindestriche).
    2. Registriert das Thema in `paare.json`.
    3. Initialisiert das Profil in `modi.json` (Standard: Kontingent-Steuerung).
    4. Hinterlegt das Anfangs-Goal in `ziele.py`.
    """
    thema_sauber = re.sub(r"[^a-z0-9-]+", "-", thema_id.lower().strip()).strip("-")
    if not thema_sauber:
        return False, "Ungültige Thema-Kennung."

    try:
        paare.thema_pruefen(thema_sauber)
    except Exception as err:
        return False, f"Ungültiges Themenformat: {err}"

    # 1. In paare.json registrieren
    try:
        vorhandene = {p.thema: p for p in paare.lesen()}
        if thema_sauber not in vorhandene:
            paare.setzen(
                thema=thema_sauber,
                codex_thread=str(uuid.uuid4()),
                laufend=paare.laufend_bilden(thema_sauber),
                aktiv=False,
            )
    except Exception as err:
        return False, f"Fehler beim Anlegen in paare.json: {err}"

    # 2. In modi.json setzen (Master auf 'kontingent')
    try:
        modi.master_setzen(thema_sauber, "kontingent")
    except Exception as err:
        return False, f"Fehler beim Initialisieren des Profils: {err}"

    # 3. Versioniertes Goal anlegen
    try:
        ziele.goal_anlegen_oder_aktualisieren(
            thema=thema_sauber,
            titel=titel or f"Neues Thema {thema_sauber}",
            zieltext=f"Autonom erkannter Chat aus {quelle}: {titel}",
            abnahmekriterien=["Initialer Entwurf geprüft", "Rollenverteilung festgelegt"],
            naechster_schritt="Aufgaben und Abnahmekriterien abstimmen",
        )
    except Exception as err:
        logger.warning("Goal-Erstellung bei Chat-Übernahme fehlgeschlagen: %s", err)

    return True, f"Chat erfolgreich als Thema '{thema_sauber}' in OrbitDesk übernommen!"


# ─────────────────────────────────────────────────────────────────────────────
# Intelligenter Sprachbefehl-Interpreter
# ─────────────────────────────────────────────────────────────────────────────

def befehl_verarbeiten(befehl: str) -> str:
    """Verarbeitet natürliche Sprach- und Textbefehle für OrbitDesk.

    Liefert die Antwort als formatierten Text, der direkt von Klaus gesprochen werden kann.
    """
    s = befehl.strip().lower()
    if not s:
        return "Hallo Sebastian, ich habe dich leider nicht verstanden. Was soll ich tun?"

    # 1. Begrüßung / Identität
    if re.search(r"\b(hallo|hi|guten\s+tag|wer\s+bist\s+du|bist\s+du\s+da)\b", s):
        return (
            "Hallo Sebastian! Ich bin Klaus, dein übergeordneter Sprachagent in OrbitDesk. "
            "Ich steuere alle deine Modelle, Rollen, Goals und Kontingente in Echtzeit. "
            "Was möchtest du tun?"
        )

    # 2. Was läuft wo?
    if re.search(r"\b(was\s+läuft\s+wo|was\s+geht|status\s+aller|übersicht|was\s+machen\s+die\s+agenten)\b", s):
        return sprach_zentrale.was_laeuft_wo()

    # 3. Blocker & Prüfungen
    if re.search(r"\b(blocker|prüfungen|was\s+steht\s+an|offene\s+arbeiten|wartegründe)\b", s):
        return sprach_zentrale.offene_pruefungen_und_blocker()

    # 4. Fragen an Sebastian
    if re.search(r"\b(fragen\s+an\s+mich|was\s+muss\s+ich\s+entscheiden|entscheidungen|meine\s+aufgaben)\b", s):
        return sprach_zentrale.fragen_an_sebastian()

    # 5. Kontingente & Verbräuche (inkl. Antigravity & Argon!)
    if re.search(r"\b(kontingent|quoten|verbrauch|verbräuche|limits|wie\s+stehen\s+die\s+abos|antigravity|argon)\b", s):
        limits = signale.alle_limits_lesen()
        texte = []
        for lim in limits:
            titel = lim.titel
            fenster_str = ", ".join(f"{f.name}: {int(f.prozent or 0)} %" for f in lim.fenster if f.prozent is not None)
            texte.append(f"{titel}: {fenster_str or 'aktiv'}.")
            if "Argon-Limit" in lim.details:
                texte.append(f"Argon-Status: {lim.details['Argon-Limit']}.")
        return "Hier sind deine aktuellen Verbräuche: " + " ".join(texte)

    # 6. Budgets & Kosten
    if re.search(r"\b(budget|kosten|ausgaben|openrouter\s+kosten|foundry\s+kosten|was\s+kostet)\b", s):
        return kosten_budget.kosten_sprachbericht()

    # 7. Neue Chats erkennen & auflisten
    if re.search(r"\b(neue\s+chats|chats\s+finden|neue\s+themen|ungemeldete\s+chats|harness)\b", s):
        bestehend = {p.thema for p in paare.lesen()}
        vorschlaege = chat_discovery.neue_themen_vorschlaege(bestehend)
        if not vorschlaege:
            return "Aktuell gibt es keine neuen unregistrierten Chats. Alle Harnesses sind synchronisiert."
        berichte = [f"{v.quelle.upper()}-Chat: {v.titel} (Vorschlag: {v.thema})" for v in vorschlaege[:5]]
        return f"Ich habe {len(vorschlaege)} neue Sitzungen gefunden: " + "; ".join(berichte) + ". Möchtest du einen davon übernehmen?"

    # 8. Neuen Chat übernehmen
    m_uebernahme = re.search(r"\b(übernimm|übernehme|registrier(e)?|importier(e)?)\s+.*(chat|thema)?\s*([a-z0-9-]+)", s)
    if m_uebernahme:
        ziel_id = m_uebernahme.group(3)
        bestehend = {p.thema for p in paare.lesen()}
        vorschlaege = chat_discovery.neue_themen_vorschlaege(bestehend)
        passend = next((v for v in vorschlaege if ziel_id in v.thema or ziel_id in v.quelle.lower()), None)
        if passend:
            ok, msg = chat_in_orbitdesk_uebernehmen(passend.thema, passend.titel, passend.quelle)
            return msg
        # Direkter Name
        ok, msg = chat_in_orbitdesk_uebernehmen(ziel_id, f"Neues Thema {ziel_id}", "Sprachbefehl")
        return msg

    # 9. Rollen ändern (Master, Prüfer, Ausführer, Arbeitsweise)
    # 9a. Master setzen: z. B. "Setze Master für typeFREE auf Codex"
    m_master = re.search(r"\b(setze|schalte|ändere)\s+.*master\s+(für|von|bei)\s+([a-z0-9-]+)\s+auf\s+([a-z0-9]+)\b", s)
    if m_master:
        thema = m_master.group(3)
        neuer_master = m_master.group(4)
        mapping = {"claude": "claude", "codex": "codex", "hermes": "hermes", "antigravity": "agy", "gemini": "agy", "kontingent": "kontingent"}
        master_val = mapping.get(neuer_master, neuer_master)
        try:
            modi.master_setzen(thema, master_val)
            return f"Master für Thema {thema} erfolgreich auf {neuer_master.upper()} umgestellt."
        except Exception as err:
            return f"Konnte Master für {thema} nicht ändern: {err}"

    # 9b. Ausführer / Worker setzen: z. B. "Setze Worker für typeFREE auf Hermes"
    m_worker = re.search(r"\b(setze|schalte|ändere)\s+.*(worker|ausführer)\s+(für|von|bei)\s+([a-z0-9-]+)\s+auf\s+([a-z0-9]+)\b", s)
    if m_worker:
        thema = m_worker.group(4)
        neuer_worker = m_worker.group(5)
        mapping = {"workflow": "workflow", "claude": "claude", "codex": "codex", "hermes": "hermes", "antigravity": "agy"}
        worker_val = mapping.get(neuer_worker, neuer_worker)
        try:
            modi.worker_setzen(thema, worker_val)
            return f"Ausführer für Thema {thema} erfolgreich auf {neuer_worker.upper()} gesetzt."
        except Exception as err:
            return f"Konnte Ausführer für {thema} nicht ändern: {err}"

    # 9c. Prüfer setzen: z. B. "Setze Prüfer für typeFREE auf Hermes"
    m_pruefer = re.search(r"\b(setze|schalte|ändere)\s+.*prüfer\s+(für|von|bei)\s+([a-z0-9-]+)\s+auf\s+([a-z0-9]+)\b", s)
    if m_pruefer:
        thema = m_pruefer.group(3)
        neuer_pruefer = m_pruefer.group(4)
        mapping = {"automatisch": "automatisch", "auto": "automatisch", "codex": "codex", "hermes": "hermes"}
        p_val = mapping.get(neuer_pruefer, neuer_pruefer)
        try:
            p_setter = getattr(pruefer_wahl, "setzen")
            p_setter(thema, p_val)
            return f"Prüfer für Thema {thema} erfolgreich auf {neuer_pruefer.upper()} gesetzt."
        except Exception as err:
            return f"Konnte Prüfer für {thema} nicht ändern: {err}"

    # 9d. Arbeitsweise setzen: z. B. "Setze Arbeitsweise bei typeFREE auf Vibe"
    m_weise = re.search(r"\b(setze|schalte|ändere)\s+.*arbeitsweise\s+(für|von|bei)\s+([a-z0-9-]+)\s+auf\s+([a-z]+)\b", s)
    if m_weise:
        thema = m_weise.group(3)
        weise_raw = m_weise.group(4)
        ist_vibe = "vibe" in weise_raw
        try:
            modi.vibe_setzen(thema, an=ist_vibe)
            label = "VIBE" if ist_vibe else "PROTOKOLL"
            return f"Arbeitsweise für Thema {thema} erfolgreich auf {label} umgestellt."
        except Exception as err:
            return f"Konnte Arbeitsweise nicht ändern: {err}"

    # 10. Goals abfragen & diktieren
    # 10a. Nächsten Schritt diktieren: z. B. "Nächster Schritt bei typeFREE ist Frontend testen"
    m_schritt = re.search(r"\bnächster\s+schritt\s+(für|von|bei)\s+([a-zA-Z0-9-]+)\s+(ist|auf)\s+(.+)$", befehl, flags=re.IGNORECASE)
    if m_schritt:
        thema = m_schritt.group(2).lower()
        schritt_text = m_schritt.group(4).strip()
        ziel = ziele.goal_lesen(thema)
        if not ziel:
            ziel = ziele.goal_anlegen_oder_aktualisieren(
                thema=thema,
                titel=f"Goal für {thema}",
                zieltext=f"Ziel für {thema}",
                naechster_schritt=schritt_text,
            )
        else:
            ziel.naechster_schritt = schritt_text
            ziele.goal_schreiben(ziel)
        return f"Nächster Schritt für {thema} ist jetzt gespeichert: {schritt_text}."

    # 10b. Goal abfragen für Thema: z. B. "Was ist das Goal von typeFREE?"
    m_goal_abfrage = re.search(r"\b(goal|ziel|status)\s+(für|von|bei)\s+([a-z0-9-]+)\b", s)
    if m_goal_abfrage:
        thema = m_goal_abfrage.group(3)
        return sprach_zentrale.thema_ansage(thema)

    # 11. Allgemeines Einzelthema
    themen = [p.thema for p in paare.lesen()]
    for t in themen:
        if t in s:
            return sprach_zentrale.thema_ansage(t)

    # 12. Unbekannter Befehl: Hilfestellung geben
    return (
        f"Ich habe den Befehl verstanden, Sebastian. Du kannst mich fragen: "
        f"'Was läuft wo?', 'Blocker?', 'Quoten und Antigravity?', 'Budgets?', "
        f"'Neue Chats?', oder 'Setze Master bei typeFREE auf Codex'."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Live-Anruf Zustandsautomat (Duplex Jarvis Session)
# ─────────────────────────────────────────────────────────────────────────────

class LiveAnrufZustand:
    BEREIT = "bereit"
    VERBINDEN = "verbinden"
    VERBUNDEN = "verbunden"
    HOEREN = "hoeren"
    DENKEN = "denken"
    SPRECHEN = "sprechen"
    AUFGELEGT = "aufgelegt"


class JarvisLiveSession:
    """Repräsentiert eine interaktive Vollduplex-Sitzung mit Klaus."""

    def __init__(self, callback_zustand: Optional[Callable[[str, str], None]] = None) -> None:
        self.zustand: str = LiveAnrufZustand.BEREIT
        self.session_id: str = str(uuid.uuid4())[:8]
        self.callback_zustand: Optional[Callable[[str, str], None]] = callback_zustand
        self._aktiv: bool = False

    def _setze_zustand(self, neuer_zustand: str, info: str = "") -> None:
        self.zustand = neuer_zustand
        if self.callback_zustand:
            try:
                self.callback_zustand(neuer_zustand, info)
            except Exception:
                pass

    def anruf_starten(self) -> str:
        """Startet den Live-Anruf mit Klaus."""
        self._aktiv = True
        self._setze_zustand(LiveAnrufZustand.VERBINDEN, "Verbindung wird aufgebaut …")
        begruessung = (
            "Hallo Sebastian! Klaus hier. Dein OrbitDesk Jarvis ist live geschaltet. "
            "Ich habe alle 4 Harnesses im Blick. Was kann ich für dich tun?"
        )
        self._setze_zustand(LiveAnrufZustand.SPRECHEN, "Klaus spricht …")
        klaus_engine.sprechen(begruessung, async_play=True)
        self._setze_zustand(LiveAnrufZustand.HOEREN, "Klaus hört zu …")
        return begruessung

    def anruf_beenden(self) -> str:
        """Beendet den Live-Anruf und stoppt Audio sofort."""
        self._aktiv = False
        klaus_engine.stoppen()
        self._setze_zustand(LiveAnrufZustand.AUFGELEGT, "Anruf beendet.")
        return "Anruf mit Klaus beendet."

    def eingabe_senden(self, text: str) -> str:
        """Verarbeitet eine gesprochene oder getippte Anweisung während des Anrufs."""
        if not text.strip():
            return ""

        # Barge-In falls Klaus gerade noch redet
        klaus_engine.stoppen()
        self._setze_zustand(LiveAnrufZustand.DENKEN, "Klaus denkt nach …")

        antwort = befehl_verarbeiten(text)

        self._setze_zustand(LiveAnrufZustand.SPRECHEN, "Klaus antwortet …")
        klaus_engine.sprechen(antwort, async_play=True)
        self._setze_zustand(LiveAnrufZustand.HOEREN, "Klaus hört zu …")
        return antwort
