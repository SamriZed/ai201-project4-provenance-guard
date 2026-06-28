# ai 201-project4-provenance-guard 

## Demo
![](./assets/Codetour.mp4)

## Running the app

The application entrypoint is **`submit_stub.py`**.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Groq API key in a .env file
echo "GROQ_API_KEY=your-key-here" > .env

# 3. Run the server (http://localhost:5000)
python submit_stub.py
```

### Endpoints

| Method & path | Purpose |
|---------------|---------|
| `POST /submit` | Analyze text with both detection signals; returns attribution, confidence, label, and per-signal scores. Rate-limited (see below). |
| `POST /appeal` | File an appeal for a prior submission by `content_id`; sets status to "under review" and logs it alongside the original decision. |
| `GET /log` | Return recent audit log entries as JSON (newest first; optional `?limit=N`). |

Submissions and appeals are held in memory and in the append-only audit log
(`audit_log.jsonl`); the in-memory store resets when the server restarts.

## Architecture overview

The path a submission takes from input to transparency label:

```
POST /submit (text + creator_id)
        │
        ├──► Signal 1: Groq LLM detector      ──► llm_score (0–1)
        └──► Signal 2: stylometric detector   ──► stylometric_score (0–1)
                        │
                        ▼
        Confidence scoring (weighted average) ──► confidence (0–1)
                        │
                        ▼
        Transparency label (threshold mapping)
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
   Audit log entry              JSON response to user
```

An appeal (`POST /appeal`) re-enters at the audit log: it sets the submission's
status to "under review" and appends event entries without re-running detection.

## Detection signals

Two independent signals are combined so neither failure mode dominates: one
reasons about *meaning*, the other measures *structure*.

**Signal 1 — Groq LLM classifier.** Sends the text to a Groq-hosted LLM and asks
for a structured AI-likelihood judgment. *Why:* it's the only signal that
understands semantics — tone, phrasing patterns, formulaic transitions, and the
"too-polished" quality of much AI writing. *Misses:* very short text, heavily
edited AI output, and polished human writing (academic/non-native) that it
mistakes for AI.

**Signal 2 — stylometric heuristics.** Computes measurable structure: sentence
length variance (coefficient of variation), vocabulary diversity (MATTR),
punctuation variety, and average sentence length. *Why:* cheap, deterministic,
API-free, and catches the *uniformity* AI text tends to exhibit — a different
axis than the LLM. *Misses:* it cannot read meaning, so it mislabels naturally
uniform human writing (poetry, terse prose) and is unreliable on short text.

## Audit Log

Every action writes a structured entry to **`audit_log.jsonl`** — one JSON
object per line (JSON Lines format), not unformatted console output. The log is
append-only and machine-readable; it can be re-read via `GET /log` or
`audit.read_entries()`.

Each **classification entry** captures the timestamp, content ID, attribution,
combined confidence, and both individual signal scores:

```json
{"content_id": "a49df534-8770-49de-8aec-bd5b07c52522", "creator_id": "writer-1", "timestamp": "2026-06-28T14:15:49.550Z", "attribution": "likely_human", "confidence": 0.177, "llm_score": 0.2, "stylometric_score": 0.1426, "status": "classified"}
{"content_id": "1d64d6b5-a1f4-47c8-a684-3e082a8fd567", "creator_id": "writer-2", "timestamp": "2026-06-28T14:15:51.068Z", "attribution": "likely_ai", "confidence": 0.6624, "llm_score": 0.8, "stylometric_score": 0.4559, "status": "classified"}
{"content_id": "68cf20ef-4fd2-4589-9344-4a7fb46d5501", "creator_id": "writer-3", "timestamp": "2026-06-28T14:15:53.831Z", "attribution": "likely_human", "confidence": 0.282, "llm_score": 0.2, "stylometric_score": 0.4051, "status": "classified"}
```

When an appeal is filed, two **event entries** are appended for the same
`content_id`. The `Appeal Submitted` entry logs the creator's reasoning
*alongside the original classification decision*, so a reviewer sees both:

```json
{"content_id": "1d64d6b5-a1f4-47c8-a684-3e082a8fd567", "timestamp": "2026-06-28T14:15:53.834Z", "event": "Appeal Submitted", "details": {"creator_reasoning": "I wrote this myself; English is my second language so my style reads as formal.", "notes": null, "original_classification": {"attribution": "likely_ai", "confidence_score": 0.6624, "label": "Likely AI-Generated", "llm_score": 0.8, "stylometric_score": 0.4559}}}
{"content_id": "1d64d6b5-a1f4-47c8-a684-3e082a8fd567", "timestamp": "2026-06-28T14:15:53.834Z", "event": "Status Updated to Under Review"}
```

Whether an appeal has been filed for a submission is determined by the presence
of its `Appeal Submitted` event (here, only `1d64d6b5…` has one).

### Fields captured

| Field | Where | Meaning |
|-------|-------|---------|
| `timestamp` | every entry | ISO-8601 UTC, millisecond precision |
| `content_id` | every entry | Unique submission ID |
| `attribution` | classification | `likely_human` / `uncertain` / `likely_ai` |
| `confidence` | classification | Combined weighted score (0–1) |
| `llm_score` | classification | Signal 1 (Groq LLM) score (0–1) |
| `stylometric_score` | classification | Signal 2 (stylometric) score (0–1) |
| `event` + `details` | appeal events | Appeal reasoning + original decision snapshot |

## Rate Limiting

The `POST /submit` endpoint is rate-limited with **Flask-Limiter**, keyed by
client IP address:

```
@limiter.limit("10 per minute;100 per day")
```

Both limits apply together — a client must stay under **10 requests/minute**
*and* **100 requests/day**. Only `/submit` is throttled; `/log` and `/appeal`
are unrestricted.

### Why these numbers

`/submit` is the one endpoint that runs the detection pipeline, including a call
to the Groq LLM, so it is both the most expensive route and the obvious target
for abuse. The limits are chosen to sit comfortably above realistic human usage
while cutting off automated flooding:

| Limit | Reasoning |
|-------|-----------|
| **10 / minute** | A real creator checking their own work submits a handful of times — initial check, a couple of edits, a re-check. Ten per minute leaves generous headroom for that bursty, manual pattern, but a script firing continuously hits the wall within seconds. |
| **100 / day** | Even a heavy legitimate user (a writer iterating on several pieces) is unlikely to exceed a few dozen submissions a day. A 100/day ceiling covers that with room to spare, while capping sustained abuse — and bounding Groq API cost — over a longer window than the per-minute rule can. |

The two windows are complementary: the per-minute limit stops short bursts, and
the per-day limit stops a slow drip that stays under the minute threshold but
still adds up to abuse (e.g. ~9 requests every minute all day).

### Behavior and storage

- Exceeding either limit returns **HTTP 429 (Too Many Requests)**.
- Storage is in-memory (`storage_uri="memory://"`), which is sufficient for
  local development; counters reset when the server restarts. A production
  deployment would point this at a shared store such as Redis so limits hold
  across multiple workers/instances.

## Terminal output example

  $ for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
200
200
200
200
200
200
200
200
200
200
429
429

## Confidence scoring

The two signal scores are combined with a **weighted average**:

```
confidence = (0.6 × llm_score) + (0.4 × stylometric_score)
```

*Why weighted, and why 0.6 / 0.4:* the LLM reasons about meaning, while the
stylometric heuristics are structural-only and easier to fool (uniform human
writing, edited AI). The LLM is therefore the more trustworthy signal and gets
the larger weight, but stylometry still pulls the score when the two disagree —
which deliberately drags borderline cases toward "uncertain" rather than forcing
a confident verdict.

*How it was validated as meaningful:* scores were checked across clearly
different inputs to confirm they spread apart and reach all three label bands. A
polished, uniform paragraph and a casual, irregular one produce very different
results:

```
=== example 1 (high confidence) ===
  llm_score:   0.8
  stylo_score: 0.3027
  confidence:  0.6011   -> Likely AI-Generated

