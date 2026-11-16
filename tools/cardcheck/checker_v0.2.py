#!/usr/bin/env python3
"""CARDCHECK-v0.2 deterministic citation checker.

Builds on checker_v0.1.r2 with E1-E3 extractor fixes and F1-F3 fetch fixes.
No AI model calls. fact_status always UNSET. Bucket 3 never set.
Thresholds, protected-word list, boundary matching unchanged from v0.1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import bs4
from bs4 import BeautifulSoup

# Local temp directory next to this script, or $CARDCHECK_TMP.
import tempfile
_TMP = Path(os.environ.get("CARDCHECK_TMP", Path(__file__).resolve().parent / "tmp"))
_TMP.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("TMPDIR", str(_TMP))
os.environ.setdefault("TMP", str(_TMP))
os.environ.setdefault("TEMP", str(_TMP))

BS4_VERSION = getattr(bs4, "__version__", "unknown")
EXTRACTOR_HTML = f"BeautifulSoup.structured_E1_E2/{BS4_VERSION}"
PDFTOTEXT_BIN = os.environ.get("CARDCHECK_PDFTOTEXT", "pdftotext")


def _pdftotext_version() -> str:
    try:
        p = subprocess.run([PDFTOTEXT_BIN, "-v"], capture_output=True, text=True, check=False)
        line = (p.stderr or p.stdout or "").splitlines()[:1]
        return line[0].strip() if line else "unknown"
    except FileNotFoundError:
        return "missing"


PDFTOTEXT_VERSION = _pdftotext_version()
EXTRACTOR_PDF = f"pdftotext -layout/{PDFTOTEXT_VERSION}"

PROTECTED_WORDS = [
    "not", "no", "never", "may", "might", "if", "unless", "except", "only",
    "alleged", "allegedly", "proposed", "reportedly", "would", "could",
]
KNOWN_INDEX_NAMES = {"", "/", "index", "index.html", "index.htm", "home", "home.html", "default.html"}
HINT_FLAG_PREFIXES = ("HOMEPAGE", "DROPPED_QUALIFIER:", "FIGURE_NOWHERE:", "REDIRECT_OFFSITE")
DEFAULT_CARD_STORE_CAP = 10_000
PROMPT_STRUCTURE_NOTE = "claim_shape: id,claim,quote,url,slots[{type,text,mappings}],question,search_plan"

# Operational defaults (documented; not matching thresholds)
FETCH_TIMEOUT_S = float(os.environ.get("CARDCHECK_FETCH_TIMEOUT", "30"))
FETCH_SIZE_CAP = int(os.environ.get("CARDCHECK_FETCH_SIZE_CAP", str(8 * 1024 * 1024)))  # 8 MiB
ARXIV_MIN_INTERVAL_S = float(os.environ.get("CARDCHECK_ARXIV_INTERVAL", "3.0"))
RUN_TIME_BUDGET_S = float(os.environ.get("CARDCHECK_RUN_BUDGET", "600"))  # for Retry-After fit check
RUN_START = time.perf_counter()

_CURLY_QUOTES = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "′": "'", "″": '"',
}
_DASHES = {
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "―": "-", "−": "-", "﹘": "-", "﹣": "-", "－": "-",
}
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(\D|$))")
_WS = re.compile(r"\s+")
# E2: drop space before ,.;:) and after (
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:)])")
_SPACE_AFTER_OPEN = re.compile(r"([(])\s+")


def normalize(text: str) -> str:
    if text is None:
        return ""
    s = str(text)
    for a, b in _CURLY_QUOTES.items():
        s = s.replace(a, b)
    for a, b in _DASHES.items():
        s = s.replace(a, b)
    s = _THOUSANDS.sub("", s)
    s = s.lower()
    s = _WS.sub(" ", s).strip()
    # E2 punctuation spacing
    s = _SPACE_BEFORE_PUNCT.sub(r"\1", s)
    s = _SPACE_AFTER_OPEN.sub(r"\1", s)
    return s


def word_set(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", normalize(text)))


@dataclass
class FetchResult:
    url: str
    final_url: str
    http_status: Optional[int]
    fetched_utc: str
    sha256: Optional[str]
    raw: Optional[bytes]
    content_type: str
    error: Optional[str] = None
    bytes_len: int = 0
    redirect_hops: List[str] = field(default_factory=list)
    redirect_offsite: bool = False


class FetchCache:
    """F1 polite fetch: per-origin serialization, arXiv spacing, timeout, size cap, 429/503 retry."""

    def __init__(self) -> None:
        self._cache: Dict[str, FetchResult] = {}
        self._origin_locks: Dict[str, threading.Lock] = {}
        self._origin_last: Dict[str, float] = {}
        self._global_lock = threading.Lock()
        self.total_bytes = 0
        self.pages_fetched = 0

    def _origin(self, url: str) -> str:
        u = urlparse(url)
        return f"{u.scheme}://{u.netloc}".lower()

    def _lock_for(self, origin: str) -> threading.Lock:
        with self._global_lock:
            if origin not in self._origin_locks:
                self._origin_locks[origin] = threading.Lock()
            return self._origin_locks[origin]

    def _wait_polite(self, origin: str) -> None:
        # serialize via lock held by caller; enforce arXiv min interval
        now = time.perf_counter()
        last = self._origin_last.get(origin, 0.0)
        interval = ARXIV_MIN_INTERVAL_S if "arxiv.org" in origin else 0.0
        delay = interval - (now - last)
        if delay > 0:
            time.sleep(delay)

    def _mark(self, origin: str) -> None:
        self._origin_last[origin] = time.perf_counter()

    def _is_challenge(self, status: int, raw: Optional[bytes], ctype: str) -> bool:
        if status == 403:
            return True
        if not raw:
            return False
        head = raw[:4096].lower()
        # lightweight challenge heuristics (no bypass)
        markers = (b"cf-challenge", b"attention required", b"captcha", b"just a moment", b"access denied")
        return any(m in head for m in markers) and status in (403, 503, 429, 200)

    def _do_fetch(self, url: str, timeout: float) -> FetchResult:
        fetched_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        hops: List[str] = []
        try:
            # Manual redirect following to record hops (F2)
            current = url
            raw = None
            status = None
            ctype = ""
            final = url
            for _ in range(10):
                req = urllib.request.Request(
                    current,
                    headers={"User-Agent": "CARDCHECK-v0.2/0.2 (+deterministic-checker)"},
                    method="GET",
                )
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        # read with size cap
                        chunks = []
                        total = 0
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > FETCH_SIZE_CAP:
                                raise urllib.error.URLError(f"response exceeds size cap {FETCH_SIZE_CAP}")
                            chunks.append(chunk)
                        raw = b"".join(chunks)
                        status = getattr(resp, "status", None) or resp.getcode()
                        final = resp.geturl()
                        ctype = resp.headers.get("Content-Type", "") or ""
                        # collect redirect history if available
                        if hasattr(resp, "geturl") and resp.geturl() != current:
                            hops.append(current)
                        break
                except urllib.error.HTTPError as e:
                    # redirects that urllib may not auto-follow for some codes
                    if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                        hops.append(current)
                        loc = e.headers.get("Location")
                        if loc.startswith("/"):
                            u = urlparse(current)
                            loc = f"{u.scheme}://{u.netloc}{loc}"
                        current = loc
                        continue
                    body = e.read() if hasattr(e, "read") else b""
                    if isinstance(body, (bytes, bytearray)) and len(body) > FETCH_SIZE_CAP:
                        body = body[:FETCH_SIZE_CAP]
                    raw = body if body else None
                    status = int(e.code)
                    final = getattr(e, "url", None) or current
                    ctype = e.headers.get("Content-Type", "") if e.headers else ""
                    # capture Retry-After for caller
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                    digest = hashlib.sha256(raw).hexdigest() if raw else None
                    cited_host = urlparse(url).netloc.lower()
                    final_host = urlparse(final).netloc.lower()
                    offsite = bool(cited_host and final_host and cited_host != final_host)
                    if hops and hops[-1] != current:
                        pass
                    fr = FetchResult(
                        url=url, final_url=final, http_status=status, fetched_utc=fetched_utc,
                        sha256=digest, raw=raw, content_type=ctype,
                        error=f"HTTPError:{e.code}" + (f";Retry-After:{retry_after}" if retry_after else ""),
                        bytes_len=len(raw) if raw else 0, redirect_hops=list(hops),
                        redirect_offsite=offsite,
                    )
                    # attach retry_after for F1 logic via error string already
                    fr._retry_after = retry_after  # type: ignore[attr-defined]
                    return fr
            if raw is None and status is None:
                raise RuntimeError("empty fetch")
            if hops and final not in hops:
                hops.append(final) if False else None
            digest = hashlib.sha256(raw).hexdigest() if raw else None
            cited_host = urlparse(url).netloc.lower()
            final_host = urlparse(final).netloc.lower()
            offsite = bool(cited_host and final_host and cited_host != final_host)
            # record hop chain: start + intermediates + final if redirected
            if final != url and url not in hops:
                hops = [url] + hops
            if final not in hops and final != url:
                hops.append(final)
            return FetchResult(
                url=url, final_url=final, http_status=int(status) if status is not None else None,
                fetched_utc=fetched_utc, sha256=digest, raw=raw, content_type=ctype,
                bytes_len=len(raw) if raw else 0, redirect_hops=hops, redirect_offsite=offsite,
            )
        except Exception as e:
            return FetchResult(
                url=url, final_url=url, http_status=None, fetched_utc=fetched_utc,
                sha256=None, raw=None, content_type="", error=f"{type(e).__name__}:{e}",
                bytes_len=0, redirect_hops=hops,
            )

    def get(self, url: str, timeout: float = FETCH_TIMEOUT_S) -> FetchResult:
        if url in self._cache:
            return self._cache[url]
        origin = self._origin(url)
        lock = self._lock_for(origin)
        with lock:
            if url in self._cache:
                return self._cache[url]
            self.pages_fetched += 1
            self._wait_polite(origin)
            fr = self._do_fetch(url, timeout)
            self._mark(origin)
            # F1: 429/503 retry once
            if fr.http_status in (429, 503):
                retry_after = None
                if fr.error and "Retry-After:" in (fr.error or ""):
                    try:
                        retry_after = float(fr.error.split("Retry-After:")[-1].split(";")[0].strip())
                    except Exception:
                        retry_after = None
                wait = retry_after if retry_after is not None else 10.0
                remaining = RUN_TIME_BUDGET_S - (time.perf_counter() - RUN_START)
                if wait <= remaining and wait >= 0:
                    time.sleep(wait)
                    self._wait_polite(origin)
                    fr2 = self._do_fetch(url, timeout)
                    self._mark(origin)
                    fr = fr2
                else:
                    fr.error = (fr.error or "") + f";retry_skipped_budget wait={wait} remaining={remaining:.1f}"
            # F1: 403 / challenge => FETCH_FAIL (access)
            if fr.http_status == 403 or (fr.raw is not None and self._is_challenge(fr.http_status or 0, fr.raw, fr.content_type)):
                if fr.http_status == 200 and self._is_challenge(200, fr.raw, fr.content_type):
                    fr.error = (fr.error or "") + ";challenge_page"
                    # treat as access failure
                    fr.http_status = 403
                    fr.error = "challenge_page_treated_as_403"
            self.total_bytes += fr.bytes_len
            self._cache[url] = fr
            return fr

    def all_successful_texts(self):
        out = []
        for url, fr in self._cache.items():
            if fr.http_status == 200 and fr.raw is not None:
                originals, extractor, meta = extract_elements(fr)
                norms = [normalize(x) for x in originals]
                out.append((url, originals, norms))
        return out


_BLOCK_TAGS = {
    "p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "figcaption", "dt", "dd", "td", "th",
    "div", "section", "main", "article", "header", "footer", "aside",
}
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "iframe", "nav"}
# leaf-preferred subset for first pass (classic blocks)
_LEAF_PREF = {"p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "figcaption", "dt", "dd", "td", "th"}


def _collapse_ws(s: str) -> str:
    return _WS.sub(" ", s).strip()


def _element_text_e2(tag) -> str:
    # E2: get_text("") then collapse whitespace
    return _collapse_ws(tag.get_text(""))


def extract_html_elements(raw: bytes) -> List[str]:
    """E1: leaf blocks + uncovered text runs grouped by nearest block ancestor."""
    soup = BeautifulSoup(raw, "lxml")
    for t in soup(_SKIP_TAGS):
        t.decompose()
    # also remove non-visible metadata-ish
    for t in soup.find_all(["meta", "link", "head"]):
        if t.name in ("meta", "link"):
            t.decompose()

    elements: List[str] = []
    covered_ids = set()

    # Pass 1: leaf-preferred block tags without nested leaf-pref parent
    for tag in soup.find_all(_LEAF_PREF):
        parent_block = tag.find_parent(_LEAF_PREF)
        if parent_block is not None:
            continue
        text = _element_text_e2(tag)
        if text:
            elements.append(text)
            covered_ids.add(id(tag))
            # mark all descendants as covered for pass 2
            for d in tag.descendants:
                if getattr(d, "name", None) is not None:
                    covered_ids.add(id(d))
                else:
                    covered_ids.add(id(d))

    # Pass 2 (E1): text runs not inside a collected block, group by nearest block ancestor
    from collections import OrderedDict
    groups: "OrderedDict[int, list]" = OrderedDict()
    ancestor_tag: Dict[int, Any] = {}

    def nearest_block(node):
        p = node.parent if hasattr(node, "parent") else None
        while p is not None and getattr(p, "name", None) is not None:
            if p.name in _BLOCK_TAGS and p.name not in _SKIP_TAGS:
                return p
            p = p.parent
        return None

    body = soup.body or soup
    for node in body.descendants:
        if getattr(node, "name", None) is not None:
            continue  # NavigableString only
        if id(node) in covered_ids:
            continue
        # skip empty/whitespace-only
        if not str(node).strip():
            continue
        # skip if any ancestor already a covered collected leaf
        skip = False
        p = node.parent
        while p is not None:
            if id(p) in covered_ids and getattr(p, "name", None) in _LEAF_PREF:
                skip = True
                break
            p = p.parent
        if skip:
            continue
        anc = nearest_block(node)
        if anc is None:
            # orphan text -> own element
            t = _collapse_ws(str(node))
            if t:
                elements.append(t)
            continue
        aid = id(anc)
        if aid not in groups:
            groups[aid] = []
            ancestor_tag[aid] = anc
        groups[aid].append(str(node))

    for aid, parts in groups.items():
        # Prefer full ancestor get_text("") if ancestor not already emitted as leaf
        anc = ancestor_tag[aid]
        if id(anc) in covered_ids:
            continue
        text = _element_text_e2(anc)
        if text and text not in elements:
            elements.append(text)
            covered_ids.add(id(anc))

    if not elements:
        body = soup.body or soup
        text = _collapse_ws(body.get_text(""))
        if text:
            elements = [text]
    return elements


def extract_pdf_elements(raw: bytes) -> Tuple[List[str], List[dict]]:
    """F3: pdftotext -layout; never join across pages; record page per element."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=str(_TMP)) as tf:
        tf.write(raw)
        pdf_path = tf.name
    try:
        p = subprocess.run([PDFTOTEXT_BIN, "-layout", "-bbox", pdf_path, "-"], capture_output=True, check=False)
        # Prefer page-aware extraction via pdftotext per-page if -f/-l available
        # Fallback: split on form feed
        p2 = subprocess.run([PDFTOTEXT_BIN, "-layout", pdf_path, "-"], capture_output=True, check=False)
        if p2.returncode != 0:
            err = (p2.stderr or b"").decode("utf-8", "replace")
            raise RuntimeError(f"pdftotext failed: {err}")
        text = p2.stdout.decode("utf-8", "replace")
    finally:
        try:
            os.unlink(pdf_path)
        except OSError:
            pass

    pages = text.split("\x0c")
    elements: List[str] = []
    meta: List[dict] = []
    for page_idx, page_text in enumerate(pages, start=1):
        lines = page_text.splitlines()
        para: List[str] = []
        page_elems: List[str] = []
        for line in lines:
            if line.strip() == "":
                if para:
                    joined = " ".join(x.strip() for x in para if x.strip())
                    if joined:
                        page_elems.append(joined)
                    para = []
            else:
                para.append(line)
                if line.strip():
                    page_elems.append(line.strip())
        if para:
            joined = " ".join(x.strip() for x in para if x.strip())
            if joined:
                page_elems.append(joined)
        # dedupe within page preserving order
        seen = set()
        for e in page_elems:
            if e and e not in seen:
                seen.add(e)
                elements.append(e)
                meta.append({"page": page_idx, "extractor": EXTRACTOR_PDF})
    return elements, meta


