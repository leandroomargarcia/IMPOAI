"""Bottom-up lexical search over 8-digit NCM items (BM25, no LLM)."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any

from ncm.medidas import fold

STOPWORDS = {
    "a", "al", "con", "de", "del", "demas", "e", "el", "en", "la", "las",
    "lo", "los", "o", "otro", "otros", "para", "por", "que", "se", "sin",
    "su", "sus", "u", "un", "una", "y",
}


def stem(word: str) -> str:
    """Light Spanish stem: muebles/mueble -> muebl, azucares/azucar -> azucar."""
    if len(word) > 3 and word.endswith("s"):
        word = word[:-1]
    if len(word) > 3 and word[-1] in "aeo":
        word = word[:-1]
    return word


def tokens(text: str) -> list[str]:
    """ Convert a text to a list of tokens. """
    words = re.findall(r"[a-z0-9]+", fold(text))
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


class ItemIndex:
    def __init__(self, items: list[dict[str, Any]], k1: float = 1.2, b: float = 0.75):
        self.items = items
        self.k1 = k1
        self.b = b
        self.docs = [Counter(tokens(i.get("descripcion_completa") or "")) for i in items]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg_len = (sum(self.lens) / len(self.lens)) if self.lens else 0.0
        df: Counter = Counter()
        self.postings: dict[str, list[int]] = defaultdict(list)
        for idx, doc in enumerate(self.docs):
            df.update(doc.keys())
            for term in doc:
                self.postings[term].append(idx)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    @classmethod
    def from_catalog(cls, catalog) -> "ItemIndex":
        return cls(catalog.data["items"])

    def search(self, query: str, k: int | None = 20) -> list[dict[str, Any]]:
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokens(query)):
            idf = self.idf.get(term)
            if not idf:
                continue
            for idx in self.postings[term]:
                tf = self.docs[idx][term]
                norm = 1 - self.b + self.b * self.lens[idx] / (self.avg_len or 1)
                scores[idx] += idf * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        if k is not None:
            ranked = ranked[:k]
        return [
            {
                "ncm": self.items[idx]["codigo"],
                "partida": self.items[idx]["partida"],
                "score": round(score, 3),
                "text": self.items[idx]["descripcion_completa"],
            }
            for idx, score in ranked
        ]