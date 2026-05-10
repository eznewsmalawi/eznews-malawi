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

Your job: take versions of the same news story (from different Malawi outlets) and produce ONE clean, neutral, factual rewrite in TWO languages, in TWO parts each.

The two parts together form one continuous article. Think of "body" as the opening of the article and "body_more" as the rest of it. They MUST read as one piece when joined together — no recap, no re-introduction, no repeated facts.

Hard requirements:
- Output MUST be a single valid JSON object, nothing else. No markdown fences. No commentary before, after, or alongside the JSON. The very first character must be `{` and the very last must be `}`.
- The English version MUST use CEFR A1 vocabulary. This is much simpler than ordinary "easy English". A reader who has only learned English for a few months should understand every word. The CEFR A1 register is roughly 500–800 common words: present tense dominant, short sentences (max 10 words), concrete nouns and verbs, no abstract nouns where avoidable.
- The Chichewa version must be at CEFR A2 level. Natural Chichewa, not word-for-word translation. Use everyday vocabulary. Short clear sentences.
- Tone: serious, clean, neutral. Not dull, but no opinion, no hype, no editorialising.
- Title: max 12 words in each language.

A1 ENGLISH GUIDANCE (critical — most AI gets this wrong):

DO use words like: said, told, asked, saw, came, went, gave, took, helped, made, found, started, stopped, went home, died, lived, was, were, will, can, want, need, big, small, new, old, good, bad, many, few, all, some.

DO NOT use words like: announced, declared, stated, reported, conducted, undertook, screened, assessed, evaluated, supported, deployed, implemented, expressed, commenced, terminated, transported, conveyed, accommodated, sympathies, condolences, welfare, crisis, situation, authorities, officials, commenced, in light of, with regard to, on behalf of, in collaboration with, in cooperation with, in coordination with, grateful, transparent, regardless, outgoing, incoming, congratulated, congratulations, institution, strengthen, protect, freedom, leadership, previous, ahead, accordingly, achieved, established, addressed, encountered, consequently, furthermore, additionally, regardless, despite, however, nevertheless.

REPLACE PHRASES like these with simpler ones:
- "expressed sympathy" → "said sorry to the families"
- "extended condolences" → "said sorry"
- "undertook screening" → "checked"
- "needed further medical attention" → "were very ill"
- "in collaboration with the authorities" → "with help from the police" (or whoever it is)
- "the situation" → "what happened"
- "during the crisis" → "during this hard time" or just leave it out
- "officials" → "the government" or "people from the government"
- "the survivors were transported" → "the people were taken" or "buses took them"
- "was grateful to members for trusting him" → "said thank you to the members for choosing him"
- "promised to lead in a transparent way" → "said he will be open and honest in his work"
- "thanked all members regardless of how they voted" → "said thank you to everyone, also to people who voted for someone else"
- "outgoing chairperson" → "the old leader" or just the person's name
- "congratulated him" → "said well done" or "said good job"
- "called on the new leaders to strengthen the institution" → "asked the new leaders to make the group stronger"
- "protect media freedom" → "make sure journalists are free to do their work" or "help journalists"
- "improve the welfare of journalists" → "help journalists have a better life"

WORKED EXAMPLE — this exact kind of sentence appeared in real output and was too hard. Study it.
TOO HARD: "Washon said he was grateful to members for trusting him with the role. He promised to lead the institute in a transparent way and to build on the work of the previous leadership. He also thanked all members regardless of how they voted. Outgoing chairperson Matonga congratulated Washon and called on the new leaders to strengthen the institution, protect media freedom, and improve the welfare of journalists in Malawi."
A1 REWRITE: "Washon said thank you to the members. He said he is happy that they chose him. He said he will be open and honest in his work. He will build on what the old team did. He also said thank you to everyone, even people who voted for someone else. The old leader, Matonga, said well done to Washon. He asked the new leaders to make the group stronger. He said they must help journalists in Malawi do their work and live better."

Sentence length: keep most sentences to 6–10 words. Break long ones into two short ones. Active voice always. If a noun is abstract (welfare, support, sympathy, situation, crisis, condition, capacity, intervention, infrastructure), find a way to write the same fact using a verb instead.

The "body" field (short opener):
- 50–80 words in each language
- Cover the core facts: what happened, who, where, when, the immediate result
- This is what readers see first, before clicking "Read more"