def extract_elements(fr: FetchResult) -> Tuple[List[str], str, List[dict]]:
    ctype = (fr.content_type or "").lower()
    url = (fr.final_url or fr.url or "").lower()
    # F3: only treat as PDF if URL/path looks like PDF (claim URL listed) or content-type
    is_pdf = ("application/pdf" in ctype) or url.endswith(".pdf") or ".pdf?" in url
    if is_pdf:
        elems, meta = extract_pdf_elements(fr.raw or b"")
        return elems, EXTRACTOR_PDF, meta
    elems = extract_html_elements(fr.raw or b"")
    return elems, EXTRACTOR_HTML, [{"page": None} for _ in elems]


def is_homepage(final_url: str) -> bool:
    try:
        u = urlparse(final_url)
    except Exception:
        return False
    path = u.path or ""
    if path in ("", "/"):
        return True
    base = path.rstrip("/").split("/")[-1].lower()
    return base in KNOWN_INDEX_NAMES


def _boundary_pattern(norm_variant: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(norm_variant) + r"(?![a-z0-9])")


def _is_alnum_ascii_word_char(ch: str) -> bool:
    return ("a" <= ch <= "z") or ("0" <= ch <= "9")


def _quote_occurrence_ok(el: str, start: int, length: int) -> bool:
    if start > 0 and _is_alnum_ascii_word_char(el[start - 1]):
        return False
    end = start + length
    if end < len(el) and _is_alnum_ascii_word_char(el[end]):
        return False
    return True


