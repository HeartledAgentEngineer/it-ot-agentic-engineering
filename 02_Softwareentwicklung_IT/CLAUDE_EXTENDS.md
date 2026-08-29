# ==============================================================================
# BEREICHS-ERWEITERUNG: SOFTWAREENTWICKLUNG (IT)
# ==============================================================================

Dieses Regelwerk erweitert die globalen KI-Direktiven um Richtlinien für responsive, ästhetisch anspruchsvolle Web- und Appentwicklung (Frontend, Backend, Mobile).

---

## 1. DESIGN-AESTHETICS & PREMIUM-LOOK

Jede Benutzeroberfläche (HMI, App, Web-Frontend) muss den Benutzer auf den ersten Blick faszinieren ("Wow-Effekt"). Einfache, standardmäßige Layouts sind nicht akzeptabel.

* **Farbpaletten:** Harmonische, kuratierte HSL-Farben statt Standardfarben. Dunkle Modi (Dark Mode) als Standard, verziert mit dezenten, edlen Farb-Akzenten.
* **Typografie:** Verwendung moderner, runder Google-Fonts (z. B. *Inter*, *Roboto*, *Outfit* oder *Lexend*) anstelle von Systemschriftarten.
* **Details:** Smooth gradients (weiche Verläufe), Glassmorphism-Effekte (transparente Frostglas-Optik) und subtile Schlagschatten für räumliche Tiefe.
* **Animationen:** Verwendung von Mikro-Animationen bei Benutzer-Interaktion (Hover-Effekte, geschmeidige Übergänge bei Button-Klicks, sanftes Einblenden).

---

## 2. WEB- & APP-TECHNOLOGIEN

* **Frontend:** Moderner, modularer Code in HTML/CSS/JS oder modernen Frameworks (Vite, React Native).
* **Mobile (Expo Go):** Lokaler Datenabgleich via `AsyncStorage` auf dem Mobilgerät. Flüssige Performance durch Lazy-Loading von Elementen.
* **Backend:** Flask / Python für asynchrone Logik auf dem PC, Port 5000. Datenhaltung in strukturierten JSON- oder SQL-Datenbanken.

---

## 3. RESPONSIVE LAYOUTS & SEO-BEST-PRACTICES

* **Responsivität:** Jede Web-Anwendung muss sich nahtlos an alle Bildschirmgrößen anpassen (Mobile, Tablet, Desktop).
* **Semantic HTML:** Verwendung von HTML5-Elementen (`<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`) statt reinem `<div>`-Wust.
* **Eindeutige IDs:** Alle interaktiven Elemente (Buttons, Inputs) müssen eindeutige, deskriptive IDs für automatisiertes Testen besitzen.
* **SEO-Richtlinien:** Jede Seite besitzt einen einzigartigen `<title>` und eine aussagekräftige `<meta description>` für Suchmaschinen.

---

## 4. PRÜFBEFEHLE (VERIFIER-GATE)

Ein Schritt gilt als fertig, wenn der Prüfbefehl des Projekts Exit-Code 0 liefert.
Die folgenden Befehle sind verifiziert — sie wurden ausgeführt, nicht abgeschrieben.
Pfade sind relativ zum Projektverzeichnis.

| Projekt | Prüfbefehl | Stand |
|---|---|---|
| `typeFREE` | `set PYTHONPATH=. && python -m pytest windows/tests -q` | 84 Prüfungen, Exit 0 (11.08.2026) |
| `concertify` | `python -m pytest tests -q` | 180 Prüfungen, Exit 0 (11.08.2026) |
| `RAG-Systeme` | **fehlt.** Nur `test_embeddings.py` als Einzelskript, keine Testsuite | — |
| `document_automation` | **fehlt.** Keine Tests vorhanden | — |
| `personal_ai_agent` | **fehlt.** Nur manueller Health-Check auf `/api/health` | — |
| `eichhoernchen_spiel` | **entfällt.** Einzelne HTML-Datei, Rapid-Prototyping-Demo | — |

**Was daraus folgt:**

* Projekte **mit** Prüfbefehl (`typeFREE`, `concertify`) dürfen an der langen Leine
  arbeiten: Phase 4–8 laufen als ein Durchlauf, mit dem Pflichtstopp nach Phase 4.
* Projekte **ohne** Prüfbefehl bleiben an der kurzen Leine: jede Änderung wird
  einzeln vorgelegt. Kein Durchlauf ohne maschinelles Gate.
* Fehlt einem Projekt der Prüfbefehl, wird das benannt — nicht ersetzt durch
  „sieht gut aus". Einen Prüfbefehl zu erfinden, der nichts prüft, ist schlimmer
  als keiner.

Prüfläufe gehören an den Subagenten `tester`, damit die Logs nicht im
Hauptkontext landen.

---

## 5. CACHE-BUSTING (PFLICHT bei Frontend-Änderungen)

**Gilt für `personal_ai_agent` (und jedes Web-Frontend im Workspace):**

Bei JEDER Änderung an Frontend-Dateien (`index.html`, `app.js`, `style.css`)
MUSS die `?v=`-Versionsnummer in `index.html` erhöht werden — sonst lädt der
Browser (Comet/Chrome) die alte gecachte Datei und die Änderung ist unsichtbar.

**Schema:** `JJJJMMTT` + laufender Buchstabe für mehrere Änderungen am selben Tag.
- Erste Änderung am 2026-08-24 → `?v=20260824A`
- Zweite am selben Tag → `?v=20260824B` (usw.)

**Regel:** Cache-Bump IMMER im selben Commit wie die Frontend-Änderung.
Niemals annehmen, der Browser lade "schon neu" — hartes Caching ist der
Normalfall (war bereits mehrfach die Fehlerursache).
