import Link from "next/link";
import { notFound } from "next/navigation";

import { BookToc } from "@/components/book-toc";
import { BookPipelineLauncher } from "@/components/pipeline-monitor";
import { SourceBadge } from "@/components/source-badge";
import { getBook, getBookChapters, getBookUpdates } from "@/lib/api";

type BookPageProps = {
  params: Promise<{ bookKey: string }>;
};

export default async function BookPage({ params }: BookPageProps) {
  const { bookKey } = await params;
  const [book, chaptersPayload, updates] = await Promise.all([
    getBook(bookKey),
    getBookChapters(bookKey),
    getBookUpdates(bookKey),
  ]);

  if (!book || !chaptersPayload) {
    notFound();
  }

  const featuredUpdates = updates.updates.slice(0, 4);

  return (
    <div className="readerPage wideReaderPage">
      <aside className="readerSidebar">
        <p className="eyebrow">Book Reader</p>
        <h1>{book.book.book_title}</h1>
        <p className="readerMeta">{book.book.input_file}</p>
        <div className="statStack">
          <div className="statPill">
            <span>Chapters</span>
            <strong>{chaptersPayload.chapters.length}</strong>
          </div>
          <div className="statPill">
            <span>Active updates</span>
            <strong>{updates.updates.length}</strong>
          </div>
        </div>
        <BookPipelineLauncher bookKey={bookKey} inputFile={book.book.input_file} />
        <BookToc bookKey={bookKey} chapters={chaptersPayload.chapters} />
        <Link href="/" className="ghostButton">
          Back to library
        </Link>
      </aside>

      <section className="readerContent">
        <section className="readerIntro">
          <p className="eyebrow">Living textbook view</p>
          <h2>Browse the recovered structure before dropping into a chapter.</h2>
          <p>
            This book overview is driven by the parsed textbook artifact and the persistent
            survivor store, so the reader reflects the latest accepted updates rather than a
            one-run snapshot.
          </p>
        </section>

        <section className="sectionHeader compactHeader">
          <div>
            <p className="eyebrow">Contents</p>
            <h2>Chapter map</h2>
          </div>
        </section>

        <section className="chapterOverviewGrid">
          {chaptersPayload.chapters.map((chapter) => (
            <article key={chapter.chapter_id} className="chapterOverviewCard">
              <div className="chapterHeader">
                <div>
                  <p className="eyebrow">Chapter {chapter.chapter_id}</p>
                  <h3>{chapter.title}</h3>
                </div>
                <span className="badge">{chapter.update_count} updates</span>
              </div>
              <p className="readerMeta">
                {chapter.section_count} sections recovered from the source textbook.
              </p>
              <div className="chapterSectionList">
                {chapter.sections.slice(0, 5).map((section) => (
                  <div key={section.section_id} className="chapterSectionRow">
                    <span>{section.section_id}</span>
                    <strong>{section.title}</strong>
                    {section.has_updates ? <span className="sidebarMiniBadge">Updated</span> : null}
                  </div>
                ))}
              </div>
              <Link href={`/books/${bookKey}/chapters/${chapter.chapter_id}`} className="ghostButton">
                Open chapter
              </Link>
            </article>
          ))}
        </section>

        <section className="sectionHeader compactHeader">
          <div>
            <p className="eyebrow">Current highlights</p>
            <h2>Recent surviving updates</h2>
          </div>
        </section>

        {featuredUpdates.length === 0 ? (
          <article className="emptyState">
            <h3>No accepted updates yet</h3>
            <p>This book is tracked, but nothing has survived the quality filters yet.</p>
          </article>
        ) : (
          <section className="updateList">
            {featuredUpdates.map((update) => (
              <article key={String(update.update_id ?? update.title)} className="updateCard">
                <div className="updateCardHeader">
                  <div>
                    <p className="updateSection">
                      {String(update.chapter_id ?? "Chapter")} · {String(update.section_id ?? "Section")}
                    </p>
                    <h4>{String(update.title ?? "Untitled update")}</h4>
                  </div>
                  <SourceBadge source={update.source} />
                </div>
                <p className="updateText">{String(update.text ?? "")}</p>
              </article>
            ))}
          </section>
        )}
      </section>
    </div>
  );
}