def find_quote(norm_quote: str, norm_elements: List[str]) -> Optional[int]:
    if not norm_quote:
        return None
    for i, el in enumerate(norm_elements):
        start = 0
        while True:
            pos = el.find(norm_quote, start)
            if pos < 0:
                break
            if _quote_occurrence_ok(el, pos, len(norm_quote)):
                return i
            start = pos + 1
    return None


def find_slot_elements(slot: dict, norm_elements: List[str]) -> List[int]:
    variants = [slot.get("text", "")] + list(slot.get("mappings") or [])
    found: List[int] = []
    compiled = []
    for v in variants:
        nv = normalize(v)
        if nv:
            compiled.append(_boundary_pattern(nv))
    for i, el in enumerate(norm_elements):
        for pat in compiled:
            if pat.search(el):
                found.append(i)
                break
    return found


def one_element_with_all_slots(slot_hits: List[List[int]]) -> Optional[int]:
    if not slot_hits:
        return None
    sets = [set(h) for h in slot_hits]
    if any(len(s) == 0 for s in sets):
        return None
    inter = sets[0]
    for s in sets[1:]:
        inter &= s
    if not inter:
        return None
    return min(inter)


def sentences_containing_quote(element_text: str, quote: str) -> str:
    """Return only sentence(s) in element that contain the quote (display/original space)."""
    if not element_text or not quote:
        return ""
    # split on sentence enders while keeping simple
    parts = re.split(r"(?<=[.!?])\s+", element_text.strip())
    nq = normalize(quote)
    kept = []
    for s in parts:
        if nq and normalize(s).find(nq) >= 0:
            # also check mid-word filter via find_quote logic on single sentence
            ns = normalize(s)
            pos = 0
            ok = False
            while True:
                p = ns.find(nq, pos)
                if p < 0:
                    break
                if _quote_occurrence_ok(ns, p, len(nq)):
                    ok = True
                    break
                pos = p + 1
            if ok:
                kept.append(s)
    return " ".join(kept)


