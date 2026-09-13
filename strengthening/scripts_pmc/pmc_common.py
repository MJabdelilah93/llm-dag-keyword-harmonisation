"""Shared utilities for the M7 biomedical (PMC / hypertension) track.

Scope of this module
--------------------
* Rate-limited access to *official NCBI/PMC endpoints only*
  (E-utilities `esearch`/`efetch`, PMC OAI-PMH).  No HTML scraping,
  no third-party services, no LLM APIs anywhere in this track.
* Conservative JATS front-matter parsing (lxml).
* Licence classification restricted to the protocol's allowed set
  (exactly CC BY, any version, or CC0).
* Conservative author-keyword-group classification.
* The frozen deterministic normalisation from
  `strengthening/config/protocol_v1.yaml` -> `normalisation.steps`.

Nothing in this module assigns, infers or reads a gold match label.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml
from lxml import etree

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
STRENGTHENING = REPO_ROOT / "strengthening"
CONFIG_PATH = STRENGTHENING / "config" / "protocol_v1.yaml"
DATA_RAW_PMC = STRENGTHENING / "data_raw" / "pmc"          # gitignored
INVENTORY_DIR = STRENGTHENING / "data_pmc"                  # tracked (CC BY/CC0 only)
REPORTS_DIR = STRENGTHENING / "reports"
BENCHMARK_DIR = STRENGTHENING / "benchmark"
RETRIEVAL_AUDIT_DIR = STRENGTHENING / "retrieval_audit"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# --------------------------------------------------------------------------
# Official NCBI endpoints
# --------------------------------------------------------------------------

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESEARCH_URL = f"{EUTILS}/esearch.fcgi"
EFETCH_URL = f"{EUTILS}/efetch.fcgi"

# PMC OAI-PMH service (used as the second, independent official licence
# source).  The historical PMC OA Service (`.../pmc/utils/oa/oa.cgi`) was
# probed on 2026-09-06 on both the legacy `www.ncbi.nlm.nih.gov` host and the
# current `pmc.ncbi.nlm.nih.gov` host and returned HTTP 404 (retired /
# migrated), so OAI-PMH `pmc_fm` front matter is used instead.  This is an
# explicitly permitted official PMC endpoint.
OAI_URL = "https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi"

TOOL_NAME = "m7-concept-harmonisation-strengthening"
TOOL_EMAIL = "abdel.elmajjaoui@assistdigital.nl"

# Anonymous NCBI rate limit is ~3 requests/second.  No API key is configured
# for this run; we simply run at the anonymous rate.
_ANON_MIN_INTERVAL = 0.40
_KEYED_MIN_INTERVAL = 0.11


class NCBIClient:
    """Minimal rate-limited client for official NCBI/PMC endpoints."""

    def __init__(self, api_key: str | None = None) -> None:
        # An API key is used only if one is already present in the
        # environment.  Its value is never logged or written anywhere.
        self.api_key = api_key or os.environ.get("NCBI_API_KEY") or os.environ.get("ENTREZ_API_KEY")
        self.min_interval = _KEYED_MIN_INTERVAL if self.api_key else _ANON_MIN_INTERVAL
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": f"{TOOL_NAME} (mailto:{TOOL_EMAIL})"})
        self._last = 0.0
        self.request_count = 0
        self.retry_events: list[str] = []

    @property
    def using_api_key(self) -> bool:
        return bool(self.api_key)

    def _throttle(self) -> None:
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()

    def _common_params(self, params: dict) -> dict:
        out = dict(params)
        out.setdefault("tool", TOOL_NAME)
        out.setdefault("email", TOOL_EMAIL)
        if self.api_key:
            out["api_key"] = self.api_key
        return out

    def get(self, url: str, params: dict, *, timeout: int = 120,
            max_retries: int = 4, post: bool = False) -> requests.Response:
        allowed = ("https://eutils.ncbi.nlm.nih.gov/", "https://www.ncbi.nlm.nih.gov/pmc/oai/")
        if not url.startswith(allowed):
            raise ValueError(f"Refusing non-NCBI endpoint: {url}")
        params = self._common_params(params)
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            self._throttle()
            try:
                if post:
                    resp = self.session.post(url, data=params, timeout=timeout)
                else:
                    resp = self.session.get(url, params=params, timeout=timeout)
                self.request_count += 1
                if resp.status_code == 200:
                    return resp
                if resp.status_code in (429, 500, 502, 503, 504):
                    self.retry_events.append(f"HTTP {resp.status_code} on attempt {attempt + 1}")
                    time.sleep(2.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
            except requests.RequestException as exc:  # network hiccup
                last_exc = exc
                self.retry_events.append(f"{type(exc).__name__} on attempt {attempt + 1}")
                time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(f"NCBI request failed after {max_retries} attempts: {url} ({last_exc})")


# --------------------------------------------------------------------------
# Frozen deterministic normalisation (protocol_v1.yaml -> normalisation)
# --------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Unicode NFKC -> lowercase -> strip -> collapse internal whitespace.

    Deliberately does NOT strip punctuation, expand acronyms, stem, lemmatise
    or remove stopwords -- those are `excluded_by_policy` in the protocol.
    """
    if text is None:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    s = s.lower()
    s = s.strip()
    s = _WS_RE.sub(" ", s)
    return s


