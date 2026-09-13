# B1-B5 frozen-inference evaluation (900 prospective pairs)

Numbers only -- no keyword strings.

## ce400 (N=400)

| Method | Precision | Recall | F1 | Coverage | F1 95% CI |
|---|---:|---:|---:|---:|---:|
| B1_Exact | 1.0000 | 0.3107 | 0.4741 | 1.0000 | [0.3676, 0.5733] |
| B2_Normalised | 1.0000 | 0.3107 | 0.4741 | 1.0000 | [0.3676, 0.5733] |
| B3_JaroWinkler | 0.9375 | 0.8738 | 0.9045 | 1.0000 | [0.8586, 0.9448] |
| B4_TFIDF | 0.7615 | 0.8058 | 0.7830 | 1.0000 | [0.7164, 0.8411] |
| B5_Embedding | 0.9778 | 0.8544 | 0.9119 | 1.0000 | [0.8677, 0.9503] |

**Selective-prediction demonstration only** (margin-based proxy confidence, not a genuine model confidence):

| Method | AURC | Coverage@no-threshold | Risk@no-threshold |
|---|---:|---:|---:|
| B3_JaroWinkler | 0.0225 | 1.0000 | 0.0482 |
| B4_TFIDF | 0.0446 | 1.0000 | 0.1168 |
| B5_Embedding | 0.0349 | 1.0000 | 0.0431 |

## diabetes500 (N=500)

| Method | Precision | Recall | F1 | Coverage | F1 95% CI |
|---|---:|---:|---:|---:|---:|
| B1_Exact | 1.0000 | 0.2484 | 0.3980 | 1.0000 | [0.3100, 0.4808] |
| B2_Normalised | 1.0000 | 0.2484 | 0.3980 | 1.0000 | [0.3100, 0.4808] |
| B3_JaroWinkler | 0.9470 | 0.7764 | 0.8532 | 1.0000 | [0.8071, 0.8942] |
| B4_TFIDF | 0.8188 | 0.7019 | 0.7559 | 1.0000 | [0.6978, 0.8066] |
| B5_Embedding | 0.9593 | 0.7329 | 0.8310 | 1.0000 | [0.7807, 0.8754] |

**Selective-prediction demonstration only** (margin-based proxy confidence, not a genuine model confidence):

| Method | AURC | Coverage@no-threshold | Risk@no-threshold |
|---|---:|---:|---:|
| B3_JaroWinkler | 0.0634 | 1.0000 | 0.0862 |
| B4_TFIDF | 0.0783 | 1.0000 | 0.1463 |
| B5_Embedding | 0.0739 | 1.0000 | 0.0962 |

## pooled900 (N=900)

| Method | Precision | Recall | F1 | Coverage | F1 95% CI |
|---|---:|---:|---:|---:|---:|
| B1_Exact | 1.0000 | 0.2727 | 0.4286 | 1.0000 | [0.3601, 0.4928] |
| B2_Normalised | 1.0000 | 0.2727 | 0.4286 | 1.0000 | [0.3601, 0.4928] |
| B3_JaroWinkler | 0.9430 | 0.8144 | 0.8740 | 1.0000 | [0.8412, 0.9039] |
| B4_TFIDF | 0.7849 | 0.7462 | 0.7650 | 1.0000 | [0.7222, 0.8043] |
| B5_Embedding | 0.9671 | 0.7803 | 0.8637 | 1.0000 | [0.8298, 0.8952] |

**Selective-prediction demonstration only** (margin-based proxy confidence, not a genuine model confidence):

| Method | AURC | Coverage@no-threshold | Risk@no-threshold |
|---|---:|---:|---:|
| B3_JaroWinkler | 0.0445 | 1.0000 | 0.0694 |
| B4_TFIDF | 0.0628 | 1.0000 | 0.1355 |
| B5_Embedding | 0.0538 | 1.0000 | 0.0728 |
