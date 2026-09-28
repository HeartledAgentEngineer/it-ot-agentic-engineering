# Changelog N27e — Beziehungen ableiten („wer war mit wem wo")

**Datum:** 29.09.2026 · **Schritt:** N27 Schritt 5 von 5 (Verknüpfungsschicht)
**Auftrag:** `docs/auftrag-n27e-beziehungen.md`

Nur Zahlen, Kennungen und Gattungsnamen — **keine** echten Personen-, Orts-,
Chat- oder Dateinamen. Beispielwerte in Tests sind erfunden.

---

## Neue Dateien

| Datei | Zeilen |
|---|---|
| `tools/foto_sortierung/beziehungen_ableiten.py` | **1.097** |
| `backend/tests/test_beziehungen_ableiten.py` | **1.530** |
| `docs/changelog-2026-09-29-n27e-beziehungen.md` | diese Datei |

Testfunktionen (`^def test_`): **183**.

Ausgaben des Werkzeugs liegen ausschließlich außerhalb des Repos
(Standardordner `~/foto_sortierung/`): `beziehungen.jsonl` (Aussagen) und
`beziehungen.json` (Übersicht).

## Wiederverwendung statt Nachbau

* `bestaetigung_lesen` und `PersonenFehler` kommen **wörtlich** aus dem
  Nachbarmodul `personen_andocken` (Import mit Rückfall-Lader auf denselben
  Dateipfad, wie es das Nachbarmodul selbst für `personen_cluster` tut).
  Ein Test belegt die Herkunft über `__globals__["__file__"]`.
* Der Repo-Schutz ist ein eigener, kleiner Wächter (`pruefe_ausserhalb_repo`),
  weil der Beauftragte Schutz **stderr + Exit 2** verlangt, das Nachbarmodul
  aber mit `print` (stdout) arbeitet und `SystemExit` wirft. Gleiche
  Rechenregel (`abspath` + `normcase` + `commonpath`), andere Ausgabe.
* Der CLI-Zweitname `haupt = main` ist gesetzt (das Nachbarmodul heißt `main`).

## Eingaben (nur lesend, echte Dateien am 29.09.2026)

| Datei | Zeilen gelesen | defekt |
|---|---|---|
| `personen_andockung.jsonl` | **5** | 0 |
| `chat_andockung.jsonl` | **2.127** | 0 |
| `ereignisse.jsonl` | **2.127** | 0 |
| `personen_bestaetigt.json` | fehlt (0 Namen) | — |

## Gemessene Sollwerte — Zeile für Zeile erreicht

| Zählung | Soll (Planer) | Ist | Δ |
|---|---|---|---|
| Personen-Andockung · Personen-Kennungen | 12 | **12** | 0 |
| Personen-Andockung · bestätigt | 0 | **0** | 0 |
| Unterart `fotos` (Paare) | 23 | **23** | 0 |
| Unterart `gemeinsam_im_chat` (Paare) | 14.902 | **14.902** | 0 |
| Unterart `fotos_und_chat` (Paare) | 126 | **126** | 0 |
| Aussagezeilen gesamt | 15.051 | **15.051** | 0 |

Zwischenschritte der Gegenprobe (unabhängig nachgerechnet und mit dem
Werkzeug übereinstimmend): Anlässe mit ≥ 1 Person **5** (davon **2** mit genau
einer Person → keine Paar-Aussage); Anlässe mit ≥ 1 Chat **2.101**;
Chat-Andockungen **45.040**; mit ≥ 1 benannten Kontakt **23.122**; mit genau
**einem** benannten Kontakt **20.543**.

**Keine Abweichung** von den Sollwerten. Die drei Unterarten-Zahlen sind
unabhängig (nicht über das Werkzeug) nachgerechnet und stimmen exakt.

## Live-Trockenlauf (Standardpfade, `--trocken`)

