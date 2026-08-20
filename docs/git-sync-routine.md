# Git-Sync-Routine (`git_stand.sh`)

**Zweck:** Vor jeder Session (auf Windows *und* Termux) klar zeigen, wo der
aktuelle Git-Stand ist — damit nicht zwei Arbeitestationen gegeneinander pushen.

**Warum:** Buddy entwickelt auf Windows, hat aber unterwegs (Zug/Wochenende ohne
Laptop) Termux-Hermes als zweiten Entwickler-Ort. Beide klonen dasselbe GitHub-
Repo. Ohne eine Routine vor jeder Session entstehen diverge-Konflikte („remote
contains work you don't have").

## Nutzung

```bash
# Stand anzeigen (read-only; nur `git fetch` aktualisiert remote-ref lokal)
bash git_stand.sh          # im Repo
bash git_stand.sh /pfad    # anderes Repo

# Vor dem Arbeiten AUF DEM AKTUELLSTEN Stand (holt + rebase deine lokalen Commits)
bash git_stand.sh --pull
```

## Was es anzeigt
- Branch
- Letzter lokaler Commit (Hash, Titel, Datum)
- **Ahead** (lokal neu, noch nie gepusht) und **Behind** (remote neu, muss geholt werden)
- Uncommittete/untracked Dateien
- Empfehlung, wenn `pull --rebase` nötig ist

## Sync-Regeln
1. **Vor jeder Session** `git_stand.sh` aufrufen — du siehst sofort, ob remote neuer ist.
2. **Wer arbeitet ganz gerade:** Windows *oder* Termux, nie beide gleichzeitig am selben Pfad.
3. **Vor dem Pushen** immer `git pull --rebase` (vorsichtig — Rebase setzt eigene Commits obendrauf).
4. **Push nie autonom** — Push bestätigt Sebastian (Klick/OK). Siehe AGENTS.md.

## Verifiziert
Läuft auf Windows-Git-Bash (getestet) und Termux/Linux. Inalienables Pull-Prinzip
entnommen aus dem ersten praktischen Sync-Problem (2026-08-21).