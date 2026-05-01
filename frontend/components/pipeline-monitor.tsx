"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { toast } from "@/components/toast";
import { API_BASE_URL, type PipelineJobResponse } from "@/lib/api";

type PipelineMonitorProps = {
  jobId: string;
  onCompleted?: () => void;
};

type PipelineJobModalProps = {
  title: string;
  eyebrow: string;
  jobId: string;
  onClose: () => void;
  onCompleted?: () => void;
};

type BookPipelineLauncherProps = {
  bookKey: string;
  inputFile: string;
};

async function fetchJob(jobId: string): Promise<PipelineJobResponse> {
  const response = await fetch(`${API_BASE_URL}/api/pipeline/jobs/${jobId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Job status failed: ${response.status}`);
  }
  return response.json() as Promise<PipelineJobResponse>;
}

export function PipelineMonitor({ jobId, onCompleted }: PipelineMonitorProps) {
  const [job, setJob] = useState<PipelineJobResponse | null>(null);
  const [error, setError] = useState("");
  const completedRef = useRef(false);
  const terminalRef = useRef<HTMLPreElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const payload = await fetchJob(jobId);
        if (cancelled) {
          return;
        }
        setJob(payload);
        setError("");
        if (payload.status === "completed" && !completedRef.current) {
          completedRef.current = true;
          onCompleted?.();
        }
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : "Unable to fetch job status.");
        }
      }
    }

    void poll();
    const interval = window.setInterval(poll, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [jobId, onCompleted]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [job?.logs]);

  const status = job?.status ?? "queued";
  const logs = job?.logs || "Waiting for pipeline logs...";

  return (
    <div className="pipelineMonitor">
      <div className="pipelineMonitorHeader">
        <div>
          <p className="eyebrow">Pipeline monitor</p>
          <h3>{status === "completed" ? "Run complete" : status === "failed" ? "Run failed" : "AI update running"}</h3>
        </div>
        <span className={`jobStatus ${status}`}>{status}</span>
      </div>
      {error ? <p className="statusMessage warningMessage">{error}</p> : null}
      {job?.error ? <p className="statusMessage warningMessage">{job.error}</p> : null}
      <pre ref={terminalRef} className="pipelineTerminal">
        {logs}
      </pre>
      {job?.summary?.run_id ? <p className="readerMeta">Run ID: {job.summary.run_id}</p> : null}
    </div>
  );
}

export function PipelineJobModal({
  title,
  eyebrow,
  jobId,
  onClose,
  onCompleted,
}: PipelineJobModalProps) {
  return (
    <div className="modalBackdrop" role="dialog" aria-modal="true" aria-labelledby="pipeline-monitor-title">
      <div className="pipelineModal">
        <div className="pipelineModalHeader">
          <div>
            <p className="eyebrow">{eyebrow}</p>
            <h2 id="pipeline-monitor-title">{title}</h2>
          </div>
          <button className="ghostButton" onClick={onClose}>
            Close
          </button>
        </div>
        <PipelineMonitor jobId={jobId} onCompleted={onCompleted} />
      </div>
    </div>
  );
}

export function BookPipelineLauncher({ bookKey, inputFile }: BookPipelineLauncherProps) {
  const router = useRouter();
  const [jobId, setJobId] = useState("");
  const [open, setOpen] = useState(false);
  const [starting, setStarting] = useState(false);

  async function startRun() {
    setStarting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/pipeline/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_file: inputFile }),
      });
      if (!response.ok) {
        throw new Error(`Run failed: ${response.status}`);
      }
      const payload = (await response.json()) as { status: string; job_id?: string };
      if (!payload.job_id) {
        throw new Error("The API did not return a job id.");
      }
      setJobId(payload.job_id);
      setOpen(true);
      toast.info("Pipeline job started.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to start the pipeline.");
    } finally {
      setStarting(false);
    }
  }

  function closeModal() {
    setOpen(false);
    router.refresh();
  }

  return (
    <>
      <button className="actionButton sidebarActionButton" onClick={startRun} disabled={starting}>
        {starting ? "Starting..." : "Run AI Update"}
      </button>
      {open ? (
        <PipelineJobModal
          title={bookKey}
          eyebrow="Book job"
          jobId={jobId}
          onClose={closeModal}
          onCompleted={() => router.refresh()}
        />
      ) : null}
    </>
  );
}
