"""
ezNews Malawi — daily content pipeline.

Runs once per day. Steps:
  1. Fetch headlines + summaries from Malawi news sources (RSS preferred, HTML fallback).
  2. Cluster articles that cover the same story (need 3+ sources to qualify).
  3. Pick the top 5 clusters by source-count and recency.
  4. For each, send to Claude to produce simplified English (A1) + Chichewa (A2).
  5. Write site/data/articles.json (atomic replace).

Designed to be replaced piecewise: swap out source list, clustering algo, or
LLM provider without touching the rest.

Run locally:    python pipeline/run.py
Run in CI:      see .github/workflows/daily.yml
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import hashlib
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import feedparser  # type: ignore
import requests
from bs4 import BeautifulSoup  # type: ignore
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
import numpy as np
from anthropic import Anthropic

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("eznews")

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "site" / "data" / "articles.json"

# ---------------------------------------------------------------------------
# Source registry. 11 outlets, curated.
#
# Each source has: name, homepage URL, list of RSS feed URLs to try in order.
# All assumed to be the standard WordPress /feed/ path — verify with
# `python pipeline/verify_sources.py` before going live, and adjust as needed.
#
# Tier 1: 9 core general-news outlets
# Tier 2: 2 business-focused outlets
# ---------------------------------------------------------------------------
SOURCES: list[dict[str, Any]] = [
    # --- Tier 1: core general news ---
    {
        "name": "Nation Online",
        "homepage": "https://mwnation.com",
        "feeds": ["https://mwnation.com/feed/"],
    },
    {
        "name": "Nyasa Times",
        "homepage": "https://www.nyasatimes.com",
        "feeds": ["https://www.nyasatimes.com/feed/"],
    },
    {
        "name": "Daily Times",
        "homepage": "https://times.mw",
        "feeds": ["https://times.mw/feed/"],
    },
    {
        "name": "Zodiak",
        "homepage": "https://www.zodiakmalawi.com",
        "feeds": [],  # No working RSS feed found. Site does not publish RSS as of last check.
    },
    {
        "name": "Capital FM",
        "homepage": "https://www.capitalradiomalawi.com",
        "feeds": [],  # SSL configuration issue on server. Re-test with `verify_sources.py` periodically.
    },
    {
        "name": "Malawi24",
        "homepage": "https://malawi24.com",
        "feeds": ["https://malawi24.com/feed/"],
    },
    {
        "name": "Maravi Post",
        "homepage": "https://www.maravipost.com",
        "feeds": ["https://www.maravipost.com/feed/"],
    },
    {
        "name": "Malawi News Agency",
        "homepage": "https://www.manaonline.gov.mw",
        "feeds": [],  # Site doesn't publish RSS. Re-test occasionally.
    },
    {
        "name": "Malawi Voice",
        "homepage": "https://www.malawivoice.com",
        "feeds": ["https://www.malawivoice.com/feed/"],
    },
    {
        "name": "MBC",
        "homepage": "https://mbc.mw",
        "feeds": ["https://mbc.mw/feed/"],
    },
    # --- Tier 2: business-focused ---
    {
        "name": "Biz Malawi",
        "homepage": "https://www.bizmalawi.com",
        "feeds": ["https://www.bizmalawi.com/feed/"],
    },
    {
        "name": "Business Malawi",
        "homepage": "https://www.businessmalawi.com",
        "feeds": ["https://www.businessmalawi.com/feed/"],
    },
]

USER_AGENT = "ezNews-Malawi-Bot/1.0 (+contact: you@example.com)"
HTTP_TIMEOUT = 30
MAX_AGE_HOURS = 36           # only consider stories from the last 36 hours
MIN_SOURCES = 2              # a story must appear in at least N sources
TARGET_STORIES = 5           # final number of stories to publish
SIMILARITY_THRESHOLD = 0.18  # tune empirically; lower = looser clusters


# ---------------------------------------------------------------------------
# Step 1: fetch
# ---------------------------------------------------------------------------

@dataclass
class RawArticle:
    source_name: str
    source_homepage: str
    title: str
    url: str
    summary: str
    published: datetime

    @property
    def id(self) -> str:
        return hashlib.sha256(self.url.encode()).hexdigest()[:12]


def fetch_source(src: dict[str, Any]) -> list[RawArticle]:
    """Pull recent articles from one source via its RSS feed."""
    out: list[RawArticle] = []
    skipped_old = 0
    skipped_bad = 0
    total_entries = 0
    for feed_url in src["feeds"]:
        try:
            log.info("Fetching %s", feed_url)
            r = requests.get(
                feed_url,
                headers={"User-Agent": USER_AGENT},
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            parsed = feedparser.parse(r.content)
        except Exception as e:
            log.warning("Failed to fetch %s: %s", feed_url, e)
            continue

        cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
        for entry in parsed.entries[:30]:
            total_entries += 1
            try:
                title = (entry.get("title") or "").strip()
                url = (entry.get("link") or "").strip()
                if not title or not url:
                    skipped_bad += 1
                    continue

                summary_html = (
                    entry.get("summary")
                    or entry.get("description")
                    or ""
                )
                summary = BeautifulSoup(summary_html, "html.parser").get_text(" ", strip=True)
                summary = re.sub(r"\s+", " ", summary)[:1200]

                pub_struct = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub_struct:
                    pub = datetime(*pub_struct[:6], tzinfo=timezone.utc)
                else:
                    # No date in feed. Assume recent rather than skipping —
                    # it's better to over-include than to lose half the input.
                    pub = datetime.now(timezone.utc)
                if pub < cutoff:
                    skipped_old += 1
                    continue

                out.append(RawArticle(
                    source_name=src["name"],
                    source_homepage=src["homepage"],
                    title=title,
                    url=url,
                    summary=summary,
                    published=pub,
                ))
            except Exception as e:
                log.debug("Bad entry in %s: %s", feed_url, e)
                skipped_bad += 1
                continue
    if len(out) == 0 and total_entries > 0:
        log.info(
            "  -> 0 recent articles from %s (skipped %d as old, %d as malformed, of %d total)",
            src["name"], skipped_old, skipped_bad, total_entries,
        )
    else:
        log.info("  -> %d recent articles from %s", len(out), src["name"])
    return out


def fetch_full_article(url: str, max_chars: int = 5000) -> str:
    """
    Fetch the full text of an article. Falls back to empty string on any failure.
    Used to enrich the input to Claude beyond the short RSS summary.
    """
    try:
        r = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
    except Exception as e:
        log.debug("Could not fetch full article %s: %s", url, e)
        return ""

    soup = BeautifulSoup(r.content, "html.parser")
    # Strip elements that are noise: scripts, styles, navigation, sidebars
    for tag in soup(["script", "style", "nav", "header", "footer", "aside",
                     "form", "button", "iframe", "noscript"]):
        tag.decompose()

    # Try to find the actual article content. WordPress sites typically use
    # <article> or .post-content / .entry-content. Fall back to <main> or full body.
    candidates = (
        soup.find("article")
        or soup.find(class_=re.compile(r"post-content|entry-content|article-body|story-body|article__body"))
        or soup.find("main")
        or soup.body
    )
    if not candidates:
        return ""

    text = candidates.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def fetch_all() -> list[RawArticle]:
    items: list[RawArticle] = []
    for src in SOURCES:
        items.extend(fetch_source(src))
        time.sleep(1)  # be polite
    log.info("Fetched %d total articles from %d sources", len(items), len(SOURCES))
    return items


# ---------------------------------------------------------------------------
# Step 2: cluster
# ---------------------------------------------------------------------------

@dataclass
class Cluster:
    articles: list[RawArticle] = field(default_factory=list)

    @property
    def sources(self) -> list[str]:
        """
        Distinct sources, after near-duplicate detection.
        If two articles share >70% of their text, they're treated as syndicated
        copies of the same content — only the first source name is counted.
        This protects the consensus filter from being fooled by content sharing
        between outlets.
        """
        kept_articles = self._dedupe_articles()
        seen: list[str] = []
        for a in kept_articles:
            if a.source_name not in seen:
                seen.append(a.source_name)
        return seen

    def _dedupe_articles(self) -> list[RawArticle]:
        """Drop articles that look like syndicated copies of earlier ones."""
        kept: list[RawArticle] = []
        for a in self.articles:
            is_dup = False
            for k in kept:
                if _text_overlap(a.title + " " + a.summary, k.title + " " + k.summary) > 0.70:
                    is_dup = True
                    log.info(
                        "  near-duplicate: '%s' (%s) ≈ '%s' (%s) — treating as one source",
                        a.title[:50], a.source_name, k.title[:50], k.source_name,
                    )
                    break
            if not is_dup:
                kept.append(a)
        return kept

    @property
    def latest(self) -> datetime:
        return max(a.published for a in self.articles)


def _text_overlap(a: str, b: str) -> float:
    """Jaccard similarity over word sets. 0.0 = nothing shared, 1.0 = identical."""
    wa = set(re.findall(r"\w+", a.lower()))
    wb = set(re.findall(r"\w+", b.lower()))
    if not wa or not wb:
        return 0.0
    intersection = len(wa & wb)
    union = len(wa | wb)
    return intersection / union if union else 0.0


def cluster_articles(articles: list[RawArticle]) -> list[Cluster]:
    """Greedy single-link clustering on TF-IDF cosine similarity of (title + summary)."""
    if not articles:
        return []
    docs = [f"{a.title}. {a.summary}" for a in articles]
    vec = TfidfVectorizer(
        max_features=4000,
        ngram_range=(1, 2),
        stop_words="english",
        min_df=1,
    )
    matrix = vec.fit_transform(docs)
    sim = cosine_similarity(matrix)

    n = len(articles)
    assigned = [-1] * n
    clusters: list[Cluster] = []

    for i in range(n):
        if assigned[i] != -1:
            continue
        cid = len(clusters)
        clusters.append(Cluster(articles=[articles[i]]))
        assigned[i] = cid
        for j in range(i + 1, n):
            if assigned[j] != -1:
                continue
            if sim[i, j] >= SIMILARITY_THRESHOLD:
                clusters[cid].articles.append(articles[j])
                assigned[j] = cid

    log.info("Built %d clusters", len(clusters))
    return clusters


def select_top(clusters: list[Cluster], k: int) -> list[Cluster]:
    qualifying = [c for c in clusters if len(c.sources) >= MIN_SOURCES]
    qualifying.sort(key=lambda c: (len(c.sources), c.latest), reverse=True)
    log.info("Clusters with %d+ sources: %d", MIN_SOURCES, len(qualifying))

    # Diagnostic: if nothing qualifies, show the largest near-misses so we can
    # tell whether the issue is matching being too strict, or just too few outlets
    # covering the same story today.
    if not qualifying:
        near_misses = sorted(clusters, key=lambda c: len(c.articles), reverse=True)[:5]
        log.info("Top 5 near-miss clusters (would need %d+ sources):", MIN_SOURCES)
        for i, c in enumerate(near_misses, 1):
            sources_str = ", ".join(c.sources) or "(none)"
            log.info(
                "  #%d: %d articles from %d source(s) [%s]",
                i, len(c.articles), len(c.sources), sources_str,
            )
            for a in c.articles[:3]:
                log.info("    - %s: %s", a.source_name, a.title[:80])

    return qualifying[:k]


# ---------------------------------------------------------------------------
# Step 3: rewrite (Claude)
# ---------------------------------------------------------------------------

VALID_TAGS = ["politics", "economy", "health", "sport", "society", "international"]


def _extract_json_object(text: str) -> str:
    """
    Given a string that contains a JSON object somewhere (possibly with extra
    prose before/after), return just the outermost {...} substring. Tracks
    nesting and respects strings so braces inside string values don't confuse it.
    Returns the input unchanged if it can't find a balanced object.
    """
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text  # unbalanced — let json.loads raise the real error

REWRITE_SYSTEM_PROMPT = """You are an editor for ezNews Malawi, a news website serving the general public of Malawi.

