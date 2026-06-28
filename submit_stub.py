"""POST /submit: runs both detection signals, combines them, and logs the result.

Returns, at minimum:
    - content_id        unique ID for this submission (needed by /appeal + audit log)
    - attribution       verdict key (likely_human / uncertain / likely_ai)
    - confidence_score  weighted average of both signals
    - label             transparency label mapped from the confidence score

Every call appends one structured entry to the audit log (see audit.py).

Run with:
    python submit_stub.py
"""

import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import audit
from confidence import assess
from signals.llm_detector import classify_text
from signals.stylometric import analyze

# Load GROQ_API_KEY from .env before the detector reads the environment.
load_dotenv()

app = Flask(__name__)

# Rate limiting keyed by client IP. In-memory storage is fine for local dev;
# swap storage_uri for Redis/Memcached in production. No global default limits —
# we only throttle the expensive /submit route (each call hits the Groq API).
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

# In-memory store (replaced by real persistence in Milestone 5). Keyed by
# content_id so the appeal endpoint can look a submission up later.
SUBMISSIONS = {}


@app.errorhandler(429)
def ratelimit_exceeded(e):
    """Return rate-limit errors as JSON, consistent with the rest of the API."""
    return jsonify({
        "error": "Rate limit exceeded. Please slow down and try again later.",
        "limit": str(e.description),
    }), 429


@app.get("/log")
def log():
    """Return the most recent audit log entries as JSON (newest first).

    Optional query param ?limit=N caps how many entries are returned (default 50).
    """
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50

    entries = audit.read_entries()
    entries.reverse()  # newest first
    return jsonify({"entries": entries[:limit]})


@app.post("/submit")
@limiter.limit("10 per minute;100 per day")
def submit():
    """Analyze a submission with Signal 1, log it, and return a structured response."""
    # --- Request validation -------------------------------------------------
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "'text' is required and must be a non-empty string."}), 400

    creator_id = data.get("creator_id")
    if not isinstance(creator_id, str) or not creator_id.strip():
        return jsonify({"error": "'creator_id' is required and must be a non-empty string."}), 400

    # --- Identify this submission -------------------------------------------
    content_id = str(uuid.uuid4())

    # --- Run both detection signals -----------------------------------------
    signal_1 = classify_text(text)            # Signal 1: Groq LLM
    signal_2 = analyze(text)                   # Signal 2: stylometric
    llm_score = round(signal_1["ai_probability"], 4)
    stylometric_score = round(signal_2["ai_probability"], 4)

    # --- Combine + classify (weighted average -> transparency label) --------
    result = assess(llm_score, stylometric_score)
    confidence_score = result["confidence"]
    attribution = result["attribution"]
    label = result["label"]
    status = "classified"

    # --- Structured audit log entry (one per submission) --------------------
    audit.log_submission(
        content_id=content_id,
        creator_id=creator_id,
        attribution=attribution,
        confidence=confidence_score,
        llm_score=llm_score,
        stylometric_score=stylometric_score,
        status=status,
    )

    # --- Persist the submission record (for /appeal + reviewer view) --------
    record = {
        "content_id": content_id,
        "creator_id": creator_id,
        "text": text,
        "signal_1": signal_1,
        "signal_2": signal_2,
        "attribution": attribution,
        "confidence_score": confidence_score,
        "label": label,
        "description": result["description"],
        "status": status,
    }
    SUBMISSIONS[content_id] = record

    return jsonify(
        {
            "content_id": content_id,
            "creator_id": creator_id,
            "attribution": attribution,
            "confidence_score": confidence_score,
            "llm_score": llm_score,
            "stylometric_score": stylometric_score,
            "label": label,
            "description": result["description"],
            "status": status,
            "signal_1_detail": signal_1,
            "signal_2_detail": signal_2,
        }
    )


@app.post("/appeal")
def appeal():
    """Submit an appeal for a prior submission.

    Request body (JSON):
        {
            "content_id": "<id returned by /submit>",
            "creator_reasoning": "<why the creator believes the result is wrong>",
            "notes": "<optional supporting notes>"
        }

    Per the Appeals Workflow (planning.md): marks the submission "under review",
    logs the appeal alongside the original classification decision, and returns
    a confirmation. Automated re-classification is intentionally out of scope.
    """
    # --- Request validation -------------------------------------------------
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    content_id = data.get("content_id")
    if not isinstance(content_id, str) or not content_id.strip():
        return jsonify({"error": "'content_id' is required and must be a non-empty string."}), 400

    creator_reasoning = data.get("creator_reasoning")
    if not isinstance(creator_reasoning, str) or not creator_reasoning.strip():
        return jsonify({"error": "'creator_reasoning' is required and must be a non-empty string."}), 400

    notes = data.get("notes")  # optional supporting notes
    if notes is not None and not isinstance(notes, str):
        return jsonify({"error": "'notes' must be a string if provided."}), 400

    # --- Look up the submission ---------------------------------------------
    record = SUBMISSIONS.get(content_id)
    if record is None:
        return jsonify({"error": f"No submission found for content_id '{content_id}'."}), 404

    # --- Snapshot the original classification decision ----------------------
    original_classification = {
        "attribution": record["attribution"],
        "confidence_score": record["confidence_score"],
        "label": record["label"],
        "llm_score": record["signal_1"]["ai_probability"],
        "stylometric_score": record["signal_2"]["ai_probability"],
    }

    # --- Create the appeal record + update status ---------------------------
    appeal_record = {
        "content_id": content_id,
        "creator_reasoning": creator_reasoning,
        "notes": notes,
        "appeal_timestamp": audit.current_timestamp(),
    }
    record["status"] = "under review"
    record["appeal"] = appeal_record

    # --- Audit trail: log the appeal alongside the original decision --------
    audit.log_event(
        content_id,
        "Appeal Submitted",
        details={
            "creator_reasoning": creator_reasoning,
            "notes": notes,
            "original_classification": original_classification,
        },
    )
    audit.log_event(content_id, "Status Updated to Under Review")

    return jsonify(
        {
            "content_id": content_id,
            "status": record["status"],
            "appeal": appeal_record,
            "message": "Appeal received and is now under review.",
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
