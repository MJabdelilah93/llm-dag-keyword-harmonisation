"""Repurposed for Phase 0B Task 14: end-to-end fixture tests for corrected
map reconstruction and downstream reproducibility.

Scope note: see conftest.py. "Candidate generation" (Node 3) itself is not
on Task 14's required test list, and its logic (lexical blocking + JW +
embedding retrieval) is not cleanly factored into an importable function in
either the original scripts/ or the Phase 0B repair scripts, so it is not
tested here. This file instead covers the two remaining required items that
need an end-to-end, multi-function fixture rather than a single unit test:
"corrected map reconstruction from a small fixture" and "downstream
reproducibility fixture."
"""
from collections import defaultdict

from regenerate_corrected_maps import union_find_clusters, make_canon_map
from downstream_deterministic import build_coword_network_deterministic, louvain_partition


# A tiny, fully synthetic fixture -- no real corpus data. Two article
# clusters: a "circular economy" family (freq-heavy) and an isolated
# unrelated pair, mirroring the real corpus's structural shape at toy scale.
FIXTURE_KEYWORDS = ["Circular economy", "circular economy", "CE", "Recycling", "recycling"]
FIXTURE_ARTICLES = {
    "e1": ["Circular economy", "Recycling"],
    "e2": ["circular economy", "Recycling"],
    "e3": ["CE", "recycling"],
    "e4": ["Circular economy", "recycling"],
    "e5": ["circular economy", "Recycling"],
    "e6": ["CE"],
    "e7": ["CE"],
    "e8": ["CE"],
}


def _kw_to_eids():
    kw_to_eids = defaultdict(set)
    for eid, kws in FIXTURE_ARTICLES.items():
        for k in kws:
            kw_to_eids[k].add(eid)
    return dict(kw_to_eids)


def test_corrected_map_reconstruction_from_small_fixture():
    kw_to_eids = _kw_to_eids()
    kw_freq = {k: len(v) for k, v in kw_to_eids.items()}
    match_edges = {("CE", "Circular economy"), ("Circular economy", "circular economy")}

    clusters = union_find_clusters(FIXTURE_KEYWORDS, match_edges, kw_to_eids)
    canon_map = make_canon_map(clusters, kw_freq)

    # all three "circular economy" variants should share one canonical label
    assert canon_map["Circular economy"] == canon_map["circular economy"] == canon_map["CE"]
    # "Recycling"/"recycling" were never matched -- remain distinct clusters
    assert canon_map["Recycling"] != canon_map["recycling"]
    # canonical label is the highest-frequency member (v1 rule): "CE" appears
    # in 4 articles vs. 2 each for the other two variants, so it must win.
    assert kw_freq["CE"] > kw_freq["Circular economy"]
    assert kw_freq["CE"] > kw_freq["circular economy"]
    assert canon_map["Circular economy"] == "CE"


def test_downstream_reproducibility_fixture_identical_across_repeated_builds():
    kw_to_eids = _kw_to_eids()
    kw_freq = {k: len(v) for k, v in kw_to_eids.items()}
    match_edges = {("CE", "Circular economy"), ("Circular economy", "circular economy")}
    clusters = union_find_clusters(FIXTURE_KEYWORDS, match_edges, kw_to_eids)
    kw_to_canon = make_canon_map(clusters, kw_freq)
    articles = list(FIXTURE_ARTICLES.keys())

    results = []
    for _ in range(5):
        G, _, _ = build_coword_network_deterministic(
            kw_to_canon, kw_to_eids, FIXTURE_ARTICLES, articles, freq_thresh=1)
        part, q, nc = louvain_partition(G, seed=42)
        results.append((G.number_of_nodes(), G.number_of_edges(), round(q, 10), nc))

    assert len(set(results)) == 1, (
        "downstream reproducibility fixture failed: repeated builds of the "
        "same deterministic graph + fixed Louvain seed produced different "
        f"results: {set(results)}"
    )
