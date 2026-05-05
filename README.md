# AI-Driven Indian Stock Market Agent

Two parallel data-ingestion pipelines run simultaneously inside a single LangGraph, both delivering to the same Telegram channel.

| Pipeline | Data source | Telegram output |
|----------|-------------|-----------------|
| **NSE Announcements** | NSE corporate announcements API + PDF attachments | BUY / SELL / NEUTRAL trading signal with full reasoning |
| **Twitter / X News** | CNBCTV18Live · NDTVProfitIndia · ETNOWlive · REDBOXINDIA | Plain-English news digests — new tweets only, no duplicates |

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Copy and fill in credentials
cp .env.example .env   # or create .env manually (see Environment section)

# Run both pipelines together (recommended)
python run.py

# Single cycle and exit
python run.py --once
```

> Standalone pipeline entry points also work independently:
> ```bash
> python main.py            # NSE pipeline only
> python twitter_main.py    # Twitter pipeline only
> ```

---

## Combined Graph Architecture

```mermaid
flowchart TD
    A([run.py — start cycle]) --> B[refresh\nFetch latest NSE announcements\nUpdate nse_master.json]

    B --> C[nse\nNSE announcements pipeline]
    B --> D[twitter\nTwitter summarisation pipeline]

    C -->|BUY / SELL / NEUTRAL signal| E[(ai_research_output.json)]
    C -->|If notify=true| F([Telegram — NSE Alert])

    D -->|New summaries digest| G[(twitter_output.json)]
    D -->|Up to 4 digest messages| H([Telegram — News Digest])

    E --> I([combined_runs.json])
    G --> I

    I --> J{NSE found a record?}
    J -- Yes --> A
    J -- No --> K[Sleep 2–5 min]
    K --> A
```

Both `nse` and `twitter` nodes execute **in parallel** — LangGraph threads them simultaneously after `refresh` completes. Each pipeline sends to Telegram independently; neither waits for the other.

---

## Pipeline 1 — NSE Announcements Agent

Processes one NSE corporate announcement per cycle, downloads its PDF disclosure, generates a Groq-backed trading signal, optionally validates with Tavily web search, and sends a Telegram alert for fresh actionable signals.

### LangGraph

```mermaid
flowchart TD
    A([Start]) --> B[pdf_node\nDownload PDF attachment]
    B --> C[pdf_summary_node\nExtract text page-by-page]

    C --> D{PDF size}
    D -- "≤ threshold" --> E[Pass through\nkeyword-aware context selection]
    D -- "> threshold" --> F[Chunk PDF with page labels\nCall Groq per chunk\nBatch-reduce → cache]

    E --> G[signal_node\nBUY / SELL / NEUTRAL via Groq]
    F --> G

    G --> H{Signal}
    H -- NEUTRAL --> I[report_node]
    H -- "BUY / SELL" --> J[validation_node\nGenerate queries via Groq\nTavily web search 3–5 queries]

    J --> K{Search results?}
    K -- None --> L[notify = false]
    K -- Found --> M[Validation LLM\nconfirm freshness]

    M --> N{Fresh news?}
    N -- "Already reflected" --> O[Downgrade / notify = false]
    N -- "Fresh signal" --> P[notify = true]

    L --> I
    O --> I
    P --> I

    I --> Q[telegram_node\nSend if notify = true]
    Q --> R[(ai_research_output.json)]
```

### Signal decision logic

- **BUY / SELL** — proceeds to Tavily validation. If no search results are found, or the LLM determines the event was already public (`already_reflected = true`), `notify` is set to `false` and no Telegram alert is sent.
- **NEUTRAL** — skips Tavily entirely; no Telegram alert.
- Telegram is only triggered when: signal is BUY or SELL **and** `notify = true`.

### Groq model fallback

Every `call_llm` call attempts models in order — if the primary returns an HTTP error or empty response the next is tried automatically:

```
GROQ_MODEL  →  GROQ_BACKUP_MODEL_1  →  GROQ_BACKUP_MODEL_2  →  raise RuntimeError
```

### Large PDF handling

| PDF size | Behaviour |
|----------|-----------|
| ≤ `PDF_SUMMARY_THRESHOLD_CHARS` | Passed directly to the signal prompt via keyword-aware compact context (head + tail + event-relevant snippets) |
| > `PDF_SUMMARY_THRESHOLD_CHARS` | Split into `PDF_SUMMARY_CHUNK_CHARS` chunks, each labelled `[PAGE N]`. Each chunk summarised by Groq independently. Chunk summaries batch-reduced until ≤ `PDF_SUMMARY_MAX_CHARS`. Result SHA-256 cached in `data/pdf_summaries.json`. |

Scanned / image pages (< 30 characters) are detected and skipped. `PDF_MAX_PAGES` caps extraction on very large documents.

---

## Pipeline 2 — Twitter News Summarisation Agent

Scrapes tweets from four high-credibility Indian financial accounts using Playwright, filters noise, deduplicates within each run, tags detected NSE stocks, summarises each update via Groq, and sends only **new** (previously unsent) tweet summaries to Telegram.

**No trading signals are generated from Twitter data.**

### LangGraph

```mermaid
flowchart LR
    A([Start]) --> B[tweet_collector_node\nPlaywright → Nitter instances\n4 accounts × 20 tweets]
    B --> C[noise_filter_node\nStrip URLs · emojis · whitespace\nReject ads / politics / sports\nKeep financial signal keywords]
    C --> D[dedup_node\nTF-IDF cosine similarity\nthreshold 0.85\nfirst-seen order wins]
    D --> E[stock_detector_node\nReload NSE master each run\nTag each tweet with detected NSE symbols]
    E --> F[tweet_summarizer_node\nBatch 10 tweets per Groq call\nOne sentence per tweet]
    F --> G[twitter_telegram_node\nFilter already-seen IDs\nSort chronologically oldest→newest\n5 summaries per message · max 4 messages\nUpdate seen_tweet_ids.json\nSave to twitter_output.json]
    G --> H([Telegram])
