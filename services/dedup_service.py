import math
import re
from collections import Counter
from typing import Dict, List


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\b[a-z]{2,}\b", text.lower())


def _build_idf(token_lists: List[List[str]]) -> Dict:
    n = len(token_lists)
    doc_freq: Counter = Counter()
    for tokens in token_lists:
        for word in set(tokens):
            doc_freq[word] += 1
    return {word: math.log((n + 1) / (freq + 1)) for word, freq in doc_freq.items()}


def _tfidf_vector(tokens: List[str], idf: dict) -> dict:
    tf = Counter(tokens)
    total = len(tokens) or 1
    return {word: (count / total) * idf.get(word, 1.0) for word, count in tf.items()}


def _cosine(v1: dict, v2: dict) -> float:
    shared = set(v1) & set(v2)
    if not shared:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in shared)
    mag1 = math.sqrt(sum(x * x for x in v1.values()))
    mag2 = math.sqrt(sum(x * x for x in v2.values()))
    if not mag1 or not mag2:
        return 0.0
    return dot / (mag1 * mag2)


def deduplicate(tweets: List[dict], threshold: float = 0.85) -> List[dict]:
    """Remove near-duplicate tweets using TF-IDF cosine similarity.

    When two tweets exceed *threshold* similarity the later one is dropped,
    keeping the tweet from the higher-weight account (or earlier arrival).
    """
    if len(tweets) <= 1:
        return list(tweets)

    # Sort by account weight desc so higher-authority tweets survive dedup
    ordered = sorted(tweets, key=lambda t: t.get("account_weight", 0.70), reverse=True)

    token_lists = [_tokenize(t.get("clean_text", "")) for t in ordered]
    idf = _build_idf(token_lists)
    vectors = [_tfidf_vector(tl, idf) for tl in token_lists]

    removed: set = set()
    for i in range(len(ordered)):
        if i in removed:
            continue
        for j in range(i + 1, len(ordered)):
            if j in removed:
                continue
            if _cosine(vectors[i], vectors[j]) >= threshold:
                removed.add(j)

    return [ordered[i] for i in range(len(ordered)) if i not in removed]
