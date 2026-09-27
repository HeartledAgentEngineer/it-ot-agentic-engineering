# OpenRouter-Datenschutz (Zero Data Retention) — Prüfung der Anbindung

> **Datum:** 27.09.2026 (Nachtlauf) · **Auftrag:** „OpenRouter-Datenschutz
> (Zero Data Retention) für unsere Anbindung prüfen und einbauen." · **Ergänzung
> von Sebastian am selben Abend:** Das OpenRouter-Konto steht in den
> Security-Einstellungen auf **ZDR-only** (nur ZDR-Endpunkte erreichbar), und es
> existiert zusätzlich ein **Management-/Provisioning-Key**.
>
> **Ergebnis in einem Satz:** Unser Modell ist ZDR-fähig (21 Anbieter, live
> geprüft), der Anfrage-Wächter `provider {zdr:true, data_collection:"deny"}`
> wird akzeptiert, Hermes kann `provider_routing` nachweislich durchreichen —
> nur der `zdr`-Schlüssel fehlt dort; der EU-Sonderhost ist für das Konto
> gesperrt, und ein Workspace-Schalter speichert Eingaben/Ausgaben serverseitig.

## 0. Kontext / Ist-Stand

- Hermes läuft auf OpenRouter mit `deepseek/deepseek-v4.1-flash`
  (`C:\Users\sebas\AppData\Local\hermes\config.yaml`: `model.default`,
  `model.provider: openrouter`, `model.base_url: https://openrouter.ai/api/v1`).
- **Alle Prüfungen unten sind echte Aufrufe** vom 27.09.2026, ~02:42–02:57 UTC.
- Der API-Key wurde **nie ausgegeben** (nur Länge/Format geprüft), die `.env`
  wurde nur lesend ausgewertet. An Konto, Produktions-Config, git oder pCloud
  wurde **nichts** geändert. Für einen Wirkungstest von Hermes lief ein
  Wegwerf-`HERMES_HOME` im Hermes-Cache (Details §1.6).
- Kosten aller Testanfragen zusammen: deutlich unter 1 Cent.

## 1. Prüfungen und Ergebnisse

### 1.1 ZDR-Endpunktliste (`/api/v1/endpoints/zdr`)

Befehl:

```bash
curl -s https://openrouter.ai/api/v1/endpoints/zdr \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

Ergebnis: **HTTP 200**, 1.134.386 Bytes, 0,57 s; Struktur `{"data": [...]}`
mit **920 Endpunkt-Einträgen** zu **324 Modellen**.

| Modell | in ZDR-Liste? | ZDR-fähige Anbieter |
|---|---|---|
| **deepseek/deepseek-v4.1-flash** (unser Modell) | **ja** | **21** |
| openai/gpt-5.6-luna | ja | 1 (Azure; `gpt-5.6-luna-pro` ebenfalls nur Azure) |
| z-ai/glm-5.2 | ja | 16 |

Anbieter für unser Modell (21): BaseTen, CoreWeave, DeepInfra, DekaLLM,
DigitalOcean, Fireworks, InferenceNet, Makora, Modal, Morph, NextBit, Novita,
OpenInference, Parasail, Phala, Relace, Sail Research, SiliconFlow, Together,
Venice, Wafer.

Anbieter für z-ai/glm-5.2 (16): BaseTen, CoreWeave, Decart, DeepInfra,
DigitalOcean, Fireworks, Inceptron, Mistral, Novita, Parasail, Phala,
SiliconFlow, Together, Venice, Wafer, Z.AI.

Nebenbei geprüft: auch das Nebenaufgaben-Modell `google/gemini-3.7-flash`
(config.yaml, Abschnitt `auxiliary`) steht in der ZDR-Liste.

Gegenprobe: Die OpenRouter-Anbieter-Tabelle
(openrouter.ai/docs/guides/privacy/provider-logging) führt diese Anbieter als
„Zero retention / Does not train" — die Live-Liste ist also die ZDR-fähige
Teilmenge je Modell.

### 1.2 Eigener API-Key (`/api/v1/auth/key`) — nur maskiert

Ergebnis: **HTTP 200**, 735 Bytes. (Key selbst nie ausgegeben; Länge: 73
Zeichen, Standard-Präfix erkannt.)

```
label:                maskiert
is_free_tier:         false
limit:                null        limit_remaining: null
usage (gesamt, USD):  142.143308068
usage_daily:          1.22627935  usage_weekly: 22.029042594
usage_monthly:        94.953563739
allowed_data_regions: ["global"]  ← einziges Datenrichtlinien-Feld am Key
workspace_id:         906c5669-a3f9-557e-a54c-92ba1e78fd24
is_management_key / is_provisioning_key: false
```

### 1.3 EU-Host (`eu.openrouter.ai`) — erreichbar, aber gesperrt

Minimale Chat-Anfrage (unser Modell, `max_tokens: 4`) an
`https://eu.openrouter.ai/api/v1/chat/completions`.

