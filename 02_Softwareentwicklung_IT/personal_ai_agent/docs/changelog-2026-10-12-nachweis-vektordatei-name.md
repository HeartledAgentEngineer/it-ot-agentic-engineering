# Der Name ist ein Hinweis, die Größe ist der Beleg — die Vektordatei des Rückfallwegs

Datum: 12.10.2026. Werkzeug: `tools/foto_sortierung/bestand_pruefen.py` (Abschnitt
„Archiv (Chat/WhatsApp)“). Test: `backend/tests/test_bestand_und_handy_uebergabe.py`.

## Der Befund, gemessen

Der alte Suchweg des Chats (`archiv_service`) öffnet seine Vektoren über **einen
festen Dateinamen** und rechnet mit **1.024 Werten je Vektor**
(`archiv_service.vektoren`, `settings.archiv_vektor_path`). Liegt die Datei nur
unter einem abweichenden Namen daneben, findet er sie nicht — die
Bedeutungssuche schweigt still, die Textsicht antwortet weiter.

Der Nachweis meldete bisher nur: „fehlt (1 Datei(en) mit abweichendem Namen
daneben)“. Das ist eine Zahl ohne Aussage: ein beliebiger Rest und die richtige
Datei unter falschem Namen sehen darin gleich aus.

Gemessen am echten Bestand (nur lesend):

- `memory.db`: 282.029 Nachrichten, 52.679 Chunks, **33.312 mit Vektor**.
- Daneben liegt **`memory.vektoren [conflicted].f32`** mit **136.445.952 Byte**
  = 33.312 × 1.024 × 4 Byte — **exakt** die Vektordatei dieser Textschicht,
  nur mit abweichendem Namen (Konflikt-Rest der Ablage, 25.09.).
- Die zweite Datei daneben (`…_vor_whatsapp_…vektoren.f32`, 126.529.536 Byte
  = 30.891 × 1.024 × 4 Byte) passt zur **Vor-WhatsApp**-Fassung, nicht zu dieser.

Damit ist der Unterschied belegt statt geraten: es fehlt keine Vektordatei, sie
ist **umbenannt**. Der Nachweis sagt das jetzt selbst.

## Was geändert wurde

1. `archiv_vektordatei_stand(ordner, vektoren=None)` prüft jede Datei mit
   abweichendem Namen gegen die Textschicht: Größe durch die Zahl der Vektoren
   teilbar **und** das Ergebnis durch 4 (float32) teilbar → sie passt; gemeldet
   werden die Anzahl passender Dateien und die **Werte je Vektor**. Ohne die
   Zahl der Vektoren (`vektoren=None`, Textschicht nicht lesbar) wird **nichts**
   behauptet (`geprueft: False`), dann bleibt es bei der reinen Zählung.
2. Die Berichtszeile benennt die Folge, statt sie offen zu lassen:
   `… fehlt (1 Datei(en) mit abweichendem Namen daneben, davon 1 passend zur
   Textschicht (33.312 Vektoren zu je 1.024 Werten) - nur der NAME weicht ab,
   die Bedeutungssuche des Rueckfallwegs findet sie so nicht)`
   bzw. `…, keine passt zur Textschicht (N Vektoren) - es ist keine Vektordatei
   dieses Weges)`.
3. Der Aufrufer übergibt die gemessene Zahl der Vektoren aus `memory.db`; es
   wird nichts importiert (das Werkzeug bleibt bei der Standardbibliothek).

**Keine neue Lücke.** Die Lückenliste bleibt bei 5: die Zeile nennt Zustand und
Folge vollständig, und der Rückfallweg ist der zweite Weg (der volle Index steht
daneben). Eine Lücke nur für den Dateinamen würde die Zahl aufblähen, ohne dass
sich etwas anderes prüfen ließe.

## Belege

- Testdatei `test_bestand_und_handy_uebergabe.py` **101 → 104 Testfunktionen**
  (3 neue: passende Neben-Datei wird belegt und ohne Dateinamen/Pfad gemeldet;
  nicht passende Neben-Datei wird als solche benannt; ohne Textschicht keine
  Behauptung), Lauf der Datei **104 passed** (24,16 s).
- Prüfbefehl: siehe Commit (frisch und vollständig, Exit 0).
- Messung am echten Bestand (nur lesend, Exit 0): die neue Zeile lautet
  „Vektordatei des Rueckfallwegs (memory.vektoren.f32): fehlt (1 Datei(en) mit
  abweichendem Namen daneben, davon 1 passend zur Textschicht (33.312 Vektoren
  zu je 1.024 Werten) - nur der NAME weicht ab, die Bedeutungssuche des
  Rueckfallwegs findet sie so nicht)“. Ergebnis unverändert 5 Lücken.

## Ehrliche Grenzen

- **Geändert wird nichts.** Die Datei liegt in einem persönlichen Datenarchiv
  (`Chats von GPT, GEMINI, Claude/`) — dort gilt weiterhin alles manuell. Das
  Werkzeug nennt nur die Zahl; ein Umbenennen/Kopieren entscheidet Sebastian.
- Ob die `.env` des Handys auf denselben Namen zeigt und ob dort dieselbe
  Umbenennung nötig ist, ist am PC **nicht** messbar (Termux-Heimordner ist per
  Kabel nicht lesbar).
- Geprüft wird die **Größe**, nicht der Inhalt: ob die Werte wirklich zu den
  Chunks passen, zeigt erst ein Lauf des alten Weges mit dieser Datei.
