from __future__ import annotations

import math
import re
from collections import Counter

_STOPWORDS = {
    "jaki",
    "jaka",
    "jakie",
    "jaką",
    "ile",
    "czy",
    "jest",
    "są",
    "oraz",
    "żeby",
    "aby",
    "tego",
    "tym",
    "tej",
    "dla",
    "bez",
    "nie",
    "tak",
    "się",
    "po",
    "na",
    "do",
    "od",
    "za",
    "co",
    "w",
    "z",
    "i",
    "a",
    "o",
    "u",
}


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.lower(), flags=re.UNICODE) if len(t) > 2 and t not in _STOPWORDS]


def _idf(docs: list[list[str]]) -> dict[str, float]:
    df: Counter[str] = Counter()
    for doc in docs:
        for term in set(doc):
            df[term] += 1
    n = max(len(docs), 1)
    return {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(tokens)
    total = max(sum(tf.values()), 1)
    return {term: (count / total) * idf.get(term, 1.0) for term, count in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_segments(
    segments: list[tuple[float, float, str]],
    question: str,
    limit: int = 24,
) -> list[tuple[float, float, str]]:
    """Lightweight TF-IDF retrieval over transcript segments."""
    if not segments:
        return []
    docs = [_tokenize(text) for _start, _end, text in segments]
    idf = _idf(docs)
    query_vec = _tfidf_vector(_tokenize(question), idf)
    if not query_vec:
        return segments[:limit]

    scored: list[tuple[float, tuple[float, float, str]]] = []
    for seg, tokens in zip(segments, docs):
        score = _cosine(_tfidf_vector(tokens, idf), query_vec)
        if "ile" in question.lower() and re.search(r"\d", seg[2]):
            score += 0.15
        scored.append((score, seg))

    scored.sort(key=lambda item: (-item[0], item[1][0]))
    top = [seg for score, seg in scored if score > 0][:limit]
    if not top:
        return segments[: min(limit, len(segments))]
    top.sort(key=lambda s: s[0])
    return top
