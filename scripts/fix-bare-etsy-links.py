#!/usr/bin/env python3
"""
Fix bare (unmonetized) Etsy links left behind by migrate-etsy-affiliate-links.py.

That script only converted Awin URLs, so plain https://www.etsy.com/... links
were never in scope. This handles the leftovers.

Three cases:

1. Text-label link   [Catan Minimalist Prints](https://www.etsy.com/...)
   -> wrap in Rakuten deeplink.

2. Image-wrapped     [![Hexagamers](https://img...)](https://www.etsy.com/...)
   -> wrap in Rakuten deeplink. The IMAGE src is left alone.

3. Empty-label       [](https://www.etsy.com/...)
   -> DELETE. These render as invisible zero-width anchors sitting in front of
      the real (already-monetized) heading link. They are migration debris from
      the WordPress conversion, click nothing, and if they were monetized they
      would just be untrackable duplicates of the link beside them.

Usage:
  python scripts/fix-bare-etsy-links.py --dry-run
  python scripts/fix-bare-etsy-links.py
"""

import re
import sys
from pathlib import Path
from urllib.parse import quote

RAKUTEN_SID = "4706536"
RAKUTEN_MID = "54027"
RAKUTEN_BASE = "https://click.linksynergy.com/deeplink"

ROOT = Path("/workspaces/projects/hexagamers")
POSTS_DIR = ROOT / "site/src/content/posts"

# Case 3: empty-label link -> delete entirely
EMPTY_LABEL = re.compile(r'\[\]\((https://www\.etsy\.com/[^)]*)\)')

# Case 2: image-wrapped link -> keep inner image, wrap outer href
IMAGE_WRAPPED = re.compile(
    r'(\[!\[[^\]]*\]\([^)]*\)\])\((https://www\.etsy\.com/[^)]*)\)'
)

# Case 1: plain text-label link -> wrap href
TEXT_LABEL = re.compile(
    r'(\[(?!!)[^\]]+\])\((https://www\.etsy\.com/[^)]*)\)'
)


def build_rakuten(etsy_url: str) -> str:
    return f"{RAKUTEN_BASE}?id={RAKUTEN_SID}&mid={RAKUTEN_MID}&murl={quote(etsy_url, safe='')}"


def fix_file(path: Path, dry_run: bool = False):
    text = path.read_text(encoding="utf-8")
    original = text
    stats = {"deleted": 0, "image": 0, "text": 0}

    # Order matters: strip empty-label anchors BEFORE the text-label pass,
    # so nothing else can match their remains.
    def drop_empty(m):
        stats["deleted"] += 1
        if dry_run:
            print(f"    DELETE empty anchor -> {m.group(1)[:70]}")
        return ""
    text = EMPTY_LABEL.sub(drop_empty, text)

    def wrap_image(m):
        stats["image"] += 1
        if dry_run:
            print(f"    WRAP  image link   -> {m.group(2)[:70]}")
        return f"{m.group(1)}({build_rakuten(m.group(2))})"
    text = IMAGE_WRAPPED.sub(wrap_image, text)

    def wrap_text(m):
        stats["text"] += 1
        if dry_run:
            print(f"    WRAP  text link    -> {m.group(2)[:70]}")
        return f"{m.group(1)}({build_rakuten(m.group(2))})"
    text = TEXT_LABEL.sub(wrap_text, text)

    changed = sum(stats.values())
    if changed and not dry_run:
        path.write_text(text, encoding="utf-8")

    return stats, changed, original, text


def main():
    dry_run = "--dry-run" in sys.argv
    mode = "DRY RUN" if dry_run else "APPLYING CHANGES"
    print(f"\n=== Fix bare Etsy links ({mode}) ===\n")

    total = {"deleted": 0, "image": 0, "text": 0}
    files = sorted(POSTS_DIR.glob("*.md"))  # .bak files excluded (gitignored)

    for path in files:
        text = path.read_text(encoding="utf-8")
        if "https://www.etsy.com" not in text:
            continue
        print(f"  {path.name}:")
        stats, changed, _, _ = fix_file(path, dry_run=dry_run)
        for k in total:
            total[k] += stats[k]
        print(f"    -> {stats['text']} text, {stats['image']} image, {stats['deleted']} deleted\n")

    print(f"Totals: {total['text']} text-label wrapped, "
          f"{total['image']} image-wrapped, {total['deleted']} empty anchors removed")

    # Safety net: nothing bare should survive.
    if not dry_run:
        leftover = 0
        for path in POSTS_DIR.glob("*.md"):
            leftover += len(re.findall(r'\]\(https://www\.etsy\.com/', path.read_text(encoding="utf-8")))
        print(f"Verification: {leftover} bare Etsy links remaining (expected 0)")
    else:
        print("\nRun without --dry-run to apply.")


if __name__ == "__main__":
    main()
