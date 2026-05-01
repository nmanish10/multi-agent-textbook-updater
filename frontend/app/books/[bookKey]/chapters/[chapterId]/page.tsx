import Link from "next/link";
import { notFound } from "next/navigation";

import { BookToc } from "@/components/book-toc";
import { ChapterReader } from "@/components/chapter-reader";
import { SectionSidebar } from "@/components/section-sidebar";
import { getBookChapter, getBookChapters } from "@/lib/api";

type ChapterPageProps = {
  params: Promise<{ bookKey: string; chapterId: string }>;
};

export default async function ChapterPage({ params }: ChapterPageProps) {
  const { bookKey, chapterId } = await params;
  const [chaptersPayload, chapter] = await Promise.all([
    getBookChapters(bookKey),
    getBookChapter(bookKey, chapterId),
  ]);

  if (!chaptersPayload || !chapter) {
    notFound();
  }

  const chapterSummary = chaptersPayload.chapters.find((item) => item.chapter_id === chapter.chapter_id);

  return (
    <div className="readerPage chapterReaderPage">
      <aside className="readerSidebar">
        <p className="eyebrow">Reading mode</p>
        <h1>{chapter.book_title}</h1>
        <p className="readerMeta">Full chapter view with inline accepted updates.</p>
        <div className="statStack">
          <div className="statPill">
            <span>Sections</span>
            <strong>{chapter.sections.length}</strong>
          </div>
          <div className="statPill">
            <span>Live updates</span>
            <strong>{chapter.updates.length}</strong>
          </div>
        </div>
        <BookToc bookKey={bookKey} chapters={chaptersPayload.chapters} activeChapterId={chapter.chapter_id} />
        <SectionSidebar
          sections={chapter.sections.map((section) => ({
            section_id: section.section_id,
            title: section.title,
            has_updates: chapter.updates.some((update) => update.section_id === section.section_id),
          }))}
        />
        <Link href={`/books/${bookKey}`} className="ghostButton">
          Back to book
        </Link>
      </aside>

      <section className="readerContent">
        <div className="chapterRouteHeader">
          <div>
            <p className="eyebrow">Chapter {chapter.chapter_id}</p>
            <h2>{chapter.title}</h2>
            <p className="readerMeta">
              {chapterSummary?.section_count ?? chapter.sections.length} sections recovered,{" "}
              {chapterSummary?.update_count ?? chapter.updates.length} active updates.
            </p>
          </div>
        </div>

        <ChapterReader chapter={chapter} />
      </section>
    </div>
  );
}