Your job: take versions of the same news story (from different Malawi outlets) and produce ONE clean, neutral, factual rewrite in simple English (CEFR A1).

The article is in two parts: "body" (opening) and "body_more" (continuation). Together they form one continuous article that reads as one piece — no recap, no re-introduction, no repeated facts.

This English version will be machine-translated into Chichewa afterwards, so the English needs to be precise, factual, and unambiguous. Any vagueness or factual mistakes will be carried into the translation.

Hard requirements:
- Output MUST be a single valid JSON object, nothing else. No markdown fences. No commentary before, after, or alongside the JSON. The very first character must be `{` and the very last must be `}`.
- The English MUST use CEFR A1 vocabulary. Roughly 500-800 common words. Present tense dominant, very short sentences (max 8 words, one idea per sentence), concrete nouns and verbs, no abstract nouns where avoidable.
- Tone: serious, clean, neutral. Not dull, but no opinion, no hype, no editorialising.
- Title: max 12 words.

FACTUAL ACCURACY (critical — this is now the most important rule):

This article will be machine-translated into Chichewa for Malawian readers. Any error here will reach them too. Therefore:

- DAYS OF THE WEEK: Only state a day if the source material clearly says it. If a source says "Thursday", write "Thursday" — not Wednesday. Double-check by re-reading the source before writing the body.
- NAMES AND TITLES: Use exact names and titles from the sources. "Minister of Trade Simon Itaye" not "Trade colleague Itaye". "Reserve Bank Governor" not "Bank Boss". If a source uses an unusual title, keep the official version.
- NUMBERS AND DATES: Quote currency amounts and dates exactly. If the source says "K600 million", write "K600 million". If it says "27 May", write "27 May". But AVOID percentages and decimals — replace them with simple phrases: "90.9 percent" → "almost all", "65 percent" → "more than half", "22.9 percent more" → "much more". Only keep a percentage if the story makes no sense without it.
- PLACE NAMES: Use the exact place name from the sources. "Blantyre" not "Bantyre". "Chichiri Trade Fair Grounds" not "the fair grounds".
- IF SOURCES DISAGREE: Mention the most-stated version. If they disagree fundamentally on a key fact, state it neutrally ("Reports say between 8 and 12 people died") or omit the disputed detail.
- IF UNSURE: Leave the detail out rather than guessing.

