# Detection Signals #

## Signal 1: Groq LLM Classification ##

### What it measures ###

The Groq-hosted LLM evaluates the overall semantic and stylistic characteristics of the writing. It looks at coherence, phrasing patterns, repetition, structure, and language usage.

### Why it differs between human and AI writing ###

Modern LLMs are trained on massive datasets and can recognize patterns that often appear in AI-generated text, such as:

Consistent tone
Predictable organization
Formulaic transitions
Excessively polished wording

### Output ###

The model returns a score between 0.0 and 1.0 representing the likelihood that the text is AI-generated.

Example 

0.10 = likely human-written
0.50 = uncertain
0.90 = likely AI-generated

### Blind spots ### 

The classifier may struggle with:

Very short text
Highly edited human writing
AI-generated text that has been heavily rewritten
Creative or professional human writing that resembles AI output

## Signal 2: Stylometric Heuristics ##

### What it measures ###

The stylometric detector computes measurable structural features such as:

Sentence length variance
Type-token ratio (vocabulary diversity)
Punctuation density
Average sentence complexity

### Why it differs between human and AI writing ###

AI-generated text often exhibits more uniform patterns because language models optimize for consistency and fluency. Human writing tends to contain greater variation in sentence lengths, vocabulary choices, and punctuation usage.

### Output ###

The stylometric module produces a score between 0.0 and 1.0 representing the likelihood that the text is AI-generated.

Example:

0.15 = strongly human-like structure
0.50 = mixed characteristics
0.85 = strongly AI-like structure

## Blind spots ##

Stylometric features cannot understand meaning.

A human writer may naturally write very consistently.
An AI-generated text can be edited to increase variability.
Different genres produce different stylistic patterns.

## False Positive Scenario ##

Suppose a student writes an essay entirely by themselves, but the writing is unusually polished and organized.

The Groq classifier predicts "likely AI."
Stylometric analysis finds low sentence-length variation and high consistency.
The combined score leans toward AI-generated content.

To reduce harm:

The system reports a confidence score rather than claiming certainty.
Labels use cautious language such as "Likely AI-Generated" instead of "AI-Generated."
The user receives a submission ID.
The user can submit an appeal using the appeal endpoint.
The appeal is logged in the audit trail for transparency and accountability.


---

# Uncertainty Representation #

The system is designed to express uncertainty rather than make absolute claims.

A confidence score of 0.60 means the combined evidence leans toward AI-generated text, but there is still significant uncertainty. The system will not present this as a definitive judgment.

### Confidence Thresholds ###

|Confidence Score	| Classification |
|-------------------|----------------|
|0.00 – 0.39	| Likely Human-Written |
|0.40 – 0.59	| Uncertain |
|0.60 – 1.00	| Likely AI-Generated |

--- 

# Transparency Label Design #

The user interface will display one of three labels.

## High-Confidence AI Result ##

Likely AI-Generated

This content shows multiple characteristics commonly associated with AI-generated writing. Confidence Score: 0.60–1.00.

## High-Confidence Human Result ##

Likely Human-Written

This content shows multiple characteristics commonly associated with human-written writing. Confidence Score: 0.00–0.39.

## Uncertain Result ##

Mixed or Uncertain Origin

The available signals do not provide enough evidence to confidently classify this content as either human-written or AI-generated. Confidence Score: 0.40–0.59.


--- 

# Appeals Workflow #

## Who Can Submit an Appeal ##

Any creator whose content was analyzed by the system may submit an appeal.

## Information Required ##

The appeal form requires:

Submission ID (content_id)
Creator reasoning or explanation
Optional supporting notes

Example:

"I wrote this essay myself and believe the system incorrectly classified it."

## System Behavior ##

When an appeal is submitted:

The submission is marked as "under review."
An appeal record is created.
The creator reasoning is stored.
A timestamp is recorded.
An audit log entry is generated, logging the appeal alongside the original classification decision.

### Audit Log Example ###

Submission Created
Analysis Completed
Label Generated
Appeal Submitted
Status Updated to Under Review

## Reviewer View ##

A human reviewer would see:

Submission ID
Original text
LLM score
Stylometric score
Combined confidence score
Generated label
Creator reasoning
Submission timestamp
Appeal timestamp

This allows reviewers to understand both the system's reasoning and the creator's explanation.

---

# Anticipated Edge Cases #

## Edge Case 1: Poetry

A poem may intentionally use repetitive wording, simple vocabulary, and consistent sentence structures.

Because AI-generated text often exhibits similar patterns, the stylometric detector may incorrectly assign a high AI score even when the poem is entirely human-written.

