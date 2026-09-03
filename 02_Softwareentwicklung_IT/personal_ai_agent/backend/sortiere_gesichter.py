"""Sortiert Smartphone-Fotos nach erkannten Gesichtern in Personen-Ordner.

Nutzt die echte SFace-Embedding-Erkennung (proot-Debian). Pro Quelle:
  - liest alle Bild-Dateien (jpg/jpeg/png/webp/heic)
  - detektiert + embeddet Gesichter, matcht gegen den Katalog
  - sortiert in <ausgabe_base>/<Person>/... bzw. _neu/ (unbekannt) / _kein_gesicht/

Modi:
  --modus copy   (Default): kopiert in JEDEN passenden Personen-Ordner, Quelle bleibt.
  --modus move         : verschiebt einmalig in den besten Treffer, Quelle wird geleert.

Checkpoint/Resume: schreibt verarbeitete Dateien in eine .state.json unter
AUSGABE_BASE — ein abgebrochener Lauf setzt beim Neustart fort statt neu
anzufangen. --checkpoint kein → Zustand ignorieren (frischer Lauf).

Sicherheit: nur lesen + schreiben in AUSGABE_BASE; fremde Dateien nie ändern.
Demo-/Trockenlauf: --dry-run gibt nur aus, wohin es ginge (kein Copy/Move).
"""
import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services import face_service  # noqa: E402

# Standards
DEFAULT_QUELLE = os.path.expanduser("~/storage/dcim/Lieblingsbilder")
DEFAULT_AUSGABE = os.path.expanduser("~/aussortierte_gesichter")
_BILD_EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")
_KEIN_GESICHT = "_kein_gesicht"
_NEU = "_neu"


def _personen_bekannt():
    return {p["name"] for p in face_service.gesichter_service.liste_personen()}


def bild_dateien(quelle):
    dateien = []
    for root, _dirs, files in os.walk(quelle):
        for f in files:
            if f.lower().endswith(_BILD_EXT) and not f.startswith("."):
                dateien.append(os.path.join(root, f))
    return sorted(dateien)


def klassifiziere(pfad):
    """Gibt (personen, hat_unbekannt) zurück.

    personen = Menge bekannter Namen, die sicher erkannt wurden.
    hat_unbekannt = True, wenn mindestens ein erkanntes Gesicht keinem
    Katalog-Eintrag <= _SCHWELLE_UNSICHER zugeordnet werden konnte.
    """
    personen = set()
    hat_unbekannt = False
    for gesicht in face_service.embeddings_fuer_pfad(pfad):
        emb = gesicht.get("embedding")
        if not emb:
            continue
        treffer = face_service.erkenne_personen(emb)
        sicher = [
            t["name"] for t in treffer if t.get("sicher")
        ]
        if sicher:
            personen.update(sicher)
        else:
            # unbekannt, sofern kein unsicherer Kandidat in der engen Naehe
            if not any(t.get("distanz") is not None for t in treffer):
                hat_unbekannt = True
    return personen, hat_unbekannt


def zielfolge(datei, personen, hat_unbekannt):
    """.(tag, absolute_zielpfade) für die Datei."""
    name = os.path.basename(datei)
    if personen:
        if MODUS == "move":
            # einmalig in besten (erste alpha) Treffer
            return [(tuple(sorted(personen)),
                     [os.path.join(ausgabe, sorted(personen)[0], name)])]
        else:
            ziele = [os.path.join(ausgabe, n, name) for n in sorted(personen)]
            return [(tuple(sorted(personen)), ziele)]
    if hat_unbekannt:
        return [({"unbekannt"}, [os.path.join(ausgabe, _NEU, name)])]
    return [({"kein_gesicht"}, [os.path.join(ausgabe, _KEIN_GESICHT, name)])]


def main():
    global MODUS, ausgabe
    ap = argparse.ArgumentParser(description="Gesichter-Sortierer")
    ap.add_argument("--quelle", default=DEFAULT_QUELLE)
    ap.add_argument("--ausgabe", default=DEFAULT_AUSGABE)
    ap.add_argument("--modus", choices=["copy", "move"], default="copy")
    ap.add_argument("--dry-run", action="store_true",
                    help="nur ausgeben, nichts kopieren/verschieben")
    ap.add_argument("--checkpoint", choices=["an", "aus"], default="an")
    ap.add_argument("--max", type=int, default=None,
                    help="nur bis N Dateien verarbeiten (zum Testen)")
    args = ap.parse_args()

    MODUS = args.modus
    SRC = None
    quelle = os.path.expanduser(args.quelle)
    ausgabe = os.path.expanduser(args.ausgabe)
    if not os.path.isdir(quelle):
        print(f"Quelle nicht gefunden: {quelle}")
        return 1

    os.makedirs(ausgabe, exist_ok=True)
    state_pfad = os.path.join(ausgabe, ".state.json")
    fertig = set()
    if args.checkpoint == "an" and os.path.exists(state_pfad):
        try:
            fertig = set(json.load(open(state_pfad)).get("fertig", []))
            print(f"Resume: {len(fertig)} bereits verarbeitete Dateien ignoriert.")
        except Exception:
            fertig = set()

    dateien = bild_dateien(quelle)
    print(f"Quelle: {quelle}\nBilder gefunden: {len(dateien)}\n"
          f"Modus: {MODUS}  DryRun: {args.dry_run}")
    if args.max:
        dateien = dateien[: args.max]

    t0 = time.time()
    zaehler = {}  # ziel -> anzahl
    for i, datei in enumerate(dateien, 1):
        if os.path.abspath(datei) in fertig:
            continue
        try:
            personen, hat_unbekannt = klassifiziere(datei)
        except Exception as e:
            print(f"  [FEHLER] {os.path.basename(datei)}: {e}")
            continue
        gruppen = zielfolge(personen, hat_unbekannt)
        for (_tag, ziele) in gruppen:
            for rel in ziele:
                dst = os.path.join(ausgabe, rel)
                zaehler[os.path.dirname(rel)] = zaehler.get(os.path.dirname(rel), 0) + 1
                if args.dry_run:
                    print(f"  [dry-run] {os.path.basename(datei)} -> {rel}")
                    continue
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if MODUS == "move":
                    if i == len(dateien) or True:
                        pass
                if MODUS == "copy":
                    shutil.copy2(datei, dst)
                else:
                    # move: nur das erste Ziel der ersten Gruppe verschieben
                    if dst == os.path.join(ausgabe, gruppen[0][1][0]):
                        shutil.move(datei, dst)
        # Checkpoint nach jeder Datei
        fertig.add(os.path.abspath(datei))
        if args.checkpoint == "an":
            with open(state_pfad, "w") as f:
                json.dump({"fertig": sorted(fertig)}, f)
        if i % 20 == 0 or i == len(dateien):
            el = time.time() - t0
            rest = (el / i) * (len(dateien) - i)
            print(f"  {i}/{len(dateien)}  ({el:.0f}s, Rest~{rest:.0f}s)")

    print("\n=== Ergebnis ===")
    for k in sorted(zaehler):
        print(f"  {k}: {zaehler[k]}")
    print(f"Fertig in {ausgabe} ({time.time()-t0:.0f}s).")


if __name__ == "__main__":
    main()