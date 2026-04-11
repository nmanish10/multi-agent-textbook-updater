# 📘 Multi-Agent Textbook Update System

## 🚀 Overview
This project implements a **multi-agent pipeline** that reads textbook chapters, analyzes them, retrieves recent research developments, and **appends meaningful updates to the end of each chapter**.

The system is designed to:
- Understand chapters holistically
- Identify relevant modern developments
- Filter and rank high-quality updates
- Generate textbook-style addenda

---

## 🧠 Current System Capabilities (MVP Complete)

### ✅ 1. Document Ingestion
- Supports:
  - PDF (via pdfplumber)
  - Markdown (.md)
- Extracts:
  - Chapters
  - Sections
  - Structured content hierarchy

---

### ✅ 2. Chapter Understanding Agent
- Generates:
  - Chapter summary
  - Key concepts
  - Research-oriented search queries

---

### ✅ 3. Retrieval Pipeline (UPDATED)
- Academic sources:
  - OpenAlex API
  - arXiv API
- Web fallback:
  - DuckDuckGo scraping
- Handles:
  - API failures
  - Timeouts
  - Deduplication (basic)

---

### ✅ 4. Evidence Extraction Agent
- Converts raw results into structured updates
- Extracts:
  - What changed
  - Why it matters
  - Supporting evidence

---

### ✅ 5. Relevance & Quality Judge Agent
- Scores each candidate on:
  - Relevance
  - Significance
  - Credibility
  - Novelty
  - Pedagogical fit
- Applies strict filtering thresholds

---

### ✅ 6. Ranking Agent
- Selects **top 3 updates per chapter**
- Removes weaker or redundant updates

---

### ✅ 7. Section Mapping Agent
- Maps updates to most relevant section
- Enables:
  - Structured numbering (e.g., 1.3.1, 1.3.2)

---

### ✅ 8. Update Writer Agent
- Generates **textbook-style content**
- Produces:
  - Subsection title
  - 2-paragraph academic explanation
  - References

---

### ✅ 9. Renderer / Export
- Outputs:
  - Updated Markdown textbook
  - Generated PDF version
- Updates are:
  - Appended at end of chapter
  - Properly numbered and structured

---

## 📂 Project Structure

```

multi_agent_textbook_updater/
│
├── agents/
│   ├── chapter_analysis.py
│   ├── retrieval.py
│   ├── evidence_extractor.py
│   ├── judge.py
│   ├── ranker.py
│   ├── section_mapper.py
│   ├── writer.py
│
├── utils/
│   ├── pdf_parser.py
│   ├── md_parser.py
│   ├── llm.py
│   ├── storage.py
│   ├── textbook_updater.py
│   ├── pdf_generator.py
│
├── schemas/
│   ├── schemas.py
│
├── data/
│   ├── sample.pdf
│   ├── sample.md
│
├── outputs/
│   ├── results.json
│   ├── updated_book.md
│   ├── updated_book.pdf
│
├── main.py
├── requirements.txt
├── README.md

````

---

## ⚙️ Setup Instructions

### 1️⃣ Clone the Repository
```bash
git clone <your-repo-url>
cd multi_agent_textbook_updater
````

---

### 2️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 3️⃣ Add API Key

Create a `.env` file:

```
MISTRAL_API_KEY=your_api_key_here
```

---

### 4️⃣ Run the Project

```bash
python main.py
```

---

## 📊 Output Example

```
📘 Chapter 1: Foundations of AI

📝 Summary:
...

🧠 Concepts:
...

🔍 Query:
...

📊 Candidate Scores:
...

🏆 Top Updates:
...

📘 Final Textbook Updates:
...
```

---

## 📄 Generated Outputs

* `outputs/results.json` → structured pipeline data
* `outputs/updated_book.md` → updated textbook
* `outputs/updated_book.pdf` → rendered PDF

---

## ⚠️ Notes

* Max **3 updates per chapter**
* Strict filtering ensures:

  * no weak updates
  * no noise
* System may return **0 updates** if nothing strong is found
* LLM fallback ensures robustness

---

## 🛠 Tech Stack

* Python
* pdfplumber (PDF parsing)
* Mistral API (LLM)
* OpenAlex API (academic search)
* arXiv API (latest research)
* DuckDuckGo (web fallback)
* ReportLab (PDF generation)

---

## 📌 Next Steps (Future Work)

* Better deduplication across sources
* Stronger section mapping (embeddings)
* UI for course-based textbook updates
* Scheduled updates / version tracking
* Domain-specific search optimization

---

## 👥 Team

Multi-Agent Textbook Update System Project