A1 ENGLISH GUIDANCE (still important):

EXPLAIN HARD WORDS: If a necessary word is hard (debt, interest, budget, election, court, tax), explain it once in one short sentence right after first use. Example: "Debt is money a country must pay back." Repetition is good — repeat the same word instead of using synonyms.

DO use words like: said, told, asked, saw, came, went, gave, took, helped, made, found, started, stopped, went home, died, lived, was, were, will, can, want, need, big, small, new, old, good, bad, many, few, all, some.

DO NOT use words like: announced, declared, stated, reported, conducted, undertook, screened, assessed, evaluated, supported, deployed, implemented, expressed, commenced, terminated, transported, conveyed, accommodated, sympathies, condolences, welfare, crisis, situation, authorities, officials, in light of, with regard to, on behalf of, in collaboration with, in cooperation with, grateful, transparent, regardless, outgoing, incoming, congratulated, institution, strengthen, protect, leadership, accordingly, achieved, established, addressed, encountered, consequently, furthermore, additionally, despite, however, nevertheless.

REPLACE PHRASES with simpler ones:
- "expressed sympathy" → "said sorry to the families"
- "undertook screening" → "checked"
- "in collaboration with the authorities" → "with help from the police"
- "the situation" → "what happened"
- "officials" → "the government"
- "the survivors were transported" → "the people were taken"
- "outgoing chairperson" → "the old leader"
- "congratulated him" → "said well done"

