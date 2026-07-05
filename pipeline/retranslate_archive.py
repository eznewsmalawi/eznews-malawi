"""
ezNews Malawi — one-off script to re-translate all archived articles.

When the pipeline switched from Claude-only to Claude+Google translation,
articles already in the archive kept their old Chichewa (which was sometimes
poor — invented words, wrong titles, etc).

This script re-translates the Chichewa for every article in articles.json:
  - Takes the existing English text (untouched)
  - Sends each field through Google Translate
  - Runs the back-translation quality check
  - Replaces the ny block, adds ny_quality and ny_needs_review fields
  - Preserves any article already marked ny_reviewed (don't overwrite human work)

Run locally:
    set ANTHROPIC_API_KEY=... (not needed, but pipeline imports require it)
    set GOOGLE_TRANSLATE_API_KEY=your-google-key
    python pipeline/retranslate_archive.py

Cost estimate: about $0.30 for ~100 articles (Google charges per character).
"""

from __future__ import annotations

import json
import os
import sys
import time
import logging
from pathlib import Path

# Make pipeline.run importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.run import (  # noqa: E402
    translate_article_fields,
    TRANSLATION_QUALITY_THRESHOLD,
    OUT_PATH,
)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("retranslate")


def main() -> int:
    google_key = os.environ.get("GOOGLE_TRANSLATE_API_KEY")
    if not google_key:
        log.error("GOOGLE_TRANSLATE_API_KEY environment variable not set.")
        log.error("This script needs the same Google key as the pipeline.")
        return 1

    if not OUT_PATH.exists():
        log.error("No articles.json found at %s", OUT_PATH)
        return 1

    data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    articles = data.get("articles", [])
    log.info("Loaded %d articles from archive", len(articles))

    retranslated = 0
    skipped_reviewed = 0
    skipped_missing_en = 0
    failed = 0

    for i, article in enumerate(articles, 1):
        article_id = article.get("id", "(no id)")

        if article.get("ny_reviewed") is True:
            log.info("[%d/%d] Skipping %s (already human-reviewed)", i, len(articles), article_id)
            skipped_reviewed += 1
            continue

        en = article.get("en", {})
        if not en.get("title") or not en.get("body"):
            log.warning("[%d/%d] Skipping %s (no English content)", i, len(articles), article_id)
            skipped_missing_en += 1
            continue

        # Build the dict translate_article_fields expects (flat shape)
        en_flat = {
            "title": en.get("title", ""),
            "body": en.get("body", ""),
            "body_more": en.get("body_more", ""),
        }

        log.info("[%d/%d] Re-translating %s...", i, len(articles), article_id)
        try:
            ny, quality = translate_article_fields(en_flat, google_key)
        except Exception as e:
            log.error("[%d/%d] Translation failed for %s: %s", i, len(articles), article_id, e)
            failed += 1
            continue

        if ny is None:
            log.error("[%d/%d] Got None back for %s", i, len(articles), article_id)
            failed += 1
            continue

        article["ny"] = ny
        article["ny_quality"] = round(quality, 3)
        if quality < TRANSLATION_QUALITY_THRESHOLD:
            article["ny_needs_review"] = True
            log.info("[%d/%d] %s flagged for review (quality=%.2f)", i, len(articles), article_id, quality)
        else:
            article.pop("ny_needs_review", None)  # remove if previously flagged
            log.info("[%d/%d] %s OK (quality=%.2f)", i, len(articles), article_id, quality)

        retranslated += 1

        # Tiny pause to be polite to Google's API
        time.sleep(0.2)

    # Write back, atomically
    log.info("Writing updated archive...")
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({**data, "articles": articles}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(OUT_PATH)

    log.info("=" * 60)
    log.info("Done.")
    log.info("  Re-translated:           %d", retranslated)
    log.info("  Skipped (reviewed):      %d", skipped_reviewed)
    log.info("  Skipped (no English):    %d", skipped_missing_en)
    log.info("  Failed:                  %d", failed)
    log.info("  Total in archive:        %d", len(articles))
    log.info("=" * 60)
    log.info("Now commit and push the updated articles.json:")
    log.info("  git add site/data/articles.json")
    log.info("  git commit -m 'Re-translate archive with Google Translate'")
    log.info("  git push")

    return 0


if __name__ == "__main__":
    sys.exit(main())
