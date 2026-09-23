# Marcel-Praxisblöcke — TEIL 4 (Playlist-Positionen 25–32)

**Playlist:** Everlast AI — „KI-NEWS“ (https://www.youtube.com/playlist?list=PLk7pG7wpqjW3pOq7tGV_t21wkJjfL3zmC, 137 Videos, neueste zuerst)
**Bereich:** Positionen 25–32 → Upload-Daten **2026-04-05 bis 2026-02-22** (Weekly-Kadenz, geprüft)
**Quellen:** ausschließlich die öffentlich verfügbaren deutschen Auto-Untertitel (yt-dlp, `--write-auto-subs --sub-langs 'de.*'`); nichts veröffentlicht, nur lokale Auswertung.
**Stand:** 2026-09-23. Zeitangaben = Position im jeweiligen Video.

---

## Kernergebnis (wichtig für die Aggregation)

> **In den Positionen 25–32 kommt „Marcel“ NICHT vor.** Es gibt in meinem Bereich **keinen** Marcel-Praxisblock — kein Name, kein Intro-Muster („Ich habe mal den Marcel …“, „einen meiner AI Developer, den Marcel“), kein Sprecherwechsel zu einem Entwickler aus dem Team. Die Videos liegen zeitlich **vor** der Etablierung dieses Formats.

**Erster Marcel-Nachweis in der Playlist (im von mir geprüften Fenster):** Position **21**, `k_-AsnFqbqQ`, 2026-05-03, `[10:34]`:
> „weiter in unser Office an einen meiner AI Developer, den Marcel. / So, dann zeige ich euch mal, wie wir bei Everlast im Development Software …“

Zum Gegencheck der Referenz-Zitate aus dem Auftrag: Position 7 (`YGfd1LiTQiY`, 2026-08-09, 4 Nennungen, z. B. `[18:35]` „damit gebe ich weiter an einen unserer Developer, den Marcel“) und Position 8 (`IYzgxWs4sZ4`, 2026-08-02, 2 Nennungen, `[14:50]` „Marcel, was hat es denn auf sich mit Bass“) — bestätigt.

---

## Prüfnachweis (reproduzierbar)

| Prüfung | Befehl / Methode | Ergebnis |
|---|---|---|
| Roh-Untertitel meiner 8 Videos | `grep -c -i "marcel" <id>.de-orig.vtt` | **0 in allen 8** |
| Namensvarianten | `grep -c -i -E "marcel\|marzel\|marsel"` auf deduplizierten Transkripten | 0 |
| Intro-Muster | `grep -c "Developer, den"` + `"entwickler, den"` + `"einen meiner"` | 0 in allen 8 |
| Steuerbegriff „gebeten“ | Suchlauf über alle 8 Transkripte | 0 |
| Doppelte Tracks | `diff -q <id>.de.vtt <id>.de-orig.vtt` | identisch (kein versteckter Track) |
| Gegentest ASR-Namen | Im selben Material korrekt verschriftet: „Leonard Schmedding“, „Kim Isenberg“, „Dr. Mark Müller“, „Philip Baumann“, „Tech-Korrespondentin Lea“ | Namen werden sonst erkannt → das Fehlen ist real, kein ASR-Artefakt |
| Kontextfenster | Positionen 18–24 (2026-04-12 … 2026-05-24) auf dasselbe Muster geprüft | nur Position 21 positiv (4 Muster-Treffer) |
| Vollständigkeit der Transkripte | letzter Zeitstempel vs. Videodauer (z. B. 26vS1Os8vek: 29:33 vs. 29:34) | deckt sich, nichts abgeschnitten |

Konvertierung: `marcel_scan4.py` (rollierende Auto-Captions → Wort-Dedupe → `[mm:ss]`-Transkripte `<id>.transcript4.txt`, im selben Ordner).

---

## Die 8 Videos im Einzelnen

### Pos. 25 — `26vS1Os8vek` · 2026-04-05 · 29:34
**„Krass: Claude Code KOSTENLOS mit Gemma-4! Neuer ‚Kairos‘ Agent, Opus 4.7, Seedance & mehr KI-News“**
**Marcel: NICHT vorhanden.** (Namensauftritte: Leonard Schmedding; Gastinterview mit Philip Baumann/Telli über Tech-Korrespondentin „Lea“, `[22:20]`.)
Agenten-Praxis im Video (Sprecher = Host, **nicht** Marcel):
* `[03:23]` „wenn du nämlich Memory in deinem Cloud Code [Claude Code] eingibst, dann kannst du bereits die Autodream [AutoDream]-Funktion aktivieren und diese hilft ja Cloud Code dabei über Subagents in der Nachtverarbeitung sein Gedächtnis, seine Erinnerungen zu konsolidieren und aufzuräumen …“
* `[04:00]` „… kannst du über Slash Ultraplan oder das Wort Ultraplan eine vollständige Cloud Code Session in der Cloud, also im Web starten und diese läuft dann auf den leistungsstärksten Modellen wie Opus und bietet 30 Minuten Zeit, um gemeinsam über den Browser einen Plan zu entwickeln …“
* `[07:00]` „für Simplify beispielsweise drei parallele Subagents gespawnt. Einer welcher einen Review Agent, einen QA Agent, also Qualitätssicherung und einen Effizienzagent.“
* `[07:15]` „weil wir selbst einige Schlüssel [Skills] rausziehen können und zwar in unseren Skills beispielsweise selbst mit einem Team aus drei Subagenten zu arbeiten, wenn wir komplexe Codebases simplifizieren wollen … das Prinzip ist ja letztlich auf jede andere Aufgabe übertragbar“
* `[13:33]` „Und die Erfahrung haben wir tatsächlich auch in unserem eigenen Entwicklerteam. Also wir arbeiten primär mit Cloud Code [Claude Code], aber für einzelne Aufgaben wie QA beispielsweise nutzen wir dann wiederum Codex und so gibt’s eben einige Use Casases, bei denen Cloud Code besser ist bei anderen Codex …“

*Ableitbar:* Plan-Modus vor Ausführung; Subagenten-Trio Review/QA/Effizienz; Modellaufteilung nach Aufgabentyp (Claude Code primär, Codex für QA); Speicher nachts durch Subagenten konsolidieren.

### Pos. 26 — `mKDL4rALSqw` · 2026-03-29 · 39:31
**„Claude ‚Mythos‘ geleakt, OpenAIs MEGA-Plan, Optimus-3, Terafab, TUM-Interview & weitere KI-News“**
**Marcel: NICHT vorhanden.**
* `[29:35]` „Auch das ist etwas, was ich meine mit dieser zentralen Entwicklung, dass Agents jetzt über die Kommandozeile laufen. Wir müssen keine API Documentations mehr selbst lesen. Gemini stellt uns dafür einen Skill zur Verfügung bzw. Gemini API Agent Skills. **Wir haben einen Skill gebaut**, der Coding Agents dabei hilft mit der Gemini API zu arbeiten, und dieser Skillstandard, der wird einfach gerade überall ausgerollt …“
* `[32:00]` „… erstellst beispielsweise einen Subagent, der jetzt erstmal als zentrale Verwaltung Telefonate klassifizieren würde, dann weiterleiten würde an dedizierte andere Subagenten, die jetzt z. B. Angebote formulieren können, Termine machen können, whatsoever. Also das Prinzip ist klar.“
* `[32:20]` „… die Skills sind nach wie vor relevant, aber nicht mehr vor dem Hintergrund, wie vielleicht noch vor dem Jahr“ (UI-Bastelei vs. agentische Ausführung).

*Ableitbar:* Für jede wiederkehrende Fremd-API einen eigenen Skill bauen statt Doku im Kontext zu halten; Router-Agent (klassifizieren) → spezialisierte Subagenten.

### Pos. 27 — `U07CLU73PEc` · 2026-03-22 · 45:37
**„KI-Agenten: DAS übersehen gerade ALLE! Claude Updates, Google Stitch & LIVE von der NVIDIA GTC“**
**Marcel: NICHT vorhanden** — der Praxis-Test wird vom Host selbst live gemacht:
* `[19:57]` „… dabei an GBT [GPT] 5.4 Mini Subagenten delegieren.“
* `[20:04]` „Bevor ich dir aber gleich die Theorie dahinter erkläre und warum das für dich so wichtig ist, lass uns zunächst anschauen, wie du das in der Praxis nutzen kannst. **Dafür lasse ich Codex und Opus 4.6 gegeneinander antreten** und zwar mit der konkreten Aufgabe: Starte zuerst einen Subagent mit dem GBT [GPT] 5.4 Minimodell.“
* `[20:24]` „Dieser Research Subagent soll kurz recherchieren und zusammenfassen, wie Subagents typischerweise genutzt werden, welche visuellen Metaphern sich dafür eignen … Lass den Research Agent die Ergebnisse zusammenfassen und anschließend erstelle eine Motion Graphic.“
* `[20:48]` „… sind also Subagents in Aktion. Ein Subagent wurde gespawnt und dieser hat dann eben die Aufgabe durchgeführt bzw. führt sie noch durch, eine Recherche zu erstellen. Und Codex ist auch bereits fertig.“
* `[21:13]` „Hier ging es mir jetzt vor allem auch nicht um das Design, sondern um die korrekte Recherche, wie Subagents denn konkret funktionieren.“
* `[21:19]` „… für den Subagent hat er jetzt wirklich auch nur die Hik [Haiku]-Modelle verwendet. Also in diesem Subagent-Praxis-Test Clud [Claude] für mich klar der Gewinner …“

*Ableitbar:* Identische Aufgabe an zwei Systeme geben, wenn eine Tool-Aussage belegt sein soll; Subagenten mit kleinen/günstigen Modellen fahren; Recherche-Subagent → danach Ausführung; Bewertung an genau einer vorab definierten Kernanforderung.

### Pos. 28 — `tu5aAXDXj6s` · 2026-03-15 · 32:23
**„Massive Claude Code & ChatGPT Updates! Neue Skills, Gemini Embedding, RAG-Interview & mehr KI-News“**
**Marcel: NICHT vorhanden** (Gastinterview Octonomy/RAG, `[19:40]` ff. — Gast, nicht Marcel).
* `[26:40]` „… denn die sind ja alle nicht optimiert auf KI Agenten. Die sind schwer zu verstehen für KI Agenten und letztlich werden KI-Agenten mehr am Computer arbeiten als wir, ja, mit all diesen Dateien.“
* `[27:00]` „… denn diese stellen jetzt einen Skill bereit, welcher ihre Paper direkt als Markdown Datei für KI Agenten bereitstellt …“
* `[27:20]` „Das ist aber ineffizient, weil es viel Kontext verbraucht, viel Token verbraucht. Viel sinnvoller wäre es doch dem Agenten direkt eine Markdown Datei mitzugeben. Und genau das macht der archef.org [arxiv.org] Skill. Den kannst du dir einfach … in dein Cloud Code reinziehen und alle Paper direkt über Markdown abrufen.“
* `[27:40]` „… wie man im Unternehmen letztendlich seine Dokumente strukturieren und bereitstellen muss, sodass jeder auf alle Dokumente … über die zentrale KI-Wissensdatenbank“ zugreift.

*Ableitbar:* Dokumente agentengerecht als Markdown bereitstellen (statt PDF/Word hochladen) → Token sparen; Firmenwissen zentral für Agenten erschließen.

### Pos. 29 — `k6QZRaqcXuE` · 2026-03-11 · 22:56
**„Googles KI-OFFENSIVE in Deutschland! Live vom AI Center Berlin“**
**Marcel: NICHT vorhanden.** Reine Vor-Ort-Reportage/Interviews (Google AI Center Berlin), kein Agenten-Praxisblock. Einziger übertragbarer Satz:
* `[03:10]` „viele Veranstaltungen zum Thema künstliche Intelligenz hier bei uns im Schnitt 200 pro Jahr … Es wird AI Hackathons geben, also wo wirklich Developer zusammenkommen, um auch gemeinsam zu entwickeln“.

*Ableitbar:* nichts Agentisches — als „ohne Marcel / ohne Praxisblock“ führen.

### Pos. 30 — `3jGeOut5HWk` · 2026-03-08 · 29:41
**„GPT-5.4: Es ist VORBEI für OpenAI! Claude Code, Google AI Center Eröffnung & weitere KI-News“**
**Marcel: NICHT vorhanden** — aber mit Team-Bezug:
* `[06:18]` „Dann startet der gesamte Kontext ja wieder komplett neu, das Kontextfenster.“
* `[06:33]` „… lass uns das doch parallel jetzt auch mal in der einfachen Webdesign Aufgabe vergleichen … die gleiche Aufgabe gebe ich jetzt auch mal ganz einfach wirklich über den Webchat hier mit Opus 4.6 und aktiviere das erweitete [erweiterte] Denken.“
* `[06:45]` „Und was mir auch direkt auffällt bei Opus, das ist nach wie vor einfach die große Stärke Read [Red?] Front-End Design Skill. Ja, Enhropic [Anthropic] nutzt einfach die Skills dafür. Das ist kein Skill von mir, sondern ein Entropic [Anthropic]-eigener Frontend Design Skill. Wenn wir jetzt wieder zurück zu ChatGBT [ChatGPT] gehen, ChatGBT macht das nicht. Das heißt, die Skills sind nach wie vor nicht Teil von ChatGBT, vor allem nicht in der Webapp.“
* `[07:05]` „… Skills wird [sind] mittlerweile Teil der Codex App und wenn du über das CLI arbeitest, so wie ich es ja ohnehin jedem empfehle, dann hast du damit …“
* `[08:57]` „Das würde ich jetzt auch auf Basis des **Feedbacks aus unserem eigenen Entwicklerteam bei Everlast AI**. Wir sind ja mittlerweile auch über 30 Leute mit im Team, ja, die den ganzen Tag mit diesen Modellen arbeiten und diese testen.“
* `[09:20]` „nutzen aktuell hauptsächlich nach wie vor Cloud Code [Claude Code] und GBT [GPT] 5.4 gerade im neuen Extra High Mode … in realen Coding Aufgaben ist Opus 4.6 aktuell unsere Einschätzung nach immer noch führend.“

*Ableitbar:* Tool-Urteile aus Team-Praxis (30+ Personen, täglich) statt aus Benchmarks; CLI als Standardweg (Skills/Kontextkontrolle); A/B-Vergleich derselben Aufgabe über zwei Oberflächen.

### Pos. 31 — `cSKS-5gbW8E` · 2026-03-01 · 35:38
**„Nutze Claude Code NICHT bis du DAS gesehen hast! ETH-Forscher enthüllt, Neue Funktionen & mehr News“**
**Marcel: NICHT namentlich.** Einziger Rollenbezug (`[04:34]`, wörtlich, ASR unsauber):
> „… wie beispielsweise das Superpers [Superpowers] Plugin. Also das ist so eines der bevorzugen [bevorzugten] Plugins mit dem KI Entwickler aus unserem Team beispielsweise hauptsächlich arbeiten.“
Agenten-Praxis (Interview mit Forscher Dr. Mark Müller zu AGENTS.md/CLAUDE.md, `[12:30]`–`[15:25]`):
* `[12:55]` „Und für Code Agents ist ganz besonders wichtig, weil im Gegensatz zu menschlichen Entwicklern, die keine Erfahrung sammeln für sich. Das heißt, jeder Task, den sie in einer Codebase im Repository erledigen, ist wie das erste Mal, dass sie mit der Codebase arbeiten. Das heißt, ein gutes Onboarding Dokument ist unheimlich wichtig, dass sie effektiv sind.“
* `[13:20]` „… Und im Schnitt waren die Ergebnisse ja auch 3 % schlechter und die ganze Sache hat sogar 20 % mehr gekostet.“ (Studie: KI-Coding-Tools mit AI-generierten Anleitungsdateien)
* `[14:10]` „Aber wir haben gesehen, die folgen diesen Anweisungen zu gut. Normalerweise stehen in Anweisungsdatei[en] unnötige Schritte drin, die für ein spezielles Problem irrelevant sind und die sorgen dann genau dafür, dass wir so ineffizient werden.“
* `[15:00]` „Also wenn Mensch sie schreibt, dann werden die Ergebnisse im Schnitt 4 % besser. Wenn die KI sie selbst generiert, werden die Ergebnisse auch schlechter.“
* `[15:25]` „Für mich persönlich ist die Schlussfolgerung: Anleitungsdatei gerne, aber auf jeden Fall selber geschrieben, kurz gehalten und rigoros kuratieren, alles was useless ist, alles was duplicate ist, muss da raus.“
* `[17:40]` „… dass wir gerade eben das Wettrüsten rund um diesen Entic [Agentic] Layer sehen. Wir hatten letzte Woche bereits über Agents, Subagents, Agent Teams gesprochen, dass diese jetzt gerade ihre finale Marktreife erreichen.“
* `[20:40]` „… das gebe ich jetzt mal Haiku 4.5 und parallel Mercury 2 … es geht um die Geschwindigkeit, ne?“

*Ableitbar:* Regeldateien selbst schreiben, kurz halten, kuratieren (messbarer Effekt); Kosten der Kontextdateien mitdenken; Plugins/Skills aus dem offiziellen Marktplatz ziehen; Geschwindigkeitsmodelle parallel testen.

### Pos. 32 — `cEsYCdoHEYA` · 2026-02-22 · 42:32
**„Das ENDE für OpenClaw! Claude 4.6 Sonnet, Gemini 3.1, Lyria & Silicon Valley Insider im Gespräch“**
**Marcel: NICHT vorhanden** (Gastinterview Browser-Use/YC-Startup, `[16:40]` ff.).
* `[05:00]` „bei Sub Agents hast du sozusagen ein Lieder [Leader] … also einen Agenten, der die anderen koordiniert und die anderen Agenten, die arbeiten alle unabhängig voneinander … quasi hierarchisch zu dem Lieder [Leader]. Das sind Subagents … Und bei Grok ist das tatsächlich anders, denn hier haben wir es mit einem Agententeam zu tun. Die Agenten Teams, die gibt es ja bei Clot [Claude] beispielsweise aktuell nur, wenn du CL [Claude Code] über das CLI, also über das Terminal verwendest. Und der Unterschied ist eben hier … die Agenten, die arbeiten eben auch untereinander. … dann würde der Front-End Agent auch mit dem Backend Agent kommunizieren. Der Backend Agent mit dem Testing Agent …“
* `[08:03]` „Zunächst ein Kontextfenster von einer Million Token. Wichtig aber auch nur über API … wenn du jetzt ganz normal über den Chat reingehst, über die normale App, dann hast du nicht die eine Million Token …“ · `[08:20]` „Du hast jetzt auch die Kontext Compion [Compaction], also wenn der Kontext dann irgendwann aufgebraucht ist, dann wird der kompaktiert und für die weitere Anfrage mitgegeben, was tendenziell einfach zu längeren besseren Chats führt.“
* `[16:40]` (Gast) „häufig möchtest du Dinge automatisieren, die du sehr sehr häufig laufen lassen möchtest … da haben wir sehr coole Features gebaut, wie du das sozusagen einmal aufnehmen kannst, dann versteht das die KI und dann kann dir das 1000 mal [1us mal] genau gleich wiederholen und das ist sehr sehr schnell, sehr billig und sehr verlässlich.“
* `[40:20]` „Bei unserer derzeitigen Entwicklung glauben wir, dass wir nur noch wenige Jahre von frühen Versionen echter Superintelligenz entfernt sind.“ (Zitat von Sam Altman, zitiert vom Host — kein Agenten-/Praxisbezug).

*Ableitbar:* Architekturwahl bewusst treffen (Hierarchie-Subagenten vs. untereinander kommunizierende Agententeams, letzteres nur im CLI); Kontextgrenzen kennen (API vs. App); wiederkehrende Abläufe einmal aufnehmen → deterministisch wiederholen.

---

## Grenzen & Unsicherheiten

* Es wurden nur die öffentlichen deutschen Auto-Untertitel ausgewertet; Marcel könnte akustisch vorkommen, ohne dass sein Name fällt — dafür gibt es in meinem Bereich aber **keinen** Hinweis: kein Intro-Muster, kein Sprecherwechsel, kein zweiter „Wir im Development“-Block.
* ASR-Fehler sind in Zitaten in `[ ]` korrigiert (Clot/Cloud → Claude, Enhropic → Anthropic, Hik → Haiku, GBT → GPT, Lieder → Leader). Wortlaut sonst unverändert aus den Untertiteln.
* „Erster Marcel-Nachweis Position 21“ gilt für den von mir geprüften Bereich (Positionen 18–32). Für Positionen 1–17 liegen mir nur die Referenzdateien (Pos. 7, 8, 9) vor — dort ist Marcel belegt.

---

## Top-Regeln aus meinem Bereich

> **Vorbehalt:** Diese Regeln sind aus den Videos 25–32 abgeleitet, aber **nicht** Marcel-Zitate — sie stammen von den Hosts (Leonard Schmedding/Leo) bzw. aus Gast-Interviews. Quelle steht jeweils dabei.

1. **Modell nach Aufgabentyp aufteilen** — Standard: Claude Code; für QA/Review gezielt Codex. *(Pos. 25, 13:33)*
2. **Erst planen, dann bauen** — Plan-Modus/„Ultraplan“-Session (Web, 30 Min Planung auf dem stärksten Modell) vor der Ausführung. *(Pos. 25, 04:00)*
3. **Subagenten-Trio für Code-Hygiene** — Review-, QA- und Effizienz-Agent parallel über die Codebasis. *(Pos. 25, 07:00; 07:15)*
4. **Subagenten immer mit günstigem/schnellem Modell** (GPT-5.4 Mini, Haiku) — die teure Leistung bleibt beim Orchestrator. *(Pos. 27, 19:57 + 21:19; Pos. 31, 20:40)*
5. **Recherche-Subagent vor Ausführungs-Schritt** — recherchieren & zusammenfassen lassen, dann erst Artefakt bauen. *(Pos. 27, 20:24)*
6. **Jede Tool-Empfehlung durch A/B belegen** — identische Aufgabe an zwei Systeme/Modelle, gleiche Kernanforderung. *(Pos. 27, 20:04; Pos. 30, 06:33)*
7. **Regeldateien selbst schreiben, kurz halten, rigoros kuratieren** — KI-generierte AGENTS.md/CLAUDE.md: Messwerte 3 % schlechter und 20 % teurer; von Menschen geschrieben 4 % besser. *(Pos. 31, 12:55–15:25)*
8. **Dokumente agentengerecht als Markdown bereitstellen** statt PDF/Word — spart Tokens und Kontext. *(Pos. 28, 26:40–27:40)*
9. **Für jede wiederkehrende Fremd-API einen eigenen Skill bauen**, statt Doku im Kontext zu halten (Beispiel: Gemini-API-Skill). *(Pos. 26, 29:35)*
10. **Router-Agent + spezialisierte Subagenten** — ein Subagent klassifiziert, die nächsten übernehmen die konkreten Tasks. *(Pos. 26, 32:00)*
11. **Terminal/CLI statt Web-App**, wenn Skills, Kontextkontrolle und Agententeams gebraucht werden. *(Pos. 30, 07:05; Pos. 32, 05:40)*
12. **Wiederkehrende Abläufe einmal aufnehmen, dann deterministisch wiederholen** — schnell, billig, verlässlich. *(Pos. 32, 16:40)*
13. **Tool-Urteil aus eigener Team-Praxis** (30+ Personen, täglich) statt aus Benchmarks. *(Pos. 30, 08:57)*
14. **Kontextfenster als knappe Ressource behandeln**: Abbrüche starten den Kontext neu *(Pos. 30, 06:18)*, Markdown statt PDF *(Pos. 28, 27:20)*, Compaction einplanen *(Pos. 32, 08:20)*.
15. **Speicher/Erinnerungen nachts durch Subagenten konsolidieren** (AutoDream) statt im laufenden Kontext aufzuräumen. *(Pos. 25, 03:23)*