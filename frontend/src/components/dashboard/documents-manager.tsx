"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import { useToast } from "@/components/toast-provider";
import { apiBaseUrl, apiRequest, buildApiHeaders } from "@/lib/auth";

type Workspace = {
  id: string;
  name: string;
  role: string;
};

type DocumentSummary = {
  id: string;
  title: string;
  mime_type: string | null;
  file_size: number | null;
  ingestion_status: "pending" | "processing" | "indexed" | "failed";
  metadata_json: Record<string, unknown> | null;
  summary: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
};

type UploadingFile = {
  id: string;
  filename: string;
  progress: number;
  status: "preparing" | "uploading" | "processing" | "failed";
  error?: string;
};

const MAX_FILE_SIZE_MB = 10;
const allowedExtensions = [".pdf", ".docx", ".txt", ".csv"];
const allowedMimeTypes = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "text/csv",
  "application/csv",
  "application/octet-stream",
]);

const statusStyles: Record<DocumentSummary["ingestion_status"], string> = {
  pending: "border-amber-400/25 bg-amber-500/10 text-amber-100",
  processing: "border-sky-400/25 bg-sky-500/10 text-sky-100",
  indexed: "border-emerald-400/25 bg-emerald-500/10 text-emerald-100",
  failed: "border-rose-400/25 bg-rose-500/10 text-rose-100",
};

function formatBytes(bytes: number | null) {
  if (!bytes) {
    return "Unknown size";
  }
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function getFileExtension(filename: string) {
  const dotIndex = filename.lastIndexOf(".");
  return dotIndex >= 0 ? filename.slice(dotIndex).toLowerCase() : "";
}

function fileToBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Could not read the selected file."));
        return;
      }
      const [, base64] = result.split(",");
      resolve(base64);
    };
    reader.onerror = () => reject(new Error("Failed to read the selected file."));
    reader.readAsDataURL(file);
  });
}

