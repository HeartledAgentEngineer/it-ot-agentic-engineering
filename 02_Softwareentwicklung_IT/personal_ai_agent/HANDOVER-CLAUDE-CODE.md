# HANDOVER — Personal AI Agent (for Claude Code)

Read this first. It is the entry point for a coding agent that has never seen
this repo. Written in English on purpose (workspace convention: scripts, agents
and docs in English, conversations in German).

**Owner:** Sebastian Wenck. **Language for user-facing talk: German.**
Code comments: English. Commit messages: German or English, both fine.

---

## 1. What this project is

A personal AI agent ("Personal AI Agent", internal name grillAnAgent) that runs
**phone-first** (Python FastAPI backend in Termux on an Android phone, vanilla-JS
PWA frontend served on `http://localhost:8080`). It answers from Sebastian's own
archive (WhatsApp, photos on pCloud, calendar, notes), listens and speaks German,
and is being extended into a self-improving "second brain".

Architecture rule (**binding**): everything that recurs must run **standalone
inside Android/Termux**; the Windows PC is only the workshop for heavy one-off
work. Data and credentials must live on the phone so jobs run without the PC.

---

## 2. Read these before touching anything

| File | Why |
|---|---|
| `../../AGENTS.md` (workspace root) | core rules: autonomy limits, push rules, verification |
| `../../02_Softwareentwicklung_IT/CLAUDE.md` | area rules: verifier gate, cache-busting, roles |
| `CLAUDE.md` in this folder | project rules: secrets, privacy, photo/face rules, duplicate rules |
| `docs/plan-nachtlauf-2026-09-26.md` | the live plan + journal (steps N1...N29b) |

**Do not** rewrite `CLAUDE.md` from scratch and do not run `/init` to overwrite
it — it is hand-maintained and contains legal/privacy decisions. Extend it.

---

## 2b. Privacy boundary — who may see what (binding)

**Claude Code / Codex / any non-Hermes agent works on CODE ONLY.**
No personal data ever passes through these tools: no chat content, no photos,
no contact names or numbers, no face data, no archive DBs, no `Chats von GPT,
GEMINI, Claude/`. Code, tests, docs and structure only.

All processing of personal data (chats, photos, contacts, calendar) happens
**only** through Hermes + OpenRouter, where `provider_routing.data_collection:
deny` is set (zero retention). Vision runs on `gemini-2.5-flash`, embeddings on
`text-embedding-3-small`, orchestration on `deepseek-v4.1-flash`. Face work uses
local models (YuNet/SFace) — no API at all.

If a task would need personal data inside Claude Code: **stop and hand it back**
to Hermes with a description of what is needed.

---

## 4. Verify command (the gate — no commit without green)

```bash
cd 02_Softwareentwicklung_IT/personal_ai_agent/backend
.venv/Scripts/python -m pytest tests/ -q        # Windows/git-bash
```

A git pre-commit hook (`.githooks/pre-commit`) runs this automatically for the
project whose code is staged. Current baseline: **2,924 passed, exit 0**.
"Done" means: gate green **and** docs updated **and** the evidence quoted.

---

## 4. Current state (measured, 28 Sep 2026)

| Area | State |
|---|---|
| Archive DB | `~/foto_sortierung`-side: 282,029 messages, 52,679 chunks, 52,679 vectors, 1,590 conversations |
| WhatsApp | 2,471 chats / 245,657 messages decrypted from the phone's local E2E backup (`msgstore.db.crypt15`) and imported; 744 chats matched to phone-book contacts, 6,242 group members (2,006 matched) |
| Photos | 9,430 files on pCloud, date + motif per event (2,127 events); **image descriptions per single photo: 2,267 of 9,430 done** |
| Persons | face clustering exists but the earlier numbers were **invalidated** (landmark bug, fixed) → must be recomputed |
| App | gallery + full-screen + slideshow done (N13b), streaming without cache growth (verified: 100 photos viewed, no memory change) |
| Open blocker | **OpenRouter credits nearly empty** (~$0.02) — anything that calls a model stops with HTTP 402 |

---

## 5. Data locations — PRIVATE, outside the repo

