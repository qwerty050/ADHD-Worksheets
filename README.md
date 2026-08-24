<div align="center">

# 🧠 ADHD Worksheets

**An intelligent educational pipeline that transforms standard lecture slides into completely self-sufficient, highly structured, and interactive learning worksheets.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js](https://img.shields.io/badge/Node.js-339933?style=flat&logo=nodedotjs&logoColor=white)]()
[![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)]()
[![Vite](https://img.shields.io/badge/Vite-B73BFE?style=flat&logo=vite&logoColor=FFD62E)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)]()
[![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()

*Do the worksheet, and you're done with the lecture.*

</div>

---

## 🎯 Why We Built This

The primary aim of this project is to **reduce distraction and cognitive load**. 

For many students, particularly those with neurodivergence or ADHD, the traditional study process involves juggling lecture slides, multiple reference books, online resources, and past exam papers. This constant context-switching is exhausting and severely hurts focus.

By combining the core material from a lecture with relevant context from reference books and actual Past Year Questions (PYQs), this application ensures that **everything a student needs to master a topic is contained in one place.**

---

## ✨ Key Benefits & Use Cases

- 🧩 **Self-Sufficient Modules**: The student only has to complete the generated worksheet. The topic will be thoroughly covered, integrating both the slide content and the broader context from reference books, alongside relevant PYQs for the specific topic.
- 🚫 **No More Context Switching**: Students no longer have to consult multiple books, repos, or AI chatbots to understand a topic. Everything is contextualized and presented sequentially.
- ✍️ **Learn by Applying**: The worksheets are predominantly question-based, actively scaffolding the student's understanding from basic recall to complex application. This drastically helps students who learn better by *applying* rather than rote learning.
- 🧠 **Neurodivergent Friendly**: Designed with ADHD in mind, the format breaks down intimidating walls of text into digestible, structured blocks with clear learning objectives, everyday analogies, and proactive misconception handling.
- 📱 **Tablet Ready**: The output is compiled into a clean, well-spaced LaTeX PDF format, perfectly optimized for use on iPads and tablets with digital pencils.

---

## ⚙️ How It Works (High Level)

The pipeline operates in three main steps:

### 1️⃣ Extraction (Understanding the Lecture)
The application reads your provided lecture slides (PDF) and breaks the content down into logical sections. It identifies the core topics, extracts any practice questions already embedded in the slides, and determines the best "pedagogical approach" (e.g., using an everyday analogy before showing a complex formula).

### 2️⃣ Memory Integration (Connecting the Dots)
Behind the scenes, a **Course Memory** database stores all your textbook chapters and past exam questions. As the application builds the worksheet, it queries this memory to pull in extra context from textbooks and relevant past questions (PYQs) that specifically match the current section. 

### 3️⃣ Generation (Building the Worksheet)
The application acts as a curriculum designer. For each section, it generates a structured theory breakdown (Motivation ➔ Intuition ➔ Formal Definition ➔ Worked Example) and a "ladder" of questions (Recall ➔ Understand ➔ Apply ➔ Analyse ➔ Evaluate). It then compiles this beautifully into a clean, tablet-ready PDF worksheet.

---

## 📅 A Student's Weekly Workflow

Here is how a student typically uses the pipeline over the course of a semester. You can run this process via our **Command Line Interface (CLI)** or through the included **local Web App (React + FastAPI)**.

1. 📥 **Gather Materials**: At the start of the course, gather past exam papers (PYQs), practice assignments, and reference textbooks.
2. 🤖 **Digitize Questions**: Using web chatbots (like Claude or ChatGPT) and our pre-written prompts, quickly convert raw PDFs of old exams into structured JSON files.
3. 🗄️ **Build the Knowledge Base**: Create your Course Memory (`course.cmkb`) and ingest the textbooks and structured PYQ files into it.
4. ⚙️ **Weekly Generation**: Every week, when a new lecture is released, run the lecture PDF through the generator (via CLI or the Web App UI) alongside your Knowledge Base.
5. 🔄 **Continuous Learning**: The pipeline produces that week's worksheet (pulling in relevant textbook excerpts and PYQs) and *automatically updates the Knowledge Base* with your progress. Next week's worksheet will organically remember what was already covered!

---

## 🚀 How to Run

### 1. Backend Setup
Create a virtual environment and install the required dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the Application
This project includes a fully-featured local Web App (React + FastAPI) that provides a user-friendly GUI to manage your workflow.

Start the FastAPI backend (in terminal 1):
```bash
uvicorn api.server:app --reload --port 8000
```

Start the React frontend (in terminal 2):
```bash
cd web
npm install
npm run dev
```
Then, open `http://localhost:5173` in your browser to create your knowledge base, upload lectures, and generate worksheets visually!

> **Prefer the Terminal?** If you want to run pipelines autonomously or prefer using the command line, check out the CLI instructions in [docs/usage.md](docs/usage.md).

---

## 📚 Documentation

For technical details, setup instructions, and CLI usage, refer to the documentation:

* 🚀 **[Installation Guide](docs/installation.md)**: How to set up the environment and models.
* 💻 **[Usage Guide](docs/usage.md)**: How to use the CLI to generate worksheets and manage the memory store.
* 🏗️ **[Pipeline Architecture](docs/pipeline.md)**: A deeper dive into the technical stages of extraction and generation.
* 📋 **[Pedagogical Schema](docs/PEDAGOGICAL_JSON_SCHEMA.md)**: The underlying JSON contract used to structure the teaching modules.
* 🤖 **[Chatbot Lecture Extraction](docs/chatbot_workflow.md)**: How to use external LLMs to extract pedagogical JSON from lectures.
* 📝 **[Chatbot PYQ Extraction](docs/pyq_chatbot_workflow.md)**: How to use external LLMs to extract and format Past Year Questions for memory ingestion.

---

## 🙏 Credits

This project utilizes **PageIndex** for semantic processing and indexing of PDFs in the Course Memory Knowledge Base.
- **GitHub**: [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex)
- **Website**: [pageindex.ai](http://pageindex.ai/)
