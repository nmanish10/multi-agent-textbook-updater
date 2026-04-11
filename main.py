from utils.pdf_parser import parse_pdf
from utils.md_parser import parse_markdown
from agents.chapter_analysis import analyze_chapter
from agents.retrieval import retrieve_all
from agents.evidence_extractor import extract_evidence
from agents.judge import judge_candidates
from agents.ranker import rank_and_select
from agents.section_mapper import map_to_sections
from utils.storage import save_results
from agents.writer import write_updates
from utils.textbook_updater import update_textbook_md
from utils.pdf_generator import generate_pdf

def load_book(file_path):
    if file_path.endswith(".pdf"):
        return parse_pdf(file_path)
    elif file_path.endswith(".md"):
        return parse_markdown(file_path)
    else:
        raise ValueError("Unsupported file format")

def refine_query(query, concepts):
    # inject concepts into query
    concept_str = ", ".join(concepts[:3])
    return f"{query} focusing on {concept_str}"

def run():
    file_path = "data/sample.pdf"  # change if needed

    book = load_book(file_path)

    all_results = []

    # 🔥 DEMO MODE: only 1 chapter
    for ch in book.chapters[:1]:
        print("\n📘", ch.title)

        # -------------------------
        # CHAPTER ANALYSIS
        # -------------------------
        analysis = analyze_chapter(ch)

        if not analysis:
            print("⚠️ Analysis failed")
            continue

        print("\n📝 Summary:")
        print(analysis.get("summary", ""))

        print("\n🧠 Concepts:")
        print(analysis.get("key_concepts", []))

        # -------------------------
        # LIMIT QUERIES (DEMO)
        # -------------------------
        queries = analysis.get("search_queries", [])[:1]

        for query in queries:
            query = refine_query(query, analysis.get("key_concepts", []))
            print("\n🔍 Query:", query)

            # -------------------------
            # RETRIEVAL
            # -------------------------
            results = retrieve_all(query)

            # 🔥 limit results (VERY IMPORTANT)
            results = results[:5]

            print(f"📥 Retrieved: {len(results)} items")

            # -------------------------
            # EVIDENCE EXTRACTION
            # -------------------------
            candidates = extract_evidence(analysis, results)
            print(f"🧾 Candidates: {len(candidates)}")

            # -------------------------
            # JUDGE
            # -------------------------
            judged = judge_candidates(analysis, candidates)
            print(f"✅ Accepted: {len(judged)}")

            # -------------------------
            # RANKING
            # -------------------------
            top_updates = rank_and_select(judged)
            print(f"🏆 Top Updates: {len(top_updates)}")

            if not top_updates:
                print("⚠️ No strong updates found for this chapter")
                continue

            # -------------------------
            # SECTION MAPPING
            # -------------------------
            mapped_updates = map_to_sections(ch, top_updates)
            
            written_updates = write_updates(ch, mapped_updates)

            print("\n📘 Final Textbook Updates:\n")

            for upd in written_updates:
                print(f"Section {upd['section_id']}\n")
                print(upd["text"])
                print("\n---\n")

            all_results.extend(written_updates)

    # -------------------------
    # SAVE OUTPUT
    # -------------------------
    # save structured JSON (optional)
    save_results(all_results)
    
    # 🔥 NEW: update textbook
    update_textbook_md(book, all_results)

    # 🔥 NEW: generate PDF
    generate_pdf(book, all_results)
    print("\n✅ Demo run completed successfully!")


if __name__ == "__main__":
    run()