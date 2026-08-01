#!/usr/bin/env node
// Critic — holt eine Zweitmeinung über OpenRouter.
//
// Aufruf:
//   node pruefe.mjs --diff                 Prueft die uncommitteten Aenderungen
//   node pruefe.mjs datei1.js datei2.js    Prueft einzelne Dateien
//
// Der API-Key kommt aus OPENROUTER_API_KEY. Er wird per Header uebertragen,
// nie ueber die URL, und nie ausgegeben.

import { execSync, spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const OPENROUTER_STANDARD_MODELL = "anthropic/claude-haiku-4.5"; // Unser gewähltes Standardmodell für Critic (etwas teurer, leicht besser)
const AGY_PFAD = "C:\\Users\\sebas\\AppData\\Local\\agy\\bin\\agy.exe";

const ANWEISUNG = `Du bist ein strenger Senior Code Reviewer. Pruefe den folgenden Code.

Gib AUSSCHLIESSLICH ein Protokoll aus, ein Befund pro Zeile, exakt in diesem Format:
DATEI:ZEILE | SCHWEREGRAD | PROBLEM | VORSCHLAG

SCHWEREGRAD ist genau eines von: KRITISCH, HOCH, MITTEL, NIEDRIG.
Ein Absturz zur Laufzeit ist mindestens HOCH. Eine Sicherheitsluecke ist KRITISCH.

Antworte auf Deutsch. Keine Einleitung, keine Zusammenfassung, kein Fliesstext,
keine Markdown-Formatierung. Findest du nichts, gib exakt "KEINE BEFUNDE" aus.

--- ZU PRUEFENDER CODE ---
`;

function keyHolen(envVarName) {
  if (process.env[envVarName]) return process.env[envVarName].trim();
  // Claude Code startet oft mit einer aelteren Umgebung als Windows sie kennt.
  try {
    return execSync(
      `powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('${envVarName}','User')"`,
      { encoding: "utf8" },
    ).trim();
  } catch {
    return "";
  }
}

function inhaltSammeln(argumente) {
  if (argumente.includes("--diff")) {
    const diff = execSync("git diff HEAD", { encoding: "utf8", maxBuffer: 20e6 });
    // git diff kennt neue Dateien nicht. Ohne sie bliebe der frischeste Code ungeprueft.
    const neue = execSync("git ls-files --others --exclude-standard", { encoding: "utf8" })
      .split("\n")
      .filter((p) => p.trim() && !/\.(png|jpg|jpeg|gif|pdf|zip|exe|dll|ico|woff2?)$/i.test(p));
    const neuerInhalt = neue
      .map((pfad) => {
        try {
          const zeilen = readFileSync(pfad, "utf8").split("\n");
          return `### NEUE DATEI: ${pfad}\n${zeilen.map((z, i) => `${i + 1}: ${z}`).join("\n")}`;
        } catch {
          return "";
        }
      })
      .filter(Boolean)
      .join("\n\n");
    if (!diff.trim() && !neuerInhalt) throw new Error("Keine uncommitteten Aenderungen gefunden.");
    return [diff, neuerInhalt].filter(Boolean).join("\n\n");
  }
  const dateien = argumente.filter((a) => !a.startsWith("--"));
  if (dateien.length === 0) throw new Error("Keine Dateien angegeben. --diff oder Dateipfade nutzen.");
  return dateien
    .map((pfad) => {
      const zeilen = readFileSync(pfad, "utf8").split("\n");
      const nummeriert = zeilen.map((z, i) => `${i + 1}: ${z}`).join("\n");
      return `### ${pfad}\n${nummeriert}`;
    })
    .join("\n\n");
}

const argumente = process.argv.slice(2);

let modell = OPENROUTER_STANDARD_MODELL;

let inhalt;
try {
  inhalt = inhaltSammeln(argumente);
} catch (fehler) {
  console.error(`FEHLER: ${fehler.message}`);
  process.exit(2);
}


// --- OpenRouter API. ---
  const key = keyHolen("OPENROUTER_API_KEY");
  if (!key) {
    console.error("FEHLER: OPENROUTER_API_KEY ist nicht gesetzt.");
    process.exit(2);
  }

  const antwort = await fetch(
    "https://openrouter.ai/api/v1/chat/completions",
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${key}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://openrouter.ai/agents/cline", // Optional: Für Statistiken
        "X-Title": "Cline Critic Skill", // Optional: Für Statistiken
      },
      body: JSON.stringify({
        model: modell,
        messages: [{ role: "user", content: ANWEISUNG + inhalt }],
        temperature: 0.1,
      }),
    },
  );

  if (!antwort.ok) {
    const text = await antwort.text();
    if (antwort.status === 429) console.error("FEHLER: OpenRouter Kontingent erschoepft (HTTP 429).");
    else if (antwort.status === 401) console.error("FEHLER: OpenRouter Key abgelehnt (HTTP 401).");
    else if (antwort.status === 404) console.error(`FEHLER: OpenRouter Modell "${modell}" existiert nicht (HTTP 404).`);
    else console.error(`FEHLER: OpenRouter HTTP ${antwort.status}`);
    console.error(text.slice(0, 400));
    process.exit(1);
  }

  const daten = await antwort.json();
  const ergebnis = daten?.choices?.[0]?.message?.content ?? "";

  if (!ergebnis.trim()) {
    console.error("FEHLER: Leere Antwort vom OpenRouter Modell.");
    console.error(JSON.stringify(daten).slice(0, 400));
    process.exit(1);
  }

  console.log(ergebnis.trim());
  console.error(`\n[Modell: ${modell} (OpenRouter) | Tokens: ${daten?.usage?.total_tokens ?? "?"}]`);
  process.exit(0);

