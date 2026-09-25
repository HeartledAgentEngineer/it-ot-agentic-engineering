"""Memory service – Erinnerungen speichern, korrigieren, auswaehlen.

Was seit dem 25.09.2026 gilt (Entscheidungen Sebastian, belegt in
`docs/konzept-gedaechtnis.md`, Abschnitt „Entschieden 25.09.2026"):

1. **Einbettungen ueber OpenRouter** (`openrouter_vektor`). Der lokale Weg
   (sentence-transformers) ist entfallen - er ist auf keinem der beiden
   Geraete installiert -, Mistral ebenfalls.
2. **Eine Korrektur ersetzt die alte Fassung.** Der neue Text wird aktiv,
   der alte wandert in das Feld ``history`` des Eintrags. Geloescht wird
   dabei NIE etwas.
3. **Sanftes Vergessen:** alte Eintraege treten in der Rangfolge zurueck
   (kleiner Abzug ab 90 Tagen), verschwinden aber nicht.
4. **Relevanz statt Vollbestand:** es wandern nur ``top_k`` Eintraege in den
   Prompt (frueher: der ganze Bestand bis 300 Eintraege, ``top_k`` war
   wirkungslos), zusaetzlich begrenzt `llm_service` den Block hart.
5. **Zeitbezug:** jeder Eintrag hat eine Art (``fakt``, ``termin``,
   ``zustand``). Ein naher Termin wird bevorzugt, ein vergangener Termin gilt
   nicht mehr als „aktuell", bleibt aber auffindbar (Suche/„erklaeren").
"""

import difflib
import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np

from app.config import settings
from app.db.chroma_client import chroma_client
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


# ── Wiederholungen, Korrekturen ────────────────────────────────────────
#
# Ohne eine solche Pruefung legte jedes Gespraech dieselben Fakten neu an:
# "Name: Sebastian" stand funfmal im Speicher. Jede Wiederholung kostet einen
# der wenigen Plaetze, die in den Prompt wandern.
#
# Die frueher allein gueltige Regel „aehnlich genug = Wiederholung" hatte
# einen belegten Fehler: sie verwarf auch KORREKTUREN. Gemessen mit der
# Funktion aus diesem Modul (25.09.2026):
#   „… seit zehn Jahren …"  vs. „… seit elf Jahren …"   -> 0,950
#   „… Hund namens Rex."     vs. „… namens Max."         -> 0,933
#   „Geburtstag: 3. Mai 1984" vs. „5. Mai 1985"          -> 0,905
# Alle drei galten als „derselbe Fakt" - die richtige Fassung wurde
# verworfen, die falsche blieb stehen. Jetzt wird unterschieden:
#
#   echte Doppelung  -> nichts wird angelegt (wie bisher)
#   Korrektur        -> neue Fassung wird aktiv, alte wandert in `history`
#
# Unterschieden wird an den WORTEN, die sich unterscheiden: nur Fuellwoerter
# verschieden = Wiederholung; ein tragendes Wort (Name, Zahl, Datum) anders =
# Korrektur. Damit das ohne Bedeutungsmodell funktioniert, braucht es keine
# Einbettung - und auf dem Handy gibt es keine.
AEHNLICHKEIT_SCHWELLE = 0.90

# Woerter, deren Austausch nichts an der Aussage aendert. Alles andere gilt
# als tragend. Bewusst grosszuegig: Ein Fehlurteil „Korrektur" kostet nur
# einen Verlaufseintrag, ein Fehlurteil „Doppelung" kostet die Korrektur.
FUELLWOERTER = {
    "aber", "alle", "allem", "allen", "aller", "alles", "also", "am", "an",
    "auch", "auf", "aus", "bei", "beim", "bereits", "bin", "bist", "circa",
    "ca", "da", "dabei", "damit", "dann", "das", "dass", "davon", "dazu",
    "dein", "deine", "dem", "den", "denn", "der", "des", "die", "dies",
    "diese", "diesem", "diesen", "dieser", "doch", "dort", "du", "durch",
    "egal", "ein", "eine", "einem", "einen", "einer", "eines", "er", "es",
    "etwa", "etwas", "euer", "eure", "fuer", "für", "gegen", "gerade",
    "gerne", "gern", "gewesen", "habe", "haben", "hat", "hatte", "hier",
    "ich", "ihr", "ihre", "im", "immer", "in", "ist", "ja", "jede", "jedem",
    "jeden", "jeder", "jedes", "kein", "keine", "keinem", "keinen", "mal",
    "manchmal", "mein", "meine", "meist", "meistens", "mit", "muss", "nach",
    "nicht", "nichts", "noch", "nun", "nur", "ob", "oder", "oft", "ohne",
    "rund", "schon", "sehr", "sein", "seine", "seit", "sich", "sie", "sind",
    "so", "soll", "ueber", "über", "um", "und", "uns", "unser", "unter",
    "vom", "von", "vor", "war", "waren", "was", "wenn", "wer", "wie",
    "wieder", "wir", "wird", "wo", "zu", "zum", "zur",
}

# ── Auswahl fuer den Prompt ────────────────────────────────────────────
#
# Frueher galt ALLES_MITGEBEN_BIS = 300: bis 300 Eintraege wanderte der
# KOMPLETTE Bestand in jede Frage (bei den 175 Eintraegen des Handys rund
# 11.000 Zeichen ≈ 2.500 Token), top_k war wirkungslos. Jetzt wird immer
# ausgewaehlt - ueber Bedeutung, wenn Vektoren da sind, sonst ueber
# Wortgleichheit, und nie mehr ueber den ganzen Bestand.
MEMORY_TOP_K = 8