def pair_key(a: str, b: str) -> str:
    """Canonical unordered pair key over normalised strings."""
    x, y = sorted([normalise(a), normalise(b)])
    return f"{x}||{y}"


def presented_pair_key(a: str, b: str) -> str:
    """Canonical unordered key over the strings *as presented to annotators*.

    Stratum i (capitalisation / whitespace variants) presents two raw surface
    forms whose normalised forms are identical, so a key built on normalised
    strings would collapse every such pair to a degenerate `x||x`.  The
    canonical key is therefore built on NFKC-normalised *presented* strings,
    which is still fully content-derived and run-order independent.
    """
    x, y = sorted([unicodedata.normalize("NFKC", a or ""),
                   unicodedata.normalize("NFKC", b or "")])
    return f"{x}||{y}"


def pair_id(a: str, b: str, prefix: str = "bio_") -> str:
    """Content-hash-derived, run-order-independent pair identifier.

    `bio_` + first 12 hex chars of sha256(canonical presented pair key).
    """
    digest = hashlib.sha256(presented_pair_key(a, b).encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:12]}"


# --------------------------------------------------------------------------
# Licence classification
# --------------------------------------------------------------------------

_CC_URL_RE = re.compile(
    r"creativecommons\.org/(?:licenses|licences)/([a-z][a-z\-]*)/?\s*([0-9]+\.[0-9]+)?", re.I)
_CC0_URL_RE = re.compile(r"creativecommons\.org/publicdomain/(zero|mark)/([0-9.]+)?", re.I)

# `content-type` tokens used by PMC on <ali:license_ref>.
_CONTENT_TYPE_MAP = {
    "ccbylicense": "by",
    "ccbynclicense": "by-nc",
    "ccbyncndlicense": "by-nc-nd",
    "ccbyncsalicense": "by-nc-sa",
    "ccbyndlicense": "by-nd",
    "ccbysalicense": "by-sa",
    "cc0license": "cc0",
    "cczerolicense": "cc0",
    "ccbyigolicense": "by",
}

ELIGIBLE_CODES = {"by", "cc0"}


@dataclass
class LicenceInfo:
    code: str = "unknown"          # 'by', 'by-nc', ..., 'cc0', 'unknown', 'none'
    version: str = ""
    url: str = ""
    license_type_attr: str = ""
    content_type_attr: str = ""
    source: str = ""               # which signal decided the code
    raw_text: str = ""

    @property
    def label(self) -> str:
        if self.code == "cc0":
            return "CC0"
        if self.code == "none":
            return "no-license-element"
        if self.code == "unknown":
            return "unclear-or-unrecognised"
        return "CC " + self.code.upper().replace("-", "-")

    @property
    def eligible(self) -> bool:
        return self.code in ELIGIBLE_CODES

    @property
    def exclusion_reason(self) -> str:
        if self.eligible:
            return ""
        if self.code == "none":
            return "no_license_element"
        if self.code == "unknown":
            return "unclear_or_unrecognised_licence"
        return f"non_permitted_licence_cc_{self.code.replace('-', '_')}"


