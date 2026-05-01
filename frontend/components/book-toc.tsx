import Link from "next/link";

import type { ChapterSummary } from "@/lib/api";

type BookTocProps = {
  bookKey: string;
  chapters: ChapterSummary[];
  activeChapterId?: string;
};

export function BookToc({ bookKey, chapters, activeChapterId }: BookTocProps) {
  return (
    <div className="sidebarBlock">
      <p className="sidebarTitle">Book contents</p>
      {chapters.length === 0 ? (
        <p className="sidebarNote">Chapter structure will appear here after parsing artifacts exist.</p>
      ) : (
        <div className="sidebarNavList">
          {chapters.map((chapter) => {
            const active = activeChapterId === chapter.chapter_id;
            return (
              <Link
                key={chapter.chapter_id}
                href={`/books/${bookKey}/chapters/${chapter.chapter_id}`}
                className={`sidebarLink stacked${active ? " active" : ""}`}
              >
                <span>{chapter.chapter_id}</span>
                <strong>{chapter.title}</strong>
                <span className="sidebarMetaRow">
                  <span>{chapter.section_count} sections</span>
                  <span>{chapter.update_count} updates</span>
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
