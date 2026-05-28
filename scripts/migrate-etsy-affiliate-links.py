#!/usr/bin/env python3
"""
Migrate Etsy affiliate links from Awin to Rakuten.

Awin format:
  http://www.awin1.com/cread.php?awinmid=6939&awinaffid=406184&clickref=&p={URL_ENCODED_ETSY_URL}

Rakuten static deep link format:
  https://click.linksynergy.com/deeplink?id=4706536&mid=54027&murl={URL_ENCODED_ETSY_URL}
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote

RAKUTEN_SID = "4706536"
RAKUTEN_MID = "54027"
RAKUTEN_BASE = "https://click.linksynergy.com/deeplink"

POSTS_DIR = Path("/workspaces/projects/hexagamers/site/src/content/posts")

# Matches both http and https Awin URLs, capturing everything up to a quote, paren, or whitespace
AWIN_PATTERN = re.compile(
    r'https?://(?:www\.)?awin1\.com/cread\.php\?[^\s")\]>]+'
)


def extract_etsy_url(awin_url: str) -> str | None:
    parsed = urlparse(awin_url)
    params = parse_qs(parsed.query)
    p_values = params.get("p")
    if not p_values:
        return None
    return p_values[0]  # parse_qs already URL-decodes


def build_rakuten_url(etsy_url: str) -> str:
    encoded = quote(etsy_url, safe="")
    return f"{RAKUTEN_BASE}?id={RAKUTEN_SID}&mid={RAKUTEN_MID}&murl={encoded}"


def migrate_file(path: Path, dry_run: bool = False) -> int:
    text = path.read_text(encoding="utf-8")
    replacements = 0
    result = text

    for match in AWIN_PATTERN.finditer(text):
        awin_url = match.group(0)
        etsy_url = extract_etsy_url(awin_url)
        if not etsy_url:
            print(f"  WARN: could not extract Etsy URL from: {awin_url[:80]}...")
            continue
        rakuten_url = build_rakuten_url(etsy_url)
        if dry_run:
            print(f"  [{replacements+1}] {awin_url[:60]}...")
            print(f"       -> {rakuten_url[:80]}...")
        result = result.replace(awin_url, rakuten_url, 1)
        replacements += 1

    if not dry_run and replacements > 0:
        path.write_text(result, encoding="utf-8")

    return replacements


def main():
    dry_run = "--dry-run" in sys.argv
    mode = "DRY RUN" if dry_run else "APPLYING CHANGES"
    print(f"\n=== Etsy Affiliate Migration: Awin -> Rakuten ({mode}) ===\n")

    md_files = sorted(POSTS_DIR.glob("*.md")) + sorted(POSTS_DIR.glob("*.mdx"))
    total = 0

    for path in md_files:
        text = path.read_text(encoding="utf-8")
        if "awin1.com" not in text:
            continue
        count = migrate_file(path, dry_run=dry_run)
        if count:
            print(f"  {path.name}: {count} link(s) replaced")
            total += count

    print(f"\nTotal links {'to replace' if dry_run else 'replaced'}: {total}")
    if dry_run:
        print("\nRun without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