# Zuschlaege in der Rangfolge (0..1 wie die Kosinus-Aehnlichkeit).
TERMIN_BONUS_NAH = 0.30      # Termin heute bis in 14 Tagen
TERMIN_BONUS_MITTEL = 0.15   # Termin in 15 bis 60 Tagen
TERMIN_BONUS_FERN = 0.05     # Termin spaeter (und wiederkehrende Termine)
IMPORTANCE_GEWICHT = 0.05    # je Stufe ueber 3 - `importance` wird damit gelesen

# Sanftes Vergessen: ab 90 Tagen Alter ein kleiner Abzug, gedeckelt.
ALTER_FREI_TAGE = 90
ALTER_ABZUG_MAX = 0.10

ARTEN = ("fakt", "termin", "zustand")

# Alte Werte werden auf die neue Art abgebildet (Migration, Anzeige).
ART_ALIASE = {
    "fact": "fakt",
    "fakt": "fakt",
    "preference": "zustand",
    "context": "zustand",
    "project": "zustand",
    "detail": "zustand",
    "zustand": "zustand",
    "ereignis": "termin",
    "termin": "termin",
}

ART_TEXTE = {"fakt": "Fakt", "termin": "Termin", "zustand": "Zustand"}

# Was eine Aussage veraenderlich macht („die sich immer aktualisieren").
ZUSTANDS_WOERTER = (
    "aktuell", "derzeit", "momentan", "zurzeit", "mag ", "magst", "mochte",
    "moechte", "liebling", "bevorzugt", "bevorzugte", "arbeitet an",
    "arbeitet gerade", "beschaeftigt sich", "beschäftigt sich", "plant",
    "vorhaben", "hat vor", "lernt gerade", "testet gerade", "probiert",
    "spielt gerade", "projekt", "naechstes ziel", "nächstes ziel",
)

# Wiederkehrende Ereignisse: kein einmaliger Termin, sondern ein Datum, das
# jedes Jahr wiederkommt (Geburtstag). Ohne eigenes Feld waere es ein
# Termin, der nach dem Tag fuer immer „vergangen" waere.
WIEDERKEHR_WOERTER = (
    "geburtstag", "geburtstags", "geburtsdatum", "jedes jahr", "jaehrlich",
    "jährlich", "alljaehrlich", "alljährlich", "wiederkehrend",
)

# Fragen, die auf die Vergangenheit zielen: Dann duerfen vergangene Termine
# mit in den Prompt (als Historie), sonst nicht („nicht mehr aktuell").
VERGANGENHEITS_WOERTER = {
    "war", "waren", "gewesen", "damals", "frueher", "früher", "ehemals",
    "vergangen", "vergangene", "vergangenen", "historie", "erinnerst",
    "erinnerung", "erinnern", "jemals", "letzte", "letzten", "letztes",
    "vorher", "zuvor", "gestern", "letzthin", "alter",
}

_MUSTER_JAHR = re.compile(r"\b(19|20)\d{2}\b")
_MUSTER_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_MUSTER_TAG_MONAT_JAHR = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b")

_MONATE = {
    "januar": 1, "februar": 2, "maerz": 3, "märz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12, "jan": 1, "feb": 2, "mrz": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "okt": 10, "nov": 11,
    "dez": 12,
}
# Monatsnamen als Regex: laengste zuerst, sonst faengt "jan" das "januar".
# Der Monat MUSS eine Gruppe sein - sonst steht der Name nicht im Treffer.
_MONATSNAMEN = "|".join(sorted(_MONATE, key=len, reverse=True))
_MUSTER_TAG_MONATSNAME = re.compile(
    r"\b(\d{1,2})\.\s*(" + _MONATSNAMEN + r")\.?\s*(\d{4})?\b",
    re.IGNORECASE,
)


# ── Einbettung ─────────────────────────────────────────────────────────

def openrouter_vektor(text: str) -> Optional[List[float]]:
    """Bettet einen Text ueber OpenRouter ein (normiert zurueck).

    Entscheidung Sebastians vom 25.09.2026: Einbettungen laufen ueber
    OpenRouter - OpenAI-kompatibler Endpunkt, Preis des Standardmodells
    rund 0,02 $/1 Mio Token. Der Text verlaesst dabei das Geraet (das ist
    der bewusste Teil der Entscheidung, Mistral entfaellt dafuer).

    Der lokale Weg (sentence-transformers) ist entfallen: Auf keinem der
    beiden Geraete installiert, und torch auf ARM-Android ist der Kampf, den
    dieses Projekt schon einmal verloren hat - siehe
    `docs/embeddings-auf-termux.md`.

    Ohne Schluessel oder bei Netzfehler kommt ``None`` zurueck. Der Aufrufer
    muss damit umgehen koennen; ein Eintrag ohne Vektor ist gueltig.
    """
    schluessel = (settings.openrouter_api_key or "").strip()
    if not schluessel or not (text or "").strip():
        return None
    try:
        antwort = httpx.post(
            f"{settings.openrouter_base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {schluessel}"},
            json={"model": settings.openrouter_embed_model, "input": [text]},
            timeout=20,
        )
        antwort.raise_for_status()
        vek = np.asarray(antwort.json()["data"][0]["embedding"], dtype=np.float32)
        norm = float(np.linalg.norm(vek))
        if not norm:
            return None
        # Normiert speichern: Dann genuegt beim Suchen das Skalarprodukt.
        return (vek / norm).tolist()
    except Exception as e:
        logger.warning("Einbettung ueber OpenRouter fehlgeschlagen: %s", e)
        return None


# ── Textvergleich ──────────────────────────────────────────────────────

