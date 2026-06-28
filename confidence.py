"""Confidence scoring.

Combines the two detection signals into a single confidence score using a
weighted average, as described in the Architecture Narrative (planning.md):

    "The confidence scoring component receives the LLM score and stylometric
     score and combines them using a weighted average. The resulting confidence
     score ranges from 0.0 to 1.0 and represents the likelihood that the text
     is AI-generated."

Signal 1 (Groq LLM) is weighted more heavily than Signal 2 (stylometric)
because it reasons about meaning, whereas the stylometric heuristics are
structural-only and easier to fool (see the blind spots in planning.md). Adjust
the weights below to change the balance.
"""

# Weights for the weighted average. They are normalized at combine time, so they
# need not sum to exactly 1.0 — only their ratio matters.
W_LLM = 0.6
W_STYLOMETRIC = 0.4

# Confidence thresholds -> transparency labels (planning.md):
#     0.00 - 0.39  Likely Human-Written
#     0.40 - 0.59  Mixed or Uncertain Origin
#     0.60 - 1.00  Likely AI-Generated
HUMAN_MAX = 0.40        # below this -> human
AI_MIN = 0.60           # at/above this -> AI; between the two -> uncertain

# Label text and machine-readable key for each band (descriptions from the
# Transparency Label Design section of planning.md).
LABELS = {
    "likely_ai": {
        "label": "Likely AI-Generated",
        "description": "This content shows multiple characteristics commonly "
        "associated with AI-generated writing.",
    },
    "uncertain": {
        "label": "Mixed or Uncertain Origin",
        "description": "The available signals do not provide enough evidence to "
        "confidently classify this content as either human-written or "
        "AI-generated.",
    },
    "likely_human": {
        "label": "Likely Human-Written",
        "description": "This content shows multiple characteristics commonly "
        "associated with human-written writing.",
    },
}


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


def classify(confidence):
    """Map a combined confidence score to a transparency label band.

    Returns a dict with ``attribution`` (machine key: 'likely_human',
    'uncertain', or 'likely_ai'), ``label`` (display text), and ``description``.
    """
    confidence = _clamp(float(confidence))
    if confidence >= AI_MIN:
        key = "likely_ai"
    elif confidence >= HUMAN_MAX:
        key = "uncertain"
    else:
        key = "likely_human"
    return {"attribution": key, **LABELS[key]}


def combine_scores(llm_score, stylometric_score,
                   w_llm=W_LLM, w_stylometric=W_STYLOMETRIC):
    """Return the weighted-average confidence that the text is AI-generated.

    Args:
        llm_score: Signal 1 score in [0, 1].
        stylometric_score: Signal 2 score in [0, 1].
        w_llm: Weight for the LLM signal.
        w_stylometric: Weight for the stylometric signal.

    Returns:
        A confidence float in [0, 1], rounded to 4 decimals.
    """
    total_weight = w_llm + w_stylometric
    if total_weight <= 0:
        raise ValueError("Signal weights must sum to a positive number.")

    llm_score = _clamp(float(llm_score))
    stylometric_score = _clamp(float(stylometric_score))

    confidence = (llm_score * w_llm + stylometric_score * w_stylometric) / total_weight
    return round(_clamp(confidence), 4)


def score_breakdown(llm_score, stylometric_score,
                    w_llm=W_LLM, w_stylometric=W_STYLOMETRIC):
    """Return the confidence score plus the inputs/weights that produced it.

    Useful for the audit log and reviewer view, which need to show how the
    combined score was reached.
    """
    confidence = combine_scores(llm_score, stylometric_score, w_llm, w_stylometric)
    return {
        "confidence": confidence,
        "llm_score": round(_clamp(float(llm_score)), 4),
        "stylometric_score": round(_clamp(float(stylometric_score)), 4),
        "weights": {"llm": w_llm, "stylometric": w_stylometric},
    }


def assess(llm_score, stylometric_score,
           w_llm=W_LLM, w_stylometric=W_STYLOMETRIC):
    """Combine both signals and classify the result in one call.

    Returns a dict with the combined ``confidence``, the per-signal
    ``breakdown``, and the resolved ``attribution``/``label``/``description``.
    This is the single entry point the /submit endpoint should call.
    """
    breakdown = score_breakdown(llm_score, stylometric_score, w_llm, w_stylometric)
    verdict = classify(breakdown["confidence"])
    return {**verdict, "confidence": breakdown["confidence"], "breakdown": breakdown}


if __name__ == "__main__":
    # Show that the combined score varies meaningfully and reaches all three
    # label bands across clearly different inputs.
    cases = [
        ("strong AI on both", 0.90, 0.85),
        ("LLM says AI, style says human", 0.80, 0.20),
        ("split / uncertain", 0.55, 0.45),
        ("strong human on both", 0.10, 0.15),
    ]
    print(f"{'case':<34}{'llm':>6}{'stylo':>7}{'conf':>7}  label")
    print("-" * 78)
    for label, llm, stylo in cases:
        result = assess(llm, stylo)
        print(f"{label:<34}{llm:>6.2f}{stylo:>7.2f}{result['confidence']:>7.2f}"
              f"  {result['label']}")