def _classify_cc_string(s: str) -> tuple[str, str, str] | None:
    """Return (code, version, matched_url) from a URL-bearing string."""
    if not s:
        return None
    m0 = _CC0_URL_RE.search(s)
    if m0:
        return ("cc0", m0.group(2) or "", m0.group(0))
    m = _CC_URL_RE.search(s)
    if m:
        code = m.group(1).lower().strip("-")
        # normalise e.g. 'by-nc-nd' / 'by' / 'zero'
        if code in ("zero", "publicdomain"):
            return ("cc0", m.group(2) or "", m.group(0))
        return (code, m.group(2) or "", m.group(0))
    return None


def _classify_licence_prose(text: str) -> str:
    """Very conservative prose fallback.  Returns a code or 'unknown'."""
    t = " ".join((text or "").lower().split())
    if not t:
        return "unknown"
    if "cc0" in t or "public domain dedication" in t or "creative commons zero" in t:
        return "cc0"
    if "creative commons" not in t and "creativecommons" not in t:
        return "unknown"
    noncomm = "noncommercial" in t or "non-commercial" in t or "non commercial" in t
    noderiv = "noderiv" in t or "no derivative" in t or "no-derivative" in t
    sharealike = "sharealike" in t or "share-alike" in t or "share alike" in t
    attribution = "attribution" in t
    if not attribution:
        return "unknown"
    parts = ["by"]
    if noncomm:
        parts.append("nc")
    if noderiv:
        parts.append("nd")
    if sharealike:
        parts.append("sa")
    return "-".join(parts)


def classify_licence(permissions_el) -> LicenceInfo:
    """Classify a JATS <permissions> element into a CC code.

    Signal priority: explicit CC URL (ali:license_ref / xlink:href) >
    `content-type` token > prose in <license-p>/<copyright-statement>.
    """
    info = LicenceInfo()
    if permissions_el is None:
        info.code = "none"
        return info

    lic = None
    for child in permissions_el.iter():
        if etree.QName(child).localname == "license":
            lic = child
            break
    if lic is None:
        # Some records carry only a copyright statement.
        info.code = "none"
        info.raw_text = " ".join(permissions_el.itertext()).strip()[:400]
        return info

    info.license_type_attr = lic.get("license-type", "") or ""

    urls: list[str] = []
    for k, v in lic.attrib.items():
        if etree.QName(k).localname == "href" and v:
            urls.append(v)
    for child in lic.iter():
        if etree.QName(child).localname == "license_ref":
            ct = child.get("content-type", "")
            if ct and not info.content_type_attr:
                info.content_type_attr = ct
            if child.text:
                urls.append(child.text.strip())
            for k, v in child.attrib.items():
                if etree.QName(k).localname == "href" and v:
                    urls.append(v)
        else:
            for k, v in child.attrib.items():
                if etree.QName(k).localname == "href" and v and "creativecommons" in v:
                    urls.append(v)

    prose = " ".join(lic.itertext()).strip()
    info.raw_text = " ".join(prose.split())[:400]

    for u in urls:
        got = _classify_cc_string(u)
        if got:
            info.code, info.version, info.url = got
            info.source = "cc_url"
            return info

    ct = (info.content_type_attr or "").lower().replace("-", "").replace("_", "")
    if ct in _CONTENT_TYPE_MAP:
        info.code = _CONTENT_TYPE_MAP[ct]
        info.source = "content_type_attr"
        return info

    got = _classify_cc_string(prose)
    if got:
        info.code, info.version, info.url = got
        info.source = "cc_url_in_prose"
        return info

    code = _classify_licence_prose(prose)
    info.code = code
    info.source = "prose" if code != "unknown" else "unresolved"
    return info


# --------------------------------------------------------------------------
# Author-keyword-group classification (CONSERVATIVE)
# --------------------------------------------------------------------------

# `kwd-group-type` values that unambiguously denote author-supplied keywords.
AUTHOR_TYPE_TOKENS = {
    "author", "authors", "authorkeywords", "authorkeyword",
    "authorsuppliedkeywords", "authorgenerated", "authorprovided",
    "kwdauthor",
}

# `kwd-group-type` values that clearly denote indexer / editorial / publisher
# assigned vocabulary -- never treated as author keywords.
NON_AUTHOR_TYPE_SUBSTRINGS = (
    "mesh", "index", "subject", "heading", "classification", "categor",
    "jel", "pacs", "msc", "ams", "toc", "abbr", "publisher", "editor",
    "keyword-group-type-other", "custom", "npg", "plos", "esubject",
    "translation", "translated", "transabstract", "highlight", "bullet",
)

