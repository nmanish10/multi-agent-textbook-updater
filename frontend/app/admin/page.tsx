import Link from "next/link";

import { getAdminConfig, getReviewRuns, getRunHistory, getSchedule } from "@/lib/api";
import { AdminControlPanel } from "@/components/admin-control-panel";

export default async function AdminPage() {
  const [config, schedule, runHistory, reviewRuns] = await Promise.all([
    getAdminConfig(),
    getSchedule(),
    getRunHistory(),
    getReviewRuns(),
  ]);

  const recentRuns = runHistory.runs.slice(-5).reverse();

  return (
    <div className="page">
      <section className="sectionHeader">
        <div>
          <p className="eyebrow">Admin Panel</p>
          <h1>Operational control surface</h1>
          <p className="lede">
            This page reads the persisted admin config, schedule ledger, and run history that the
            backend now maintains.
          </p>
        </div>
      </section>

      <section className="adminGrid">
        <article className="adminCard">
          <p className="eyebrow">Scheduling</p>
          <h2>{schedule.manual_only ? "Manual mode" : schedule.update_frequency}</h2>
          <p>
            {schedule.due_now
              ? "A scheduled run is due now."
              : schedule.next_run_utc
                ? `Next due: ${new Date(schedule.next_run_utc).toLocaleString()}`
                : "No next run is scheduled."}
          </p>
          <dl className="detailList">
            <div>
              <dt>Last run</dt>
              <dd>{schedule.last_run_utc ? new Date(schedule.last_run_utc).toLocaleString() : "Never"}</dd>
            </div>
            <div>
              <dt>Last run id</dt>
              <dd>{schedule.last_run_id ?? "None"}</dd>
            </div>
          </dl>
        </article>

        <article className="adminCard">
          <p className="eyebrow">Thresholds</p>
          <h2>Selection controls</h2>
          <dl className="detailList compact">
            <div>
              <dt>Max updates / run</dt>
              <dd>{config.max_updates_per_chapter}</dd>
            </div>
            <div>
              <dt>Max total / chapter</dt>
              <dd>{config.max_total_updates_per_chapter}</dd>
            </div>
            <div>
              <dt>Min accept score</dt>
              <dd>{config.min_accept_score}</dd>
            </div>
            <div>
              <dt>Min relevance</dt>
              <dd>{config.min_relevance}</dd>
            </div>
            <div>
              <dt>Min credibility</dt>
              <dd>{config.min_credibility}</dd>
            </div>
            <div>
              <dt>Min significance</dt>
              <dd>{config.min_significance}</dd>
            </div>
          </dl>
        </article>

        <article className="adminCard">
          <p className="eyebrow">Source mix</p>
          <h2>Enabled retrieval lanes</h2>
          <div className="badgeRow">
            {config.enabled_sources.map((source) => (
              <span key={source} className="badge">
                {source}
              </span>
            ))}
          </div>
          <p className="adminMeta">
            Parallelism: {config.chapter_parallelism} chapter jobs
          </p>
        </article>
      </section>

      <AdminControlPanel initialConfig={config} initialSchedule={schedule} />

      <section className="sectionHeader">
        <div>
          <p className="eyebrow">Recent runs</p>
          <h2>Run history ledger</h2>
        </div>
      </section>

      <section className="historyTable">
        {recentRuns.length === 0 ? (
          <article className="emptyState">
            <h3>No run history yet</h3>
            <p>The API is ready, but no pipeline runs have been recorded yet.</p>
          </article>
        ) : (
          recentRuns.map((run) => (
            <article key={run.run_id} className="historyRow">
              <div>
                <p className="historyBook">{run.book_title ?? run.book_key}</p>
                <p className="historyMeta">{run.run_id}</p>
              </div>
              <div>
                <p className="historyMetric">{run.stats?.final_updates ?? 0} final updates</p>
                <p className="historyMeta">
                  Delta: {run.version_delta?.kind === "initial_run" ? "initial" : run.version_delta?.final_updates_delta ?? 0}
                </p>
              </div>
              <div>
                <p className="historyMetric">
                  {run.recorded_at ? new Date(run.recorded_at).toLocaleString() : "Unknown time"}
                </p>
                <p className="historyMeta">
                  Input changed: {run.version_delta?.input_changed ? "yes" : "no"}
                </p>
              </div>
            </article>
          ))
        )}
      </section>

      <section className="sectionHeader">
        <div>
          <p className="eyebrow">Editorial review</p>
          <h2>Review-ready runs</h2>
        </div>
      </section>

      <section className="historyTable">
        {reviewRuns.runs.length === 0 ? (
          <article className="emptyState">
            <h3>No review packs yet</h3>
            <p>Run the pipeline with review-pack generation enabled to review updates in-browser.</p>
          </article>
        ) : (
          reviewRuns.runs.slice(0, 5).map((run) => (
            <article key={run.run_id} className="historyRow">
              <div>
                <p className="historyBook">{run.book_title ?? run.book_key}</p>
                <p className="historyMeta">{run.run_id}</p>
              </div>
              <div>
                <p className="historyMetric">
                  {run.recorded_at ? new Date(run.recorded_at).toLocaleString() : "Unknown time"}
                </p>
                <p className="historyMeta">Review pack ready</p>
              </div>
              <div>
                <Link href={`/review/${run.run_id}`} className="ghostButton">
                  Open review queue
                </Link>
              </div>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
