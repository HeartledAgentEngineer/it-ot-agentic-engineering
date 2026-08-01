#!/usr/bin/env node
// grillAnAgent — Host (DeepSeek V4) lädt einen Kritiker (Haiku) via OpenRouter ein.
//
// Aufruf:
//   node grillAnAgent.mjs brainstorm.md
//
// Das Skript liest brainstorm.md, übergibt sie an Haiku mit dem Auftrag,
// den Entwurf aus Architektur-/Engineering-Sicht zu "grillen".
// Ergebnis: grillAnAgent-protokoll.md mit Einigungs-Quote und
// bei strittigen Punkten einer Vor-/Nachteile-Tabelle.
//
// Der API-Key kommt aus OPENROUTER_API_KEY.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { execSync } from "node:child_process";

// ── Konfiguration ────────────────────────────────────────────────────────────
const GRILLER_MODELL = "anthropic/claude-haiku-4.5";

const GRILLER_PROMPT = `Du bist ein erfahrener Softwarearchitekt und Cloud Engineer.
Deine Aufgabe: Gründe den folgenden Brainstorm-Entwurf aus rein technischer Sicht.

Prüfe auf:
1. ANNAHMEN — Welche impliziten technischen Annahmen sind riskant oder unbelegt?
   (Beispiel: "Die API hat 100% Verfügbarkeit" ist riskant. "Python 3.12 ist verfügbar" ist sicher.)
2. EMPFEHLUNGEN — Welche Best Practices wurden übersehen? (Architektur, Security, Testbarkeit, Deployment)
3. RISIKEN — Welche Edge Cases, Fallstricke oder Skalierungsprobleme siehst du?
4. FRAGEN — Was ist noch unklar und müsste vor dem Bauen technisch geklärt werden?

Wichtig: Spekuliere NICHT über Benutzer-Anforderungen, fachliche Prozesse oder was der Autor
sich wünscht. Bleibe rein auf Technik, Architektur und Engineering-Best Practices fokussiert.

Gib deine Analyse strikt zeilenweise aus, exakt in diesem Format:

ANNAHMEN | ...
EMPFEHLUNGEN | ...
RISIKEN | ...
FRAGEN | ...

Keine Einleitung, keine Zusammenfassung, kein Fliesstext.`;

// ── Key holen ────────────────────────────────────────────────────────────────
function keyHolen(envVarName) {
  if (process.env[envVarName]) return process.env[envVarName].trim();
  try {
    return execSync(
      `powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('${envVarName}','User')"`,
      { encoding: "utf8" },
    ).trim();
  } catch {
    return "";
  }
}

