# Embeddings auf Termux — Befundlage

> Erstellt 11.08.2026. Übergabe an den Strang „Wissensdatenbank aus den
> Chat-Archiven". Alles unter „Geprüft" ist am Code nachgesehen, alles unter
> „Offen" ausdrücklich nicht.

## Kurzfassung

Das Projekt hat den Kampf mit PyTorch auf ARM schon einmal geführt und durch
Verzicht beendet. Die Folge: **Auf dem Handy findet vermutlich keine
semantische Suche statt** — das Gedächtnis liefert dort die *neuesten*
Einträge, nicht die *passenden*. Für eine Wissensdatenbank über 1 GB
Chat-Archive ist das die zentrale offene Frage.

## Geprüft

| Fundstelle | Befund |
|---|---|
| `backend/requirements.txt` | Weder `sentence-transformers` noch `chromadb`. Nur `numpy` als Rechenteil. |
| `backend/app/db/chroma_client.py:1` | „Simple JSON-based memory store (drop-in replacement for ChromaDB **on ARM**)" — JSON-Datei plus numpy statt Vektordatenbank |
| `backend/app/services/memory_service.py:13–27` | `sentence_transformers` steht in einem `try/except`. Schlägt der Import fehl, läuft alles weiter, nur ohne Vektoren. |
| `memory_service.py:44–49` | Beim Speichern: kein Embedder → Eintrag **ohne Vektor** |
| `memory_service.py:79–81` | Beim Abrufen: kein Embedder → `get_all_memories(limit=top_k)`. **Das ist keine Suche, sondern die letzten N Einträge.** |

### Was daraus folgt

1. Die Architekturzeile „Embeddings werden lokal berechnet
   (sentence-transformers)" aus der `CLAUDE.md` beschreibt die **Absicht**,
   nicht notwendigerweise den Zustand auf dem Gerät.
2. Ein Gedächtnis, das immer die neuesten fünf Einträge liefert, wirkt von
   außen wie „es sammelt Müll an" — der Verdacht aus dem Hauptplan
   (`auf-meinem-handy-ich-zesty-bird.md`, Befund 1) bekommt hier eine zweite,
   unabhängige Ursache.
3. Der Fallback ist **still**. Es gibt keine Anzeige in der Oberfläche und
   keinen Eintrag im Health-Endpunkt, der verrät, ob Vektorsuche läuft. Nur
   eine Warnzeile im Log beim Serverstart.

## Offen — nicht geprüft, nicht annehmen

- **Fehlt `torch` auf Sebastians Handy tatsächlich?** Sehr wahrscheinlich, aber
  ungeprüft. Nachweis: Beim Serverstart im Termux-Log nach `Embedding model`
  suchen. Steht dort `NOT available`, ist es bestätigt.
- **Größe und Zusammensetzung der Archive.** Über 1 GB laut Sebastian. Wie viel
  davon Gesprächstext und wie viel Google-Takeout-Ballast (Bilder, Anhänge,
  Aktivitätsprotokolle) ist, ist unbekannt. Der Ordner
  `Chats von GPT, GEMINI, Claude/` ist per `deny`-Regel in
  `.claude/settings.json` für den Agenten gesperrt — **diese Sperre soll
  bleiben**. Der Importer liest die Dateien zur Laufzeit; der Agent nie.

## Drei Wege, keiner davon geprüft

| Weg | Idee | Spricht dafür | Spricht dagegen |
|---|---|---|---|
| **A — ONNX Runtime** | Sentence-Transformer-Modell nach ONNX exportieren, mit `onnxruntime` ausführen | Echte semantische Suche auf dem Gerät, kein PyTorch | Ob `onnxruntime` auf Termux baut, ist ungeprüft |
| **B — SQLite FTS5** | Volltextsuche statt Vektoren. `sqlite3` bringt Python mit, FTS5 ist eingebaut | Läuft garantiert überall, keine neue Abhängigkeit, sehr schnell auch bei 1 GB | Findet Wortformen, nicht Bedeutung. Deutsche Komposita brauchen Zusatzarbeit |
| **C — Embeddings auf dem PC** | Indizierung einmalig am PC, fertige Vektoren aufs Handy | Schwere Arbeit nur einmal, Handy rechnet nur Skalarprodukte (numpy ist da) | **Die Suchanfrage braucht auch ein Embedding.** Ohne lokalen Embedder muss dafür eine API ran — Daten verlassen das Gerät |

**Kombination, die vermutlich am weitesten trägt:** B als Grundlage (funktioniert
sofort und immer), A als Ausbaustufe, sobald geprüft ist, dass `onnxruntime`
auf Termux läuft. C scheitert allein am Anfrage-Embedding, ist aber als
Beschleuniger für A brauchbar: Der PC berechnet die Dokument-Vektoren, das
Handy nur noch den einen Vektor der Frage.

## Prüfschritte vor jeder Planung

1. `pip install onnxruntime` in Termux versuchen → entscheidet über Weg A
2. Im Termux-Log nachsehen, ob der Embedder heute lädt
3. Archivgröße und Dateitypen ermitteln (nur Sebastian, der Ordner ist gesperrt):
   ```
   du -sh . && find . -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn | head
   ```

## Was NICHT angetastet werden sollte

- Die `deny`-Regel für den Archivordner in `.claude/settings.json`
- Der `.gitignore`-Eintrag Zeile 113/114
- Der bestehende `SimpleMemoryStore` — er läuft auf ARM nachweislich. Eine
  Wissensdatenbank sollte **daneben** entstehen, nicht an seiner Stelle:
  Gedächtnis (wenige, kuratierte Fakten) und Archiv (Hunderttausende
  Nachrichten) haben unterschiedliche Zugriffsmuster.