def _normalisiert(text: str) -> str:
    """Kleinschreibung, ohne Satzzeichen, ohne doppelte Leerzeichen."""
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> List[str]:
    """Wortliste eines normalisierten Textes."""
    return _normalisiert(text).split()


def _tragende_unterschiede(a_norm: str, b_norm: str) -> List[str]:
    """Die Woerter, in denen sich zwei Texte inhaltlich unterscheiden.

    Getauschte Fuellwoerter zaehlen nicht ("auch Kaffee" statt "Kaffee" ist
    dieselbe Aussage). Alles andere zaehlt: Namen, Zahlen, Daten, Orte.
    """
    a, b = a_norm.split(), b_norm.split()
    if not a or not b:
        return []
    unterschiede: List[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        for wort in a[i1:i2] + b[j1:j2]:
            if wort.isdigit():
                unterschiede.append(wort)
            elif len(wort) >= 2 and wort not in FUELLWOERTER:
                unterschiede.append(wort)
    return unterschiede


def _ist_doppelung(a: str, b: str) -> bool:
    """Dieselbe Aussage, nur wiederholt (kein Widerspruch)?"""
    na, nb = _normalisiert(a), _normalisiert(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if difflib.SequenceMatcher(None, na, nb).ratio() < AEHNLICHKEIT_SCHWELLE:
        return False
    return not _tragende_unterschiede(na, nb)


def _ist_korrektur(a: str, b: str) -> bool:
    """Widerspricht ``b`` dem ``a`` zum selben Gegenstand?

    Nur dann, wenn die beiden Texte ueberhaupt als dieselbe Sache durchgehen
    (Schwelle) UND sich in einem tragenden Wort unterscheiden. Eine ganz
    andere Formulierung derselben Sache bleibt ein eigener Eintrag - dafuer
    braeuchte es Bedeutung, nicht Zeichenvergleich.
    """
    na, nb = _normalisiert(a), _normalisiert(b)
    if not na or not nb or na == nb:
        return False
    if difflib.SequenceMatcher(None, na, nb).ratio() < AEHNLICHKEIT_SCHWELLE:
        return False
    return bool(_tragende_unterschiede(na, nb))


# ── Zeitbezug ──────────────────────────────────────────────────────────

def _datum(jahr: int, monat: int, tag: int) -> Optional[date]:
    try:
        return date(jahr, monat, tag)
    except ValueError:
        return None


def _erkenne_datum(text: str, heute: Optional[date] = None) -> Optional[str]:
    """Datum aus dem Text als ISO-String, sonst ``None``.

    Erkannt werden bewusst nur drei Formen, damit nichts erfunden wird:
    ``2026-11-02``, ``02.11.2026`` (auch ``2.11.26``) und ``2. November 2026``.
    Fehlt die Jahreszahl („am 2. November"), gilt das NAECHSTE Vorkommen:
    Liegt der Tag in diesem Jahr schon hinter uns, ist das naechste gemeint.
    """
    heute = heute or date.today()
    text = text or ""

    treffer = _MUSTER_ISO.search(text)
    if treffer:
        tag = _datum(int(treffer.group(1)), int(treffer.group(2)), int(treffer.group(3)))
        if tag:
            return tag.isoformat()

    treffer = _MUSTER_TAG_MONAT_JAHR.search(text)
    if treffer:
        jahr = int(treffer.group(3))
        if jahr < 100:
            jahr += 2000 if jahr < 70 else 1900
        tag = _datum(jahr, int(treffer.group(2)), int(treffer.group(1)))
        if tag:
            return tag.isoformat()

    treffer = _MUSTER_TAG_MONATSNAME.search(text)
    if treffer:
        monat = _MONATE.get(treffer.group(2).lower().rstrip("."))
        if monat:
            jahr = int(treffer.group(3)) if treffer.group(3) else heute.year
            tag = _datum(jahr, monat, int(treffer.group(1)))
            if tag and not treffer.group(3) and tag < heute:
                # „2. November" im Dezember gesagt = naechstes Jahr.
                tag = _datum(jahr + 1, monat, int(treffer.group(1)))
            if tag:
                return tag.isoformat()
    return None


def _lage(datum_iso: Optional[str], heute: Optional[date] = None) -> Tuple[str, Optional[int]]:
    """``("vergangen"|"heute"|"kommend", Tage bis dahin)`` - oder ``("", None)``."""
    if not datum_iso:
        return "", None
    heute = heute or date.today()
    try:
        tag = date.fromisoformat(datum_iso)
    except (TypeError, ValueError):
        return "", None
    tage = (tag - heute).days
    if tage < 0:
        return "vergangen", tage
    if tage == 0:
        return "heute", 0
    return "kommend", tage


def erkenne_art(content: str, heute: Optional[date] = None) -> Dict[str, Any]:
    """Art eines Eintrags aus seinem Wortlaut ableiten.

    Reihenfolge (erste passende Regel gewinnt):
      1. wiederkehrendes Datum („Geburtstag") -> ``termin``, ohne Enddatum
      2. Datum im Text                        -> ``termin`` mit ``ereignis_datum``
      3. veraenderliche Formulierung           -> ``zustand``
      4. sonst                                 -> ``fakt``

    Das ist absichtlich eine feste Regel und kein Modellaufruf: Es muss bei
    jedem Speichern laufen (auch auf dem Handy), und ein Fehlurteil ist
    billig - die Art steuert nur die Reihenfolge, nichts wird geloescht.
    """
    heute = heute or date.today()
    text = _normalisiert(content)

    if any(w in text for w in WIEDERKEHR_WOERTER):
        return {"art": "termin", "ereignis_datum": None, "wiederkehrend": True, "wichtig": 4}

    datum = _erkenne_datum(content, heute)
    if datum:
        return {"art": "termin", "ereignis_datum": datum, "wiederkehrend": False, "wichtig": 4}

    if any(w in text for w in ZUSTANDS_WOERTER):
        return {"art": "zustand", "ereignis_datum": None, "wiederkehrend": False, "wichtig": 3}

    return {"art": "fakt", "ereignis_datum": None, "wiederkehrend": False, "wichtig": 3}


def normalisiere_art(wert: Optional[str]) -> str:
    """Alten oder neuen Kategoriewert auf eine der drei Arten abbilden."""
    return ART_ALIASE.get((wert or "").strip().lower(), "fakt")


def art_aus_angabe(wert: Optional[str]) -> Optional[str]:
    """Art aus einer ausdruecklichen Angabe - ``None`` heisst „keine Angabe".

    ``"fact"`` war der alte feste Wert und bedeutet inhaltlich nichts; er
    zaehlt deshalb NICHT als Vorgabe, sondern wird aus dem Text erkannt.
    """
    if not wert:
        return None
    art = ART_ALIASE.get(str(wert).strip().lower())
    return art if art in ARTEN else None


def _wirksame_art(
    eintrag: Dict[str, Any], heute: Optional[date] = None
) -> Tuple[str, Optional[str], bool]:
    """Art, Datum und Wiederkehr eines Eintrags - auch fuer Alteintraege.

    Alte Eintraege tragen ``category: "fact"``. Wuerde man sie einfach als
    ``fakt`` lesen, verhielte sich ein alter Zahnarzttermin anders als ein
    neuer. Deshalb wird bei ihnen die Art einmal aus dem Inhalt abgeleitet.
    """
    roh = (eintrag.get("category") or "").strip().lower()
    if roh in ARTEN:
        datum = eintrag.get("ereignis_datum")
        wiederkehrend = bool(eintrag.get("wiederkehrend"))
        if roh == "termin" and not datum and not wiederkehrend:
            erkannt = erkenne_art(eintrag.get("content", ""), heute)
            datum = erkannt.get("ereignis_datum")
            wiederkehrend = bool(erkannt.get("wiederkehrend"))
        return roh, datum, wiederkehrend
    erkannt = erkenne_art(eintrag.get("content", ""), heute)
    return erkannt["art"], erkannt.get("ereignis_datum"), bool(erkannt.get("wiederkehrend"))


def _termin_wert(
    art: str, datum_iso: Optional[str], wiederkehrend: bool, heute: Optional[date] = None
) -> Tuple[float, str]:
    """Zuschlag und Lage eines Termins fuer die Rangfolge.

    „Soll auftauchen, wenn es naeher kommt": je naeher, desto mehr. Ein
    vergangener Termin bekommt keinen Zuschlag und meldet die Lage
    ``vergangen`` - der Aufrufer laesst ihn dann aus dem Prompt heraus.
    """
    if art != "termin":
        return 0.0, ""
    if wiederkehrend:
        return TERMIN_BONUS_FERN, "wiederkehrend"
    if not datum_iso:
        return 0.0, ""
    lage, tage = _lage(datum_iso, heute)
    if lage == "vergangen":
        return 0.0, "vergangen"
    if lage == "heute":
        return TERMIN_BONUS_NAH, "heute"
    if tage is not None and tage <= 14:
        return TERMIN_BONUS_NAH, "kommend"
    if tage is not None and tage <= 60:
        return TERMIN_BONUS_MITTEL, "kommend"
    return TERMIN_BONUS_FERN, "kommend"


def _alter_tage(timestamp: Optional[str], heute: Optional[date] = None) -> Optional[int]:
    """Alter eines Eintrags in Tagen, ``None`` wenn der Zeitstempel fehlt."""
    if not timestamp:
        return None
    heute = heute or date.today()
    try:
        wann = datetime.fromisoformat(str(timestamp))
    except ValueError:
        return None
    if wann.tzinfo is None:
        wann = wann.replace(tzinfo=timezone.utc)
    return (heute - wann.date()).days


def _alter_abzug(timestamp: Optional[str], heute: Optional[date] = None) -> float:
    """Sanftes Vergessen: kleiner Abzug fuer alte Eintraege (nie ein Ausschluss).

    Ab ``ALTER_FREI_TAGE`` Tagen je angefangene 30 Tage 0,01 - hoechstens
    0,10. Das verschiebt die Reihenfolge, es entfernt nichts: Ein alter,
    thematisch passender Eintrag bleibt vorn, ein alter unpassender faellt
    hinter einen frischen.
    """
    tage = _alter_tage(timestamp, heute)
    if tage is None or tage <= ALTER_FREI_TAGE:
        return 0.0
    stufen = int((tage - ALTER_FREI_TAGE) // 30) + 1
    return -min(ALTER_ABZUG_MAX, 0.01 * stufen)


def _fragt_nach_vergangenheit(query: str) -> bool:
    """Zielt die Frage auf die Vergangenheit (dann Historie mitliefern)?"""
    text = _normalisiert(query)
    if not text:
        return False
    if _MUSTER_JAHR.search(text):
        return True
    return any(w in VERGANGENHEITS_WOERTER for w in text.split())


def _wort_score(query: str, text: str) -> float:
    """Anteil der Fragewoerter, die im Text vorkommen (0..1).

    Wortgleichheit, keine Bedeutung - und ohne Wortstamm: „Zahnarzt" findet
    „Zahnarzttermin" nicht. Genau deshalb ist das nur der Ersatzweg, wenn
    keine Vektoren da sind.
    """
    frage = {
        t for t in _tokens(query)
        if t.isdigit() or (len(t) >= 2 and t not in FUELLWOERTER)
    }
    if not frage:
        return 0.0
    im_text = set(_tokens(text))
    if not im_text:
        return 0.0
    return len(frage & im_text) / len(frage)


def _passt(content: str, begriff: str) -> bool:
    """Trifft der Suchbegriff den Text? (Wortlaut, keine Bedeutung)"""
    text = _normalisiert(content)
    suche = _normalisiert(begriff)
    if not text or not suche:
        return False
    if suche in text:
        return True
    teile = [t for t in suche.split() if t.isdigit() or len(t) >= 2]
    return bool(teile) and all(t in text.split() for t in teile)


class MemoryService:
    """Orchestrates memory operations: storage, retrieval, extraction."""

    # ── store ──────────────────────────────────────────────────────

    def store_memory(
        self,
        content: str,
        category: Optional[str] = None,
        importance: Optional[int] = None,
        conversation_id: Optional[str] = None,
        heute: Optional[date] = None,
    ) -> str:
        """Speichert eine Erinnerung - neu, als Korrektur, oder gar nicht.

        Rueckgabe ist immer eine gueltige ID:

        * neue Erinnerung -> neue ID
        * echte Doppelung -> ID des vorhandenen Eintrags (nichts angelegt)
        * Korrektur       -> ID des abgeloesten Eintrags; die neue Fassung ist
          aktiv, die alte steht in dessen ``history`` (nichts geloescht)

        ``category`` ist optional: Ohne Angabe (bzw. mit dem alten Wert
        ``"fact"``) wird die Art aus dem Text erkannt (`erkenne_art`).
        """
        content = (content or "").strip()
        if not content:
            return ""

        heute = heute or date.today()
        erkannt = erkenne_art(content, heute)
        art = art_aus_angabe(category) or erkannt["art"]
        datum = erkannt.get("ereignis_datum") if art == "termin" else None
        wiederkehrend = bool(erkannt.get("wiederkehrend")) if art == "termin" else False
        if importance is None:
            importance = erkannt.get("wichtig", 3) if art == erkannt["art"] else 3
        wichtig_int = int(importance) if importance else 3

        kandidat = self._naechster_verwandter(content)
        if kandidat is not None:
            if _ist_korrektur(kandidat.get("content", ""), content):
                return self._loese_ab(
                    kandidat, content, art, datum, wiederkehrend, wichtig_int,
                    conversation_id,
                )
            logger.info("Bereits bekannt (Doppelung), nichts angelegt: %s", content[:80])
            return kandidat.get("id") or ""

        memory_id = chroma_client.add_memory(
            content=content,
            embedding=openrouter_vektor(content),
            category=art,
            importance=wichtig_int,
            conversation_id=conversation_id,
            ereignis_datum=datum,
            wiederkehrend=wiederkehrend,
        )
        logger.info("Erinnerung gespeichert: %s (art=%s)", content[:80], art)
        return memory_id

    def _naechster_verwandter(self, content: str) -> Optional[Dict[str, Any]]:
        """Der aehnlichste vorhandene Eintrag ueber der Schwelle, sonst None.

        Geprueft wird gegen den ganzen Bestand, nicht nur gegen die letzten
        Eintraege - eine Korrektur betrifft oft einen alten Fakt.
        """
        neu = _normalisiert(content)
        if not neu:
            return None
        bester: Optional[Dict[str, Any]] = None
        beste_quote = 0.0
        for m in chroma_client.get_all_memories(limit=100000):
            alt = _normalisiert(m.get("content", ""))
            if not alt:
                continue
            if alt == neu:
                return m
            quote = difflib.SequenceMatcher(None, alt, neu).ratio()
            if quote >= AEHNLICHKEIT_SCHWELLE and quote > beste_quote:
                bester, beste_quote = m, quote
        return bester

    def _loese_ab(
        self,
        kandidat: Dict[str, Any],
        content: str,
        art: str,
        datum: Optional[str],
        wiederkehrend: bool,
        importance: int,
        conversation_id: Optional[str],
    ) -> str:
        """Neue Fassung aktiv, alte Fassung in ``history`` - nichts geloescht.

        In ``history`` wandert die abgeloeste Fassung mit ihrem Inhalt, dem
        Zeitpunkt der Abloesung (``abgeloest_am``), dem Zeitpunkt, an dem sie
        selbst geschrieben wurde (``geschrieben_am``) und ihrer Art. Damit
        bleibt auch das Alter der alten Aussage nachvollziehbar.
        """
        jetzt = datetime.now(timezone.utc).isoformat()
        verlauf = list(kandidat.get("history") or [])
        verlauf.append({
            "inhalt": kandidat.get("content", ""),
            "abgeloest_am": jetzt,
            "geschrieben_am": kandidat.get("timestamp"),
            "art": normalisiere_art(kandidat.get("category")),
        })

        felder: Dict[str, Any] = {
            "content": content,
            "category": art,
            "importance": int(importance),
            "timestamp": jetzt,
            "embedding": openrouter_vektor(content),
            "history": verlauf,
            "ereignis_datum": datum,
            "wiederkehrend": wiederkehrend,
        }
        if conversation_id:
            felder["conversation_id"] = conversation_id

        if not chroma_client.aktualisiere_memory(kandidat.get("id", ""), felder):
            # Kann nur passieren, wenn der Eintrag zwischenzeitlich fehlt.
            logger.warning("Abloesung fehlgeschlagen - lege neu an: %s", content[:80])
            return chroma_client.add_memory(
                content=content,
                embedding=felder["embedding"],
                category=art,
                importance=int(importance),
                conversation_id=conversation_id,
                history=verlauf,
                ereignis_datum=datum,
                wiederkehrend=wiederkehrend,
            )

        logger.info(
            "Korrektur: neue Fassung aktiv, alte in history (%d. Fassung): %s",
            len(verlauf), content[:80],
        )
        return kandidat.get("id", "")

    # ── aufraeumen ─────────────────────────────────────────────────

    def entferne_wiederholungen(self, nur_zeigen: bool = True) -> Dict[str, Any]:
        """Raeumt echte Doppelungen aus dem Bestand.

        Der jeweils aelteste Eintrag bleibt stehen, spaetere wortgleiche
        Wiederholungen fallen weg. Standardmaessig wird nur berichtet, was
        passieren wuerde - Loeschen erst mit ``nur_zeigen=False``.

        Wichtig seit der Korrektur-Regel: Eintraege, die sich in einem
        tragenden Wort unterscheiden, sind KEINE Doppelungen und werden hier
        nicht angefasst. Sonst wuerde ein Aufraeumen genau die Fassungen
        wegwerfen, die als Verlauf erhalten bleiben sollen.
        """
        alle = chroma_client.get_all_memories(limit=100000)
        behalten: List[Tuple[str, str]] = []      # (normalisierter Text, Inhalt)
        entfernen: List[Dict[str, Any]] = []

        for m in alle:
            norm = _normalisiert(m.get("content", ""))
            inhalt = m.get("content", "")
            treffer = next(
                (b for b in behalten if _ist_doppelung(b[0], norm)),
                None,
            )
            if treffer is not None:
                entfernen.append({
                    "id": m.get("id"),
                    "inhalt": inhalt,
                    "wiederholt": treffer[1],
                })
            else:
                behalten.append((norm, inhalt))

        if not nur_zeigen:
            for e in entfernen:
                chroma_client.delete_memory(e["id"])
            logger.info("%d Wiederholungen entfernt", len(entfernen))

        return {
            "vorher": len(alle),
            "nachher": len(alle) - len(entfernen),
            "entfernt": len(entfernen),
            "nur_gezeigt": nur_zeigen,
            "betroffen": entfernen,
        }

    # ── retrieve ───────────────────────────────────────────────────

    def retrieve_relevant_memories(
        self,
        query: str,
        top_k: int = MEMORY_TOP_K,
        *,
        heute: Optional[date] = None,
        mit_vergangenen: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Die Erinnerungen auswaehlen, die zur Frage gehoeren.

        Ablauf:

        1. Frage einbetten (OpenRouter). Gelingt das nicht, wird ueber
           Wortgleichheit ausgewaehlt - in jedem Fall aber BEGRENZT; der
           ganze Bestand wandert nie mehr in den Prompt.
        2. Termine bewerten: ein naher Termin bekommt einen Zuschlag, ein
           vergangener gilt nicht mehr als „aktuell" - es sei denn, die Frage
           zielt ausdruecklich auf die Vergangenheit („war ich 2026 beim
           Zahnarzt?"), dann kommt er als Historie mit.
        3. ``top_k`` begrenzen. Zusaetzlich kappt
           `llm_service._build_memory_context` den Block hart nach Zeichen.

        Jeder zurueckgegebene Eintrag traegt ``art``, ``zeitbezug``,
        ``relevanz``, ``relevanz_quelle`` sowie ``such_modus`` und
        ``such_hinweis`` - daran sieht der Prompt, wie gut die Suche war.
        """
        alle = chroma_client.get_all_memories(limit=100000)
        if not alle:
            return []

        heute = heute or date.today()
        if mit_vergangenen is None:
            mit_vergangenen = _fragt_nach_vergangenheit(query)

        query_vec = openrouter_vektor(query)
        scores = chroma_client.vektor_score(query_vec) if query_vec else {}
        modus = "vektor" if scores else "wort"

        ohne_vektor = 0
        # (Wert, Basis, Eintrag, Quelle, Lage, Datum, Art)
        bewertet: List[Tuple[float, float, Dict[str, Any], str, str, Optional[str], str]] = []
        for m in alle:
            art, datum, wiederkehrend = _wirksame_art(m, heute)
            bonus, lage = _termin_wert(art, datum, wiederkehrend, heute)
            if lage == "vergangen" and not mit_vergangenen:
                continue          # nicht mehr aktuell - aber nicht geloescht

            if m.get("id") in scores:
                basis = max(0.0, scores[m["id"]])
                quelle = "vektor"
            else:
                ohne_vektor += 1
                basis = _wort_score(query, m.get("content", ""))
                quelle = "wort"

            wichtig = m.get("importance")
            if not isinstance(wichtig, int) or not 1 <= wichtig <= 5:
                wichtig = 3
            wert = (
                basis
                + bonus
                + (wichtig - 3) * IMPORTANCE_GEWICHT
                + _alter_abzug(m.get("timestamp"), heute)
            )
            bewertet.append((wert, basis, m, quelle, lage, datum, art))

        if not bewertet:
            return []

        # Ohne Vektoren UND ohne Worttreffer bleibt nur „die neuesten" - das
        # wird als Notbehelf gekennzeichnet (frueher passierte das unsichtbar).
        if modus == "wort" and not any(basis > 0 for _, basis, *_ in bewertet):
            modus = "neuheit"

        bewertet.sort(key=lambda t: t[2].get("timestamp", ""), reverse=True)
        bewertet.sort(key=lambda t: t[0], reverse=True)

        hinweis = self._such_hinweis(modus, ohne_vektor, len(alle))
        grenze = max(1, int(top_k))
        ergebnis: List[Dict[str, Any]] = []
        for wert, _, m, quelle, lage, datum, art in bewertet[:grenze]:
            eintrag = dict(m)
            eintrag["art"] = art
            eintrag["zeitbezug"] = {"lage": lage, "datum": datum}
            eintrag["relevanz"] = round(wert, 4)
            eintrag["relevanz_quelle"] = quelle
            eintrag["such_modus"] = modus
            eintrag["such_hinweis"] = hinweis
            ergebnis.append(eintrag)
        return ergebnis

    def _such_hinweis(self, modus: str, ohne_vektor: int, gesamt: int) -> str:
        """Satz fuer den Prompt, der die Guete der Suche offenlegt."""
        if modus == "neuheit":
            return (
                "keine Vektoren verfügbar und kein Worttreffer – im Prompt "
                "stehen die neuesten Erinnerungen, nicht die passendsten"
            )
        if modus == "wort":
            return (
                "keine Vektoren verfügbar – ausgewählt über Wortgleichheit, "
                "nicht über Bedeutung"
            )
        if ohne_vektor:
            return (
                f"{ohne_vektor} von {gesamt} Erinnerungen ohne Vektor – für "
                "sie wurde über Wortgleichheit ausgewählt"
            )
        return ""

    # ── extract & store (LLM-based) ───────────────────────────────

    def extract_and_store_memories(
        self,
        user_message: str,
        llm_reply: str,
        conversation_id: Optional[str] = None,
        heute: Optional[date] = None,
    ) -> List[str]:
        """Use LLM to extract facts from conversation and store them.

        Das Modell liefert weiterhin nur Saetze (sein Auftrag ist streng:
        hoechstens 3, nichts Erfundenes). Art und Datum erkennt der Dienst
        danach selbst (`erkenne_art`) - so bleibt der LLM-Auftrag schlank
        und die Einordnung nachpruefbar.
        """
        facts = llm_service.extract_memories(user_message, llm_reply)
        stored_ids = []

        for fact in facts:
            if len(fact) > 10:
                memory_id = self.store_memory(
                    content=fact,
                    conversation_id=conversation_id,
                    heute=heute,
                )
                stored_ids.append(memory_id)

        if stored_ids:
            logger.info("Extracted and stored %d new memories", len(stored_ids))
        return stored_ids

    # ── query ──────────────────────────────────────────────────────

    def get_all_memories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all stored memories."""
        return chroma_client.get_all_memories(limit=limit)

    def get_memory_count(self) -> int:
        """Get the number of stored memories."""
        return chroma_client.count()

    def ruste_vektoren_nach(self) -> Dict[str, Any]:
        """Bettet Eintraege nach, die noch keinen Vektor haben.

        Noetig fuer alles, was vor der Umstellung gespeichert wurde (oder
        gespeichert wurde, als der Schluessel fehlte): Ohne Vektor findet die
        Bedeutungssuche einen Eintrag nie, egal wie gut er passt. Ein
        API-Aufruf je Eintrag, deshalb bewusst von Hand ausgeloest statt bei
        jedem Serverstart - jetzt ueber OpenRouter, ein Mistral-Schluessel
        ist nicht mehr noetig.
        """
        offen = chroma_client.eintraege_ohne_vektor()
        gelungen = 0
        for e in offen:
            vek = openrouter_vektor(e["content"])
            if vek and chroma_client.setze_vektor(e["id"], vek):
                gelungen += 1

        logger.info("Vektoren nachgerechnet: %d von %d", gelungen, len(offen))
        return {
            "offen_gewesen": len(offen),
            "eingebettet": gelungen,
            "fehlgeschlagen": len(offen) - gelungen,
        }

    # ── Migration ──────────────────────────────────────────────────

    def migriere_bestand(self, nur_zeigen: bool = True, heute: Optional[date] = None) -> Dict[str, Any]:
        """Traegt Art und Zeitbezug in Alteintraege nach - Inhalt unberuehrt.

        Hintergrund: Alle Eintraege vor dem 25.09.2026 tragen
        ``category: "fact"`` und ``importance: 3``; beides wurde nirgends
        gelesen. Damit der Zeitbezug ueberhaupt wirken kann, bekommen sie
        hier ihre Art:

        * ``fact`` -> ``fakt``
        * ``preference`` / ``context`` / ``project`` -> ``zustand``
        * danach einmalig die inhaltliche Erkennung: Datum -> ``termin``
          (mit ``ereignis_datum``), wiederkehrendes Datum -> ``termin``,
          veraenderliche Formulierung -> ``zustand``

        Garantien: Der Inhalt bleibt Zeichen fuer Zeichen gleich, es wird
        nichts geloescht, die Anzahl der Eintraege aendert sich nicht, und
        ohne ``nur_zeigen=False`` wird nur berichtet.
        """
        heute = heute or date.today()
        alle = chroma_client.get_all_memories(limit=100000)
        betroffen: List[Dict[str, Any]] = []

        for m in alle:
            aenderungen: Dict[str, Any] = {}
            roh = m.get("category")
            art = normalisiere_art(roh)
            if roh != art:
                aenderungen["category"] = art

            wichtig = m.get("importance")
            if not isinstance(wichtig, int) or not 1 <= wichtig <= 5:
                aenderungen["importance"] = 3

            if "history" not in m:
                aenderungen["history"] = []

            if art == "fakt":
                erkannt = erkenne_art(m.get("content", ""), heute)
                if erkannt["art"] != "fakt":
                    aenderungen["category"] = erkannt["art"]
                    if erkannt.get("ereignis_datum"):
                        aenderungen["ereignis_datum"] = erkannt["ereignis_datum"]
                    if erkannt.get("wiederkehrend"):
                        aenderungen["wiederkehrend"] = True

            if not aenderungen:
                continue
            betroffen.append({
                "id": m.get("id"),
                "inhalt": m.get("content", ""),
                "aenderungen": aenderungen,
            })
            if not nur_zeigen:
                chroma_client.aktualisiere_memory(m.get("id", ""), aenderungen)

        if not nur_zeigen and betroffen:
            logger.info(
                "Gedaechtnis migriert: %d von %d Eintraegen ergaenzt",
                len(betroffen), len(alle),
            )

        return {
            "vorher": len(alle),
            "nachher": chroma_client.count(),
            "geaendert": len(betroffen),
            "unveraendert": len(alle) - len(betroffen),
            "nur_gezeigt": nur_zeigen,
            "betroffen": betroffen[:200],
        }

    # ── erklaeren (Transparenz, ohne LLM) ──────────────────────────

    def erklaere_begriff(self, begriff: str, top_k: int = 10, *, heute: Optional[date] = None) -> Dict[str, Any]:
        """Was weiss der Agent ueber einen Begriff? Nur Lesen, kein Modell.

        Gesucht wird im Wortlaut (auch in den abgeloesten Fassungen in
        ``history``) - das laeuft ohne Schluessel, ohne Netz und ohne LLM und
        ist damit auch auf dem Handy benutzbar. Was der Agent NICHT hat, wird
        nicht erfunden: Ohne Treffer bleibt die Liste leer und der Hinweis
        sagt, wonach gesucht wurde.
        """
        begriff = (begriff or "").strip()
        heute = heute or date.today()
        antwort: Dict[str, Any] = {
            "begriff": begriff,
            "suchweise": "wortgleichheit",
            "hinweis": "",
            "anzahl": 0,
            "aktiv": 0,
            "historie": 0,
            "treffer": [],
        }
        if not begriff:
            antwort["hinweis"] = "Kein Suchbegriff angegeben."
            return antwort

        alle = chroma_client.get_all_memories(limit=100000)
        treffer: List[Dict[str, Any]] = []

        for m in alle:
            art, datum, wiederkehrend = _wirksame_art(m, heute)
            historie = list(m.get("history") or [])
            passt_aktiv = _passt(m.get("content", ""), begriff)
            passende_historie = [
                h for h in historie if _passt(str(h.get("inhalt", "")), begriff)
            ]
            if not passt_aktiv and not passende_historie:
                continue

            if passt_aktiv:
                treffer.append({
                    "id": m.get("id"),
                    "inhalt": m.get("content", ""),
                    "aktiv": True,
                    "art": art,
                    "art_text": ART_TEXTE.get(art, art),
                    "zeitbezug": self._zeitbezug(art, datum, wiederkehrend, heute),
                    "wichtig": m.get("importance", 3),
                    "seit": m.get("timestamp"),
                    "historie": [
                        {
                            "inhalt": h.get("inhalt", ""),
                            "abgeloest_am": h.get("abgeloest_am"),
                            "art": normalisiere_art(h.get("art")),
                        }
                        for h in historie
                    ],
                })

            for h in passende_historie:
                treffer.append({
                    "id": f"{m.get('id')}#historie",
                    "inhalt": h.get("inhalt", ""),
                    "aktiv": False,
                    "art": normalisiere_art(h.get("art")),
                    "art_text": ART_TEXTE.get(normalisiere_art(h.get("art")), ""),
                    "zeitbezug": {"lage": "abgeloest", "datum": None, "tage_bis": None},
                    "wichtig": None,
                    "seit": h.get("abgeloest_am"),
                    "historie_von": m.get("id"),
                    "abgeloest_am": h.get("abgeloest_am"),
                    "historie": [],
                })

        # Aktive Fassungen zuerst, dann die Historie - je neuer zuerst.
        treffer.sort(key=lambda t: (t.get("seit") or ""), reverse=True)
        treffer.sort(key=lambda t: 0 if t["aktiv"] else 1)
        treffer = treffer[:max(1, int(top_k))]

        antwort["treffer"] = treffer
        antwort["anzahl"] = len(treffer)
        antwort["aktiv"] = sum(1 for t in treffer if t["aktiv"])
        antwort["historie"] = antwort["anzahl"] - antwort["aktiv"]
        if not treffer:
            antwort["hinweis"] = (
                f"Keine Erinnerung enthält „{begriff}\". Gesucht wurde im "
                "Wortlaut (nicht nach Bedeutung), und es wurde nichts "
                "geloescht oder erfunden."
            )
        return antwort

    def _zeitbezug(
        self, art: str, datum: Optional[str], wiederkehrend: bool, heute: date
    ) -> Dict[str, Any]:
        """Zeitbezug eines Eintrags lesbar machen: Lage, Datum, Tage bis dahin."""
        if art != "termin":
            return {"lage": "ohne", "datum": None, "tage_bis": None}
        if wiederkehrend:
            return {"lage": "wiederkehrend", "datum": None, "tage_bis": None}
        lage, tage = _lage(datum, heute)
        return {"lage": lage or "ohne", "datum": datum, "tage_bis": tage}

    def loesche_erinnerung(self, memory_id: str) -> bool:
        """Loescht einen einzelnen Eintrag. True, wenn es ihn gab.

        Nur von Hand ausgeloest (API-Route/Blatt) - nirgends automatisch.
        """
        return chroma_client.delete_memory(memory_id)

    def clear_memories(self) -> None:
        """Clear all memories (for testing)."""
        chroma_client.clear_all()
        logger.info("All memories cleared.")


# Singleton instance
memory_service = MemoryService()
