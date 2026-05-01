type UpdateStoreUpdate = {
  chapter_id?: string;
  section_id?: string;
  title?: string;
  text?: string;
  why_it_matters?: string;
  source?: string;
  status?: string;
  update_id?: string;
};

export type ChapterSummary = {
  chapter_id: string;
  title: string;
  section_count: number;
  update_count: number;
  sections: Array<{
    section_id: string;
    title: string;
    has_updates: boolean;
  }>;
};

export type BookChapterListResponse = {
  book_key: string;
  book_title: string;
  chapters: ChapterSummary[];
};

export type BookChapterResponse = {
  book_key: string;
  book_title: string;
  chapter_id: string;
  title: string;
  content: string;
  sections: Array<{
    section_id: string;
    title: string;
    content: string;
  }>;
  updates: UpdateStoreUpdate[];
};

type UpdateStorePayload = {
  book_key: string;
  chapters: Record<string, UpdateStoreUpdate[]>;
  history: Array<Record<string, any>>;
};

type BookDetailResponse = {
  book: {
    book_key: string;
    book_title: string;
    input_file: string;
    latest_run_id: string;
    artifact_dir: string;
    last_recorded_at: string;
    update_count: number;
    chapters_with_updates: number;
  };
  update_store: UpdateStorePayload;
};

export type AdminConfigResponse = {
  update_frequency: string;
  chapter_parallelism: number;
  max_updates_per_chapter: number;
  max_total_updates_per_chapter: number;
  min_accept_score: number;
  min_relevance: number;
  min_credibility: number;
  min_significance: number;
  enabled_sources: string[];
  render_pdf: boolean;
  render_docx: boolean;
  generate_review_pack: boolean;
};

export type ScheduleResponse = {
  update_frequency: string;
  next_run_utc: string | null;
  last_run_utc: string | null;
  last_run_id: string | null;
  manual_only: boolean;
  due_now: boolean;
};

export type PipelineJobResponse = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  logs: string;
  summary?: {
    run_id?: string;
    outputs?: Record<string, unknown>;
  } | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
  input_file?: string;
};

export type ReviewQueueRow = {
  chapter_id: string;
  chapter_title: string;
  section_id: string;
  proposed_subsection_id: string;
  title: string;
  source_summary: string;
  score_summary: string;
  review_decision: string;
  review_notes: string;
  section_title: string;
  section_context: string;
  proposed_text: string;
  why_it_matters: string;
  mapping_rationale: string;
  source: string;
};

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    next: { revalidate: 0 },
  });
  if (!response.ok) {
    throw new Error(`API request failed for ${path}: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type BookListItem = {
  book_key: string;
  book_title: string;
  input_file: string;
  latest_run_id: string;
  artifact_dir: string;
  last_recorded_at: string;
  update_count: number;
  chapters_with_updates: number;
};

export async function getBooks(): Promise<BookListItem[]> {
  const payload = await fetchJson<{ books: BookListItem[] }>("/api/books");
  return payload.books;
}

export async function getBook(bookKey: string): Promise<BookDetailResponse | null> {
  try {
    return await fetchJson<BookDetailResponse>(`/api/books/${bookKey}`);
  } catch {
    return null;
  }
}

export async function getBookUpdates(bookKey: string): Promise<{
  updates: UpdateStoreUpdate[];
  history: Array<Record<string, any>>;
}> {
  try {
    return await fetchJson<{
      updates: UpdateStoreUpdate[];
      history: Array<Record<string, any>>;
    }>(`/api/books/${bookKey}/updates`);
  } catch {
    return { updates: [], history: [] };
  }
}

export async function getBookChapters(bookKey: string): Promise<BookChapterListResponse | null> {
  try {
    return await fetchJson<BookChapterListResponse>(`/api/books/${bookKey}/chapters`);
  } catch {
    return null;
  }
}

export async function getBookChapter(
  bookKey: string,
  chapterId: string
): Promise<BookChapterResponse | null> {
  try {
    return await fetchJson<BookChapterResponse>(`/api/books/${bookKey}/chapters/${chapterId}`);
  } catch {
    return null;
  }
}

export async function getAdminConfig(): Promise<AdminConfigResponse> {
  return fetchJson("/api/admin/config");
}

export async function getSchedule(): Promise<ScheduleResponse> {
  return fetchJson("/api/admin/schedule");
}

export async function getRunHistory(): Promise<{ runs: Array<Record<string, any>> }> {
  return fetchJson("/api/admin/run-history");
}

export async function getReviewRuns(): Promise<{ runs: Array<Record<string, any>> }> {
  return fetchJson("/api/review/runs");
}

export async function getReviewRun(
  runId: string
): Promise<{
  run_id: string;
  artifact_dir: string;
  review_pack: { book_title: string };
  review_queue: ReviewQueueRow[];
} | null> {
  try {
    return await fetchJson(`/api/review/runs/${runId}`);
  } catch {
    return null;
  }
}
