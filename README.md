# ezNews Malawi

Daily Malawi news, rewritten in simple English (CEFR A1) and Chichewa (CEFR A2). Lightweight, mobile-first, low-data. Fully automated.

Each story published here is reported by at least three mainstream Malawi news outlets. The original sources are credited and linked at the bottom of every article. Stories appear about half a day after the original reporting because the pipeline runs once per day.

---

## What's in this repo

```
eznews-malawi/
├── site/                      The static website. Deploy this folder.
│   ├── index.html
│   ├── style.css              ~3 KB
│   ├── app.js                 ~4 KB, vanilla JS
│   └── data/articles.json     Updated daily by the pipeline
├── pipeline/
│   ├── run.py                 The full daily pipeline in one file
│   └── verify_sources.py      Run once to check feeds work
├── .github/workflows/
│   └── daily.yml              Runs the pipeline every day at 06:00 CAT
├── requirements.txt
├── .env.example
├── EDITOR_GUIDE.md            Hand this to the Chichewa reviewer
└── README.md
```

The site loads in well under 50 KB on first visit, and subsequent visits are even smaller (cached). It works on 2G/3G connections and renders correctly without JavaScript for the basic layout — though search and language switching require JS.

---

## How it works

1. **Fetch.** Twice a day at 06:00 and 18:00 Central Africa Time (CAT), GitHub Actions starts the pipeline. The pipeline reads RSS feeds from the Malawi news outlets listed in `pipeline/run.py`. Articles older than 36 hours are discarded.
2. **Cluster.** Articles are grouped using TF-IDF similarity on title + summary text. Stories that appear in fewer than three sources are dropped.
3. **Pick top 5.** Clusters are ranked by source count, then by recency.
4. **Rewrite with Claude.** For each of the top five stories, the pipeline sends the source titles and summaries to Claude with strict instructions: simple English at A1, natural Chichewa at A2, neutral tone, no invented facts, no copying of source sentences.
5. **Save.** The output is written to `site/data/articles.json` and committed back to the repo.
6. **Deploy.** Cloudflare Pages (or whichever host you choose) detects the commit and rebuilds the site automatically.

If at any step the pipeline cannot find five qualifying stories, or the LLM rewrite fails, the previous day's `articles.json` is kept untouched. The site never goes blank.

---

## Cost estimate

- **AI calls:** 5 stories × 2 runs per day × ~2,500 input tokens + ~600 output tokens, on Claude Haiku. Roughly USD $1–3 per month.
- **Hosting:** Cloudflare Pages free tier is more than enough.
- **GitHub Actions:** Free for public repositories.
- **Domain:** ~$10–15 per year. Optional but recommended.

Total: roughly **$1–3/month** plus the domain.

---

## Step-by-step deployment

### 1. Get an Anthropic API key

Go to <https://console.anthropic.com/>, create an account, add a small amount of credit (USD $5 is plenty to start), and create an API key. Copy it. You won't be able to see it again.

### 2. Put this code on GitHub

Create a new GitHub repository (it can be public — there are no secrets in the code itself). Then on your computer:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/eznews-malawi.git
git push -u origin main
```

### 3. Add your API key as a GitHub secret

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**.

- Name: `ANTHROPIC_API_KEY`
- Value: paste the key from step 1.

### 4. Verify the news sources

Before letting the pipeline run, check which RSS feeds actually work today:

```bash
pip install -r requirements.txt
python pipeline/verify_sources.py
```

You'll get a coloured report — green tick for working feeds, red cross for broken ones, with a sample headline from each working feed so you can confirm it's the right outlet. Any source with no working feed is highlighted at the bottom with suggestions for fixing it. Edit `SOURCES` in `pipeline/run.py` until the verifier is happy.

This script doesn't call Claude, so no API key is needed. Run it again any time the pipeline starts producing fewer articles than expected — RSS URLs do break occasionally.

### 5. Test the pipeline manually before waiting for the cron

In your GitHub repo: **Actions → Daily news refresh → Run workflow**. It should run, fetch articles, call Claude, and commit a new `articles.json`. Watch the logs.

If it fails because some RSS feeds are wrong (the verifier in step 4 should catch most of these, but some sites block requests from cloud IPs that worked from your laptop), open `pipeline/run.py`, edit the `SOURCES` list, and push the fix.

### 6. Deploy the website

The simplest free option is Cloudflare Pages.

1. Sign up at <https://pages.cloudflare.com>.
2. Click **Create a project → Connect to Git**, authorise GitHub, pick your repo.
3. Build settings:
   - **Framework preset:** None
   - **Build command:** *(leave empty)*
   - **Build output directory:** `site`
4. Click **Save and Deploy**. Within a minute you'll have a `*.pages.dev` URL.

Every time the daily cron commits a new `articles.json`, Cloudflare will rebuild the site automatically.

### 7. Add a custom domain (optional)

Buy a domain — Namecheap, Porkbun, Cloudflare Registrar all work. Then in Cloudflare Pages: **Custom domains → Set up a custom domain**. Cloudflare will give you DNS records to add. SSL is automatic and free.

---

## Running the pipeline locally (for testing)

```bash
python -m venv venv
source venv/bin/activate          # on Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and paste your real ANTHROPIC_API_KEY

