# Planprüfung Fassung 4 „Websuche mit Namensverbot" — Hermes (14.10.2026)

**Rolle:** Hermes ist laut Rollentabelle (AGENTS.md, Regel ab 12.10.2026) **zweiter Planprüfer**
(„Planprüfung: Hermes (DeepSeek v4.1 Flash) **und** Codex"). Codex hat die Runden 1–4 gefahren (alle
EINWAND, Protokoll `.hermes/pruefkreis/websuche-namensverbot-plan.md`); eine **Hermes-Runde zu
Fassung 4 fehlte** — genau der offene Schritt, den dieser Lauf genommen hat.

**Prüfgegenstand:** `.hermes/plans/2026-10-14_websuche-namensverbot.md`, Fassung 4, Stand 15:44.

**Vorgehen:** Vorlage statisch gelesen, dazu die genannten Codestellen gelesen und die benannten
Funktionen **mit eigenen Sonden gegen den echten Bestand** geprüft. Kein Netzaufruf, kein
Modellaufruf, kein Bild geöffnet, keine Geräteeingriffe. Alle Zahlen unten sind **gemessen**, alle
Namen in den Beispielen sind **erfunden** (so wie im Plan selbst).

## Urteil: EINWAND (1 hoch, 2 mittel) und zwei Hinweise

Die Mechanik selbst ist schlüssig und behebt beide offenen Codex-Einwände der Runde 4: `N1` nimmt im
Werkzeug-Weg das Server-Werkzeug weg und führt den Suchtext über ein eigenes Werkzeug mit Prüfung,
`N3` schließt die unkontrollierten Wege (Plugin und Server-Werkzeug fallen aus allen Hauptaufrufen,
`manual` sucht mit Sebastians eigenem Satz). Der verbleibende Einwand sitzt **nicht** in der
Verdrahtung, sondern in der **Vollständigkeit der Namensliste** — also genau dort, wo die Wirkung
des Versprechens hängt.

### Einwand 1 (hoch) — die Namensliste ist schmaler als der Kontext, den das Modell sieht

- **Quelle der Liste:** `backend/app/services/werkzeuge.py:399–424` — `_bekannte_personen()` liest
  das Personen-Quiz (`gruppen_quiz.personen()`), sonst den alten Gesichtskatalog. Es sind die
  **benannten Fotopersonen**, sonst nichts.
- **Gemessen am PC-Bestand (nur Zahlen):** **7 Personen / 8 Namensteile.** Die maßgebliche Fassung
  liegt am Gerät; am PC ist sie nicht prüfbar (die PC-Kopie ist vom 08.10.).
- **Der Kontext trägt mehr Namen als die Liste:** Erinnerungen
  (`backend/app/services/llm_service.py:717`) und **Archiv-Fundstellen echter Gesprächsinhalte**
  (`:723`, je bis 1.200 Zeichen) stehen im Systemtext. In `N1` formuliert das Modell den Suchtext
  (`anfrage`) **selbst** — die Prüfung sieht nur die Argumente des Modells, nicht dessen Denken.
- **Folge:** Ein Name, der über eine Archiv-Fundstelle oder eine Erinnerung im Kontext steht und
  **nicht** im Foto-Personenbestand ist, passiert die Prüfung und geht in die Suche. `N2` sagt
  ausdrücklich, ein fremder Name ohne gemeinsamen Teil sei **nie** ein Treffer (Plan:63–70) —
  gemeint sind damit öffentliche Personen (Sebastians Wunsch vom 14.10.). Für eine **private**
  Person außerhalb des Foto-Bestands (Nachbarin, Kollege, Arzt) ist der Weg damit offen, ohne dass
  der Plan diese Grenze benennt.
- **Beleg, dass das Haus solche Namen kennt (gemessen, nur Zahlen):**
  `C:/Users/sebas/foto_sortierung/whatsapp_zuordnung.json` führt **2.471 Chat-Zuordnungen** und
  **55 Geburtstage**. Nicht im Foto-Bestand, also nie in der Sperrliste.
- **Vorschlag (klein, alles lokal, kein neuer Datenfluss):** `bekannte_namen_streng()` speist sich
  zusätzlich aus den schon vorhandenen lokalen Namensquellen (Telefonbuch-Zuordnung, Kontaktprofile,
  Geburtstage) — oder der Plan **benennt die Grenze ausdrücklich** und ein Test hält sie fest. Beides
  ist besser als der jetzige Zustand, in dem das Versprechen weiter reicht als die Liste.