def protected_word_flags_for_quote(element_text: str, quote: str, claim: str) -> List[str]:
    # E3: only sentences containing the quote
    scope = sentences_containing_quote(element_text, quote)
    if not scope:
        return []
    el_words = word_set(scope)
    claim_words = word_set(claim)
    flags = []
    for w in PROTECTED_WORDS:
        if w in el_words and w not in claim_words:
            flags.append(f"DROPPED_QUALIFIER:{w}")
    return flags


REQUIRED_KEYS = ("id", "claim", "url", "slots", "question")


def validate_claim(obj: dict) -> Optional[str]:
    for k in REQUIRED_KEYS:
        if k not in obj:
            return f"missing key: {k}"
    if not isinstance(obj.get("question"), str) or not obj["question"].strip():
        return "question must be a non-empty string"
    if not isinstance(obj.get("claim"), str):
        return "claim must be a string"
    if not isinstance(obj.get("url"), str) or not obj["url"].strip():
        return "url must be a non-empty string"
    if not isinstance(obj.get("slots"), list):
        return "slots must be a list"
    for i, s in enumerate(obj["slots"]):
        if not isinstance(s, dict):
            return f"slots[{i}] must be object"
        if "text" not in s or "type" not in s:
            return f"slots[{i}] needs type and text"
        if s["type"] not in ("entity", "date", "figure"):
            return f"slots[{i}].type must be entity|date|figure"
        if "mappings" in s and not isinstance(s["mappings"], list):
            return f"slots[{i}].mappings must be list"
    quote = obj.get("quote", "")
    if quote is None:
        obj["quote"] = ""
    elif not isinstance(quote, str):
        return "quote must be a string"
    return None