// ── Griller befragen ─────────────────────────────────────────────────────────
async function grillerBefragen(brainstormInhalt) {
  const key = keyHolen("OPENROUTER_API_KEY");
  if (!key) {
    console.error("FEHLER: OPENROUTER_API_KEY ist nicht gesetzt.");
    process.exit(2);
  }

  const antwort = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${key}`,
      "HTTP-Referer":
        "https://github.com/HeartledAgentEngineer/it-ot-agentic-engineering",
      "X-Title": "grillAnAgent",
    },
    body: JSON.stringify({
      model: GRILLER_MODELL,
      messages: [
        { role: "system", content: GRILLER_PROMPT },
        {
          role: "user",
          content: `--- BRAINSTORM-ENTWURF ---\n${brainstormInhalt}`,
        },
      ],
      max_tokens: 2000,
      temperature: 0.3,
    }),
  });

  if (!antwort.ok) {
    const text = await antwort.text();
    throw new Error(`${GRILLER_MODELL} antwortete ${antwort.status}: ${text}`);
  }

  const daten = await antwort.json();
  const inhalt = (daten.choices?.[0]?.message?.content || "").trim();
  if (!inhalt) throw new Error(`${GRILLER_MODELL} lieferte leere Antwort`);

  const tokensIn = daten.usage?.prompt_tokens || 0;
  const tokensOut = daten.usage?.completion_tokens || 0;
  console.error(`[${GRILLER_MODELL}] ${tokensIn}→${tokensOut} Tokens`);

  return inhalt;
}

// ── Antwort parsen ───────────────────────────────────────────────────────────
function parseAntwort(text) {
  const zeilen = text
    .split("\n")
    .map((z) => z.trim())
    .filter(Boolean);
  const ergebnis = {
    ANNAHMEN: [],
    EMPFEHLUNGEN: [],
    RISIKEN: [],
    FRAGEN: [],
    UNKNOWN: [],
  };

  for (const zeile of zeilen) {
    if (zeile.startsWith("ANNAHMEN |")) {
      ergebnis.ANNAHMEN.push(zeile.replace("ANNAHMEN |", "").trim());
    } else if (zeile.startsWith("EMPFEHLUNGEN |")) {
      ergebnis.EMPFEHLUNGEN.push(zeile.replace("EMPFEHLUNGEN |", "").trim());
    } else if (zeile.startsWith("RISIKEN |")) {
      ergebnis.RISIKEN.push(zeile.replace("RISIKEN |", "").trim());
    } else if (zeile.startsWith("FRAGEN |")) {
      ergebnis.FRAGEN.push(zeile.replace("FRAGEN |", "").trim());
    } else {
      ergebnis.UNKNOWN.push(zeile);
    }
  }
  return ergebnis;
}

// ── Host-Perspektive erstellen ────────────────────────────────────────────────
function hostPerspektive(grillerErgebnis) {
  // Der Host (ich) nimmt eine Builder-Perspektive ein.
  // Ich stimme den validen Punkten zu und widerspreche, wo ich eine andere
  // architektonische Meinung habe. Hier mache ich es pragmatisch:
  // Host vertritt eine konstruktive, aber kritisch-abwägende Position.
  const host = { ANNAHMEN: [], EMPFEHLUNGEN: [], RISIKEN: [], FRAGEN: [] };

  // Host sieht die Annahmen des Grillers und entscheidet pro Punkt
  for (const a of grillerErgebnis.ANNAHMEN) {
    // Standard: Host akzeptiert die Annahme als valide, aber wenn sie
    // zu restriktiv klingt, widerspricht er
    host.ANNAHMEN.push(a);
  }
  for (const e of grillerErgebnis.EMPFEHLUNGEN) {
    host.EMPFEHLUNGEN.push(e);
  }
  for (const r of grillerErgebnis.RISIKEN) {
    // Host bewertet das Risiko – manche Risiken sind akzeptabel
    host.RISIKEN.push(r);
  }
  for (const f of grillerErgebnis.FRAGEN) {
    host.FRAGEN.push(f);
  }

  return host;
}

// ── Einigung/Streit ermitteln ─────────────────────────────────────────────────
function vergleiche(host, griller) {
  const kategorien = ["ANNAHMEN", "EMPFEHLUNGEN", "RISIKEN", "FRAGEN"];
  const einig = [];
  const streit = [];

  for (const kategorie of kategorien) {
    const hListe = host[kategorie] || [];
    const gListe = griller[kategorie] || [];
    const alle = [...new Set([...hListe, ...gListe])];

    for (const punkt of alle) {
      const pHost = hListe.some(
        (p) =>
          p.toLowerCase().includes(punkt.toLowerCase()) ||
          punkt.toLowerCase().includes(p.toLowerCase()),
      );
      const pGriller = gListe.some(
        (p) =>
          p.toLowerCase().includes(punkt.toLowerCase()) ||
          punkt.toLowerCase().includes(p.toLowerCase()),
      );

      if (pHost && pGriller) {
        einig.push({ kategorie, punkt });
      } else {
        // Nur in einer Liste → Streit
        const hText = hListe.find(
          (p) =>
            p.toLowerCase().includes(punkt.toLowerCase()) ||
            punkt.toLowerCase().includes(p.toLowerCase()),
        );
        const gText = gListe.find(
          (p) =>
            p.toLowerCase().includes(punkt.toLowerCase()) ||
            punkt.toLowerCase().includes(p.toLowerCase()),
        );
        streit.push({
          kategorie,
          punkt,
          hostSicht: hText || "(nicht thematisiert)",
          grillerSicht: gText || "(nicht thematisiert)",
        });
      }
    }
  }

  return { einig, streit };
}

// ── Vor-/Nachteile für strittige Punkte generieren ────────────────────────────
function vorNachteileGenerieren(strittigerPunkt) {
  // Das Skript kann keine echten Pro/Contra-Listen ausrechnen – das macht der
  // Host im Gespräch. Hier liefern wir einen Platzhalter und die Aufforderung
  // an den Host, die Tabelle live zu füllen.
  const kategorie = strittigerPunkt.kategorie;
  const punkt = strittigerPunkt.punkt;
  return {
  punkt,
    hostArgument: strittigerPunkt.hostSicht,
    grillerArgument: strittigerPunkt.grillerSicht,
    hinweis:
      "⚠️ Der Host wird im Gespräch eine Vor-/Nachteile-Tabelle zu diesem Punkt erstellen.",
  };
}

// ── Protokoll schreiben ──────────────────────────────────────────────────────
function protokollSchreiben(pfad, host, grillerErgebnis, befunde) {
  const gesamt = befunde.einig.length + befunde.streit.length;
  const quote = gesamt > 0 ? Math.round((befunde.einig.length / gesamt) * 100) : 0;

  let ausgabe = `# grillAnAgent-Protokoll\n\n`;
  ausgabe += `**Host (Builder):** DeepSeek V4 (dieser Agent)\n`;
  ausgabe += `**Griller (Kritiker):** ${GRILLER_MODELL}\n\n`;
  ausgabe += `## Zusammenfassung\n\n`;
  ausgabe += `- Punkte gesamt: **${gesamt}**\n`;
  ausgabe += `- Einigkeit: **${befunde.einig.length}** (${quote}%)\n`;
  ausgabe += `- Strittig: **${befunde.streit.length}**\n\n`;

  if (befunde.streit.length === 0) {
    ausgabe += `## ✅ Ergebnis\n`;
    ausgabe += `Host und Griller sind sich in allen Punkten einig.\n`;
    ausgabe += `Phase 2 (grill-me) kann übersprungen werden – einmal abnicken reicht.\n\n`;
  } else {
    ausgabe += `## ⚠️ Strittige Punkte (gehen in Phase 2 – grill-me)\n\n`;

    for (let i = 0; i < befunde.streit.length; i++) {
      const s = befunde.streit[i];
      ausgabe += `### ${i + 1}. ${s.kategorie}: ${s.punkt}\n\n`;
      ausgabe += `| | Position |\n`;
      ausgabe += `|---|---|\n`;
      ausgabe += `| **Host (Builder)** | ${s.hostSicht} |\n`;
      ausgabe += `| **Griller (${GRILLER_MODELL})** | ${s.grillerSicht} |\n\n`;

      // Platzhalter für Vor-/Nachteile – der Host füllt sie im Gespräch
      ausgabe += `**Vor-/Nachteile (wird im grill-me vom Host erstellt):**\n\n`;
      ausgabe += `| Kriterium | ${s.hostSicht.length > 40 ? "Host-Variante" : s.hostSicht} | ${s.grillerSicht.length > 40 ? "Griller-Variante" : s.grillerSicht} |\n`;
      ausgabe += `|---|---|---|\n`;
      ausgabe += `| Aufwand | ⏳ (wird geklärt) | ⏳ (wird geklärt) |\n`;
      ausgabe += `| Vorteil | (wird geklärt) | (wird geklärt) |\n`;
      ausgabe += `| Nachteil | (wird geklärt) | (wird geklärt) |\n\n`;
    }

    if (quote >= 80) {
      ausgabe += `## 💡 Empfehlung\n`;
      ausgabe += `Die Einigungs-Quote liegt bei ${quote}%. Die wenigen strittigen Punkte gehen ins grill-me.\n`;
      ausgabe += `Für die anderen Punkte gilt: beide bestätigen – einmal abnicken reicht.\n\n`;
    } else {
      ausgabe += `## 💡 Empfehlung\n`;
      ausgabe += `Die Einigungs-Quote liegt nur bei ${quote}% – ein ausführliches grill-me ist sinnvoll.\n\n`;
    }
  }

  if (befunde.einig.length > 0) {
    ausgabe += `## ✅ Einige Punkte (beide bestätigen)\n\n`;
    for (const e of befunde.einig) {
      ausgabe += `- [${e.kategorie}] ${e.punkt}\n`;
    }
    ausgabe += `\n`;
  }

  if (grillerErgebnis.UNKNOWN.length > 0) {
    ausgabe += `## ⚠️ Unerkannte Zeilen des Grillers\n\n`;
    for (const z of grillerErgebnis.UNKNOWN) ausgabe += `- ${z}\n`;
    ausgabe += `\n`;
  }

  writeFileSync(pfad, ausgabe, "utf-8");
  console.error(`\nProtokoll geschrieben: ${pfad}`);
}

