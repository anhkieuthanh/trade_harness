from __future__ import annotations

import math
import re
from collections import Counter

from tradeharness.runtime.skills.library import get_skill_library


TOKEN_PATTERN = re.compile(r"[a-z0-9_:-]+")


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _skill_document(skill: dict[str, object]) -> str:
    return " ".join(
        str(skill[field])
        for field in ["title", "tags", "when_to_use", "procedure", "anti_patterns"]
    )


def retrieve_relevant_skills(query: str, top_k: int = 2) -> list[dict[str, object]]:
    skills = get_skill_library()
    documents = [_tokenize(_skill_document(skill)) for skill in skills]
    query_tokens = _tokenize(query)
    if not query_tokens:
        return skills[:top_k]

    doc_lengths = [len(doc) for doc in documents]
    avg_doc_length = sum(doc_lengths) / max(len(doc_lengths), 1)
    document_frequencies = Counter()
    for document in documents:
        for token in set(document):
            document_frequencies[token] += 1

    k1 = 1.5
    b = 0.75
    total_docs = len(documents)
    scored: list[tuple[float, dict[str, object]]] = []

    for skill, document in zip(skills, documents):
        term_counts = Counter(document)
        score = 0.0
        for token in query_tokens:
            if token not in term_counts:
                continue
            df = document_frequencies[token]
            idf = math.log(1 + ((total_docs - df + 0.5) / (df + 0.5)))
            tf = term_counts[token]
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (len(document) / max(avg_doc_length, 1)))
            score += idf * (numerator / denominator)
        scored.append((score, skill))

    ranked = sorted(scored, key=lambda item: item[0], reverse=True)
    return [skill for score, skill in ranked[:top_k] if score > 0] or [skills[0]]