Ergebnis: DNS löst auf (Cloudflare, `2a06:98c1:3200::90:83`), **HTTP 403**,
0,46 s. Fehlertext **wortgetreu** (kein Modell gelaufen, daher keine Modell-ID
in der Antwort):

```
{"message": "Regional routing not enabled for this account. Please reach out to our enterprise sales team to enable this feature.", "code": 403}
```

Der regionale EU-Host ist also eine **Enterprise-Funktion** und für dieses
Konto nicht freigeschaltet. (Ein Umstellen von `model.base_url` darauf wäre
technisch möglich, bringt aber nichts, solange das Konto nicht freigeschaltet
ist.)

### 1.4 Anfrage-Wächter `provider {zdr:true, data_collection:"deny"}` — akzeptiert

Fünf echte Chat-Anfragen gegen `https://openrouter.ai/api/v1/chat/completions`,
Modell `deepseek/deepseek-v4.1-flash`:

| Variante | HTTP | Antwort-Provider | Dauer | Kosten |
|---|---|---|---|---|
| Basis (ohne `provider`) | 200 | DeepInfra | 1,22 s | 0,000007 $ |
| `{zdr:true, data_collection:"deny"}` | 200 | DeepInfra | 0,65 s | 0,000007 $ |
| `{zdr:true}` | 200 | DeepInfra | 1,39 s | 0,000007 $ |
| `{data_collection:"deny"}` | 200 | DeepInfra | 3,98 s | 0,000007 $ |
| `{zdr:true, data_collection:"deny"}`, sichtbare Antwort | 200 | **Together** | 0,68 s | 0,000027 $ |

Beispielbefehl (letzte Zeile, gekürzt):

```bash
curl -s -X POST https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek/deepseek-v4.1-flash",
       "messages":[{"role":"user","content":"Antworte nur mit dem Wort OK"}],
       "max_tokens":200,
       "provider":{"zdr":true,"data_collection":"deny"}}'
```

Sichtbare Antwort der letzten Anfrage: `content: "OK"`, `finish_reason: stop`.
(Die ersten vier liefen mit `max_tokens: 4` vollständig in Reasoning-Tokens —
`reasoning_tokens: 4` —, deshalb dort kein sichtbarer Text;
`finish_reason: "length"`.) Beide bedienenden Anbieter (DeepInfra, Together)
stehen in der ZDR-Liste unseres Modells.

→ **Kein „no eligible endpoint":** Der kombinierte Wächter wird von OpenRouter
akzeptiert und die Anfrage regulär bedient.

### 1.5 Kann Hermes Request-Felder durchreichen? — Ja (`provider_routing`); `zdr` fehlt

- **Hermes-Doku** (live abgerufen, HTTP 200):
  `/docs/user-guide/features/provider-routing` — „Provider routing preferences
  are passed to OpenRouter on agent chat requests … via the `extra_body.provider`
  field." Unterstützte Schlüssel: `sort`, `only`, `ignore`, `order`,
  `require_parameters`, `data_collection` (plus per-Modell-Overrides `models`).
- **`hermes chat --help`**: keine Flags für Request-Felder (kein `--extra-body`
  o. Ä.); `--provider` betrifft nur die Provider-Auswahl.