_AUTHOR_LABEL_RE = re.compile(
    r"\bauthor(?:s|'s|s')?\s*[-_ ]?\s*(?:supplied\s+|provided\s+|generated\s+)?"
    r"(?:key\s?words?|keywords?)\b", re.I)
_NON_AUTHOR_LABEL_RE = re.compile(
    r"\b(mesh|medical subject headings?|index(?:ing)? terms?|subject headings?|"
    r"subject terms?|subject areas?|publisher(?:'s)? keywords?|"
    r"key ?words? \(mesh\)|classification|jel codes?|pacs)\b", re.I)


@dataclass
class KwdGroup:
    group_index: int
    group_type: str
    xml_lang: str
    title_text: str
    label_text: str
    keywords: list[str] = field(default_factory=list)
    classification: str = "ambiguous"   # confidently_author | ambiguous | clearly_not_author
    classification_reason: str = ""


def classify_kwd_group(group_type: str, title_text: str, label_text: str,
                       xml_lang: str) -> tuple[str, str]:
    """Return (classification, reason).

    Conservative by construction: anything that is not *unambiguously*
    author-supplied is at best 'ambiguous', and ambiguous groups are excluded
    from benchmark / frequency construction downstream.
    """
    gt_raw = (group_type or "").strip()
    gt = gt_raw.lower().replace("-", "").replace("_", "").replace(" ", "")
    labels = " ".join(x for x in (title_text, label_text) if x).strip()

    # A non-English keyword group is a translation of the author keywords and
    # is not used, to avoid mixing languages into the benchmark.
    lang = (xml_lang or "").strip().lower()
    if lang and not lang.startswith("en"):
        return ("clearly_not_author", f"non_english_kwd_group_xml_lang={lang}")

    if _NON_AUTHOR_LABEL_RE.search(labels):
        return ("clearly_not_author", f"indexer_label:{labels[:60]!r}")

    gt_l = gt_raw.lower()
    if gt and any(sub in gt_l for sub in NON_AUTHOR_TYPE_SUBSTRINGS):
        return ("clearly_not_author", f"indexer_kwd_group_type={gt_raw!r}")

    if gt in AUTHOR_TYPE_TOKENS:
        return ("confidently_author", f"kwd_group_type={gt_raw!r}")

    if _AUTHOR_LABEL_RE.search(labels):
        return ("confidently_author", f"author_label:{labels[:60]!r}")

    if not gt and not labels:
        return ("ambiguous", "no_kwd_group_type_and_no_title_or_label")
    if not gt:
        return ("ambiguous", f"no_kwd_group_type; label={labels[:60]!r}")
    return ("ambiguous", f"unrecognised_kwd_group_type={gt_raw!r}")


# --------------------------------------------------------------------------
# JATS parsing
# --------------------------------------------------------------------------

def _local(el) -> str:
    return etree.QName(el).localname


def _text_of(el) -> str:
    if el is None:
        return ""
    return " ".join(" ".join(el.itertext()).split())


def _find_all_local(root, name: str) -> list:
    return [e for e in root.iter() if isinstance(e.tag, str) and _local(e) == name]


@dataclass
class ArticleRecord:
    pmcid: str = ""
    pmid: str = ""
    doi: str = ""
    title: str = ""
    abstract: str = ""
    journal: str = ""
    pub_year: str = ""
    pub_date: str = ""
    article_type: str = ""
    xml_lang: str = ""
    licence: LicenceInfo = field(default_factory=LicenceInfo)
    kwd_groups: list[KwdGroup] = field(default_factory=list)
    parse_error: str = ""

    @property
    def author_keywords(self) -> list[str]:
        out: list[str] = []
        for g in self.kwd_groups:
            if g.classification == "confidently_author":
                out.extend(g.keywords)
        return out

    @property
    def has_any_kwd_group(self) -> bool:
        return bool(self.kwd_groups)

    @property
    def has_confident_author_kwds(self) -> bool:
        return bool(self.author_keywords)

    @property
    def n_ambiguous_groups(self) -> int:
        return sum(1 for g in self.kwd_groups if g.classification == "ambiguous")