```
Zeilen gelesen: Person 5 x Chat 2.127 x Ereignis 2.127   defekte Zeilen: 0
Aussagen fotos: 23   gemeinsam_im_chat: 14.902   fotos_und_chat: 126
Aussagen gesamt: 15.051
Personen-Kennungen: 12   bestaetigte Namen in der Ausgabe: 0   benannte Kontakte: 253
Datum von: 2016-05-04   bis: 2025-08-16
Anlaesse mit Foto-Personen: 3   Anlaesse mit Chat: 1.300
```

Ergebnis: Exit **0**, keine Datei geschrieben.

Übersicht (`beziehungen.json`) des Schreib-Probelaufs: `anzahl` =
`fotos` 23 · `gemeinsam_im_chat` 14.902 · `fotos_und_chat` 126;
`anzahl_personen_kennungen` 12; `anzahl_namen_bestaetigt` **0**;
`anzahl_kontakte` 253; `datum_von` 2016-05-04; `datum_bis` 2025-08-16;
Dateigröße **715 Byte**.

## Zwei Schreibläufe mit festem `--stand` — byte-gleich

Zielordner **außerhalb** des Repos, frische Ordner
(`C:/Users/sebas/foto_sortierung/n27e_probe_c` und `…_d`), beide Läufe mit
`--stand 2026-09-29T03:00:00+02:00`:

| Datei | Größe | SHA-256 (beide Läufe gleich) |
|---|---|---|
| `beziehungen.jsonl` | **12.601.994 Byte** (15.051 Zeilen + Schluss-NL) | `549eafbc59bf6e58…cbec7bfc0b99` |
| `beziehungen.json` | **715 Byte** | `083503afbb462602…ce88dcc2b` |

`cmp` meldet beide Paare als byte-gleich; keine `.tmp`-Reste. Ohne festen
`--stand` unterscheiden sich zwei Läufe ausschließlich im Feld `stand`.

## Repo-Schutz (Exit 2)

| Versuch | Ergebnis |
|---|---|
| `--ausgabe tools/foto_sortierung/beziehungen.jsonl --trocken` | Exit **2**, deutsche Meldung auf stderr, keine Datei |
| `--ausgabe … --schreiben` | Exit **2**, keine Datei im Repo |

Ungültiges Datum (`--datum 21.08.2022`) → deutsche Meldung auf stderr,
Exit **2**. `--nur-bestaetigt` ohne Bestätigungsdatei → **0** Aussagen.
`--datum 2022-08-21` → 61 Aussagen (fotos 10 · chat 6 · fotos_und_chat 45),
alle mit genau diesem Datum.