- **Quelltext der installierten Version**
  (`C:\Users\sebas\AppData\Local\hermes\hermes-agent`):
  - `cli-config.yaml.example`, Abschnitt „OpenRouter Provider Routing":
    dokumentiert `provider_routing:` mit genau den sechs Schlüsseln.
  - `agent/chat_completion_helpers.py` → Funktion
    `_provider_preferences_for_agent`: baut das `provider`-Objekt aus genau
    diesen sechs Werten.
  - `hermes_cli/cli_init_mixin.py` liest beim Start
    `CLI_CONFIG.get("provider_routing")` — u. a. `data_collection`; dieselbe
    Sektion lesen auch Gateway und Cron-Pfade.
  - **`zdr` kommt in Hermes-Doku und Config-Schema nicht vor** (nur ein
    interner Kommentar nennt `zdr` als OpenRouter-Feld, das bewusst NICHT an
    Nous Portal gesendet wird). → Für den Haupt-Chat kann Hermes `provider.zdr`
    nicht setzen; das deckt die Konto-Einstellung ab.
  - `extra_body` existiert an drei anderen Stellen: `providers.<name>.extra_body`
    (eigene Provider-Definitionen), `auxiliary.<task>.extra_body`
    (wird **wortgetreu** an OpenRouter weitergereicht — dort wären auch
    `provider.zdr`-Felder möglich) und `delegation.request_overrides.extra_body`
    (Subagenten).
- **Ist-Zustand:** `hermes config get provider_routing` → „Config key not set:
  provider_routing" (nichts geändert).

### 1.6 End-zu-Ende-Beweis in einer Sandbox (nur Hermes-Cache, nicht Produktion)

Wegwerf-`HERMES_HOME` unterhalb `C:\Users\sebas\AppData\Local\hermes\cache\scratch`:

1. `hermes config set provider_routing.data_collection deny` → schreibt den
   Block korrekt. Der Setter warnt dabei „not a recognized config key"
   (Registry-Lücke des Setters; der Laufzeit-Code liest den Schlüssel
   nachweislich, siehe §1.5).
2. Echter Einzeiler mit dieser Config → Antwort **„OK"** (Session
   `20260927_045541_cd8866`).
3. **Differenztest:** zusätzlich `only: [zzz-nonexistent-provider]` in der
   Sandbox-Config → die Anfrage scheitert mit **HTTP 404**:

   ```
   Provider said: HTTP 404: No allowed providers are available for the
   selected model. Providers serving deepseek/deepseek-v4.1-flash-20260910:
   inference-net, wafer, relace, morph, sail-research, open-inference,
   deepinfra, dekallm, deepseek, streamlake, gmicloud, coreweave, nextbit,
   fireworks, phala, novita, atlas-cloud, baset…   (gekürzt)
   ```

   Kontrolllauf ohne den Filter → wieder „OK" (Session
   `20260927_045700_634c8d`; Fehllauf-Session `20260927_045637_d2ab71`).

→ Damit ist **bewiesen** (nicht nur laut Doku): Hermes reicht
`provider_routing` aus `config.yaml` wirklich als Provider-Vorgabe an
OpenRouter weiter. `data_collection` wird im selben Codepfad aus derselben
Sektion gelesen wie das getestete `only`.

### 1.7 Management-/Provisioning-Key (Nachtrag Sebastian)

**Variablennamen in `C:\Users\sebas\AppData\Local\hermes\.env`** (nur Namen,
niemals Werte): `TERMINAL_MODAL_IMAGE`, `TERMINAL_TIMEOUT`,
`TERMINAL_LIFETIME_SECONDS`, `BROWSERBASE_PROXIES`,
`BROWSERBASE_ADVANCED_STEALTH`, `BROWSER_SESSION_TIMEOUT`,
`BROWSER_INACTIVITY_TIMEOUT`, `WEB_TOOLS_DEBUG`, `VISION_TOOLS_DEBUG`,
`MOA_TOOLS_DEBUG`, `IMAGE_TOOLS_DEBUG`, **`OPENROUTER_API_KEY`**,
`API_SERVER_ENABLED`, `API_SERVER_KEY`, `API_SERVER_HOST`,
**`OPENROUTER_MANAGEMENT_KEY`**, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`.
→ Es existiert **beides**: normaler Key und Management-/Provisioning-Key.

Mit dem Management-Key (`GET https://openrouter.ai/api/v1/keys`):

- **HTTP 200**, 3.099 Bytes, **5 Keys**. Felder je Eintrag: `hash`, `name`,
  `label`, `disabled`, `limit`, `limit_remaining`, `limit_reset`, `usage` /
  `usage_daily` / `usage_weekly` / `usage_monthly`, `byok_usage*`,
  `include_byok_in_limit`, `created_at`, `updated_at`, `expires_at`,
  `creator_user_id`, `external_user`, `workspace_id`.
