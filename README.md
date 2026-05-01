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
  frontend/              Next.js reader and admin UI shell
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
The new service wrapper lives in [app/api.py](./app/api.py).

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
`agents/retrieval.py` fetches evidence from academic and web sources, including an official-source lane for standards, benchmark owners, and major AI labs.

Retrieval now combines:
- source normalization and URL canonicalization
- official-source discovery for sources such as OpenAI, Google DeepMind, Meta AI, NIST, and IEEE
- optional Semantic Scholar enrichment for author h-index style metadata and citation velocity support
- a multi-signal credibility model using venue quality, author signal, recency, citation velocity, and source channel
- lexical and embedding-aware reranking with graceful fallback when the embedding model is unavailable

### 6. Evidence extraction
`agents/evidence_extractor.py` turns raw retrieval results into candidate updates with structured fields.

### 7. Judging and filtering
`agents/judge.py` scores candidates on quality and relevance signals and rejects low-value updates.

### 8. Section mapping
`agents/section_mapper.py` maps accepted content back to textbook sections using a hybrid strategy:
- semantic similarity when embeddings are available
- token overlap
- title overlap
- LLM fallback only when heuristic confidence is weak

### 9. Ranking and selection
`agents/ranker.py` performs final selection in two layers:
- per-run ranking to keep only the strongest updates for the current chapter pass
- competitive replacement against previously accepted chapter updates, so each chapter maintains a capped, curated update set over time instead of accumulating forever

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

### 13. Persistent chapter update store
`storage/update_store.py` keeps surviving updates per book and per chapter.

This enables:
- competitive replacement across runs
- curated chapter update thresholds
- replacement audit trails
- rendering a "living textbook" from the best surviving updates, not just the latest run

### 14. Review decision ingestion
Reviewer decisions can be re-applied through `review/decision_ingest.py`, which turns `review_queue.csv` into:
- an approval summary
- approved and pending update JSON files
- approved Markdown, DOCX, and PDF textbook exports

### 15. Admin configuration and scheduling
Persistent admin settings now live in `outputs/admin/` and are managed through `storage/admin_config_store.py`.

This layer currently provides:
- persisted admin configuration
- threshold control for acceptance and chapter update caps
- source enablement control
- bounded chapter-level parallelism control
- scheduling metadata with `daily`, `weekly`, `monthly`, or `manual`
- scheduler state with `last_run_utc`, `next_run_utc`, and due-now evaluation
- audit logging for config changes

### 16. Run history and version tracking
Run history is now persisted in `outputs/admin/run_history.json` through `storage/run_history_store.py`.

Each run records:
- run id
- book key and title
- input fingerprint
- output locations
- aggregate run stats
- applied admin config
- version delta against the previous run for the same book

This gives the system a lightweight version-tracking ledger so you can see whether the input changed, whether admin configuration changed, and how accepted/final update counts moved across runs. Together with scheduler state, it also gives the repo an operational basis for due-run execution instead of config-only scheduling.

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
- can run an optional OCR fallback strategy when `OCR_ENABLED=true` and the OCR runtime is installed

### Important PDF note
OCR fallback is optional. If OCR dependencies are not installed, the system still detects likely scanned PDFs and reports that OCR is recommended instead of silently overtrusting a weak parse.

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
- replacement audit files
- prompt traces
- run summary
- export manifests
- review pack files

The persistent chapter update store lives separately under `outputs/update_store/` and records which updates survived or were replaced across runs.
Run-level history and version deltas are also recorded in `outputs/admin/run_history.json`.

This makes the pipeline auditable, easier to debug, and much closer to a resumable living-update system.

## Logging and Observability
The pipeline now uses structured logging through [core/logging.py](./core/logging.py).

It records:
- run start and completion
- per-chapter progress
- retrieval activity and counts
- export outcomes
- timing information for major steps

This is a big step up from ad hoc `print()`-based debugging and makes later operational work much easier.

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
5. Apply the decisions with:

```bash
python main.py --apply-review-queue outputs/artifacts/<run_id>/review/review_queue.csv --review-run-dir outputs/artifacts/<run_id>
```

6. Use reviewer notes to guide downstream editing or future automation.

