# 📘 Multi-Agent Textbook Update System

## 🚀 Overview
This project implements a **multi-agent pipeline** that reads textbook chapters, analyzes them, and retrieves relevant recent developments from academic and web sources.

The goal is to simulate a system that can **augment textbooks with updated knowledge**.

---

## 🧠 Features Implemented (Week 1 + Week 2)

### ✅ 1. Document Ingestion
- Parses PDF and Markdown textbooks
- Extracts:
  - Chapters
  - Sections
  - Content structure

### ✅ 2. Chapter Understanding Agent
- Generates:
  - Chapter summary
  - Key concepts
  - Search queries

### ✅ 3. Retrieval Pipeline
- Academic search (Semantic Scholar API)
- Web search (simulated)
- Returns structured JSON results

### ✅ 4. Structured Output
- Saves results in `outputs/results.json`

---

## 📂 Project Structure

```

multi_agent_textbook_updater/
│
├── agents/
│   ├── chapter_analysis.py
│   ├── retrieval.py
│
├── utils/
│   ├── pdf_parser.py
│   ├── md_parser.py
│   ├── llm.py
│   ├── storage.py
│
├── schemas/
│   ├── schemas.py
│
├── data/
│   ├── sample.pdf
│   ├── sample.md
│
├── outputs/
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

Create a `.env` file in the root directory:

```
MISTRAL_API_KEY=your_api_key_here
```

---

### 4️⃣ Run the Project

```bash
python main.py
```

---

## 📊 Example Output

```
📘 Chapter 8 / Intrusion Detection

📝 Summary:
...

🧠 Concepts:
...

🔍 Queries:
...

```

Results are saved in:

```
outputs/results.json
```

---

## ⚠️ Notes

* Academic API may return **429 (rate limit)** → system will still continue using web results
* Queries are limited to avoid API overload
* Currently operates at **chapter level**
* Section-level mapping and scoring are planned for next phases

---

## 🛠 Tech Stack

* Python
* pdfplumber (PDF parsing)
* Mistral API (LLM)
* Semantic Scholar API (academic search)

---

## 📌 Future Work

* Scoring and filtering updates
* Section mapping
* Ranking top updates
* Markdown output generation

---

## 👥 Team

* Multi-Agent Textbook Update System Project