"""Web research helper for the Lead Qualifier.

Two fetch strategies:
- Playwright + Chromium (preferred — handles JS-rendered sites)
- requests + BeautifulSoup (fallback when Playwright is unavailable or fails)

Returns source-annotated facts so the agent can never claim something the page
didn't actually say. When both methods fail, returns `accessible=False` with a
human-readable note — the caller should turn that into Unverified-section
entries, not invent content.

Supports single-page fetch (default) and multi-page crawl (--crawl):
- Crawl mode: parses sitemap.xml → extracts homepage links as fallback →
  filters to key business pages → fetches up to --max-pages (default 5) →
  returns merged extraction with per-page source annotations.
- Reports discovered-but-not-crawled pages so the freelancer can manually
  review the full site if the lead looks promising.

Run as a module to invoke from a SKILL.md:
    python -m web_research <url> [--crawl] [--max-pages N] [--no-playwright]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any
from urllib.parse import urljoin, urlparse

try:
    import requests  # type: ignore[import-untyped]
    from bs4 import BeautifulSoup  # type: ignore[import-untyped]
    _HAS_HTTP = True
except ImportError:  # pragma: no cover
    _HAS_HTTP = False

try:
    from playwright.sync_api import sync_playwright  # type: ignore[import-untyped]
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False


USER_AGENT = (
    "Mozilla/5.0 (compatible; FreelanceForge/1.0; "
    "+https://github.com/anthropics/freelance-forge)"
)

# Skip these file extensions when discovering pages
_SKIP_EXTENSIONS = re.compile(
    r"\.(jpg|jpeg|png|gif|svg|ico|webp|pdf|zip|gz|css|js|woff|woff2|ttf|eot|mp[34]|avi|mov|rss|xml)(\?|$)",
    re.I,
)

# Patterns for classifying business-relevant page types
_BUSINESS_PAGE_PATTERNS: dict[str, list[str]] = {
    "contact": [r"(?:contact|get-in-touch|enquir)"],
    "about": [r"(?:about|who-we|our-(?:story|team|company))"],
    "services": [r"(?:serv|what-we|our-(?:serv|work|offer|clean))"],
    "testimonials": [r"(?:testim|review|feedback|client)"],
    "pricing": [r"(?:pric|cost|rate|package|quote)"],
    "blog": [r"(?:blog|news|article|post)"],
}


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    url: str
    html: str = ""
    text: str = ""
    source: str = "none"          # 'playwright' | 'http' | 'none'
    accessible: bool = False
    status_code: int | None = None
    notes: list[str] = field(default_factory=list)


def fetch_page(url: str, *, timeout: int = 15, prefer_playwright: bool = True) -> FetchResult:
    """Fetch a page. Try Playwright first if available; fall back to HTTP.

    Always returns a FetchResult — never raises for network failures. Caller
    inspects `accessible` and `notes`.
    """
    result = FetchResult(url=url)

    if prefer_playwright and _HAS_PLAYWRIGHT:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=USER_AGENT)
                page = context.new_page()
                response = page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
                # Brief settle for JS-rendered content
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass  # networkidle isn't critical
                result.html = page.content()
                result.text = page.evaluate("() => document.body ? document.body.innerText : ''")
                result.source = "playwright"
                result.accessible = True
                result.status_code = response.status if response else None
                browser.close()
                if not result.text.strip():
                    result.notes.append("Playwright loaded page but body text is empty")
                return result
        except Exception as exc:
            result.notes.append(f"Playwright failed: {type(exc).__name__}: {exc}")

    if _HAS_HTTP:
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT}, allow_redirects=True)
            result.status_code = resp.status_code
            if resp.status_code >= 400:
                result.notes.append(f"HTTP {resp.status_code} {resp.reason}")
                return result
            result.html = resp.text
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            result.text = " ".join(soup.get_text(separator=" ").split())
            result.source = "http"
            result.accessible = bool(result.text.strip()) and len(result.text) > 200
            if not result.accessible:
                result.notes.append(
                    "HTTP fetch returned empty/minimal body — likely a JS-rendered shell. "
                    "Install Playwright for better coverage."
                )
            return result
        except Exception as exc:
            result.notes.append(f"HTTP fetch failed: {type(exc).__name__}: {exc}")
    else:
        result.notes.append("requests/BeautifulSoup not installed — no HTTP fallback available")

    return result


# ---------------------------------------------------------------------------
# Extraction (source-annotated facts only)
# ---------------------------------------------------------------------------

@dataclass
class Fact:
    claim: str
    source_section: str           # e.g. "<title>", "meta[name=description]", "footer"
    source_url: str
    confidence: str               # 'HIGH' | 'MEDIUM' | 'LOW'

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


# Regex patterns
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"\+?\d[\d\s\-().]{7,}\d"  # loose international
)
_SOCIAL_HOSTS = {
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "tiktok.com": "tiktok",
}


def extract_company_info(html: str, url: str) -> dict[str, Any]:
    """Pull source-annotated facts from a page's HTML.

    Returns a dict of the shape:
        {
          "facts": [Fact, ...],          # everything the page actually said
          "tech_stack": [Fact, ...],     # detected CMS/framework hints (separate so caller can tag)
          "social_links": [Fact, ...],
          "contacts": {"emails": [...], "phones": [...]},
          "suggested_tags": [str, ...],
          "missing": [str, ...],         # things the caller should flag as Unverified
        }
    """
    if not _HAS_HTTP:
        # Fall back to crude regex parsing
        return {
            "facts": [],
            "tech_stack": [],
            "social_links": [],
            "contacts": {"emails": list(set(_EMAIL_RE.findall(html))),
                         "phones": list(set(_PHONE_RE.findall(html)))},
            "suggested_tags": [],
            "missing": ["BeautifulSoup unavailable — extraction limited to regex matches"],
        }

    soup = BeautifulSoup(html, "html.parser")
    facts: list[Fact] = []
    missing: list[str] = []

    # Title
    if soup.title and soup.title.string:
        facts.append(Fact(soup.title.string.strip(), "<title>", url, "HIGH"))

    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"}) \
        or soup.find("meta", attrs={"property": "og:description"})
    if meta_desc and meta_desc.get("content"):
        facts.append(Fact(meta_desc["content"].strip(), "meta[description]", url, "HIGH"))
    else:
        missing.append("No meta description tag found")

    # Headings give a quick sense of what the page emphasises
    for h in soup.find_all(["h1", "h2"])[:8]:
        text = " ".join(h.get_text().split())
        if text and len(text) < 200:
            facts.append(Fact(text, h.name, url, "HIGH"))

    # Tech-stack hints — from meta generator + script src + classnames
    tech: list[Fact] = []
    generator = soup.find("meta", attrs={"name": "generator"})
    if generator and generator.get("content"):
        tech.append(Fact(generator["content"], "meta[generator]", url, "HIGH"))

    html_lower = html.lower()
    tech_signatures = {
        "wordpress": ["wp-content/", "wp-includes/", "wp-json"],
        "shopify": ["cdn.shopify.com", "shopify.theme"],
        "wix": ["static.wixstatic.com", "wix.com"],
        "squarespace": ["static1.squarespace.com", "squarespace.com"],
        "webflow": ["webflow.com", "webflow.js"],
        "next.js": ["/_next/", "__next_data__"],
        "react": ["react-dom", "data-reactroot"],
        "vue": ["__vue_app__", "vue.js"],
        "drupal": ["sites/default/", "drupal.js"],
        "hubspot": ["js.hs-scripts.com", "hsforms.net"],
    }
    for name, sigs in tech_signatures.items():
        if any(sig in html_lower for sig in sigs):
            tech.append(Fact(f"Likely uses {name}", f"asset signatures: {', '.join(sigs)}", url, "MEDIUM"))

    # Social links
    socials: list[Fact] = []
    seen_socials: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        try:
            host = urlparse(href).netloc.lower().lstrip("www.")
        except Exception:
            continue
        for known_host, network in _SOCIAL_HOSTS.items():
            if known_host in host and href not in seen_socials:
                seen_socials.add(href)
                socials.append(Fact(href, f"link to {network}", url, "HIGH"))
                break

    # Contacts
    body_text = soup.get_text(separator=" ")
    emails = sorted(set(m.lower() for m in _EMAIL_RE.findall(body_text)
                        if not m.lower().endswith((".png", ".jpg", ".svg"))))
    phones_raw = _PHONE_RE.findall(body_text)
    phones = sorted({re.sub(r"\s+", " ", p).strip() for p in phones_raw})

    if not emails and not phones:
        missing.append("No email or phone number found in body text")

    # Suggested tags
    suggested_tags: list[str] = []
    for fact in tech:
        match = re.search(r"Likely uses (\S+)", fact.claim)
        if match:
            suggested_tags.append(match.group(1).lower().rstrip("."))
        if "wordpress" in fact.claim.lower():
            suggested_tags.append("wordpress")
        if "shopify" in fact.claim.lower():
            suggested_tags.append("ecommerce")
    # Crude "local business" heuristic — phone present + body mentions a city/area
    if phones and any(word in body_text.lower() for word in ("address", "located", "directions", "opening hours")):
        suggested_tags.append("local-business")

    return {
        "facts": [f.to_dict() for f in facts],
        "tech_stack": [f.to_dict() for f in tech],
        "social_links": [f.to_dict() for f in socials],
        "contacts": {"emails": emails, "phones": phones},
        "suggested_tags": sorted(set(suggested_tags)),
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Page discovery (sitemap → homepage links → filter → cap)
# ---------------------------------------------------------------------------

def parse_sitemap(text: str) -> list[dict[str, Any]]:
    """Parse an XML sitemap. Returns list of {url, priority, lastmod} dicts.

    Tries XML parsing first, falls back to regex if the XML is malformed.
    """
    urls: list[dict[str, Any]] = []
    try:
        clean = re.sub(r'\sxmlns[^"]*"[^"]*"', '', text, flags=re.DOTALL)
        root = ET.fromstring(clean)
        for url_el in root.iter("url"):
            loc, pri, mod = "", None, None
            for child in url_el:
                if child.tag == "loc" and child.text:
                    loc = child.text.strip()
                elif child.tag == "priority" and child.text:
                    try:
                        pri = float(child.text)
                    except ValueError:
                        pass
                elif child.tag == "lastmod" and child.text:
                    mod = child.text.strip()
            if loc:
                urls.append({"url": loc, "priority": pri, "lastmod": mod})
    except ET.ParseError:
        # Regex fallback for malformed XML
        for m in re.finditer(r"<loc>\s*(.*?)\s*</loc>", text):
            urls.append({"url": m.group(1).strip(), "priority": None, "lastmod": None})

    # Sort by priority (highest first), None priority at the end
    urls.sort(key=lambda u: (u["priority"] is not None, u["priority"] or 0), reverse=True)
    return urls


def extract_links_from_html(html: str, base_url: str) -> list[dict[str, Any]]:
    """Extract same-domain links from HTML content.

    Used as fallback when sitemap yields insufficient pages.
    Returns list of {"url": ..., "priority": None, "lastmod": None} dicts.
    """
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    for m in re.finditer(r'<a\s+[^>]*href=["\']([^"\' >]+)["\'][^>]*>', html, re.I):
        href = m.group(1).strip()
        # Skip anchors, javascript, mailto
        if href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:'):
            continue
        # Resolve relative URLs
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        # Same domain only, skip asset extensions, skip duplicates
        if parsed.netloc != base_domain:
            continue
        if _SKIP_EXTENSIONS.search(parsed.path):
            continue
        if full in seen:
            continue
        seen.add(full)
        links.append({"url": full, "priority": None, "lastmod": None})

    return links


def classify_business_page(url: str) -> str:
    """Classify a URL by business page type.

    Returns: 'homepage', 'contact', 'about', 'services', 'testimonials',
             'pricing', 'blog', or 'other'.
    """
    path = urlparse(url).path.rstrip("/")
    if path in ("", "/"):
        return "homepage"
    for ptype, patterns in _BUSINESS_PAGE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, path, re.I):
                return ptype
    return "other"


def _normalise_url(url: str) -> str:
    """Strip trailing slash and fragment for dedup."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def discover_pages(
    base_url: str,
    homepage_html: str,
    homepage_url: str,
    max_pages: int = 5,
    prefer_playwright: bool = True,
) -> dict[str, Any]:
    """Discover and prioritise pages to crawl.

    Three-stage discovery:
    1. Try /sitemap.xml (plain HTTP — sitemaps don't need JS rendering)
    2. If sitemap empty/missing, extract same-domain links from homepage
    3. Filter to key business pages, cap at max_pages

    Returns:
        {
            "total_discovered": int,
            "source": "sitemap" | "homepage_links" | "none",
            "all_pages": [{"url", "page_type", "priority", "lastmod"}],
            "audited": [{"url", "page_type"}],
            "not_crawled": [{"url", "page_type"}],
        }
    """
    # Stage 1: Try sitemap.xml
    parsed = urlparse(base_url)
    sm_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    sitemap_pages: list[dict[str, Any]] = []

    if _HAS_HTTP:
        try:
            resp = requests.get(sm_url, timeout=10, headers={"User-Agent": USER_AGENT}, allow_redirects=True)
            if resp.status_code == 200 and resp.text:
                sitemap_pages = parse_sitemap(resp.text)
        except Exception:
            pass

    # Also try WordPress sitemap location
    if not sitemap_pages and _HAS_HTTP:
        wp_sm_url = f"{parsed.scheme}://{parsed.netloc}/wp-sitemap.xml"
        try:
            resp = requests.get(wp_sm_url, timeout=10, headers={"User-Agent": USER_AGENT}, allow_redirects=True)
            if resp.status_code == 200 and resp.text:
                sitemap_pages = parse_sitemap(resp.text)
        except Exception:
            pass

    # Stage 2: Homepage link fallback
    homepage_links: list[dict[str, Any]] = []
    if not sitemap_pages:
        homepage_links = extract_links_from_html(homepage_html, homepage_url)

    # Combine and deduplicate
    all_discovered: dict[str, dict[str, Any]] = {}
    source = "none"
    for p in sitemap_pages:
        norm = _normalise_url(p["url"])
        if norm != _normalise_url(homepage_url) and not _SKIP_EXTENSIONS.search(urlparse(p["url"]).path):
            all_discovered[norm] = {**p, "page_type": classify_business_page(p["url"])}
    if sitemap_pages:
        source = "sitemap"
    for p in homepage_links:
        norm = _normalise_url(p["url"])
        if norm != _normalise_url(homepage_url) and norm not in all_discovered:
            all_discovered[norm] = {**p, "page_type": classify_business_page(p["url"])}
    if homepage_links and not sitemap_pages:
        source = "homepage_links"
    if sitemap_pages and homepage_links:
        source = "sitemap"

    # Stage 3: Prioritise business-relevant pages
    # Priority order: contact, about, services, testimonials, pricing, homepage-already-done, then others
    priority_order = {"contact": 0, "about": 1, "services": 2, "testimonials": 3, "pricing": 4, "blog": 5, "other": 6}
    all_pages_sorted = sorted(
        all_discovered.values(),
        key=lambda p: (
            priority_order.get(p["page_type"], 6),
            p.get("priority") is not None,
            p.get("priority") or 0,
        ),
        reverse=False,
    )

    audited = all_pages_sorted[:max_pages]
    not_crawled = all_pages_sorted[max_pages:]

    return {
        "total_discovered": len(all_discovered),
        "source": source,
        "all_pages": all_pages_sorted,
        "audited": [{"url": p["url"], "page_type": p["page_type"]} for p in audited],
        "not_crawled": [{"url": p["url"], "page_type": p["page_type"]} for p in not_crawled],
    }


