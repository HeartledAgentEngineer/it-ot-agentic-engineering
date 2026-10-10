# Geschichtsprüfung für eine Veröffentlichung — Arbeitspaket 1

Auftrag: `.hermes/plans/2026-10-10_portfolio-personal-ai-agent.md`, harte Vorbedingung
(Prüfung der **gesamten Versionsgeschichte**, nicht nur des aktuellen Standes).
Durchgeführt am 10.10.2026 von Hermes (Agentic-Engineering-Sitzung).

**Grundsatz dieser Prüfung:** Es werden **keine Werte ausgegeben** — weder im Bericht noch im
Terminal. Verglichen wird über **Längen** und **Prüfsummen** (SHA-256, erste 10 Zeichen).

## Verfahren

1. `git log --all -S <muster>` (Pickaxe) auf den Projektpfad — findet Commits, in denen ein Muster
   hinzukam oder verschwand, über **alle** Zweige.
2. Für jeden Treffer: die betroffene Datei im **jeweiligen Commit** auslesen (`git show <commit>:<pfad>`).
3. Bei Schlüsselverdacht: Länge und Prüfsumme bilden und gegen die echten Schlüssel in der
   (nicht versionierten) `.env` abgleichen.

Umfang: **761 Commits** berühren das Projekt, davon 958 Commits im gesamten Arbeitsbaum.

## Befunde

| Prüfpunkt | Befund | Bewertung |
|---|---|---|
| Zugangsschlüssel in `.env.example` | `OPENROUTER_API_KEY` in **allen 7 Fassungen 22 Zeichen** lang = Platzhalter; `MISTRAL_API_KEY` und `PCLOUD_TOKEN` leer | **sauber** |
| Echter `PCLOUD_TOKEN` (39 Zeichen) | kommt in **keiner** committeten Fassung vor; Prüfsumme weicht von allen Vorlagenwerten ab | **sauber** |
| `sk-or-v1-` (7 Commits) | ausschließlich Platzhalter in der Vorlage, Dokumentation und **Tests, die prüfen, dass kein Schlüssel durchkommt** (`test_selbsttest.py`, `test_sprachaufnahme.js`) | **sauber** |
| `sk-proj-` (OpenAI) | 0 Commits | sauber |
| Handy-Seriennummer | **3 Commits**: Vorgabewert in `backend/scripts/whatsapp_exporte_holen.sh` (im aktuellen Stand!) sowie zwei Änderungsprotokolle | **zu beheben** |
| Private Pfade `C:/Users/sebas` | **11 Commits** | **zu beheben** |
| Verweise auf das gesperrte Archiv (`Chats von GPT, GEMINI, Claude/`) | **13 Commits** (überwiegend Änderungsprotokolle) | **vor Veröffentlichung zu ersetzen** |
| Adresse, Telefonnummer | **0 Commits** | sauber |
| Klarname `Wenck` | 4 Commits | unkritisch (Sebastians eigener Name gehört in ein Portfolio) — Familiennamen sind noch zu prüfen |
| Bilder/Bildinhalte in der Geschichte | **noch nicht geprüft** | offen |

## Bewertung

Die gefährlichste Klasse — echte Zugangsschlüssel — ist **frei**. Der Weg dahin war bewusst:
`.gitignore` sperrt `.env` **und** `.env.bak*`, und die Tests prüfen aktiv, dass kein Schlüssel
im Quelltext oder im Frontend landet.

Die verbleibenden Befunde sind **keine Geheimnisse, sondern Privatsphäre**: Gerätekennung,
Windows-Pfade und der Ordnername des gesperrten Archivs. Sie stehen fast ausschließlich in
**Änderungsprotokollen und Hilfsskripten**, nicht im Anwendungscode.

## Was daraus folgt

1. **Arbeitspaket 2 (Beispiel-Konfiguration)** übernimmt: Seriennummer und Pfade wandern aus dem
   Code in eine Vorlage; das Skript liest sie aus der Umgebung.
2. Für eine Veröffentlichung ist zu entscheiden, ob die **Geschichte** mitveröffentlicht wird.
   Steht nur der aktuelle Stand öffentlich (frisches Repository), sind Seriennummer und Pfade aus
   den Protokollen **nicht** sichtbar — die Protokolle selbst bleiben aber Teil der Substanz und
   sollten dabei sprachlich bereinigt werden („das Handy" statt der Kennung).
3. **Arbeitspaket 1, zweiter Teil (offen):** ein Werkzeug im Repo, das künftig bei jedem Lauf
   anschlägt — geprüft werden der aktuelle Stand **und** die Geschichte, Rückgabewert ungleich 0
   bei Befund, damit ein Git-Haken den Commit abbrechen kann.
4. **Offen:** Prüfung auf Bilder/Bildinhalte in der Geschichte (vierter Prüfpunkt der
   Vorbedingung).

## Nachweis

- Umfang und Trefferzahlen: `git log --all -S` (siehe Verfahren), Rohausgabe im Sitzungsprotokoll.
- Schlüsselabgleich: Längen und Prüfsummen gegen `backend/.env` (nicht versioniert, nur lokal
  gelesen, Kopien nach dem Lauf entfernt).
- Keine Datei im Projekt wurde durch diese Prüfung verändert; es wurde ausschließlich gelesen.
