"use client";

import { useState } from "react";

import { API_BASE_URL, type ReviewQueueRow } from "@/lib/api";

type ReviewQueueEditorProps = {
  runId: string;
  bookTitle: string;
  initialRows: ReviewQueueRow[];
};

export function ReviewQueueEditor({
  runId,
  bookTitle,
  initialRows,
}: ReviewQueueEditorProps) {
  const [rows, setRows] = useState<ReviewQueueRow[]>(initialRows);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  function updateRow(index: number, patch: Partial<ReviewQueueRow>) {
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row))
    );
  }

  async function applyDecisions() {
    setSubmitting(true);
    setMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/review/runs/${runId}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rows,
          export_docx_enabled: true,
          export_pdf_enabled: true,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || `Apply failed: ${response.status}`);
      }
      setMessage(`Applied review decisions for ${bookTitle}. Approved markdown: ${payload.outputs.approved_book_markdown}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to apply review decisions.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="reviewQueuePanel">
      <div className="buttonRow">
        <button className="actionButton" onClick={applyDecisions} disabled={submitting}>
          {submitting ? "Applying..." : "Apply Decisions"}
        </button>
      </div>

      <div className="reviewQueueList">
        {rows.length === 0 ? (
          <article className="emptyState">
            <h3>No review rows found</h3>
            <p>This run does not currently have a review queue.</p>
          </article>
        ) : (
          rows.map((row, index) => (
            <article key={`${row.chapter_id}-${row.section_id}-${row.title}`} className="updateCard">
              <div className="updateCardHeader">
                <div>
                  <p className="updateSection">{row.section_id}</p>
                  <h4>{row.title}</h4>
                  {row.section_title ? <p className="historyMeta">Section title: {row.section_title}</p> : null}
                </div>
                <span className="badge subtle">{row.chapter_title || row.chapter_id}</span>
              </div>
              <p className="updateFooter">Source: {row.source_summary || "n/a"}</p>
              <p className="updateFooter">Scores: {row.score_summary || "n/a"}</p>

              <div className="reviewContextGrid">
                <div className="contextPanel">
                  <p className="eyebrow">Original Context</p>
                  <p className="contextText">
                    {row.section_context || "No original section context was captured for this row."}
                  </p>
                </div>
                <div className="contextPanel">
                  <p className="eyebrow">Proposed Update</p>
                  <p className="contextText">
                    {row.proposed_text || "No proposed text available."}
                  </p>
                  {row.why_it_matters ? (
                    <p className="contextMeta">Why it matters: {row.why_it_matters}</p>
                  ) : null}
                  {row.mapping_rationale ? (
                    <p className="contextMeta">Mapping rationale: {row.mapping_rationale}</p>
                  ) : null}
                </div>
              </div>

              <div className="formGrid reviewFormGrid">
                <label>
                  <span>Decision</span>
                  <select
                    value={row.review_decision}
                    onChange={(event) => updateRow(index, { review_decision: event.target.value })}
                  >
                    <option value="">unreviewed</option>
                    <option value="approve">approve</option>
                    <option value="revise">revise</option>
                    <option value="reject">reject</option>
                  </select>
                </label>
                <label className="fullWidth">
                  <span>Review notes</span>
                  <input
                    type="text"
                    value={row.review_notes}
                    onChange={(event) => updateRow(index, { review_notes: event.target.value })}
                  />
                </label>
              </div>
            </article>
          ))
        )}
      </div>

      {message ? <p className="statusMessage">{message}</p> : null}
    </section>
  );
}
