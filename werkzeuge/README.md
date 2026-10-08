# Werkzeuge für den PC

Kleine Helfer für Sebastians Windows-PC. Sie gehören zu keinem Projekt.

## `programme_aufraeumen.ps1` — Programme kontrolliert deinstallieren (08.10.2026)

Anlass: Laufwerk C: war voll (238 von 238 GB). Viele Programme sind installiert, die
nicht mehr gebraucht werden.

**Was es tut:** Ein Fenster listet alle deinstallierbaren Programme. Dazu gehören die
klassischen Programme aus der Registry und Store-Apps, auf Wunsch auch Windows-eigene
Store-Apps. Zu jedem Programm stehen Größe, Herausgeber, Datum und eine Empfehlung.

| Empfehlung | Bedeutung | Vorab geschützt? |
|---|---|---|
| Deine Liste | Hermes, Claude, Codex, Antigravity, DeepL, PowerShell, pCloud, Google Drive, OneDrive, Teams, Git, Python, Node.js, Android Studio, Edge, Comet, Bitwarden, VS Code, scrcpy, FFmpeg … | ja |
| Laufzeit/Treiber | Visual-C++-Pakete, .NET, WebView2, Treiber; davon hängen andere Programme ab | ja |
| Windows-App | Store-Apps von Microsoft | ja |
| Arbeit/Studium | Beckhoff/TwinCAT, Visual Studio, Office, SQL Server, TeXstudio, CEWE … | nein, du entscheidest |
| Du entscheidest | alles andere | nein |

**Nichts passiert unkontrolliert:**
1. Für die Deinstallation ist anfangs **nichts** angehakt.
2. „Brauche ich" schützt ein Programm. Die Auswahl wird sofort gespeichert und beim nächsten
   Start wieder geladen. Ein geschütztes Programm lässt sich nicht zur Deinstallation auswählen.
3. „Ausgewählte deinstallieren …" zeigt die Liste noch einmal und fragt nach.
4. Danach startet je Programm dessen **eigenes** Deinstallationsprogramm, nacheinander und mit
   dessen Rückfragen. Store-Apps werden über `Remove-AppxPackage` entfernt.
5. Jede Deinstallation steht im Protokoll: Name, Version, Befehl, Exit-Code.

**Aufruf** (PowerShell **als Administrator**):

```powershell
& "C:\Users\sebas\Desktop\workspace agentic engineering\werkzeuge\programme_aufraeumen.ps1"
```

Nur anschauen, ohne Admin und ohne Fenster:

```powershell
& "C:\Users\sebas\Desktop\workspace agentic engineering\werkzeuge\programme_aufraeumen.ps1" -NurListe
```

**Ablage** (außerhalb des Repos): `%LOCALAPPDATA%\ProgrammAufraeumen\`
- `brauche_ich.json`: deine Schutzliste.
- `protokoll.csv`: alle Deinstallationen. Eine Deinstallation lässt sich nicht rückgängig
  machen. Das Protokoll zeigt, was neu zu installieren wäre.

**Prüfung:**
- PowerShell-Parser ohne Fehler.
- `-NurListe` auf dem PC am 08.10.2026 durchgelaufen. Die Empfehlungen wurden nach der
  ersten Liste korrigiert: TwinCAT-Git zählt nicht als „dein Git", Codex, Antigravity,
  scrcpy und FFmpeg sind geschützt.
- Die Datei ist UTF-8 **mit BOM** gespeichert, sonst zeigt Windows PowerShell 5.1 die
  Umlaute falsch.
- Achtung beim Bearbeiten: Die Zeichen „ “ ” gelten in PowerShell als Anführungszeichen. In
  "…"-Texten deshalb nur `'` verwenden.
