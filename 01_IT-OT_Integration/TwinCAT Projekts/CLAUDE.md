# TwinCAT Projekte — Claude Direktiven

## Projekte in diesem Ordner

| Ordner | Inhalt |
|--------|--------|
| `Elevator_TC/` | Fahrstuhl Digital Twin — Lernprojekt |
| `Elevator_TC/ads_bridge/` | ADS WebSocket Bridge (Node.js) für Fahrstuhl |

## ⚠️ Sicherheitsregeln (immer gültig)

- Plan-Mode ist Standard — Auto-Mode nur auf explizite Freigabe

## Projekt-Architektur (TwinCAT 3)

Programme sind so aufgebaut:
  Task → PRG → Actions (Eingaenge, Ausgaenge, Fehler, Funktionen)

Schrittnummern-Konvention:
  - Enum-Schrittkette `eStep : E_ElevatorState` (abgeleitet von `DINT` mit expliziten Integer-Nummern)
  - Zehner-Schritte: 10, 20, 30 ... (Lücken für spätere Einfügungen)
  - Jede Action besitzt einen Schrittbereich

Variablen-Präfixe (Beckhoff):
  b - BOOL,  r - REAL,  i - INT,  di - DINT,  ui - UINT,  udi - UDINT,  t - TIME,  s - STRING,  e - ENUM

## Neuen FB / DUT / GVL anlegen (vollautomatisch)

Claude macht BEIDES gleichzeitig:
1. .TcPOU / .TcDUT / .TcGVL Datei anlegen
2. Eintrag in [Projektname].plcproj ergänzen:
   <Compile Include="POUs\FB_Name.TcPOU">
     <SubType>Code</SubType>
   </Compile>

Fallback wenn .plcproj nicht editierbar:
  XAE Shell → Rechtsklick auf Ordner → "Vorhandenes Element hinzufügen"

## Latch-Muster (wichtig bei schnellen Prozessen)

Bei Schrittwechsel Werte einfrieren:
  IF bSensor AND NOT bSensorLast THEN
      nWinkelLatch := Encoder.nPosition;
      nNestNr      := NestDetekt.nAktuell;
      iStep        := 20;
  END_IF
  bSensorLast := bSensor;

Latch ist eine bewusste "Aktion in der Transition" — kein Fehler.
Gilt besonders bei Trommeln / schnellen Prozessen (700 Teile/min).

## Draw.io Dokumentation

Seite 1: Ablaufdiagramm (Blöcke mit iStep-Nummer + Aktionen + IF-Bedingungen)
Seite 2: Schnittstellentabelle (VAR_INPUT / VAR_OUTPUT / VAR lokal)

Pfeile zwischen Schritten:
  - Oben: Transitionsbedingung
  - Unten (orange): LATCH-Operationen falls vorhanden

## Prompt-Vorlagen

Unbekannten Code analysieren:
  "Analysiere dieses TwinCAT 3 Projekt. Erkläre Namenskonventionen,
   PRG/Action-Struktur, Schrittnummern-Bereiche. Ändere noch nichts."

Neuen FB planen:
  "Ich möchte [Beschreibung]. Zeig mir NUR den Plan: Steps, Variablen,
   welche Action, gibt es einen Latch-Moment? Ändere noch nichts."
