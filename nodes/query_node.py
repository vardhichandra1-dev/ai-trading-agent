import json
import re

from services.ollama_service import call_query_model
from utils.logger import log


def fallback_queries(company, subject, details):
    return [
        f"{company} {subject} news",
        f"{company} {subject} stock impact",
        f"{details} market impact India",
        f"similar {subject} announcement stock reaction India",
        f"{company} latest corporate announcement analysis",
    ]


def clean_query(query):
    query = re.sub(r"\s+", " ", str(query)).strip(" -\"'")
    return query[:220]


def parse_queries(raw_response):
    text = raw_response.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            parsed = parsed.get("queries", [])
        if isinstance(parsed, list):
            return [clean_query(q) for q in parsed if clean_query(q)]
    except json.JSONDecodeError:
        pass

    queries = []
    for line in text.splitlines():
        clean = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if clean:
            queries.append(clean_query(clean))
    return [q for q in queries if q]


def generate_queries(state):
    r = state["records"][0]

    company = r.get("COMPANY NAME") or r.get("SYMBOL", "")
    subject = r.get("SUBJECT") or "corporate announcement"
    details = r.get("DETAILS") or ""

    prompt = f"""
You generate search queries for an Indian stock-market research pipeline.

Company: {company}
Symbol: {r.get("SYMBOL", "")}
Announcement subject: {subject}
Announcement details: {details}

Return only valid JSON in this exact shape:
["query 1", "query 2", "query 3", "query 4", "query 5"]

Rules:
- Generate 4 to 5 high-quality web search queries.
- Include the company name or symbol in company-specific queries.
- Include one query for similar historical market reactions in India.
- Keep each query short and searchable.
- Do not include explanations or markdown.
""".strip()

    try:
        raw_response = call_query_model(prompt)
        queries = parse_queries(raw_response)
    except Exception as e:
        queries = []
        state["error_stage"] = state.get("error_stage") or "QUERY"
        state["error_reason"] = state.get("error_reason") or str(e)

    if len(queries) < 4:
        queries.extend(fallback_queries(company, subject, details))

    deduped = []
    seen = set()
    for query in queries:
        normalized = query.lower()
        if normalized not in seen:
            deduped.append(query)
            seen.add(normalized)

    state["queries"] = deduped[:5]
    log("QUERY", f"{len(state['queries'])} queries generated")
    return state