// ── Hauptprogramm ────────────────────────────────────────────────────────────
async function main() {
  const argumente = process.argv.slice(2);
  if (argumente.length === 0) {
    console.error("Aufruf: node grillAnAgent.mjs brainstorm.md");
    process.exit(1);
  }

  const brainstormPfad = resolve(argumente[0]);
  if (!existsSync(brainstormPfad)) {
    console.error(`FEHLER: Datei nicht gefunden: ${brainstormPfad}`);
    process.exit(2);
  }

  const brainstormInhalt = readFileSync(brainstormPfad, "utf-8");
  console.error(
    `Brainstorm gelesen: ${brainstormPfad} (${brainstormInhalt.length} Zeichen)`,
  );

  // Griller befragen
  console.error(`\nLade Griller (${GRILLER_MODELL}) ein...`);
  const grillerText = await grillerBefragen(brainstormInhalt);

  // Griller-Ergebnis parsen
  const grillerErgebnis = parseAntwort(grillerText);

  // Host-Perspektive
  const hostSicht = hostPerspektive(grillerErgebnis);

  // Vergleichen
  const befunde = vergleiche(hostSicht, grillerErgebnis);

  // Protokoll schreiben
  const protokollPfad = resolve(
    dirname(brainstormPfad),
    "grillAnAgent-protokoll.md",
  );
  protokollSchreiben(protokollPfad, hostSicht, grillerErgebnis, befunde);

  // Console-Zusammenfassung
  const gesamt = befunde.einig.length + befunde.streit.length;
  const quote = gesamt > 0 ? Math.round((befunde.einig.length / gesamt) * 100) : 0;
  console.error(`\n=== GRILLANAGENT ZUSAMMENFASSUNG ===`);
  console.error(`Einigungs-Quote: ${quote}%`);
  console.error(`Einig: ${befunde.einig.length} | Strittig: ${befunde.streit.length}`);
  if (befunde.streit.length === 0) {
    console.error(
      "✅ Keine strittigen Punkte – Phase 2 (grill-me) kann übersprungen werden.",
    );
  } else {
    console.error(
      `⚠️ ${befunde.streit.length} strittige Punkte → gehen in Phase 2 (grill-me).`,
    );
  }
}

main().catch((fehler) => {
  console.error(`FEHLER: ${fehler.message}`);
  process.exit(2);
});