# Ergebnisprüfung Websuche-Sperre, Runde 2 (Hermes) — 14.10.2026

Prüfauftrag: Vorlage `.hermes/plans/2026-10-14_websuche-ergebnis-pruefung.md`.
Gegenstand: Commit `b09c5cf` und die Nachbesserungen zu den zwei Einwänden der
Codex-Ergebnisprüfung Runde 1 (`.hermes/pruefkreis/websuche-persoenlich-ergebnis.md`).
Geprüft wurde die Fassung im Arbeitsbaum; sie ist während dieser Prüfung unverändert als
Commit `3431526` festgeschrieben worden (identisch, `git status` zeigt die Dateien danach
unverändert) — die Prüfung bezieht sich also auf genau diesen Stand.
Rolle: Hermes als zweiter Prüfer (AGENTS.md, Abschnitt „Rollen und Datenschutz im
Agenten-Workflow"). Es wurde nichts geändert und nichts freigegeben — nur gemessen.

Prüfart: Code gelesen, echte Tests ausgeführt, eigene Prüfsonde gegen die echten Funktionen
(`app/services/websuche_schutz.py`) — kein Netzaufruf, kein Modellaufruf, kein Bild geöffnet.
Testnamen sind erfunden („Ida Testmann", „Bodo Beispiel").

## 1. Die zwei Einwände aus Runde 1 sind behoben (gemessen, nicht geglaubt)

**Einwand 1 — bloße Google-Erwähnung hob die Sperre auf.** Ursache war `_GOOGLE`; jetzt zählt
Google nur noch als Verb (`websuche_schutz.py:37–38`). Eigene Sonde gegen die echte Funktion:

| Eingabe | Ergebnis |
|---|---|
| „Ida Testmann nutzt Google Drive" | `off`, Grund `person` |
| „Hat Opa ein Google-Konto?" | `off`, Grund `familie` |
| „Was ist Google Fuchs?" (neutral) | `manual`, kein Grund (Suche bleibt erlaubt) |
| „Google mal Bodo Beispiel" | `manual` (Auftrag, wie gewollt) |
| „googel nach Opa Testmann" | `manual` (Auftrag, wie gewollt) |
| „Ich nutze Google Drive" (`ist_suchauftrag`) | `False` |

**Einwand 2 — persönliche Werkzeugergebnisse wurden nicht berücksichtigt.** Behoben in
`llm_service.py:893–898`: Vor jeder Runde prüft `erstellen()`, ob im Verlauf schon eine Nachricht
mit `role == "tool"` steht; dann ist die Websuche für diese und alle weiteren Runden `off`.

Belege für die Wirksamkeit:
- Der Werkzeugweg schreibt die Ergebnisse selbst als `role: "tool"` in dieselbe Liste
  (`werkzeug_schleife.py:205`, `:229`), die `erstellen()` als `verlauf` bekommt
  (`llm_service.py:892`, Aufruf `:911`) — die Prüfung greift also auf der echten Schleife.
- Test `test_nach_eigenem_werkzeug_keine_websuche_mehr` (für `auto` und `manual`) läuft grün:
  Runde 1 trägt Suchplugin bzw. Suchwerkzeug, Runde 2 nach dem Werkzeugergebnis nicht mehr.
- Die Regel „nach jedem eigenen Werkzeug ist die Websuche aus" ist belegt tragfähig: das
  Werkzeugregister hat **10 Einträge**, alle persönlich — `archiv_suchen`, `datei_ansehen`,
  `dateien_suchen`, `erinnerungen_suchen`, `fotos_mit_person`, `fotos_uebersicht`,
  `notizen_suchen`, `person_auskunft`, `personen_liste`, `wer_war_wann` (gemessen über
  `werkzeuge.REGISTER`). Es gibt kein neutrales Werkzeug, für das die Regel die Suche
  unnötig abschalten würde.
- Der Rückfall ohne Werkzeuge (`llm_service.py:839`) ist unbedenklich: er arbeitet auf der
  **Kopie** `[dict(m) for m in messages]` (`:827`), trägt also keine Werkzeugergebnisse mit.

Ausgeführte Tests (genau diese fünf Dateien, vollständig):
`test_websuche_schutz.py test_werkzeug_schleife.py test_tool_use_stream.py
test_chat_endpoint.py test_personen_werkzeuge_quiz.py` → **98 passed, 3 warnings**
(105,59 s). Der volle Prüfbefehl steht unten.

## 2. Zwei verbleibende Lücken (neu, mit Beleg) — Status EINWAND

### Lücke 1 (hoch): Angehängte Namensendungen umgehen die Namenssperre

Das Namensmuster verlangt nach dem Namen ein Nicht-Wortzeichen
(`websuche_schutz.py:60`: `(?<!\w)(…) (?!\w)`). Deutsche Genitiv- und Anhängeformen fallen
dadurch durch — gemessen an der echten Funktion:

| Eingabe (Modus `manual`) | Ergebnis | erwartet |
|---|---|---|
| „Was macht Ida Testmann beruflich?" | `off`, Grund `person` | gesperrt |
| „Was macht **Idas** Firma?" | **`manual`** | gesperrt |
| „Wo arbeitet **Bodos** Arbeitgeber?" | **`manual`** | gesperrt |
| „Wo wohnt **Testmanns** Familie?" | **`manual`** | gesperrt |
| „Wie ist **Idas** Familienstand?" | **`manual`** | gesperrt |

Dazu fehlen im Familienwortschatz (`websuche_schutz.py:28–32`) deutsche Formen wie
**„Familie"**, „Schwiegertochter", „Schwiegersohn" — gemessen: „Was macht meine Familie am
Wochenende?" und „Wo wohnt Schwiegertochter?" bleiben `manual`, während „Wie geht es
Enkelin?" über `enkel` greift.

Folge in Klartext: Eine Frage, die eine Person nur in gebeugter Form nennt und kein Bild-,
Familien- oder Vollnamenswort enthält, lässt die Websuche an — der Name geht dann an den
Suchdienst, ohne dass Sebastian das verlangt hat. Das ist dieselbe Fehlerklasse wie der
Einwand 1 aus Runde 1 und deren Ursache liegt tiefer (im Muster, nicht in `_GOOGLE`).
Vorschlag zur Behebung (nicht von mir gebaut): nach dem Namen eine kurze deutsche Endung
zulassen (`(?:s|ens|in)?` statt starrer Wortgrenze) und die Familienliste um „familie",
„schwiegertochter", „schwiegersohn", „verwandt\w*" ergänzen.

### Lücke 2 (mittel, offen — außerhalb des Planwortlauts, gleiche Wirkung)

Die Sperre prüft nur Nachricht, Verlauf und Zusammenfassung (`chat.py:1770`). Der **Systemtext
selbst** trägt aber persönlichen Inhalt, den sie nie sieht:

- gemerkte Fakten: `_build_memory_context` (`llm_service.py:436`, eingehängt `:717`),
- Archiv-Fundstellen: `_build_archiv_context` (`llm_service.py:608`, eingehängt `:723`) — bis
  zu 5 Chunks echter Gesprächsinhalte, je bis 1.200 Zeichen (`:637–640`).

Beide werden dem Aufruf getrennt übergeben (`chat.py:536`, `:540`; im Stream `:2166`, `:2170`)
und landen im System-Prompt; die Sperre bekommt sie nicht. Bei Schalter `manual` sucht das
Plugin aber **einmal je Anfrage** mit dem ganzen Prompt (`llm_service.py:517–518`), bei `auto`
gilt dasselbe für die erste Runde. Beispiel ohne jedes persönliche Merkmal in der Frage:
„Was war 2022 in Österreich los?" — Buchwort, Familienwort und Personenname fehlen, die
Websuche bleibt an.
**Ehrliche Grenze dieser Messung:** dass der suchdienst-seitige Plugin-Weg den Systemtext
mitliest, ist hier **nicht gemessen** (dafür wäre ein echter Suchaufruf nötig, und der gehört
nicht in einen Nachtlauf). Belegt ist, dass die Sperre diese Quelle nicht prüft, obwohl sie
persönlichen Inhalt enthält. Entscheidung darüber ist Sache des Masters bzw. Sebastians.

## 3. Beobachtung ohne Fund (bewusst so belassen)

Nachrichten mit `role: "assistant"` im übertragenen Verlauf werden nicht geprüft (gemessen:
„zeig mehr davon" bei einer Assistenten-Antwort mit Personenfotos bleibt `manual`). Das
entspricht dem freigegebenen Plan (Fassung 4: „gesamter übertragener Nutzerverlauf") und wird
deshalb nicht als Fehler gewertet — nur notiert.

## 4. Prüfbefehl und Grenzen dieses Laufs

- Genaue Testmenge dieses Laufs: siehe Abschnitt 1 (98 passed) und der volle Prüfbefehl:
  `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **4181 passed, 2 skipped,
  3 warnings, Exit 0** (640,54 s), frisch und vollständig in diesem Lauf ausgeführt.
  Gegenprobe (keine Regression): der Vorlauf meldete 4130 passed; die neuen Websuche-Tests
  machen genau die Differenz von 51 aus (4130 + 51 = 4181).
- Nichts geändert, nichts freigegeben, nichts gelöscht. Kein Netzaufruf, kein Modellaufruf,
  kein Bild geöffnet, keine Kosten, kein Geräteeingriff.
- Der Befund ist ausdrücklich **kein** Freibrief: Die Sperre wirkt nur, wenn die Personenliste
  gelesen werden kann (`werkzeuge.bekannte_namen()`, `werkzeuge.py:415`; bei fehlender
  Quizdatei Rückfall auf den alten Katalog, `:399–413`) und wenn ein Name überhaupt bekannt
  ist. Unbenannte Gruppen schützen nichts, weil ihr Name unbekannt ist.

URTEIL: EINWAND (zwei belegte Lücken; die Nachbesserungen zu Runde 1 sind wirksam).
