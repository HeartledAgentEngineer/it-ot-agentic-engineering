"""
tests/test_rip_namensfilter.py
==============================
Schaerft _plausible_artist_name gegen den realen Noise aus dem RIP-2027-Scrape
(Website-Nav, Fremdseiten, Social, Datums-/Encoding-Fragmente), ohne echte
Bandnamen zu verlieren. Negativ-/Positivfaelle sind echte Scrape-Treffer.
"""

from rock_im_park import _plausible_artist_name as ok

# Echte Bandnamen — MUESSEN durchkommen (inkl. kurzer & kniffliger)
ECHTE_BANDS = [
    "Blink-182", "Turnstile", "Bring Me The Horizon", "Die Toten Hosen",
    "The Prodigy", "Faith No More", "Bad Religion", "SPEED", "TBS", "Clutch",
    "Poppy", "Donots", "I Prevail", "Amon Amarth", "As December Falls",
    "Nothing But Thieves", "Killswitch Engage", "Parkway Drive",
    "Falling In Reverse", "Motionless In White",
]

# Realer Noise — MUSS rausfliegen
NOISE = [
    "Skip to content", "festivalpilot", "DE", "EN", "Days", "Timetable", "Bands",
    "Full lineup (1)", "Tier 1 Headliners (1)", "Username or Email Address",
    "Password", "Remember Me", "CONTACT US", "FTC DISCLOSURE", "Facebook",
    "Instagram", "231K followers", "52 following", "German server. Pro for €5.99",
    ": tbc", ": Pending", "Words:", "Jun 4�6", "06 Jun 26", "June 4-6",
    "About Us", "Sign Up", "Playlist", "App", "Line-Up", "Headliner",
    "Very special guest", "Logo The Prodigy", "This year", "4. Juni. Logo Turnstile",
    "Welcome to Music Festival Wizard", "Venue: Zeppelinfeld",
    "Additional Ticket Options", "Buy Tickets Here", "Official Website",
    "When are the set times",
]


def test_echte_bands_kommen_durch():
    durchgefallen = [b for b in ECHTE_BANDS if not ok(b)]
    assert durchgefallen == [], f"faelschlich abgelehnt: {durchgefallen}"


def test_noise_wird_abgelehnt():
    durchgerutscht = [n for n in NOISE if ok(n)]
    assert durchgerutscht == [], f"Noise nicht gefiltert: {durchgerutscht}"
