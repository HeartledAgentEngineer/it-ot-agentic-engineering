<!--
  DIESE DATEI WURDE AUTOMATISCH GENERIERT (sync-rules.ps1)
  AENDERUNGEN IN DIESER DATEI WERDEN BEIM NAECHSTEN RUN UEBERSCHRIEBEN!
  Bitte aendere die globale CLAUDE.md im Hauptverzeichnis oder die lokale CLAUDE_EXTENDS.md.
-->

> **Basis-Regelwerk:** Es gelten weiterhin die globalen KI-Direktiven aus `../CLAUDE.md` (Workspace-Wurzel).
> Sie sind hier bewusst nicht kopiert, damit es nur eine Quelle gibt. Claude Code liest sie von sich aus mit.

<!-- LOKALE PROJEKT-ERWEITERUNGEN (EXTENDS) -->

# BEREICHS-ERWEITERUNG: AUTOMATISIERUNGSTECHNIK (OT) — Theoretischer Entwurf

> **⚠️ DSGVO-Konformität hat Vorrang.** Dieses Regelwerk erweitert die globalen KI-Direktiven um Leitplanken für TwinCAT 3 (IEC 61131-3). Es dient als Vorlage für eine spätere Nutzung — aktuell ist der OT-Bereich nicht aktiv. **Verfahrenstechnisches Wissen (Prozess-Know-how, kundenspezifische Logik) darf niemals das Repository verlassen, auch nicht über DSGVO-konforme Gateways.**

---

## 🔒 DSGVO & Sicherheit

* **Kein Abfluss von Verfahrenstechnik-Wissen:** Prozess-Know-how, kundenspezifische Algorithmen und Anlagenlogik verlassen niemals das Repository — auch nicht zur Prüfung über OpenRouter. Die Fremdprüfung (`/critic`) ist für OT-Code gesperrt.
* **Nur DSGVO-konforme Modelle:** Wenn externe Modelle für OT-Code verwendet werden, dann ausschließlich Modelle ohne Datenweitergabe für Training (OpenRouter/Claude/Haiku). OpenAI, Groq etc. sind ausgeschlossen.
* **Safety bleibt Hardware:** Not-Halt, Feuerwehr-Modus und sicherheitsrelevante Logik werden nie von einem KI-Agenten programmiert oder verändert.

---

## 📐 Namenskonventionen (Stilfrage, nicht sicherheitsrelevant)

Diese Konventionen dienen der Lesbarkeit — sie haben keine sicherheitstechnische Bedeutung:

| Präfix | Typ | Beispiel |
|---|---|---|
| `b` | BOOL | `bStart` |
| `r` | REAL | `rSollwert` |
| `i` | INT | `iZaehler` |
| `di` | DINT | `diPosition` |
| `ui` | UINT | `uiIndex` |
| `udi` | UDINT | `udiZaehler` |
| `t` | TIME | `tVerzoegerung` |
| `s` | STRING | `sFehlermeldung` |
| `st` | STRUCT | `stHMI_Data` |
| `fb` | FUNCTION_BLOCK | `fbHauptantrieb` |
| `e` | ENUM | `eMaschinenZustand` |

Schrittketten in Zehner-Schritten (10, 20, 30…) mit Enum (`eStep : E_State`), Lücken für spätere Erweiterungen freilassen.

---

## 📁 Datei-Registrierung (Bautechnisch)

Neue `.TcPOU` oder `.TcDUT` müssen in der `.plcproj` registriert werden:

```xml
<Compile Include="POUs\FB_Name.TcPOU">
  <SubType>Code</SubType>
</Compile>
```

