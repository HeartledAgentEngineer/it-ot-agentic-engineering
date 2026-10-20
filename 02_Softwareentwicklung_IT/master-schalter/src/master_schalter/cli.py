"""Befehlszeile `masterwechsel`.

    masterwechsel status              beide Kontingente anzeigen
    masterwechsel statuszeile         Statuszeilen-Befehl für Claude Code (liest JSON von stdin)
    masterwechsel claude-kontingent   Claude-Werte von Hand eintragen (Ersatzweg ohne Statuszeile)
    masterwechsel claude-messen       Claude-Kontingent über die OAuth-API messen
    masterwechsel master              aktiven Master, Lage und Besetzung anzeigen
    masterwechsel wechsel claude|codex|hermes [--hinweis TEXT]
                                      Master wechseln und Übergabepaket schreiben
    masterwechsel paare               Paare aus Thema und Codex-Chat anzeigen
    masterwechsel paar-setzen THEMA UUID DATEI
                                      Paar anlegen/überschreiben (DATEI = .hermes/uebergabe/laufend/<thema>.md)
    masterwechsel paar-aktiv THEMA an|aus
                                      Paar für die Automatik ein- oder ausschalten
    masterwechsel automatik-pruefen [--trocken]
                                      Automatik Claude → Codex prüfen (trocken: nur zeigen)
    masterwechsel profil THEMA [--json]
                                      Rollenprofil lesen (Master, Ausführer, Modell) – vor jedem Workerauftrag
    masterwechsel master-setzen THEMA MASTER
                                      Masterrolle eines Themas setzen (kontingent|claude|codex|hermes)
    masterwechsel worker-setzen THEMA WORKER
                                      Ausführervorgabe setzen (workflow|claude|codex|hermes)
    masterwechsel modell-setzen THEMA MODELL
                                      Ausführermodell setzen ("standard" = Standard des Werkzeugs)
    masterwechsel modelle [PROVIDER] [--aktualisieren] [--json]
                                      Modellkataloge der Werkzeuge anzeigen oder abgleichen

Fehler werden mit Exit 1 und einer klaren Diagnose gemeldet – ohne rohe Antworten der Werkzeuge.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import (__version__, anzeige, automatik, claude_messen, modi, modelle, paare, rollen, rueckgabe,
               signale, wechsel, zustand)


def _statuszeile() -> int:
    """Darf nie scheitern: Claude Code zeigt sonst eine Fehlermeldung in der Statuszeile."""
    try:
        daten = json.load(sys.stdin)
        if isinstance(daten, dict):
            signale.claude_schreiben(daten.get("rate_limits"))
        print(anzeige.tooltip([signale.claude_lesen()]))
    except Exception:  # noqa: BLE001 - bewusst breit, siehe Docstring
        print(anzeige.tooltip([signale.claude_lesen()]))
    return 0


def _zeitpunkt(text: str) -> datetime:
    zeit = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)


def _prozent(text: str) -> float:
    wert = float(text)
    if not 0 <= wert <= 100:
        raise argparse.ArgumentTypeError("Prozent muss zwischen 0 und 100 liegen")
    return wert


def _claude_kontingent(args: argparse.Namespace) -> int:
    signale.claude_schreiben({
        "five_hour": {"used_percentage": args.fuenf, "resets_at": args.reset_fuenf.timestamp()},
        "seven_day": {"used_percentage": args.woche, "resets_at": args.reset_woche.timestamp()},
    })
    print(anzeige.tooltip([signale.claude_lesen()]))
    return 0


def _claude_messen() -> int:
    try:
        claude_messen.messen()
    except claude_messen.MessFehler as fehler:
        print(f"Claude-Messung fehlgeschlagen: {fehler}", file=sys.stderr)
        return 1
    except Exception:
        print("Claude-Messung fehlgeschlagen.", file=sys.stderr)
        return 1
    print("Claude-Kontingent aktualisiert.")
    return 0


def _lage(kontingente: list[signale.Kontingent]) -> tuple[str | None, str]:
    claude, codex = kontingente
    schwelle = anzeige.schwelle()
    return rollen.lage(claude, codex, schwelle), rollen.lage_grund(claude, codex, schwelle)


def master_zeile() -> str:
    """Die Zeile „Master: … · Lage …" für `status` und andere Anzeigen."""
    lage, grund = _lage(signale.alle_lesen())
    return anzeige.master_status_zeile(zustand.lesen(), lage, grund)


