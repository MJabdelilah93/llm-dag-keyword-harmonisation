# PMC hypertension feasibility report

Generated: 2026-09-07T06:51:29.692534+00:00

## API/service and query
- Services: NCBI E-utilities esearch, NCBI E-utilities efetch, PMC OAI-PMH GetRecord
- Topic-evidence terms (title/abstract only): ['hypertens*', 'high blood pressure']
- Primary date range: 2015-01-01 to 2025-12-31
- Extended date range tested: 2010-01-01 to 2025-12-31
- Primary retrieval window (UTC): 2026-09-06T16:13:00.687174+00:00 to 2026-09-06T17:21:14.197353+00:00
- Extended retrieval window (UTC): 2026-09-06T20:10:33.133922+00:00 to 2026-09-06T21:20:31.900293+00:00
- Broader time window tested: True (2010-01-01 (primary 2015-01-01 was insufficient for stratum iv alone; merged with primary rather than replacing it))
- Diabetes fallback activated: False

## Filter funnel
- Total records found (raw esearch): 15368
- Passing language filter: 15343
- Passing date filter: 15342
- Passing topic filter (title/abstract only): 15311
- With abstract present: 15079
- CC BY: 12769, CC0: 97
- Excluded-licence counts by reason: {'non_permitted_licence_cc_by_nc_nd': 1127, 'non_permitted_licence_cc_by_nc': 874, 'non_permitted_licence_cc_by_nc_sa': 252, 'unclear_or_unrecognised_licence': 162, 'no_license_element': 74, 'non_permitted_licence_cc_by_nd': 9, 'non_permitted_licence_cc_by_sa': 3, 'non_permitted_licence_cc_cc_by': 1}
- With any keyword group: 13982
- With confident author keywords: 1635
- Ambiguous keyword-group count (excluded from benchmark): 12425
- **Fully eligible articles: 1364**

## Keyword statistics (strict: fully-eligible articles, confidently-author groups only)
- Total author-keyword occurrences: 7633
- Unique raw author-keyword strings: 5283
- Contributing articles: 1364
- Keywords-per-article distribution: {'count': 1364.0, 'mean': 5.596041055718475, 'std': 1.5687751533618475, 'min': 1.0, '25%': 5.0, '50%': 5.0, '75%': 6.0, 'max': 23.0}
- Duplicate PMCID check: 0
- Duplicate DOI check: 0
- Character-pattern flags on unique keywords: {'punctuation': 295, 'hyphen': 508, 'uppercase_acronym_like': 75, 'digits': 166, 'parentheses': 227}

## Ten-stratum candidate pool sizes (target: strengthening/config/protocol_v1.yaml stratum_quotas.biomedical_500)
- stratum i: available=178, quota=40, OK
- stratum ii: available=5561, quota=45, OK
- stratum iii: available=332, quota=55, OK
- stratum iv: available=36, quota=40, SHORTFALL of 4
- stratum v: available=61, quota=35, OK
- stratum vi: available=1407, quota=75, OK
- stratum vii: available=8164, quota=75, OK
- stratum viii: available=793, quota=60, OK
- stratum ix: available=38, quota=35, OK
- stratum x: available=14109, quota=40, OK

## Gate result: all ten strata achievable = **False**

NCBI rate-limit policy: anonymous ~3 req/s (no API key configured); min inter-request interval 0.4s; total live requests: 992