PRESERVE these words even though they look "hard" — these are precise terms that lose accuracy if simplified:
- Names of ministers, MPs, officials, athletes (keep exact names and titles)
- Names of organisations (Reserve Bank of Malawi, Anti-Corruption Bureau, Tea Association of Malawi)
- Place names (Blantyre, Lilongwe, Mzuzu, district names)
- Currency amounts in their original form (K600 million, US$1.5 billion)
- Dates and days in their original form
- Official event names (Malawi International Trade Fair, AFCON qualifier)

The "body" field:
- 50-80 words
- Cover the core facts: what happened, who, where, when, the immediate result

The "body_more" field:
- A direct continuation of "body" — never re-introduce the story, never re-state who or what was already named, never recap the headline
- TARGET: around 300 words. Acceptable range: 220-380 words. Going below 220 should be rare.
- Extract every fact from the sources: every name, place, number, date, quote (paraphrased), action, reason, consequence, reaction.
- MUST be split into THREE OR FOUR paragraphs separated by \\n\\n. Never one giant block of text.
- Start naturally — as if continuing the article. NOT: "[Name] said..." (already in body). YES: "The arrest follows...", "Earlier this week...", "Officials added that..."

Pick exactly one tag from this list: politics, economy, health, sport, society, international.

Output JSON shape:
{
  "tag": "<one of the allowed tags>",
  "title": "...",
  "body": "...",
  "body_more": "...\\n\\n..."
}
"""


def build_user_message(cluster: Cluster) -> str:
    parts = ["Here are versions of the same story from different Malawi news sites:\n"]
    # Use deduplicated articles only — we don't want to give Claude two copies of
    # the same syndicated text and have it average them.
    for i, a in enumerate(cluster._dedupe_articles(), 1):
        parts.append(f"--- Source {i}: {a.source_name} ---")
        parts.append(f"Title: {a.title}")
        # Try to fetch the full article. If it fails or returns nothing useful,
        # fall back to the short RSS summary.
        full = fetch_full_article(a.url)
        if full and len(full) > len(a.summary):
            parts.append(f"Article text: {full}")
        else:
            parts.append(f"Summary: {a.summary}")
        parts.append("")
    parts.append(
        "Produce the JSON object as specified. Remember: very simple A1 English "
        "(max 8 words per sentence, no percentages, explain hard words), "
        "natural A2 Chichewa, neutral tone, only facts from the sources. "
        "The body_more must be ABOUT 300 WORDS (acceptable: 220-380) split across "
        "3-4 paragraphs, drawing on every relevant fact from the article texts above. "
        "If you find yourself writing only 150 words, go back and look for more "
        "details in the source articles — there is almost always more there."
    )
    return "\n".join(parts)


def rewrite_cluster(client: Anthropic, cluster: Cluster) -> dict[str, Any] | None:
    try:
        msg = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=3000,
            system=REWRITE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_message(cluster)}],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        ).strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        # If Claude added extra text before/after the JSON, find the outermost
        # {...} block and use just that. Handles nested braces correctly.
        text = _extract_json_object(text)
        data = json.loads(text)

        for path in [
            ["tag"],
            ["title"], ["body"], ["body_more"],
        ]:
            cur = data
            for key in path:
                cur = cur[key]
            if not isinstance(cur, str) or not cur.strip():
                raise ValueError(f"Missing or empty field: {'/'.join(path)}")

        if data["tag"] not in VALID_TAGS:
            log.warning("Invalid tag '%s', defaulting to 'society'", data["tag"])
            data["tag"] = "society"

        return data
    except json.JSONDecodeError as e:
        log.error("LLM returned invalid JSON: %s", e)
        return None
    except Exception as e:
        log.error("Rewrite failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Step 4: Translation (English → Chichewa) with quality check
# ---------------------------------------------------------------------------

GOOGLE_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"

# Back-translation quality threshold. If the round-trip similarity is below
# this, mark the article as "auto-translated, needs review". Tune empirically.
TRANSLATION_QUALITY_THRESHOLD = 0.55


def google_translate(text: str, source: str, target: str, api_key: str) -> str | None:
    """Translate text using Google Cloud Translation API v2."""
    try:
        r = requests.post(
            GOOGLE_TRANSLATE_URL,
            params={"key": api_key},
            json={"q": text, "source": source, "target": target, "format": "text"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return data["data"]["translations"][0]["translatedText"]
    except Exception as e:
        log.error("Google Translate failed (%s → %s): %s", source, target, e)
        return None


def _word_overlap(a: str, b: str) -> float:
    """Jaccard similarity over word sets. Used for back-translation quality check."""
    wa = set(re.findall(r"\w+", a.lower()))
    wb = set(re.findall(r"\w+", b.lower()))
    if not wa or not wb:
        return 0.0
    intersection = len(wa & wb)
    union = len(wa | wb)
    return intersection / union if union else 0.0


def translate_with_quality_check(
    text: str, api_key: str
) -> tuple[str | None, float]:
    """
    Translate English text to Chichewa and run a back-translation quality check.

    Returns (chichewa_text, quality_score). The quality_score is 0.0–1.0 based
    on how well the back-translated English matches the original. A high score
    means the translation is likely accurate; a low score means parts may have
    been mistranslated.

    Returns (None, 0.0) if translation fails.
    """
    if not text or not text.strip():
        return "", 1.0  # nothing to translate, vacuously fine

    ny = google_translate(text, source="en", target="ny", api_key=api_key)
    if ny is None:
        return None, 0.0

    # Back-translation: ny → en, compared with original
    en_back = google_translate(ny, source="ny", target="en", api_key=api_key)
    if en_back is None:
        # We got the translation but can't verify quality
        log.warning("Back-translation failed; translation kept but unverified")
        return ny, 0.5  # neutral score

    score = _word_overlap(text, en_back)
    return ny, score


def translate_article_fields(
    rewritten: dict[str, Any], api_key: str
) -> tuple[dict[str, str] | None, float]:
    """
    Translate the title, body, and body_more fields of an English article
    into Chichewa. Returns (chichewa_dict, overall_quality_score).
    """
    en = rewritten  # flat shape: title, body, body_more directly in dict

    ny_title, score_title = translate_with_quality_check(en["title"], api_key)
    if ny_title is None:
        return None, 0.0

    ny_body, score_body = translate_with_quality_check(en["body"], api_key)
    if ny_body is None:
        return None, 0.0

    ny_body_more, score_body_more = translate_with_quality_check(en["body_more"], api_key)
    if ny_body_more is None:
        return None, 0.0

    # Weighted average: body and body_more matter more than title
    overall = (score_title * 0.1) + (score_body * 0.3) + (score_body_more * 0.6)

    log.info(
        "Translation quality: title=%.2f, body=%.2f, body_more=%.2f, overall=%.2f",
        score_title, score_body, score_body_more, overall,
    )

    return {
        "title": ny_title,
        "body": ny_body,
        "body_more": ny_body_more,
    }, overall


# ---------------------------------------------------------------------------
# Step 5: assemble JSON
# ---------------------------------------------------------------------------

def cluster_to_article(
    cluster: Cluster,
    rewritten: dict[str, Any],
    ny: dict[str, str] | None,
    ny_quality: float,
) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date().isoformat()
    slug_basis = rewritten["title"].lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug_basis).strip("-")[:50] or "story"

    # Use the deduplicated list — don't show readers two "sources" that are
    # really the same syndicated article.
    seen: set[str] = set()
    sources: list[dict[str, str]] = []
    for a in cluster._dedupe_articles():
        if a.source_name in seen:
            continue
        seen.add(a.source_name)
        sources.append({"name": a.source_name, "url": a.url})

    article = {
        "id": f"{today}-{slug}",
        "tag": rewritten["tag"],
        "published": cluster.latest.isoformat(),
        "en": {
            "title": rewritten["title"],
            "body": rewritten["body"],
            "body_more": rewritten["body_more"],
        },
        "sources": sources,
    }

    if ny is not None:
        article["ny"] = ny
        article["ny_quality"] = round(ny_quality, 3)
        # If the back-translation check is below threshold, flag for review
        if ny_quality < TRANSLATION_QUALITY_THRESHOLD:
            article["ny_needs_review"] = True

    return article


def load_existing_articles() -> dict[str, dict[str, Any]]:
    """Load the previous articles.json, indexed by id, for merge purposes."""
    if not OUT_PATH.exists():
        return {}
    try:
        data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        return {a["id"]: a for a in data.get("articles", []) if "id" in a}
    except Exception as e:
        log.warning("Could not read previous articles.json: %s", e)
        return {}


def merge_with_reviewed(
    new_article: dict[str, Any],
    previous_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    If the editor has marked an article as reviewed (ny_reviewed: true), preserve
    their Chichewa text instead of overwriting it with fresh AI output. Everything
    else (English, sources, timestamps) is updated normally.
    """
    prev = previous_by_id.get(new_article["id"])
    if not prev:
        return new_article  # brand-new article, nothing to preserve

    if prev.get("ny_reviewed") is True:
        new_article["ny"] = prev.get("ny", new_article["ny"])
        new_article["ny_reviewed"] = True
        if prev.get("ny_reviewed_at"):
            new_article["ny_reviewed_at"] = prev["ny_reviewed_at"]
        log.info("Preserved human-reviewed Chichewa for %s", new_article["id"])

    return new_article


