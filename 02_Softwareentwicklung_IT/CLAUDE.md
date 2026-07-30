<!--
  DIESE DATEI WURDE AUTOMATISCH GENERIERT (sync-rules.ps1)
  AENDERUNGEN IN DIESER DATEI WERDEN BEIM NAECHSTEN RUN UEBERSCHRIEBEN!
  Bitte aendere die globale CLAUDE.md im Hauptverzeichnis oder die lokale CLAUDE_EXTENDS.md.
-->

> **Basis-Regelwerk:** Es gelten weiterhin die globalen KI-Direktiven aus `../CLAUDE.md` (Workspace-Wurzel).
> Sie sind hier bewusst nicht kopiert, damit es nur eine Quelle gibt. Claude Code liest sie von sich aus mit.

<!-- LOKALE PROJEKT-ERWEITERUNGEN (EXTENDS) -->

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

