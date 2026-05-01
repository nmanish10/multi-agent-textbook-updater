import Link from "next/link";
import { notFound } from "next/navigation";

import { getReviewRun } from "@/lib/api";
import { ReviewQueueEditor } from "@/components/review-queue-editor";

type ReviewPageProps = {
  params: Promise<{ runId: string }>;
};

export default async function ReviewRunPage({ params }: ReviewPageProps) {
  const { runId } = await params;
  const reviewRun = await getReviewRun(runId);

  if (!reviewRun) {
    notFound();
  }

  return (
    <div className="page">
      <section className="sectionHeader">
        <div>
          <p className="eyebrow">Review Queue</p>
          <h1>{reviewRun.review_pack.book_title}</h1>
          <p className="lede">
            Approve, revise, or reject proposed updates directly in the browser, then apply the
            decisions to generate approved exports.
          </p>
        </div>
        <Link href="/admin" className="ghostButton">
          Back to admin
        </Link>
      </section>

      <ReviewQueueEditor
        runId={runId}
        initialRows={reviewRun.review_queue}
        bookTitle={reviewRun.review_pack.book_title}
      />
    </div>
  );
}