=== example 2 (lower confidence) ===
  llm_score:   0.2
  stylo_score: 0.1475
  confidence:  0.179    -> Likely Human-Written
```

## Transparency label

The confidence score maps to one of three labels (thresholds from the spec).
Exact displayed text:

| Range | Label | Description shown |
|-------|-------|-------------------|
| `0.60–1.00` | **Likely AI-Generated** | "This content shows multiple characteristics commonly associated with AI-generated writing." |
| `0.40–0.59` | **Mixed or Uncertain Origin** | "The available signals do not provide enough evidence to confidently classify this content as either human-written or AI-generated." |
| `0.00–0.39` | **Likely Human-Written** | "This content shows multiple characteristics commonly associated with human-written writing." |

Labels use cautious "Likely…" wording and report a confidence score rather than
claiming certainty.

## Known limitations

**Polished human writing by non-native English speakers (or formal academic
prose) is likely misclassified as AI.** The LLM associates consistent tone and
formal phrasing with AI generation, and the stylometric detector reads the
resulting uniformity as further evidence — so both signals push the same wrong
way and can cross the 0.60 threshold. This is exactly the case the appeal
workflow exists to catch: the creator can contest the result, and the appeal is
logged alongside the original decision for human review. (Other weak spots:
heavily edited AI text can read as human, and text under ~20 words is too short
for the stylometric signal to judge, so it abstains to a neutral 0.5.)

## Spec reflection

*Where the spec helped:* the explicit confidence thresholds and label design
(0.00–0.39 / 0.40–0.59 / 0.60–1.00 with fixed label text) made the
scoring-to-label step unambiguous to implement and easy to test at the
boundaries.

*Where implementation diverged:* the spec listed raw **type-token ratio** as the
vocabulary-diversity feature. In testing, raw TTR proved length-dependent — short
submissions always score high, zeroing the feature out — so it was replaced with
**MATTR** (moving-average TTR over a fixed window), which is comparable across
input lengths and only fires on genuine repetition.

## AI usage

AI-assisted development was used throughout, with the planning document as the
source of truth and human review on every generated piece. Two specific
instances:

1. **Stylometric signal + scoring.** Directed the AI to generate Signal 2 and the
   confidence-combination logic from the spec. On testing, the type-token-ratio
   feature was always returning 0 on short inputs. I diagnosed it with the AI,
   rejected a quick "just lower the threshold" patch, and directed it to
   implement the length-normalized **MATTR** approach instead.

2. **Appeal endpoint.** Directed the AI to build `POST /appeal` from the spec. I
   overrode its initial output: renamed the field to `creator_reasoning`, changed
   the status value to **"under review"**, and required the appeal to be logged
   *alongside the original classification decision* — then updated the planning
   doc to match so spec and code stayed consistent.
