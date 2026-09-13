"""Tests for the verified v1 normalisation chain (Node 2).

Scope note: see conftest.py. This exercises normalise() as copied verbatim
into scripts/current_paper/regenerate_corrected_maps.py from the executed
v1 code (scripts/rebuild_downstream.py et al.), confirmed identical across
five original scripts during the 2026-08 audit.
"""
import unicodedata
import re

from regenerate_corrected_maps import normalise


def test_lowercases():
    assert normalise("Circular Economy") == "circular economy"


def test_strips_leading_trailing_whitespace():
    assert normalise("  circular economy  ") == "circular economy"


def test_collapses_internal_whitespace():
    assert normalise("circular   economy") == "circular economy"
    assert normalise("circular\teconomy\n") == "circular economy"


def test_unicode_nfkc_normalisation():
    # U+FB01 LATIN SMALL LIGATURE FI -> "fi" under NFKC
    ligature = "ﬁber"
    assert normalise(ligature) == unicodedata.normalize("NFKC", ligature).lower()
    assert normalise(ligature) == "fiber"


def test_does_NOT_strip_punctuation():
    # v1 executed behaviour: NO punctuation standardisation at Node 2
    # (confirmed against origin/main's configs/normalisation_config.yaml
    # and the README's overstated claim — see
    # docs/provenance/v1_execution_config_provenance.md)
    assert normalise("circular-economy") == "circular-economy"
    assert normalise("circular (economy)") == "circular (economy)"


def test_does_NOT_expand_acronyms():
    assert normalise("CE") == "ce"
    assert normalise("CE") != normalise("circular economy")


def test_idempotent():
    s = "  Circular   Economy (CE)  "
    once = normalise(s)
    twice = normalise(once)
    assert once == twice
