"""Tests for verified v1 union-find clustering, frequency-only
canonicalisation, and deterministic graph insertion (Nodes 6-7 + the
Phase 0B Task 7 determinism fix).

Scope note: see conftest.py.
"""
import random

from regenerate_corrected_maps import union_find_clusters, make_canon_map
from downstream_deterministic import build_coword_network_deterministic


def test_union_find_merges_transitively():
    all_kws = ["a", "b", "c", "d"]
    kw_to_eids = {k: {"e1"} for k in all_kws}  # all present in the corpus
    match_edges = {("a", "b"), ("b", "c")}  # a-b-c chain, d isolated
    clusters = union_find_clusters(all_kws, match_edges, kw_to_eids)
    members_by_size = sorted((len(v) for v in clusters.values()), reverse=True)
    assert members_by_size == [3, 1]  # {a,b,c} merged, {d} singleton


def test_union_find_ignores_non_match_edges_implicitly():
    # non_match/uncertain decisions are never passed as match_edges at all --
    # this test documents that contract rather than testing a "no" path.
    all_kws = ["a", "b"]
    kw_to_eids = {k: {"e1"} for k in all_kws}
    clusters = union_find_clusters(all_kws, set(), kw_to_eids)
    assert len(clusters) == 2  # no edges -> both singletons


def test_union_find_membership_is_independent_of_edge_processing_order():
    all_kws = ["a", "b", "c", "d", "e"]
    kw_to_eids = {k: {"e1"} for k in all_kws}
    edges = {("a", "b"), ("b", "c"), ("c", "d")}
    sizes_1 = sorted(len(v) for v in union_find_clusters(all_kws, edges, kw_to_eids).values())
    # process the mathematically-identical edge set inserted via a python set
    # built in a different order (sets are unordered, but membership is fixed)
    edges_reordered = set(reversed(list(edges)))
    sizes_2 = sorted(len(v) for v in union_find_clusters(all_kws, edges_reordered, kw_to_eids).values())
    assert sizes_1 == sizes_2 == [1, 4]


def test_canonicalisation_is_frequency_only():
    clusters = {"root1": ["Circular Economy", "CE", "circular economy"]}
    kw_freq = {"Circular Economy": 5, "CE": 100, "circular economy": 2}
    canon_map = make_canon_map(clusters, kw_freq)
    # highest raw frequency wins, regardless of form/length/alphabetical order
    assert canon_map["Circular Economy"] == "CE"
    assert canon_map["CE"] == "CE"
    assert canon_map["circular economy"] == "CE"


def test_canonicalisation_does_not_change_cluster_membership():
    clusters = {"root1": ["a", "b", "c"]}
    kw_freq_v1 = {"a": 1, "b": 2, "c": 3}
    kw_freq_alt = {"a": 3, "b": 2, "c": 1}  # different frequencies, different label
    canon_v1 = make_canon_map(clusters, kw_freq_v1)
    canon_alt = make_canon_map(clusters, kw_freq_alt)
    assert canon_v1["a"] != canon_alt["a"]  # label CAN change
    assert set(clusters["root1"]) == {"a", "b", "c"}  # membership never touched


def test_deterministic_graph_insertion_sorts_node_order_regardless_of_input():
    """Regression test for the Phase 0B Task 7 fix: node insertion order
    must be sorted, not dependent on Python's (hash-seed-randomised) set
    iteration order. This is the exact bug that caused the rerun-instability
    found in Phase 0A."""
    kw_to_canon = {"z": "z", "a": "a", "m": "m"}
    kw_to_eids = {"z": {"e1"}, "a": {"e1", "e2", "e3", "e4", "e5"},
                  "m": {"e1", "e2", "e3", "e4", "e5"}}
    article_to_kws = {"e1": ["z", "a", "m"], "e2": ["a", "m"], "e3": ["a", "m"],
                       "e4": ["a", "m"], "e5": ["a", "m"]}
    articles = list(article_to_kws.keys())

    G, c_freq, nodes = build_coword_network_deterministic(
        kw_to_canon, kw_to_eids, article_to_kws, articles, freq_thresh=5)

    assert list(G.nodes()) == sorted(G.nodes())  # insertion order is sorted
    assert set(G.nodes()) == {"a", "m"}  # z has freq 1, excluded by freq_thresh


def test_deterministic_graph_insertion_repeatable_across_calls():
    kw_to_canon = {k: k for k in "edcba"}
    kw_to_eids = {k: {f"e{i}" for i in range(6)} for k in "edcba"}
    article_to_kws = {f"e{i}": list("edcba") for i in range(6)}
    articles = list(article_to_kws.keys())

    node_orders = []
    for _ in range(5):
        G, _, _ = build_coword_network_deterministic(
            kw_to_canon, kw_to_eids, article_to_kws, articles, freq_thresh=5)
        node_orders.append(list(G.nodes()))
    assert all(order == node_orders[0] for order in node_orders)
    assert node_orders[0] == sorted(node_orders[0])