Applying review decisions produces:
- `review/review_decision_summary.json`
- `review/approved_updates.json`
- `review/pending_review_updates.json`
- `review/approved_book.md`
- `review/approved_book.docx`
- `review/approved_book.pdf`
- export manifests for the approved DOCX and PDF paths

This is now the recommended publication path when a human review step is part of your workflow: only approved updates are promoted into the gated exports.

## Prompt and Run Tracing
The system records prompt usage through:
- prompt name
- prompt version
- model chain
- structure mode
- cache hit status
- temperature

This information is saved to artifacts so prompt changes are inspectable across runs.

Prompt definitions are now externalized under [prompts/](./prompts/) and loaded through [core/prompts.py](./core/prompts.py). This makes prompt edits, versioning, and future experiment workflows much easier without burying long prompt strings inside agent files.

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
python main.py --apply-review-queue outputs/artifacts/<run_id>/review/review_queue.csv --review-run-dir outputs/artifacts/<run_id>
python main.py --apply-review-queue outputs/artifacts/<run_id>/review/review_queue.csv --review-run-dir outputs/artifacts/<run_id> --approved-docx outputs/approved.docx --approved-pdf outputs/approved.pdf
python main.py --show-admin-config
python main.py --show-schedule
python main.py --show-run-history
python main.py --run-if-due
python main.py --set-update-frequency weekly --set-chapter-parallelism 3 --set-max-updates-per-chapter 4 --set-enabled-sources openalex,arxiv,official,semantic_scholar
```

### CLI flags
- `--input-file`
- `--output-dir`
- `--chapter-limit`
- `--full-run`
- `--skip-pdf`
- `--skip-docx`
- `--skip-review-pack`
- `--apply-review-queue`
- `--review-run-dir`
- `--approved-markdown`
- `--approved-docx`
- `--approved-pdf`
- `--skip-approved-docx`
- `--skip-approved-pdf`
- `--show-admin-config`
- `--show-schedule`
- `--show-run-history`
- `--run-if-due`
- `--set-update-frequency`
- `--set-chapter-parallelism`
- `--set-max-updates-per-chapter`
- `--set-max-total-updates-per-chapter`
- `--set-min-accept-score`
- `--set-min-relevance`
- `--set-min-credibility`
- `--set-min-significance`
- `--set-enabled-sources`
- `--disable-pdf`
- `--disable-docx`
- `--disable-review-pack`

## API Usage
The project now also exposes a small FastAPI service layer in [app/api.py](./app/api.py). This is the backend contract intended for a future Next.js reader/admin UI.

Example local launch:

```bash
uvicorn app.api:create_app --factory --reload
```

Current endpoints include:
- `GET /api/health`
- `GET /api/admin/config`
- `PUT /api/admin/config`
- `GET /api/admin/schedule`
- `GET /api/admin/run-history`
- `POST /api/books/upload`
- `GET /api/books`
- `GET /api/books/{book_key}`
- `GET /api/books/{book_key}/chapters`
- `GET /api/books/{book_key}/chapters/{chapter_id}`
- `GET /api/books/{book_key}/updates`
- `GET /api/review/runs`
- `GET /api/review/runs/{run_id}`
- `POST /api/review/runs/{run_id}/apply`
- `POST /api/pipeline/run`

This does not replace the CLI. It wraps the same stores and pipeline so the system can be driven either from scripts or from a UI/client app.

## Frontend Usage
A first-pass Next.js platform shell now lives in [frontend/](./frontend/). It is designed to sit on top of the FastAPI layer and currently provides:
- browser-side textbook upload
- a library view for tracked books
- a book overview with TOC-style chapter cards
- a chapter deep-read route with recovered section text and inline accepted updates
- an admin panel for schedule, thresholds, and run history
- browser-side admin actions for saving config and triggering runs
- browser-side review queue editing and approval application
- review context panels showing original textbook section context beside the proposed update

The frontend expects the API to be reachable at `NEXT_PUBLIC_API_BASE_URL`, which defaults to `http://127.0.0.1:8000`.
The API now also enables local browser access by default for `http://127.0.0.1:3000` and `http://localhost:3000`. You can override this with `API_CORS_ORIGINS`.