@dataclass
class PartialCard:
    card: dict
    originals: List[str]
    norms: List[str]
    fetch_ok: bool
    slot_defs: List[dict]


def process_claim(claim: dict, cache: FetchCache) -> PartialCard:
    t0 = time.perf_counter()
    err = validate_claim(claim)
    if err:
        card = {
            "id": claim.get("id"), "url": claim.get("url"), "final_url": None,
            "http_status": None, "fetched_utc": None, "sha256": None, "extractor": None,
            "quote_status": "NO_QUOTE_GIVEN" if not claim.get("quote") else "NOT_FOUND",
            "quote_element": None, "quote_text": None, "slots": [], "one_element": None,
            "element_text": None, "before": None, "after": None,
            "flags": [f"INPUT_INVALID:{err}"], "fact_status": "UNSET", "bucket": 1,
            "seconds": round(time.perf_counter() - t0, 6),
            "question": claim.get("question"), "search_plan": claim.get("search_plan", ""),
            "claim": claim.get("claim"), "redirect_hops": [], "pdf_pages": None,
        }
        return PartialCard(card, [], [], False, [])

    fr = cache.get(claim["url"])
    if fr.http_status != 200 or fr.raw is None:
        flags = ["FETCH_FAIL"]
        if fr.redirect_offsite:
            flags.append("REDIRECT_OFFSITE")
            flags.append("HINT:REDIRECT_OFFSITE")
        card = {
            "id": claim["id"], "url": claim["url"], "final_url": fr.final_url,
            "http_status": fr.http_status, "fetched_utc": fr.fetched_utc, "sha256": fr.sha256,
            "extractor": None,
            "quote_status": "NO_QUOTE_GIVEN" if not (claim.get("quote") or "").strip() else "NOT_FOUND",
            "quote_element": None, "quote_text": None,
            "slots": [{"text": s.get("text"), "found_in_elements": [], "type": s.get("type")} for s in claim["slots"]],
            "one_element": None, "element_text": None, "before": None, "after": None,
            "flags": flags, "fact_status": "UNSET", "bucket": 1,
            "seconds": round(time.perf_counter() - t0, 6),
            "question": claim["question"], "search_plan": claim.get("search_plan", ""),
            "claim": claim["claim"], "fetch_error": fr.error,
            "redirect_hops": fr.redirect_hops, "pdf_pages": None,
        }
        return PartialCard(card, [], [], False, claim["slots"])

    originals, extractor, meta = extract_elements(fr)
    norms = [normalize(x) for x in originals]
    flags: List[str] = []

    if is_homepage(fr.final_url):
        flags.append("HOMEPAGE")
    if fr.redirect_offsite:
        flags.append("REDIRECT_OFFSITE")

    quote = claim.get("quote") or ""
    if not quote.strip():
        quote_status = "NO_QUOTE_GIVEN"
        quote_element = None
        quote_text = None
    else:
        qi = find_quote(normalize(quote), norms)
        if qi is None:
            quote_status = "NOT_FOUND"
            quote_element = None
            quote_text = None
        else:
            quote_status = "FOUND"
            quote_element = qi
            quote_text = originals[qi]

    slot_results = []
    slot_hits: List[List[int]] = []
    missing_slots: List[str] = []
    for s in claim["slots"]:
        hits = find_slot_elements(s, norms)
        slot_hits.append(hits)
        slot_results.append({"text": s["text"], "type": s["type"], "found_in_elements": hits})
        if not hits:
            missing_slots.append(s["text"])
            flags.append(f"SLOT_MISSING:{s['text']}")

    one_el = one_element_with_all_slots(slot_hits) if claim["slots"] else None
    if claim["slots"] and not missing_slots and one_el is None:
        if all(len(h) > 0 for h in slot_hits):
            flags.append("SPLIT")

    ctx_idx = quote_element if quote_element is not None else one_el
    element_text = originals[ctx_idx] if ctx_idx is not None else None
    before = originals[ctx_idx - 1] if ctx_idx is not None and ctx_idx > 0 else None
    after = originals[ctx_idx + 1] if ctx_idx is not None and ctx_idx + 1 < len(originals) else None

    # E3: protected words ONLY when quote FOUND, only quote-bearing sentences
    if quote_status == "FOUND" and element_text is not None:
        for f in protected_word_flags_for_quote(element_text, quote, claim["claim"]):
            if f not in flags:
                flags.append(f)

    hard_absent = quote_status == "NOT_FOUND" or bool(missing_slots)
    hard_rule_fired = "SPLIT" in flags
    if hard_absent:
        bucket: Optional[int] = 1
    elif hard_rule_fired:
        bucket = 2
    else:
        bucket = None

    out_flags: List[str] = []
    for f in flags:
        out_flags.append(f)
        if f == "HOMEPAGE" or f.startswith("DROPPED_QUALIFIER:") or f.startswith("FIGURE_NOWHERE:") or f == "REDIRECT_OFFSITE":
            hint = f"HINT:{f}"
            if hint not in out_flags:
                out_flags.append(hint)

    pdf_pages = None
    if ctx_idx is not None and meta and ctx_idx < len(meta):
        pdf_pages = meta[ctx_idx].get("page")

    card = {
        "id": claim["id"], "url": claim["url"], "final_url": fr.final_url,
        "http_status": fr.http_status, "fetched_utc": fr.fetched_utc, "sha256": fr.sha256,
        "extractor": extractor, "quote_status": quote_status, "quote_element": quote_element,
        "quote_text": quote_text, "slots": slot_results, "one_element": one_el,
        "element_text": element_text, "before": before, "after": after,
        "flags": out_flags, "fact_status": "UNSET", "bucket": bucket,
        "seconds": round(time.perf_counter() - t0, 6),
        "question": claim["question"], "search_plan": claim.get("search_plan", ""),
        "claim": claim["claim"], "prompt_structure": PROMPT_STRUCTURE_NOTE,
        "redirect_hops": fr.redirect_hops, "pdf_page": pdf_pages,
    }
    return PartialCard(card, originals, norms, True, claim["slots"])


