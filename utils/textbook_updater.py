from collections import defaultdict


def update_textbook_md(book, updates, output_file="outputs/updated_book.md"):

    with open(output_file, "w", encoding="utf-8") as f:

        f.write(f"# {book.book_title}\n\n")

        for chapter in book.chapters:

            # -------------------------
            # CHAPTER TITLE
            # -------------------------
            title = chapter.title
            if not title.lower().startswith("chapter"):
                title = f"Chapter {chapter.chapter_id}: {title}"

            f.write(f"# {title}\n\n")

            # -------------------------
            # ORIGINAL CONTENT
            # -------------------------
            for section in chapter.sections:
                f.write(f"## {section.section_id} {section.title}\n\n")
                f.write(section.content + "\n\n")

            # -------------------------
            # FILTER UPDATES
            # -------------------------
            chapter_updates = [
                u for u in updates
                if u.get("section_id", "").startswith(chapter.chapter_id)
            ]

            if not chapter_updates:
                continue

            # -------------------------
            # NUMBERING (SECTION-BASED)
            # -------------------------
            section_counts = defaultdict(int)

            f.write("\n---\n\n")
            f.write(f"## Chapter {chapter.chapter_id} Updates\n\n")

            for upd in chapter_updates:

                parent = upd.get("section_id")
                section_counts[parent] += 1

                subsection_id = f"{parent}.{section_counts[parent]}"

                title = upd.get("subsection_title", "Update")
                content = upd.get("content", "").strip()

                # -------------------------
                # WRITE UPDATE
                # -------------------------
                f.write(f"### {subsection_id} {title}\n\n")
                f.write(content + "\n\n")

                # references
                refs = upd.get("references", [])
                if refs:
                    f.write("References:\n")
                    for r in refs:
                        f.write(f"- {r}\n")
                    f.write("\n")