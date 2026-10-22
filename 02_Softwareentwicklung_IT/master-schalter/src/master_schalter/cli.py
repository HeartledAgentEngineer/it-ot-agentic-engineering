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
    masterwechsel quittieren VORGANG neu|abgabe
                                      Übernahme (neu) bzw. Abgabe (abgabe) eines Assistentenvorgangs bestätigen
    masterwechsel uebergeben THEMA ZIEL [--von WERKZEUG:KENNUNG] [--nach WERKZEUG:KENNUNG]
                                      Wechselassistent: Thema vom alten an den neuen Master übergeben
    masterwechsel fortsetzen [VORGANG]
                                      Wechselvorgänge weiterführen (Frist, Rolle setzen, zustellen)
    masterwechsel chats [--liste]     zuletzt benutzte Chats (24 h): ohne --liste nur Zählwerte und Quellenstatus

Fehler werden mit Exit 1 und einer klaren Diagnose gemeldet – ohne rohe Antworten der Werkzeuge.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import (__version__, anzeige, assistent, assistent_vorgaenge, automatik, chat_register, chat_zuordnung, claude_messen,
               modi, modelle, paare, rollen, rueckgabe, signale, wechsel, zustand)


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


def _quittieren_cli(args: argparse.Namespace) -> int:
    """Quittung eines Zielchats (`neu`) bzw. des alten Chats (`abgabe`) – nur bei gültiger Marke."""
    try:
        vorgang = assistent_vorgaenge.quittieren(args.vorgang, args.art)
    except assistent_vorgaenge.AssistentFehler as fehler:   # Texte ohne Eingabe-Echo und ohne Pfade
        print(f"Nicht quittiert: {fehler}", file=sys.stderr)
        return 1
    except OSError as fehler:
        print(f"Nicht quittiert: Datei nicht lesbar ({type(fehler).__name__})", file=sys.stderr)
        return 1
    if args.art == "neu":
        print(f"Übernahme von {vorgang.thema} quittiert (Vorgang {vorgang.id}).")
    else:
        print(f"Abgabe von {vorgang.thema} quittiert (Vorgang {vorgang.id}).")
    return 0


def _chat_ref(text: str | None) -> assistent.ChatRef | None:
    """`WERKZEUG:KENNUNG` → Chat-Referenz. Die Fehlermeldungen nennen die Eingabe nie (sie enthält die Kennung)."""
    if text is None:
        return None
    werkzeug, trenner, kennung = text.partition(":")
    if not trenner:
        raise assistent_vorgaenge.AssistentFehler("Chat-Angabe muss WERKZEUG:KENNUNG lauten")
    return assistent.ChatRef(werkzeug, kennung)


def _uebergeben_cli(args: argparse.Namespace) -> int:
    """Wechsel starten. Ausgabe nur Vorgangs-ID und Phase – nie eine Chat-Kennung."""
    try:
        vorgang = assistent.uebergeben(args.thema, args.ziel, von_chat=_chat_ref(args.von),
                                       nach_chat=_chat_ref(args.nach))
    except assistent_vorgaenge.AssistentFehler as fehler:   # Texte sind bereinigt (assistent._assistentfehler)
        print(f"Nicht übergeben: {fehler}", file=sys.stderr)
        return 1
    except OSError as fehler:                                # Rohtext kann Pfade enthalten: nur die Klasse
        print(f"Nicht übergeben: Datei nicht lesbar ({type(fehler).__name__})", file=sys.stderr)
        return 1
    print(f"Vorgang {vorgang.id}: {vorgang.phase}")
    return 0


