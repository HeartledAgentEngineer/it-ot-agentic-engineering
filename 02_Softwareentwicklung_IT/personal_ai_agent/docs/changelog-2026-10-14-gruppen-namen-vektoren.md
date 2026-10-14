# Gruppen, Namen und Vektoren — die vier Verständnisfragen beantwortet (14.10.2026)

**Auftrag:** `.hermes/plans/2026-10-10_personen-orte-erzaehlungen.md`, Abschnitt 5
(„Wie hängen Gruppen, Namen und Vektoren zusammen?") — Sebastian hat ausdrücklich
eine schriftliche Antwort mit **Code-Beleg** verlangt, nicht aus dem Gedächtnis.
Prüfkriterium des Plans: ein Abschnitt in der Doku beantwortet alle vier Fragen mit
Datei:Zeile.

**Diese Antwort ist reine Diagnose: nichts geändert, kein Code, kein Verhalten.**
Kein Bild geöffnet, kein Modell, kein Netz, keine Kosten, keine Geräteeingriffe.
Alle Zahlen sind am hiesigen Bestand **gemessen** (nur lesend), Stichzeitpunkt
14.10.2026 vormittags; genannt werden nur Zählungen, keine Personennamen, keine
Vektoren, keine Koordinaten.

Zwei Wege tragen in diesem Projekt Personennamen — sie sind getrennt und dürfen
nicht verwechselt werden:

| Weg | Was er kennt | Wer ihn liest |
|---|---|---|
| **Gruppenweg** (Quiz am Handy) | Gruppen als Kennung + Name | App (`gruppen_quiz.py`), PC-Lauf (`personen_gruppieren.py`) |
| **Alter Katalog** (Bild-für-Bild-Quiz) | Personen mit Referenzbildern/Embedding | nur `gesichter_service.py` |

---

## Frage 1: Wird eine Gruppe, die benannt wird, zum Referenzvektor für künftige Bilder?

**Antwort: Nein — das Benennen legt keinen Referenzvektor an.** Der Referenzvektor
der Gruppe entsteht beim **Gruppieren**, nicht beim Benennen; er ist schon da, bevor
irgendein Name fällt.

- Der Bezugspunkt einer Gruppe ist ihr **Mittelpunkt** in `kennungen.json`:
  `personen_gruppieren.py:47–48` („``kennungen.json`` — Mittelpunkte je Kennung
  (stabile Kennungen beim naechsten Lauf). **Biometrie — bleibt am PC.**"),
  geschrieben in `personen_gruppieren.py:824–827` (`kennungen()`) über
  `schreiben()` (`:809`), berechnet in `_mittelpunkte()` (`:378`) bzw.
  `_mittelpunkt()` (`:917`).
- **Gemessen (PC):** `personen_gruppen/kennungen.json` = 1.367 Einträge, **alle
  1.367 mit Mittelpunkt**.
- Das Benennen schreibt ausschließlich **Bezeichnungs- und Vorgabendateien**, nie
  Vektoren: `gruppen_quiz.py:26–35` (Ablage-Liste) und `_antwort_anwenden()`
  (`gruppen_quiz.py:1301–1380`): `personen_bestaetigt.json` (Kennung → Name, `:1313`),
  `personen_vorgaben.json` (`gleich`/`verschieden`/`ausgeschlossen`/`zugeordnet`),
  `gruppen_quiz_stand.json`, `gruppen_antworten.jsonl` (Protokoll),
  `personen_profile.json`. **Kein Schreibpfad auf einen Vektor.**
- Dass neue Bilder die Benennung trotzdem erben, liegt am **Nachtragen**: neue
  Gesichter werden gegen die **alten** Mittelpunkte gemessen
  (`personen_gruppieren.py:1047–1058`, Cosinus ≥ `ZUORDNUNG_AEHNLICH`, nie zwei
  Gesichter desselben Bildes in dieselbe Gruppe) und bekommen die getroffene
  **Kennung**; den Namen erbt die Gruppe über die Kennung
  (`personen_gruppieren.py:1125`: `"name": bekannt.get("name") or namen.get(kennung)`).
  Der Name wandert also **mit der Kennung**, nicht in den Vektor.
- **Der alte Katalog bekommt dabei nichts.** Er wird nur in
  `gesichter_service.py` geschrieben (`KATALOG_DATEI` `:33`, `_speichern()` `:66–72`,
  `person_speichern()` `:158`, erreicht über `router/gesichter.py`). In
  `gruppen_quiz.py` kommt `gesichter_katalog` **nicht vor** (0 Treffer), und im
  gesamten `backend/app/**` nennen ihn nur `gesichter_service.py` und
  `face_service.py` (Feld `embedding`, 128 Dimensionen). Auf diesem Rechner
  **existiert die Datei nicht** (gemessen) — es gibt hier also gar keinen alten
  Katalog, in den etwas hineinwachsen könnte.
- Diese Brücke ist im eigenen Haus seit dem 01.10. als **offen** vermerkt:
  `docs/changelog-2026-10-01-gruppen-quiz.md:84` („Brücke in den
  `gesichter_katalog.json` (neue Handy-Fotos erkennen die benannte Person) braucht …")
  und `docs/uebergabe-2026-10-01-cloud.md:69` (derselbe Punkt in der Cloud-Übergabe).
  Der Plan `docs/plan-foto-personen-und-erinnerungen.md:72` nennt ihn als Soll
  („Katalog … bekommt den Namen"). **Soll und Ist weichen also weiterhin ab.**

## Frage 2: Werden mehrere Gruppen desselben Namens miteinander verbunden?

**Antwort: Sie bleiben getrennte Gruppen (eigene Kennungen), teilen aber den Namen
und werden über eine Vorgabe aneinandergebunden — nicht zu einem Cluster verschmolzen.**

- `personen_bestaetigt.json` ist eine **Tabelle Kennung → Name**, kein Personenobjekt:
  mehrere Kennungen dürfen denselben Namen tragen (`gruppen_quiz.py:29`).
  **Gemessen (PC-Fassung vom 08.10., 23:51):** 20 Kennungen, 7 verschiedene Namen,
  davon **6 Namen an mehr als einer Kennung** (größter Fall: 4 Kennungen).
- `person(name)` (`gruppen_quiz.py:1135–1157`) sammelt **alle** Kennungen dieses
  Namens (`:1144`) und liefert sie als *Vorschläge* **einer** Person;
  `personen()` (`:1097–1132`) fasst sie nach gefaltetem Namen zusammen und zählt die
  Gesichter über alle Vorschläge (`:1108–1112`).
- Beim Benennen einer gleichnamigen Gruppe setzt das Werkzeug zusätzlich ein
  `gleich`-Paar in die Vorgaben (`gruppen_quiz.py:1339–1343`); beim Umbenennen auf
  einen bestehenden Namen ebenso (`umbenennen()`, `:1160–1194`, Zusammenführen
  `:1187–1194`, Profil-Zusammenführung `:1201–1210`). Ein Name wird auch **an die
  gleich-verbundenen Gruppen weitergereicht** (`:1361–1369`, mehrstufig).
- Im Lauf wirkt der Name als **Verbindungs- und Trennregel**:
  `verschieden()`/`darf()` (`personen_gruppieren.py:684–687`, `:539`) — gleicher
  bestätigter Name verbindet, verschiedene Namen trennen; `gleich`-Paare werden
  zusammengelegt (`:692`).
- **Gemessen (PC):** `personen_vorgaben.json` = **14 gleich-Paare, 5 verschieden-Paare,
  40 ausgeschlossene Gesichter, 0 feste Einzelzuordnungen** — bei 20 benannten
  Kennungen also die Mehrheit der Gruppen über Paare verbunden, nicht über die Kennung.

## Frage 3: Wird bei einem manuellen Eingriff neu geclustert — verschiebt das bestehende Zuordnungen?

**Antwort: Der Eingriff selbst rechnet nie neu. Ein neuer _voller_ PC-Lauf rechnet
neu und kann Zuordnungen verschieben; der Nachtragen-Weg ist genau deswegen gebaut
und verschiebt nichts.**

- Das Quiz schreibt nur Tabellen (siehe Frage 1); `gesicht_zuordnung.jsonl` und
  `kennungen.json` bleiben unberührt, bis am PC ein Lauf gestartet wird. Es gibt
  **keinen Auslöser am Handy**: `router/gruppen.py` hat 17 Routen (Stand gemessen,
  `/stand`, `/naechste`, `/antwort`, `/rueckgaengig`, `/bilder`, `/profil`,
  `/suche`, `/gesichter`, `/bild-gesichter`, `/ausschliessen`,
  `/person/ausschliessen`, `/zuordnen`, `/personen`, `/person`, `/umbenennen`,
  `/loesen`) — **keine** zum Neugruppieren. Das Neugruppieren ist Paket 4 des Plans
  (`2026-10-10_personen-orte-erzaehlungen.md`, Abschnitt 4).
- **Voller Lauf:** clustert neu und kann Altzuordnungen verschieben. Der Schaden ist
  im Werkzeugkopf als Messung festgehalten (`personen_gruppieren.py:60–63`):
  „ein voller Neu-Lauf bringt die schon benannten Gruppen durcheinander (gemessen:
  eine Gruppe behielt nur 22 % ihrer Gesichter, 27 Gesichter wanderten zu einer
  anderen benannten Person)".
- **Nachtragen:** alte Zuordnungszeilen werden 1:1 weitergereicht
  (`zuordnung_zeilen_lesen()`, `:868–874`) und nur bei **ausdrücklichen** festen
  Zuordnungen korrigiert (`:1004–1017`); die **alten Mittelpunkte werden nicht
  verschoben** (`:63–66`, gelesen in `:1000–1001`); nur **neue** Gesichter docken an
  (`nachtrag_rechnen()`, `:958–1090`). Idempotent („zweiter Lauf = 0 neu") ist
  mehrfach gemessen, zuletzt am 13.10. (Journal 44 der Planliste).
- **Der Nutzer behält in beiden Wegen die Kontrolle**, seine Eingriffe sind
  Bedingungen und werden nicht wegoptimiert: `verschieden`/Namen trennen
  (`:684–687`), `ausgeschlossen` bleibt draußen (`:702–715`, `:1002`, `:1054`),
  `gleich` verschmilzt (`:692`), und eine **feste Einzelzuordnung** überschreibt die
  automatische Entscheidung (`:670`, `:710–712`, `:997–998`), aufgelöst in
  `_einzelzuordnungen_auflosen()` (`:240–269`) — bei fehlendem Beleg bricht der Lauf
  ehrlich ab (`:674–676`, `:990–992`) statt still zu raten.
- **Gemessen:** die festen Einzelzuordnungen im hiesigen Bestand = **0**
  (`personen_vorgaben.json`, Fassung 08.10.). Der Entwurf dazu ist Thema von
  **GitHub-Issue #5** (fremd belegt, „Bitte nicht parallel bearbeiten") — hier
  **nicht angefasst**, auch kein Code.

## Frage 4: Verbessert manuelles Sortieren die Erkennung künftiger Bilder?

**Antwort: Es verbessert die _Zuordnung_ künftiger Bilder, nicht die
_Erkennungsähnlichkeit_. Aus den Korrekturen lernt niemand.**

Was besser wird:

1. **Die Kennung bleibt die Naht für neue Gesichter.** Beim Lauf werden alte
   Kennungen über ihre Mittelpunkte wiederverwendet (`vorab_kennung`,
   `personen_gruppieren.py:679–682`; `kennungen_vergeben()`, `:591`), und neue
   Gesichter hängen sich daran. Jedes neue Gesicht einer benannten Gruppe trägt danach
   den Namen (`:1125`) und erscheint in `person(name)` und `bilder_mit()`.
2. **Falsche Anhängsel werden verhindert.** `verschieden`, Ausschlüsse und die
   cannot-link-Regel (nie zwei Gesichter desselben Bildes in eine Gruppe, `:22–24`)
   halten fremde Gesichter heraus — die Zuordnungsqualität wächst mit jeder Antwort.
3. **Gemessen an der Wirkung, nicht am Gefühl:** nach dem Nachtragen vom 13.10.
   1.170 → 1.367 Gruppen, 26.524 → 30.830 Gesichter in Gruppen, Zuordnung 63,7 % → 61,3 %
   (Planliste, Journal 44).

Was **nicht** besser wird:

- **Der Mittelpunkt selbst wird nicht nachgeführt.** Der Nachtragen-Weg verschiebt
  alte Mittelpunkte ausdrücklich nicht (`:63–66`); der volle Lauf nimmt für
  wiederverwendete Kennungen den Mittelpunkt des Clusters
  (`:759–764`: für automatische Kennungen `auto_mitte`) — nicht den Mittelpunkt der
  korrigierten Menge. **Aus einer Handkorrektur wird also kein neuer Referenzvektor
  gerechnet.** Ein Nachlern-/Referenzbild-Verfahren gibt es in diesem Weg nicht;
  der einzige Ort, an dem Referenzbilder je Person liegen, ist der **alte Katalog**
  (`gesichter_service.py:100–158`), und der bekommt aus dem Quiz nichts (Frage 1).
- **Die Wirkung erreicht das Handy nur über zwei Dateien.** Übergeben werden
  `personen_beispiele.json` und `gesicht_zuordnung.jsonl`; `kennungen.json`
  („Biometrie — bleibt am PC", `:47–48`) ist bewusst **nicht** in der Übergabeliste
  (der Nachweis führt 8 Übergabedateien, `kennungen.json` ist nicht darunter).
  Ohne PC-Lauf plus Übergabe ändert sich am Handy kein Gruppenstand.

## Was daraus für den Plan folgt (Vorschlag, nicht umgesetzt)

1. **Die Brücke zum alten Katalog ist der harte offene Punkt** — solange sie fehlt,
   erkennt der Bild-für-Bild-Weg keinen im Quiz benannten Menschen. Vorbedingung ist
   eine Entscheidung, ob der alte Katalog überhaupt weiterleben soll (auf diesem
   Rechner existiert er nicht).
2. **Korrekturen sollten den Mittelpunkt nachführen** (Mittelpunkt aus den belegten
   Mitgliedern statt aus dem Cluster) — sonst wiederholt das Sortieren dieselbe Arbeit
   bei jeder neuen Bildmenge. Das ist eine Änderung am Gruppierer und damit
   **Issue-#5-Gebiet** → Planrunde, nicht Nachtlauf.
3. **Paket 4 des Plans** (Übersicht, Bild für Bild, Zusammenführen, Neugruppieren
   vom Handy) bleibt der Hebel für Sebastian selbst: heute gibt es dafür keine Route
   (Frage 3, gemessene Routenliste).

**Grenzen dieses Belegs (ehrlich):** alle Zahlen stammen vom PC-Bestand; die
maßgebliche Fassung von `personen_bestaetigt.json` / `personen_vorgaben.json` liegt
am Handy (die PC-Fassung ist die Kopie vom 08.10., 23:51) — Mengenangaben am Handy
können höher sein. Ausgesagt ist die **Verdrahtung** (Code, Datei:Zeile) und der
hiesige Bestand, nichts über Handy-Zahlen.