The "body_more" field (the continuation):
- A direct continuation of "body" — never re-introduce the story, never re-state who or what was already named, never recap the headline
- TARGET: around 300 words in each language. Acceptable range: 220 to 380 words. Going below 220 should be rare and only when the source material is truly minimal (e.g. a one-sentence sports score with no further context).
- Before deciding the sources are too thin, EXTRACT every fact from them: every name, place, number, date, quote (paraphrased), action, reason, consequence, reaction. Sources usually contain more than they appear to on first read.
- Add NEW information not already in "body": background, context, secondary facts, who else is affected, what happens next, relevant numbers, paraphrased reactions
- MUST be split into THREE OR FOUR paragraphs separated by \\n\\n (a literal blank line in the JSON string). Never one giant block of text. Never more than four paragraphs — readability suffers. Each paragraph should focus on one aspect of the story (e.g. paragraph 1: more detail on what happened; paragraph 2: reactions or context; paragraph 3: what happens next).
- Start naturally — as if continuing the article. Good openings: "The arrest follows...", "Police say the...", "Earlier this week...", "Officials added that..."
- Bad openings (NEVER use these): "The Anti-Corruption Bureau is searching for [name who was already named in body]...", anything that re-states the headline, or "It is reported that [opening fact already in body]"

Strict factuality:
- Stick strictly to facts that appear in the source material. Do not invent details, names, numbers, quotes, or context.
- If sources disagree, say so neutrally or omit the disputed detail.
- Do NOT copy sentences verbatim from the sources. Always paraphrase.

Pick exactly one tag from this list: politics, economy, health, sport, society, international.

Output JSON shape:
{
  "tag": "<one of the allowed tags>",
  "en": { "title": "...", "body": "...", "body_more": "...\\n\\n..." },
  "ny": { "title": "...", "body": "...", "body_more": "...\\n\\n..." }
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
        "Produce the JSON object as specified. Remember: simple A1 English, "
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
            ["en", "title"], ["en", "body"], ["en", "body_more"],
            ["ny", "title"], ["ny", "body"], ["ny", "body_more"],
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
# Step 4: assemble JSON
# ---------------------------------------------------------------------------

def cluster_to_article(cluster: Cluster, rewritten: dict[str, Any]) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date().isoformat()
    slug_basis = rewritten["en"]["title"].lower()
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

    return {
        "id": f"{today}-{slug}",
        "tag": rewritten["tag"],
        "published": cluster.latest.isoformat(),
        "en": rewritten["en"],
        "ny": rewritten["ny"],
        "sources": sources,
    }


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


def write_output(articles: list[dict[str, Any]]) -> None:
    """
    Merge new articles into the existing archive.

    The pipeline produces the day's top stories every run, but we don't want
    each run to wipe out everything that came before — readers expect the
    Archive view to accumulate over time. So we:

    1. Load the existing articles.json (if any)
    2. Build a fresh list: today's new articles first, then existing articles
       that don't share an ID with a new one
    3. Sort by published time (newest first)
    4. Cap at MAX_ARCHIVE_ARTICLES so the JSON file stays a reasonable size

    Articles previously edited (ny_reviewed: true) are handled separately by
    merge_with_reviewed() and arrive here with their reviewed content intact.
    """
    existing = []
    if OUT_PATH.exists():
        try:
            data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
            existing = data.get("articles", [])
        except Exception as e:
            log.warning("Couldn't read existing archive, starting fresh: %s", e)

    new_ids = {a["id"] for a in articles}
    kept_from_archive = [a for a in existing if a.get("id") not in new_ids]

    combined = articles + kept_from_archive
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
        "Wrote archive: %d new, %d preserved from previous runs, %d total in archive",
        len(articles), len(kept_from_archive), len(combined),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY environment variable not set.")
        return 1

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
    previous_by_id = load_existing_articles()
    for c in top:
        log.info(
            "Rewriting cluster of %d articles from sources: %s",
            len(c.articles), ", ".join(c.sources),
        )
        rewritten = rewrite_cluster(client, c)
        if rewritten is None:
            log.warning("Skipping cluster due to rewrite failure.")
            continue
        article = cluster_to_article(c, rewritten)
        article = merge_with_reviewed(article, previous_by_id)
        final.append(article)

    if not final:
        log.error("No clusters successfully rewritten. Keeping previous output.")
        return 1

    write_output(final)
    return 0


if __name__ == "__main__":
    sys.exit(main())