def _extract_pub_date(front) -> tuple[str, str]:
    """Return (year, iso-ish date) preferring the electronic/print pub date."""
    best: tuple[int, str, str] | None = None
    priority = {"epub": 0, "ppub": 1, "epub-ppub": 1, "collection": 2, "pub": 0}
    for pd in _find_all_local(front, "pub-date"):
        dtype = (pd.get("pub-type") or pd.get("date-type") or "").lower()
        y = m = d = ""
        for c in pd:
            ln = _local(c)
            if ln == "year":
                y = (c.text or "").strip()
            elif ln == "month":
                m = (c.text or "").strip()
            elif ln == "day":
                d = (c.text or "").strip()
        if not y:
            continue
        rank = priority.get(dtype, 3)
        iso = y
        if m:
            iso += f"-{int(m):02d}" if m.isdigit() else f"-{m}"
            if d and d.isdigit():
                iso += f"-{int(d):02d}"
        if best is None or rank < best[0]:
            best = (rank, y, iso)
    if best:
        return best[1], best[2]
    return "", ""


def parse_article(art) -> ArticleRecord:
    """Parse one JATS <article> element into an ArticleRecord."""
    rec = ArticleRecord()
    try:
        rec.article_type = art.get("article-type", "") or ""
        rec.xml_lang = art.get("{http://www.w3.org/XML/1998/namespace}lang", "") or ""
        fronts = _find_all_local(art, "front")
        front = fronts[0] if fronts else art

        # PMC emits the PMCID as pub-id-type="pmcid" (and the bare accession
        # number as "pmcaid"); older/alternate records use "pmc".
        pmc_types = ("pmcid", "pmc", "pmcaid", "pmc-uid")
        for aid in _find_all_local(front, "article-id"):
            t = (aid.get("pub-id-type") or "").lower()
            val = (aid.text or "").strip()
            if not val:
                continue
            if t in pmc_types and not rec.pmcid:
                rec.pmcid = val if val.upper().startswith("PMC") else f"PMC{val}"
            elif t == "pmid" and not rec.pmid:
                rec.pmid = val
            elif t == "doi" and not rec.doi:
                rec.doi = val

        for jt in _find_all_local(front, "journal-title"):
            rec.journal = _text_of(jt)
            if rec.journal:
                break

        for tg in _find_all_local(front, "title-group"):
            for at in tg:
                if _local(at) == "article-title":
                    rec.title = _text_of(at)
                    break
            if rec.title:
                break
        if not rec.title:
            ats = _find_all_local(front, "article-title")
            if ats:
                rec.title = _text_of(ats[0])

        abstracts = []
        for ab in _find_all_local(front, "abstract"):
            atype = (ab.get("abstract-type") or "").lower()
            if atype in ("graphical", "teaser", "toc", "video", "précis", "precis"):
                continue
            lang = (ab.get("{http://www.w3.org/XML/1998/namespace}lang") or "").lower()
            if lang and not lang.startswith("en"):
                continue
            txt = _text_of(ab)
            if txt:
                abstracts.append(txt)
        rec.abstract = " ".join(abstracts).strip()

        rec.pub_year, rec.pub_date = _extract_pub_date(front)

        perms = _find_all_local(front, "permissions")
        rec.licence = classify_licence(perms[0] if perms else None)

        for i, kg in enumerate(_find_all_local(front, "kwd-group")):
            gtype = kg.get("kwd-group-type", "") or ""
            xlang = kg.get("{http://www.w3.org/XML/1998/namespace}lang", "") or ""
            title_text = label_text = ""
            for c in kg:
                ln = _local(c)
                if ln == "title" and not title_text:
                    title_text = _text_of(c)
                elif ln == "label" and not label_text:
                    label_text = _text_of(c)
            kws: list[str] = []
            for c in kg:
                ln = _local(c)
                if ln == "kwd":
                    t = _text_of(c)
                    if t:
                        kws.append(t)
                elif ln == "compound-kwd":
                    parts = [_text_of(p) for p in c if _local(p) == "compound-kwd-part"]
                    t = " ".join(p for p in parts if p).strip()
                    if t:
                        kws.append(t)
            cls, reason = classify_kwd_group(gtype, title_text, label_text, xlang)
            rec.kwd_groups.append(KwdGroup(
                group_index=i, group_type=gtype, xml_lang=xlang,
                title_text=title_text, label_text=label_text,
                keywords=kws, classification=cls, classification_reason=reason))
    except Exception as exc:  # pragma: no cover - defensive
        rec.parse_error = f"{type(exc).__name__}: {exc}"
    return rec


