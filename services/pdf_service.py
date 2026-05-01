import os

import fitz
import requests

PDF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/octet-stream,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

DEFAULT_PDF_MAX_PAGES = 200
MIN_PAGE_TEXT_CHARS = 30


def extract_pdf_text(url):
    res = requests.get(url, headers=PDF_HEADERS, timeout=30)
    res.raise_for_status()

    content_type = res.headers.get("Content-Type", "").lower()
    if "pdf" not in content_type and not url.lower().endswith(".pdf"):
        raise ValueError(f"Attachment is not a PDF: {content_type or 'unknown content type'}")

    max_pages = int(os.getenv("PDF_MAX_PAGES", str(DEFAULT_PDF_MAX_PAGES)))
    doc = fitz.open(stream=res.content, filetype="pdf")

    try:
        total_pages = len(doc)
        pages_to_read = min(total_pages, max_pages)

        parts = []
        scanned_pages = 0

        for page_num in range(pages_to_read):
            page = doc[page_num]
            page_text = page.get_text()

            if len(page_text.strip()) < MIN_PAGE_TEXT_CHARS:
                scanned_pages += 1
                continue

            parts.append(f"[PAGE {page_num + 1}]\n{page_text.strip()}")

        text = "\n\n".join(parts)

        notes = []
        if total_pages > max_pages:
            notes.append(
                f"PDF has {total_pages} pages; only first {max_pages} pages extracted "
                f"(set PDF_MAX_PAGES to increase)"
            )
        if scanned_pages > 0:
            notes.append(
                f"{scanned_pages} of {pages_to_read} pages appear scanned/image-only and were skipped"
            )
        if notes:
            text = "[NOTE: " + "; ".join(notes) + "]\n\n" + text

    finally:
        doc.close()

    return text
