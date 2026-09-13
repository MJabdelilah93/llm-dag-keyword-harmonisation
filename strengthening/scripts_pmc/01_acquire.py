"""Stage 3 (biomedical track) -- acquisition from official PMC/NCBI endpoints.

Two-pass design
---------------
Pass A -- "population_probe".  The frozen hypertension query over the PMC Open
Access subset with no licence targeting.  This gives *unbiased* population
rates for the funnel (what fraction of OA hypertension articles are CC BY/CC0,
what fraction carry explicitly author-typed keyword groups).

Pass B -- "working_corpus".  The same frozen topic/date/language query plus a
licence-targeting clause.  NOTE: PMC silently remaps `[license]` to
`[All Fields]` (verifiable in the esearch `querytranslation`), so this clause
is a *full-text string match*, not a true licence field.  It is therefore used
purely as a retrieval-efficiency device, never as evidence of licence: every
article's licence is independently verified from the JATS <permissions>
element, and contributing articles are re-verified against PMC OAI-PMH.

Because Pass B is a biased sample of the literature, funnel *rates* are always
reported from Pass A; Pass B only supplies the candidate keyword pool.

No labels of any kind are produced here.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pmc_common as pc  # noqa: E402

TOPIC_KEY = "hypertension"


# --------------------------------------------------------------------------
# Query construction (from frozen config only)
# --------------------------------------------------------------------------

def build_terms(cfg: dict, topic_key: str = TOPIC_KEY,
                start_override: str | None = None) -> dict:
    bio = cfg["biomedical"]
    ev = cfg["topic_inclusion_evidence"][topic_key]
    clauses = []
    for t in ev:
        t = t.strip().strip('"')
        clauses.append(f'"{t}"[Title/Abstract]' if " " in t else f"{t}[Title/Abstract]")
    topic = "(" + " OR ".join(clauses) + ")"

    def _d(v) -> str:
        return v.replace("-", "/") if isinstance(v, str) else v.strftime("%Y/%m/%d")

    start = start_override or _d(bio["primary_start_date"])
    end = _d(bio["primary_end_date"])
    date_clause = f'("{start}"[PDAT] : "{end}"[PDAT])'
    lang_clause = f'{bio["language"].lower()}[Language]'
    base = f"{topic} AND {date_clause} AND {lang_clause}"

    # Licence-targeting clause (retrieval efficiency only -- see module docstring).
    lic_incl = '("cc by"[license] OR "cc0"[license])'
    lic_excl = ('NOT ("cc by-nc"[license] OR "cc by-nd"[license] OR "cc by-sa"[license] '
                'OR "cc by-nc-nd"[license] OR "cc by-nc-sa"[license])')
    return {
        "topic_key": topic_key,
        "topic_clause": topic,
        "date_clause": date_clause,
        "language_clause": lang_clause,
        "query_unfiltered": base,
        "query_open_access": f'{base} AND "open access"[Filter]',
        "query_licence_targeted": f"{base} AND {lic_incl} {lic_excl}",
        "licence_targeting_note": (
            "PMC maps [license] to [All Fields]; this clause is a full-text "
            "string match used only to raise retrieval efficiency. Licence "
            "eligibility is decided solely by JATS <permissions>, cross-checked "
            "against PMC OAI-PMH."),
        "start_date": start, "end_date": end,
    }


def year_clause(y: int) -> str:
    return f'("{y}/01/01"[PDAT] : "{y}/12/31"[PDAT])'


def per_year_query(terms: dict, year: int, pass_name: str) -> str:
    base = f'{terms["topic_clause"]} AND {year_clause(year)} AND {terms["language_clause"]}'
    if pass_name == "population_probe":
        return f'{base} AND "open access"[Filter]'
    lic_incl = '("cc by"[license] OR "cc0"[license])'
    lic_excl = ('NOT ("cc by-nc"[license] OR "cc by-nd"[license] OR "cc by-sa"[license] '
                'OR "cc by-nc-nd"[license] OR "cc by-nc-sa"[license])')
    return f"{base} AND {lic_incl} {lic_excl}"


# --------------------------------------------------------------------------
# E-utilities helpers
# --------------------------------------------------------------------------

def esearch_count(client: pc.NCBIClient, term: str) -> tuple[int, str]:
    r = client.get(pc.ESEARCH_URL, {"db": "pmc", "term": term, "retmax": 0, "retmode": "json"})
    res = r.json()["esearchresult"]
    return int(res["count"]), res.get("querytranslation", "")


def esearch_ids(client: pc.NCBIClient, term: str, retmax: int) -> tuple[list[str], int]:
    r = client.get(pc.ESEARCH_URL, {
        "db": "pmc", "term": term, "retmax": retmax, "retstart": 0,
        "retmode": "json", "sort": "pub_date",
    })
    res = r.json()["esearchresult"]
    return list(res.get("idlist", [])), int(res.get("count", 0))


def fetch_batch(client: pc.NCBIClient, chunk: list[str]) -> tuple[bytes, str, bool]:
    """Content-addressed efetch with on-disk cache (raw dir is gitignored)."""
    key = pc.sha256_bytes(",".join(chunk).encode())[:16]
    name = f"efetch_{key}"
    cached = pc.load_raw(name)
    if cached is not None:
        return cached, name, True
    resp = client.get(pc.EFETCH_URL, {
        "db": "pmc", "id": ",".join(chunk), "rettype": "full", "retmode": "xml",
    }, timeout=300, post=True)
    pc.save_raw(name, resp.content)
    return resp.content, name, False


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-per-year", type=int, default=120,
                    help="unbiased population-probe articles per year")
    ap.add_argument("--corpus-per-year", type=int, default=1200,
                    help="licence-targeted working-corpus articles per year")
    ap.add_argument("--batch-size", type=int, default=40)
    ap.add_argument("--years", default="2015-2025")
    ap.add_argument("--topic", default=TOPIC_KEY)
    ap.add_argument("--start-override", default=None,
                    help="broader pre-specified start date, e.g. 2010/01/01")
    ap.add_argument("--oai-crosscheck", type=int, default=150,
                    help="how many eligible articles to cross-check via OAI-PMH")
    ap.add_argument("--out-prefix", default="pmc_hypertension")
    args = ap.parse_args()

    y0, y1 = (int(x) for x in args.years.split("-"))
    cfg = pc.load_config()
    terms = build_terms(cfg, args.topic, args.start_override)
    topic_res = pc.build_topic_regexes(cfg["topic_inclusion_evidence"][args.topic])

    client = pc.NCBIClient()
    started = datetime.now(timezone.utc)
    print(f"[{started.isoformat()}] start; api_key_in_use={client.using_api_key} "
          f"min_interval={client.min_interval}s", flush=True)
    for k in ("query_unfiltered", "query_open_access", "query_licence_targeted"):
        print(f"{k}: {terms[k]}", flush=True)

    counts = {}
    for k in ("query_unfiltered", "query_open_access", "query_licence_targeted"):
        n, qt = esearch_count(client, terms[k])
        counts[k] = {"count": n, "query_translation": qt}
        print(f"  esearch {k}: {n}", flush=True)

    # ---- id selection, both passes ----------------------------------------
    passes = [("population_probe", args.probe_per_year),
              ("working_corpus", args.corpus_per_year)]
    pass_ids: dict[str, list[str]] = {}
    per_year_totals: dict[str, dict[str, int]] = {}
    for pass_name, per_year in passes:
        if per_year <= 0:
            pass_ids[pass_name] = []
            continue
        ids, seen, totals = [], set(), {}
        for year in range(y0, y1 + 1):
            got, total = esearch_ids(client, per_year_query(terms, year, pass_name), per_year)
            totals[str(year)] = total
            new = [i for i in got if i not in seen]
            seen.update(new)
            ids.extend(new)
        pass_ids[pass_name] = ids
        per_year_totals[pass_name] = totals
        print(f"  pass {pass_name}: {len(ids)} unique UIDs "
              f"(per-year totals available: {sum(totals.values())})", flush=True)

    # UID -> set of passes it belongs to (an article may appear in both)
    uid_passes: dict[str, set[str]] = {}
    for pass_name, ids in pass_ids.items():
        for i in ids:
            uid_passes.setdefault(i, set()).add(pass_name)
    all_ids = list(uid_passes.keys())
    print(f"total unique UIDs to fetch: {len(all_ids)}", flush=True)

    # ---- efetch ------------------------------------------------------------
    records: list[tuple[pc.ArticleRecord, str]] = []
    batch_meta = []
    n_cached = 0
    nbatch = (len(all_ids) + args.batch_size - 1) // args.batch_size
    for bi in range(nbatch):
        chunk = all_ids[bi * args.batch_size:(bi + 1) * args.batch_size]
        raw, name, was_cached = fetch_batch(client, chunk)
        n_cached += int(was_cached)
        batch_meta.append({"batch": name, "n_ids": len(chunk), "bytes": len(raw),
                           "sha256": pc.sha256_bytes(raw), "from_cache": was_cached})
        try:
            recs = pc.parse_articleset(raw)
        except Exception as exc:
            print(f"  !! batch {bi} parse failure: {exc}", flush=True)
            recs = []
        for r in recs:
            records.append((r, name))
        if bi % 25 == 0 or bi == nbatch - 1:
            print(f"  efetch batch {bi + 1}/{nbatch} -> {len(records)} records "
                  f"({client.request_count} live requests, {n_cached} cached)", flush=True)

    fetched = datetime.now(timezone.utc)
    print(f"[{fetched.isoformat()}] parsed {len(records)} article records", flush=True)

    # ---- evaluate funnel ---------------------------------------------------
    by_pmcid: dict[str, dict] = {}
    kw_rows, kwgroup_rows = [], []
    dup_pmcid_hits, no_pmcid = 0, 0

    for rec, batch_name in records:
        if not rec.pmcid:
            no_pmcid += 1
            continue
        uid = rec.pmcid.upper().replace("PMC", "")
        pass_tags = "|".join(sorted(uid_passes.get(uid, {"unknown"})))

        year_ok = rec.pub_year.isdigit() and y0 <= int(rec.pub_year) <= y1
        hits = pc.topic_evidence_hits(rec.title, rec.abstract, topic_res)
        topic_ok = bool(hits)
        abstract_ok = len(rec.abstract.strip()) > 0
        lang_ok = (not rec.xml_lang) or rec.xml_lang.lower().startswith("en")
        lic = rec.licence
        lic_ok = lic.eligible
        author_kg = rec.has_confident_author_kwds

        release_ok = bool(year_ok and topic_ok and abstract_ok and lic_ok and lang_ok)
        fully = bool(release_ok and author_kg)

        if rec.pmcid in by_pmcid:
            dup_pmcid_hits += 1
            continue

        by_pmcid[rec.pmcid] = {
            "pmcid": rec.pmcid, "pmid": rec.pmid, "doi": rec.doi,
            "corpus_pass": pass_tags,
            "journal": rec.journal if lic_ok else "",
            "pub_year": rec.pub_year, "pub_date": rec.pub_date,
            "article_type": rec.article_type, "xml_lang": rec.xml_lang,
            # Title text is retained in this tracked file only for
            # licence-eligible (CC BY / CC0) articles.
            "title": rec.title if lic_ok else "",
            "abstract_char_len": len(rec.abstract),
            "licence_code": lic.code, "licence_label": lic.label,
            "licence_version": lic.version, "licence_url": lic.url,
            "licence_type_attr": lic.license_type_attr,
            "licence_content_type_attr": lic.content_type_attr,
            "licence_signal_source": lic.source,
            "licence_exclusion_reason": lic.exclusion_reason,
            "flag_language_english": int(lang_ok),
            "flag_date_in_window": int(year_ok),
            "flag_topic_evidence": int(topic_ok),
            "topic_evidence_terms_hit": "|".join(hits),
            "flag_abstract_present": int(abstract_ok),
            "flag_licence_ccby_or_cc0": int(lic_ok),
            "flag_any_kwd_group": int(rec.has_any_kwd_group),
            "flag_confident_author_kwds": int(author_kg),
            "n_kwd_groups": len(rec.kwd_groups),
            "n_ambiguous_kwd_groups": rec.n_ambiguous_groups,
            "n_author_keywords": len(rec.author_keywords),
            "flag_eligible_for_release": int(release_ok),
            "flag_fully_eligible": int(fully),
            "oai_licence_code": "", "oai_licence_agrees": "",
            "oai_setspecs": "", "raw_batch": batch_name,
            "parse_error": rec.parse_error,
        }

        for g in rec.kwd_groups:
            kwgroup_rows.append({
                "pmcid": rec.pmcid, "corpus_pass": pass_tags,
                "group_index": g.group_index,
                "kwd_group_type": g.group_type, "xml_lang": g.xml_lang,
                "group_title": g.title_text, "group_label": g.label_text,
                "n_keywords": len(g.keywords),
                "classification": g.classification,
                "classification_reason": g.classification_reason,
                "article_licence_code": lic.code,
                "article_licence_eligible": int(lic_ok),
            })
            if not lic_ok:
                continue  # keyword strings written only for CC BY / CC0 articles
            for kw in g.keywords:
                kw_rows.append({
                    "pmcid": rec.pmcid, "pmid": rec.pmid, "doi": rec.doi,
                    "corpus_pass": pass_tags, "pub_year": rec.pub_year,
                    "licence_code": lic.code, "licence_label": lic.label,
                    "group_index": g.group_index, "kwd_group_type": g.group_type,
                    "group_classification": g.classification,
                    "keyword_raw": kw, "keyword_normalised": pc.normalise(kw),
                    "article_date_ok": int(year_ok),
                    "article_topic_ok": int(topic_ok),
                    "article_abstract_ok": int(abstract_ok),
                    "article_fully_eligible": int(fully),
                })

    # ---- OAI-PMH licence cross-check --------------------------------------
    eligible_pmcids = sorted([p for p, r in by_pmcid.items() if r["flag_fully_eligible"]])
    sample = eligible_pmcids[:: max(1, len(eligible_pmcids) // max(args.oai_crosscheck, 1))]
    sample = sample[:args.oai_crosscheck]
    oai_agree = oai_disagree = oai_err = 0
    oai_disagreements = []
    print(f"OAI-PMH cross-check on {len(sample)} fully-eligible articles ...", flush=True)
    for pmcid in sample:
        info, sets, err = pc.oai_licence(client, pmcid)
        row = by_pmcid[pmcid]
        row["oai_licence_code"] = info.code
        row["oai_setspecs"] = "|".join(sets)
        if err:
            oai_err += 1
            row["oai_licence_agrees"] = "error"
            continue
        agrees = (info.code == row["licence_code"])
        row["oai_licence_agrees"] = int(agrees)
        if agrees:
            oai_agree += 1
        else:
            oai_disagree += 1
            oai_disagreements.append(
                {"pmcid": pmcid, "jats": row["licence_code"], "oai": info.code})
    print(f"  OAI agree={oai_agree} disagree={oai_disagree} error={oai_err}", flush=True)

    # ---- write -------------------------------------------------------------
    pc.INVENTORY_DIR.mkdir(parents=True, exist_ok=True)

    def write_csv(path: Path, rows: list[dict]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            if not rows:
                return
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    inv_rows = list(by_pmcid.values())
    inv_path = pc.INVENTORY_DIR / f"{args.out_prefix}_article_inventory.csv"
    kwg_path = pc.INVENTORY_DIR / f"{args.out_prefix}_kwd_groups.csv"
    kw_path = pc.INVENTORY_DIR / f"{args.out_prefix}_author_keywords_raw.csv"
    write_csv(inv_path, inv_rows)
    write_csv(kwg_path, kwgroup_rows)
    write_csv(kw_path, kw_rows)

    finished = datetime.now(timezone.utc)
    manifest = {
        "track": f"biomedical_{args.topic}",
        "stage": "3_acquisition",
        "topic_key": args.topic,
        "start_date_override_used": args.start_override,
        "retrieval_started_utc": started.isoformat(),
        "retrieval_finished_utc": finished.isoformat(),
        "services_used": [
            {"name": "NCBI E-utilities esearch", "url": pc.ESEARCH_URL, "db": "pmc"},
            {"name": "NCBI E-utilities efetch", "url": pc.EFETCH_URL,
             "db": "pmc", "rettype": "full", "retmode": "xml"},
            {"name": "PMC OAI-PMH GetRecord", "url": pc.OAI_URL,
             "metadataPrefix": "pmc_fm", "role": "independent licence cross-check"},
        ],
        "pmc_oa_service_note": (
            "The historical PMC OA Service endpoint /pmc/utils/oa/oa.cgi was probed "
            "on both www.ncbi.nlm.nih.gov and pmc.ncbi.nlm.nih.gov and returned HTTP 404 "
            "(retired/migrated). PMC OAI-PMH pmc_fm front matter was used instead as the "
            "second official licence source."),
        "ncbi_api_key_used": client.using_api_key,
        "rate_limit_policy": (f"anonymous ~3 req/s (no API key configured); min "
                              f"inter-request interval {client.min_interval}s"),
        "total_live_ncbi_requests": client.request_count,
        "cached_batches_reused": n_cached,
        "retry_events": client.retry_events,
        "queries": terms,
        "esearch_counts": counts,
        "per_year_available_totals": per_year_totals,
        "probe_per_year": args.probe_per_year,
        "corpus_per_year": args.corpus_per_year,
        "efetch_batch_size": args.batch_size,
        "n_uids_requested": len(all_ids),
        "n_article_records_parsed": len(records),
        "n_unique_pmcids": len(by_pmcid),
        "n_records_without_pmcid": no_pmcid,
        "n_duplicate_pmcid_records_dropped": dup_pmcid_hits,
        "oai_crosscheck": {"n_checked": len(sample), "agree": oai_agree,
                           "disagree": oai_disagree, "errors": oai_err,
                           "disagreements": oai_disagreements[:50]},
        "raw_xml_batches": batch_meta,
        "outputs": {
            "article_inventory": str(inv_path.relative_to(pc.REPO_ROOT)).replace("\\", "/"),
            "kwd_groups": str(kwg_path.relative_to(pc.REPO_ROOT)).replace("\\", "/"),
            "author_keywords_raw": str(kw_path.relative_to(pc.REPO_ROOT)).replace("\\", "/"),
        },
    }
    mpath = pc.INVENTORY_DIR / f"{args.out_prefix}_acquisition_manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {inv_path.name} ({len(inv_rows)} rows), {kwg_path.name} "
          f"({len(kwgroup_rows)}), {kw_path.name} ({len(kw_rows)}), {mpath.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