def _master() -> int:
    lage, grund = _lage(signale.alle_lesen())
    print(anzeige.master_menuezeile(zustand.lesen()))
    print("\n".join(anzeige.lage_zeilen(lage, grund)))
    return 0


def _wechsel(args: argparse.Namespace) -> int:
    erg = wechsel.wechseln(args.nach, args.hinweis)
    if erg.art == "fehler":
        print(f"Wechsel fehlgeschlagen: {erg.meldung}", file=sys.stderr)
        return 1
    if erg.art == "gleich":
        print(f"Standard-Master ist schon {anzeige.MASTER_NAMEN[erg.master]} – kein Wechsel, kein Paket.")
        return 0
    print(f"Standard-Master jetzt {anzeige.MASTER_NAMEN[erg.master]}. Geschützte Hermes-Themen bleiben unverändert.")
    print(f"Übergabepaket: {erg.paket}")
    return 0


def _paare_zeigen() -> int:
    liste = paare.lesen()
    if not liste:
        print("Keine Paare angelegt.")
        return 0
    for p in liste:
        print(f"{p.thema}  {'an' if p.aktiv else 'aus'}  {p.codex_thread}  {p.laufend}")
    return 0


def _modus_cli(args: argparse.Namespace) -> int:
    try:
        if args.modus is None:
            wert = modi.modus(args.thema)
            sicher = modi.geschuetzt(args.thema)
            print(f"{args.thema}: {wert}" + (" · geschützt durch Hermes-Besitz" if sicher and wert != modi.HERMES_CODEX else ""))
            return 0
        modi.setzen(args.thema, args.modus)
    except (modi.ModusFehler, OSError) as fehler:
        print(f"Arbeitsmodus nicht geändert: {fehler}", file=sys.stderr)
        return 1
    if args.modus == modi.HERMES_CODEX:
        print(f"{args.thema}: Hermes führt – Codex nur Ausführer. Keine Sitzung gestartet.")
    else:
        print(f"{args.thema}: Kontingentbetrieb – Übernahme offen.")
    return 0


# --- Rollenprofile, Ausführermodelle und Modellkataloge (v0.4.0) ---------------

STANDARD_SCHLUESSELWORT = "standard"


def _profil_cli(args: argparse.Namespace) -> int:
    """Rollenprofil eines Themas lesen – die verbindliche Abfrage vor jedem neuen Workerauftrag."""
    try:
        wert = modi.profil(args.thema)
        sicher = modi.geschuetzt(args.thema)
    except (modi.ModusFehler, OSError) as fehler:
        print(f"Profil nicht lesbar: {fehler}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"thema": args.thema, "master": wert.master, "worker": wert.worker,
                          "modell": wert.modell, "modell_standard": wert.modell is None,
                          "geschuetzt": sicher}, ensure_ascii=False))
        return 0
    stand = anzeige.Rollenstand(wert.master, wert.worker, wert.modell)
    print("\n".join(anzeige.rollen_zeilen(args.thema, stand, sicher)))
    return 0


def _master_setzen_cli(args: argparse.Namespace) -> int:
    if args.master not in modi.MASTER_WERTE:
        print(f"Master nicht gesetzt: unbekannte Masterrolle {args.master!r} "
              f"(erlaubt: {', '.join(modi.MASTER_WERTE)})", file=sys.stderr)
        return 1
    try:
        modi.master_setzen(args.thema, args.master)
    except (modi.ModusFehler, OSError) as fehler:
        print(f"Master nicht gesetzt: {fehler}", file=sys.stderr)
        return 1
    print(anzeige.master_meldung(args.thema, args.master))
    return 0


def _worker_setzen_cli(args: argparse.Namespace) -> int:
    if args.worker not in modi.WORKER_WERTE:
        print(f"Ausführer nicht gesetzt: unbekannter Provider {args.worker!r} "
              f"(erlaubt: {', '.join(modi.WORKER_WERTE)})", file=sys.stderr)
        return 1
    try:
        profil = modi.worker_setzen(args.thema, args.worker)
    except (modi.ModusFehler, OSError) as fehler:
        print(f"Ausführer nicht gesetzt: {fehler}", file=sys.stderr)
        return 1
    print(anzeige.ausfuehrer_meldung(args.thema, args.worker, profil.modell))
    return 0