export function DocumentsManager() {
  const { pushToast } = useToast();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null,
    [selectedWorkspaceId, workspaces],
  );
  const canManageDocuments = selectedWorkspace?.role !== "viewer";

  function renderMetadataFact(metadata: Record<string, unknown> | null) {
    const pageCount = metadata?.["page_count"];
    if (typeof pageCount === "number") {
      return `${pageCount} pages`;
    }
    const rowCount = metadata?.["row_count"];
    if (typeof rowCount === "number") {
      return `${rowCount} rows`;
    }
    return "Metadata extracted";
  }

  useEffect(() => {
    let active = true;
    async function loadWorkspaces() {
      setIsLoading(true);
      setError("");
      try {
        const workspaceList = await apiRequest<Workspace[]>("/api/v1/workspaces");
        if (!active) {
          return;
        }
        setWorkspaces(workspaceList);
        if (workspaceList.length) {
          setSelectedWorkspaceId((current) => current || workspaceList[0].id);
        }
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load workspaces.");
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    void loadWorkspaces();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      setDocuments([]);
      return;
    }

    let active = true;
    async function loadDocuments() {
      setIsLoading(true);
      setError("");
      try {
        const documentList = await apiRequest<DocumentSummary[]>(
          `/api/v1/workspaces/${selectedWorkspaceId}/documents`,
        );
        if (!active) {
          return;
        }
        setDocuments(documentList);
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load documents.");
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    void loadDocuments();

    return () => {
      active = false;
    };
  }, [selectedWorkspaceId]);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      return;
    }
    const hasActiveIndexing = documents.some((document) =>
      ["pending", "processing"].includes(document.ingestion_status),
    );
    if (!hasActiveIndexing) {
      return;
    }
    const interval = window.setInterval(() => {
      void refreshDocuments();
    }, 2500);
    return () => window.clearInterval(interval);
  }, [documents, selectedWorkspaceId]);

  function validateFile(file: File) {
    const extension = getFileExtension(file.name);
    if (!allowedExtensions.includes(extension)) {
      throw new Error("Unsupported file. Use PDF, DOCX, TXT, or CSV.");
    }
    if (!allowedMimeTypes.has(file.type || "application/octet-stream")) {
      throw new Error("Unsupported MIME type for this upload.");
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      throw new Error(`File too large. Maximum size is ${MAX_FILE_SIZE_MB} MB.`);
    }
  }

  function updateUploadState(uploadId: string, patch: Partial<UploadingFile>) {
    setUploadingFiles((current) =>
      current.map((item) => (item.id === uploadId ? { ...item, ...patch } : item)),
    );
  }

  async function refreshDocuments() {
    if (!selectedWorkspaceId) {
      return;
    }
    const documentList = await apiRequest<DocumentSummary[]>(
      `/api/v1/workspaces/${selectedWorkspaceId}/documents`,
    );
    setDocuments(documentList);
  }

  async function uploadSingleFile(file: File) {
    validateFile(file);
    const uploadId = crypto.randomUUID();
    setUploadingFiles((current) => [
      ...current,
      {
        id: uploadId,
        filename: file.name,
        progress: 5,
        status: "preparing",
      },
    ]);

    try {
      const contentBase64 = await fileToBase64(file);
      updateUploadState(uploadId, { progress: 22, status: "uploading" });

      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${apiBaseUrl}/api/v1/workspaces/${selectedWorkspaceId}/documents`);
        xhr.withCredentials = true;
        const headers = buildApiHeaders({ "Content-Type": "application/json" }, "POST");
        headers.forEach((value, key) => {
          xhr.setRequestHeader(key, value);
        });

        xhr.upload.onprogress = (event) => {
          if (!event.lengthComputable) {
            return;
          }
          const uploadProgress = Math.min(85, Math.round((event.loaded / event.total) * 75) + 15);
          updateUploadState(uploadId, { progress: uploadProgress, status: "uploading" });
        };

        xhr.onreadystatechange = () => {
          if (xhr.readyState !== XMLHttpRequest.DONE) {
            return;
          }
          if (xhr.status >= 200 && xhr.status < 300) {
            updateUploadState(uploadId, { progress: 100, status: "processing" });
            resolve();
            return;
          }
          try {
            const parsed = JSON.parse(xhr.responseText) as { detail?: string };
            reject(new Error(parsed.detail ?? "Upload failed."));
          } catch {
            reject(new Error("Upload failed."));
          }
        };

        xhr.onerror = () =>
          reject(
            new Error(
              `Could not reach the backend at ${apiBaseUrl}. Make sure the FastAPI server is running.`,
            ),
          );

        xhr.send(
          JSON.stringify({
            filename: file.name,
            mime_type: file.type || "application/octet-stream",
            file_size: file.size,
            content_base64: contentBase64,
          }),
        );
      });

      await refreshDocuments();
      pushToast({
        title: `${file.name} uploaded`,
        description: "The document was stored and queued for background indexing.",
        tone: "info",
      });
      window.setTimeout(() => {
        setUploadingFiles((current) => current.filter((item) => item.id !== uploadId));
      }, 1200);
    } catch (uploadError) {
      const message = uploadError instanceof Error ? uploadError.message : "Upload failed.";
      updateUploadState(uploadId, { status: "failed", error: message, progress: 100 });
      pushToast({
        title: "Upload failed",
        description: message,
        tone: "error",
      });
    }
  }

  async function handleFiles(files: FileList | File[]) {
    if (!selectedWorkspaceId) {
      pushToast({
        title: "No workspace selected",
        description: "Choose a workspace before uploading documents.",
        tone: "error",
      });
      return;
    }
    if (!canManageDocuments) {
      pushToast({
        title: "Read-only workspace",
        description: "Viewer access can review documents but cannot upload, delete, or re-index them.",
        tone: "error",
      });
      return;
    }

    for (const file of Array.from(files)) {
      await uploadSingleFile(file);
    }
  }

  async function handleDeleteDocument(documentId: string, title: string) {
    try {
      await apiRequest(`/api/v1/workspaces/${selectedWorkspaceId}/documents/${documentId}`, {
        method: "DELETE",
      });
      setDocuments((current) => current.filter((item) => item.id !== documentId));
      pushToast({
        title: `${title} deleted`,
        description: "The original file and its indexed chunks were removed.",
        tone: "success",
      });
    } catch (deleteError) {
      pushToast({
        title: "Delete failed",
        description:
          deleteError instanceof Error ? deleteError.message : "Could not delete this document.",
        tone: "error",
      });
    }
  }

  async function handleReindexDocument(documentId: string, title: string) {
    try {
      await apiRequest(`/api/v1/workspaces/${selectedWorkspaceId}/documents/${documentId}/reindex`, {
        method: "POST",
      });
      await refreshDocuments();
      pushToast({
        title: `${title} re-indexed`,
        description: "The document was queued for background re-indexing.",
        tone: "info",
      });
    } catch (reindexError) {
      pushToast({
        title: "Re-index failed",
        description:
          reindexError instanceof Error
            ? reindexError.message
            : "Could not re-index this document.",
        tone: "error",
      });
    }
  }

  if (isLoading && !documents.length && !workspaces.length) {
    return (
      <main className="space-y-6">
        <LoadingGrid rows={2} />
        <LoadingGrid rows={4} />
      </main>
    );
  }

  if (error) {
    return (
      <ErrorState
        actionLabel="Retry loading"
        description={error}
        onAction={() => window.location.reload()}
        title="Document workspace could not be loaded"
      />
    );
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.14),transparent_32%),linear-gradient(145deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">Knowledge intake</p>
            <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">Document Command</h2>
            <p className="mt-4 text-slate-300">
              Upload PDF, DOCX, TXT, and CSV files, preserve originals locally, and track processing status from pending through indexed.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <select
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none"
              onChange={(event) => setSelectedWorkspaceId(event.target.value)}
              value={selectedWorkspaceId}
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name} · {workspace.role}
                </option>
              ))}
            </select>
            <button
              className="rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canManageDocuments}
              onClick={() => inputRef.current?.click()}
              type="button"
            >
              Upload files
            </button>
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">Workspace</p>
            <p className="mt-3 text-2xl font-semibold text-white">
              {selectedWorkspace?.name ?? "No workspace"}
            </p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">Stored documents</p>
            <p className="mt-3 text-2xl font-semibold text-white">{documents.length}</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">Upload policy</p>
            <p className="mt-3 text-2xl font-semibold text-white">Max {MAX_FILE_SIZE_MB} MB</p>
          </div>
        </div>
      </section>

      <section
        className={`rounded-[2rem] border border-dashed p-8 transition ${
          isDragging
            ? "border-cyan-300/60 bg-cyan-400/10"
            : "border-white/15 bg-white/[0.03]"
        }`}
        onDragEnter={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          setIsDragging(false);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          void handleFiles(event.dataTransfer.files);
        }}
      >
        <input
          accept=".pdf,.docx,.txt,.csv"
          className="hidden"
          multiple
          onChange={(event) => {
            if (event.target.files) {
              void handleFiles(event.target.files);
            }
            event.target.value = "";
          }}
          ref={inputRef}
          type="file"
        />

        <div className="mx-auto max-w-2xl text-center">
          <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Drag and drop</p>
          <h3 className="mt-3 text-3xl font-semibold text-white">Drop files to begin processing</h3>
          <p className="mt-3 text-slate-400">
            Supported formats: PDF, DOCX, TXT, CSV. We validate file type and size, store the original file, extract text and metadata, and update status automatically.
          </p>
          <button
            className="mt-6 rounded-full border border-cyan-400/25 bg-cyan-400/10 px-5 py-2.5 text-sm font-medium text-cyan-100 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!canManageDocuments}
            onClick={() => inputRef.current?.click()}
            type="button"
          >
            Select files
          </button>
        </div>

        {uploadingFiles.length ? (
          <div className="mt-8 grid gap-4">
            {uploadingFiles.map((file) => (
              <div
                key={file.id}
                className="rounded-3xl border border-white/10 bg-slate-950/60 p-5"
              >
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="font-medium text-white">{file.filename}</p>
                    <p className="mt-1 text-sm text-slate-400">
                      {file.status === "preparing"
                        ? "Preparing file"
                        : file.status === "uploading"
                          ? "Uploading"
                          : file.status === "processing"
                            ? "Processing and indexing"
                            : file.error ?? "Upload failed"}
                    </p>
                  </div>
                  <span className="text-sm text-slate-300">{file.progress}%</span>
                </div>
                <div className="mt-4 h-2 rounded-full bg-white/10">
                  <div
                    className={`h-2 rounded-full ${
                      file.status === "failed" ? "bg-rose-500" : "bg-gradient-to-r from-cyan-400 to-sky-500"
                    }`}
                    style={{ width: `${file.progress}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      {!documents.length ? (
        <section className="rounded-[2rem] border border-dashed border-white/15 bg-white/[0.03] p-10 text-center">
          <p className="text-sm uppercase tracking-[0.3em] text-cyan-200/70">Empty state</p>
          <h3 className="mt-3 text-2xl font-semibold text-white">No documents uploaded yet</h3>
          <p className="mt-3 text-slate-400">
            Upload your first PDF, DOCX, TXT, or CSV file to start building the workspace knowledge base.
          </p>
        </section>
      ) : (
        <section className="grid gap-4">
          {documents.map((document) => (
            <article
              key={document.id}
              className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6"
            >
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="max-w-3xl">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="text-xl font-semibold text-white">{document.title}</h3>
                    <span
                      className={`rounded-full border px-3 py-1 text-xs font-medium ${statusStyles[document.ingestion_status]}`}
                    >
                      {document.ingestion_status}
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-slate-400">
                    {document.summary ?? "No summary available yet."}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500">
                    <span>{document.mime_type ?? "Unknown MIME"}</span>
                    <span>{formatBytes(document.file_size)}</span>
                    <span>{document.chunk_count} chunks</span>
                    <span>{renderMetadataFact(document.metadata_json)}</span>
                  </div>
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!canManageDocuments}
                    onClick={() => void handleReindexDocument(document.id, document.title)}
                    type="button"
                  >
                    Re-index
                  </button>
                  <button
                    className="rounded-full border border-rose-400/20 bg-rose-500/10 px-4 py-2 text-sm text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!canManageDocuments}
                    onClick={() => void handleDeleteDocument(document.id, document.title)}
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