def apply_figure_nowhere(partials: List[PartialCard], cache: FetchCache) -> None:
    corpus = cache.all_successful_texts()
    for pc in partials:
        if not pc.fetch_ok:
            continue
        for s in pc.slot_defs:
            if s.get("type") != "figure":
                continue
            variants = [s.get("text", "")] + list(s.get("mappings") or [])
            pats = [_boundary_pattern(normalize(v)) for v in variants if normalize(v)]
            found_anywhere = False
            for _url, _orig, norms in corpus:
                for el in norms:
                    for pat in pats:
                        if pat.search(el):
                            found_anywhere = True
                            break
                    if found_anywhere:
                        break
                if found_anywhere:
                    break
            if not found_anywhere:
                flag = f"FIGURE_NOWHERE:{s.get('text')}"
                if flag not in pc.card["flags"]:
                    pc.card["flags"].append(flag)
                hint = f"HINT:{flag}"
                if hint not in pc.card["flags"]:
                    pc.card["flags"].append(hint)


class CardStore:
    def __init__(self, path: Path, cap: int = DEFAULT_CARD_STORE_CAP) -> None:
        self.path = path
        self.cap = cap
        self.count = 0
        self.rejected = 0
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                self.count = sum(1 for line in f if line.strip())

    def admit(self, card: dict) -> bool:
        if card.get("fact_status") != "UNSET" or "bucket" not in card:
            self.rejected += 1
            return False
        if self.count >= self.cap:
            self.rejected += 1
            return False
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(card, ensure_ascii=False) + "\n")
        self.count += 1
        return True


