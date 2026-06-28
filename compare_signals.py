"""Compare Signal 1 (Groq LLM) and Signal 2 (stylometric) on identical inputs.

Runs both detectors over the SAME sample texts used in the Signal 1 harness,
then shows their scores side by side, the combined confidence, and whether the
two signals agree or diverge. This is the Milestone 4 verification step: does a
structural signal corroborate or contradict the semantic one?

Run from the project root:
    python compare_signals.py
"""

from dotenv import load_dotenv

from confidence import combine_scores
from signals.llm_detector import classify_text
from signals.stylometric import analyze

load_dotenv()  # pull GROQ_API_KEY out of .env for Signal 1

# Same inputs Signal 1 was tested on, so the comparison is apples-to-apples.
SAMPLES = {
    "clearly human": "ugh, monday again. spilled coffee on my notes lol. "
    "gonna be one of those weeks i can already tell.",
    "clearly AI": "In conclusion, leveraging synergistic methodologies "
    "enables stakeholders to optimize outcomes across multiple dimensions "
    "while ensuring sustainable, scalable, and impactful results.",
    "short text": "Hello there.",
    "long human": "I spent the whole weekend rewiring the old lamp my "
    "grandfather left me. Half the screws were stripped and I swore at it "
    "more than once, but when it finally flickered on I just sat there "
    "grinning like an idiot. Funny how a busted lamp can do that.",
}


def band(score):
    """Coarse verdict band, using the thresholds from planning.md."""
    if score >= 0.60:
        return "likely_ai"
    if score >= 0.40:
        return "uncertain"
    return "likely_human"


def main():
    header = f"{'input':<16}{'llm':>7}{'stylo':>8}{'diff':>7}{'combined':>10}  agreement"
    print(header)
    print("-" * len(header))

    for label, text in SAMPLES.items():
        llm = classify_text(text)["ai_probability"]
        stylo = analyze(text)["ai_probability"]
        combined = combine_scores(llm, stylo)
        diff = abs(llm - stylo)

        # Do the two signals land in the same verdict band?
        agree = "AGREE" if band(llm) == band(stylo) else "DIVERGE"
        agreement = f"{agree} ({band(llm)} vs {band(stylo)})"

        print(f"{label:<16}{llm:>7.2f}{stylo:>8.2f}{diff:>7.2f}"
              f"{combined:>10.2f}  {agreement}")

    print("\nReading the table:")
    print("  - diff is |llm - stylo|; small = the signals corroborate each other.")
    print("  - DIVERGE rows are the interesting ones: e.g. a polished human essay")
    print("    where the LLM says 'human' but uniform structure reads 'AI', or an")
    print("    edited AI text where structure looks human but the LLM is suspicious.")


if __name__ == "__main__":
    main()
