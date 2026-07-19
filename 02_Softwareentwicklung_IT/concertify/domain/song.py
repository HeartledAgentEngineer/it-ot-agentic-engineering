"""
domain/song.py
===============
Die Song-Klasse repraesentiert einen einzelnen Lied-Eintrag in einer Setlist.

Engineering-Konzept: "Domain Object"
    Eine Klasse die ein Konzept aus der echten Welt abbildet.
    Hier: ein Song mit Titel, Spotify-Link und Statistiken.

Brueckenwissen fuer Sebastian:
    IEC 61131-3:  Wie ein STRUCT, oder ein FUNCTION_BLOCK ohne externe Aktionen.
                  Die Attribute unten = VAR-Block. Die Methoden = METHODs.
    C#:           Wie eine Klasse mit Auto-Properties. Aehnlich einem `record`.
    C:            Wie ein typedef struct, aber mit Methoden dran.

Beispiel:
    song = Song(title="Numb", play_count=83, score=1.0)
    if song.is_likely_played():
        print(f"{song.title} wird mit hoher Wahrscheinlichkeit gespielt")
"""

from dataclasses import dataclass, field


# ─── Was ist @dataclass? ─────────────────────────────────────────────────────
# @dataclass ist ein Python-Decorator (man liest "at-dataclass").
# Er sorgt automatisch dafuer dass die Klasse einen Konstruktor bekommt,
# der die Attribute als Parameter nimmt. Sonst muesstest du manuell schreiben:
#
#   def __init__(self, title, spotify_uri=None, score=0.0, ...):
#       self.title = title
#       self.spotify_uri = spotify_uri
#       ...
#
# Mit @dataclass schreibst du nur die Attribute mit Typen, fertig.
# Vergleichbar mit C# Auto-Properties: { get; set; } macht das gleiche.

@dataclass
class Song:
    """Ein Song in einer Setlist.

    Attribute (= VAR-Block eines IEC FB):
        title:           Anzeigename des Songs, z.B. "Numb"
        spotify_uri:     Spotify-Track-URI oder None falls noch nicht aufgeloest
                         Format: "spotify:track:abc123..."
        score:           Wahrscheinlichkeit dass der Song live gespielt wird
                         Wertebereich: 0.0 (nie) bis 1.0 (immer)
        play_count:      Anzahl der bisher beobachteten Konzerte mit diesem Song
        positions_hist:  Slot-Wahrscheinlichkeiten als Histogramm.
                         Schluessel = Position im Set, Wert = Anzahl Vorkommen.
                         Beispiel: {1: 5, 3: 2}  → 5x als Opener, 2x als 3. Song
        badge:           UI-Marker: 'setlist', 'spotify', 'prediction_hoch',
                         'prediction_mittel', 'prediction_niedrig' oder ''
    """

    # Type Hints (`title: str`) entsprechen IEC-Variablendeklarationen:
    #   title : STRING;   ←→   title: str
    #   anzahl: INT;      ←→   anzahl: int
    #   aktiv : BOOL;     ←→   aktiv: bool

    title: str
    spotify_uri: str | None = None       # `| None` = optional (kann auch None sein)
    score: float = 0.0
    play_count: int = 0
    # field(default_factory=dict) → leeres Dict als Default.
    # Wichtig: NICHT einfach `= {}` schreiben — das waere ein gemeinsames Dict
    # fuer alle Instanzen! (klassischer Python-Bug)
    positions_hist: dict[int, int] = field(default_factory=dict)
    badge: str = ""

    # ─── Verhalten / Methoden ───────────────────────────────────────────────
    # In IEC waeren das die METHODs eines FUNCTION_BLOCK.
    # In C# waeren das public methods der Klasse.

    def has_uri(self) -> bool:
        """True wenn der Song eine Spotify-URI hat (also abspielbar ist)."""
        return self.spotify_uri is not None and self.spotify_uri != ""

    def position_range(self) -> tuple[int, int] | None:
        """Min/Max der Positionen aus positions_hist.

        Returns:
            (min_pos, max_pos) als Tupel, oder None wenn keine Daten.

        Beispiel:
            song = Song(title="X", positions_hist={3: 5, 5: 2, 7: 1})
            song.position_range()  → (3, 7)

            song2 = Song(title="Y")  # leere History
            song2.position_range()  → None
        """
        if not self.positions_hist:
            return None
        positions = list(self.positions_hist.keys())
        return (min(positions), max(positions))

    def is_likely_played(self, threshold: float = 0.5) -> bool:
        """True wenn der Song mit Wahrscheinlichkeit >= threshold gespielt wird.

        Args:
            threshold: Untergrenze, default 0.5 (= 50% der Konzerte).
        """
        return self.score >= threshold

    def average_position(self) -> float | None:
        """Durchschnittliche Position aus dem Histogramm.

        Berechnung: gewichteter Mittelwert ueber alle Positionen.

        Beispiel:
            positions_hist = {3: 4, 5: 1}  → 4 Mal Pos 3, 1 Mal Pos 5
            Mittel = (3*4 + 5*1) / (4+1) = 17/5 = 3.4

        Returns:
            Float-Wert oder None wenn keine Daten.
        """
        if not self.positions_hist:
            return None
        total_plays = sum(self.positions_hist.values())
        weighted_sum = sum(pos * count for pos, count in self.positions_hist.items())
        return weighted_sum / total_plays
