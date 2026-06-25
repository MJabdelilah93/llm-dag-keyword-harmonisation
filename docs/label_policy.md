# Label Policy — Quick Reference

Use this table when annotating. Full rules and examples in `docs/annotation_guide.md`.

| Case type | Default label |
|-----------|---------------|
| Spelling variant | match |
| Punctuation / hyphenation variant | match |
| Singular / plural variant | match |
| Acronym + expanded form (unambiguous) | match |
| Near-synonym (clear same-concept) | match |
| Broader–narrower relation | **non-match** |
| Related but distinct concepts | **non-match** |
| Polysemous acronym / ambiguous short form | **uncertain** |
| Context-dependent overlap | **uncertain** |
| Malformed / truncated string | **uncertain** |

**When in doubt: label `uncertain`.** A false merge is harder to undo downstream than a missed merge.