```

### Scraping strategy

Tweets are fetched via **Playwright + Nitter** (no X account or API key required):

1. Playwright launches a headless Chromium browser
2. Navigates to each Nitter instance (tried in order until one responds)
3. Parses `.timeline-item` elements for tweet text and timestamp
4. Falls back to `x.com` directly only if all Nitter instances fail

Nitter instances tried (in order):

```
nitter.tiekoetter.com → nitter.poast.org → nitter.1d4.us →
nitter.kavin.rocks → nitter.cz → nitter.it → x.com (last resort)
```

### Deduplication — two layers

| Layer | Scope | Method |
|-------|-------|--------|
| Within-run | Same pipeline cycle | TF-IDF cosine similarity ≥ 0.85; first-seen order wins (no account weighting) |
| Cross-run | Across all previous runs | Content-stable `tweet_id` (MD5 of normalised text + author) checked against `data/seen_tweet_ids.json` |

`tweet_id` is derived from normalised tweet content — not timestamps — so it stays stable even if Playwright renders the page slightly differently each run. IDs are recorded only after a Telegram message sends successfully.

### Target accounts

| Account | Filter rule |
|---------|-------------|
| CNBCTV18Live | Stock-market keyword filter |
| ETNOWlive | Stock-market keyword filter |
| NDTVProfitIndia | Stock-market keyword filter |
| REDBOXINDIA | **No filter — every tweet reaches Telegram** |

### Telegram digest format

Messages are sent in chronological order (oldest tweet first) so the digest reads like a timeline.

```
📊 Market Flash  ·  04 May 2026  ·  11:13 UTC

@REDBOXINDIA
POWER TARIFFS LIKELY TO RISE AS REGULATORS ACT ON SC ORDER - FE

@CNBCTV18Live
Marico Q4: Revenue ₹3,325 Cr, EBITDA ₹527 Cr, margin 15.8% vs poll
🏷 MARICO

@ETNOWlive
L&T wins ₹2,500–5,000 Cr order from NTPC
🏷 LT  ·  COALINDIA

─────────────────────────
🔄 3 new updates  ·  `a3f8b1c2`
```

REDBOXINDIA updates are included as-is (raw headline if the LLM summary is unavailable). All other accounts show the LLM-generated one-sentence summary.

---

## Data Files

All outputs are written to `data/` and kept newest-first. Each file is capped to prevent unbounded growth.

### `data/nse_master.json`
Raw NSE corporate announcements fetched from the NSE API. Refreshed at the start of every combined cycle.

### `data/seen_ids.json`
Set of NSE announcement IDs already ingested — prevents re-processing the same disclosure.

### `data/pdf_summaries.json`
SHA-256 keyed cache of large-PDF chunk summaries. Re-processing the same PDF file skips Groq calls entirely.

### `data/ai_research_output.json`
Full LangGraph result for every processed NSE announcement. Newest entry first.

### `data/twitter_output.json`
One entry per Twitter pipeline run. Newest first, capped at 500 runs.
```json
[
  {
    "run_id": "a3f8b1c2",
    "timestamp": "2026-05-04T11:13:19+00:00",
    "pipeline_stats": {
      "raw_tweets": 76,
      "filtered_tweets": 61,
      "deduplicated_tweets": 61,
      "new_tweets": 12,
      "summaries": 61,
      "alerts_sent": 3
    },
    "tweets": [
      {
        "tweet_id": "3f8b1c2a4d6e",
        "author": "CNBCTV18News",
        "raw_text": "L&T wins ₹2,500–5,000 Cr order...",
        "clean_text": "L&T wins 2500 5000 Cr order...",
        "summary": "Larsen & Toubro wins ₹2,500–5,000 Cr infra order from NTPC.",
        "created_at": "2026-05-04T09:10:00+00:00",
        "stock_tags": ["LT", "BHARATCOAL"],
        "source": "playwright+nitter:nitter.tiekoetter.com"
      }
    ],
    "fetch_debug": [
      {
        "account": "CNBCTV18News",
        "status": "SUCCESS",
        "tweets_fetched": 20,
        "error": "",
        "source": "playwright+nitter"
      }
    ],
    "telegram_errors": []
  }
]
```

### `data/seen_tweet_ids.json`
Flat list of tweet IDs (MD5 hashes) already sent to Telegram. Capped at 5,000 entries. Prevents the same tweet being re-sent across multiple runs.

### `data/combined_runs.json`
One entry per combined `run.py` cycle. Newest first, capped at 500 runs.

---

## Environment Variables

Create `.env` in the project root:

```env
# ── Groq LLM (both pipelines) ────────────────────────────────────────────────
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
GROQ_BACKUP_MODEL_1=llama-3.3-70b-versatile
GROQ_BACKUP_MODEL_2=llama3-70b-8192
GROQ_TIMEOUT_SECONDS=90
GROQ_QUERY_TIMEOUT_SECONDS=90
GROQ_VALIDATION_TIMEOUT_SECONDS=120