set -a; source .env; set +a       # load env vars (Linux/Mac)
python pipeline/run.py
```

Then preview the site:

```bash
cd site
python -m http.server 8000
# Open http://localhost:8000
```

---

## Things you should change before going live

1. **Read each source's terms of service.** Republishing scraped content wholesale is generally not allowed. This pipeline does **not** republish — it reads multiple sources, then writes its own short summary. That's a much safer pattern, but you should still confirm each outlet is comfortable with this. Reaching out to editors for a courtesy email is wise.
2. **Get a Chichewa speaker to review output twice a day.** AI Chichewa quality is decent at the A2 level but not perfect. The site supports human-corrected articles via a simple GitHub-based workflow — see `EDITOR_GUIDE.md` for the page you'd hand to the reviewer. When they mark an article as reviewed, future pipeline runs preserve their correction instead of overwriting it.
3. **Update the bot's contact email.** In `pipeline/run.py`, change the `USER_AGENT` string from `you@example.com` to a real address. Some sites block requests without a contact.
4. **Add an "About" / "Editorial standards" / "Contact" page.** Readers will trust the site more if there's a clear human accountability story, even if the writing is automated.

---

## How the editor workflow works

When the AI generates an article, the JSON looks like this (simplified):
```json
{
  "id": "2026-05-09-cholera-down",
  "ny": { "title": "...", "body": "...", "body_more": "..." }
}
```

After the editor reviews and corrects the Chichewa, they add one flag:
```json
{
  "id": "2026-05-09-cholera-down",
  "ny_reviewed": true,
  "ny": { "title": "...", "body": "...", "body_more": "..." }
}
```

On the next pipeline run, `merge_with_reviewed()` in `pipeline/run.py` checks each article: if a previous version had `ny_reviewed: true`, the editor's Chichewa text is preserved and only English/sources/timestamps are updated from the new AI output. The editor's work survives.

The website displays a small green "✓ Chichewa checked by editor" badge on reviewed articles when viewed in Chichewa, so readers can see which content a human has signed off on.

If you want to *re-check* an article (e.g. after revising your prompts), simply remove the `ny_reviewed` flag and the next pipeline run will treat it as fresh.

---

## Tuning the pipeline

Open `pipeline/run.py` and look near the top:

| Variable | Meaning | Default |
|---|---|---|
| `MAX_AGE_HOURS` | Ignore articles older than this | 36 |
| `MIN_SOURCES` | Required source overlap | 3 |
| `TARGET_STORIES` | How many stories to publish per day | 5 |
| `SIMILARITY_THRESHOLD` | Tighter clustering = higher value | 0.30 |

If you find clusters are too aggressive (unrelated stories getting merged), raise `SIMILARITY_THRESHOLD` to 0.4 or 0.5. If you're rarely getting five qualifying clusters, lower `MIN_SOURCES` to 2 or loosen the threshold.

The system prompt for Claude lives in `REWRITE_SYSTEM_PROMPT`. Tweak it whenever you spot patterns in the output you want to fix — e.g. if Chichewa keeps using overly formal vocabulary, add a sentence about that.

---

## Failure modes to be aware of

- **An outlet changes its RSS structure.** Watch the GitHub Actions logs weekly for warnings.
- **An outlet blocks the bot.** Identify yourself politely in the User-Agent and consider reaching out for explicit permission.
- **The AI hallucinates a fact.** This is rare with three sources of grounding, but possible. Spot-check daily output against the linked sources, especially for numbers and proper nouns. Consider adding a final verification step that asks Claude to re-read its own output and flag any claim not directly supported by the input.
- **Chichewa quality drift.** Have a reviewer read the Chichewa weekly. If quality degrades, refine the system prompt with concrete examples of what's wrong and what's right.

---

## License and credits

Code: MIT. Use it, modify it, deploy it.

This is a tool for amplifying public-interest news in Malawi. It depends entirely on the work of the journalists at the source outlets — please always link to them and treat them as partners, not as a feed to scrape.
