import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';

export const GuidePage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'questions' | 'extraction'>('questions');

  const tabStyle = (isActive: boolean) => ({
    padding: '0.75rem 1.5rem',
    cursor: 'pointer',
    backgroundColor: isActive ? 'var(--color-black)' : 'var(--color-white)',
    color: isActive ? 'var(--color-white)' : 'var(--color-black)',
    border: '2px solid var(--color-black)',
    fontWeight: 'bold',
    borderBottom: isActive ? 'none' : '2px solid var(--color-black)',
    marginBottom: '-2px',
    zIndex: isActive ? 1 : 0,
    position: 'relative' as const,
    borderTopLeftRadius: '4px',
    borderTopRightRadius: '4px',
  });

  return (
    <div className="brutalist-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>AI Guide</h2>
        <Button variant="secondary" onClick={() => navigate(-1)}>Back</Button>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2rem', borderBottom: '2px solid var(--color-black)' }}>
        <div style={tabStyle(activeTab === 'questions')} onClick={() => setActiveTab('questions')}>
          Make Questions
        </div>
        <div style={tabStyle(activeTab === 'extraction')} onClick={() => setActiveTab('extraction')}>
          Extract Lecture
        </div>
      </div>

      {activeTab === 'questions' && (
        <div>
          <h3>Make Questions (from PYQs)</h3>
          <p>Copy this prompt and paste it into ChatGPT/Claude along with your past year questions document.</p>
          <div style={{ backgroundColor: '#f0f0f0', padding: '1rem', border: '2px solid black', borderRadius: '4px', marginTop: '0.5rem' }}>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace' }}>
{`You are an expert academic data extraction agent. 
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
        "question": "...",
        "options": null,
        "answer": "..."
      }
    ]
  }
]`}
            </pre>
          </div>
        </div>
      )}

      {activeTab === 'extraction' && (
        <div>
          <h3>Extract Lecture (Bypass PDF Parsing)</h3>
          <p>You can run the extraction pipeline using web LLMs in 3 steps. Paste these prompts sequentially into the same chat.</p>
          
          <h4 style={{ marginTop: '1.5rem' }}>Step 1: Upload and Extract</h4>
          <div style={{ backgroundColor: '#f0f0f0', padding: '1rem', border: '2px solid black', borderRadius: '4px', marginTop: '0.5rem' }}>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace', fontSize: '0.85rem' }}>
{`You are an academic extraction agent. Your task is to clean and organize content from the attached lecture slide, generate a Section Map, and isolate the raw content for each section.

TASKS:
1. Clean Slide Content: Extract all academic text, formulas, and describe diagrams from the Target Slide. Organize it logically.
2. Context Gap Analysis: Identify if any concepts in the slide require prerequisites NOT found in the provided "Previous Context".
3. Section Map Generation: Segment the extracted content into ordered sections based on topics and subtopics.
4. Per-Section Content Isolation: For EACH section in the map, extract and populate its \`section_content\` field with the RAW content relevant to that section — including definitions, formulas, diagram descriptions, and slide references. Each section's content must be self-contained and exclude material belonging to other sections.

Return your findings in valid JSON format responding to this structure:
{
  "cleaned_content": "...",
  "prerequisite_gaps": ["..."],
  "section_map": [
    {
      "section_title": "...",
      "section_content": "...",
      "topics": ["..."],
      "subtopics": ["..."],
      "dependency_order": 1
    }
  ]
}`}
            </pre>
          </div>

          <h4 style={{ marginTop: '1.5rem' }}>Step 2: Extract Embedded Questions</h4>
          <div style={{ backgroundColor: '#f0f0f0', padding: '1rem', border: '2px solid black', borderRadius: '4px', marginTop: '0.5rem' }}>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace', fontSize: '0.85rem' }}>
{`You are a question extraction and classification agent. 
Using the JSON you just generated, perform the following two tasks:

TASK 1 — EXTRACTION:
Extract every practice question, worked example problem, or exercise embedded in the lecture slide itself.
For each question record:
  - "text": the full question text, verbatim
  - "source": "lecture slide"
  - "type": one of [numerical, conceptual, derivation, design, mcq]
  - "difficulty": one of [recall, understand, apply, analyse, evaluate]
  - "assumed_knowledge": list any concepts the question assumes the student already knows

TASK 2 — SECTION MAPPING:
For each extracted question, identify which section(s) from the section map it belongs to.
Assign:
  - "mapped_sections": list of section_title strings from the section map that this question is relevant to
  - "mapping_confidence": one of [high, medium, low]
  - "mapping_reason": one sentence explaining why

RULES:
- Do not paraphrase or modify questions during extraction. Preserve original wording exactly.
- If a question cannot be mapped to any section with confidence, set mapped_sections to [] and mapping_confidence to "low". Do not discard it.
- Do not invent questions. Extract only what is present in the slide.

OUTPUT FORMAT:
{
  "extracted_questions": [
    {
      "text": "...",
      "source": "lecture slide",
      "type": "...",
      "difficulty": "...",
      "assumed_knowledge": ["..."],
      "mapped_sections": ["..."],
      "mapping_confidence": "...",
      "mapping_reason": "..."
    }
  ]
}

Return valid JSON only.`}
            </pre>
          </div>

          <h4 style={{ marginTop: '1.5rem' }}>Step 3: Pedagogical Structuring</h4>
          <div style={{ backgroundColor: '#f0f0f0', padding: '1rem', border: '2px solid black', borderRadius: '4px', marginTop: '0.5rem' }}>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace', fontSize: '0.85rem' }}>
{`You are a curriculum designer. Your job is to read the extracted section map and the extracted questions, and annotate each section with pedagogical metadata.

FOR EACH SECTION, DETERMINE AND OUTPUT:

"learning_objectives": [2-4 statements in the form "Student can..."]
"teach_approach": Choose ONE: analogy_first | example_first | concept_first | problem_first
"opening_analogy": One concrete everyday-life analogy (no math/domain examples).
"prerequisite_bridge": {
  "needed": true/false,
  "covers": "...",
  "because": "..."
}
"key_misconceptions": [1-3 things students commonly get wrong about this topic.]
"notation_introduced": [ {"symbol": "...", "meaning": "..."} ]
"worked_example_required": true/false
"worked_example_spec": "If required: describe exactly what the example should show"
"question_prompts": {
  "recall":      "...",
  "understand":  "...",
  "apply":       "...",
  "analyse":     "...",
  "evaluate":    "..."
}
"extracted_questions": [Transfer any questions from the extracted_questions list that have THIS section's title in their "mapped_sections" list.]

CONSTRAINTS:
- Assume the student knows ONLY what appears in sections before this one.
- The opening_analogy must use everyday life, not domain examples.
- Every section must have question prompts at all five levels.
- prerequisite_bridge.needed should be true liberally.

OUTPUT: Return the full, finalized JSON object. It must have the \`section_map\` array where each section object now includes all of these new fields. Output ONLY valid JSON in a code block so I can download it.`}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
