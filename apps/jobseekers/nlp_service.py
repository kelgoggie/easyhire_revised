"""Lightweight NLP service used by autocomplete + analytics clustering.

Design notes
------------
* The sentence-transformers model (~80 MB) is loaded LAZILY on first use and
  cached for the process lifetime. We never block Django startup on it.
* Embeddings for static vocabularies are memoised by `cache_key` so we encode
  each candidate list once per process.
* If sentence_transformers/torch isn't available at runtime, all semantic
  helpers degrade gracefully — `semantic_rank()` returns [] and clustering
  falls back to identity (each input stays in its own bucket). This keeps
  the site working even on hosts where the ML deps fail to install.
"""

from __future__ import annotations

from typing import Iterable, Sequence

_model = None
_model_failed = False
_embedding_cache: dict[str, object] = {}  # cache_key -> torch tensor


# ── Canonical industry buckets for analytics ─────────────────────────
CANONICAL_INDUSTRIES = [
    'Healthcare',
    'Education',
    'Information Technology',
    'Retail',
    'Manufacturing',
    'Construction',
    'Finance & Banking',
    'Hospitality & Tourism',
    'Government',
    'Agriculture',
    'Transportation & Logistics',
    'Real Estate',
    'Food Service',
    'Professional Services',
    'Non-profit / NGO',
    'Media & Entertainment',
    'Telecommunications',
    'Energy & Utilities',
    'Other',
]


def get_model():
    """Lazy-load the sentence-transformer model. Returns None on failure."""
    global _model, _model_failed
    if _model is not None:
        return _model
    if _model_failed:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    except Exception:
        _model_failed = True
        return None
    return _model


def _get_or_compute_embeddings(candidates: Sequence[str], cache_key: str | None):
    """Encode candidates once, reuse on subsequent calls with the same key."""
    model = get_model()
    if model is None:
        return None
    if cache_key and cache_key in _embedding_cache:
        return _embedding_cache[cache_key]
    embs = model.encode(list(candidates), convert_to_tensor=True, show_progress_bar=False)
    if cache_key:
        _embedding_cache[cache_key] = embs
    return embs


def semantic_rank(
    query: str,
    candidates: Sequence[str],
    *,
    cache_key: str | None = None,
    top_k: int = 10,
    min_similarity: float = 0.4,
) -> list[tuple[str, float]]:
    """Return [(candidate, similarity_score)] sorted by similarity (descending).

    Filters out matches below `min_similarity` (cosine similarity, 0-1 range).
    Returns [] if NLP model isn't available or input is empty.
    """
    if not query or not candidates:
        return []
    model = get_model()
    if model is None:
        return []
    try:
        from sentence_transformers import util
        query_emb = model.encode(query, convert_to_tensor=True, show_progress_bar=False)
        cand_embs = _get_or_compute_embeddings(candidates, cache_key)
        sims = util.cos_sim(query_emb, cand_embs)[0]
        scored = [
            (cand, float(score))
            for cand, score in zip(candidates, sims)
            if float(score) >= min_similarity
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
    except Exception:
        return []


def smart_rank(
    query: str,
    candidates: Iterable[str],
    *,
    limit: int = 10,
    cache_key: str | None = None,
    enable_semantic: bool = True,
) -> list[str]:
    """Combined ranking: prefix > substring > fuzzy > semantic.

    Each signal contributes to a per-candidate score; the top `limit` strings
    are returned, deduplicated, sorted by score.

    * Prefix match — anchors to what users typing actually expect
    * Substring match — also a strong signal
    * Fuzzy (rapidfuzz) — typo tolerance, only for 2+ char queries
    * Semantic — meaning-related suggestions, only for 3+ char queries
    """
    q = (query or '').strip().lower()
    if not q:
        return []

    candidates = list(dict.fromkeys(c for c in candidates if c))  # dedupe, drop blanks
    if not candidates:
        return []

    scores: dict[str, float] = {}

    # prefix
    for c in candidates:
        cl = c.lower()
        if cl.startswith(q):
            scores[c] = max(scores.get(c, 0), 100.0)

    # 2) substring
    for c in candidates:
        if c in scores:
            continue
        if q in c.lower():
            scores[c] = max(scores.get(c, 0), 75.0)

    # 3) fuzzy
    if len(q) >= 2:
        try:
            from rapidfuzz import fuzz
            for c in candidates:
                if c in scores:
                    continue
                score = fuzz.partial_ratio(q, c.lower())
                if score >= 82:   # tight threshold so we don't pollute
                    scores[c] = max(scores.get(c, 0), score * 0.55)
        except ImportError:
            pass

    # 4) semantic — concept similarity (3+ chars for meaningful queries)
    if enable_semantic and len(q) >= 3:
        for cand, sim in semantic_rank(q, candidates, cache_key=cache_key,
                                       top_k=8, min_similarity=0.45):
            # Convert 0-1 cosine sim to a 0-60 contribution so prefix/substring
            # matches still win when they exist.
            existing = scores.get(cand, 0)
            semantic_score = sim * 60
            if semantic_score > existing:
                scores[cand] = semantic_score

    ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
    return [c for c, _ in ranked]


def cluster_to_canonical(
    values: Iterable[str],
    canonical_buckets: Sequence[str] = CANONICAL_INDUSTRIES,
    *,
    min_similarity: float = 0.35,
    cache_key: str | None = 'canonical_industries',
) -> dict[str, str]:
    """Map each input value to the closest canonical bucket.

    Returns: { input_value: canonical_bucket }.
    If the best match is below `min_similarity`, the value is mapped to 'Other'.
    If NLP is unavailable, returns identity mapping (each value maps to itself).
    """
    values = [v for v in values if v]
    if not values:
        return {}

    model = get_model()
    if model is None:
        return {v: v for v in values}

    try:
        from sentence_transformers import util
        bucket_embs = _get_or_compute_embeddings(canonical_buckets, cache_key)
        value_embs = model.encode(list(values), convert_to_tensor=True, show_progress_bar=False)
        sims = util.cos_sim(value_embs, bucket_embs)
        out = {}
        for i, value in enumerate(values):
            best_idx = int(sims[i].argmax())
            best_sim = float(sims[i][best_idx])
            if best_sim >= min_similarity:
                out[value] = canonical_buckets[best_idx]
            else:
                out[value] = 'Other'
        return out
    except Exception:
        return {v: v for v in values}