Example local startup:

```bash
# terminal 1
venv\Scripts\python.exe -m uvicorn app.api:create_app --factory --reload

# terminal 2
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` for the UI.

## Environment and Configuration
Settings are managed through [core/config.py](./core/config.py) and can be configured by environment variables.

Important settings include:
- `INPUT_FILE`
- `OUTPUT_DIR`
- `CANONICAL_MARKDOWN`
- `OUTPUT_PDF`
- `OUTPUT_DOCX`
- `ARTIFACT_DIR`
- `UPDATE_STORE_DIR`
- `ADMIN_CONFIG_PATH`
- `ADMIN_AUDIT_LOG_PATH`
- `SCHEDULER_STATE_PATH`
- `RUN_HISTORY_PATH`
- `DEMO_MODE`
- `MAX_UPDATES_PER_CHAPTER`
- `MAX_TOTAL_UPDATES_PER_CHAPTER`
- `MIN_ACCEPT_SCORE`
- `MIN_RELEVANCE`
- `MIN_CREDIBILITY`
- `MIN_SIGNIFICANCE`
- `CHAPTER_PARALLELISM`
- `ENABLED_SOURCES`
- `RETRIEVAL_PREVIEW_LIMIT`
- `CHAPTER_LIMIT`
- `RENDER_PDF`
- `RENDER_DOCX`
- `GENERATE_REVIEW_PACK`
- `PANDOC_COMMAND`
- `OCR_ENABLED`
- `TESSERACT_CMD`
- `POPPLER_PATH`

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
MAX_UPDATES_PER_CHAPTER=3
MAX_TOTAL_UPDATES_PER_CHAPTER=5
MIN_ACCEPT_SCORE=0.78
MIN_RELEVANCE=0.75
MIN_CREDIBILITY=0.70
MIN_SIGNIFICANCE=0.65
CHAPTER_PARALLELISM=1
ENABLED_SOURCES=openalex,arxiv,web,official
SEMANTIC_SCHOLAR_API_KEY=
SCHEDULER_STATE_PATH=outputs/admin/scheduler_state.json
RUN_HISTORY_PATH=outputs/admin/run_history.json
OCR_ENABLED=false
TESSERACT_CMD=
POPPLER_PATH=
```

## Dependencies
Core dependencies currently used include:
- `pydantic`
- `fastapi`
- `uvicorn`
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

## OCR Setup
True OCR fallback still requires system tooling plus Python bindings. On Windows, the recommended install path is:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
winget install --id oschwartz10612.Poppler -e
venv\Scripts\python.exe -m pip install pytesseract pdf2image PyMuPDF
```

If `winget` is not available, install Tesseract manually and add its install directory to `PATH`. Poppler is recommended for rasterizing PDF pages during OCR fallback workflows.

## Testing
The regression suite covers parsing, rendering, export, decision quality, prompt tracing, multimodal preservation, competitive replacement, OCR fallback, and review workflows.

Run it with:

```bash
venv\Scripts\python.exe tests\run_tests.py
```

## Current Strengths
- typed core data model
- layered architecture
- API service layer
- reader/admin frontend shell
- multimodal parsing with images, tables, and callouts
- multi-strategy PDF parsing with OCR-aware scan detection
- canonical Markdown-first publishing
- official-source aware retrieval
- optional Semantic Scholar metadata enrichment
- multi-signal credibility scoring
- hybrid embedding-aware section mapping
- persistent chapter update storage with competitive replacement
- bounded async chapter-level parallelism
- DOCX and PDF export
- structured logging
- prompt tracing
- artifact persistence
- regression tests
- human review pack generation
- review-decision ingestion

## Known Limitations
- PDF table and figure placement remains best-effort
- no automatic background scheduler daemon yet, only persisted due-run helpers
- version tracking is currently ledger-based, not a full structural textbook diff workflow
- no dedicated UI or dashboard yet

## Highest-Value Next Steps
- deepen PDF structure recovery with font-aware headings and TOC-guided reconstruction
- add background scheduling execution and deeper textbook diff workflows
- deepen the Next.js Learning Platform UI with write actions, review controls, and richer reader interactions

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
