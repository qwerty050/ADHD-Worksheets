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
          <p>You can run the extraction pipeline using web LLMs in 2 steps. Paste these prompts sequentially into the same chat, then paste the final JSON in the lecture upload page.</p>

          <h4 style={{ marginTop: '1.5rem' }}>Step 1: Section Map</h4>
          <div style={{ backgroundColor: '#f0f0f0', padding: '1rem', border: '2px solid black', borderRadius: '4px', marginTop: '0.5rem' }}>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace', fontSize: '0.85rem' }}>
{`You are an academic extraction agent. You receive the text of a lecture deck (the attached PDF) and produce a section map for a self-study worksheet.

TASKS:
1. Clean the content: keep all academic text and formulas. Where a page is mostly a diagram or figure, describe what it shows based only on the surrounding text and captions — never invent visual details.
2. Segment the material into ordered sections by topic. Merge trivial follow-on slides into their parent section; keep genuinely distinct topics apart. Typically 3-8 sections.
3. For EACH section, populate "section_content" with the RAW teaching material of that section — definitions, formulas, descriptions — excluding material that belongs to other sections. Section content must be self-contained.

OUTPUT — a single JSON object:
{"section_map": [
  {"section_title": "...",
   "section_content": "...",
   "topics": ["..."],
   "subtopics": ["..."],
   "dependency_order": 1}
]}
Return valid JSON only in a code block so I can download it.`}
            </pre>
          </div>

          <h4 style={{ marginTop: '1.5rem' }}>Step 2: Annotate Each Section</h4>
          <div style={{ backgroundColor: '#f0f0f0', padding: '1rem', border: '2px solid black', borderRadius: '4px', marginTop: '0.5rem' }}>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace', fontSize: '0.85rem' }}>
{`You are a curriculum designer. You do not write student-facing content. Using the section map you just produced, annotate EVERY section.

For each section, OUTPUT this JSON object (and repeat for all sections as a JSON array, in the same order):

{"section_title": "(copy exactly)",
 "learning_objectives": ["Student can ...", "..."],
 "key_misconceptions": ["...", "..."],
 "worked_example_spec": "...",
 "extracted_questions": [
   {"text": "...", "type": "numerical|conceptual|derivation|design|mcq",
    "difficulty": "recall|understand|apply|analyse|evaluate",
    "assumed_knowledge": ["..."]}
 ]}

RULES:
- 2-4 learning objectives, each achievable by a beginner reading only this section and the sections before it.
- 1-3 key misconceptions students commonly hold about this topic. Be specific.
- worked_example_spec: what a fully solved example should demonstrate. Empty string if purely conceptual.
- extracted_questions: every practice question or exercise embedded in that section's slides, verbatim. Do not paraphrase. Do not invent. Empty list if none.

The final output must be a JSON ARRAY — one object per section — each also containing the original fields (section_title, section_content, topics, subtopics, dependency_order) copied unchanged. Output ONLY valid JSON in a code block so I can download it.`}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
