import Link from "next/link";

import { UploadPanel } from "@/components/upload-panel";
import { getBooks, getSchedule } from "@/lib/api";

export default async function HomePage() {
  const [books, schedule] = await Promise.all([getBooks(), getSchedule()]);

  return (
    <div className="page">
      <section className="hero">
        <div>
          <p className="eyebrow">Reader Experience</p>
          <h1>Read textbooks as living documents, not frozen PDFs.</h1>
          <p className="lede">
            This interface sits on top of the hardened update pipeline and shows which books
            have active curated updates, when the system is due to run, and where editorial
            review still matters.
          </p>
        </div>
        <div className="heroCard">
          <p className="metricLabel">Schedule</p>
          <p className="metricValue">{schedule.manual_only ? "Manual" : schedule.update_frequency}</p>
          <p className="metricMeta">
            {schedule.due_now
              ? "A run is due now."
              : schedule.next_run_utc
                ? `Next run: ${new Date(schedule.next_run_utc).toLocaleString()}`
                : "No scheduled run."}
          </p>
        </div>
      </section>

      <section className="sectionHeader">
        <div>
          <p className="eyebrow">Library</p>
          <h2>Tracked textbooks</h2>
        </div>
        <Link href="/admin" className="ghostButton">
          Open admin controls
        </Link>
      </section>

      <UploadPanel />

      <section className="bookGrid">
        {books.length === 0 ? (
          <article className="emptyState">
            <h3>No books tracked yet</h3>
            <p>
              Run the pipeline once through the CLI or API and the library view will start
              filling with tracked books and curated updates.
            </p>
          </article>
        ) : (
          books.map((book) => (
            <Link key={book.book_key} href={`/books/${book.book_key}`} className="bookCard">
              <div className="coverTone" />
              <div className="bookMeta">
                <p className="bookTitle">{book.book_title}</p>
                <p className="bookPath">{book.input_file}</p>
              </div>
              <div className="badgeRow">
                <span className="badge">{book.update_count} updates</span>
                <span className="badge subtle">{book.chapters_with_updates} chapters</span>
              </div>
              <p className="bookTimestamp">
                Last run:{" "}
                {book.last_recorded_at
                  ? new Date(book.last_recorded_at).toLocaleString()
                  : "Unknown"}
              </p>
            </Link>
          ))
        )}
      </section>
    </div>
  );
}