| What | Where |
|---|---|
| Archive (chats, indexes) | `Chats von GPT, GEMINI, Claude/` (repo-ignored, never commit) |
| Sorting keys, plans, results | `C:\Users\sebas\foto_sortierung\` (outside the repo) |
| pCloud token, OpenRouter key | `backend/.env` (ignored; **never** print, copy or commit) |
| WhatsApp key + Google token | `Chats von GPT, GEMINI, Claude/whatsapp_uebertragung/` |

**Privacy rules (binding, legal):**
- Chats and photos contain **third-party personal data**. Never put names, phone
  numbers, photos, chat content or addresses into the repo, docs, logs, commit
  messages or reports. Reports use **counts only**.
- Photos are never copied or stored by the backend: in-memory for the model call,
  then dropped. Media stays on the phone / pCloud and is streamed.
- Face vectors and the face catalogue never leave the PC.
- Duplicates may only be deleted when `hash` **and** `size` prove identity, and
  only the upload copy — never the original. Every deletion goes into a manifest.

---

## 6. Git rules for agents (collision protection)

```bash
# NEVER: git add -A / git commit -a  (a second agent may be working in the tree)
git commit --only <path> <path> -m "..."
git log --oneline -3            # look who else worked before committing
git rev-list --left-right --count origin/main...HEAD   # expect "0 0" after push
```

Push after a green gate is allowed (standing approval). **Never** `--force`.
On `cannot lock ref` / rejected push: `git pull --rebase`, then retry.

---

## 7. Cost and model rules

- Plan/verify with strong models, execute mass work with cheap ones
  (`deepseek-v4.1-flash`); `gpt-5.6-terra` only through the Codex CLI, never via
  OpenRouter (2.00/12.00 USD per M tokens).
- Measured reference prices: vision sheet 36 tiles ≈ **$0.0047**, i.e. ~$1.24
  for all 9,430 photos; text embeddings for 199,255 messages ≈ **$0.11**.
- Always set a hard budget cap per run and measure on a small sample first.

---

## 8. Open steps (see the plan file for details)

| Step | What | State |
|---|---|---|
| N15 | image description per photo (2,267 done) + image vector DB | blocked on credits |
| N19 | archive search: match **mentions**, not only chat partners | open |
| N22 | nightly maintenance job (new chats, photos, calendar) | open |
| N23 | everything must run on the phone alone (Termux scheduler) | rule, partially built |
| N24 | privacy/IT-security pass (app, Android, encryption, revocation) | planned |
| N25 | automatic backup of the archive DBs to pCloud (encrypted, restore test) | open |
| N26 | WhatsApp media (3,660 + 346 images) as second photo source | open |
| N27 | **link layer**: event objects = date + theme + photos + chats + people + calendar | done (N27a–e accepted) |
| N29 | transfer of relationship/event data files to the phone | done: code (N29) + cable push (N29b, 29.09.2026) — all five files in `/sdcard/Download` byte-identical (md5+sha256), manifest `manifest_handy.jsonl` has 5 lines; first takeover run on the phone still to be observed via `hermes_diag/uebergabe_letzte.txt` |
| N8 | actually move the 7,616 sorted photos (2,108 folders) | blocked: needs Sebastian's explicit go |
| N18 | deletion tool for the 12 copy remnants (581 MB) | approved, not built |

---

## 9. How to run Claude Code productively in this repo

```bash
# one-shot task, bounded (preferred)
claude -p "Run the gate and report the result" --allowedTools 'Read,Bash' --max-turns 5

# a step from the plan, isolated copy of the working tree
claude -w n27-link-layer -p "Read docs/plan-nachtlauf-2026-09-26.md, implement N27 step 1 only, add offline tests, update the changelog" --max-turns 30

# interactive, multi-turn (needs tmux)
claude --permission-mode acceptEdits
```

Rules of engagement for this repo:
1. **One plan step per session.** Do not invent scope.
2. Read the plan file, do the step, write offline tests, update
   `docs/changelog-*.md`, run the gate, commit with `--only`.
3. Ask before: deleting anything, touching pCloud contents, moving photos,
   spending more than $1, editing `CLAUDE.md`/`AGENTS.md` semantics.
4. Never print secrets; never copy private data into the repo.
5. Verification goes in the report: command + exit code + the numbers.
