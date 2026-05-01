import { InlineUpdateCard } from "@/components/inline-update-card";
import type { BookChapterResponse } from "@/lib/api";

type ChapterReaderProps = {
  chapter: BookChapterResponse;
};

function renderParagraphs(text: string, className = "readerParagraph") {
  return text
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
    .map((paragraph, index) => (
      <p key={`${className}-${index}`} className={className}>
        {paragraph}
      </p>
    ));
}

export function ChapterReader({ chapter }: ChapterReaderProps) {
  const updatesBySection = new Map<string, typeof chapter.updates>();
  for (const update of chapter.updates) {
    const key = String(update.section_id ?? "");
    if (!updatesBySection.has(key)) {
      updatesBySection.set(key, []);
    }
    updatesBySection.get(key)?.push(update);
  }

  return (
    <div className="chapterReader">
      <section className="readerIntro">
        <p className="eyebrow">Chapter reader</p>
        <h2>{chapter.title}</h2>
        <p>
          This chapter view preserves the recovered textbook structure and places surviving
          updates directly beside the sections they extend.
        </p>
      </section>

      {chapter.content ? (
        <article className="readerTextCard">
          <p className="eyebrow">Recovered chapter text</p>
          {renderParagraphs(chapter.content)}
        </article>
      ) : null}

      {chapter.sections.length === 0 ? (
        <article className="emptyState">
          <h3>No section structure available</h3>
          <p>This chapter parsed without section boundaries, so inline placement is limited.</p>
        </article>
      ) : (
        chapter.sections.map((section) => {
          const updates = updatesBySection.get(section.section_id) ?? [];
          return (
            <section key={section.section_id} id={section.section_id} className="readerSectionCard">
              <div className="readerSectionHeader">
                <div>
                  <p className="eyebrow">Section {section.section_id}</p>
                  <h3>{section.title}</h3>
                </div>
                <span className="badge">{updates.length} updates</span>
              </div>

              <div className="readerSectionGrid">
                <div className="readerSectionText">
                  {section.content ? (
                    renderParagraphs(section.content)
                  ) : (
                    <p className="readerParagraph muted">No recovered body text for this section.</p>
                  )}
                </div>

                <div className="readerSectionUpdates">
                  {updates.length === 0 ? (
                    <article className="inlineUpdateCard placeholder">
                      <h4>No accepted updates</h4>
                      <p className="updateText">
                        This section currently has no surviving updates in the competitive store.
                      </p>
                    </article>
                  ) : (
                    updates.map((update) => (
                      <InlineUpdateCard
                        key={String(update.update_id ?? `${section.section_id}-${update.title}`)}
                        update={update}
                      />
                    ))
                  )}
                </div>
              </div>
            </section>
          );
        })
      )}
    </div>
  );
}
