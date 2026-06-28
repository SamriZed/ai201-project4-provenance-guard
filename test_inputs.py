"""Run your own test inputs through /submit and print the results.

Edit the TEST_INPUTS list below with your own (label, text, creator_id) cases,
then run from the project root:

    python test_inputs.py

Uses Flask's test client, so you do NOT need the server running separately.
(It still calls the Groq API, so GROQ_API_KEY must be set in .env.)
"""

import submit_stub

# --- Put your test inputs here ------------------------------------------------
TEST_INPUTS = [
    {
        "label": "example 1",
        "creator_id": "test-user-1",
        "text": "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment.",
    },
    {
        "label": "example 2",
        "creator_id": "test-user-1",
        "text": "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there",
    },
    {
        "label": "example 3",
        "creator_id": "test-user-1",
        "text": "The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations.",
    },
    {
        "label": "example 4",
        "creator_id": "test-user-1",
        "text": "I've been thinking a lot about remote work lately. There are genuine tradeoffs — flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivity varies widely by individual and role type.",
    },
    
]
# -----------------------------------------------------------------------------


def main():
    client = submit_stub.app.test_client()

    for case in TEST_INPUTS:
        response = client.post(
            "/submit",
            json={"text": case["text"], "creator_id": case["creator_id"]},
        )
        data = response.get_json()

        print(f"\n=== {case.get('label', 'input')} ===")
        if response.status_code != 200:
            print(f"  ERROR {response.status_code}: {data}")
            continue

        print(f"  content_id:  {data['content_id']}")
        print(f"  llm_score:   {data['llm_score']}")
        print(f"  stylo_score: {data['stylometric_score']}")
        print(f"  confidence:  {data['confidence_score']}")
        print(f"  label:       {data['label']}")


if __name__ == "__main__":
    main()
