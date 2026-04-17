# Multi-Agent Textbook Update System

## Overview
This project is a production-oriented multi-agent pipeline for updating textbooks with recent developments while preserving textbook structure and export quality.

The system:
- ingests textbooks from `PDF`, `Markdown`, `DOCX`, and `HTML`
- parses them into a structured `Book -> Chapter -> Section -> Block` model
- analyzes each chapter as a semantic unit
- retrieves and filters current research and web evidence
- maps accepted updates back to the most relevant textbook sections
- writes textbook-style addenda
- renders canonical Markdown plus optional `DOCX` and `PDF`
- saves per-run artifacts, prompt traces, export manifests, and a human review pack

The current implementation is no longer a simple MVP script. It is a layered pipeline with typed models, artifact persistence, multimodal parsing, structured rendering, regression tests, and editorial review outputs.

## Current Architecture
The repo is organized around pipeline responsibilities rather than a single `utils/` script flow.

```text
multi_agent_textbook_updater/
  agents/                Legacy-compatible research agents
  app/                   CLI and orchestration entrypoints
  core/                  Config, run context, console helpers, typed models, prompt metadata
  data/                  Sample inputs
  evaluations/           Parser and evaluation utilities
  ingestion/             Format parsers, normalization, validation, asset handling
  outputs/               Generated books, manifests, extracted assets, run artifacts
  rendering/             Canonical Markdown, DOCX, and PDF export
  research/              Explicit query planning and research-stage helpers
  review/                Human review pack generation
  schemas/               Legacy schema compatibility
  storage/               Artifact writing and output persistence
  tests/                 Regression, snapshot, multimodal, decision-quality, and export tests
  utils/                 Legacy compatibility modules still used by parts of the pipeline
  main.py                Thin entrypoint that delegates to the CLI
```

## Pipeline Flow
The active pipeline lives in [app/run_pipeline.py](./app/run_pipeline.py).

### 1. Ingestion
`ingestion/pipeline.py` selects a parser by file extension:
- `Markdown` via `ingestion/parsers/markdown_parser.py`
- `PDF` via `ingestion/parsers/pdf_parser.py`
- `DOCX` via `ingestion/parsers/docx_parser.py`
- `HTML` via `ingestion/parsers/html_parser.py`

### 2. Normalization and validation
After parsing, the book passes through:
- `ingestion/normalization/repair.py`
- `ingestion/normalization/validation.py`

This repairs weak section ids, inserts overview sections when needed, normalizes titles and content, and records structural warnings.

### 3. Chapter analysis
Each chapter is analyzed with `agents/chapter_analysis.py` to produce:
- summary
- key concepts
- likely outdated topics
- search-oriented context

### 4. Query planning
`research/query_planner.py` converts chapter understanding into explicit retrieval plans with:
- base queries
- refined queries
- reasoning summary

### 5. Retrieval
`agents/retrieval.py` fetches evidence from academic and web sources, normalizes URLs, applies credibility heuristics, and improves ranking quality.

### 6. Evidence extraction
`agents/evidence_extractor.py` turns raw retrieval results into candidate updates with structured fields.

### 7. Judging and filtering
`agents/judge.py` scores candidates on quality and relevance signals and rejects low-value updates.

### 8. Section mapping
`agents/section_mapper.py` maps accepted content back to textbook sections using section-aware matching and rationale generation.

### 9. Ranking and selection
`agents/ranker.py` performs final selection, limiting updates per chapter and preferring stronger, less redundant updates.

### 10. Writing
`agents/writer.py` produces textbook-style update prose suitable for insertion as chapter-end addenda.

### 11. Rendering and export
The pipeline renders canonical Markdown first, then optionally exports:
- `DOCX` via `rendering/docx_exporter.py`
- `PDF` via `rendering/pdf_exporter.py`

### 12. Review handoff
Each run can generate a review pack through `review/review_pack.py`:
- `review_pack.md`
- `review_pack.json`
- `review_queue.csv`

This gives a human reviewer a clean approval or revision surface instead of raw artifacts only.

## Document Model
The canonical document model is defined in [core/models/book.py](./core/models/book.py).

### Book hierarchy
- `Book`
- `Chapter`
- `Section`
- `Block`

### Block types currently supported
- `paragraph`
- `image`
- `caption`
- `table`
- `callout`

This means the system now preserves more than plain text. It can carry figures, captions, blockquote-style notes, and tables from ingestion through export.

## Parsing Capabilities

### Markdown
- parses chapter and section headings
- preserves local images
- preserves captions
- preserves Markdown tables
- preserves blockquote callouts
- falls back to an internal parser when the older strict parser would drop valid short books

### HTML
- preserves headings and paragraphs
- preserves images and `figcaption`
- preserves `blockquote` callouts
- preserves HTML tables

### DOCX
- preserves heading hierarchy
- extracts embedded images into `outputs/extracted_assets/...`
- walks paragraphs and tables in document order
- preserves tables as structured blocks
- preserves quote-style blocks as callouts when detectable

### PDF
- runs multiple parsing strategies and chooses the stronger result
- extracts images on a best-effort basis
- records strategy scores and parse warnings
- detects low-text or image-heavy pages
- flags `ocr_recommended` when the PDF appears scan-heavy

### Important PDF note
True OCR fallback is not yet active in this environment because OCR-specific dependencies are not installed. The system now detects likely scanned PDFs and reports that OCR is recommended instead of silently overtrusting a weak parse.

