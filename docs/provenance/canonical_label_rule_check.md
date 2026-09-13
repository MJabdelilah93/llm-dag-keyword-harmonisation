# Canonical-Label Rule Check

**Status: diagnostic only. v1 clustering was NOT changed. No retrofit applied.**

## What ran vs. what was documented

| | Executed (v1) | Documented (`configs/canonical_rules.yaml`, LEGACY) |
|---|---|---|
| Rule | Highest raw frequency only (`max()` over cluster members, ties broken by corpus row order) | 4-tier: controlled vocabulary → frequency → shortest label → alphabetical |

## Why only 3 of 4 tiers could be tested

Tier 1 ("controlled vocabulary — prefer MeSH, ACM CCS, or JEL terms") has
**no corresponding lookup table anywhere in this repository**. There is no
data source from which to determine whether any given keyword "is" a
MeSH/ACM-CCS/JEL term. Per Task 12's explicit instruction, this diagnostic
does not invent one — implementing tier 1 for this check would mean
fabricating exactly the kind of unfounded retrofit the task prohibits. Tiers
2 (frequency), 3 (shortest label) and 4 (alphabetical) are all objectively
defined from data already present in the corrected map files, and were
fully implemented and tested.

## Result

| Condition | Multi-member clusters | Labels that would change | % changed |
|---|---|---|---|
| Full LLM-DAG | 7,713 | 1,366 | 17.71% |
| B3 Jaro-Winkler | 6,601 | 1,339 | 20.29% |

Roughly one in five or six multi-member clusters would receive a different
canonical label under the tiers-2-4 rule — almost always a formatting
variant (capitalisation, hyphenation, singular/plural, or an acronym
preferred over its expansion) rather than a substantively different
concept name. See `docs/provenance/canonical_label_rule_check.json` for ten
worked examples per condition.

## Effects

- **Cluster membership: unaffected, by construction.** Canonicalisation runs
  strictly after union-find clustering and only chooses a *display label*
  for an already-fixed group of keywords. No rule change here can alter
  which raw keywords are grouped together — the 194 / 56 / 216 / 214 / 57
  figures verified elsewhere in this repair are entirely unaffected.
- **Downstream numeric metrics (vocab/edges/density/modularity/ARI/AMI):
  unaffected in count**, but the network's node *identifiers* would change
  for ~17-20% of nodes, since those metrics are computed over canonical
  labels as graph node names. Vocabulary size, edge count, density, and
  (Louvain-seed-dependent) modularity/ARI/AMI values are invariant to what
  a node is *called* — only to how many distinct nodes exist and how they
  connect, which does not change here.
- **Figure 2 labels: would change** for whichever of the displayed top
  keywords happen to fall among the ~17-20% affected clusters. Not
  independently checked against the current Figure 2's specific displayed
  labels in this diagnostic — see Task 11.

## Recommendation for the current paper

**Describe the method that actually ran** (frequency-only canonicalisation)
rather than retrofitting the documented 4-tier rule into v1. Retrofitting
would require either fabricating a controlled-vocabulary data source that
never existed in this study, or silently changing ~1,300-1,400 canonical
labels after the fact without having done so during the actual experiment —
neither is a legitimate description of what produced the reported results.
If a richer canonicalisation rule is wanted, it belongs in the *enhanced*
Scientometrics study as a new, explicitly-implemented and evaluated design
choice, not as a retroactive correction to v1.
