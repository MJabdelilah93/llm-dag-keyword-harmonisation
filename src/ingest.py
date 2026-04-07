"""
Node 1: Corpus ingest and snapshot.

Loads raw Scopus exports (.csv, .bib, .ris) from data/raw/,
validates schema, deduplicates records, and writes a
timestamped snapshot to data/interim/ for downstream nodes.
"""
