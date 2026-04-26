"""Web research helper for the Lead Qualifier.

Two fetch strategies:
- Playwright + Chromium (preferred — handles JS-rendered sites)
- requests + BeautifulSoup (fallback when Playwright is unavailable or fails)

Returns source-annotated facts so the agent can never claim something the page
didn't actually say. When both methods fail, returns `accessible=False` with a
human-readable note — the caller should turn that into Unverified-section
entries, not invent content.

Run as a module to invoke from a SKILL.md:
    python -m web_research <url> [--no-playwright]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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
# CLI shim
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="web_research")
    p.add_argument("url")
    p.add_argument("--no-playwright", dest="prefer_playwright",
                   action="store_false", default=True)
    p.add_argument("--timeout", type=int, default=15)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
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
    print(json.dumps(payload, indent=2))
    return 0 if fetch.accessible else 2


if __name__ == "__main__":
    sys.exit(main())
