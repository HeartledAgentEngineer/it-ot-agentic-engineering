# Referenzaudio für Sprachmessungen

`de_referenz.wav` — 69,7 s deutscher Text, 16 kHz mono PCM (genau das Format,
das typeFREE aufnimmt), bekannt gesprochen von einer deutschen Neural-Stimme.
Der Wortlaut steht in `de_referenz.txt`; `windows/sprachmessung.py` misst damit
die Wortfehlerquote:

```
py -3.12 windows/sprachmessung.py -d windows/referenzaudio/de_referenz.wav --happen 25
```

## Wie die Datei entstanden ist

```bash
uv venv tf_tts --python 3.12
uv pip install --python tf_tts/Scripts/python.exe edge-tts
# Text aus de_referenz.txt mit edge_tts, Stimme de-DE-KatjaNeural, rate +5%
ffmpeg -y -i de_referenz.mp3 -ac 1 -ar 16000 -c:a pcm_s16le de_referenz.wav
```

## Sprechprobe (Vorlesetext)

`de_kurz.txt` ist kein Referenzaudio, sondern ein **Vorlesetext** für eine
Messung an Sebastians echter Stimme: zweimal laut vorlesen (einmal normal,
einmal so schnell wie möglich) und beide Diktate ins typeFREE-Log schreiben.
Danach die Wortfehlerquote aus dem Log gegen diesen Wortlaut rechnen — die
Rohläufe stehen als `Erkannt (…)` in `typefree.log`:

```python
import sprachmessung
sprachmessung.wortfehlerquote(erkannt_aus_dem_log, open('de_kurz.txt').read())
```

Der Text enthält absichtlich Fachwörter (Repository, Commit, Branch, Rebase,
Ticket, Board) und am Ende ein langes Kompositum („Vertragsverlängerung") —
die Stelle, an der Whisper im Betrieb zu raten anfängt.

## Messstand 25.09.2026 (Groq `whisper-large-v3`, Kern-Vokabular)

| Aufnahme | Wortfehler |
|---|---|
| 69,7 s am Stück | **4,0 %** |
| in 3 Happen (24/24/22 s) mit vorherigem Text als Kontext | **3,4 %** |
| 37,8 s, derselbe Satz wie ein echtes Diktat, normale Sprechweise | **0,0 %** |
| derselbe Satz 30 % schneller | 1,2 % |
| derselbe Satz 30 % schneller und 35 % leiser | 0,0 % |

Ergebnis der Messreihe: Länge und Sprechweise sind **nicht** die Ursache für
sinnlose Wörter am Ende eines Diktats — Happen bringen praktisch nichts
(0,6 Prozentpunkte, im Rauschen). Die Ursache liegt in der Aufnahme an der
jeweiligen Stelle selbst; deshalb protokolliert typeFREE seit dem 25.09.2026
den Pegel jeder Aufnahme (`Aussteuerung: Spitze … · RMS …`) und warnt unter
RMS 0,02. Referenzpegel fehlerfreier Aufnahmen: RMS 0,088 bis 0,095, leise aber
noch fehlerfrei 0,062.