# ── Telegram (both pipelines) ─────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ── NSE pipeline ──────────────────────────────────────────────────────────────
TAVILY_API_KEY=

PDF_MAX_PAGES=200
SIGNAL_PDF_MAX_CHARS=18000
PDF_SUMMARY_THRESHOLD_CHARS=18000
PDF_SUMMARY_CHUNK_CHARS=12000
PDF_SUMMARY_MAX_CHARS=5000
PDF_SUMMARY_TIMEOUT_SECONDS=180
PDF_SUMMARY_NUM_PREDICT=384
PDF_SUMMARY_FINAL_NUM_PREDICT=700
PDF_SUMMARY_BATCH_SIZE=6

# ── Twitter pipeline ──────────────────────────────────────────────────────────
# Number of tweets to fetch per account per run (default 20)
TWEETS_PER_ACCOUNT=20
```

> No Twitter/X account or API key is required. Playwright scrapes via public Nitter instances.

---

## Project Structure

```
ai_research_agent/
│
│  ── Entry points ──────────────────────────────────────────────────────
├── run.py                           # ★ PRIMARY — both pipelines in parallel
├── main.py                          # NSE pipeline standalone
├── twitter_main.py                  # Twitter pipeline standalone
│
│  ── Combined graph ────────────────────────────────────────────────────
├── combined_graph.py                # refresh → [nse ‖ twitter] → END
├── combined_state.py                # CombinedState TypedDict
│
│  ── NSE pipeline ───────────────────────────────────────────────────────
├── graph.py                         # NSE LangGraph (6 nodes)
├── state.py                         # GraphState TypedDict
├── nse_fetcher.py                   # NSE API fetcher + nse_master.json writer
│
│  ── Twitter pipeline ──────────────────────────────────────────────────
├── twitter_graph.py                 # Twitter LangGraph (6 nodes)
├── twitter_state.py                 # TwitterState TypedDict
│
├── nodes/
│   │  NSE nodes
│   ├── pdf_node.py                  # Download PDF attachment
│   ├── pdf_summary_node.py          # Chunk-summarise large PDFs; cache results
│   ├── signal_node.py               # Generate BUY / SELL / NEUTRAL via Groq
│   ├── validation_node.py           # Validate signal with Tavily web search
│   ├── report_node.py               # Format final report string
│   ├── telegram_node.py             # Send Telegram alert when notify=true
│   │
│   │  Twitter nodes
│   ├── tweet_collector_node.py      # Fetch tweets via Playwright+Nitter
│   ├── noise_filter_node.py         # Clean text; keep only financial keywords
│   ├── dedup_node.py                # TF-IDF cosine deduplication (within-run)
│   ├── stock_detector_node.py       # Reload NSE master; tag tweets with NSE symbols
│   ├── tweet_summarizer_node.py     # Batch Groq summarisation (10 tweets/call)
│   └── twitter_telegram_node.py     # Filter seen IDs; sort chronologically; send digests; write output
│
├── services/
│   ├── llm_service.py               # Groq API — primary + 2 backup models
│   ├── telegram_service.py          # Telegram Bot API
│   ├── pdf_service.py               # PDF download + page-by-page extraction
│   ├── tavily_service.py            # Tavily web search
│   ├── twitter_scraper_service.py   # Playwright+Nitter scraper (no login needed)
│   ├── stock_detector_service.py    # NSE symbol lookup + 50+ company aliases
│   └── dedup_service.py             # Pure-Python TF-IDF cosine similarity
│
├── utils/
│   ├── logger.py                    # log(stage, message) helper
│   └── retry.py                     # Retry decorator
│
└── data/                            # All outputs — never committed to git
    ├── nse_master.json              # NSE announcements cache (auto-refreshed)
    ├── seen_ids.json                # Processed NSE record IDs
    ├── pdf_summaries.json           # SHA-256 keyed PDF summary cache
    ├── ai_research_output.json      # NSE signal results (full state per stock)
    ├── twitter_output.json          # Twitter run log with full tweet records
    ├── seen_tweet_ids.json          # Tweet IDs already sent to Telegram
    └── combined_runs.json           # Combined cycle log (capped 500)
```

---

## Dependencies

```
langchain
langgraph
requests
python-dotenv
pymupdf
pandas
beautifulsoup4
playwright
```

Install:
```bash
pip install -r requirements.txt
playwright install chromium
```