## Rendering and Output

### Canonical Markdown
Canonical Markdown is the primary render target and is generated by `rendering/markdown_renderer.py`.

It includes:
- book title
- table of contents
- chapter and section headings
- preserved images
- preserved tables
- preserved callouts
- chapter-end `Recent Advances` sections for accepted updates

### DOCX export
`rendering/docx_exporter.py` produces a styled `DOCX` with:
- title page
- export summary
- sectioned chapter content
- embedded images where available
- rendered tables
- styled callout paragraphs
- chapter-end update sections

### PDF export
`rendering/pdf_exporter.py` prefers `pandoc` when available and falls back to `xhtml2pdf`.

It also writes an export manifest so each run records:
- engine used
- success or failure
- output location
- notes when export fails

## Artifacts and Auditability
Every run writes structured artifacts under `outputs/artifacts/<run_id>/`.

Typical artifact contents include:
- parsed book JSON
- parse report JSON
- per-chapter analysis
- query plans
- retrieval results
- candidates
- accepted updates
- written updates
- prompt traces
- run summary
- export manifests
- review pack files

This makes the pipeline resumable in spirit, auditable, and easier to debug.

## Human Review Workflow
The review workflow is designed for editorial safety.

Each run can produce:
- `review/review_pack.md`
  - human-readable summary of parse quality, warnings, and accepted updates
- `review/review_pack.json`
  - machine-readable review payload
- `review/review_queue.csv`
  - editable sheet with `review_decision` and `review_notes` columns

Recommended workflow:
1. Run the pipeline.
2. Inspect the parse warnings and OCR recommendation if present.
3. Review accepted updates in `review_pack.md`.
4. Fill `review_queue.csv` with `approve`, `revise`, or `reject`.
5. Use reviewer notes to guide downstream editing or future automation.

## Prompt and Run Tracing
The system records prompt usage through:
- prompt name
- prompt version
- model chain
- structure mode
- cache hit status
- temperature

This information is saved to artifacts so prompt changes are inspectable across runs.

## CLI Usage
The main entrypoint is:

```bash
python main.py
```

Useful options:

```bash
python main.py --input-file data/sample.md --skip-pdf
python main.py --input-file data/sample.pdf --full-run
python main.py --input-file data/sample.docx --skip-review-pack
python main.py --input-file data/sample.html --chapter-limit 2
```

### CLI flags
- `--input-file`
- `--output-dir`
- `--chapter-limit`
- `--full-run`
- `--skip-pdf`
- `--skip-docx`
- `--skip-review-pack`

## Environment and Configuration
Settings are managed through [core/config.py](./core/config.py) and can be configured by environment variables.

Important settings include:
- `INPUT_FILE`
- `OUTPUT_DIR`
- `CANONICAL_MARKDOWN`
- `OUTPUT_PDF`
- `OUTPUT_DOCX`
- `ARTIFACT_DIR`
- `DEMO_MODE`
- `MAX_UPDATES_PER_CHAPTER`
- `RETRIEVAL_PREVIEW_LIMIT`
- `CHAPTER_LIMIT`
- `RENDER_PDF`
- `RENDER_DOCX`
- `GENERATE_REVIEW_PACK`
- `PANDOC_COMMAND`

## Installation

### 1. Clone the repo
```bash
git clone <your-repo-url>
cd multi_agent_textbook_updater
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
Create a `.env` file if you are using provider APIs such as the LLM backend.

Example:

```env
MISTRAL_API_KEY=your_api_key_here
```

## Dependencies
Core dependencies currently used include:
- `pydantic`
- `pdfplumber`
- `beautifulsoup4`
- `python-docx`
- `markdown`
- `xhtml2pdf`
- `sentence-transformers`
- `torch`
- `requests`
- `aiohttp`
- `diskcache`
- `Pillow`

## Testing
The regression suite covers parsing, rendering, export, decision quality, prompt tracing, multimodal preservation, and review-pack generation.

Run it with:

```bash
venv\Scripts\python.exe tests\run_tests.py
```

## Current Strengths
- typed core data model
- layered architecture
- multimodal parsing with images, tables, and callouts
- canonical Markdown-first publishing
- DOCX and PDF export
- prompt tracing
- artifact persistence
- regression tests
- human review pack generation

## Known Limitations
- full OCR fallback is not yet installed or active
- PDF table and figure placement remains best-effort
- no database-backed persistence yet
- no scheduler or version-diff workflow yet
- no dedicated UI or dashboard yet
- no automated loop yet that re-ingests reviewer decisions

## Highest-Value Next Steps
- install and wire real OCR fallback for scanned PDFs
- add table and figure placement improvements for difficult PDFs
- add reviewer-decision ingestion and approval gating
- add version tracking and scheduled reruns
- add optional database-backed persistence
- enable a stronger `pandoc` publishing path where available

## Output Files
Common outputs include:
- `outputs/updated_book.md`
- `outputs/updated_book.docx`
- `outputs/updated_book.pdf`
- `outputs/results.json`
- `outputs/extracted_assets/...`
- `outputs/artifacts/<run_id>/...`

## Status
This project has moved well beyond the original MVP shape. It now operates as a hardened multi-stage pipeline with structured ingestion, multimodal preservation, typed contracts, export traceability, and a human review layer.
