# Kosten-Wächter: jeder Modell-Aufruf einzeln protokolliert

**Angelegt:** 06.10.2026 · **Grund:** Tageswerte pro Chat waren nur schätzbar, nie exakt.

## Warum es das braucht

`state.db` speichert Kosten nur als **Summe je (Sitzung, Modell, Aufgabe) über die
gesamte Laufzeit**. Es gibt **keine Tagesspalte**, `messages.token_count` ist
durchgängig 0, und die Request-Dumps enthalten keine Nutzungsdaten (alles am
06.10.2026 nachgemessen). Jeder Tageswert war deshalb eine Schätzung — und
Schätzungen waren entweder 0,00 € oder vielfach zu hoch.

## Was gebaut ist

### 1. Aufruf-Protokoll (das Hintergrundprogramm)

| | |
|---|---|
| Ort | `%LOCALAPPDATA%\hermes\plugins\kosten-protokoll\` |
| Art | echtes Hermes-Plugin (kein Eingriff in Hermes-Quellcode → updatefest) |
| Haken | `post_api_request`, `post_auxiliary_call`, `api_request_error` |
| Ablage | `%LOCALAPPDATA%\hermes\kosten\api_calls.jsonl` (anhangend, eine Zeile je Aufruf) |

**Eine Zeile je Aufruf enthält:** Zeitstempel, Chat-Kennung, Aufgabe/Turn, Modell
und Anbieter, **Input-, Output-, Cache-Lese-, Cache-Schreib- und Denk-Tokens**,
Gesamt-Tokens, Dauer, Zeit bis zum ersten Zeichen, Ende-Grund, Zahl der
Werkzeug-Aufrufe, Aufrufzähler des Agenten. Dazu `art` = `aufruf`,
`nebenaufruf` (Titel, Kompression, Vision, Freigabe — die fehlten bisher in jeder
Anzeige) oder `fehler`.

**Eigenschaften:** kein Netz, keine Preisrechnung und keine Datenbank im Haken —
der Haken läuft im Agenten-Loop und darf ihn nie bremsen. Jeder Fehler wird
geschluckt, der Agent läuft weiter.

Die Haken sind im Manifest als `provides_hooks` deklariert; ohne diese Angabe
lädt Hermes das Plugin, verdrahtet die Haken aber nicht.
`hermes plugins validate <Pfad>` prüft das (Soll: 13 × bestanden).

### 2. Auswerter (Tokens × Preisliste = Geld)

```
python %LOCALAPPDATA%\hermes\scripts\kosten_aus_protokoll.py                  # heute
python %LOCALAPPDATA%\hermes\scripts\kosten_aus_protokoll.py --taeglich 14    # je Tag
python %LOCALAPPDATA%\hermes\scripts\kosten_aus_protokoll.py --chat <Kennung> # ein Chat
python %LOCALAPPDATA%\hermes\scripts\kosten_aus_protokoll.py --befehle 20     # teuerste Befehle
python %LOCALAPPDATA%\hermes\scripts\kosten_aus_protokoll.py --json           # für andere Werkzeuge
```

Die Preisliste (464 Modelle) kommt von OpenRouter und wird 6 Stunden
zwischengespeichert (`kosten\preise.json`). Der Schlüssel wird nie ausgegeben.

## Betrieb

* Das Protokoll startet **mit dem Prozess**: Desktop-App und Gateway laden
  Plugins beim Start. Nach einer Änderung am Plugin also Hermes neu starten.
* Ein `Wo liegen die Daten`-Hinweis: das Protokoll ist reine Nutzungsstatistik,
  keine Chat-Inhalte.

## Warum nicht die OpenRouter-Logs

Geprüft am 06.10.2026: die Aktivitäts-API liefert **nur Tagessummen je Modell,
konto-weit** (alle Schlüssel zusammen) und **ohne Cache-Tokens**. Die
Generierungs-API (Kosten je Aufruf) braucht die Aufruf-Kennung — die schreibt
Hermes nicht mit. Der Haken im Agenten sieht dagegen *jeden* Aufruf, *mit* Cache
und *mit* Chat-Kennung. Die OpenRouter-Zahl bleibt die Kontrollgröße für „stimmt
die Summe", die Aufrufzeilen liefern die Aufteilung.
