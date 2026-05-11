"use client";

import { useEffect, useMemo, useState } from "react";

import { ExportModal } from "@/components/dashboard/export-modal";
import { ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import { useToast } from "@/components/toast-provider";
import {
  bulkReviewFaqs,
  deleteFaqs,
  FAQGenerationState,
  FAQStatus,
  FAQSummary,
  fetchFaqWorkspaces,
  generateFaqs,
  listFaqs,
  updateFaq,
  WorkspaceSummary,
} from "@/lib/faq";

const statusTone: Record<FAQStatus, string> = {
  draft: "border-amber-400/25 bg-amber-500/10 text-amber-100",
  approved: "border-emerald-400/25 bg-emerald-500/10 text-emerald-100",
  rejected: "border-rose-400/25 bg-rose-500/10 text-rose-100",
};

type DraftForm = {
  faqId: string;
  question: string;
  answer: string;
  category: string;
  status: FAQStatus;
};

export function FAQManager() {
  const { pushToast } = useToast();
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [faqs, setFaqs] = useState<FAQSummary[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<FAQStatus | "">("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [generation, setGeneration] = useState<FAQGenerationState | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [editing, setEditing] = useState<DraftForm | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");
  const [exportModalOpen, setExportModalOpen] = useState(false);

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null,
    [selectedWorkspaceId, workspaces],
  );
  const canManageFaqs = selectedWorkspace?.role !== "viewer";
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      setIsLoading(true);
      setError("");
      try {
        const workspaceList = await fetchFaqWorkspaces();
        if (!active) return;
        setWorkspaces(workspaceList);
        if (workspaceList.length) {
          setSelectedWorkspaceId((current) => current || workspaceList[0].id);
        }
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Failed to load workspaces.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      setFaqs([]);
      setCategories([]);
      setGeneration(null);
      return;
    }
    let active = true;
    async function refresh() {
      setIsLoading(true);
      setError("");
      try {
        const response = await listFaqs({
          workspaceId: selectedWorkspaceId,
          category: selectedCategory || undefined,
          status: selectedStatus || undefined,
          search: search || undefined,
          page,
          pageSize,
        });
        if (!active) return;
        setFaqs(response.items);
        setCategories(response.categories);
        setTotal(response.total);
        setGeneration(response.generation ?? null);
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load FAQs.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void refresh();
    return () => {
      active = false;
    };
  }, [page, pageSize, search, selectedCategory, selectedStatus, selectedWorkspaceId]);

  useEffect(() => {
    if (!selectedWorkspaceId) return;
    if (!generation || !["queued", "running"].includes(generation.status)) return;
    const interval = window.setInterval(() => {
      void listFaqs({
        workspaceId: selectedWorkspaceId,
        category: selectedCategory || undefined,
        status: selectedStatus || undefined,
        search: search || undefined,
        page,
        pageSize,
      }).then((response) => {
        setFaqs(response.items);
        setCategories(response.categories);
        setTotal(response.total);
        setGeneration(response.generation ?? null);
        if (response.generation?.status === "completed") {
          setIsGenerating(false);
        }
      });
    }, 2500);
    return () => window.clearInterval(interval);
  }, [generation, page, pageSize, search, selectedCategory, selectedStatus, selectedWorkspaceId]);

  useEffect(() => {
    setSelectedIds([]);
  }, [selectedWorkspaceId, selectedCategory, selectedStatus, search, page]);

  const draftCount = faqs.filter((faq) => faq.status === "draft").length;
  const approvedCount = faqs.filter((faq) => faq.status === "approved").length;

  function toggleSelection(faqId: string) {
    setSelectedIds((current) =>
      current.includes(faqId) ? current.filter((item) => item !== faqId) : [...current, faqId],
    );
  }

  async function refreshCurrentPage() {
    if (!selectedWorkspaceId) return;
    const response = await listFaqs({
      workspaceId: selectedWorkspaceId,
      category: selectedCategory || undefined,
      status: selectedStatus || undefined,
      search: search || undefined,
      page,
      pageSize,
    });
    setFaqs(response.items);
    setCategories(response.categories);
    setTotal(response.total);
    setGeneration(response.generation ?? null);
  }

  async function handleGenerate(force = false) {
    if (!selectedWorkspaceId) return;
    if (!canManageFaqs) {
      pushToast({
        title: "Read-only workspace",
        description: "Viewer access can review FAQs but cannot generate or publish them.",
        tone: "error",
      });
      return;
    }
    setIsGenerating(true);
    try {
      const response = await generateFaqs({
        workspaceId: selectedWorkspaceId,
        force,
        maxFaqsPerSource: 5,
      });
      setGeneration(response.generation);
      pushToast({
        title: "FAQ generation queued",
        description: response.message,
        tone: "info",
      });
    } catch (submitError) {
      setIsGenerating(false);
      pushToast({
        title: "Generation failed",
        description: submitError instanceof Error ? submitError.message : "Could not start FAQ generation.",
        tone: "error",
      });
    }
  }

  async function handleBulkReview(action: "approve" | "reject") {
    if (!selectedWorkspaceId || !selectedIds.length) return;
    setIsSaving(true);
    try {
      const response = await bulkReviewFaqs({
        workspaceId: selectedWorkspaceId,
        faqIds: selectedIds,
        action,
      });
      await refreshCurrentPage();
      setSelectedIds([]);
      pushToast({
        title: action === "approve" ? "FAQs approved" : "FAQs rejected",
        description: response.message,
        tone: action === "approve" ? "success" : "info",
      });
    } catch (reviewError) {
      pushToast({
        title: "Bulk review failed",
        description: reviewError instanceof Error ? reviewError.message : "Could not update the selected FAQs.",
        tone: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSaveEdit() {
    if (!editing || !selectedWorkspaceId) return;
    setIsSaving(true);
    try {
      await updateFaq({
        workspaceId: selectedWorkspaceId,
        faqId: editing.faqId,
        question: editing.question,
        answer: editing.answer,
        category: editing.category,
        status: editing.status,
      });
      await refreshCurrentPage();
      setEditing(null);
      pushToast({
        title: "FAQ updated",
        description: "Your edits are saved and ready for review.",
        tone: "success",
      });
    } catch (saveError) {
      pushToast({
        title: "Save failed",
        description: saveError instanceof Error ? saveError.message : "Could not save FAQ changes.",
        tone: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDeleteSelected(singleId?: string) {
    if (!selectedWorkspaceId) return;
    const faqIds = singleId ? [singleId] : selectedIds;
    if (!faqIds.length) return;
    setIsSaving(true);
    try {
      const response = await deleteFaqs({ workspaceId: selectedWorkspaceId, faqIds });
      await refreshCurrentPage();
      setSelectedIds([]);
      pushToast({
        title: "FAQs deleted",
        description: response.message,
        tone: "success",
      });
    } catch (deleteError) {
      pushToast({
        title: "Delete failed",
        description: deleteError instanceof Error ? deleteError.message : "Could not delete the selected FAQs.",
        tone: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleBulkReviewSingle(faqId: string, action: "approve" | "reject") {
    if (!selectedWorkspaceId) return;
    setIsSaving(true);
    try {
      await bulkReviewFaqs({ workspaceId: selectedWorkspaceId, faqIds: [faqId], action });
      await refreshCurrentPage();
      pushToast({
        title: action === "approve" ? "FAQ approved" : "FAQ rejected",
        description: "The review state has been updated.",
        tone: action === "approve" ? "success" : "info",
      });
    } catch (reviewError) {
      pushToast({
        title: "Update failed",
        description: reviewError instanceof Error ? reviewError.message : "Could not update this FAQ.",
        tone: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading && !workspaces.length && !faqs.length) {
    return (
      <main className="space-y-6">
        <LoadingGrid rows={6} />
      </main>
    );
  }

  if (error && !workspaces.length) {
    return (
      <ErrorState
        title="FAQ dashboard could not be loaded"
        description={error}
        actionLabel="Retry loading"
        onAction={() => window.location.reload()}
      />
    );
  }

  return (
    <main className="space-y-6">
      <section className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(14,116,144,0.18),rgba(15,23,42,0.94),rgba(30,41,59,0.88))] p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/75">FAQ Studio</p>
            <h2 className="mt-3 text-3xl font-semibold text-white">Review grounded answers before they go live</h2>
            <p className="mt-3 text-sm text-slate-300">
              Generate draft FAQs from indexed documents and website pages, review them in context, then approve only the answers that are ready for customer-facing use.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-4 py-2.5 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isGenerating || isSaving}
              onClick={() => void handleGenerate(false)}
              type="button"
            >
              {isGenerating ? "Generating FAQs..." : "Generate Draft FAQs"}
            </button>
            <button
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isGenerating || isSaving}
              onClick={() => void handleGenerate(true)}
              type="button"
            >
              Force Refresh
            </button>
            <button
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/10"
              onClick={() => setExportModalOpen(true)}
              type="button"
            >
              Export Data
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-4">
          <MetricCard label="Visible FAQs" value={String(total)} hint="Current filtered result set" />
          <MetricCard label="Drafts" value={String(draftCount)} hint="Awaiting approval" />
          <MetricCard label="Approved" value={String(approvedCount)} hint="Available for chatbot fast-path" />
          <MetricCard
            label="Generation"
            value={generation?.status ? generation.status.toUpperCase() : "IDLE"}
            hint={generation?.message ?? "No generation job has run yet"}
          />
        </div>
      </section>

      <section className="rounded-[2rem] border border-white/10 bg-slate-950/70 p-5">
        <div className="grid gap-3 lg:grid-cols-[1.2fr,1fr,1fr,1fr]">
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Workspace</span>
            <select
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
              value={selectedWorkspaceId}
              onChange={(event) => {
                setSelectedWorkspaceId(event.target.value);
                setPage(1);
              }}
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name} - {workspace.role}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Category</span>
            <select
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
              value={selectedCategory}
              onChange={(event) => {
                setSelectedCategory(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All categories</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Status</span>
            <select
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
              value={selectedStatus}
              onChange={(event) => {
                setSelectedStatus(event.target.value as FAQStatus | "");
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Search</span>
            <input
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500"
              placeholder="Search questions, answers, or sources"
              type="text"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-100 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!selectedIds.length || isSaving}
            onClick={() => void handleBulkReview("approve")}
            type="button"
          >
            Bulk Approve
          </button>
          <button
            className="rounded-full border border-amber-400/20 bg-amber-500/10 px-4 py-2 text-sm font-medium text-amber-100 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!selectedIds.length || isSaving}
            onClick={() => void handleBulkReview("reject")}
            type="button"
          >
            Bulk Reject
          </button>
          <button
            className="rounded-full border border-rose-400/20 bg-rose-500/10 px-4 py-2 text-sm font-medium text-rose-100 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!selectedIds.length || isSaving}
            onClick={() => void handleDeleteSelected()}
            type="button"
          >
            Delete Selected
          </button>
          {generation && (
            <p className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300">
              {generation.message}
            </p>
          )}
        </div>
      </section>

      {isLoading ? (
        <LoadingGrid rows={4} />
      ) : error ? (
        <ErrorState
          title="FAQs could not be loaded"
          description={error}
          actionLabel="Retry"
          onAction={() => window.location.reload()}
        />
      ) : (
        <section className="space-y-4">
          {faqs.length ? (
            faqs.map((faq) => {
              const expanded = previewId === faq.id;
              const selected = selectedIds.includes(faq.id);
              return (
                <article
                  key={faq.id}
                  className="rounded-[1.75rem] border border-white/10 bg-slate-950/75 p-5 shadow-xl shadow-slate-950/20"
                >
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="flex gap-3">
                      <input
                        checked={selected}
                        className="mt-1 h-4 w-4 rounded border-white/20 bg-white/5 text-cyan-400"
                        onChange={() => toggleSelection(faq.id)}
                        type="checkbox"
                      />
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`rounded-full border px-3 py-1 text-xs font-medium ${statusTone[faq.status]}`}>
                            {faq.status}
                          </span>
                          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                            {faq.category}
                          </span>
                          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-400">
                            {Math.round(faq.confidence_score * 100)}% confidence
                          </span>
                        </div>
                        <h3 className="mt-3 text-lg font-semibold text-white">{faq.question}</h3>
                        <p className="mt-2 text-sm text-slate-300">
                          {expanded ? faq.answer : `${faq.answer.slice(0, 220)}${faq.answer.length > 220 ? "..." : ""}`}
                        </p>
                        <p className="mt-3 text-xs uppercase tracking-[0.25em] text-slate-500">Source</p>
                        <p className="mt-1 text-sm text-slate-400">{faq.source}</p>
                        {expanded && faq.citations.length > 0 ? (
                          <div className="mt-4 space-y-2 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Preview Before Publishing</p>
                            {faq.citations.map((citation, index) => (
                              <div key={`${faq.id}-${index}`} className="rounded-2xl border border-white/10 bg-slate-900/70 p-3">
                                <p className="text-sm text-white">
                                  {citation.file_name || citation.url || "Knowledge source"}
                                  {citation.page_number ? ` · page ${citation.page_number}` : ""}
                                </p>
                                <p className="mt-1 text-sm text-slate-400">{citation.chunk_preview}</p>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 xl:max-w-sm xl:justify-end">
                      <button
                        className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-sm text-white transition hover:bg-white/10"
                        onClick={() => setPreviewId((current) => (current === faq.id ? null : faq.id))}
                        type="button"
                      >
                        {expanded ? "Hide Preview" : "Preview"}
                      </button>
                      <button
                        className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-2 text-sm text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={!canManageFaqs}
                        onClick={() =>
                          setEditing({
                            faqId: faq.id,
                            question: faq.question,
                            answer: faq.answer,
                            category: faq.category,
                            status: faq.status,
                          })
                        }
                        type="button"
                      >
                        Edit
                      </button>
                      <button
                        className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={!canManageFaqs || faq.status === "approved"}
                        onClick={() => void handleBulkReviewSingle(faq.id, "approve")}
                        type="button"
                      >
                        Approve
                      </button>
                      <button
                        className="rounded-full border border-amber-400/20 bg-amber-500/10 px-3 py-2 text-sm text-amber-100 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={!canManageFaqs || faq.status === "rejected"}
                        onClick={() => void handleBulkReviewSingle(faq.id, "reject")}
                        type="button"
                      >
                        Reject
                      </button>
                      <button
                        className="rounded-full border border-rose-400/20 bg-rose-500/10 px-3 py-2 text-sm text-rose-100 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={!canManageFaqs}
                        onClick={() => void handleDeleteSelected(faq.id)}
                        type="button"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </article>
              );
            })
          ) : (
            <div className="rounded-[1.75rem] border border-dashed border-white/15 bg-slate-950/55 p-10 text-center">
              <p className="text-lg font-medium text-white">No FAQs match the current filters.</p>
              <p className="mt-2 text-sm text-slate-400">
                Generate FAQs from your indexed knowledge base or adjust the filters to review existing drafts.
              </p>
            </div>
          )}

          <div className="flex items-center justify-between rounded-[1.5rem] border border-white/10 bg-slate-950/70 px-5 py-4">
            <p className="text-sm text-slate-400">
              Page {page} of {totalPages}
            </p>
            <div className="flex gap-2">
              <button
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                type="button"
              >
                Previous
              </button>
              <button
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={page >= totalPages}
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                type="button"
              >
                Next
              </button>
            </div>
          </div>
        </section>
      )}

      {editing ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm">
          <div className="w-full max-w-3xl rounded-[2rem] border border-white/10 bg-slate-950 p-6 shadow-2xl shadow-slate-950/50">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/75">Admin Review</p>
                <h3 className="mt-2 text-2xl font-semibold text-white">Edit FAQ Before Publishing</h3>
              </div>
              <button
                className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-sm text-white transition hover:bg-white/10"
                onClick={() => setEditing(null)}
                type="button"
              >
                Close
              </button>
            </div>

            <div className="mt-6 space-y-4">
              <label className="block space-y-2">
                <span className="text-sm text-slate-300">Question</span>
                <input
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
                  value={editing.question}
                  onChange={(event) => setEditing((current) => (current ? { ...current, question: event.target.value } : current))}
                />
              </label>
              <label className="block space-y-2">
                <span className="text-sm text-slate-300">Answer</span>
                <textarea
                  className="min-h-40 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
                  value={editing.answer}
                  onChange={(event) => setEditing((current) => (current ? { ...current, answer: event.target.value } : current))}
                />
              </label>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="block space-y-2">
                  <span className="text-sm text-slate-300">Category</span>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
                    value={editing.category}
                    onChange={(event) => setEditing((current) => (current ? { ...current, category: event.target.value } : current))}
                  />
                </label>
                <label className="block space-y-2">
                  <span className="text-sm text-slate-300">Status</span>
                  <select
                    className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
                    value={editing.status}
                    onChange={(event) => setEditing((current) => (current ? { ...current, status: event.target.value as FAQStatus } : current))}
                  >
                    <option value="draft">Draft</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                  </select>
                </label>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/10"
                onClick={() => setEditing(null)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-4 py-2.5 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={isSaving}
                onClick={() => void handleSaveEdit()}
                type="button"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <ExportModal
        open={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        exportType="faq"
        workspaceId={selectedWorkspaceId}
        title="Export approved FAQs"
        description="Queue a workspace-safe export for FAQs in CSV, JSON, or a client-ready PDF packet."
        initialFilters={{
          status: selectedStatus || "approved",
          category: selectedCategory,
        }}
      />
    </main>
  );
}

function MetricCard(props: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.04] p-4">
      <p className="text-xs uppercase tracking-[0.25em] text-slate-400">{props.label}</p>
      <p className="mt-3 text-2xl font-semibold text-white">{props.value}</p>
      <p className="mt-2 text-sm text-slate-400">{props.hint}</p>
    </div>
  );
}
