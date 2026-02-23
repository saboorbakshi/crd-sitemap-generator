"""
Full-site web scraper for https://www.crdcreighton.com/
Crawls every page by following all internal href links recursively.
Saves scraped content to a JSON file.

Requirements:
    pip install requests beautifulsoup4
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import time
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────
START_URL    = "https://www.crdcreighton.com/"
OUTPUT_JSON  = "scraped_data.json"
DELAY        = 0.5               # seconds between requests (be polite)
TIMEOUT      = 15                # request timeout in seconds
HEADERS      = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SiteScraper/1.0; +https://example.com)"
    )
}
# ────────────────────────────────────────────────────────────────────────────


def normalize_url(url: str) -> str:
    """Strip fragment and trailing slash for deduplication."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return parsed._replace(fragment="", path=path, query=parsed.query).geturl()


def is_internal(url: str, base_netloc: str) -> bool:
    """Return True if the URL belongs to the same domain."""
    netloc = urlparse(url).netloc
    return netloc == base_netloc or netloc == ""


def get_links(soup: BeautifulSoup, page_url: str, base_netloc: str) -> tuple[list[str], list[str]]:
    """Extract all href links from a page, split into internal and external."""
    internal, external = [], []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        # Skip anchors, mailto, tel, javascript
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(page_url, href)
        # Only keep http/https
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        if is_internal(absolute, base_netloc):
            internal.append(normalize_url(absolute))
        else:
            external.append(absolute)
    return internal, external


def scrape_page(url: str, session: requests.Session) -> dict | None:
    """Fetch a URL and return a dict with metadata."""
    try:
        resp = session.get(url, timeout=TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "html" not in content_type:
            print(f"  [skip] non-HTML content-type: {content_type}  ({url})")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.strip() if soup.title else ""

        return {
            "url":          url,
            "title":        title,
            "status_code":  resp.status_code,
            "content_type": content_type,
            "html":         resp.text,
            "scraped_at":   datetime.now(timezone.utc).isoformat(),
        }
    except requests.RequestException as e:
        print(f"  [error] {url} → {e}")
        return None


def crawl(start_url: str) -> list[dict]:
    base_netloc = urlparse(start_url).netloc
    visited:  set[str]  = set()
    queue:    list[str] = [normalize_url(start_url)]
    results:  list[dict] = []

    with requests.Session() as session:
        while queue:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            print(f"[{len(visited):>4}] Scraping: {url}")
            data = scrape_page(url, session)

            if data is None:
                continue

            results.append({k: v for k, v in data.items() if k != "html"})

            # Parse links and enqueue new ones
            soup = BeautifulSoup(data["html"], "html.parser")
            internal_links, external_links = get_links(soup, url, base_netloc)

            # Tag external links in the result
            results[-1]["external_links"] = sorted(set(external_links))

            for link in internal_links:
                if link not in visited and link not in queue:
                    queue.append(link)

            print(f"         → internal: {len(internal_links)} | external: {len(external_links)} | queue: {len(queue)} | visited: {len(visited)}")
            time.sleep(DELAY)

    return results


def main():
    print(f"Starting crawl of {START_URL}")
    print(f"Delay between requests: {DELAY}s\n")

    results = crawl(START_URL)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Scraped {len(results)} pages.")
    print(f"   Summary saved to: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()