def one_liner(card: dict) -> str:
    flags = ",".join(card.get("flags") or []) or "-"
    return (
        f"{card.get('id')}: quote={card.get('quote_status')} bucket={card.get('bucket')} "
        f"flags=[{flags}] seconds={card.get('seconds')} status={card.get('http_status')}"
    )


def load_claims(path: Path) -> List[dict]:
    claims = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                claims.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"claims.jsonl line {lineno}: {e}")
    return claims


def run(claims_path: Path, cards_path: Path, cap: int, summary_path: Optional[Path]) -> dict:
    global RUN_START
    RUN_START = time.perf_counter()
    t_wall0 = time.perf_counter()
    claims = load_claims(claims_path)
    cache = FetchCache()
    store = CardStore(cards_path, cap=cap)
    partials: List[PartialCard] = []
    for claim in claims:
        partials.append(process_claim(claim, cache))
    apply_figure_nowhere(partials, cache)
    lines = []
    for pc in partials:
        ok = store.admit(pc.card)
        pc.card["admitted"] = ok
        lines.append(one_liner(pc.card))
    wall = time.perf_counter() - t_wall0
    summary = {
        "wall_seconds": round(wall, 6),
        "wall_minutes": round(wall / 60.0, 6),
        "bytes_fetched": cache.total_bytes,
        "pages_fetched": cache.pages_fetched,
        "claims": len(claims),
        "cards_admitted": store.count,
        "cards_rejected": store.rejected,
        "cards_path": str(cards_path),
        "extractor_html": EXTRACTOR_HTML,
        "extractor_pdf": EXTRACTOR_PDF,
        "one_liners": lines,
        "prompt_structure": PROMPT_STRUCTURE_NOTE,
        "ops": {
            "FETCH_TIMEOUT_S": FETCH_TIMEOUT_S,
            "FETCH_SIZE_CAP": FETCH_SIZE_CAP,
            "ARXIV_MIN_INTERVAL_S": ARXIV_MIN_INTERVAL_S,
            "RUN_TIME_BUDGET_S": RUN_TIME_BUDGET_S,
        },
    }
    if summary_path:
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="CARDCHECK-v0.2 deterministic citation checker")
    ap.add_argument("--claims", required=True, type=Path)
    ap.add_argument("--cards", required=True, type=Path)
    ap.add_argument("--summary", type=Path, default=None)
    ap.add_argument("--cap", type=int, default=DEFAULT_CARD_STORE_CAP)
    args = ap.parse_args(argv)
    if args.cards.exists() and args.cards.stat().st_size > 0:
        print(f"ERROR: cards path exists and non-empty: {args.cards}", file=sys.stderr)
        return 2
    summary = run(args.claims, args.cards, args.cap, args.summary)
    for line in summary["one_liners"]:
        print(line)
    print(
        f"TOTAL wall_seconds={summary['wall_seconds']} bytes={summary['bytes_fetched']} "
        f"pages={summary['pages_fetched']} admitted={summary['cards_admitted']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
