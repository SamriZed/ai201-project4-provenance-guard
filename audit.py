"""Structured audit logging for Provenance Guard.

Every submission appends one JSON object (one line) to an append-only log file
(JSON Lines / .jsonl). This keeps the log structured and machine-readable while
staying dead simple to write and to read back later for the reviewer view.

Each entry looks like:

    {
      "content_id": "3f7a2b1e-...",
      "creator_id": "test-user-1",
      "timestamp": "2026-06-27T14:32:10.123Z",
      "attribution": "likely_ai",
      "confidence": 0.78,
      "llm_score": 0.81,
      "status": "classified"
    }
"""

import json
import os
from datetime import datetime, timezone

# Log lives next to this module so it's found regardless of where the app is run.
AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_log.jsonl")


def current_timestamp():
    """Return an ISO-8601 UTC timestamp with millisecond precision, e.g.
    '2026-06-27T14:32:10.123Z'."""
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _append(entry, path):
    """Write one JSON entry as a line to the append-only log."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def log_event(content_id, event, details=None, path=AUDIT_LOG_PATH):
    """Append a lifecycle/event entry to the audit log.

    Used for events that aren't a full classification, e.g. "Appeal Submitted"
    or "Status Updated to Appeal Pending" (see the Audit Log Example in
    planning.md).

    Args:
        content_id: Submission the event relates to.
        event: Short event name.
        details: Optional dict of extra context (reason, notes, etc.).
        path: Override the log file location (useful for tests).

    Returns:
        The entry dict that was written (timestamp included).
    """
    entry = {
        "content_id": content_id,
        "timestamp": current_timestamp(),
        "event": event,
    }
    if details:
        entry["details"] = details
    return _append(entry, path)


def log_submission(content_id, creator_id, attribution, confidence,
                   llm_score, stylometric_score=None, status="classified",
                   path=AUDIT_LOG_PATH):
    """Append a structured submission entry to the audit log.

    Args:
        content_id: Unique ID for the submission.
        creator_id: ID of the creator who submitted the content.
        attribution: Human-readable verdict, e.g. "likely_ai".
        confidence: Combined confidence score in [0, 1].
        llm_score: Signal 1 (Groq LLM) score in [0, 1].
        stylometric_score: Signal 2 (stylometric) score in [0, 1], or None.
        status: Lifecycle status, e.g. "classified".
        path: Override the log file location (useful for tests).

    Returns:
        The entry dict that was written (timestamp included).
    """
    entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": current_timestamp(),
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylometric_score": stylometric_score,
        "status": status,
    }
    return _append(entry, path)


def read_entries(path=AUDIT_LOG_PATH):
    """Read all audit entries back as a list of dicts (for reviewer/debugging)."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
