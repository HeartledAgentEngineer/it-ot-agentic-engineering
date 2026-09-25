"""Welches Transkriptionsmodell versteht schnelles, genuscheltes Deutsch am besten?

Warum es dieses Werkzeug gibt
-----------------------------
Die Wahl des Transkriptionswegs soll nicht geraten sein. Dieses Werkzeug
schickt DIESELBE Aufnahme nacheinander an mehrere Kandidaten und stellt die
Ergebnisse nebeneinander - so laesst sich am eigenen Sprachmaterial
entscheiden, wer am besten passt.

Kandidaten (alle mit Zero-Data-Retention-Policy, bis auf die Groq-Referenz):
  * Groq direkt      whisper-large-v3          Referenz: schnellster Weg, US
  * OpenRouter       whisper-large-v3          ZDR, ausgefuehrt bei DeepInfra
  * OpenRouter       whisper-large-v3-turbo    ZDR, schneller, etwas schwaecher
  * OpenRouter       voxtral-mini-transcribe   ZDR, Mistral - EU (Frankreich)
  * OpenRouter       nova-3                    ZDR, Deepgram - stark bei Genuschel
  * OpenRouter       voxtral-small-24b-2507    ZDR, EU, ueber den Audio-Chat-Weg

Datenschutz
-----------
Die Aufnahme liegt ausschliesslich im temporaeren Ordner und wird am Ende
geloescht. Sie wird nicht archiviert, nicht protokolliert und nicht ins
Repository geschrieben.

Aufruf
------
    py -3.12 windows/stimmvergleich.py                 # 20 s aufnehmen
    py -3.12 windows/stimmvergleich.py -s 30           # 30 s aufnehmen
    py -3.12 windows/stimmvergleich.py -d probe.wav    # vorhandene Datei nutzen
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from openai import OpenAI

import typefree

PROJEKT = Path(__file__).resolve().parent.parent
ABTASTRATE = 16000


def schluessel_lesen() -> dict[str, str]:
    """Liest die Schluessel aus der Projekt-.env. Werte werden nie ausgegeben."""
    env: dict[str, str] = {}
    pfad = PROJEKT / ".env"
    if not pfad.exists():
        return env
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if "=" in zeile and not zeile.strip().startswith("#"):
            name, wert = zeile.split("=", 1)
            env[name.strip()] = wert.strip()
    return env


def aufnehmen(sekunden: int, ziel: Path) -> None:
    """Nimmt ueber das Standardmikrofon auf und schreibt eine WAV-Datei."""
    import sounddevice as sd
    import soundfile as sf

    print(f"\nAufnahme laeuft - sprich jetzt {sekunden} Sekunden lang,")
    print("so wie du sonst diktierst (ruhig schnell und undeutlich).\n")
    for rest in range(sekunden, 0, -1):
        print(f"  {rest:>3} s ...", end="\r", flush=True)
        if rest == sekunden:
            audio = sd.rec(int(sekunden * ABTASTRATE), samplerate=ABTASTRATE, channels=1, dtype="int16")
        time.sleep(1)
    sd.wait()
    print("  fertig.                  ")
    sf.write(str(ziel), audio, ABTASTRATE, subtype="PCM_16")


def ueber_openrouter_transkription(klient: OpenAI, modell: str, pfad: Path) -> tuple[float, str]:
    t0 = time.monotonic()
    with open(pfad, "rb") as fh:
        ergebnis = klient.audio.transcriptions.create(
            model=modell, file=fh, language="de", extra_body={"provider": {"zdr": True}}
        )
    return time.monotonic() - t0, ergebnis.text.strip()


def ueber_groq(klient: OpenAI, pfad: Path) -> tuple[float, str]:
    t0 = time.monotonic()
    with open(pfad, "rb") as fh:
        ergebnis = klient.audio.transcriptions.create(model="whisper-large-v3", file=fh, language="de")
    return time.monotonic() - t0, ergebnis.text.strip()


def ueber_scribe(schluessel: str, pfad: Path) -> tuple[float, str]:
    """ElevenLabs Scribe v2 — nutzt genau den Code der App, Keyterms inklusive."""
    with open(pfad, "rb") as fh:
        puffer = io.BytesIO(fh.read())
    puffer.name = "audio.wav"
    t0 = time.monotonic()
    text = typefree._transkribiere_scribe(
        schluessel, "scribe_v2", puffer, typefree.FACH_VOKABULAR,
        "https://api.elevenlabs.io/v1")
    return time.monotonic() - t0, text


def ueber_openrouter_chat(schluessel: str, modell: str, pfad: Path) -> tuple[float, str]:
    """Audio ueber den Chat-Weg (input_audio) - fuer Modelle ohne Transkriptions-Endpunkt."""
    b64 = base64.b64encode(pfad.read_bytes()).decode()
    nutzlast = {
        "model": modell,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Transkribiere diese deutsche Sprachaufnahme wörtlich und vollständig. "
                            "Gib nur den transkribierten Text zurück, ohne Kommentar."
                        ),
                    },
                    {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}},
                ],
            }
        ],
        "temperature": 0,
        "provider": {"zdr": True},
    }
    anfrage = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(nutzlast).encode(),
        headers={"Authorization": f"Bearer {schluessel}", "Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    antwort = json.load(urllib.request.urlopen(anfrage, timeout=180))
    text = (antwort["choices"][0]["message"].get("content") or "").strip()
    return time.monotonic() - t0, text


def main() -> int:
    zerleger = argparse.ArgumentParser(description="Transkriptionsmodelle an einer Aufnahme vergleichen")
    zerleger.add_argument("-d", "--datei", help="vorhandene Audiodatei statt Mikrofonaufnahme")
    zerleger.add_argument("-s", "--sekunden", type=int, default=20, help="Aufnahmedauer in Sekunden (Standard: 20)")
    argumente = zerleger.parse_args()

    schluessel = schluessel_lesen()
    if not schluessel.get("OPENROUTER_API_KEY"):
        print("FEHLER: OPENROUTER_API_KEY fehlt in der Projekt-.env")
        return 1

    or_klient = OpenAI(api_key=schluessel["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1")
    groq_klient = None
    if schluessel.get("GROQ_API_KEY"):
        groq_klient = OpenAI(api_key=schluessel["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")

    aufraeumen = None
    if argumente.datei:
        probe = Path(argumente.datei)
        if not probe.exists():
            print(f"FEHLER: {probe} nicht gefunden")
            return 1
    else:
        probe = Path(tempfile.gettempdir()) / "typefree_stimmprobe.wav"
        aufraeumen = probe
        aufnehmen(argumente.sekunden, probe)

    groesse = probe.stat().st_size
    print(f"\nProbe: {probe}  ({groesse} Bytes)\n")
    print("=" * 100)

    kandidaten: list[tuple[str, str, object]] = []
    if schluessel.get("ELEVENLABS_API_KEY"):
        kandidaten.append(("ElevenLabs", "scribe_v2 mit Keyterms",
                           lambda: ueber_scribe(schluessel["ELEVENLABS_API_KEY"], probe)))
    if groq_klient is not None:
        kandidaten.append(("Groq direkt", "whisper-large-v3 (US)", lambda: ueber_groq(groq_klient, probe)))
    kandidaten += [
        ("OpenRouter", "whisper-large-v3 (ZDR)", lambda: ueber_openrouter_transkription(or_klient, "openai/whisper-large-v3", probe)),
        ("OpenRouter", "whisper-large-v3-turbo (ZDR)", lambda: ueber_openrouter_transkription(or_klient, "openai/whisper-large-v3-turbo", probe)),
        ("OpenRouter", "voxtral-mini-transcribe (EU, ZDR)", lambda: ueber_openrouter_transkription(or_klient, "mistralai/voxtral-mini-transcribe", probe)),
        ("OpenRouter", "nova-3 (ZDR)", lambda: ueber_openrouter_transkription(or_klient, "deepgram/nova-3", probe)),
        ("OpenRouter", "voxtral-small (EU, ZDR, Chat-Weg)", lambda: ueber_openrouter_chat(schluessel["OPENROUTER_API_KEY"], "mistralai/voxtral-small-24b-2507", probe)),
    ]

    ergebnisse = []
    for anbieter, modell, aufruf in kandidaten:
        try:
            dauer, text = aufruf()
            ergebnisse.append((anbieter, modell, dauer, text, None))
        except urllib.error.HTTPError as fehler:
            ergebnisse.append((anbieter, modell, 0.0, "", f"HTTP {fehler.code}: {fehler.read()[:120].decode('utf-8', 'replace')}"))
        except Exception as fehler:  # noqa: BLE001 - ein Kandidat darf das Werkzeug nicht anhalten
            ergebnisse.append((anbieter, modell, 0.0, "", f"{type(fehler).__name__}: {fehler}"))

    for anbieter, modell, dauer, text, fehler in ergebnisse:
        print(f"\n### {anbieter} - {modell}")
        if fehler:
            print(f"    FEHLER: {fehler}")
            continue
        print(f"    {dauer:.2f} s | {len(text)} Zeichen")
        print(f"    {text}")

    print("\n" + "=" * 100)
    print(f"{'Anbieter':<14}{'Modell':<40}{'Zeit':>8}  Zeichen")
    for anbieter, modell, dauer, text, fehler in ergebnisse:
        if fehler:
            print(f"{anbieter:<14}{modell:<40}{'--':>8}  Fehler")
        else:
            print(f"{anbieter:<14}{modell:<40}{dauer:>7.2f}s  {len(text)}")

    if aufraeumen is not None and aufraeumen.exists():
        aufraeumen.unlink()
        print(f"\nAufnahme geloescht: {aufraeumen}")
    print("\nVergleiche die Transkripte: Wer hat deine Fachwoerter und Verschleifungen richtig?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
