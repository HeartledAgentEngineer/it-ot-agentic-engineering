#!/usr/bin/env node
// Critic — holt eine Zweitmeinung von Gemini ueber die Developer-API.
//
// Aufruf:
//   node pruefe.mjs --diff                 Prueft die uncommitteten Aenderungen
//   node pruefe.mjs datei1.js datei2.js    Prueft einzelne Dateien
//   node pruefe.mjs --diff --modell gemini-3-flash-preview
//
// Der API-Key kommt aus GEMINI_API_KEY. Er wird per Header uebertragen,
// nie ueber die URL, und nie ausgegeben.

import { execSync, spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const STANDARD_MODELL = "gemini-flash-latest";
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

function keyHolen() {
  if (process.env.GEMINI_API_KEY) return process.env.GEMINI_API_KEY.trim();
  // Claude Code startet oft mit einer aelteren Umgebung als Windows sie kennt.
  try {
    return execSync(
      `powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('GEMINI_API_KEY','User')"`,
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
const modellIndex = argumente.indexOf("--modell");
const modell = modellIndex !== -1 ? argumente[modellIndex + 1] : STANDARD_MODELL;

const nutzeAgy = argumente.includes("--agy");

let inhalt;
try {
  inhalt = inhaltSammeln(argumente);
} catch (fehler) {
  console.error(`FEHLER: ${fehler.message}`);
  process.exit(2);
}

// --- Weg 2: Antigravity (agy). 20 Anfragen/Tag, dafuer ohne API-Schluessel. ---
if (nutzeAgy) {
  const prompt = ANWEISUNG + inhalt;
  // Windows begrenzt Kommandozeilen auf ~32k Zeichen. Groessere Diffs abfangen,
  // statt sie abgeschnitten zu pruefen - ein halbes Review ist schlimmer als keins.
  if (prompt.length > 30000) {
    console.error(
      `FEHLER: Umfang zu gross fuer agy (${prompt.length} Zeichen, Grenze 30000).\n` +
        `Weniger Dateien pruefen oder ohne --agy laufen lassen (API-Weg hat kein Limit).`,
    );
    process.exit(2);
  }
  // --sandbox: agy darf nichts ausfuehren. Der Code steckt im Prompt, damit agy
  // keine Werkzeug-Rechte braucht - im Hintergrundbetrieb wuerden die abgelehnt.
  const lauf = spawnSync(AGY_PFAD, ["--sandbox", "-p", prompt], {
    encoding: "utf8",
    maxBuffer: 20e6,
  });
  if (lauf.error) {
    console.error(`FEHLER: agy nicht startbar (${lauf.error.message}).`);
    console.error(`Erwartet unter: ${AGY_PFAD}`);
    process.exit(1);
  }
  const ausgabe = (lauf.stdout ?? "").trim();
  if (!ausgabe || /permission|no output produced/i.test(ausgabe)) {
    console.error("FEHLER: agy lieferte kein Protokoll.");
    console.error(ausgabe || lauf.stderr?.slice(0, 400) || "(keine Ausgabe)");
    process.exit(1);
  }
  console.log(ausgabe);
  console.error(`\n[Modell: Antigravity (agy) | Kontingent: 20 Anfragen/Tag]`);
  process.exit(0);
}

// --- Weg 1: Gemini Developer-API. 1.500 Anfragen/Tag. ---
const key = keyHolen();
if (!key) {
  console.error("FEHLER: GEMINI_API_KEY ist nicht gesetzt.");
  process.exit(2);
}

const antwort = await fetch(
  `https://generativelanguage.googleapis.com/v1beta/models/${modell}:generateContent`,
  {
    method: "POST",
    headers: { "x-goog-api-key": key, "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [{ text: ANWEISUNG + inhalt }] }],
      generationConfig: { temperature: 0.1 },
    }),
  },
);

if (!antwort.ok) {
  const text = await antwort.text();
  // Klartext statt Rohfehler - sonst ist "Kontingent leer" nicht von "kaputt" zu unterscheiden.
  if (antwort.status === 429) console.error("FEHLER: Tageskontingent erschoepft (HTTP 429).");
  else if (antwort.status === 403) console.error("FEHLER: Key abgelehnt oder Modell gesperrt (HTTP 403).");
  else if (antwort.status === 404) console.error(`FEHLER: Modell "${modell}" existiert nicht (HTTP 404).`);
  else console.error(`FEHLER: HTTP ${antwort.status}`);
  console.error(text.slice(0, 400));
  process.exit(1);
}

const daten = await antwort.json();
const ergebnis = daten?.candidates?.[0]?.content?.parts?.map((p) => p.text).join("") ?? "";

if (!ergebnis.trim()) {
  console.error("FEHLER: Leere Antwort vom Modell.");
  console.error(JSON.stringify(daten).slice(0, 400));
  process.exit(1);
}

console.log(ergebnis.trim());
console.error(`\n[Modell: ${modell} | Tokens: ${daten?.usageMetadata?.totalTokenCount ?? "?"}]`);
