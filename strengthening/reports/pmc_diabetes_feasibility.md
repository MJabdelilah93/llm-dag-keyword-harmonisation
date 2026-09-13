# PMC diabetes-mellitus feasibility report (activated fallback)

Generated: 2026-09-07T09:39:36.934281+00:00
Hypertension (primary topic) is documented as a failed feasibility outcome and is preserved unmodified in strengthening/reports/pmc_hypertension_feasibility.{json,md}; this is a separate, new feasibility run for the pre-specified fallback topic, not a correction of the hypertension result.

## API/service and query
- Services: NCBI E-utilities esearch, NCBI E-utilities efetch, PMC OAI-PMH GetRecord
- Topic-evidence terms (title/abstract only): ['diabetes mellitus', 'type 1 diabetes', 'type 2 diabetes']
- Exact query string: ("diabetes mellitus"[Title/Abstract] OR "type 1 diabetes"[Title/Abstract] OR "type 2 diabetes"[Title/Abstract]) AND ("2015/01/01"[PDAT] : "2025/12/31"[PDAT]) AND english[Language]
- Date range: 2015-01-01 to 2025-12-31
- Retrieval window (UTC): 2026-09-07T08:06:30.190508+00:00 to 2026-09-07T09:17:42.635739+00:00
- Broader time window tested: False

## Filter funnel
- Raw esearch (unfiltered) result count: 141860
- Fetched (efetch requested): 15106
- Parsed: 15106
- Unique PMCIDs: 15106
- Total records found (this acquisition's inventory): 15106
- Passing language filter: 15098
- Passing date filter: 15093
- Passing topic filter (title/abstract only): 14913
- With abstract present: 14851
- CC BY: 12977, CC0: 76
- Excluded-licence counts by reason: {'non_permitted_licence_cc_by_nc_nd': 869, 'non_permitted_licence_cc_by_nc': 684, 'unclear_or_unrecognised_licence': 215, 'non_permitted_licence_cc_by_nc_sa': 196, 'no_license_element': 81, 'non_permitted_licence_cc_by_nd': 8}
- With any keyword group: 14043
- With confident author keywords: 1312
- Ambiguous keyword-group count (excluded from benchmark): 12807
- **Fully eligible articles: 1066**
- Duplicate PMCID check: 0
- Duplicate DOI check: 0
- Missing title / missing abstract: 2053 / 255

## Keyword statistics (strict: fully-eligible articles, confidently-author groups only)
- Total author-keyword occurrences: 6029
- Unique raw author-keyword strings: 4092
- Contributing articles: 1066
- Character-pattern flags on unique keywords: {'punctuation': 254, 'hyphen': 492, 'uppercase_acronym_like': 80, 'digits': 293, 'parentheses': 211}

## Ten-stratum candidate pool sizes (target: strengthening/config/protocol_v1.yaml stratum_quotas.biomedical_500)
- stratum i: available=176, quota=40, OK
- stratum ii: available=3641, quota=45, OK
- stratum iii: available=312, quota=55, OK
- stratum iv: available=40, quota=40, OK
- stratum v: available=41, quota=35, OK
- stratum vi: available=971, quota=75, OK
- stratum vii: available=5204, quota=75, OK
- stratum viii: available=601, quota=60, OK
- stratum ix: available=90, quota=35, OK
- stratum x: available=8811, quota=40, OK

## Gate result: all ten strata achievable = **True**

NCBI rate-limit policy: anonymous ~3 req/s (no API key configured); min inter-request interval 0.4s; total live requests: 1003