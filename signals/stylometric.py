"""Signal 2: Stylometric Heuristics.

Computes measurable structural features of the text and combines them into a
single score representing the likelihood that the text is AI-generated.

Features (see planning.md):
    - Sentence length variance   (uniform lengths   -> more AI-like)
    - Type-token ratio           (low vocab variety -> more AI-like)
    - Punctuation variety        (few mark types    -> more AI-like)
    - Average sentence length    ("complexity" proxy; AI clusters mid-length)

Rationale: AI-generated text tends to be more uniform because language models
optimize for consistency and fluency, while human writing varies more in
sentence length, vocabulary, and punctuation.

    0.15 = strongly human-like structure
    0.50 = mixed characteristics
    0.85 = strongly AI-like structure

Blind spots (see planning.md): cannot understand meaning; a naturally
consistent human writer, an edited AI text, or a particular genre (e.g. poetry)
can all fool these heuristics. Treated as one signal among several, never alone.
"""

import re
from statistics import mean, pstdev

# --- Tunable reference points -------------------------------------------------
# Each reference is the value at/above which a feature reads as fully "human"
# (sub-score 0). They are deliberately simple and adjustable.
_CV_REF = 0.5            # coefficient of variation of sentence lengths
# Vocabulary diversity is measured with MATTR (moving-average type-token ratio)
# over a fixed window so it is comparable across short and long inputs -- raw
# TTR inflates on short text and clamps the feature to zero. _MATTR_REF is the
# "diverse human vocabulary" level: at/above it the text reads fully human; only
# genuine repetition (MATTR well below it) pushes the score toward AI.
_MATTR_WINDOW = 25       # words per window
_MATTR_REF = 0.85
_PUNCT_VARIETY_REF = 4   # number of distinct punctuation marks used
_LEN_CENTER = 20         # sentence length (words) AI output tends to cluster near
_LEN_SPREAD = 20         # how far from center before the length signal fades

# Relative weights of each feature in the final stylometric score (sum to 1.0).
_WEIGHTS = {
    "sentence_length_cv": 0.35,
    "type_token_ratio": 0.30,
    "avg_sentence_length": 0.20,
    "punctuation_variety": 0.15,
}

# Below this many words there isn't enough structure to judge; return neutral.
_MIN_WORDS = 20

_PUNCTUATION = set(".,;:!?—-()\"'")

_NEUTRAL = {
    "ai_probability": 0.5,
    "features": {},
    "subscores": {},
    "note": "Text too short for reliable stylometric analysis; returning a "
    "neutral score.",
}


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


def _split_sentences(text):
    """Split into sentences on terminal punctuation, dropping empties."""
    parts = re.split(r"[.!?]+", text)
    return [p.strip() for p in parts if p.strip()]


def _words(text):
    """Lowercased word tokens (letters and apostrophes only)."""
    return re.findall(r"[a-z']+", text.lower())


def _ttr(tokens):
    """Type-token ratio: unique words / total words."""
    return len(set(tokens)) / len(tokens) if tokens else 0.0


def _mattr(tokens, window=_MATTR_WINDOW):
    """Moving-average type-token ratio.

    Averages the TTR of every ``window``-word sliding window, which makes the
    measure independent of total length. For text shorter than one window, falls
    back to plain TTR over all tokens.
    """
    if len(tokens) <= window:
        return _ttr(tokens)
    windows = [_ttr(tokens[i:i + window]) for i in range(len(tokens) - window + 1)]
    return sum(windows) / len(windows)


def analyze(text):
    """Return a structured stylometric assessment of ``text``.

    Returns a dict with keys ``ai_probability`` (float in [0, 1]), ``features``
    (the raw measurements), ``subscores`` (each feature's 0-1 AI-likeness), and
    an optional ``note``. Never raises on normal input.
    """
    if not text or not text.strip():
        return dict(_NEUTRAL)

    words = _words(text)
    if len(words) < _MIN_WORDS:
        return dict(_NEUTRAL)

    sentences = _split_sentences(text)
    sentence_lengths = [len(_words(s)) for s in sentences] or [len(words)]

    # --- Raw feature measurements ------------------------------------------
    avg_len = mean(sentence_lengths)
    # Coefficient of variation = std / mean (length-independent spread).
    cv = (pstdev(sentence_lengths) / avg_len) if avg_len else 0.0
    ttr = _ttr(words)            # whole-text TTR, reported for transparency
    mattr = _mattr(words)        # length-normalized; drives the sub-score
    punct_variety = len({ch for ch in text if ch in _PUNCTUATION})

    features = {
        "sentence_count": len(sentences),
        "word_count": len(words),
        "avg_sentence_length": round(avg_len, 2),
        "sentence_length_cv": round(cv, 3),
        "type_token_ratio": round(ttr, 3),
        "mattr": round(mattr, 3),
        "punctuation_variety": punct_variety,
    }

    # --- Per-feature AI-likeness sub-scores (0 = human, 1 = AI) -------------
    # Low variance -> uniform -> AI-like.
    ai_cv = _clamp(1 - cv / _CV_REF)
    # Low vocabulary diversity (MATTR below the human reference) -> AI-like.
    ai_ttr = _clamp(1 - mattr / _MATTR_REF)
    # Few distinct punctuation marks -> AI-like.
    ai_punct = _clamp(1 - punct_variety / _PUNCT_VARIETY_REF)
    # Sentence length near the typical AI range -> AI-like; extremes -> human.
    ai_len = _clamp(1 - abs(avg_len - _LEN_CENTER) / _LEN_SPREAD)

    subscores = {
        "sentence_length_cv": round(ai_cv, 3),
        "type_token_ratio": round(ai_ttr, 3),
        "avg_sentence_length": round(ai_len, 3),
        "punctuation_variety": round(ai_punct, 3),
    }

    # --- Weighted combination into one stylometric score -------------------
    score = sum(subscores[name] * weight for name, weight in _WEIGHTS.items())

    return {
        "ai_probability": round(_clamp(score), 4),
        "features": features,
        "subscores": subscores,
    }


if __name__ == "__main__":
    # Independent test harness. Run from project root:
    #   python -m signals.stylometric
    samples = {
        "clearly human": "Ugh, Monday again. I spilled coffee on my notes this "
        "morning — classic. Honestly? It's going to be one of those weeks; I can "
        "already tell. But hey, the dog seems thrilled about it.",
        "clearly AI": "Effective time management is essential for success. It "
        "allows individuals to prioritize tasks efficiently. It also reduces "
        "stress and improves productivity. Furthermore, it enables people to "
        "achieve their goals consistently. In conclusion, time management is a "
        "valuable skill for everyone.",
        "short text": "Hello there. How are you?",
    }
    for label, sample in samples.items():
        result = analyze(sample)
        print(f"\n=== {label} ===")
        print(f"  ai_probability: {result['ai_probability']}")
        print(f"  subscores:      {result.get('subscores')}")
        if result.get("note"):
            print(f"  note:           {result['note']}")