def _fortsetzen_cli(args: argparse.Namespace) -> int:
    """Einen oder alle nicht endgültigen Vorgänge weiterführen; je Vorgang ID, Thema und Phase."""
    if args.vorgang is not None:
        ids = [args.vorgang]
    else:
        try:
            ids = [v.id for v in assistent_vorgaenge.lesen() if v.phase not in assistent_vorgaenge.ENDGUELTIG]
        except OSError as fehler:
            print(f"Vorgänge nicht lesbar ({type(fehler).__name__})", file=sys.stderr)
            return 1
    fehlgeschlagen = False
    for ident in ids:
        # Die ID nur nennen, wenn sie dem Muster entspricht – eine ungeprüfte Eingabe nie wiederholen (R6/1).
        gezeigt = ident if modi.VORGANG_ID_MUSTER.fullmatch(ident) else "ungültige Kennung"
        try:
            vorgang = assistent.fortsetzen(ident)
        except assistent_vorgaenge.AssistentFehler as fehler:
            print(f"Nicht fortgesetzt ({gezeigt}): {fehler}", file=sys.stderr)
            fehlgeschlagen = True
            continue
        except OSError as fehler:
            print(f"Nicht fortgesetzt ({gezeigt}): Datei nicht lesbar ({type(fehler).__name__})", file=sys.stderr)
            fehlgeschlagen = True
            continue
        print(f"{vorgang.id}  {vorgang.thema}  {vorgang.phase}")
    return 1 if fehlgeschlagen else 0


def _chats_cli(args: argparse.Namespace) -> int:
    """Chatliste (nur Metadaten, nur lesend). Ohne `--liste` nur Zählwerte: keine Titel, Ordner, Kennungen."""
    ergebnis, zeilen = chat_zuordnung.uebersicht_mit_quellen()
    for quelle in chat_register.QUELLEN:
        status = ergebnis.quellen.get(quelle, "fehlt")
        anzahl = sum(1 for chat in ergebnis.chats if chat.quelle == quelle)
        print(f"{quelle}: {status}, {anzahl} {'Chat' if anzahl == 1 else 'Chats'}" if status == "ok"
              else f"{quelle}: {status}")
    zugeordnet = sum(1 for _, thema, _ in zeilen if thema is not None)
    print(f"zugeordnet: {zugeordnet}, ohne Projekt: {len(zeilen) - zugeordnet}")
    if args.liste:
        for chat, thema, grund in zeilen:
            zeit = chat.zuletzt.astimezone().strftime("%Y-%m-%d %H:%M")
            print(f"{chat.werkzeug}  {chat.kennung[:8]}  {zeit}  {thema or '-'} ({grund})  {chat.titel}")
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
    quittieren = unter.add_parser("quittieren", help="Übernahme oder Abgabe eines Wechselvorgangs bestätigen")
    quittieren.add_argument("vorgang", help="Vorgangskennung aus der Postfachnachricht")
    quittieren.add_argument("art", metavar="ART", help="neu (Übernahme) oder abgabe")   # ohne choices: kein Echo
    uebergeben = unter.add_parser("uebergeben", help="Wechselassistent: Thema an einen neuen Master übergeben")
    uebergeben.add_argument("thema", help="vorhandenes Thema")
    # Ohne `choices`: argparse würde eine ungültige Eingabe wörtlich wiederholen (R7/1); `assistent.uebergeben`
    # prüft die Zielrolle selbst und nennt nur die erlaubten Werte.
    uebergeben.add_argument("ziel", metavar="ZIEL", help=f"neue Masterrolle ({'|'.join(modi.ZIEL_ROLLEN)})")
    uebergeben.add_argument("--von", default=None, metavar="WERKZEUG:KENNUNG",
                            help="alter Chat (ohne Angabe wird die Abgabe übersprungen)")
    uebergeben.add_argument("--nach", default=None, metavar="WERKZEUG:KENNUNG",
                            help="neuer Chat (ohne Angabe wird nur die Rolle gesetzt)")
    fortsetzen = unter.add_parser("fortsetzen", help="Wechselvorgänge weiterführen (idempotent)")
    fortsetzen.add_argument("vorgang", nargs="?", default=None,
                            help="Vorgangskennung (Standard: alle nicht endgültigen Vorgänge)")
    chats = unter.add_parser("chats", help="zuletzt benutzte Chats (24 h) und ihre Projekt-Vorschläge")
    chats.add_argument("--liste", action="store_true",
                       help="nur für Sebastian; zeigt persönliche Titel (Kennungen gekürzt, Vorschlag und Grund)")
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
    if args.befehl == "chats":
        return _chats_cli(args)
    if args.befehl == "quittieren":
        return _quittieren_cli(args)
    if args.befehl == "uebergeben":
        return _uebergeben_cli(args)
    if args.befehl == "fortsetzen":
        return _fortsetzen_cli(args)
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
