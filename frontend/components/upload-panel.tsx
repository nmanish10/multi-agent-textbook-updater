"use client";

import { useState } from "react";
import { toast } from "@/components/toast";

import { API_BASE_URL } from "@/lib/api";

export function UploadPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  async function upload() {
    if (!file) {
      toast.info("Choose a textbook file first.");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${API_BASE_URL}/api/books/upload`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || `Upload failed: ${response.status}`);
      }
      toast.success(`Uploaded to ${payload.stored_path}`);
      setFile(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="uploadPanel">
      <div>
        <p className="eyebrow">Book Intake</p>
        <h2>Upload a textbook into the platform</h2>
        <p className="lede">
          Supported formats: PDF, Markdown, DOCX, and HTML. Uploaded files are stored on the
          backend and can then be used for pipeline runs.
        </p>
      </div>
      <div className="uploadControls">
        <input
          type="file"
          accept=".pdf,.md,.markdown,.docx,.html,.htm"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button className="actionButton" onClick={upload} disabled={uploading}>
          {uploading ? "Uploading..." : "Upload Book"}
        </button>
      </div>
    </section>
  );
}