### Einwand 2 (mittel) — das Prüfkriterium nennt keine Messung der Namensliste

Die Schutzwirkung steht und fällt mit der Liste. Der Plan nennt keine Zahl, keine Untergrenze und
keine Messung im Changelog; am PC gemessen sind es 7 Namen. Ohne diese Messung lässt sich
„Namensverbot" weder belegen noch später überprüfen — genau der Punkt, den „fertig ist, was
verifiziert ist" verlangt. **Auflage:** Messung (Zahl der Namen und Namensteile, PC und Gerät) in
den Changelog, mit dem Hinweis, welche Fassung maßgeblich ist.

### Einwand 3 (mittel) — die Testfolgen der neuen Werkzeugnummer stehen nicht im Plan

- `backend/tests/test_werkzeuge.py:40` prüft `len(schemata) == len(wz.REGISTER) == 10` — mit
  `web_suche` sind es **11**; die Zeile muss mit.
- `backend/tests/test_tool_use_stream.py:161–162` erwartet bei `auto` **sowohl**
  `set(REGISTER) <= set(namen)` als auch ein `openrouter:web_search` in `tools`. **Beides zusammen
  geht nach `N1` nicht mehr** (Server-Werkzeug entfällt, `web_suche` steht nur bei `auto` im
  Schema).
- `werkzeuge.pruefe_register()` (`werkzeuge.py:812–855`) muss `web_suche` führen; `schemata()` und
  `status_text()` ebenso.
- Diese Punkte fehlen in der Testliste (Plan:124–157), obwohl derselbe Sprung 9→10 in einem
  früheren Schritt ausdrücklich mitgenannt wurde. Bei `off`/`manual` fehlt `web_suche` im Schema —
  ein Test sollte das festhalten (der Plan sieht ihn, ergänzt ihn aber nur für den Werkzeug-Weg).

### Hinweis 1 (niedrig) — die Ausnahme und das Versprechen stehen in Spannung

Die Ausnahme „eigener Suchauftrag mit vollem fremden Namen" (Plan:71–83) lässt laut Codex R3/1 auch
„Suche im Internet nach Ida Geburtstag" durch, obwohl „Ida" ein bekannter Vorname ist; der Plan
entscheidet das als **gewollte Regel** (Sebastians eigener Auftrag). Das ist als Entscheidung
nachvollziehbar und begründet — es widerspricht aber dem Satz „Personennamen dürfen nie in eine
Internetsuche gelangen" (Plan:5–6) im selben Dokument. **Bitte im Changelog beides klar sagen**
(Verbote gelten für alles, was der Agent selbst sucht; ein ausdrücklicher Auftrag Sebastians ist
seine Entscheidung).

### Hinweis 2 (niedrig) — Umschrift-Varianten bleiben offen

Gemessen am echten Muster (`websuche_schutz.py:60`, `(?<!\w)(…)(?!\w)`, `_MIN_TEIL = 3`) mit
erfundenen Namen: „Idas Firma", „Bodos Arbeitgeber", „Testmanns Familie" **passieren heute** (der
Plan behebt genau das über die Endungen `s`, `'s`, `’s` — der Hermes-Einwand aus Runde 2 ist damit
eingelöst). **„Mueller"** statt „Müller" passiert auch nach dem Plan, ebenso eine andere Schreibweise
mit Bindestrich im Vornamen. Ehrlich als Grenze dokumentieren; ein Test würde reichen.

## Was ich **nicht** freigebe

Keine Freigabe der Fassung 4 in diesem Zustand: Einwand 1 betrifft genau die Wirkung des
Namensverbots und ist vor der Umsetzung zu entscheiden (Liste erweitern **oder** Grenze ausdrücklich
festschreiben und testen). Einwand 2 und 3 sind kleine Auflagen ohne Bauänderung. Selbstfreigabe
findet nicht statt; die Umsetzung liegt beim Master.

## Grenzen dieses Laufs

Kein Bild geöffnet oder gesendet, kein Vision-Aufruf, kein Netz- und kein Modellaufruf, keine
Kosten, keine Geräteeingriffe (heute kein Gerät), kein pCloud-Zugriff, nichts gelöscht, nichts
freigegeben. Gelesen wurden nur lokale Bestandsdateien; der Bericht enthält **nur Zahlen**, keine
Namen, Nummern, Kennungen oder Pfade zu Personen.