## Edge Case 2: Professional Academic Writing ##

A student or researcher may produce highly polished, grammatically consistent writing with formal organization.

The LLM classifier may interpret this consistency as AI-like behavior, leading to a false positive despite the work being original.

## Edge Case 3: Heavily Edited AI Content ##

A user may generate text with an AI tool and then manually revise vocabulary, sentence lengths, and structure.

The stylometric features may appear more human-like, causing the system to underestimate AI involvement.

## Edge Case 4: Very Short Text ##

A submission containing only one or two sentences does not provide enough information for either detector to make a reliable judgment.

The system may return an "Uncertain" label because both signals have limited evidence available.

---

# Architecture #

## Architecture Narrative ##

The confidence scoring component receives the LLM score and stylometric score and combines them using a weighted average. The resulting confidence score ranges from 0.0 to 1.0 and represents the likelihood that the text is AI-generated. The transparency labeling component then maps this score into one of three categories: Likely Human-Written (0.00–0.39), Mixed or Uncertain Origin (0.40–0.59), or Likely AI-Generated (0.60–1.00).

The audit log stores the submission ID, timestamp, individual signal scores, combined confidence score, generated label, and any later appeal activity to provide transparency and accountability.

## Architecture Diagram ##

### SUBMISSION FLOW ###

User
 |
 v
POST /submit
 |
 v
Raw Text
 |
 +------------------------+
 |                        |
 v                        v
Groq LLM Detector    Stylometric Detector
 |                        |
 | LLM Score              | Heuristic Score
 +-----------+------------+
             |
             v
      Confidence Scoring
      (Weighted Average)
             |
             v
      Transparency Label
             |
             |
      +------+------+
      |             |
      v             v
   Audit Log     API Response
                    |
                    v
                  User


### APPEAL FLOW ###

User
 |
 v
POST /appeal
 |
 v
Submission ID + Reason
 |
 v
Appeal Processor
 |
 v
Status = Under Review
 |
 v
Audit Log Update
 |
 v
Reviewer Queue
 |
 v
Response

---

# AI Tool Plan #

## AI Tool Plan

This project will use AI-assisted development to accelerate implementation while maintaining human oversight. Before each milestone, I will provide the AI tool with the relevant sections of my planning document so that generated code aligns with the intended system architecture.

### Milestone 3: Submission Endpoint and First Detection Signal

#### Specification Sections Provided

* Detection Signals
* Architecture Narrative
* Submission Flow Diagram
* API Surface Definitions

#### What I Will Ask the AI Tool to Generate

* Flask application skeleton
* `POST /submit` endpoint
* Groq LLM classification function
* Basic request validation and JSON response structure

#### Verification Process

Before connecting the classifier to the endpoint, I will test the signal function independently using several sample inputs.

Test cases will include:

* Clearly human-written text
* Clearly AI-generated text
* Short text samples
* Long text samples

I will verify that:

* The function returns a score between 0 and 1
* No runtime errors occur
* Different inputs produce different scores
* The endpoint correctly accepts text and returns a structured response

---

### Milestone 4: Second Detection Signal and Confidence Scoring

#### Specification Sections Provided

* Detection Signals
* Uncertainty Representation
* Confidence Thresholds
* Submission Flow Diagram

#### What I Will Ask the AI Tool to Generate

* Stylometric heuristic detector
* Functions for calculating:

  * Sentence length variance
  * Type-token ratio
  * Punctuation density
* Confidence score calculation logic
* Weighted score combination function

#### Verification Process

I will test both signals separately and then test the combined scoring system.

I will verify that:

* Both detectors return values between 0 and 1
* The weighted average is calculated correctly
* Scores vary meaningfully between clearly AI-generated and clearly human-written writing
* Similar texts produce reasonably consistent results
* Edge cases such as short submissions do not crash the system

---

### Milestone 5: Production Layer and User-Facing Features

#### Specification Sections Provided

* Transparency Label Design
* Appeals Workflow
* Confidence Thresholds
* Architecture Diagram
* API Surface Definitions

#### What I Will Ask the AI Tool to Generate

* Transparency label generation logic
* Threshold-based classification logic
* `POST /appeal` endpoint
* Appeal status tracking
* Audit log integration
* Submission and appeal record models

#### Verification Process

I will test the complete workflow from submission through appeal.

I will verify that:

* All three transparency labels can be reached:

  * Likely Human-Written
  * Mixed or Uncertain Origin
  * Likely AI-Generated
* Confidence thresholds are applied correctly
* Submission records are stored properly
* Appeals create new audit log entries
* Appeal status changes to "under review"
* The appeal endpoint returns the expected response structure


---
