# Brainstorming / Vorlage: Foto-Kontext für den persönlichen Agenten

> **Erstellt:** 13.08.2026 · **Projekt:** `personal_ai_agent` · **Zweck:** Tech-Anstoß und Übergabe an Claude als Gesprächsgrundlage für die nächste Sitzung.

---

## 🎯 Ziel

Der persönliche Agent soll **deinen Lebenskontext kennen**: wer die Personen in deinem Leben sind, wo du warst, welche Erlebnisse du hattest — damit er personalisiert und im Kontext antworten kann.

Der **Einstiegspunkt ist das Foto im Chat**: Du schickst ein Bild (oder machst eins mit der Handy-Kamera), der Agent sieht es, beschreibt es, **errät Personen** (wenn er sie schon kennt) oder **fragt einmal gezielt** („Wer ist das?"), du bestätigst oder antwortest — und **dieses Wissen wird dauerhaft in der Wissensdatenbank gespeichert**.

Langfristig soll der Agent dadurch dich so gut kennen, dass er selbst Verknüpfungen herstellt („Sieht aus wie ein Urlaubsbild, mediterran, vielleicht Pisa. Dein Bruder Julian?") und dich später direkt aus der Cloud beliefern kann („Zeig mir mal das Foto von mir mit meinem kleinen Bruder bei den Sonnenfinsternisbrillen").

---

## 🚫 Bewusst NICHT in diesem Umfang

Klare Nicht-Ziele — **bewusste Entscheidungen**, keine Vergesslichkeit:

- **Kein Bulk-Import** der ganzen vielen Jahre an alten Fotos. Die Datenbank soll nicht die komplette Bildhistorie aufnehmen — das wäre unverhältnismäßig und unnötig.
- **Kein Foto-Speicher in der DB**: Fotos liegen in deiner Galerie bzw. später in der pCloud, *nicht* in der Wissensdatenbank.
- **Keine automatische Gesichtserkennung als Suchfunktion** — Personen benennst du im Dialog.
- **Kein Live-Kamera-Modus wie Gemini Live** — das ist die Fernvision, später, nicht in diesem ersten Schritt.
- **Keine klassische Foto-Verwaltung** (Alben sortieren, Metadaten-Massenanalyse).

---

## ✅ Getroffene Entscheidungen (aus dem Grill-Gespräch, Stand 13.08.2026)

| # | Entscheidung | Begründung |
|---|---|---|
| 1 | **Vision-Kanal: Cloud-Vision über OpenRouter, nur ZDR-gekennzeichnete Modelle** | Der Datenschutz-Riegel existiert bereits in der Modellauswahl des Frontends. Phone-First bleibt intakt. Bilddaten verlassen das Gerät nur über Modelle mit Zero Data Retention (ZDR). |
| 2 | **Speicherformat: Beschreibung + Bild-Hash, kein Bild selbst** | Ermöglicht Wiedererkennung („Das kenne ich schon von 2019, Julian!") ohne Bildspeicher. Kein Rückfinden der Bilddatei aus der DB nötig. |
| 3 | **Eingabe: Neuer 📷-Button im Chat** | Phone-First, klar erkennbar, kein Overload am bestehenden Mikrofon-Button. Die Kamera-API (getUserMedia) ist im Frontend bereits eingebunden. |
| 4 | **Agenten-Verhalten beim Foto: erst beschreiben, dann bei bekannten Personen erraten und bestätigen lassen (ja/nein), bei Unbekannten einmal gezielt fragen** | Genau der gewünschte Dialog. Nutzt bereits gespeicherte Beschreibungen vom ersten Mal an. |

> **Hinweis zum Datenschutz (ZDR):** Für dieses Feature gilt verschärft — *keine* Bilder und *keine* Personendaten an Anbieter ohne Zero Data Retention. Im Zweifel lieber ein schwächeres, aber datenschutzsicheres Modell.

---

## 🧠 Was der Slice später können muss (Ausblick, nicht Teil des ersten Durchstichs)

Diese Punkte wurden im Gespräch genannt und sind als **Erweiterungen** notiert — **nicht** Teil des ersten Slices:

- **pCloud-Anbindung:** Agent kann gespeicherte Fotos aus der pCloud anzeigen („Zeig mir mal von damals das Foto mit meinem kleinen Bruder bei den Sonnenfinsternisbrillen"). Dafür braucht es API, Authentifizierung und Dateisuche — eigener Slice.
- **Web-Suche zur Orts-/Kontextbestimmung:** Agent darf selbst recherchieren, was im Hintergrund war und wo das sein könnte (z. B. Sehenswürdigkeit). Nutzt den bestehenden Websuche-Schalter/die bestehende Websuche.
- **Fotobücher der Mutter:** Werden *nach und nach im Gespräch* Seite für Seite erklärt — kein Bulk-Scan. Digitalisierung analoger Bücher (abfotografieren/einscannen) ist separater Aufwand außerhalb des Agenten.
- **Live-Kamera wie Gemini Live** als Fernvision. Der Agent sieht das live-Bild und kommentiert in Echtzeit („Dieses Bild erinnert mich an Pisa").

---

## 🏗️ Ablage-Logik

- Die **Beschreibungen** (Person, Ort, Geschichte, Verknüpfung zu Bild-Hash) landen in der **Wissensdatenbank** (SQLite + `mistral-embed`, dem Projekt des anderen Strangs) — **nicht** im kleinen Gedächtnis (`SimpleMemoryStore`).
- Das **kleine Gedächtnis** bleibt für kuratierte, wenige Fakten (persönliche Eckdaten).
- Die **Wissensdatenbank** nimmt die umfangreichen, durchsuchbaren Foto-Beschreibungen und Lebenskontext-Einträge auf.

---

## ⚠️ Bewusst offen / zu klären

- **pCloud-API**: exakter Endpunkt, Auth-Modell (Token vs. OAuth), Ordnerstruktur — erst im pCloud-Slice.
- **Bild-Hash**: welcher Algorithmus (perzeptueller Hash `pHash` ist robust gegen leichte Änderungen; kryptografischer `SHA-256` ist exakt, aber empfindlich gegen Skalierung/Filter). Empfehlung: `pHash` für Wiedererkennung, ggf. zusätzlich SHA-256 zur Identifikation des Originalbilds.
- **Wiederverwendung des bestehenden Datenschutz-Riegels**: Die Modellauswahl-Filter („Bilder/Dateien", ZDR-Kennzeichnung) müssen im Foto-Endpunkt erzwungen werden — nicht nur im Frontend angeboten.
- **Grenzen der Speichermenge**: Wie viele Foto-Einträge pro Person/Urlaub sind sinnvoll, bevor es Rauschen wird?
- **Löschen/Korrigieren von gespeicherten Personen-Fakten** — soll es einen Pfad geben („Doch, das war nicht Pisa")?

---

## 📂 Weiterführendes aus diesem Workspace

- Mikrofon-Slice (Transkription → Glättung → Auto-Senden) ist fertig: `plan.md`, `docs/embeddings-auf-termux.md`
- Wissensdatenbank-Strang läuft in einer eigenen Sitzung (Projektplan: `C:\Users\sebas\.claude\plans\resilient-sleeping-kurzweil.md`) — SQLite + `mistral-embed` über API, Scheibe 1+2 fertig (35.893 Nachrichten, 26.354 Chunks, 175 Tests grün)
- **Befund** aus den Embeddings-Notizen: OpenRouter kann **keine** Embeddings; Mistral ohne ZDR hält Daten 30 rollierende Tage. Für Fotos (Personendaten) ist die ZDR-Frage daher strenger zu prüfen als für Text-Chats.

---

*Brainstorming-Vorlage erstellt am 13.08.2026 aus dem Grill-Gespräch mit Cline. Basis für die nächste Planungs-Phase (Slice A: Foto im Chat → Beschreibung → Wiedererkennung).*