MAX_ARCHIVE_ARTICLES = 500   # cap the archive size so articles.json doesn't grow forever


def find_matching_existing_article(
    cluster: Cluster,
    existing_articles: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Look at the cluster's source URLs. If we've already published an article
    that drew on the same URLs, this is the same story — return that article
    so we can update it rather than create a duplicate.

    Match criterion: at least one shared source URL between the cluster and an
    existing article. Source URLs are stable identifiers — if Nyasa Times wrote
    article X yesterday and we re-cluster it tonight, the URL is the same.
    """
    cluster_urls = {a.url for a in cluster.articles}
    if not cluster_urls:
        return None

    for existing in existing_articles:
        existing_urls = {s.get("url") for s in existing.get("sources", []) if isinstance(s, dict)}
        if cluster_urls & existing_urls:  # any overlap = same story
            return existing
    return None


def merge_new_sources_into_existing(
    existing: dict[str, Any],
    cluster: Cluster,
) -> dict[str, Any]:
    """
    The cluster matches a story we've already published. Don't regenerate it —
    just add any new sources the cluster brings, and update the published time
    to the latest of the two.
    """
    existing_urls = {s.get("url") for s in existing.get("sources", []) if isinstance(s, dict)}
    seen_names = {s.get("name") for s in existing.get("sources", []) if isinstance(s, dict)}

    new_sources = list(existing.get("sources", []))
    added = 0
    for a in cluster._dedupe_articles():
        if a.url in existing_urls:
            continue
        if a.source_name in seen_names:
            continue
        new_sources.append({"name": a.source_name, "url": a.url})
        seen_names.add(a.source_name)
        added += 1

    if added > 0:
        existing["sources"] = new_sources
        log.info(
            "Updated existing article '%s' with %d new sources (now %d total)",
            existing["id"], added, len(new_sources),
        )

    # bump published time forward only if newer
    cluster_latest = cluster.latest.isoformat()
    if cluster_latest > existing.get("published", ""):
        existing["published"] = cluster_latest

    return existing


def write_output(
    articles: list[dict[str, Any]],
    updated_existing: list[dict[str, Any]] | None = None,
    existing_articles: list[dict[str, Any]] | None = None,
) -> None:
    """
    Build the new articles.json from three inputs:
      - `articles`: brand-new articles (just generated by Claude)
      - `updated_existing`: existing articles that got new sources added
      - `existing_articles`: full archive from previous runs (passed in by main)

    Everything is merged, deduplicated by ID, sorted newest first, and capped
    at MAX_ARCHIVE_ARTICLES so the JSON file stays a reasonable size.

    Articles previously edited (ny_reviewed: true) are handled by
    merge_with_reviewed() and arrive here with their reviewed content intact.
    """
    updated_existing = updated_existing or []
    existing_articles = existing_articles or []

    # If main() didn't pass the archive in, load it from disk as a fallback
    if not existing_articles and OUT_PATH.exists():
        try:
            data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
            existing_articles = data.get("articles", [])
        except Exception as e:
            log.warning("Couldn't read existing archive, starting fresh: %s", e)

    updated_ids = {a["id"] for a in updated_existing}
    new_ids = {a["id"] for a in articles}

    # Keep archive articles that weren't replaced or updated this run
    untouched = [
        a for a in existing_articles
        if a.get("id") not in updated_ids and a.get("id") not in new_ids
    ]

    combined = articles + updated_existing + untouched
    combined.sort(key=lambda a: a.get("published", ""), reverse=True)
    combined = combined[:MAX_ARCHIVE_ARTICLES]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "articles": combined,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUT_PATH)
    log.info(
        "Wrote archive: %d new, %d updated in place, %d untouched, %d total",
        len(articles), len(updated_existing), len(untouched), len(combined),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY environment variable not set.")
        return 1

    google_key = os.environ.get("GOOGLE_TRANSLATE_API_KEY")
    if not google_key:
        log.warning(
            "GOOGLE_TRANSLATE_API_KEY not set — pipeline will run but produce "
            "English-only articles. Set the secret in GitHub to enable Chichewa."
        )

    client = Anthropic(api_key=api_key)

    raw = fetch_all()
    if not raw:
        log.error("No articles fetched. Aborting and keeping previous output.")
        return 1

    clusters = cluster_articles(raw)
    top = select_top(clusters, k=TARGET_STORIES)

    if not top:
        log.warning(
            "No clusters with %d+ sources today. Keeping previous output.",
            MIN_SOURCES,
        )
        return 0

    final: list[dict[str, Any]] = []
    existing_articles = list(load_existing_articles().values())
    updated_existing: list[dict[str, Any]] = []  # articles updated in place rather than regenerated

    for c in top:
        # Check if this cluster is the same story as something already in the archive
        match = find_matching_existing_article(c, existing_articles)
        if match is not None:
            log.info(
                "Cluster matches existing article '%s' — updating in place, skipping LLM call",
                match["id"],
            )
            updated = merge_new_sources_into_existing(match, c)
            updated_existing.append(updated)
            continue

        log.info(
            "Rewriting cluster of %d articles from sources: %s",
            len(c.articles), ", ".join(c.sources),
        )
        rewritten = rewrite_cluster(client, c)
        if rewritten is None:
            log.warning("Skipping cluster due to rewrite failure.")
            continue

        # Translate to Chichewa, with quality check via back-translation
        ny = None
        ny_quality = 0.0
        if google_key:
            log.info("Translating to Chichewa with Google Cloud Translation...")
            ny, ny_quality = translate_article_fields(rewritten, google_key)
            if ny is None:
                log.warning("Translation failed; article will be English-only")
            elif ny_quality < TRANSLATION_QUALITY_THRESHOLD:
                log.warning(
                    "Translation quality below threshold (%.2f < %.2f) — flagging for review",
                    ny_quality, TRANSLATION_QUALITY_THRESHOLD,
                )

        article = cluster_to_article(c, rewritten, ny, ny_quality)
        previous_by_id = {a["id"]: a for a in existing_articles}
        article = merge_with_reviewed(article, previous_by_id)
        final.append(article)

    if not final and not updated_existing:
        log.error("No new articles produced and no existing articles updated. Keeping previous output.")
        return 1

    write_output(final, updated_existing=updated_existing, existing_articles=existing_articles)
    return 0


if __name__ == "__main__":
    sys.exit(main())
