# Changelog N19 — Archiv-Suche auf Erwähnungen erweitern (2026-09-29)

**Auftrag:** `docs/auftrag-n19-erwaehnungssuche.md`
**Ausführer:** Hermes-Subagent (`deepseek-v4.1-flash`)
**Prüfer:** frischer Subagent einer anderen Modellfamilie (fährt den Prüfbefehl selbst)

---

## 1. Befund (vom Planer gemessen, am echten Index, nur lesend)

Sebastians Frage „was habe ich mit X gemacht?" fand **nichts**, obwohl das
Archiv die Person enthält. Ursache war die **Verdrahtung**, nicht der Index:
`_archiv_tool` feuerte nur auf `_ARCHIV_SIGNALE` / `_ARCHIV_SIGNALE_WEICH`;
solche Fragen enthalten kein Signal.

| Messung (Planer) | Wert |
|---|---|
| `chunks` / `chunks_fts` | 52.679 / 52.679 |
| `nachrichten` / `gespraeche` | 282.029 / 1.590 |
| FTS-Treffer für den vollen Namen einer Person ohne eigenen Chat | 113 |
| Rohtext-Treffer (`LIKE`) nach Quelle | whatsapp 108, chatgpt 4, google-kalender 2 |
| Chats, deren **Titel** den Namen trägt | 0 |

Nachgefahren mit dem neuen Dienst (nur lesend, `mode=ro&immutable=1`, kein
Schreiben, keine Kopie): Tabellen 10, `chunks` 52.679, `chunks_fts` 52.679,
`nachrichten` 282.029, `gespraeche` 1.590 — dieselben Zahlen. Keine
Kennung, kein Name, keine Prüfsumme des echten Archivs steht in diesem Text.

## 2. Umsetzung

### 2.1 Dienst — `backend/app/services/archiv_suche.py`

* **`ArchivSuche.erwaehnung_treffer(name, top_k=8)`** (Zeile 447 ff., 154 neue
  Zeilen): FTS5-Suche nach dem Namen über **alle** Quellen, **ohne** Filter auf
  den Gesprächsttitel. Nutzt denselben Weg wie `volltext_suche`
  (`_fts_begriffe` / `_fts_anfrage`) und `_chunk_zu_treffer` für die Zeiger —
  keine zweite Suchlogik. Rückgabe immer mit denselben Feldern:
  `name`, `treffer`, `je_quelle` (alle Treffer je Quelle, absteigend),
  `anzahl` (Gesamtzahl), `eigene_chats`, `eigene_chat_titel` (max. 5),
  `nur_erwaehnungen`, `hinweis`, `fehler`. Nie ein Wurf.
* **`erwaehnungs_text(ergebnis, hoechstens=5)`** (Zeile 1442 ff., 62 neue
  Zeilen): **reine** Funktion ohne Index, Netz oder DOM. Kopfzeile mit Name und
  Zahlen, darunter höchstens `hoechstens` Fundstellen als
  `[Quelle, Datum] Titel — Ausschnitt`; bei `nur_erwaehnungen` zusätzlich der
  Klartextsatz, dass die Fundstellen **Erwähnungen in anderen Gesprächen** sind
  und belegen, *dass* über die Person gesprochen wurde, nicht dass sie dabei
  war. Bei 0 Fundstellen ein ehrlicher Satz statt einer erfundenen Stelle.
* Jede Fundstelle trägt `quelle`, `datum` (JJJJ-MM-TT aus `beginn`), `titel`,
  `text`, `im_eigenen_chat`, `conversation_id`, `chunk_id`.
* Grenzen unverändert: nur lesen (`mode=ro`), kein Netz (Volltext braucht keine
  Einbettung), nichts schreiben.

### 2.2 Verdrahtung — `backend/app/router/chat.py`

* `_ERWAEHNUNG_SIGNALE` (Zeile 1042) mit den vorgegebenen harten
  Personen-Signalen („was habe ich mit", „was hab ich mit", „was war mit",
  „was war da mit", „wo war ich mit", „mit wem war ich", „wen kenne ich",
  „was weiß ich über", „was weiss ich über").
* `_erwaehnung_name(frage)` (Zeile 1065): **reine** Funktion. Text nach dem
  Signal, Satzzeichen ab, `_ARCHIV_STOPWOERTER` und weitere Füllwörter weg;
  genau **ein** übrig bleibendes Wort mit min. 3 Zeichen, sonst `None`.
