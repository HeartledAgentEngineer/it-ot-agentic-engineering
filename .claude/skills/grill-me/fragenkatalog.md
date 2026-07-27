# Fragenkatalog

Reservoir, kein Fragebogen. Pro Slice nur die Fragen ziehen, deren Antwort den Plan tatsächlich ändert. Reihenfolge kommt aus dem Entscheidungsbaum, nicht aus dieser Liste.

Jede Frage wird vor dem Stellen in das Pflichtformat gebracht: 2–4 konkrete Optionen + Empfehlung + ein Satz Begründung.

---

## 1. Ziel und Nutzen

- Was ist danach besser als vorher — in einem Satz?
- Woran merkst du im Alltag, dass es funktioniert?
- Wenn nur eine einzige Sache funktionieren würde: welche?

## 2. Nicht-Ziele (Pflichtkategorie)

- Was bauen wir bewusst **nicht** in diesem Slice?
- Welche naheliegende Erweiterung soll ausdrücklich warten?
- Welches Problem sieht ähnlich aus, gehört aber nicht dazu?

## 3. Nutzer und Kontext

- Wer bedient es — nur du, oder auch andere?
- In welcher Situation: am Schreibtisch, an der Anlage, unterwegs, unter Zeitdruck?
- Wie oft: einmal am Tag, ständig, einmal im Quartal?

## 4. Umfang und Grenzen

- Was ist der kleinste Ende-zu-Ende-Durchstich, der schon nützt?
- Welcher Teil ist Pflicht, welcher wäre nur schön?
- Gibt es einen Stichtag oder äußeren Zwang?

## 5. Daten und Zustand

- Was wird gespeichert, wo, in welchem Format?
- Was passiert bei Neustart — ist der Zustand weg oder bleibt er?
- Gibt es personenbezogene oder vertrauliche Daten?
- Wer ist die Wahrheitsquelle, wenn zwei Stellen sich widersprechen?

## 6. Fehlerfälle

- Was passiert, wenn die Verbindung/das Netz/die Datei fehlt?
- Soll ein Fehler laut sein (Meldung, Abbruch) oder leise (Fallback)?
- Was ist schlimmer: falsches Ergebnis oder gar kein Ergebnis?

## 7. Umkehrbarkeit

- Wie teuer ist es, diese Entscheidung in drei Monaten zu ändern?
- Erzeugt sie Daten oder Dateien, die dann migriert werden müssten?
- Gibt es eine Variante, die die Entscheidung offenhält?

## 8. Zuständigkeit

- Wer pflegt das in sechs Monaten?
- Muss es jemand anderes verstehen können, ohne dich zu fragen?
- Braucht es eine Doku-Zeile, oder erklärt sich der Code selbst?

## 9. Verworfene Alternativen

- Welche Lösung hast du dir überlegt und wieder verworfen — und warum?
- Gibt es ein fertiges Werkzeug, das 80 % davon kann?
- Was spricht gegen die einfachste denkbare Variante?

## 10. Erfolgskriterien für Phase 5

- Woran erkennen wir beim Testen, dass es passt?
- Welcher konkrete Handgriff muss funktionieren?
- Was wäre ein klares „nein, so nicht"?

---

## Bereichs-Weiche

### `01_IT-OT_Integration` — Pflichtfragen

- In welchem Zustand bleibt die Anlage, wenn der Ablauf mittendrin abbricht?
- Welche Werte müssen eingefroren werden (Latch) und in welcher Transition?
- Wie ist die iStep-Nummerierung gedacht — reicht der Zehnerraster für spätere Zwischenschritte?
- Namenskonvention der neuen Variablen: `b` / `r` / `i` / `di` / `ui` / `udi` — welche Typen kommen dazu?
- Was bleibt ausdrücklich manuell? (Einspielen, Kompilieren, Online-Change macht Sebastian selbst.)
- Muss der Ablauf sicherheitsgerichtet sein, oder ist er rein funktional?

### `02_Softwareentwicklung_IT` — Pflichtfragen

- Mobile oder Desktop zuerst?
- Farbwelt und Stimmung: an ein bestehendes Projekt anlehnen oder eigene Palette?
- Dark Mode von Anfang an oder später?
- Stack: Flask, Vite, React Native/Expo — oder passt es zu einem bestehenden Projekt dazu?
- Ist die Seite öffentlich sichtbar? Wenn ja: SEO-relevant (Title, Meta, semantisches HTML)?
- Ansprache und Ton: sachlich, verspielt, technisch?
