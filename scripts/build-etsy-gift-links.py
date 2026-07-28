#!/usr/bin/env python3
"""
Normalize Etsy listing URLs and build Rakuten affiliate links.

Locale prefix
-------------
Collected URLs are a mix of https://www.etsy.com/ca/listing/... (28) and
https://www.etsy.com/listing/... (13), depending on whether Ryan was browsing
signed in to the Canadian storefront.

The /ca/ segment is a display-locale hint, not a separate storefront: it drives
Etsy's default currency/language presentation, not which catalogue is served or
which affiliate program the sale is booked against. Etsy shows all items to all
buyers regardless of region preference. A US reader who lands on a /ca/ URL sees
prices defaulted to CAD, which is worse for the (majority US) audience.

So: strip it. The canonical form is https://www.etsy.com/listing/<id>/<slug>,
which lets Etsy resolve locale from the visitor instead of pinning it to Canada.

This does NOT have the amazon.com/amazon.ca split problem, where a .ca ASIN is a
genuinely different product page and a .com affiliate tag doesn't track on .ca.
Etsy is one marketplace with one Rakuten merchant ID (54027), so tracking is
unaffected by the prefix.

Usage:
  python scripts/build-etsy-gift-links.py            # writes enriched JSON
  python scripts/build-etsy-gift-links.py --check     # report only
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

RAKUTEN_SID = "4706536"
RAKUTEN_MID = "54027"
RAKUTEN_BASE = "https://click.linksynergy.com/deeplink"

ROOT = Path("/workspaces/projects/hexagamers")
SRC = ROOT / ".tmp/etsy-gifts.json"
OUT = ROOT / ".tmp/etsy-gifts-final.json"

LOCALE_RE = re.compile(r'^https://www\.etsy\.com/[a-z]{2}(?:-[a-z]{2})?/listing/', re.I)
LISTING_RE = re.compile(r'^https://www\.etsy\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?listing/(\d+)/([^/?#]*)')


def normalize(url: str) -> str:
    """Strip any /<locale>/ segment so Etsy resolves locale from the visitor."""
    m = LISTING_RE.match(url)
    if not m:
        raise ValueError(f"Unrecognized Etsy listing URL: {url}")
    listing_id, slug = m.groups()
    return f"https://www.etsy.com/listing/{listing_id}/{slug}"


def build_rakuten(etsy_url: str) -> str:
    return f"{RAKUTEN_BASE}?id={RAKUTEN_SID}&mid={RAKUTEN_MID}&murl={quote(etsy_url, safe='')}"


def main():
    check_only = "--check" in sys.argv
    items = json.loads(SRC.read_text(encoding="utf-8"))

    stripped = 0
    seen_ids = {}
    out = []

    for i, it in enumerate(items):
        original = it["etsy_url"]
        canonical = normalize(original)
        if LOCALE_RE.match(original):
            stripped += 1

        listing_id = LISTING_RE.match(canonical).group(1)
        if listing_id in seen_ids:
            print(f"  WARN: duplicate listing {listing_id} "
                  f"(items {seen_ids[listing_id]} and {i})")
        seen_ids[listing_id] = i

        if not it.get("image_url", "").startswith("https://i.etsystatic.com/"):
            print(f"  WARN: unexpected image host on item {i}: {it.get('image_url','')[:60]}")

        out.append({
            **it,
            "listing_id": listing_id,
            "etsy_url": canonical,
            "original_url": original,
            "affiliate_url": build_rakuten(canonical),
        })

    print(f"\nItems:            {len(out)}")
    print(f"Locale stripped:  {stripped}  (/ca/ -> canonical)")
    print(f"Already clean:    {len(out) - stripped}")
    print(f"Unique listings:  {len(seen_ids)}")

    if check_only:
        print("\n--check: nothing written.")
        return

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
