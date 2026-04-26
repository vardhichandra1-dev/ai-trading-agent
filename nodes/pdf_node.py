from services.pdf_service import extract_pdf_text
from utils.logger import log
from utils.retry import retry

def pdf_node(state):
    try:
        url = state["records"][0].get("ATTACHMENT")

        if not url:
            state["pdf_text"] = ""
            return state

        text = retry(lambda: extract_pdf_text(url))

        log("PDF", f"{len(text)} chars")

        state["pdf_text"] = text
        return state

    except Exception as e:
        state["pdf_text"] = ""
        state["error_stage"] = "PDF"
        state["error_reason"] = str(e)
        return state