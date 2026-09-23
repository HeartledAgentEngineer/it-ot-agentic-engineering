# Marcel-Praxisblöcke — Everlast AI „KI-NEWS", Playlist-Positionen 1–8 (neueste zuerst)

**Quelle:** Öffentliche YouTube-Untertitel (Auto-Captions, `de-orig.vtt`) der Playlist
`PLk7pG7wpqjW3pOq7tGV_t21wkJjfL3zmC` (137 Videos, Positionen 1–8).
**Datum der Auswertung:** 23.09.2026 · **Umfang:** 8 Videos, 29:39 / 25:18 / 29:05 / 28:36 / 29:23 / 29:42 / 26:54 / 28:19
**Hinweis zur Zitat-Treue:** Zitate sind wörtlich aus den Auto-Untertiteln übernommen. ASR-Fehler
(z. B. „Codepaste" statt Codebase, „Hurder", „Bass") bleiben stehen und sind mit `[Anm.: …]`
gekennzeichnet, statt stillschweigend korrigiert zu werden. Unsichere Produktnamen sind als solche markiert.
**Ergebnis vorab:** 7 von 8 Videos enthalten einen Marcel-Block; **1 Video (z8OocncaeEs) enthält keinen.**

---

## 1) 38qNMuPd0eo — „KI-Notbremse: DAS steckt wirklich dahinter! Es ist NICHT, was die dir erzählen | KI-NEWS"

**Marcel-Stelle: 18:40 – 22:10** (Leonard-Übergabe: „Ich habe mal den Marcel aus unserem Engineering Team gebeten, das zu zeigen.")

| Zeit | Wörtliches Zitat |
|---|---|
| 18:40 | „Ich habe mal den Marcel aus unserem Engineering Team gebeten, das zu zeigen. Ja, also wie schafft man es überhaupt? seine Agenten tagelang am Stück durcharbeiten zu lassen." |
| 18:52 | „Das ist essentiell, bevor du beispielsweise ein neues Feature oder auch einen Bugfix in deine Codepaste [Anm.: Codebase] implementierst, dass du primär erstmal mit einer Planning Session einen Plan erstellst." |
| 19:02 | „Dieser Plan wird dann später in GitHub beispielsweise abgespeichert Form von einem Issue." |
| 19:10 | „Doch wenn es dann nun an die Implementierung dieses Issues geht, ist es essentiell, dass du nicht die gleiche Session, mit welcher du den Plan erstellt hast, zum Implementieren benutzt, sondern du das Planner Worker Prinzip anwendest." |
| 19:27 | „Bei dem Planner Worker Prinzip arbeitest du prinzipiell mit zwei neuen Sessions, jeweils mit einem neuen bzw. anderen LM Modell." |
| 19:36 | „Wichtig dabei ist, dass das Modell, welches für die Planner Session ausgewählt wurde, nicht das gleiche Modell ist, mit welchem du den Plan zuvor erstellt hast." |
| 19:45 | „Denn die Planner Session verifiziert noch mal deinen gesamten Plan, bevor sie dann Aufgabe für Aufgabe, um diesen Plan abzuarbeiten, an die Worker Session gibt." |
| 19:57 | „Während die Worker Session arbeitet, kontrolliert die Planner Session, die Arbeit des Workers, dokumentiert alles auf GitHub und meldet sich beispielsweise mit gewünschten Anpassungen wieder beim Worker." |
| 20:13 | „Das Ganze geht so lange hin und her, bis das gesamte Issue abgearbeitet ist." |
| 20:19 | „Beispielsweise habe ich genau mit diesem Planner Worker Prinzip aktuell den gesamten Datef [Anm.: Dart] MCP gebaut. Hier siehst du einmal links die Planner Session und rechts die Worker Session. Das Ganze hat insgesamt vier Tage lang gedauert." |
| 20:47 | „Vier Tage lang haben der Planner und der Worker sich untereinander ausgetauscht, das gesamte GitHub Issue, also den Plan abgearbeitet, alles feinsäuberlich dokumentiert und der Worker hat eine Aufgabe nach der anderen abgearbeitet" |
| 20:56 | „und dies kann ich natürlich vielfach parallel laufen lassen. beispielsweise habe ich jetzt hier nicht nur vier Tage lang den Dart MCP bauen lassen, sondern habe unter anderem auch in einer anderen Session noch nebenbei einen Elster MCP gebaut" |
| 21:12 | „dass hier der Worker dementsprechend am Arbeiten ist und sobald er fertig ist wiederum den Planner informiert, damit der Planner dem Worker den nächsten Step geben kann zum Abarbeiten." |
| 21:25 | „Und zwar benutze ich in diesem Fall hier Hurder [Anm.: Produktname in der ASR unklar, vermutlich „Herd" – vgl. Video IYzgxWs4sZ4, 18:50: „Herd mit dem Agent Management"]. Hurder kümmert sich darum, dass diese zwei Sessions über einen Skill miteinander kommunizieren können und somit Informationen austauschen können." |
| 21:42 | „Und wenn beispielsweise der Planner von dem Worker irgendeine Information bekommen hat … was ich jetzt in meinen Terminkalender wissen muss oder aber auch ich wieder dran erinnert werden muss, sendet der Planner das dementsprechend an eine weitere Session, hier in dem Fall an eine sogenannte Backoffice Session" |

**Ableitbare Praktiken**
1. **Erst Plan-Session, dann Implementierung** – niemals direkt ins Coden; am Anfang steht eine dedizierte Planungs-Session.
2. **Plan als Artefakt versionieren** – das Ergebnis der Plan-Session landet als GitHub-Issue, nicht im Chatverlauf (Plan ist damit prüfbar, verlinkbar, wiederfindbar).
3. **Session-Trennung (Planner ≠ Worker)** – die implementierende Session ist NICHT die planende Session; Kontext-Trennung statt Kontext-Verschmutzung.
4. **Modell-Diversität als Verifikation** – Planner läuft auf einem anderen Modell als das, mit dem der Plan entstand; das erzwingt echte Fremdprüfung des Plans statt Selbstbestätigung.
5. **Planner als Reviewer-Schleife** – Planner kontrolliert, dokumentiert und schickt Anpassungen zurück; Loop bis das ganze Issue abgearbeitet ist (nicht bis die erste Antwort „fertig" sagt).
6. **Dokumentation läuft automatisch mit** – „alles feinsäuberlich dokumentiert" auf GitHub, pro Aufgabe.
7. **Parallelisierung mehrerer Aufträge** – mehrere Planner/Worker-Paare gleichzeitig betreiben (Dart MCP + Elster MCP „nebenbei").
8. **Session-zu-Session-Kommunikation über Skills** – nicht der Mensch kopiert zwischen Sessions, sondern die Sessions sprechen über einen Skill miteinander.
9. **Dritte Rolle für Mensch-Schnittstelle** – eine zusätzliche „Backoffice"-Session übersetzt Agenten-Output in menschenrelevante Ausgabe (Terminvorbereitung, Erinnerungen).
10. **Erwartungsmanagement Laufzeit** – ein komplexer Bau läuft realistisch **4 Tage am Stück**; das ist der Normalzustand, nicht ein Fehler.

---

## 2) nV55rZLPPjc — „Es ist passiert: KI löst ein Millenium-Problem! DAS bedeutet es jetzt wirklich + weitere KI-News"

**Marcel-Stelle: 17:43 – 21:07** (Übergabe 17:27: „Und damit will ich jetzt noch mal dem Marcel das Wort überlassen. Der hat nämlich jetzt die letzte Woche mit unserem Developer Team über 6 Milliarden Tokens verheilt [Anm.: verheizt] mit GBT6 Astra, wie dieses Modell dann wirklich neben all dem Hype in der Praxis funktioniert.")

| Zeit | Wörtliches Zitat |
|---|---|
| 17:43 | „Ein Computer gesteuert von einem LM. So richtig gut funktioniert das erst seit GPT6 Astra." |
| 17:51 | „Vor allem bei der Entwicklung von Voicley [Anm.: Produktname ASR-unsicher] haben wir festgestellt, dass im Bereich des Testings, also wenn wir beispielsweise einen Bug Report gemeldet bekommen von den Nutzern oder aber auch wenn wir ein neues Feature testen und verifizieren wollen, GPT6 Astra im Bereich des Computeruse und unfassbar viele Vorteile bringt." |
| 18:26 | „Und hier siehst du schon, ich habe einmal links eine Pain [Anm.: Pane/Session] offen für macOS, rechts oben eine Pain offen für Windows. Ich habe hier die Möglichkeit, dass ich dem Windows Rechner, welcher für Voicely zuständig ist, von hier aus steuern kann." |
| 18:41 | „Und diese beiden Sessions tauschen Information untereinander aus. Sprich, sobald es eine Änderung auf Windows gibt, informiert die Windows Session die MacOS Session und andersrum genauso." |
| 19:21 | „Was du gerade auf dem Video gesehen hast, war GPT6 Astra, wie er den Windows Computer gesteuert hat und selber im Prinzip die Tasten simuliert hat" |
| 19:37 | „und auch dadurch, dass ja der Lautsprecher direkt vor dem Mikrofon stand, er selber diese Latenz, die er zuvor festgestellt hatte, verifizieren konnte." |
| 19:46 | „Er hat damit angefangen, dass er die Ist Situation festgehalten hat und so lange den Code angepasst und geprüft, bis dann die Latenz wirklich instantan war." |
| 20:03 | „GPT6 Astra hat folgendes festgestellt. Zuvor war die Latenz bei Voice Lied deswegen so lange, weil beispielsweise unter Windows zuerst über die Powerhell [Anm.: PowerShell] angefragt wurde, ob Voicel Zugriff auf das Mikrofon hat. Hier sind wir dann bei einer gesamten Latenz von etwas über 600 Millisekunden" |
| 20:34 | „Jetzt nachdem GPT6 Astra alles mögliche durchgetestet hat, um den schnellsten Weg zu finden, haben wir nun nur noch eine Latenz von 7 Millisekunden, bis Voicley reagiert." |
| 20:48 | „Und das ganze hat GPT6 Astra so umgesetzt, dass er nicht mehr eine PowerSell [Anm.: PowerShell] startet für Voicely, sondern dementsprechend jedes Mal, wenn der User den Hotkey drückt, einfach Voicely selber direkt eine Schnittstelle an diese rechte Verwaltung [Anm.: Registry/Rechteverwaltung, ASR-unsicher] stellt und somit direkt die Antwort bekommt." |

*Randnotiz aus dem Block davor (Leonard, 17:13, kein Marcel-Zitat):* „wir nutzen GBT6 aber auf Fable nur auf Medium und kommen dadurch kaum an Usage Limits" — Reasoning-Stufe „medium" liefert laut DeepSam-Benchmark dieselbe Qualität wie „extra high" bei 25 % geringeren Kosten.

**Ableitbare Praktiken**
11. **Computer-Use als Verifikationswerkzeug** – einen echten Desktop fernsteuern lassen, statt sich auf Textbeschreibungen zu verlassen; explizit für Testing/Feature-Verifikation und Bug-Reports.
12. **Plattform-Sessions koppeln** – je Zielsystem (macOS/Windows) eine eigene Session, die sich gegenseitig über Änderungen informieren; kein „eine Session muss alles wissen".
13. **Ist-Zustand zuerst messen** – vor jeder Optimierung den Ist-Zustand festhalten (hier: 600+ ms Latenz) und als Baseline dokumentieren.
14. **Messen statt behaupten** – den Erfolg selbst nachmessen lassen (der Agent hat die Latenz über Lautsprecher→Mikrofon selbst verifiziert: 600 ms → 7 ms).
15. **Iterationsschleife „anpassen und prüfen"** – so lange Code anpassen und testen, bis das Zielkriterium („instantan") wirklich erreicht ist.
16. **Ursache vor Lösung** – Ursachenanalyse durch den Agenten: nicht „schneller machen", sondern den konkreten Verursacher finden (Prozess-Start pro Hotkey) und durch eine direkte Schnittstelle ersetzen.
17. **Günstigere Reasoning-Stufe als Default** – gleiche Qualität auf „medium" statt „extra high" ⇒ Kosten-/Limit-Hebel von 25 % (Leonard, nicht Marcel).

---

## 3) BSyes3ApU8c — „GPT-6 Astra: ‚DAS wird die Welt für immer verändern!' Alles was du jetzt wissen musst | KI-NEWS"

**Marcel-Stelle: 12:44 – 19:55** (Übergabe 12:44: „Dazu habe ich jetzt mal unser AR [Anm.: AI] Developer, den Marcel gebeten, das in die Praxis einzuordnen. Marcel, was ist denn deine Meinung dazu?")

| Zeit | Wörtliches Zitat |
|---|---|
| 12:50 | „Bei der Entwicklung eines neuen Features ist es essentiell, dass du unterscheidest zwischen einem sogenannten Greenfield Projekt, sprich einem Projekt, wo noch nichts vordefiniert ist, keine Architektur, keine Codebase, gar nichts und einem sogenannten Brownfield Projekt, wo du natürlich dementsprechend schon eine Architektur definiert hast, gewisse Funktionalitäten bereits bestehen" |
| 13:20 | „Wenn du das Ganze ohne einen Prototypen baust, hast du die Gefahr und meistens ist es auch genau der Fall, dass du dieses Feature implementierst und dann auf einmal es irgendwo klemmt. Und genau aus dem Grund ist es ratsam, dass du Prototypen verwendest." |
| 13:40 | „Mit einem Prototyp definierst du einmal das Feature völlig unabhängig von der restlichen Codebase und der Architektur und stellst einfach nur fest, dass die Funktionalität, welche du haben möchtest, perfekt funktioniert. Und sobald dies gegeben ist, fährst du fort und fügst es dann in deine bereitsfahrende [Anm.: bereits fahrende/bestehende] Codebase ein" |
| 14:00 | „und da diese Woche sowohl TPT6 [Anm.: GPT-6] Astra und Fable 5.1 ein [Anm.: veröffentlicht] worden sind, haben wir uns bei Relation Flow gedacht, wir bauen einen Prototypen für eine ganz einfache, simple Funktionalität." |
| 15:40 | „Das einzige, was nicht sehr sauber aussieht, ist aktuell, dass hier überall einfach nur Feld und die Nummer steht. Das ist dann tatsächlich für das Schema, wie die Daten abgefragt werden, nicht ganz so übersichtlich. Und was jetzt auch nicht toll ist, ich muss jetzt hier bei jedem einzelnen auf übernehmen klicken." |
| 16:20 | „Für den Prototypen okay, die Funktionalität ist gegeben, aber von der User Experience müsste man hier auf jeden Fall noch mal nacharbeiten." |
| 18:00 | „was GPT6 aber sehr interessant umgesetzt hat. Und zwar kommuniziert GPT6 im Vergleich zu Fable 5.1 direkt mit der API jetzt hier in dem Fall von MRAL [Anm.: Mistral, ASR-unsicher], um die Daten aus dem PDF, also den Text mittels des OCR herauszuziehen." |
| 18:20 | „denn dadurch, dass wir direkt mit der API kommunizieren, haben wir nicht das Limit wie bei Versell [Anm.: Vercel] jetzt beispielsweise von 20 Mbit pro Datei, wodurch wir hier bei GPT Astra natürlich deutlich größere PDFs direkt im Prototyp testen können." |
| 19:00 | „Dafür hat Fable 5.1 eine weitere Dependency geladen, in dem Fall React PDF, um einfach das Ganze optisch besser darstellen zu können. Des weiteren hat Fable 5.1 aber auch einen dynamischen Worker importiert, eine zweite Dependency" |
| 19:20 | „Und wir haben hierbei ganz klar festgestellt, dass GPT6 deutlich besser ist in der Isolation und auch beim Puncttous Security [Anm.: Punkt/Aspekt Security]." |
| 19:35 | „Wo GPT6 allerdings nicht so gut war, ist beispielsweise, wenn wir jetzt diesen Prototypen nehmen würden und dann hier das Ganze direkt in die Codebase geben würden, würden unsere aktuellen Tests fehlschlagen. Das heißt, hier müssten wir noch mal nacharbeiten" |
| 20:00 | „heißt für uns ganz klar GPT6, was Codesauberkeit, Security und Scalability angeht und Fable 5 nach wie vor UI UX, also alles was Front-End betrifft." |

**Ableitbare Praktiken**
18. **Greenfield vs. Brownfield explizit klassifizieren** – vor dem Start einordnen, ob es eine bestehende Architektur/Codebase gibt; davon hängt das Vorgehen ab.
19. **Prototyp vor Integration** – neues Feature zuerst völlig unabhängig von Codebase und Architektur bauen; erst wenn die Funktionalität nachweislich funktioniert, in die bestehende Codebase einfügen.
20. **Prototyp als Modell-Vergleichsbank** – dieselbe kleine, klar umrissene Aufgabe mit mehreren Modellen bauen lassen und den Output vergleichen (gleiche Aufgabe = vergleichbares Ergebnis).
21. **Code, nicht nur Optik bewerten** – beim Vergleich ausdrücklich in den Code springen, nicht bei der UI-Demo stehen bleiben.
22. **Integrations-/Test-Prognose stellen** – vor dem Merge prüfen, ob die bestehenden Tests mit dem Prototypen durchlaufen würden, und Lücken benennen.
23. **Modell-Stärken zuordnen statt „bestes Modell"** – Modellwahl nach Aufgabenklasse: Code-Sauberkeit/Security/Scalability vs. UI/UX/Frontend.
24. **Bewertungskriterien festhalten** – Befunde konkret protokollieren (fehlende Feldnamen, Einzelbestätigung pro Feld, 20-Mbit-Limit, unnötige Dependencies) – so wird Modellwahl reproduzierbar.
25. **Prototyp-Status offen markieren** – „für den Prototypen okay, UX muss nachgearbeitet werden" statt als fertig zu verkaufen.

---

## 4) tHv7eyiDPWg — „‚DAS ist ein Warnschuss für die Welt!' OpenAI-Agenten bilden SCHWARM & fälschen Protokolle | KI-NEWS"

**Marcel-Stelle: 22:52 – 27:35** (Übergabe 22:52: „Da gibt der Marcel, einer unserer Lead Developer, die jetzt mal einen kleinen Einblick.")

| Zeit | Wörtliches Zitat |
|---|---|
| 22:52 | „Du kennst das bestimmt auch. Du gibst einen Prompt an die KI und der Output ist einfach nicht so, wie du ihn dir vorstellst, obwohl du beispielsweise zehn oder noch mehr Skills installiert hast, alleine für den Bereich UI und UX. Und genau deswegen zeige ich dir mein Setup. Um das Ganze umzusetzen, brauchst du nur drei ganz einfache Prinzipien befolgen." |
| 23:20 | **„Prinzip Nummer 1 ist nutze KI, um KI einzurichten."** |
| 23:27 | „Denn früher hattest du beispielsweise nicht die Möglichkeit, dass du Excel verwendest, um Excel zu bedienen oder um dir Excel richtig zu konfigurieren. Das kannst du aber mit KI. Erkläre ihr einfach in einer Session, was du machst, welche Arbeitsabläufe du hast. wie beispielsweise ein Ergebnis aussehen soll. Am besten gibst du ihr sogar noch Beispiele mit und dann kann die KI wirklich für dich so arbeiten, dass die Ergebnisse so aussehen, als hättest du es selber gemacht." |
| 23:53 | **„Prinzip Nummer 2 ist sei wirklich wählerisch bei dem, was du installierst. Du brauchst nicht tausende Skills oder Plugins und MCPs für ein und die gleiche Aufgabe, damit du hier nicht einen absoluten Overload machst."** |
| 24:00 | „Halte dich an Prinzip 1. Gehe in Konversation mit der KI und zeige ihr, was du jetzt gerade am Überlegen bist, welchen Skill du beispielsweise interessant findest oder aber auch welchen Agenten du interessant findest und entscheide zusammen mit der KI, ob das Ganze in dein Setup überhaupt passt oder ob du nicht vielleicht sogar schon eine eigene Lösung installiert hast für dieses Problem." |
| 24:40 | „Prinzip Nummer 3 ist dann tatsächlich die Umsetzung des Ganzen im Alltag. Wenn du dann mit der KI arbeitest und du der KI beispielsweise sagst, implementiere Feature XY, brauchst du dich nicht wundern, dass das Ergebnis nicht dem entspricht, was du dir vorstellst." |
| 25:00 | „Denn woher soll denn die KI beispielsweise wissen, was du präferierst oder aber auch wie du es dir genau in diesem spezifischen Fall vorstellst? Denn natürlich, wenn du Prinzip 1 befolgt hast, weiß sie z.B. welche Farben dir gefallen, wie deine Corporate Identity aussieht, welche Schriftarten du bevorzugst, welche Tonalität du bevorzugst. Aber das kann ja auch mal in einem bestimmten Fall komplett anders aussehen oder überhaupt nicht relevant sein." |
| 25:28 | **„Und genau aus diesem Grund starte immer mit dem Planmodus. Hier kannst du wirklich sagen, ich möchte Feature XY implementieren und dann in eine Fragerunde mit der KI starten."** |
| 25:40 | „Um dir das Ganze einfach mal anhand von einem Beispiel zu zeigen, springen wir mal in GitHub. Hier siehst du ein Epic Issue, also ein zusammenfassendes Issue, was mehrere Unterfaben [Anm.: Unteraufgaben] in sich beinhaltet" |
| 26:20 | „wäre ich jetzt einfach hergegangen und hätte gesagt, implementiere diese Funktionalität, dann wäre da niemals solch ein umfangreicher Plan dabei rumgekommen, wo sogar Akzeptanzkriterien festgelegt worden sind, Unterfaben [Anm.: Unteraufgaben] festgelegt worden sind" |
| 26:45 | „denn hier habe ich ungefähr run about [Anm.: rund about/etwa] 200 Fragen beantwortet und jedes Mal wieder stelle ich fest, dass ich mit Fragen konfrontiert werde von der KI, an die ich beispielsweise selber gar nicht gedacht hätte, wo ich dann aber auch gar nicht mehr dran denken muss, wenn es dann an die Implementierung geht" |
| 27:07 | „denn ich weiß, nachdem dieser Plan zusammen mit der KI ausgearbeitet wurde, ist das Endergebnis genauso, wie ich es mir vorgestellt habe." |
| 27:20 | „Und wenn du diese drei Prinzipien wirklich berücksichtigst, wirst du feststellen, dass es vollkommen egal ist, welches Fronttiermodel [Anm.: Frontier-Modell] du benutzt, ob du Cloud [Anm.: Claude] benutzt oder Codex benutzt, denn das Ergebnis wird immer demsprechen [Anm.: dem entsprechen], was du dir vorstellst." |

**Ableitbare Praktiken**
26. **Setup mit KI einrichten, nicht per Hand** – der KI in einer Session Arbeitsabläufe, gewünschte Ergebnisse und Beispiele erklären; die KI richtet darauf ihr eigenes Setup/Skills ein.
27. **Skill-Disziplin gegen Overload** – keine zehn+ Skills/Plugins/MCPs für dieselbe Aufgabe; Abdeckung prüfen, Duplikate vermeiden.
28. **Installations-Entscheidungen als Dialog** – vor dem Installieren eines Skills/Agenten gemeinsam mit der KI prüfen, ob er ins Setup passt oder ob es die Lösung schon gibt.
29. **Präferenzen explizit hinterlegen** – Farben, Corporate Identity, Schriftarten, Tonalität einmal beschreiben; sie sind Standardkontext, nicht jedes Mal neu zu erklären.
30. **Immer im Planmodus starten** – „implementiere Feature XY" ist verboten als erster Schritt; erst Planmodus, dann Fragerunde.
31. **Planmodus-Maßstab: ~200 Rückfragen** – die Fragen der KI sind der Wert, nicht die Bremse; Fragen, an die man selbst nicht gedacht hätte, sind der eigentliche Qualitätsgewinn.
32. **Akzeptanzkriterien und Unteraufgaben im Plan** – Epic-Issue-Struktur mit Acceptance Criteria und Sub-Tasks, bevor implementiert wird.
33. **Modell-Unabhängigkeit als Zielgröße** – richtig aufgesetztes Setup (Plan + Kontext) macht das Ergebnis unabhängig von der Wahl zwischen Claude und Codex.

---

## 5) kMuT8Uc7q6U — „Chinas Roboter drehen frei: DAS passiert hier gerade wirklich + Geheimmodell schlägt Fable 5"

**Marcel-Stelle: 11:25 – 16:20** (Übergabe 11:25: „Und dazu gebe ich mal weiter an einen meiner Developer, den Marcel. Was ist denn deine Meinung dazu?")

| Zeit | Wörtliches Zitat |
|---|---|
| 11:25 | „In einem anderen Vergleich hatten wir ja schon mal mehrere Modelle gegeneinander antreten lassen und 3D Webseiten mit Hilfe von 3JS [Anm.: Three.js] bauen lassen. Das gleiche haben wir jetzt auch einmal mit OX Alpha [Anm.: Produktname ASR-unsicher] gemacht" |
| 11:40 | „Aber selbstverständlich schauen wir hier, was den Code angeht und natürlich auch wie die ganze Funktionalität der Webseite dann ist." |
| 12:40 | „Aber selbstverständlich haben wir uns das Ganze auch noch mal aus einer ganz anderen Perspektive angeschaut und zwar in einem sehr, sehr großen Projekt, wo schon sehr viel passiert ist und auch dementsprechend natürlich auch die Genauigkeit noch mal deutlich wichtiger ist." |
| 13:00 | „Und aus diesem Grund haben wir uns dafür entschieden, OX Alpha einfach mal auf Relation Flow loszulassen in einer kleinen Sandbox. sozusagen und dementsprechend Aufgaben, welche wir immer in Epic Issues bei GitHub bündeln, mal gemeinsam mit OX Alpha anzugehen." |
| 13:20 | „Und zwar wollten wir einfach mal sehen, wie gut findet sich Ox Alpha in einer sehr sehr großen Codebase zurecht, weil beispielsweise das Projekt mit dem 3D Auto hat ja Ox Alpha komplett von Scratch auf, also von null aufgebaut und bei Relation Flow ist ja schon deutlich mehr vorhanden" |
| 14:00 | „dass wir mit Hilfe von Ox Alpha einmal die gesamte Codebase uns angeschaut haben und hier nun festgestellt haben, dass sehr sehr viele Fehlermeldungen im Prinzip, die dann auch beim Kunden am Ende des Tages ersichtlich werden, Fehlermeldungen sind, welche technisch sind, welche auch manchmal dann Serverlogs enthalten und das wollen wir natürlich nicht" |
| 14:33 | „Deswegen ist Ox Alpha losgegangen, hat einmal sich die gesamte Codebase gemeinsam mit uns angeschaut, hat dementsprechend dieses Epic Issue mit uns angelegt und hier dementsprechend auch so wie wir es in unserem Projekt einfach machen, Subissues gemacht, also Unterfgaben [Anm.: Unteraufgaben], um dieses übergeordnete Thema vollend [Anm.: vollends] abschließen zu können." |
| 14:52 | „Hier sehen wir bereits, dass OX Alpha sehr sehr gut damit umgehen kann, wenn die Codebase sehr groß ist und auch sehr gut damit umgehen kann, das Ganze zu planen und danach nach dem Plan, nachdem dieses Issue angelegt wurde, es auch abzuarbeiten." |
| 15:00 | „Hier sehen wir nämlich schon, dass die Session, in welcher wir das Epic Issue geplant haben, tatsächlich auch das Ganze jetzt gerade sequentiell abarbeitet nach Gitflow Standards und dementsprechend immer sobald ein Subissue, also eine Unterfabe abgearbeitet ist, dementsprechend einen Pull request macht, damit das Ganze wieder in das Repo hineinkommt." |
| 15:33 | „Und bisher müssen wir tatsächlich sagen, dass Ox Alpha sich wahnsinnig gut orientieren kann. und tatsächlich sehr sehr gut komplett autonom laufen kann. Also wir haben hier wirklich zwei drei Prompts eingegeben, um einfach das Sparing [Anm.: Sparring] mit dem Modell zu halten und dementsprechend seitdem arbeitet OX Alpha komplett alleine das Ganze ab." |
| 15:57 | „Wie wir sehen, haben wir bereits 150.000 jetzt etwas mehr Tokens verbraucht und insgesamt nur 15% vom Kontextfenster." |

**Ableitbare Praktiken**
34. **Feste Benchmark-Aufgabe für Modellvergleiche** – immer dieselbe Aufgabe (z. B. 3D-Webseite mit Three.js) über mehrere Modelle, damit Ergebnisse vergleichbar sind.
35. **Zwei Prüf-Perspektiven** – Modell erst auf einer isolierten Aufgabe (Greenfield), dann in einer großen bestehenden Codebase (Brownfield) testen.
36. **Sandbox für Fremdmodelle** – neue/unbekannte Modelle zuerst in einer abgeschotteten Sandbox auf das echte Projekt loslassen.
37. **Refactoring in Epic Issues bündeln** – ein übergeordnetes Thema als Epic mit Subissues, nicht als Sammel-PR.
38. **Realistischen, fachlich relevanten Fehlerfall wählen** – technische Fehlermeldungen mit Serverlogs, die beim Kunden sichtbar würden, statt synthetischer Testaufgaben.
39. **Nach Gitflow-Standards abarbeiten** – pro Subissue ein Pull Request zurück ins Repo; keine großen ungeteilten Merges.
40. **Sparring-Prompts statt Dauerbetreuung** – 2–3 Prompts zum Einsteuern, danach vollständig autonom laufen lassen.
41. **Kontext-/Token-Verbrauch überwachen** – Token-Zahl gegen Kontextfenster mitlesen (150k Tokens ≈ 15 % Kontextfenster) und als Abbruch-/Steuerkriterium nutzen.
42. **Beobachtung: Plan-Session kann selbst abarbeiten** – hier wurde bewusst NICHT getrennt: dieselbe Session, die das Epic geplant hat, arbeitet es sequentiell ab (Unterschied zum Planner-Worker-Prinzip aus Video 1; dort explizite Trennung, hier eine Session mit Gitflow-Inkrementen).

---

## 6) z8OocncaeEs — „Krass: Claude markiert jetzt JEDEN Text mit Wasserzeichen! So wirst du es los | KI-NEWS"

**Kein Marcel-Block.** Das Transkript (29:42, 875 Segmente) enthält **null** Treffer für `Marcel`,
`Engineering`, `Developer/Entwickler`, `Claude Code`, `Codex`, `Skill`, `Planner`, `Worker`, `Subagent`,
`Kontextfenster`. Es gibt in diesem Video also **keinen** Praxisblock aus dem Engineering-Team
(kein Ersatz-Auftritt, nichts, was hier erfunden werden müsste).

---

## 7) YGfd1LiTQiY — „KI-Agenten brechen reihenweise aus: DAS passiert gerade wirklich! KI-NEWS"

**Marcel-Stelle: 18:35 – 22:40** (Übergabe 18:35: „Und damit gebe ich weiter an einen unserer Developer, den Marcel. Marcel, was ist den mit Relation Flow jetzt möglich?")

| Zeit | Wörtliches Zitat |
|---|---|
| 18:41 | „Mit dem neuen Update von Relation Flow habt ihr die Möglichkeit, eure Tools, die ihr im Alltag jeden Tag benutzt, ganz einfach mit Relation Flow zu verbinden." |
| 18:52 | „Um diese Verbindung herzustellen, navigiert ihr einfach in die Einstellungen und der Verbindungen und schon findet ihr eine Liste von allen möglichen Tools, die nur da drauf warten, von euch mit Relation Flow verbunden zu werden." |
| 19:00 | „Für dieses Beispiel habe ich einmal fünf Verbindungen hergestellt. Hubspot, Outlock [Anm.: Outlook], Google Sheets, Mailchimp und Typeform." |
| 19:12 | „Anhand von einem einfachen Beispiel möchte ich euch nun zeigen, wie ihr diese Tools in einem Chat alle gebündelt benutzen könnt und somit nicht nur Zeit sparen könnt, sondern auch immer wiederkehrende Arbeit ganz einfach mit ein paar Fragen in einem Chat überflüssig macht." |
| 19:40 | „Dementsprechend ist Relation Flow hergegangen, hat sich erstmal alle Informationen aus Hubspot herausgesucht und hat dann nachgefragt, wie denn das Google Sheet heißt." |
| 20:00 | „Nachdem ich Relation Flow gesagt habe, wie das Google Sheet betitelt wurde, hat natürlich Relation Flow auch hier die Daten herausgezogen und dementsprechend mit den Daten aus Hubspot kombiniert." |
| 20:20 | „Und ganz am Ende wollte ich diese gesamten Daten, die ja jetzt gebündelt nur in diesem Chat gerade existieren würden, mit Hilfe der Outlook Verbindung per Mail an meinem Vertriebsteam schicken." |
| 20:40 | „Wir haben hier einfach nur gesagt, erstelle einen Entwurf in Outlook und schon geht Relation Flow her. Nutzt die bestehende Verbindung, erstellt mir einen Entwurf in Outlook selber und ich brauche ihn nur kurz Korrektur lesen und kann sofort auf Absenden drücken." |
| 21:00 | „Jetzt ist diese Arbeit ja aber etwas, was gerade im Vertrieb nicht alle heilige Zeit [Anm.: alle heiligen Zeiten] mal passiert, sondern regelmäßig stattfindet. Aus diesem Grund wäre es natürlich praktisch, wenn wir ganz einfach diese Analysen und diese Chats in einem Projekt zusammen bündeln könnten." |
| 21:20 | „Ich habe hier die Möglichkeit, die analytische Auswertung in meinem Firmenwissen abzuspeichern in einem bestimmten Ordner beispielsweise Vertriebsanalysen, welcher wiederum mit einem Projekt verbunden ist, der genau diese Chats dann, indem ich den Chat einfach in dem Projekt hinzufüge, dann bündelt" |
| 21:55 | „Und wenn ich jetzt nächste Woche genau die gleiche Aufgabe noch mal machen muss oder ein Kollege, haben wir die Informationen aus den vergangenen Analysen für die KI bereits aufbereitet." |
| 22:07 | „Genau für solche Arbeitsabläufe und auch noch viele, viele andere haben wir die Relation Flow Community gebaut. Ihr braucht nicht mehr selber euch Gedanken drüber machen, wie ihr einen Agenten definiert, einen Prompt schreibt oder aber auch einen Skill erstellt. Ihr könnt einfach aus der Relation Flow Community auf einen Button klicken und schon wird das Ganze in euer Relation Flow übertragen und ihr könnt direkt loslegen." |
| 22:38 | „Damit habt ihr die Möglichkeit mit Relation Flow Arbeiten, die zuvor Stunden gebraucht haben und eine Haufenrecherche [Anm.: Haufen Recherche] innerhalb von wenigen Minuten umzusetzen." |

**Ableitbare Praktiken**
43. **Tools in einem Chat bündeln** – alle Alltagstools an einen Agenten anbinden, statt zwischen Anwendungen zu wechseln; Datenquellen im selben Kontext kombinieren.
44. **Nachfragen zulassen** – der Agent darf rückfragen („wie heißt das Google Sheet?"), statt zu raten; fehlende Parameter werden erfragt.
45. **Letzten Schritt als Entwurf, nicht als Versand** – Ausgabe als Outlook-Entwurf zum Korrekturlesen; der Mensch bleibt am Absenden-Knopf (Human in the Loop).
46. **Wiederkehrende Arbeit als Projekt bündeln** – Analysen/Chats in einem Projekt + Ordner im Firmenwissen ablegen, damit derselbe Ablauf wiederholbar ist.
47. **Wissen für Nachnutzer aufbereiten** – Ergebnisse so ablegen, dass nächste Woche oder ein Kollege den Kontext fertig vorbereitet vorfindet (Wissenstransfer statt Einmal-Chat).
48. **Nicht alles selbst bauen** – Agenten, Prompts und Skills aus der Community per Klick übernehmen, statt jedes Setup von Hand zu definieren.

---

## 8) IYzgxWs4sZ4 — „KI-Videos haben eine GRENZE überschritten: DAS kann Seedance 2.5! + Claude Code & Codex Updates"

**Marcel-Stelle: 14:52 – 19:57** (Übergabe 14:50: „Marcel, was hat es denn auf sich mit Bass [Anm.: Produktname in der ASR uneinheitlich „Bass/BS/Bas", gemeint ist die Open-Source-Gruppenchat-Plattform für Menschen + Agenten] und wie funktioniert das?")

| Zeit | Wörtliches Zitat |
|---|---|
| 14:53 | „Wenn wir uns einmal die Oberfläche anschauen vom Bass, stellen wir auch direkt fest, dass es sehr, sehr ähnlich zu Slack aufgebaut ist. Man hat hier im linken Bereich seine Channels, hier oben die Inbox mit einer Suchleiste, im Mainbereich dann eben den Chat an sich bzw. den Channel und rechts hat man dann die Möglichkeit Threads aufzumachen." |
| 15:20 | „Ich habe hier jetzt einfach mal ein ganz einfaches Beispiel anhand von der Muster API gemacht. Also, wir haben hier jetzt keine echten Daten drinne, um einfach einen Channel zu haben, wo ein Agent mir regelmäßig in dem Fall Eny [Anm.: Agentenname ASR-unsicher], mir die KPIs von Relation Flow sendet" |
| 15:34 | „und dementsprechend einfach nur mit einem Addzeichen [Anm.: @-Zeichen] getagt werden muss und dann einfach man sagt, gebe mir erneut die KPI und dies kann man natürlich dann auch automatisieren, dass das regelmäßig von alleine passiert." |
| 16:20 | „Cool ist es aber, dass du in Bass die Möglichkeit hast, deine eigenen Agenten zu erstellen für gewisse Aufgaben, diesen dann auch dementsprechend Instructions geben kannst und bis ins kleinste Detail voll konfigurieren kannst." |
| 16:40 | „Also wir sind hier nicht an ein bestimmtes Harness, wie z.B. wird hier das Bass Harness gebunden, sondern wir können auch Cloud Code [Anm.: Claude Code], Codex, OMYP [Anm.: Kürzel ASR-unsicher] oder sonstige installieren, da BS einfach auf dem ACP Protocol aufbaut und somit überall mit angebunden werden kann." |
| 16:52 | „Dementsprechend kann man aber auch bestimmte Agent Teams einfach zusammenführen, so dass Agenten miteinander kollaborieren in den Channels." |
| 17:00 | „Und zwar kriegt jeder Agent und jeder Nutzer, Mensch jetzt in dem Falle ein sogenanntes Cryptographic Key Pair, wo dementsprechend immer nachverfolgbar ist, welcher Agent hat was gemacht und von welchem Menschen wurde dieser Agent beauftragt." |
| 17:40 | „Und somit ist alles dank dem Nostar [Anm.: Nostr] Protokoll, was ja auch im Bidget [Anm.: ASR-unsicher] verwendet wird, ist jedes Event signiert. heißt, es ist nachverfolgbar und durch ein Log, welches searchable ist, durchsuchbar. Sprich, es ist alles dokumentiert, es ist alles nachverfolgbar" |
| 18:00 | „und wir haben auch die Möglichkeit, dadurch, dass Bass in einem eigenen Folder arbeitet, dass dementsprechend Buff [Anm.: ASR-Versprecher] niemals unsere lokalen eigenen Worktree und Branches angreift, sondern immer Kopien erstellt, in welchen die Agents dann arbeiten können." |
| 18:26 | „Die einzige Einschränkung, die hier beispielsweise ist, wenn wir jetzt noch mal in den Thread von Anly [Anm.: Agentenname, ASR-unsicher] reingehen, wir kriegen hier nur den Respons. Wir sehen hier leider nicht, was passiert im Terminal, was passiert im Background. Wird wahrscheinlich noch in einem der künftigen Updates folgen" |
| 18:50 | „BS ist eigentlich wie anfangs schon gesagt eine Kombination aus Slack, Herd [Anm.: Produktname, ASR-unsicher] mit dem Agent Management, Hermess [Anm.: Hermes] mit dem Harness und Open Claw [Anm.: OpenClaw], dass man einfach mehrere Agenten in einem kombinieren kann." |
| 19:00 | „Damit ihr keine Agenten selber von Hand erstellen müsst, haben wir bereits in Relation Flow sehr, sehr viele Agenten für euch out of the box zur Verfügung gestellt. Und seit gestern mit dem neuen Update habt ihr sogar die Möglichkeit, Agenten direkt aus der Community in eurer Relation Flow hineinzuziehen." |
| 19:32 | „Ähnlich wie bei Bass haben wir bei Relation Flow natürlich auch die Funktionalität in den Chats direkt mit Agenten zu interagieren. Hierfür müsst ihr einfach nur, sobald ihr in einem neuen Chat seid oder in einem bereits vorhandenen Chat mit Hilfe des Addzeichens den entsprechenden Agenten euch heraussuchen." |

*Randnotiz aus dem Block davor (Leonard, 12:30, kein Marcel-Zitat):* „weshalb es durchaus sinnvoll sein kann, jetzt darüber nachzudenken, noch mehr seine Aufgaben aufzuteilen und vor allem GBT 5.6 Luna beispielsweise für Subagents einzusetzen."

**Ableitbare Praktiken**
49. **Agenten per @-Tag im Team-Chat** – Agenten wie Kollegen ansprechen (Channel/Thread), nicht über separate Konsolen; Aufgaben bleiben im gemeinsamen Verlauf.
50. **Routinen automatisieren** – wiederkehrende Abfragen (z. B. KPIs) als automatisierten Agentenauftrag statt manueller Wiederholung.
51. **Harness-Freiheit** – Agenten an kein festes Harness binden; über ein offenes Protokoll (ACP) verschiedene CLIs/Modelle (Claude Code, Codex, weitere) anschließen können.
52. **Agenten-Teams statt Einzelagenten** – mehrere Agenten in denselben Channels zusammenführen, damit sie miteinander kollaborieren.
53. **Agenten klar instruieren und konfigurieren** – jedem Agenten explizite Instructions für seine Aufgabe geben, „bis ins kleinste Detail".
54. **Nachvollziehbarkeit erzwingen** – kryptografische Key Pairs/Signaturen pro Agent und Mensch: welcher Agent hat was getan, von welchem Menschen beauftragt; durchsuchbares Log.
55. **Worktree-Isolation** – Agenten arbeiten in Kopien/eigenem Ordner, niemals direkt auf lokalem Worktree und Branch.
56. **Kontroll-Lücke kennen** – Tool zeigt nur Response, nicht Terminal/Background: nicht blind vertrauen, Zwischenschritte anderweitig einsehbar machen.
57. **Agenten/Skills aus Community ziehen** – statt jeden Agenten von Hand definieren; fertige Definitionen mit einem Klick übernehmen.

---

## Top-Regeln aus meinem Bereich

**A. Trennen statt vermischen**
1. Planen und Implementieren sind **zwei Sessions** — nie dieselbe Session für beides.
2. Der **Planner läuft auf einem anderen Modell** als das, mit dem der Plan entstand: Fremdprüfung statt Selbstbestätigung.
3. Der Plan ist ein **Artefakt (GitHub-Issue)** mit Sub-Tasks und Akzeptanzkriterien — nicht ein Chatverlauf.
4. Pro Zielsystem/-aufgabe **eigene Sessions**, die sich untereinander über einen Skill informieren — nicht eine Session, die alles wissen muss.
5. Der **Mensch bleibt am letzten Schritt**: Entwurf statt Versand, Review statt Autopilot.

**B. Autonomie richtig aufsetzen**
6. Erst **Ist-Zustand messen** (Baseline), dann ändern, dann **selbst nachmessen lassen**, bis das Zielkriterium wirklich erreicht ist.
7. **Sparring-Prompts statt Dauerbetreuung**: 2–3 Prompts zum Einsteuern, dann tagelang autonom laufen lassen (realistisch 4 Tage für einen MCP).
8. **Loop bis das Issue abgearbeitet ist** — Planner kontrolliert, dokumentiert, schickt Anpassungen zurück; „fertig" ist erst, wenn die Arbeit verifiziert ist.
9. **Parallelisieren**: mehrere Planner-Worker-Paare gleichzeitig betreiben.
10. **Kontextfenster mitlesen** (Token vs. Fenster) und als Steuer-/Abbruchkriterium nutzen.
11. **Worktree-Isolation**: Agenten arbeiten in Kopien, nie direkt auf lokalem Branch/Worktree.
12. **Nachvollziehbarkeit**: signierte Aufträge/logs — wer hat welchen Agenten wofür beauftragt.

**C. Kontext ist die eigentliche Arbeit**
13. **Immer im Planmodus starten** — und die Fragerunde aushalten (Größenordnung ~200 Fragen); die Fragen, an die man selbst nicht gedacht hat, sind der Gewinn.
14. **Präferenzen einmal hinterlegen** (Arbeitsabläufe, Ziel-Output, Beispiele, CI-Farben/Tonalität) — die KI richtet damit ihr Setup selbst ein (**KI, um KI einzurichten**).
15. **Skill-Disziplin**: keine tausenden Skills/Plugins/MCPs für dieselbe Aufgabe; vor dem Installieren gemeinsam mit der KI prüfen, ob es das schon gibt.
16. **Wissen wiederverwendbar ablegen**: Ergebnis in Ordner/Projekt im Firmenwissen — damit die nächste Woche oder der Kollege den Kontext fertig vorfindet.

**D. Bauen und prüfen**
17. **Greenfield vs. Brownfield explizit einordnen**, bevor gebaut wird.
18. **Prototyp vor Integration**: Feature erst unabhängig von Codebase/Architektur bauen, Funktionalität nachweisen, dann integrieren; vorher die Test-/Integrationsprognose stellen.
19. **Modellwahl nach Aufgabenklasse**, nicht „bestes Modell": Code-Sauberkeit/Security/Scalability vs. UI/UX/Frontend.
20. **Vergleich mit fester Aufgabe**: dasselbe kleine Ziel über mehrere Modelle, dann in den Code springen (nicht bei der UI-Demo stehen bleiben) und Befunde konkret protokollieren.
21. **Brownfield-Großtest in Sandbox** für neue Modelle; Abarbeitung **nach Gitflow** mit PR pro Subissue.
22. **Tool-Bündelung**: alle Alltags-Tools in einem Chat/Agenten kombinieren, statt Kontextwechsel; Ursachenanalyse vor Optimierung.

**E. Was mich überrascht hat / offene Punkte**
- Video 1 (Planner-Worker, explizite Trennung) und Video 5 (dieselbe Session arbeitet das Epic sequentiell nach Gitflow ab) sind **zwei unterschiedliche Muster** von Marcel — je nachdem, ob das Modell sich in der Codebase selbst orientieren kann.
- Video 6 (z8OocncaeEs, „Claude Wasserzeichen") hat **keinen** Praxisblock.
- Offene Frage an Marcel wert: Wie wird der Planner-Worker-Austausch („Hurder"/„Herd" + Skill) konkret technisch verdrahtet — das war im Video nicht sichtbar.

---
*Erstellt aus öffentlichen Auto-Untertiteln; keine Veröffentlichung. Quellen-VTTs: `<video-id>.de-orig.vtt` im selben Ordner.*