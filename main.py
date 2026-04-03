from utils.pdf_parser import parse_pdf
from utils.md_parser import parse_markdown
from agents.chapter_analysis import analyze_chapter
from agents.retrieval import retrieve_all
from utils.storage import save_results


def load_book(file_path):
    if file_path.endswith(".pdf"):
        return parse_pdf(file_path)
    elif file_path.endswith(".md"):
        return parse_markdown(file_path)
    else:
        raise ValueError("Unsupported file format")


def run():
    file_path = "data/sample.pdf"  # change to .md if needed

    book = load_book(file_path)

    all_results = []

    # 🔥 limit chapters for demo stability
    for ch in book.chapters[:1]:
        print("\n📘", ch.title)

        analysis = analyze_chapter(ch)

        # safety check
        if not analysis:
            print("⚠️ Analysis failed")
            continue

        print("\n📝 Summary:")
        print(analysis.get("summary", ""))

        print("\n🧠 Concepts:")
        print(analysis.get("key_concepts", []))

        print("\n🔍 Queries:")

        queries = analysis.get("search_queries", [])

        # limit queries (VERY IMPORTANT)
        for query in queries[:2]:
            print("-", query)

            print("🔍 Searching:", query)

            results = retrieve_all(query)
            all_results.extend(results)

    save_results(all_results)

    print("\n✅ Results saved successfully!")


if __name__ == "__main__":
    run()