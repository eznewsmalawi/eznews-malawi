"""
ezNews Malawi — source verification utility.

Run this BEFORE deploying, and any time you change the SOURCES list,
or when the pipeline starts producing fewer articles than expected.

It tries every feed URL in pipeline/run.py's SOURCES list, reports
which ones return valid RSS, and shows a sample headline from each.
No API key needed — this script does not call Claude.

Usage:
    python pipeline/verify_sources.py

Exit code is 0 if all sources have at least one working feed,
1 if any source has zero working feeds.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root or from pipeline/ folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser  # type: ignore
import requests

from pipeline.run import SOURCES, USER_AGENT, HTTP_TIMEOUT


GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
RESET = "\033[0m"


def check_feed(url: str) -> tuple[bool, str, int, str]:
    """Returns (ok, message, num_entries, sample_title)."""
    try:
        r = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        return False, "timeout", 0, ""
    except requests.exceptions.SSLError as e:
        return False, f"SSL error: {e}", 0, ""
    except requests.exceptions.ConnectionError:
        return False, "connection failed", 0, ""
    except Exception as e:
        return False, f"error: {type(e).__name__}", 0, ""

    if r.status_code != 200:
        return False, f"HTTP {r.status_code}", 0, ""

    content_type = r.headers.get("Content-Type", "").lower()
    body = r.content[:2000].decode("utf-8", errors="replace").lower()

    looks_like_feed = (
        "xml" in content_type
        or "rss" in content_type
        or "atom" in content_type
        or "<rss" in body
        or "<feed" in body
        or "<?xml" in body
    )

    if not looks_like_feed:
        return False, f"not RSS/Atom (got {content_type or 'no Content-Type'})", 0, ""

    parsed = feedparser.parse(r.content)
    n = len(parsed.entries)
    if n == 0:
        return False, "parsed but zero entries", 0, ""

    sample = parsed.entries[0].get("title", "(no title)")[:80]
    return True, "OK", n, sample


def main() -> int:
    print(f"\nVerifying {len(SOURCES)} sources...\n")

    failed_sources: list[str] = []

    for src in SOURCES:
        name = src["name"]
        feeds = src["feeds"]

        if not feeds:
            print(f"  {name}")
            print(f"    {DIM}(disabled — no feed configured){RESET}\n")
            continue

        print(f"  {name}")
        any_worked = False
        for feed_url in feeds:
            ok, msg, n, sample = check_feed(feed_url)
            short_url = feed_url.replace("https://", "").replace("http://", "")
            if ok:
                print(f"    {GREEN}✓{RESET} {short_url}")
                print(f"      {DIM}{n} entries · sample: \"{sample}\"{RESET}")
                any_worked = True
            else:
                colour = RED
                print(f"    {colour}✗{RESET} {short_url}  {DIM}({msg}){RESET}")

        if not any_worked:
            failed_sources.append(name)
            print(f"    {YELLOW}→ no working feed for this source{RESET}")
        print()

    print("─" * 60)
    if failed_sources:
        print(f"\n{RED}{len(failed_sources)} source(s) have no working feed:{RESET}")
        for name in failed_sources:
            print(f"  - {name}")
        print(f"\n{YELLOW}What to do:{RESET}")
        print("  1. Visit each failing site, look for an RSS link in the page source")
        print("     or footer. Common alternatives: /rss, /rss.xml, /feed/atom/, /?feed=rss2")
        print("  2. Update SOURCES in pipeline/run.py")
        print("  3. Re-run this script.")
        print("  4. If a site truly has no feed, you can leave it in the list —")
        print("     the pipeline logs the failure and continues with the others.\n")
        return 1
    else:
        print(f"\n{GREEN}All sources have at least one working feed.{RESET}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
