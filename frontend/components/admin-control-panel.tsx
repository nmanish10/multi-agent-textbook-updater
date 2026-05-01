"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "@/components/toast";

import { PipelineJobModal } from "@/components/pipeline-monitor";
import { API_BASE_URL, type AdminConfigResponse, type ScheduleResponse } from "@/lib/api";

type AdminControlPanelProps = {
  initialConfig: AdminConfigResponse;
  initialSchedule: ScheduleResponse;
};

type RunResponse = {
  status: string;
  job_id?: string;
  summary?: {
    run_id?: string;
  };
  scheduler?: {
    next_run_utc?: string | null;
  };
};

export function AdminControlPanel({
  initialConfig,
  initialSchedule,
}: AdminControlPanelProps) {
  const router = useRouter();
  const [config, setConfig] = useState(initialConfig);
  const [schedule] = useState(initialSchedule);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [activeJobId, setActiveJobId] = useState("");
  const [activeJobTitle, setActiveJobTitle] = useState("");

  async function saveConfig() {
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!response.ok) {
        throw new Error(`Save failed: ${response.status}`);
      }
      const payload = (await response.json()) as AdminConfigResponse;
      setConfig(payload);
      toast.success("Admin configuration saved.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save config.");
    } finally {
      setSaving(false);
    }
  }

  async function triggerRun(runIfDue: boolean) {
    setRunning(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/pipeline/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_if_due: runIfDue }),
      });
      if (!response.ok) {
        throw new Error(`Run failed: ${response.status}`);
      }
      const payload = (await response.json()) as RunResponse;
      if (payload.status === "not_due") {
        toast.info(
          payload.scheduler?.next_run_utc
            ? `No run started. Next due: ${new Date(payload.scheduler.next_run_utc).toLocaleString()}`
            : "No run started because the schedule is not due."
        );
      } else if (payload.job_id) {
        setActiveJobId(payload.job_id);
        setActiveJobTitle(runIfDue ? "Scheduled pipeline run" : "Manual pipeline run");
      } else {
        toast.success(`Pipeline run completed${payload.summary?.run_id ? `: ${payload.summary.run_id}` : "."}`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to trigger run.");
    } finally {
      setRunning(false);
    }
  }

  function closeJobModal() {
    setActiveJobId("");
    setActiveJobTitle("");
    router.refresh();
  }

  return (
    <section className="adminActionPanel">
      <div className="sectionHeader">
        <div>
          <p className="eyebrow">Actions</p>
          <h2>Control the system from the browser</h2>
        </div>
      </div>

      <div className="adminActionGrid">
        <article className="adminCard">
          <p className="eyebrow">Run control</p>
          <h3>Trigger pipeline execution</h3>
          <p className="lede">
            Due now: {schedule.due_now ? "yes" : "no"}. Use the guarded run to respect the
            schedule, or force a run manually.
          </p>
          <div className="buttonRow">
            <button className="actionButton" onClick={() => triggerRun(true)} disabled={running}>
              {running ? "Working..." : "Run If Due"}
            </button>
            <button className="ghostButton" onClick={() => triggerRun(false)} disabled={running}>
              Force Run
            </button>
          </div>
        </article>

        <article className="adminCard">
          <p className="eyebrow">Config editor</p>
          <h3>Update selection thresholds</h3>
          <div className="formGrid">
            <label>
              <span>Frequency</span>
              <select
                value={config.update_frequency}
                onChange={(event) => setConfig({ ...config, update_frequency: event.target.value })}
              >
                <option value="daily">daily</option>
                <option value="weekly">weekly</option>
                <option value="monthly">monthly</option>
                <option value="manual">manual</option>
              </select>
            </label>
            <label>
              <span>Parallelism</span>
              <input
                type="number"
                min={1}
                max={8}
                value={config.chapter_parallelism}
                onChange={(event) =>
                  setConfig({ ...config, chapter_parallelism: Number(event.target.value) || 1 })
                }
              />
            </label>
            <label>
              <span>Max updates / run</span>
              <input
                type="number"
                min={1}
                max={20}
                value={config.max_updates_per_chapter}
                onChange={(event) =>
                  setConfig({ ...config, max_updates_per_chapter: Number(event.target.value) || 1 })
                }
              />
            </label>
            <label>
              <span>Max total / chapter</span>
              <input
                type="number"
                min={1}
                max={50}
                value={config.max_total_updates_per_chapter}
                onChange={(event) =>
                  setConfig({ ...config, max_total_updates_per_chapter: Number(event.target.value) || 1 })
                }
              />
            </label>
            <label>
              <span>Min accept score</span>
              <input
                type="number"
                min={0}
                max={1}
                step="0.01"
                value={config.min_accept_score}
                onChange={(event) =>
                  setConfig({ ...config, min_accept_score: Number(event.target.value) || 0 })
                }
              />
            </label>
            <label>
              <span>Min relevance</span>
              <input
                type="number"
                min={0}
                max={1}
                step="0.01"
                value={config.min_relevance}
                onChange={(event) => setConfig({ ...config, min_relevance: Number(event.target.value) || 0 })}
              />
            </label>
            <label>
              <span>Min credibility</span>
              <input
                type="number"
                min={0}
                max={1}
                step="0.01"
                value={config.min_credibility}
                onChange={(event) =>
                  setConfig({ ...config, min_credibility: Number(event.target.value) || 0 })
                }
              />
            </label>
            <label>
              <span>Min significance</span>
              <input
                type="number"
                min={0}
                max={1}
                step="0.01"
                value={config.min_significance}
                onChange={(event) =>
                  setConfig({ ...config, min_significance: Number(event.target.value) || 0 })
                }
              />
            </label>
            <label className="fullWidth">
              <span>Enabled sources</span>
              <input
                type="text"
                value={config.enabled_sources.join(",")}
                onChange={(event) =>
                  setConfig({
                    ...config,
                    enabled_sources: event.target.value
                      .split(",")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  })
                }
              />
            </label>
          </div>

          <div className="toggleRow">
            <label className="checkboxLabel">
              <input
                type="checkbox"
                checked={config.render_pdf ?? true}
                onChange={(event) => setConfig({ ...config, render_pdf: event.target.checked })}
              />
              <span>Render PDF</span>
            </label>
            <label className="checkboxLabel">
              <input
                type="checkbox"
                checked={config.render_docx ?? true}
                onChange={(event) => setConfig({ ...config, render_docx: event.target.checked })}
              />
              <span>Render DOCX</span>
            </label>
            <label className="checkboxLabel">
              <input
                type="checkbox"
                checked={config.generate_review_pack ?? true}
                onChange={(event) =>
                  setConfig({ ...config, generate_review_pack: event.target.checked })
                }
              />
              <span>Generate review pack</span>
            </label>
          </div>

          <div className="buttonRow">
            <button className="actionButton" onClick={saveConfig} disabled={saving}>
              {saving ? "Saving..." : "Save Config"}
            </button>
          </div>
        </article>
      </div>

      {message ? <p className="statusMessage">{message}</p> : null}
      {activeJobId ? (
        <PipelineJobModal
          title={activeJobTitle}
          eyebrow="Admin job"
          jobId={activeJobId}
          onClose={closeJobModal}
          onCompleted={() => router.refresh()}
        />
      ) : null}
    </section>
  );
}
