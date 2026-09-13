# C2 evaluation results (real predictions, joined strictly after prediction freeze)

## Binary evaluation (gold-uncertain excluded)

### ce400

| Method | TP | FP | FN | TN | Precision | Recall | F1 | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_Exact | 32 | 0 | 71 | 291 | 1.0000 | 0.3107 | 0.4741 | 1.0000 |
| B2_Normalised | 32 | 0 | 71 | 291 | 1.0000 | 0.3107 | 0.4741 | 1.0000 |
| B3_JaroWinkler | 90 | 6 | 13 | 285 | 0.9375 | 0.8738 | 0.9045 | 1.0000 |
| B4_TFIDF | 82 | 29 | 21 | 262 | 0.7387 | 0.7961 | 0.7664 | 1.0000 |
| B5_Embedding | 88 | 2 | 15 | 289 | 0.9778 | 0.8544 | 0.9119 | 1.0000 |
| Primary_M7 | 99 | 4 | 4 | 269 | 0.9612 | 0.9612 | 0.9612 | 0.9543 |
| B6 | 98 | 34 | 5 | 257 | 0.7424 | 0.9515 | 0.8340 | 1.0000 |
| B7 | 99 | 19 | 4 | 272 | 0.8390 | 0.9612 | 0.8959 | 1.0000 |
| B8 | 27 | 4 | 76 | 287 | 0.8710 | 0.2621 | 0.4030 | 1.0000 |
| OpenAI_Robustness | 97 | 8 | 2 | 171 | 0.9238 | 0.9798 | 0.9510 | 0.7056 |

### diabetes500

| Method | TP | FP | FN | TN | Precision | Recall | F1 | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_Exact | 40 | 0 | 121 | 338 | 1.0000 | 0.2484 | 0.3980 | 1.0000 |
| B2_Normalised | 40 | 0 | 121 | 338 | 1.0000 | 0.2484 | 0.3980 | 1.0000 |
| B3_JaroWinkler | 125 | 7 | 36 | 331 | 0.9470 | 0.7764 | 0.8532 | 1.0000 |
| B4_TFIDF | 115 | 25 | 46 | 313 | 0.8214 | 0.7143 | 0.7641 | 1.0000 |
| B5_Embedding | 118 | 5 | 43 | 333 | 0.9593 | 0.7329 | 0.8310 | 1.0000 |
| Primary_M7 | 151 | 2 | 7 | 332 | 0.9869 | 0.9557 | 0.9711 | 0.9860 |
| B6 | 151 | 14 | 10 | 324 | 0.9152 | 0.9379 | 0.9264 | 1.0000 |
| B7 | 156 | 7 | 5 | 331 | 0.9571 | 0.9689 | 0.9630 | 1.0000 |
| B8 | 133 | 2 | 28 | 336 | 0.9852 | 0.8261 | 0.8986 | 1.0000 |
| OpenAI_Robustness | 148 | 14 | 1 | 246 | 0.9136 | 0.9933 | 0.9518 | 0.8196 |

### pooled900

| Method | TP | FP | FN | TN | Precision | Recall | F1 | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_Exact | 72 | 0 | 192 | 629 | 1.0000 | 0.2727 | 0.4286 | 1.0000 |
| B2_Normalised | 72 | 0 | 192 | 629 | 1.0000 | 0.2727 | 0.4286 | 1.0000 |
| B3_JaroWinkler | 215 | 13 | 49 | 616 | 0.9430 | 0.8144 | 0.8740 | 1.0000 |
| B4_TFIDF | 197 | 54 | 67 | 575 | 0.7849 | 0.7462 | 0.7650 | 1.0000 |
| B5_Embedding | 206 | 7 | 58 | 622 | 0.9671 | 0.7803 | 0.8637 | 1.0000 |
| Primary_M7 | 250 | 6 | 11 | 601 | 0.9766 | 0.9579 | 0.9671 | 0.9720 |
| B6 | 249 | 48 | 15 | 581 | 0.8384 | 0.9432 | 0.8877 | 1.0000 |
| B7 | 255 | 26 | 9 | 603 | 0.9075 | 0.9659 | 0.9358 | 1.0000 |
| B8 | 160 | 6 | 104 | 623 | 0.9639 | 0.6061 | 0.7442 | 1.0000 |
| OpenAI_Robustness | 245 | 22 | 3 | 417 | 0.9176 | 0.9879 | 0.9515 | 0.7693 |

## Three-way evaluation (all gold labels included; uncertain treated descriptively)

### ce400

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| B1_Exact | 0.8075 | 0.4524 |
| B2_Normalised | 0.8075 | 0.4524 |
| B3_JaroWinkler | 0.9375 | 0.6208 |
| B4_TFIDF | 0.8600 | 0.5566 |
| B5_Embedding | 0.9425 | 0.6245 |
| Primary_M7 | 0.9350 | 0.7717 |
| B6 | 0.8875 | 0.5821 |
| B7 | 0.9275 | 0.6128 |
| B8 | 0.7850 | 0.4242 |
| OpenAI_Robustness | 0.6850 | 0.5878 |