- Namen der Keys: „Hermes Agent", „personal_ai_agent", „typeFree",
  „critic-Skill", „agentic enineering". **Hashes und Labels sind maskiert;
  Schlüsselwerte stehen nirgends im Dokument.**
- `GET /api/v1/auth/key` mit dem Management-Key: HTTP 200 —
  `is_management_key: true`, `is_provisioning_key: true`, `usage: 0`,
  `allowed_data_regions: ["global"]`.

Weitere Proben (nur lesend, Management-Key): `/api/v1/account`, `/api/v1/settings`,
`/api/v1/me`, `/api/v1/organizations` → **404** („Not Found");
`/api/v1/workspaces` → **HTTP 200** (1 Eintrag „Default Workspace");
`/api/v1/guardrails` → HTTP 200, **`total_count: 0`** (keine Guardrails
konfiguriert); Einzelabruf der im Workspace referenzierten Guardrail → 404
„Workspace default guardrail has not been configured yet"; mit dem normalen
Key: 401 „Invalid management key".

**Klarstellung (wichtig):** Eine kontoweite „ZDR-only"-Einstellung ist über
**keinen** dieser API-Endpunkte sichtbar. Sichtbar sind nur
`allowed_data_regions` („global") und die Workspace-Schalter (§1.8). Der Beleg
für die ZDR-Schutzstufe ist daher die Kette: **Live-ZDR-Liste enthält unser
Modell (21 Anbieter) + echte erfolgreiche Anfragen, bedient von ZDR-Anbietern
(DeepInfra, Together) + akzeptierter Anfrage-Wächter `zdr+deny`.** Die
Konto-Einstellung selbst kann nur das Dashboard (Browser) zeigen — der
Management-Key gibt keine Konto-Richtlinien her.

### 1.8 Workspace-Befund: Eingabe-/Ausgabe-Logging ist AKTIV

`GET /api/v1/workspaces` (Management-Key), relevante Rohfelder:

```json
{"id":"906c5669-a3f9-557e-a54c-92ba1e78fd24",
 "default_guardrail_id":"2f6e923d-4cf6-59ba-9971-4aba8c47c025",
 "name":"Default Workspace","slug":"default",
 "is_observability_io_logging_enabled":true,
 "is_observability_broadcast_enabled":false,
 "is_data_discount_logging_enabled":false,
 "include_byok_in_budgets":false,"io_logging_sampling_rate":1,
 "io_logging_api_key_ids":null,
 "created_at":"2026-07-30T20:24:58.564Z","updated_at":"2026-08-02T23:17:31.919Z"}
```

Bedeutung laut OpenRouter-Doku (`/docs/guides/features/input-output-logging`,
`/docs/guides/privacy/data-collection`):

- `is_observability_io_logging_enabled: true` = **„Input & Output Logging"
  aktiv**: Prompt-/Completion-Inhalte werden serverseitig bei OpenRouter
  gespeichert (Logs-Seite; Aufbewahrung **mindestens 3 Monate**, Löschung auf
  Anfrage an support@openrouter.ai). Nicht für Training genutzt, admin-only.
- `is_data_discount_logging_enabled: false` = der Datenrabatt („OpenRouter darf
  Inputs/Outputs nutzen", 1 % Rabatt) ist **aus**. Gut.
- `is_observability_broadcast_enabled: false` = keine Weitergabe an externe
  Observability-Ziele.
- Allgemein (Doku): Ohne Opt-in speichert OpenRouter keine Prompt-Inhalte;
  **Metadaten** (Tokens, Latenz, Kosten) werden immer erfasst.

→ Das ist die eine Stelle, an der trotz ZDR **Inhalte gespeichert** sind. Sie
ist **nicht** per API änderbar — nur im Dashboard (Settings → Observability).

## 2. Welche Schutzstufe hat unser Modell jetzt?

| Ebene | Stand |
|---|---|
| Modell | `deepseek/deepseek-v4.1-flash` ist **ZDR-fähig** — 21 Anbieter in der Live-Liste (laut Anbieter-Tabelle: Zero retention, „Does not train") |
| Anfrage | Wächter `{zdr:true, data_collection:"deny"}` wird akzeptiert (live getestet); Hermes setzt ihn derzeit **nicht** (`provider_routing` leer) |
| Konto | laut Sebastian auf **ZDR-only** gestellt (nur im Dashboard sichtbar); Indiz: alle Testanfragen landeten auf ZDR-Anbietern (DeepInfra, Together) |
| Hermes | kann Routing per `provider_routing` senden (Sandbox-bewiesen); `zdr`-Schlüssel wird nicht unterstützt |
| Rest-Punkt | Workspace-**IO-Logging aktiv** (OpenRouter speichert Inhalte ≥ 3 Monate); EU-Host nicht nutzbar |

## 3. Was NICHT geht und warum

1. **EU-Host `eu.openrouter.ai`:** 403 „Regional routing not enabled for this
   account…" — Enterprise-Funktion, Konto nicht freigeschaltet.
2. **`zdr` als Hermes-Config-Schlüssel:** `provider_routing` kennt nur die
   sechs dokumentierten Schlüssel; `zdr` wird weder gelesen noch gesendet. Für
   den Haupt-Chat ist ZDR pro Anfrage nicht über die Hermes-Config erzwingbar
   — dafür ist die Konto-Einstellung da (Umweg: Custom-Provider mit
   `extra_body`, nicht nötig).
3. **Konto-Einstellungen per API:** nicht lesbar/änderbar (404 bzw. keine
   Policy-Felder) — nur Browser/Dashboard.
4. **Guardrails als ZDR-Weg:** aktuell keine konfiguriert (`total_count: 0`).
5. **IO-Logging-Schalter:** nur über das Dashboard änderbar (Browser nötig).

## 4. Empfehlung (NICHT ausgeführt — es wurde nichts geändert)

Der Reihe nach:

1. **Workspace-IO-Logging prüfen** (der wichtigste Punkt für „ZDR wörtlich"):
   Dashboard → Workspace-Settings → **Observability** → „Input & Output
   Logging". Wenn serverseitige Speicherung nicht gewollt ist: ausschalten.
   Vorher lohnt ein Blick auf `openrouter.ai/logs`, ob dort Inhalte liegen.
   *Nur mit Browser/Login möglich — bewusst nicht angefasst.*
2. **`provider_routing` in der Hermes-Config** (Verteidigung in der Tiefe,
   wirkt auch, falls sich die Konto-Einstellung einmal ändert).
   Datei: `C:\Users\sebas\AppData\Local\hermes\config.yaml` — neue
   Top-Level-Sektion, aktuell **nicht** vorhanden:

   ```yaml
   provider_routing:
     data_collection: "deny"
   ```

   Äquivalenter Befehl: `hermes config set provider_routing.data_collection deny`
   (Sandbox-getestet, §1.6; der Setter zeigt dabei den „not a recognized config
   key"-Hinweis — der Laufzeit-Code liest den Schlüssel trotzdem. Danach zur
   Gegenprobe `hermes config get provider_routing`.)
3. Optional für **Nebenaufgaben/Subagenten** (sie erben `provider_routing`
   nicht): `auxiliary.<task>.extra_body.provider.data_collection: "deny"`
   bzw. `delegation.request_overrides.extra_body.provider…` — Hermes reicht
   `extra_body` wortgetreu an OpenRouter weiter (Doku, §1.5).
4. **EU-Host:** kein Handlungsbedarf — nur Enterprise; nichts umstellen.

## 5. Belege

- Rohantworten der Prüfungen:
  `C:\Users\sebas\AppData\Local\hermes\cache\scratch\` (`zdr.json`,
  `authkey.json`, `chat_*.json`, `eu_chat.json`, `mkey_*.json`,
  `probe_*.json`) — Cache, nicht versioniert.
- OpenRouter-Doku: `guides/privacy/data-collection`,
  `guides/privacy/provider-logging`, `guides/features/input-output-logging`;
  ZDR-Anbieter-Liste per API (`api/v1/endpoints/zdr`).
- Hermes-Doku: `user-guide/features/provider-routing`; Quelltext
  `hermes-agent` (siehe §1.5); Sandbox-Beweise §1.6 (Sessions
  `20260927_045541_cd8866`, `20260927_045637_d2ab71`, `20260927_045700_634c8d`).