## Prüfbefehl (selbst gefahren, Projekt-venv)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
→ 2789 passed, 3 warnings  (Exit 0)
```

Baseline vor diesem Schritt: 2606 (Arbeitsbaum) · neue Tests: **183**
→ 2606 + 183 = **2789**. Die Rechnung geht genau auf.

## Auslegungen (bewusst, im Modulkopf dokumentiert)

1. **Chat-Kontakte vs. Gesichtskennungen.** Die Regel „nament niemanden" gilt
   für die Gesichtskennungen `Person_00x`: ein `name` dort **nur** aus der
   Bestätigungsdatei, sonst `null`. Chat-Kontakte tragen dagegen ihren Namen,
   weil er bereits in `chat_andockung.jsonl` aus der Kontaktzuordnung des
   Nutzers steht (nicht geraten). In der Aussagezeile sind sie als
   `kennung: null`, `name: <Name>`, `bestaetigt: true`, `bilder: 0`,
   `gesichter: 0` gekennzeichnet — der Unterschied ist damit sichtbar.
2. **„Namen in der Ausgabe: 0"** ist als `anzahl_namen_bestaetigt` umgesetzt:
   ohne Bestätigungsdatei 0 **bestätigte Personennamen**. Die Zahl der
   benannten Chat-Kontakte ist ein getrennter Zähler (`anzahl_kontakte` = 253),
   damit die beiden Bedeutungen nicht vermischt werden.
3. **Kontaktname-Filter.** `"unbekannt"`, leere Namen und Namen, die wie eine
   Nummern-Maske aussehen (Sternchen oder nur Ziffern), zählen **nicht** als
   Kontakt. Im echten Bestand greift nur der `"unbekannt"`-Filter
   (9.086 Beteiligten-Einträge); die Zahlen 45.040 / 23.122 / 20.543 / 14.902
   bleiben mit dem strengeren Filter unverändert.
4. **`fotos_und_chat` je Anlass zusammengeführt.** Nennt derselbe Anlass einen
   Kontakt in mehreren Chats, entsteht **ein** Paar je Anlass (Nachrichten
   summiert). Ohne diese Zusammenführung gäbe es Doppel-Aussagen; die 126
   Paare stimmen nur mit Zusammenführung (unabhängig nachgerechnet).
5. **Fester `--stand`** ist der einzige zeitabhängige Wert; jede Zeile trägt ihn.

## Wächter-Tests auf den Quelltext

Belegt: keine Datei-/Funktionsreferenz auf eine Kandidatenliste
(`personen_vorschlaege.json`), keine Lösch-/Verschiebefunktion (außer der
eigenen temp-Datei in `schreiben`), kein Netz- und kein Bild-Import, keine
gelesene Nummern-Maske, kein gelesener Nachrichtentext, keine
Nachrichten-Kennungen. Jede Aussagezeile trägt einen deutschen `hinweis` zur
ehrlichen Abgrenzung (Mitgliedschaft ≠ Anwesenheit, Bildnähe ≠ Beziehung).

## Prüfer-Abnahme (29.09.2026)

**Prüfer: `z-ai/glm-5.2` (frische Sitzung, andere Modellfamilie als der
Ausführer `deepseek-v4.1-flash`) — BESTANDEN, 0 Abweichungen.**
`openai/gpt-5.6-luna` war davor **zweimal** rate-limitiert (Anbieter-Limit;
`hermes` endet dann mit Exit 2, kein Repo-Fehler), deshalb das zweite im Plan
vorgesehene Prüfer-Modell.

Der Prüfer hat **selbst** gemessen (nicht geglaubt):

| Prüfung | Ergebnis |
|---|---|
| Prüfbefehl `pytest tests/ -q` | **2.789 passed, 3 warnings, Exit 0** (105 s) |
| N27e-Suite allein | **183 passed, Exit 0** (5,4 s) |
| Zeilen / Testfunktionen | **1.097 / 1.530** Zeilen, **183** Testfunktionen |
| Trockenlauf (Sollwerte Zeile für Zeile) | erreicht, keine Abweichung |
| Repo-Ziel / ungültiges Datum / fehlende Eingabe | **Exit 2 / Exit 2 / Exit 2** |
| `--nur-bestaetigt` | **0** Aussagen |
| Zwei `--schreiben`-Läufe, fester `--stand` | **byte-gleich** (12.601.994 B / 715 B, gleiche sha256), keine `.tmp`-Reste |
| Datenschutz (echte Namen in den Dateien?) | **0 Treffer** |
| Namensregel ohne Bestätigung | **172** Einträge, alle `name: null` |
| Namensregel mit Probe-Bestätigung | erfundener Name in **genau 13** Aussagen = genau denen mit `Person_001`, keine Aussage mit Namen ohne `Person_001` |
| Git | Commit `f333051` **6** Dateien, keine Fremdarbeit, **0 0**, `manifest.jsonl` fehlt |

**Grenze der unabhängigen Prüfung (kein Befund):** die Zwischenschritte
2.101 / 45.040 / 23.122 / 20.543 sind im Werkzeug-Output nicht exponiert und
waren nicht unabhängig nachrechenbar; die daraus abgeleitete Endzahl **14.902**
ist verifiziert.

**Damit ist Schritt 5 von 5 und die Verknüpfungsschicht N27 insgesamt
abgenommen.**

## Bekannte Eigenheit

Bei einem ersten Probelauf wurden MSYS-Pfade (`/c/Users/…`) an das native
Python gereicht; dabei entstand außerhalb des Repos ein Ordner
`C:/c/Users/sebas/foto_sortierung/n27e_probe_a|_b` mit 3 Dateien. Er wurde
**nicht gelöscht** (Löschverbot). Die gültigen Probeläufe `…/n27e_probe_c`
und `…_d` liegen unter dem Standardbasispfad.