### diabetes500

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| B1_Exact | 0.7560 | 0.4150 |
| B2_Normalised | 0.7560 | 0.4150 |
| B3_JaroWinkler | 0.9120 | 0.5970 |
| B4_TFIDF | 0.8560 | 0.5537 |
| B5_Embedding | 0.9020 | 0.5875 |
| Primary_M7 | 0.9660 | 0.6470 |
| B6 | 0.9500 | 0.6297 |
| B7 | 0.9740 | 0.6479 |
| B8 | 0.9380 | 0.6182 |
| OpenAI_Robustness | 0.7880 | 0.5853 |

### pooled900

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| B1_Exact | 0.7789 | 0.4307 |
| B2_Normalised | 0.7789 | 0.4307 |
| B3_JaroWinkler | 0.9233 | 0.6070 |
| B4_TFIDF | 0.8578 | 0.5550 |
| B5_Embedding | 0.9200 | 0.6030 |
| Primary_M7 | 0.9522 | 0.7484 |
| B6 | 0.9222 | 0.6092 |
| B7 | 0.9533 | 0.6331 |
| B8 | 0.8700 | 0.5528 |
| OpenAI_Robustness | 0.7422 | 0.5906 |

## Paired bootstrap (Primary M7 vs. baselines, F1, N=10000, seed=42)

### ce400

- Primary_M7_vs_B3_JaroWinkler: diff=0.0566, 95% CI=[0.0188, 0.0991], excludes_zero=True
- Primary_M7_vs_B5_Embedding: diff=0.0492, 95% CI=[0.0086, 0.0917], excludes_zero=True
- Primary_M7_vs_B6: diff=0.1271, 95% CI=[0.0816, 0.1781], excludes_zero=True
- Primary_M7_vs_B7: diff=0.0652, 95% CI=[0.0344, 0.1002], excludes_zero=True
- Primary M7 F1 95% CI: [0.9312, 0.9858] (point=0.9612)

### diabetes500

- Primary_M7_vs_B3_JaroWinkler: diff=0.1178, 95% CI=[0.0779, 0.1615], excludes_zero=True
- Primary_M7_vs_B5_Embedding: diff=0.1401, 95% CI=[0.0980, 0.1872], excludes_zero=True
- Primary_M7_vs_B6: diff=0.0447, 95% CI=[0.0160, 0.0757], excludes_zero=True
- Primary_M7_vs_B7: diff=0.0081, 95% CI=[-0.0138, 0.0304], excludes_zero=False
- Primary M7 F1 95% CI: [0.9504, 0.9877] (point=0.9711)

### pooled900

- Primary_M7_vs_B3_JaroWinkler: diff=0.0931, 95% CI=[0.0638, 0.1238], excludes_zero=True
- Primary_M7_vs_B5_Embedding: diff=0.1034, 95% CI=[0.0732, 0.1346], excludes_zero=True
- Primary_M7_vs_B6: diff=0.0794, 95% CI=[0.0539, 0.1067], excludes_zero=True
- Primary_M7_vs_B7: diff=0.0313, 95% CI=[0.0128, 0.0508], excludes_zero=True
- Primary M7 F1 95% CI: [0.9501, 0.9816] (point=0.9671)

## Selective prediction (genuine confidence only: Primary M7, OpenAI)

### Primary_M7

| Partition | N (binary) | Coverage | Risk | AURC |
|---|---:|---:|---:|---:|
| ce400 | 394 | 1.0000 | 0.0660 | 0.0128 |
| diabetes500 | 499 | 1.0000 | 0.0321 | 0.0048 |
| pooled900 | 893 | 1.0000 | 0.0470 | 0.0079 |

### OpenAI_Robustness

| Partition | N (binary) | Coverage | Risk | AURC |
|---|---:|---:|---:|---:|
| ce400 | 394 | 1.0000 | 0.3198 | 0.0650 |
| diabetes500 | 499 | 1.0000 | 0.2104 | 0.0332 |
| pooled900 | 893 | 1.0000 | 0.2587 | 0.0453 |

## Transitivity diagnostic (lower-bound safety diagnostic, not complete cluster metric)

Closed triangles observed: 6 -- descriptive only -- too few (6) to support a stable consistency estimate; not forced.

| Method | Gold non-match evaluated | Connected incorrectly | Direct | Transitive-only |
|---|---:|---:|---:|---:|
| B1_Exact | 629 | 0 | 0 | 0 |
| B2_Normalised | 629 | 0 | 0 | 0 |
| B3_JaroWinkler | 629 | 13 | 13 | 0 |
| B4_TFIDF | 629 | 54 | 54 | 0 |
| B5_Embedding | 629 | 7 | 7 | 0 |
| Primary_M7 | 629 | 6 | 6 | 0 |
| B6 | 629 | 48 | 48 | 0 |
| B7 | 629 | 26 | 26 | 0 |
| B8 | 629 | 6 | 6 | 0 |
| OpenAI_Robustness | 629 | 22 | 22 | 0 |