# ---------------------------------------------------------------------------
# Merge extractions from multiple pages
# ---------------------------------------------------------------------------

def merge_extractions(extractions: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple page extractions into one combined result.

    Deduplicates facts by (claim, source_section), keeps the highest confidence.
    Merges contacts (deduplicates emails and phones).
    Merges tech_stack (deduplicates by claim).
    Merges social_links (deduplicates by URL).
    Combines missing lists (deduplicates).
    Combines suggested_tags.
    """
    merged_facts: dict[tuple[str, str], dict] = {}   # (claim, source_section) → fact dict
    merged_tech: dict[str, dict] = {}                 # claim → fact dict
    merged_socials: dict[str, dict] = {}              # url → fact dict
    all_emails: set[str] = set()
    all_phones: set[str] = set()
    all_missing: set[str] = set()
    all_tags: set[str] = set()
    confidence_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    for ext in extractions:
        for fact in ext.get("facts", []):
            key = (fact["claim"], fact["source_section"])
            if key not in merged_facts or confidence_rank.get(fact["confidence"], 0) > confidence_rank.get(merged_facts[key]["confidence"], 0):
                merged_facts[key] = fact

        for fact in ext.get("tech_stack", []):
            if fact["claim"] not in merged_tech or confidence_rank.get(fact["confidence"], 0) > confidence_rank.get(merged_tech[fact["claim"]]["confidence"], 0):
                merged_tech[fact["claim"]] = fact

        for fact in ext.get("social_links", []):
            if fact["claim"] not in merged_socials:
                merged_socials[fact["claim"]] = fact

        contacts = ext.get("contacts", {})
        all_emails.update(contacts.get("emails", []))
        all_phones.update(contacts.get("phones", []))

        all_missing.update(ext.get("missing", []))
        all_tags.update(ext.get("suggested_tags", []))

    return {
        "facts": [v for v in merged_facts.values()],
        "tech_stack": list(merged_tech.values()),
        "social_links": list(merged_socials.values()),
        "contacts": {"emails": sorted(all_emails), "phones": sorted(all_phones)},
        "suggested_tags": sorted(all_tags),
        "missing": sorted(all_missing),
        "pages_scanned": len(extractions),
    }


# ---------------------------------------------------------------------------
# Crawl orchestrator
# ---------------------------------------------------------------------------

def crawl_and_extract(
    url: str,
    *,
    max_pages: int = 5,
    timeout: int = 15,
    prefer_playwright: bool = True,
) -> dict[str, Any]:
    """Fetch a URL, discover related pages, crawl key business pages, merge extractions.

    Returns a dict with:
        fetch: homepage fetch result
        crawl: page discovery info
        extraction: merged extraction across all pages
    """
    # 1. Fetch the homepage (or whatever URL was given)
    homepage_fetch = fetch_page(url, timeout=timeout, prefer_playwright=prefer_playwright)

    result: dict[str, Any] = {
        "fetch": {
            "url": homepage_fetch.url,
            "source": homepage_fetch.source,
            "accessible": homepage_fetch.accessible,
            "status_code": homepage_fetch.status_code,
            "notes": homepage_fetch.notes,
        },
        "crawl": None,
        "extraction": None,
    }

    if not homepage_fetch.accessible or not homepage_fetch.html:
        return result

    # 2. Extract from homepage
    homepage_extraction = extract_company_info(homepage_fetch.html, url)

    # 3. Discover pages
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    discovery = discover_pages(base_url, homepage_fetch.html, url, max_pages=max_pages, prefer_playwright=prefer_playwright)

    result["crawl"] = {
        "source": discovery["source"],
        "total_discovered": discovery["total_discovered"],
        "pages_crawled": len(discovery["audited"]) + 1,  # +1 for homepage
        "audited_pages": [
            {"url": url, "page_type": "homepage"},
            *[{"url": p["url"], "page_type": p["page_type"]} for p in discovery["audited"]],
        ],
        "not_crawled": discovery["not_crawled"],
    }

    # 4. Fetch and extract additional pages
    all_extractions = [homepage_extraction]
    for page_info in discovery["audited"]:
        page_url = page_info["url"]
        page_fetch = fetch_page(page_url, timeout=timeout, prefer_playwright=prefer_playwright)
        if page_fetch.accessible and page_fetch.html:
            all_extractions.append(extract_company_info(page_fetch.html, page_url))

    # 5. Merge all extractions
    merged = merge_extractions(all_extractions)
    result["extraction"] = merged

    return result


# ---------------------------------------------------------------------------
# CLI shim
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="web_research")
    p.add_argument("url")
    p.add_argument("--crawl", action="store_true", default=False,
                   help="Crawl the site: parse sitemap, fetch key business pages, merge extractions")
    p.add_argument("--max-pages", type=int, default=5,
                   help="Max additional pages to crawl (default: 5, homepage always included)")
    p.add_argument("--no-playwright", dest="prefer_playwright",
                   action="store_false", default=True)
    p.add_argument("--timeout", type=int, default=15)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.crawl:
        payload = crawl_and_extract(
            args.url,
            max_pages=args.max_pages,
            timeout=args.timeout,
            prefer_playwright=args.prefer_playwright,
        )
        accessible = payload["fetch"]["accessible"]
    else:
        fetch = fetch_page(args.url, timeout=args.timeout, prefer_playwright=args.prefer_playwright)
        payload: dict[str, Any] = {
            "fetch": {
                "url": fetch.url,
                "source": fetch.source,
                "accessible": fetch.accessible,
                "status_code": fetch.status_code,
                "notes": fetch.notes,
            }
        }
        if fetch.accessible and fetch.html:
            payload["extraction"] = extract_company_info(fetch.html, fetch.url)
        accessible = fetch.accessible

    print(json.dumps(payload, indent=2))
    return 0 if accessible else 2


if __name__ == "__main__":
    sys.exit(main())
