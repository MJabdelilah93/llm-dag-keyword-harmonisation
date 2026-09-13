"""Unit tests for the strengthening-phase CE candidate-generation package.
No network, no legacy-data dependency (legacy_access.py is exercised only
by generate_ce_candidates.py's own script entry point, not by these tests).
"""
from strengthening.candidate_gen.features import (
    acronym_feature,
    case_whitespace_only_variant,
    jaro_winkler_score,
    lexical_equal,
    malformed_feature,
    plural_feature,
    punctuation_feature,
)
from strengthening.candidate_gen.normalise import normalise, unordered_pair_key
from strengthening.candidate_gen.pair_ids import stable_pair_id
from strengthening.candidate_gen.stratify import classify_pair


def test_normalise_nfkc_lower_strip_collapse():
    assert normalise("  Circular   Economy  ") == "circular economy"
    assert normalise("Circular Economy") == normalise("circular economy")


def test_normalise_does_not_strip_punctuation():
    assert normalise("eco-design") != normalise("eco design")
    assert normalise("eco-design") == "eco-design"


def test_unordered_pair_key_order_independent():
    assert unordered_pair_key("A", "B") == unordered_pair_key("B", "A")


def test_lexical_equal_and_case_whitespace_variant():
    assert lexical_equal("Circular Economy", "circular   economy")
    assert case_whitespace_only_variant("Circular Economy", "circular economy")
    assert not case_whitespace_only_variant("Circular Economy", "Circular Economy")  # identical, not a variant
    assert not case_whitespace_only_variant("Circular Economy", "Linear Economy")


def test_jaro_winkler_score_range_and_identity():
    assert jaro_winkler_score("recycling", "recycling") == 1.0
    s = jaro_winkler_score("recycling", "recyckling")
    assert 0.85 <= s < 1.0


def test_acronym_feature_parenthetical_and_initials():
    f = acronym_feature("Material flow analysis (MFA)", "MFA")
    assert f.is_parenthetical_pair or f.initials_match
    f2 = acronym_feature("Circular Economy", "CE")
    assert f2.initials_match


def test_punctuation_feature():
    assert punctuation_feature("eco-design", "eco design")
    assert not punctuation_feature("eco-design", "eco-design")


def test_plural_feature():
    assert plural_feature("recycling process", "recycling processes")
    assert not plural_feature("recycling", "upcycling")


def test_malformed_feature():
    assert malformed_feature("aaaaaaaa")
    assert malformed_feature("###???###")
    assert not malformed_feature("circular economy")


def test_classify_pair_priority_order():
    # Malformed beats everything else.
    r = classify_pair("aaaaaaaa", "circular economy", embedding_cosine=0.9)
    assert r.stratum == "ix"
    # Case/whitespace-only beats spelling/embedding routes.
    r = classify_pair("Circular Economy", "circular   economy", embedding_cosine=0.9)
    assert r.stratum == "i"
    # Punctuation beats singular/plural and score-based routes.
    r = classify_pair("eco-design", "eco design", embedding_cosine=0.9)
    assert r.stratum == "iv"
    # Pure embedding-interval fallback when no structural feature applies.
    r = classify_pair("solar power", "photovoltaic energy", embedding_cosine=0.80)
    assert r.stratum == "vi"
    r = classify_pair("solar power", "renewable energy", embedding_cosine=0.65)
    assert r.stratum == "vii"
    r = classify_pair("solar power", "unrelated concept", embedding_cosine=0.55)
    assert r.stratum == "x"


def test_stable_pair_id_reproducible_and_order_independent():
    id1 = stable_pair_id("Circular Economy", "circular economy", "ce")
    id2 = stable_pair_id("circular economy", "Circular Economy", "ce")
    assert id1 == id2
    assert id1.startswith("ce_")
    # Different content -> different id.
    id3 = stable_pair_id("Circular Economy", "Linear Economy", "ce")
    assert id3 != id1