def _modell_setzen_cli(args: argparse.Namespace) -> int:
    modell = None if args.modell == STANDARD_SCHLUESSELWORT else args.modell
    try:
        profil = modi.modell_setzen(args.thema, modell)
    except (modi.ModusFehler, OSError) as fehler:
        print(f"Modell nicht gesetzt: {fehler}", file=sys.stderr)
        return 1
    print(anzeige.modell_meldung(args.thema, profil.modell))
    return 0


def _katalogstand(katalog: modelle.Katalog) -> anzeige.Katalogstand:
    return anzeige.Katalogstand(katalog.provider, tuple((m.id, m.name) for m in katalog.modelle),
                                katalog.zeit.isoformat() if katalog.zeit else None,
                                katalog.fehler, katalog.veraltet)


def _katalog_json(katalog: modelle.Katalog) -> dict:
    return {"provider": katalog.provider,
            "modelle": [{"id": m.id, "name": m.name} for m in katalog.modelle],
            "zeit": katalog.zeit.isoformat() if katalog.zeit else None,
            "fehler": katalog.fehler, "veraltet": katalog.veraltet}


def _modelle_cli(args: argparse.Namespace) -> int:
    """Kataloge anzeigen oder frisch abgleichen; im Abgleichfall meldet ein Fehler Exit 1."""
    provider = args.provider
    if provider is not None and provider not in modelle.PROVIDER:
        print(f"Unbekannter Modellprovider: {provider!r} (bekannt: {', '.join(modelle.PROVIDER)})",
              file=sys.stderr)
        return 1
    try:
        if args.aktualisieren:
            if provider is None:
                ergebnis = modelle.alle_aktualisieren()
                kataloge = [ergebnis[name] for name in modelle.PROVIDER]
            else:
                kataloge = [modelle.aktualisieren(provider)]
        else:
            kataloge = [modelle.lesen(name) for name in ((provider,) if provider else modelle.PROVIDER)]
    except (modelle.KatalogFehler, OSError) as fehler:
        print(f"Modelle nicht gelesen: {fehler}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([_katalog_json(k) for k in kataloge], ensure_ascii=False))
    else:
        print("\n".join("\n".join(anzeige.katalog_ausgabe(_katalogstand(k))) for k in kataloge))
    if args.aktualisieren:
        gescheitert = [k for k in kataloge if k.fehler is not None or k.veraltet]
        for k in gescheitert:
            print(f"Modellkatalog nicht ermittelt: {anzeige.PROVIDER_NAMEN.get(k.provider, k.provider)}"
                  f" – {k.fehler or 'veraltet oder leer'}", file=sys.stderr)
        if gescheitert:
            return 1
    return 0


def _paar_setzen(args: argparse.Namespace) -> int:
    try:
        paar = paare.setzen(args.thema, args.uuid, args.datei,
                            aktiv=True if args.aktiv is None else args.aktiv)
    except paare.PaarFehler as fehler:
        print(f"Paar nicht gespeichert: {fehler}", file=sys.stderr)
        return 1
    print(f"Paar {paar.thema}: {'an' if paar.aktiv else 'aus'} · {paar.codex_thread} · {paar.laufend}")
    return 0


def _paar_aktiv(args: argparse.Namespace) -> int:
    try:
        paar = paare.aktiv_setzen(args.thema, args.zustand == "an")
    except paare.PaarFehler as fehler:
        print(f"Paar nicht geändert: {fehler}", file=sys.stderr)
        return 1
    print(f"Paar {paar.thema}: {'an' if paar.aktiv else 'aus'}")
    return 0


def _automatik_pruefen(args: argparse.Namespace) -> int:
    try:
        staende = automatik.lauf(trocken=args.trocken)
    except Exception as fehler:  # noqa: BLE001 - die Zeile darf nie abstürzen
        print(f"Automatikprüfung fehlgeschlagen: {fehler}", file=sys.stderr)
        return 1
    for stand in staende:
        print(f"{stand.thema}: {stand.status}" if stand.thema else stand.status)
    return 0


def _automatik_cli(args: argparse.Namespace) -> int:
    anzeige.automatik_setzen(args.zustand == "an")
    print(f"Automatik: {args.zustand}")
    return 0


def _rueckgabe_cli(args: argparse.Namespace) -> int:
    if not args.ja:
        try:
            staende = rueckgabe.rueckgabe(themen=args.themen or None, hinweis=args.hinweis,
                                          trocken=True, erneut=args.erneut)
        except rueckgabe.RueckgabeFehler as fehler:
            print(f"Rückgabe nicht möglich: {fehler}", file=sys.stderr)
            return 1
        for stand in staende:
            print(f"{stand.thema}: {stand.status}" if stand.thema else stand.status)
        print("Trockenlauf – nichts gesendet (mit --ja wird wirklich übergeben).")
        return 0
    erg = wechsel.wechseln("codex", args.hinweis)
    if erg.art == "fehler":
        print(f"Wechsel fehlgeschlagen: {erg.meldung}", file=sys.stderr)
        return 1
    if erg.art == "gewechselt":
        print(f"Standard-Master jetzt Codex. Geschützte Hermes-Themen bleiben unverändert. Technisches Übergabepaket: {erg.paket}")
    else:
        print("Standard-Master ist schon Codex – kein Wechsel, kein Paket.")
    try:
        staende = rueckgabe.rueckgabe(themen=args.themen or None, hinweis=args.hinweis,
                                      erneut=args.erneut)
    except rueckgabe.RueckgabeFehler as fehler:
        print(f"Rückgabe nicht möglich: {fehler}", file=sys.stderr)
        return 1
    for stand in staende:
        print(f"{stand.thema}: {stand.status}" if stand.thema else stand.status)
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="masterwechsel", description="Befehlszeile des Master-Schalters")
    p.add_argument("--version", action="version", version=f"master-schalter {__version__}")
    unter = p.add_subparsers(dest="befehl", required=True)
    unter.add_parser("status", help="beide Kontingente anzeigen")
    unter.add_parser("statuszeile", help="Statuszeilen-Befehl für Claude Code")
    hand = unter.add_parser("claude-kontingent", help="Claude-Werte von Hand eintragen")
    hand.add_argument("--fuenf", type=_prozent, required=True, help="5-Stunden-Verbrauch in Prozent")
    hand.add_argument("--woche", type=_prozent, required=True, help="Wochen-Verbrauch in Prozent")
    hand.add_argument("--reset-fuenf", type=_zeitpunkt, required=True, help="ISO-Zeitpunkt")
    hand.add_argument("--reset-woche", type=_zeitpunkt, required=True, help="ISO-Zeitpunkt")
    unter.add_parser("claude-messen", help="Claude-Kontingent über die OAuth-API messen")
    unter.add_parser("master", help="aktiven Master, Lage und Besetzung anzeigen")
    w = unter.add_parser("wechsel", help="Master wechseln und Übergabepaket schreiben")
    w.add_argument("nach", choices=zustand.MASTER, help="neuer Master")
    w.add_argument("--hinweis", default=None, help="Hinweis an den neuen Master (nur Technik, kein Chat-Rohtext)")
    unter.add_parser("paare", help="Paare aus Thema und Codex-Chat anzeigen")
    psetzen = unter.add_parser("paar-setzen", help="Paar anlegen oder überschreiben")
    psetzen.add_argument("thema", help="Thema (^[a-z0-9][a-z0-9-]{0,79}$)")
    psetzen.add_argument("uuid", help="Kennung (UUID) des Codex-Chats")
    psetzen.add_argument("datei", help="laufende Übergabe, exakt .hermes/uebergabe/laufend/<thema>.md")
    psetzen.add_argument("--aktiv", action=argparse.BooleanOptionalAction, default=None,
                         help="Paar sofort an- oder abschalten (Standard: an)")
    paktiv = unter.add_parser("paar-aktiv", help="Paar für die Automatik ein- oder ausschalten")
    paktiv.add_argument("thema", help="Thema")
    paktiv.add_argument("zustand", choices=("an", "aus"), help="an oder aus")
    modus_parser = unter.add_parser("modus", help="Arbeitsmodus eines Themas anzeigen oder setzen")
    modus_parser.add_argument("thema", help="vorhandenes Thema")
    modus_parser.add_argument("modus", nargs="?", help="kontingent oder hermes-codex")
    profil_parser = unter.add_parser("profil", help="Rollenprofil eines Themas anzeigen (Master, Ausführer, Modell)")
    profil_parser.add_argument("thema", help="vorhandenes Thema")
    profil_parser.add_argument("--json", action="store_true", help="maschinenlesbare Ausgabe")
    master_setzen = unter.add_parser("master-setzen", help="Masterrolle eines Themas setzen")
    master_setzen.add_argument("thema", help="vorhandenes Thema")
    master_setzen.add_argument("master", help="kontingent, claude, codex oder hermes")
    worker_setzen = unter.add_parser("worker-setzen", help="Ausführervorgabe eines Themas setzen")
    worker_setzen.add_argument("thema", help="vorhandenes Thema")
    worker_setzen.add_argument("worker", help="workflow, claude, codex oder hermes")
    modell_setzen = unter.add_parser("modell-setzen", help="Ausführermodell eines Themas setzen")
    modell_setzen.add_argument("thema", help="vorhandenes Thema")
    modell_setzen.add_argument("modell", help="Modellkennung aus dem Katalog oder \"standard\"")
    modelle_parser = unter.add_parser("modelle", help="Modellkataloge der Werkzeuge anzeigen oder abgleichen")
    modelle_parser.add_argument("provider", nargs="?", help="claude oder codex (Standard: beide)")
    modelle_parser.add_argument("--aktualisieren", action="store_true",
                                help="Kataloge frisch abgleichen (Kindprozess der Werkzeuge, keine Inferenz)")
    modelle_parser.add_argument("--json", action="store_true", help="maschinenlesbare Ausgabe")
    pruefen = unter.add_parser("automatik-pruefen", help="Automatik Claude → Codex prüfen")
    pruefen.add_argument("--trocken", action="store_true", help="nur zeigen, nichts senden")
    auto = unter.add_parser("automatik", help="Automatik Claude → Codex ein- oder ausschalten")
    auto.add_argument("zustand", choices=("an", "aus"), help="an oder aus")
    rueck = unter.add_parser("rueckgabe", help="Themen an Codex zurückgeben (ohne --ja nur Trockenlauf)")
    rueck.add_argument("themen", nargs="*", help="Themen (Standard: alle aktiven)")
    rueck.add_argument("--ja", action="store_true", help="wirklich wechseln und die Übergaben senden")
    rueck.add_argument("--erneut", action="store_true", help="auch senden, wenn bereits übergeben")
    rueck.add_argument("--hinweis", default=None, help="kurzer Zusatz für die Übergabenachricht")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as ende:
        if ende.code not in (0, None):
            return 2
        raise
    if args.befehl == "statuszeile":
        return _statuszeile()
    if args.befehl == "claude-kontingent":
        return _claude_kontingent(args)
    if args.befehl == "claude-messen":
        return _claude_messen()
    if args.befehl == "master":
        return _master()
    if args.befehl == "wechsel":
        return _wechsel(args)
    if args.befehl == "paare":
        return _paare_zeigen()
    if args.befehl == "paar-setzen":
        return _paar_setzen(args)
    if args.befehl == "paar-aktiv":
        return _paar_aktiv(args)
    if args.befehl == "modus":
        return _modus_cli(args)
    if args.befehl == "profil":
        return _profil_cli(args)
    if args.befehl == "master-setzen":
        return _master_setzen_cli(args)
    if args.befehl == "worker-setzen":
        return _worker_setzen_cli(args)
    if args.befehl == "modell-setzen":
        return _modell_setzen_cli(args)
    if args.befehl == "modelle":
        return _modelle_cli(args)
    if args.befehl == "automatik-pruefen":
        return _automatik_pruefen(args)
    if args.befehl == "automatik":
        return _automatik_cli(args)
    if args.befehl == "rueckgabe":
        return _rueckgabe_cli(args)
    if args.befehl == "status":
        print(master_zeile())
    print("\n".join(anzeige.details(signale.alle_lesen())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
