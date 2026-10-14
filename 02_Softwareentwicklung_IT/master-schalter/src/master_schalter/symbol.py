"""Das Bild des Taskleisten-Symbols: zwei senkrechte Balken (links Claude, rechts Codex)."""
from __future__ import annotations

from PIL import Image, ImageDraw

GROESSE = 64
CLAUDE = (217, 119, 87)
CODEX = (16, 163, 127)
GELB = (234, 179, 8)
ROT = (220, 38, 38)
RAHMEN = (229, 231, 235)
WARN_AB = 80

# (links, oben, rechts, unten) je Balken
BALKEN = ((6, 4, 29, 61), (35, 4, 58, 61))


def balken_mitte() -> tuple[int, int]:
    return tuple((l + r) // 2 for l, _, r, _ in BALKEN)  # type: ignore[return-value]


def _farbe(prozent: float, grundfarbe: tuple[int, int, int], schwelle: int) -> tuple[int, int, int]:
    if prozent >= schwelle:
        return ROT
    return GELB if prozent >= WARN_AB else grundfarbe


def bild(claude: float | None, codex: float | None, schwelle: int) -> Image.Image:
    """Füllhöhe = 5-Stunden-Verbrauch; gelb ab 80 %, rot ab Schwelle; leer = unbekannt."""
    b = Image.new("RGBA", (GROESSE, GROESSE), (0, 0, 0, 0))
    zeichnen = ImageDraw.Draw(b)
    for (links, oben, rechts, unten), prozent, grundfarbe in zip(BALKEN, (claude, codex), (CLAUDE, CODEX)):
        zeichnen.rectangle((links, oben, rechts, unten), outline=RAHMEN, width=2)
        if prozent is None or prozent <= 0:
            continue
        innen_oben, innen_unten = oben + 2, unten - 2
        hoehe = round((innen_unten - innen_oben) * min(prozent, 100) / 100)
        if hoehe <= 0:
            continue
        zeichnen.rectangle((links + 2, innen_unten - hoehe, rechts - 2, innen_unten),
                           fill=_farbe(prozent, grundfarbe, schwelle))
    return b
