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


def extract_pdf_text(url):
    res = requests.get(url, headers=PDF_HEADERS, timeout=30)
    res.raise_for_status()

    content_type = res.headers.get("Content-Type", "").lower()
    if "pdf" not in content_type and not url.lower().endswith(".pdf"):
        raise ValueError(f"Attachment is not a PDF: {content_type or 'unknown content type'}")

    doc = fitz.open(stream=res.content, filetype="pdf")

    try:
        text = ""
        for page in doc:
            text += page.get_text()
    finally:
        doc.close()

    return text[:3000]
