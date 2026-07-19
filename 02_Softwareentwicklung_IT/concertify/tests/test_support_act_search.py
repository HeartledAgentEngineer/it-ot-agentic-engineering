"""
tests/test_support_act_search.py
================================
Tests fuer die Support-Act-Extraktion aus Web-Suchtreffern (Serper).
Reine Logik, kein Netzwerk.
"""

from support_act_search import extract_support_acts


def test_extracts_named_support_act():
    text = "Breaking Benjamin. UK / EU Tour 2026. Support act Chevelle - Bestel tickets"
    assert extract_support_acts(text) == ["Chevelle"]


def test_ignores_generic_phrase_without_name():
    # "support act information" darf NICHT als Name "Information" durchrutschen
    text = "find event, venue and support act information and reviews for Breaking Benjamin"
    assert extract_support_acts(text) == []


def test_extracts_special_guest_multiword():
    text = "Breaking Benjamin announces tour with special guests Papa Roach at the arena"
    assert extract_support_acts(text) == ["Papa Roach"]


def test_supported_by_pattern():
    text = "The band will be supported by Bilmuri on all dates."
    assert extract_support_acts(text) == ["Bilmuri"]


def test_excludes_main_artist():
    text = "Support act Breaking Benjamin opens the night"
    assert extract_support_acts(text, exclude={"Breaking Benjamin"}) == []


def test_dedups_repeated_names():
    text = "Support act Chevelle. Later: special guest Chevelle confirmed."
    assert extract_support_acts(text) == ["Chevelle"]


def test_case_insensitive_prefix_but_name_must_be_capitalised():
    # Prefix in beliebiger Schreibweise, aber der Name muss gross anfangen
    assert extract_support_acts("SUPPORT ACT Architects join the bill") == ["Architects"]
    assert extract_support_acts("support act tickets available now") == []


def test_empty_and_no_match():
    assert extract_support_acts("") == []
    assert extract_support_acts("Just a normal concert announcement.") == []
