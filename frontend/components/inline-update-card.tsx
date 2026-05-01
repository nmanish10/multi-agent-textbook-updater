import { SourceBadge } from "@/components/source-badge";

type InlineUpdateCardProps = {
  update: {
    update_id?: string;
    section_id?: string;
    title?: string;
    text?: string;
    why_it_matters?: string;
    source?: string;
    status?: string;
  };
};

export function InlineUpdateCard({ update }: InlineUpdateCardProps) {
  return (
    <article className="inlineUpdateCard" id={String(update.update_id ?? update.title ?? "")}>
      <div className="inlineUpdateHeader">
        <div>
          <p className="updateSection">{String(update.section_id ?? "Mapped section pending")}</p>
          <h4>{String(update.title ?? "Untitled update")}</h4>
        </div>
        <div className="inlineUpdateMeta">
          <SourceBadge source={update.source} />
          <span className="badge subtle">{String(update.status ?? "active")}</span>
        </div>
      </div>
      <p className="updateText">{String(update.text ?? "")}</p>
      {update.why_it_matters ? (
        <p className="inlineUpdateWhy">
          <strong>Why it matters:</strong> {String(update.why_it_matters)}
        </p>
      ) : null}
    </article>
  );
}
