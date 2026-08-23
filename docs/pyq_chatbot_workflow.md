# Extracting PYQs using Chatbots (Claude / ChatGPT / Gemini)

In addition to extracting lecture structure, you can use web-based LLMs (like **Claude 3.5 Sonnet**, **ChatGPT (GPT-4o)**, or **Gemini 1.5 Pro**) to rapidly digitize Past Year Questions (PYQs), quizzes, or practice tests into the exact JSON format required by the Course Memory Knowledge Base (CMKB).

Once you have this JSON, you can easily ingest it using the `memory ingest questions` CLI command.

## Workflow

1. **Upload** your exam PDF, quiz document, or assignment to the chatbot interface.
2. **Paste the Extraction Prompt** (provided below).
3. **Download** the resulting JSON file.
4. **Ingest** it into your memory store.

---

### Step 1: The Extraction Prompt

Copy and paste the following prompt along with your uploaded document:

```text
You are an expert academic data extraction agent. 
I have attached a document containing an exam, quiz, or practice test. 

Your task is to extract every single question from this document and format it into a specific JSON schema.

RULES:
1. Identify the name of the exam or test (e.g., "Endsem Monsoon 2023"). If it is not explicitly stated, infer a reasonable title or use "Practice Questions".
2. For each question, extract the question text verbatim.
3. If the question has multiple choice options (A, B, C, D, etc.), extract them into a nested "options" object. If there are no options, set "options" to null.
4. If an answer key or solution is provided, extract it into the "answer" field. If no answer is provided, leave it as an empty string "".
5. Maintain all mathematical notation or formulas as accurately as possible.

OUTPUT FORMAT:
Output ONLY valid JSON in a code block so I can download it. The JSON must strictly match this structure:

[
  {
    "exam": "Endsem Monsoon 2023",
    "questions": [
      {
        "id": 1,
        "question": "In the context of batch learning in neural networks, does the order in which input data is presented to the network influence the learning process?",
        "options": {
          "A": "Yes, the order significantly affects learning, leading to different models.",
          "B": "No, the order of input data does not influence the learning outcome in batch learning.",
          "C": "Yes, but only in networks with more than three layers.",
          "D": "The order only matters in real-time data streaming, not in batch learning."
        },
        "answer": "(B) No, the order of input data does not influence the learning outcome in batch learning."
      },
      {
        "id": 2,
        "question": "Prove that approximately 63% of the entire original dataset is present in any of the sampled bootstrap datasets using the Bagging method.",
        "options": null,
        "answer": "Probability of an observation not being chosen in one draw is 1 − 1/n. As n → ∞, this limit is e^−1 ≈ 0.368. Probability of appearing is 1 − 0.368 = 0.632."
      }
    ]
  }
]
```

### Step 2: Ingest the JSON

Once the chatbot generates the JSON, save it as a file (e.g., `exams.json`). 

You can then ingest these questions into your Course Memory Knowledge Base (CMKB) so the generation pipeline can automatically query and adapt them for your worksheets.

Run the following command:

```bash
python main_cli.py memory ingest questions course.cmkb exams.json
```

After ingestion, you should run the cluster command to ensure these new questions are semantically indexed and ready for retrieval:

```bash
python main_cli.py memory cluster course.cmkb
```

Your Past Year Questions are now part of the memory store!
