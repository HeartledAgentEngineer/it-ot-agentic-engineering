# Alignment: Alltagsprotokoll im Agenten — Slice 1 „Eintragen"

**Datum:** 2026-11-02 · **Projekt:** `02_Softwareentwicklung_IT/personal_ai_agent` · **Phase:** 2 von 8

> Dieses Dokument beschreibt nur die Software. Echte Einträge gehören nie ins Repo; Tests laufen
> ausschließlich mit erfundenen Daten.

---

## Ziel

Aus stündlichen, gesprochenen oder getippten Einträgen (Stimmung, Anspannung, Gefühle, Aktivität,
Essen, Schlaf) sollen Verhaltensmuster sichtbar werden: als Grundlage, um gemeinsam mit einer
Begleitperson Routinen, Grenzen, Abwechslung, Aktivität und gesunde Ernährung zu erarbeiten, mehr
Ausgeglichenheit zu schaffen und Überlastung vorzubeugen.

**Slice 1** liefert den Kern: stündliches Pop-up, Eintragen per Sprache oder Tastatur, strukturiertes
Herausziehen der Daten mit kurzer Rückfrage-Einblendung, Tagesablauf zum Ansehen.

## Nicht-Ziele

- Kein Ersatz für fachliche Begleitung, kein Notfalldienst.
- Der Agent setzt **keine** Ziele und schlägt **keine** Routinen/Verhaltensänderungen vor (Ziele entstehen
  mit einer Begleitperson; Verbindlichkeit gegenüber einem Menschen ist der Wirkmechanismus).
- Keine medizinischen Ratschläge, keine Diagnosen.
- Keine fremden Apps/Anbieter (Daylio, Yazio o. Ä.), keine Daten außerhalb des eigenen Agenten.
- Kein technischer Stundenwecker mit Ton/Alarm, nur Pop-ups.
- **Nicht in Slice 1:** Kalorien/Fotos, Wochenansicht/PDF, Sprachfragen an das Protokoll, Uhr-Anbindung,
  automatische Bildschirmzeit.

## Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| 1 | Modul im eigenen Agenten (Alltagsprotokoll), Abfrage später auch per Sprache | Eine App, eine Datenbasis, auswertbar über alle Dimensionen |
| 2 | Verarbeitung (Sprache, Struktur, Zusammenfassung) über OpenRouter ZDR, Namen/private Angaben vorher per PII-Shield maskiert; Speicherung lokal | Gleiche geprüfte Strecke wie Erzählung/Bildbeschreibung; nur so sind Foto-Schätzung und gute Zusammenfassungen machbar |
| 3 | Pop-up rund um die Uhr, stündlich | Auch nächtliche Wachphasen sollen ins Protokoll |
| 4 | **Ein** Pop-up, das sich aktualisiert („Bitte X Stunden nachtragen") statt sich zu stapeln | Beim Aufwachen sofort sichtbar, wie viel fehlt |
| 5 | Antippen → App öffnet, Mikro nimmt sofort auf; großer Knopf „Tastatur" bricht ab und wechselt zum Tippen | Ein Tipp tagsüber; Tastatur, um nachts niemanden zu wecken |
| 6 | Zwischeneinträge jederzeit („Ich gehe schlafen", „Ich wache auf", „Kann nicht schlafen", „Gehe wieder schlafen"); Schlafdauer/Wachphasen werden daraus berechnet | Genauer als eine Morgen-Abfrage |
| 7 | Nachtragen über einen Stundenbereich in einem Rutsch; Agent verteilt auf die Stunden | Lücken schnell schließen |
| 8 | Fehlt etwas, kurze überspringbare Rückfrage als **Einblendung** („Wie ist es mit deiner Stimmung?") | Vollständiges Protokoll ohne Nerven |
| 9 | Stimmung in 5 Stufen: sehr gut / gut / mittel / schlecht / sehr schlecht | Wunsch Sebastian |
| 10 | Anspannung/Stress 0–100 % (0 = Schlaf, 100 = Megastress mit Gedankenblockaden), angelehnt an eine stündliche Spannungskurve; Bereiche/Form mit der Begleitperson abgleichen | Passt zum stündlichen Protokoll |
| 11 | Gefühle der letzten Stunde: vorhandene + vorherrschendes | Musteranalyse braucht beides |
| 12 | (Folge-Slice) Kalorien: Foto oder Kurzerzählung → Schätzung einblenden → bestätigen/korrigieren; Getränke zählen mit; Tagesstand gegen ~2.000 kcal als **Richtwert** | Foto-Schätzungen sind grob; Korrektur hält die Summe ehrlich |
| 13 | (Folge-Slice) Wochenansicht im Agenten-Browser (Tablet über Tailscale), zuletzt geladene Woche offline per Service Worker, dazu PDF-Export | Besprechung auch ohne Netz; nichts doppelt bauen |
| 14 | Auswertung: Muster sichtbar machen + Stand der vereinbarten Ziele anzeigen; kein aktives Erinnern | Ziele kommen von Menschen, nicht von der KI |
| 15 | Slice 1 = Eintragen (A) | Herzstück zuerst; Folge-Slices bauen auf erprobtem Datenmodell auf |

## Verworfene Alternativen

| Alternative | Verworfen, weil |
|---|---|
| Eigene separate App | Nicht integrierbar, zweite Datenbasis |
| Nur lokale KI auf dem Handy | Hardware schafft Foto-Schätzung/Zusammenfassung nicht |
| Pop-ups nur 8–22 Uhr | Nächtliche Wachphasen würden fehlen |
| Zwei Knöpfe direkt in der Benachrichtigung | Sebastian will Antippen → Mikro sofort |
| Agent schlägt selbst Routinen vor | Sprachmodell als Ersatz-Berater ist zu riskant; Ziele gehören zu Menschen |
| Fertige Apps (Daylio, Yazio) | Fremde Anbieter, keine Sprach-Strukturierung, keine gemeinsame Auswertung |
| Einstellbarer Pop-up-Abstand / „heute pausieren" | Sebastian: bis zu 24 Pop-ups sind okay, Lücken werden rückwirkend gefüllt |

## Annahmen (unbestätigt)

- [ ] Nach „Ich gehe schlafen" aktualisiert sich das Pop-up **lautlos** (kein Ton/Vibration) bis „Ich bin wach".
- [ ] Gefühle: feste Liste von Grundgefühlen (für Wochenvergleich) **plus** eigene Worte; Liste mit der Begleitperson abstimmen.
- [ ] Auswertung zeigt den Zielstand nur an, erinnert nicht aktiv (siehe Entscheidung 14).
- [ ] Ein vereinbarter Notfallplan kann hinterlegt und mit einem Tipp angezeigt werden.
- [ ] Die Offline-Kopie im Browser liegt nur auf Sebastians Geräten; Abmelden löscht sie.
- [ ] Nur Sebastian bedient es; Dritte bekommen höchstens einen Export.
- [ ] Hauptgerät ist das Handy.
- [ ] Vergangene Tage nachtragen/korrigieren und Einträge vollständig löschen ist möglich.
- [ ] Keine eigene PIN im ersten Wurf (Handy ist gesperrt).
- [ ] Design wie der Agent (Dark Mode, gleiche Farbwelt).
- [ ] Claude sieht nie echte Einträge; Tests nur mit erfundenen Daten.

## Offene Punkte

- [ ] **Zuverlässigkeit des stündlichen Pop-ups am Handy** (Android-Akku-Optimierung, ggf. HyperOS) — in Slice 1 auf dem Gerät prüfen.
- [ ] **Xiaomi-Uhr** (eigener Slice): Modell prüfen, aufladen, Kopplung testen. Weg 1 Health Connect, Alternative Gadgetbridge.
- [ ] Automatische Bildschirmzeit als Teil der Aktivität (eigener Slice).
- [ ] Skala/Bereiche der Anspannung und Gefühlsliste mit der Begleitperson abgleichen.
- [ ] Visualisierung der vielen Dimensionen: vor dem Wochenansicht-Slice ein Entwurf zum Anschauen.

## Risiken aus der Devil's-Advocate-Runde

| Einwand | Bewertung | Umgang |
|---|---|---|
| Android/HyperOS verhindert zuverlässige stündliche Pop-ups | offen | In Slice 1 auf dem echten Gerät messen; Zähler „X Stunden nachtragen" fängt Lücken auf |
| Protokoll-Müdigkeit durch bis zu 24 Pop-ups/Tag | zählt nicht | Längere Lücken werden rückwirkend über einen Stundenbereich gefüllt |
| Fertige Apps wären einfacher | zählt nicht | Eigener Agent, keine fremden Anbieter, integrierbar |

## Erfolgskriterien für Phase 5

- [ ] Stündlich erscheint genau **ein** Pop-up; nach verpassten Stunden zeigt es „Bitte X Stunden nachtragen".
- [ ] Antippen öffnet die App, das Mikro nimmt sofort auf; „Tastatur" bricht die Aufnahme ab und öffnet die Texteingabe.
- [ ] Ein gesprochener Satz wie „Letzte Stunde Wäsche gemacht, Stimmung gut, Anspannung 30, etwas genervt" wird zu Aktivität, Stimmung (gut), Anspannung (30) und Gefühl (Ärger, vorherrschend) + Originalworten.
- [ ] Fehlt ein Punkt, erscheint eine überspringbare Rückfrage-Einblendung.
- [ ] „Von 2 bis 5 geschlafen, um 3 kurz wach" verteilt sich korrekt auf die Stunden; Schlafdauer wird berechnet.
- [ ] „Ich gehe schlafen" / „Ich wache auf" erzeugen Schlaf-Ereignisse mit Uhrzeit.
- [ ] Der Tagesablauf zeigt alle Einträge des Tages chronologisch.
- [ ] Ein Eintrag lässt sich korrigieren und vollständig löschen.
- [ ] Keine echten Einträge verlassen das Gerät außer maskiert über ZDR; Tests laufen mit erfundenen Daten; Prüfbefehl grün.

---

*Erstellt mit dem Skill `grill-me`.*
