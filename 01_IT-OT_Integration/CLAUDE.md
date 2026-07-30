<!--
  DIESE DATEI WURDE AUTOMATISCH GENERIERT (sync-rules.ps1)
  AENDERUNGEN IN DIESER DATEI WERDEN BEIM NAECHSTEN RUN UEBERSCHRIEBEN!
  Bitte aendere die globale CLAUDE.md im Hauptverzeichnis oder die lokale CLAUDE_EXTENDS.md.
-->

> **Basis-Regelwerk:** Es gelten weiterhin die globalen KI-Direktiven aus `../CLAUDE.md` (Workspace-Wurzel).
> Sie sind hier bewusst nicht kopiert, damit es nur eine Quelle gibt. Claude Code liest sie von sich aus mit.

<!-- LOKALE PROJEKT-ERWEITERUNGEN (EXTENDS) -->

# BEREICHS-ERWEITERUNG: AUTOMATISIERUNGSTECHNIK (OT)

Dieses Regelwerk erweitert die globalen KI-Direktiven um hochspezifische Richtlinien für TwinCAT 3 (IEC 61131-3).

---

## 1. BECKHOFF VARIABLEN-NAMENSKONVENTIONEN

Jede Variable muss streng nach Beckhoff-Sicherheits-Konventionen mit dem passenden Typ-Präfix deklariert werden:

* `b`  - BOOL (z. B. `bStart`, `bBereit`)
* `r`  - REAL (z. B. `rSollwert`, `rIstwert`)
* `i`   - INT (z. B. `iZaehler`, `iStep`)
* `di`  - DINT (z. B. `diPosition`, `diWinkelLatch`)
* `ui`  - UINT (z. B. `uiIndex`)
* `udi` - UDINT (z. B. `udiZaehler`)
* `t`  - TIME (z. B. `tVerzoegerung`)
* `s`  - STRING (z. B. `sFehlermeldung`)
* `st` - STRUCT (z. B. `stHMI_Data`)
* `fb` - FUNCTION_BLOCK (z. B. `fbHauptantrieb`)
* `e`  - ENUM (z. B. `eMaschinenZustand`)

---

## 2. ESTEP-SCHRITTKETTEN-KONVENTION (ENUM-BASIERT)

Deine Schrittketten müssen pragmatisch und deterministisch als Enum-Abläufe in `CASE eStep OF` (unter Verwendung von sprechenden Konstanten mit expliziter Zahlenzuweisung) entworfen werden:

* **Datentyp:** `eStep : E_State` (Enum abgeleitet von `DINT` / `INT`).
* **Zehner-Schritte:** Standard-Abläufe mit festen Nummern in 10, 20, 30, 40... deklarieren.
* **Flexibilität:** Lücken freihalten (z. B. 11, 12, 15), um später Zwischenschritte einfügen zu können.
* **Kommentare:** Jeder Schritt MUSS im Code kommentiert werden:
  `eFoerderband_An: (* [10] Förderband läuft *)`

---

## 3. LATCH-ARCHITEKTUR (Wert-Einfrierung)

Der Latch-Mechanismus ist das entscheidende Bindeglied zwischen Steuerfluss und schnellem Datenfluss (Esterel-Prinzip):

* **Das Prinzip:** Encoder- oder Messwerte werden exakt beim Sensor-Trigger eingefroren. Alle weiteren Schritte rechnen mit dem Latch-Wert, nicht mit dem Live-Encoder.
* **Die Ausnahme:** Das Einfrieren des Wertes erfolgt als **"Aktion in der Transition"** direkt im Umschalt-Moment. Das ist ein bewährtes Design-Pattern für schnelle Maschinen (700 Teile/Min):
  ```pascal
  IF bSensor AND NOT bSensorLast THEN
      nWinkelLatch := Encoder.nPosition;   (* Latch-Moment *)
      nNestNr      := NestDetekt.nAktuell;
      iStep        := 20;
  END_IF
  bSensorLast := bSensor;
  ```

---

## 4. DATEI-REGISTRIERUNGS-WORKFLOW (.PLCPROJ XML)

Wenn eine neue `.TcPOU` (Funktionsbaustein) oder `.TcDUT` (Struct/Enum) erstellt wird, muss diese zwingend in der XML-Projektdatei (`.plcproj`) registriert werden, damit sie in der XAE Shell sofort sichtbar ist:

```xml
<Compile Include="POUs\FB_Name.TcPOU">
  <SubType>Code</SubType>
</Compile>
```
*Der Pfad der `.plcproj` liegt im PLC-Unterordner des Maschinenprojekts.*

