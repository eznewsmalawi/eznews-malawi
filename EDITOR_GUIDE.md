# ezNews Malawi — Editor Guide for Chichewa Review

A short guide for the Chichewa editor. **You only need to read this once.** After that, fixing a Chichewa error takes about 60 seconds and a single browser tab.

---

## What you're doing

The website ezNews-Malawi rewrites the day's biggest news stories in simple English and Chichewa. The Chichewa is written by an AI and is usually good but sometimes makes mistakes. Your job is to read it twice a day and correct anything that sounds wrong, sounds unnatural, or isn't proper Chichewa.

You will **not** need to know any computer programming. You will not write code. You will just edit text in a web form, the way you would edit a Word document.

---

## When to review

The website refreshes twice a day:

| Refresh time | Your review window |
|---|---|
| 06:00 CAT | 06:00 – 07:00 |
| 18:00 CAT | 18:00 – 19:00 |

If a refresh produces no changes (because no new stories appeared), you'll see the same articles you reviewed last time. In that case, you have nothing new to do — your previous corrections are preserved.

---

## What to do, step by step

### Step 1: Open the file

Bookmark this link, you'll use it twice a day:

```
https://github.com/YOUR_USERNAME/eznews-malawi/blob/main/site/data/articles.json
```

(The actual URL will be given to you. Click the bookmark — you'll see a long list of text. Don't be intimidated; you only edit small bits of it.)

### Step 2: Click the pencil icon

In the top right of the file, there's a small pencil icon. Click it. The file becomes editable, like a long text box.

If GitHub asks you to log in, do so with your GitHub account.

### Step 3: Find the Chichewa text

The file is structured like a list of articles. For each article, there are two languages: English (under `"en"`) and Chichewa (under `"ny"`). You only edit what's inside `"ny"`.

A typical article looks like this:

```
{
  "id": "2026-05-09-cholera-down",
  "tag": "health",
  "published": "2026-05-09T06:00:00+02:00",
  "en": {
    "title": "Cholera cases drop in Lilongwe",
    "body": "Health workers say cholera cases are going down...",
    "body_more": "Doctors ask people to wash their hands often..."
  },
  "ny": {
    "title": "Matenda a kolera akuchepa ku Lilongwe",
    "body": "Antchito a zaumoyo akuti matenda a kolera akuchepa ku Lilongwe...",
    "body_more": "Madotolo akupempha anthu kuti aziphimba m'manja kawirikawiri..."
  }
}
```

You only change the text **inside the quotes** of the three Chichewa fields:
- `"title"` — the headline
- `"body"` — the short summary
- `"body_more"` — the longer extended part

### Step 4: Make your correction

Click inside the quotes and edit the text. For example, if you see:

```
"title": "Matenda a kolera akuchepa ku Lilongwe",
```

and you want to change it to:

```
"title": "Matenda a kolera achepa ku Lilongwe",
```

just click between the quotes and edit normally.

### Step 5 (IMPORTANT): Mark the article as reviewed

After you fix an article, you must add one new line just below `"published"`:

```
"ny_reviewed": true,
```

So the article becomes:

```
{
  "id": "2026-05-09-cholera-down",
  "tag": "health",
  "published": "2026-05-09T06:00:00+02:00",
  "ny_reviewed": true,
  "en": { ... },
  "ny": { ... }
}
```

**Why this matters:** without this flag, the next time the AI refreshes the site, it would replace your correction with new (uncorrected) AI output. The flag tells the system to keep your work.

If the article already has `"ny_reviewed": true,` (because you reviewed it last time), leave it as is.

### Step 6: Save

Scroll to the bottom of the page. You'll see a green button that says **Commit changes**. Click it.

A small box appears. In the description field, write something short like *"Fixed Chichewa typo in cholera headline"*. Then click the green **Commit changes** button again.

That's it. Within 1–2 minutes the website will update with your correction.

---

## Three things to watch out for

**1. Commas matter.** JSON files use commas to separate items. After most lines except the last in a block, there's a comma. If you accidentally remove one or add an extra one, GitHub will warn you with a red mark in the left margin. If you see one, look at the line it points to and check the commas. When in doubt, ask for help — don't save broken syntax.

**2. Don't change the structure.** Don't change `"en":` to `"english":`. Don't add new fields the system doesn't know about. Don't delete fields. You're only editing the Chichewa text inside the existing quotes, plus adding the `"ny_reviewed": true` line.

**3. Don't change the English.** That's not your job, and changing it could confuse readers comparing the two languages.

---

## What to fix vs. what to leave alone

**Fix these:**
- Wrong noun-class agreement
- Misspelled words
- Unnatural word order
- Words that aren't actually Chichewa
- Sentences that don't make sense
- Translation that misses the meaning of the English version

**Leave these alone, even if you'd word things differently:**
- Style preferences (the AI has a consistent simple style — let it stay consistent)
- Vocabulary choices that are correct but you'd use a different word
- Sentence length (the goal is short and clear at A2 level)
- Anything in English

If you're not sure whether to fix something, lean toward leaving it. Real errors are usually obvious; stylistic disagreements aren't worth it for a reader-facing website.

---

## What if I make a mistake?

Don't worry. GitHub keeps a history of every change. If something goes wrong, the project owner can revert your edit with one click. You can't break anything permanently.

If your save shows a red error message about "invalid JSON", it means a comma or quote mark got out of place. The error will say which line. If you can't fix it within a minute, click "Cancel" to discard your changes and try again — better to leave the AI's version up than save broken text.

---

## Showing readers that you reviewed

When you add the `"ny_reviewed": true,` flag, a small green badge appears on that article when readers view it in Chichewa:

> ✓ Chichewa chayang'aniridwa ndi mkonzi

This builds reader trust — they can see which articles a real Chichewa speaker has checked. It's not just for show; it's a real signal of quality.

---

## Quick reference card

Print this or pin it somewhere:

1. Open the bookmark
2. Click pencil icon
3. Find the article, look inside `"ny": { ... }`
4. Fix the text inside the quotes
5. Add `"ny_reviewed": true,` below `"published":`
6. Scroll down, click "Commit changes" twice
7. Done. The site updates in a minute or two.

---

## Help

If something doesn't work or you're not sure what to do, ask the project owner. Don't just save — leaving uncorrected text up is much better than saving a broken file.
