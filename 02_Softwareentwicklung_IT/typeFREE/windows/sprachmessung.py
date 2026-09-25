"""Wortfehlerquote gegen bekannten Text messen.

Anlass (25.09.2026): Im Betriebslog häuften sich sinnlose Wörter am Ende von
Diktaten („Brother 1", „Buster Brauch", „im Kauf mit"). Verdächtigt wurden
zuerst die Länge der Aufnahme, dann die Sprechweise. Beides ließ sich mit
diesem Werkzeug widerlegen — sauberes deutsches Referenzaudio von 70 Sekunden
kam auf 4,0 % Wortfehler, in 25-Sekunden-Happen sogar 3,4 %, und dieselbe
Passage mit 30 % schnellerem, 35 % leiserem Sprechen und vielen Füllwörtern auf
0,0 bis 1,2 %. Ursache ist also die Aufnahme an der fraglichen Stelle selbst.

Aufruf (Schlüssel aus der Projekt-.env, sie werden nie ausgegeben):
    py -3.12 windows/sprachmessung.py -d referenzaudio/de_referenz.wav
    py -3.12 windows/sprachmessung.py -d aufnahme.wav -t mein_text.txt
    py -3.12 windows/sprachmessung.py -d aufnahme.wav --happen 25
"""
import argparse
import difflib
import io
import os
import re
import sys
import time

import numpy as np
import soundfile as sf

import typefree

STILLE_NACHLAUF = 0.8      # Sekunden Stille, die angehängt werden können


def worte(text):
    """Wörter für den Vergleich: Kleinschreibung, Umlaute aufgelöst."""
    text = (text.lower().replace('ä', 'ae').replace('ö', 'oe')
            .replace('ü', 'ue').replace('ß', 'ss'))
    return [w for w in re.split(r'[^a-z0-9]+', text) if w]


def wortfehlerquote(erkannt, soll):
    """Anteil falscher Wörter in Prozent — reine Funktion.

    Verglichen werden die Wörter der Referenz mit den erkannten; gleiche Blöcke
    zählen als richtig (SequenceMatcher). 0 % heißt: jedes Wort stimmt.
    """
    referenz, gefunden = worte(soll), worte(erkannt)
    if not referenz:
        return 0.0
    gleich = sum(block.size for block in difflib.SequenceMatcher(
        None, referenz, gefunden).get_matching_blocks())
    return 100.0 * (len(referenz) - gleich) / len(referenz)


def als_wav(daten, rate):
    """Audiodaten als WAV-Puffer, wie stop_and_transcribe ihn übergibt."""
    puffer = io.BytesIO()
    sf.write(puffer, daten, rate, format='WAV', subtype='PCM_16')
    puffer.seek(0)
    puffer.name = 'audio.wav'
    return puffer


def stillste_stelle(daten, rate, ziel, suchweite=1.5):
    """Letzte leise Stelle vor `ziel` (Sekunden) — dort schneiden, nicht ins Wort."""
    von = int(max(0.0, ziel - suchweite) * rate)
    bis = int(min(len(daten) / rate, ziel) * rate)
    if bis - von < rate // 10:
        return int(ziel * rate)
    block = daten[von:bis]
    schritt = int(0.05 * rate)
    bestes, beste_energie = bis - von, None
    for i in range(0, max(1, len(block) - schritt), schritt):
        energie = float(np.sqrt(np.mean(np.square(block[i:i + schritt]))))
        if beste_energie is None or energie < beste_energie:
            beste_energie, bestes = energie, i + schritt // 2
    return von + bestes


def in_happen(daten, rate, grenze):
    """Schnittstellen für Happen mit höchstens `grenze` Sekunden."""
    stellen, start = [], 0
    while (len(daten) - start) / rate > grenze:
        schnitt = stillste_stelle(daten, rate, start / rate + grenze)
        stellen.append((start, schnitt))
        start = schnitt
    stellen.append((start, len(daten)))
    return stellen


