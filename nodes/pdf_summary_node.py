import hashlib
import json
import os
import re
from pathlib import Path

from services.llm_service import call_llm
from utils.logger import log


CACHE_FILE = Path("data/pdf_summaries.json")
DEFAULT_CHUNK_CHARS = 12000
DEFAULT_MAX_SUMMARY_CHARS = 5000
DEFAULT_SUMMARY_BATCH_SIZE = 6
DEFAULT_SUMMARY_THRESHOLD_CHARS = 18000


def load_cache():
    if not CACHE_FILE.exists() or CACHE_FILE.stat().st_size == 0:
        return {}

    try:
        with CACHE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def chunk_text(text, chunk_chars):
    return [text[i : i + chunk_chars] for i in range(0, len(text), chunk_chars)]


def find_page_range(chunk):
    page_nums = [int(m) for m in re.findall(r"\[PAGE (\d+)\]", chunk)]
    if not page_nums:
        return ""
    if min(page_nums) == max(page_nums):
        return f" (page {min(page_nums)})"
    return f" (pages {min(page_nums)}-{max(page_nums)})"


def compact(text, max_chars):
    clean = " ".join(str(text or "").split())
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rstrip() + "..."


def build_chunk_prompt(record, chunk, chunk_number, total_chunks):
    page_range = find_page_range(chunk)
    return f"""
You are summarizing a large NSE disclosure PDF for a stock trading signal system.

Read this PDF chunk carefully and extract only market-relevant facts.

NSE EVENT:
SYMBOL: {record.get("SYMBOL", "")}
COMPANY NAME: {record.get("COMPANY NAME", "")}
SUBJECT: {record.get("SUBJECT", "")}
DETAILS: {record.get("DETAILS", "")}
BROADCAST DATE/TIME: {record.get("BROADCAST DATE/TIME", "")}

PDF CHUNK {chunk_number} OF {total_chunks}{page_range}:
{chunk}

Return a concise summary with:
- material event facts
- financial/order/contract/legal/management details
- dates, values, quantities, parties, approvals, risks
- whether this chunk supports BUY, SELL, or NEUTRAL and why
- any page-local caveats such as missing tables, annexures, or scanned text
""".strip()


def build_final_summary_prompt(record, chunk_summaries):
    return f"""
You are preparing a compact PDF summary for Groq to generate a final trading signal.

NSE EVENT:
SYMBOL: {record.get("SYMBOL", "")}
COMPANY NAME: {record.get("COMPANY NAME", "")}
SUBJECT: {record.get("SUBJECT", "")}
DETAILS: {record.get("DETAILS", "")}
BROADCAST DATE/TIME: {record.get("BROADCAST DATE/TIME", "")}

CHUNK SUMMARIES:
{chunk_summaries}

Create one structured summary for the final signal model.
Include:
- event type and materiality
- exact PDF facts that matter
- positive catalysts
- negative risks
- whether the disclosure looks routine or price-sensitive
- likely short-term market implication

Keep it compact but complete.
""".strip()


def reduce_summaries(record, summaries, timeout, num_ctx):
    batch_size = int(os.getenv("PDF_SUMMARY_BATCH_SIZE", str(DEFAULT_SUMMARY_BATCH_SIZE)))
    num_predict = int(os.getenv("PDF_SUMMARY_FINAL_NUM_PREDICT", "700"))
    current = summaries
    round_number = 1

    while len(current) > batch_size:
        reduced = []
        for index in range(0, len(current), batch_size):
            batch = "\n\n".join(current[index : index + batch_size])
            reduced.append(
                call_llm(
                    build_final_summary_prompt(record, batch),
                    timeout=timeout,
                    options={
                        "temperature": 0.1,
                        "num_predict": num_predict,
                    },
                )
            )
        current = reduced
        log("PDF_SUMMARY", f"Reduction round {round_number}: {len(current)} summaries")
        round_number += 1

    return current


def summarize_pdf(record, pdf_text):
    chunk_chars = int(os.getenv("PDF_SUMMARY_CHUNK_CHARS", str(DEFAULT_CHUNK_CHARS)))
    max_summary_chars = int(os.getenv("PDF_SUMMARY_MAX_CHARS", str(DEFAULT_MAX_SUMMARY_CHARS)))
    timeout = int(os.getenv("PDF_SUMMARY_TIMEOUT_SECONDS", "180"))
    num_predict = int(os.getenv("PDF_SUMMARY_NUM_PREDICT", "384"))

    chunks = chunk_text(pdf_text, chunk_chars)
    chunk_summaries = []

    for index, chunk in enumerate(chunks, start=1):
        summary = call_llm(
            build_chunk_prompt(record, chunk, index, len(chunks)),
            timeout=timeout,
            options={
                "temperature": 0.1,
                "num_predict": num_predict,
            },
        )
        chunk_summaries.append(summary)
        log("PDF_SUMMARY", f"Chunk {index}/{len(chunks)} summarized")

    reduced_summaries = reduce_summaries(record, chunk_summaries, timeout, None)
    combined = "\n\n".join(reduced_summaries)
    if len(combined) <= max_summary_chars:
        return compact(combined, max_summary_chars)

    final_summary = call_llm(
        build_final_summary_prompt(record, combined),
        timeout=timeout,
        options={
            "temperature": 0.1,
            "num_predict": int(os.getenv("PDF_SUMMARY_FINAL_NUM_PREDICT", "700")),
        },
    )
    return compact(final_summary, max_summary_chars)


def pdf_summary_node(state):
    pdf_text = state.get("pdf_text", "")
    if not pdf_text:
        state["pdf_summary"] = ""
        return state

    threshold_chars = int(os.getenv("PDF_SUMMARY_THRESHOLD_CHARS", str(DEFAULT_SUMMARY_THRESHOLD_CHARS)))
    if len(pdf_text) <= threshold_chars:
        state["pdf_summary"] = ""
        log("PDF_SUMMARY", f"Skipped for short PDF {len(pdf_text)} chars")
        return state

    record = state["records"][0]
    cache_key = text_hash(pdf_text)
    cache = load_cache()

    if cache_key in cache:
        state["pdf_summary"] = cache[cache_key]
        log("PDF_SUMMARY", f"Loaded cached summary {len(state['pdf_summary'])} chars")
        return state

    try:
        state["pdf_summary"] = summarize_pdf(record, pdf_text)
        cache[cache_key] = state["pdf_summary"]
        save_cache(cache)
        log("PDF_SUMMARY", f"{len(state['pdf_summary'])} chars")
    except Exception as e:
        state["pdf_summary"] = ""
        state["error_stage"] = state.get("error_stage") or "PDF_SUMMARY"
        state["error_reason"] = state.get("error_reason") or str(e)
        log("PDF_SUMMARY", f"Failed: {e}")

    return state
