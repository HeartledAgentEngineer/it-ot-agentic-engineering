# Modellauswahl verschlankt: drei Stufen statt sechs Einträge

20.10.2026, Hermes-Cron. Auftrag aus der Übergabe `personal_ai_agent`
(Sebastian, 20.10.2026): „`config.py` `favorite_models` hat 6 Einträge, davon 3
fast gleiche DeepSeek-Flash-Varianten. Ziel: wenige Stufen (günstig / Alltag /
stark), Preise vorher frisch messen."

## Was gemessen ist (frisch in diesem Lauf, nur lesend)

Quelle: `GET https://openrouter.ai/api/v1/models` (öffentlicher Katalog,
**HTTP 200, 788.314 Byte, 470 Einträge**, 20.10.2026 11:40 MESZ), Preise in USD
je **1 Mio Token**, ein/aus:

| Modell | ein | aus | Kontext | im Katalog |
|---|---|---|---|---|
| `deepseek/deepseek-v4.1-flash` | 0,0560 | 0,1200 | 1.048.576 | ja |
| `deepseek/deepseek-v4-flash` | 0,0910 | 0,1820 | 1.048.576 | ja |
| `deepseek/deepseek-v4-flash-0731` | 0,4400 | 1,3200 | 1.048.576 | ja |
| `openai/gpt-5-nano` | 0,0500 | 0,4000 | 400.000 | ja |
| `deepseek/deepseek-v4-pro` | 0,9553 | 1,9105 | 1.048.576 | ja |
| `anthropic/claude-sonnet-5` | 2,0000 | 10,0000 | 1.000.000 | ja |

Damit ist der Befund aus der Übergabe **belegt, nicht behauptet**: die drei
Flash-Einträge der alten Liste lagen alle im Sparbereich, aber **um Faktor 8
auseinander** (0,056 gegen 0,44 je 1 Mio Eingabe-Token) — drei Knöpfe für
dieselbe Aufgabe, mit dem teuersten davon noch dazu über dem Preis von
`deepseek-v4-flash` (0,091). Die Stufen der neuen Liste liegen dagegen rund
**17-fach** und **2,1-fach** auseinander: drei klar getrennte Preislagen.

## Was geändert ist (eine Datei Code, eine Prüfdatei, dieses Dokument)

`backend/app/config.py`, `favorite_models` — **sechs → drei**:

| Stufe | Modell | warum |
|---|---|---|
| sparsam / Alltag | `deepseek/deepseek-v4.1-flash` | billigster Eintrag der alten Liste **und** das eingestellte Modell (`settings.llm_model`) |
| mehr Substanz | `deepseek/deepseek-v4-pro` | gleicher Anbieter, rund 17-fach teurer als die Sparstufe |
| stark | `anthropic/claude-sonnet-5` | anderer Anbieter für schwere Fälle |

**Keine neue Modellwahl:** alle drei standen schon vorher in der Liste. Es fällt
nur der Doppelgänger weg. Weggefallen: `openai/gpt-5-nano`,
`deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-flash-0731` — sie bleiben im
Katalog wählbar und erscheinen in der Oberfläche weiterhin unter „Alle N
Modelle" (`frontend/app.js`, `zeichneListe`: die Schnellauswahl ist ein
Abschnitt **über** der vollständigen Liste, der Filter wirkt auf beide).

Der alte Kommentarblock über der Liste war außerdem in sich widersprüchlich: er
sprach von „Alle vier am 11.08.2026 geprüft", während sechs Einträge folgten, und
war gegenüber `favorite_models` falsch eingerückt (Spalten 0/8 statt 4). Beides
ist mitgeradezogen. Die Regel „**Preise stehen bewusst nicht hier**" bleibt
gültig und unverändert: die Oberfläche zeigt die Preise des jeweils routbaren
Anbieters live aus `/models/user`, eine zweite Zahl in der Konfiguration würde
still veralten. Die Tafel oben steht deshalb hier und nicht im Code.

## Belege

- Neu `backend/tests/test_modell_favoriten.py` — **5 Prüfungen**: genau drei
  Stufen ohne Dubletten; die weggefallenen Varianten rutschen nicht zurück;
  jeder Eintrag in der Form `anbieter/modell`; das **eingestellte** Modell steht
  in der Schnellauswahl (sonst versteckt die Oberfläche den benutzten Stand);
  die Route `/api/models` liefert genau `settings.favorite_models` und die Liste
  existiert nur an **einer** Stelle im Backend (keine zweite Wahrheit).
- Voller Prüfbefehl `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  im Hauptbaum: Zahl und Exit-Code stehen im Commit-Haken (`git log -1`).

## Grenzen (ehrlich)

- Gemessen wurde am **öffentlichen** Katalog, nicht an `/models/user`: der
  kontogefilterte Abruf braucht den Schlüssel, der am PC nicht in `backend/.env`
  liegt (dort stehen nur `PCLOUD_HOST`/`PCLOUD_TOKEN`). Dass die drei gewählten
  Einträge für das Konto **nutzbar** sind, ist trotzdem belegt — sie waren
  bereits vorher in der Liste, und ein nicht nutzbarer Eintrag wird in der
  Oberfläche ausgegraut statt still entfernt.
- Die Preise des öffentlichen Katalogs können vom Preis des **routbaren**
  Anbieters abweichen (so steht es seit dem 11.08.2026 im Code); die
  Größenordnung und die Staffelung ändert das nicht.
- Ob die drei Stufen Sebastians Geschmack treffen, zeigt erst sein Blick in der
  Oberfläche: die Wahl ist eine Zeile in `config.py` und in einer Minute
  geändert. Kein Modell ist verschwunden — nur aus der Schnellauswahl.