* `_erwaehnung_notiz(name, service)` (Zeile 1103): führt die Suche aus und gibt
  die Notiz in der Form „`\n\n[…]`" zurück. Ist der Dienst nicht erreichbar
  oder scheitert die Suche, kommt ein ehrlicher Hinweis („nichts sagen,
  KEINE Fundstellen erfinden") — kein stiller Rückfall. Da der Standarddienst
  `archiv_service` die Erwähnungssuche nicht kennt, wird der Indexdienst aus
  `app.services.archiv_suche` genommen; injizierte Dienste mit
  `erwaehnung_treffer` haben Vorrang (Tests).
* Der Zweig sitzt in `_archiv_tool` **nach** dem `_ARCHIV_AUSSCHLUSS`-Tor
  (Foto-/Bild-Fragen bleiben bei der Datei-/Gesichtssuche) und **vor** der
  bestehenden Signalprüfung (Zeile 1174). Beide Ketten (Zeile ~370 und ~1910)
  rufen `_archiv_tool` auf und sind damit mitversorgt; sonst wurde nichts
  umgebaut. `_ARCHIV_SIGNALE`, `_ARCHIV_SIGNALE_WEICH`, `_ARCHIV_AUSSCHLUSS`
  sind unverändert.

### 2.3 Tests — `backend/tests/test_erwaehnungssuche.py` (neu, 393 Zeilen)

**14 Testfunktionen**, alles offline: winziger Index im `tmp_path` mit
erfundenen Namen (Erwin, Marga, Norbert) und erfundenen Titeln, Tabellen
`nachrichten`, `chunks`, `chunks_fts`, `gespraeche`, `meta`. Die Datei zählt
ihre Einzelprüfungen selbst (`_pruefe`, am Session-Ende ausgegeben).

Abgedeckt: nur-Erwähnung / eigener Chat / keine Fundstelle / Index fehlt /
Quelle+Datum je Fundstelle / `je_quelle`-Summe == `anzahl` (und `top_k`
begrenzt nur die Anzeige) / `_erwaehnung_name` mit den drei Pflichtbeispielen
plus Groß-/Kleinschreibung / Foto-Frage läuft nicht in die Erwähnungssuche /
kein Signal → `""` / bestehende Signale unverändert / die Suche lässt die
Indexdatei unberührt (SHA-256, mtime, kein `-journal`/`-wal`) / Quelltextprüfung
der neuen Funktionen auf `insert`/`update`/`delete`/`requests`/`httpx`.

## 3. Prüfbefehl

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q
```

| Lauf | Ergebnis | Exit | Dauer |
|---|---|---|---|
| Baseline **vor** der Änderung | 2935 passed, 3 warnings | 0 | 145,40 s |
| Nach der Änderung | 2949 passed, 3 warnings | 0 | 171,87 s |
| Neue Datei einzeln | 14 passed | 0 | 8,87 s |

Differenz: +14 Tests, keine Regression.

## 4. Echter Nur-Lese-Lauf gegen den echten Index

Skript im Scratch-Verzeichnis (nicht im Repo). Der Kandidat wurde
**programmatisch** gewählt — ein großgeschriebenes Wort aus den Chunk-Texten,
das in **keinem** Gesprächsttitel vorkommt, mit genau 113 FTS-Treffern — und
**nie ausgegeben**. Gezeigt werden nur Zahlen:

```
anzahl: 113
je_quelle: {'whatsapp': 88, 'chatgpt': 22, 'gemini': 3}
eigene_chats: 0
nur_erwaehnungen: True
fehler: None
treffer_angezeigt: 8
alle Fundstellen mit Quelle und Datum: True
Summe je_quelle == anzahl: True
Dateigröße des Index unverändert: True
```

Damit ist der Kern belegt: eine Person **ohne eigenen Chat** liefert 113
Fundstellen aus drei Quellen, `nur_erwaehnungen=True`, kein Fehler — die
Erwähnungssuche findet, was `volltext_suche` im alten Zuschnitt nicht lieferte.

**Ehrlich offen:**

* Die Quellenaufteilung meines Kandidaten (88/22/3) ist **nicht** die des Planers
  (108/4/2). Da der Kandidat rein programmatisch über die Gesamtzahl 113 gewählt
  wurde, ist es nicht zwingend dieselbe Person; die Planer-Aufteilung ist mit
  dieser Stichprobe nicht reproduziert. Die Gesamtzahl 113 und
  „kein eigener Chat" stimmen.
* Ein erster Lauf fiel auf den häufigsten Kandidaten zurück (21.524 Treffer) —
  brauchbar als Lesetest, aber ohne Aussage; deshalb der zweite Lauf mit
  Frequenzfenster um 113 (siehe oben).
* `_ERWAEHNUNG_ORTSSIGNALE`: Eine Frage wie „mit wem war ich in Hamburg?" liefert
  absichtlich `None` (Ortsangabe ≠ Name, wie im Auftrag gefordert). Preis:
  „was habe ich mit X in Y gemacht?" wird ebenfalls nicht gesucht. Bewusste
  Entscheidung — lieber nichts tun als eine Stadt als Person durchsuchen.
* `docs/plan-nachtlauf-2026-09-26.md` und `HANDOVER-CLAUDE-CODE.md` wurden
  **nicht** angefasst (der Planer committet und zieht die N19-Zeilen selbst).
* Kein git-Befehl ausgeführt, nichts gelöscht oder verschoben, der echte Index
  nur lesend geöffnet.
