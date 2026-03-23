import os
import json
from pathlib import Path

# --- CONFIGURATION ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODELS = {
    "pro": "gpt-oss:120b-cloud",
    "flash": "gpt-oss:120b-cloud",
    "flashLite": "gpt-oss:120b-cloud"
}

SYSTEM_PROMPT_GLOBAL_EXTRACTION = """
You are an academic extraction agent. Your task is to clean and organize content from lecture slides and supporting documents, generate a Section Map, and isolate the raw content for each section.

TASKS:
1. Clean Slide Content: Extract all academic text, formulas, and describe diagrams from the Target Slide. Organize it logically.
2. Context Gap Analysis: Identify if any concepts in the slide require prerequisites NOT found in the provided "Previous Context".
3. Section Map Generation: Segment the extracted content into ordered sections based on topics and subtopics.
4. Per-Section Content Isolation: For EACH section in the map, extract and populate its `section_content` field with the RAW content relevant to that section — including definitions, formulas, diagram descriptions, and slide references. Each section's content must be self-contained and exclude material belonging to other sections.

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
  ],
  "extracted_pyqs": []
}
"""

def read_file_content(path: Path) -> str:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        return f"[Cannot decode {path.name} as text. Assuming binary/image file. You may need an OCR/PDF extraction library locally before passing to Ollama.]"

source_folder = Path("src")
target_slide = source_folder / "W5M1.pdf"
supporting_folder = source_folder / "supporting"
context_folder = source_folder / "context"

supporting_docs = list(supporting_folder.rglob("*.*")) if supporting_folder.exists() else list(source_folder.glob("support*.*"))
context_files = list(context_folder.rglob("*.*")) if context_folder.exists() else list(source_folder.glob("context*.*"))

prompt_parts = [f"Target Slide Content:\n{read_file_content(target_slide)}\n"]

if context_files:
    prompt_parts.append("--- PREVIOUS CONTEXT ---")
    for f in context_files:
        prompt_parts.append(read_file_content(f))

if supporting_docs:
    prompt_parts.append("--- SUPPORTING DOCS ---")
    for f in supporting_docs:
        prompt_parts.append(read_file_content(f))

combined_prompt = "\n".join(prompt_parts)

payload = {
    "model": MODELS["pro"],
    "prompt": combined_prompt,
    "system": SYSTEM_PROMPT_GLOBAL_EXTRACTION,
    "stream": False,
    "format": "json"
}

import requests

try:
    response = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
    print("Status:", response.status_code)
    try:
        print("Text:", response.text)
    except:
        pass
except Exception as e:
    print("Error:", e)