def parse_articleset(xml_bytes: bytes) -> list[ArticleRecord]:
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False,
                             load_dtd=False, no_network=True)
    root = etree.fromstring(xml_bytes, parser=parser)
    if root is None:
        return []
    if _local(root) == "article":
        return [parse_article(root)]
    return [parse_article(a) for a in root.iter()
            if isinstance(a.tag, str) and _local(a) == "article"]


# --------------------------------------------------------------------------
# Topic eligibility (title/abstract text ONLY, per protocol)
# --------------------------------------------------------------------------

def build_topic_regexes(evidence_terms: Iterable[str]) -> list[tuple[str, re.Pattern]]:
    """Translate config evidence terms into regexes.

    `hypertens*` -> word starting with 'hypertens'.  Quoted phrases are matched
    literally with flexible internal whitespace.  No silent broadening.
    """
    out = []
    for term in evidence_terms:
        t = term.strip().strip('"')
        if t.endswith("*"):
            stem = re.escape(t[:-1])
            pat = re.compile(rf"\b{stem}\w*", re.I)
        else:
            pat = re.compile(r"\b" + r"\s+".join(re.escape(w) for w in t.split()) + r"\b", re.I)
        out.append((term, pat))
    return out


def topic_evidence_hits(title: str, abstract: str,
                        regexes: list[tuple[str, re.Pattern]]) -> list[str]:
    blob = f"{title or ''}\n{abstract or ''}"
    return [term for term, pat in regexes if pat.search(blob)]


# --------------------------------------------------------------------------
# Independent licence cross-check via PMC OAI-PMH
# --------------------------------------------------------------------------

def oai_licence(client: "NCBIClient", pmcid: str) -> tuple[LicenceInfo, list[str], str]:
    """Second official-source licence read for one PMCID.

    Returns (LicenceInfo, oai_setSpecs, error).  Uses the PMC OAI-PMH
    `pmc_fm` (front-matter) metadata prefix.
    """
    uid = pmcid.upper().replace("PMC", "")
    try:
        resp = client.get(OAI_URL, {
            "verb": "GetRecord",
            "identifier": f"oai:pubmedcentral.nih.gov:{uid}",
            "metadataPrefix": "pmc_fm",
        }, timeout=90)
    except Exception as exc:
        return LicenceInfo(code="unknown", source="oai_error"), [], f"{type(exc).__name__}: {exc}"

    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False,
                             load_dtd=False, no_network=True)
    try:
        root = etree.fromstring(resp.content, parser=parser)
    except Exception as exc:
        return LicenceInfo(code="unknown", source="oai_parse_error"), [], str(exc)
    if root is None:
        return LicenceInfo(code="unknown", source="oai_empty"), [], "empty OAI response"

    sets = [(_text_of(e) or "") for e in root.iter()
            if isinstance(e.tag, str) and _local(e) == "setSpec"]
    errs = [(_text_of(e) or "") for e in root.iter()
            if isinstance(e.tag, str) and _local(e) == "error"]
    perms = [e for e in root.iter()
             if isinstance(e.tag, str) and _local(e) == "permissions"]
    if not perms:
        return (LicenceInfo(code="none", source="oai_no_permissions"), sets,
                "; ".join(errs))
    return classify_licence(perms[0]), sets, "; ".join(errs)


# --------------------------------------------------------------------------
# Raw XML storage (gitignored)
# --------------------------------------------------------------------------

def save_raw(name: str, content: bytes) -> Path:
    DATA_RAW_PMC.mkdir(parents=True, exist_ok=True)
    path = DATA_RAW_PMC / f"{name}.xml.gz"
    with gzip.open(path, "wb") as fh:
        fh.write(content)
    return path


def load_raw(name: str) -> bytes | None:
    path = DATA_RAW_PMC / f"{name}.xml.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rb") as fh:
        return fh.read()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()