def transkribiere(daten, rate, clients, kette, vokabular=None, kontext=''):
    """Ein Aufruf über die Anbieterkette — Vokabular wie im Betrieb."""
    vokabular = typefree.WHISPER_VOKABULAR if vokabular is None else vokabular
    hinweis = f'{kontext} {vokabular}'.strip()[:700]
    text, anbieter = typefree._kette_durchlaufen(als_wav(daten, rate), clients,
                                                 kette, hinweis)
    return text, anbieter


def eigene_clients():
    """Clients für Werkzeugläufe — die App baut ihre eigenen erst beim Start.

    `typefree.transkriptions_clients()` liefert außerhalb der App nur `None`:
    `main()` setzt die Modulvariablen. Ein Werkzeug muss sie deshalb selbst
    bauen — und vorher die .env lesen, sonst fehlen die Schlüssel.
    """
    typefree.load_env_file()
    return {
        'voxtral': typefree.baue_client('https://openrouter.ai/api/v1',
                                        os.environ.get('OPENROUTER_API_KEY')),
        'groq': typefree.baue_client('https://api.groq.com/openai/v1',
                                     os.environ.get('GROQ_API_KEY')),
        'openai': typefree.baue_client('https://api.openai.com/v1',
                                       os.environ.get('OPENAI_API_KEY')),
    }


def main():
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument('-d', '--datei', required=True, help='WAV-Datei')
    zerleger.add_argument('-t', '--text', help='Referenztext (sonst gleichnamige .txt)')
    zerleger.add_argument('--weg', default=None, help='Transkriptionsweg (eu|beste|schnell)')
    zerleger.add_argument('--happen', type=float, default=0.0,
                          help='zusätzlich in Happen dieser Länge messen')
    args = zerleger.parse_args()

    daten, rate = sf.read(args.datei, dtype='float32')
    if daten.ndim > 1:
        daten = daten.mean(axis=1)
    soll = args.text
    if soll is None:
        pfad = re.sub(r'\.wav$', '.txt', args.datei, flags=re.IGNORECASE)
        try:
            with open(pfad, encoding='utf-8') as datei:
                soll = datei.read().strip()
        except OSError:
            print(f'Kein Referenztext gefunden ({pfad}) — es wird nur ausgegeben.')
            soll = ''

    kette = typefree.KETTEN[args.weg or typefree.transkription_wahl()]
    clients = eigene_clients()
    print(f'Datei: {args.datei} · {len(daten) / rate:.1f} s · {rate} Hz')
    print('Weg  : ' + ', '.join(name for name, _, _, _ in kette))

    fehlend = [name for name, _, _, _ in kette if clients.get(name) is None]
    if fehlend:
        print('\nAbbruch: kein Schlüssel für ' + ', '.join(fehlend)
              + ' — bitte in der .env setzen (die Werte werden nie ausgegeben).')
        return 1

    begonnen = time.monotonic()
    text, anbieter = transkribiere(daten, rate, clients, kette)
    dauer = time.monotonic() - begonnen
    print(f'\nAnbieter: {anbieter} in {dauer:.1f} s')
    if soll:
        print(f'Wortfehler: {wortfehlerquote(text, soll):.1f} % '
              f'({len(worte(soll))} Wörter Referenz)')
    print(f'Erkannt: {text}')

    if args.happen:
        stellen = in_happen(daten, rate, args.happen)
        print(f'\nHappen ({len(stellen)}): '
              + ', '.join(f'{bis / rate:.1f}s' for _, bis in stellen))
        texte, begonnen = [], time.monotonic()
        for von, bis in stellen:
            teil, _ = transkribiere(daten[von:bis], rate, clients, kette,
                                    kontext=' '.join(texte)[-200:])
            texte.append(teil)
        zusammen = ' '.join(texte)
        print(f'Anbieter in {time.monotonic() - begonnen:.1f} s')
        if soll:
            print(f'Wortfehler: {wortfehlerquote(zusammen, soll):.1f} %')
        print(f'Erkannt: {zusammen}')


if __name__ == '__main__':
    sys.exit(main())
