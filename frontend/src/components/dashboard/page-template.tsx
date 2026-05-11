"use client";

import { useEffect, useMemo, useState } from "react";

import { useToast } from "@/components/toast-provider";
import { EmptyState, ErrorState, LoadingGrid } from "@/components/dashboard/page-states";

type Metric = {
  label: string;
  value: string;
  hint: string;
};

type CardItem = {
  id: string;
  title: string;
  subtitle: string;
  meta: string;
  badge?: string;
};

type DashboardPageTemplateProps = {
  eyebrow: string;
  title: string;
  description: string;
  metrics: Metric[];
  items: CardItem[];
  emptyTitle: string;
  emptyDescription: string;
  errorTitle: string;
  errorDescription: string;
  primaryActionLabel: string;
  primaryActionToast: {
    title: string;
    description: string;
  };
};

type ViewState = "loading" | "ready" | "empty" | "error";

export function DashboardPageTemplate({
  eyebrow,
  title,
  description,
  metrics,
  items,
  emptyTitle,
  emptyDescription,
  errorTitle,
  errorDescription,
  primaryActionLabel,
  primaryActionToast,
}: DashboardPageTemplateProps) {
  const { pushToast } = useToast();
  const [viewState, setViewState] = useState<ViewState>("loading");

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setViewState(items.length ? "ready" : "empty");
    }, 700);

    return () => window.clearTimeout(timeout);
  }, [items.length]);

  const renderedItems = useMemo(() => {
    if (viewState !== "ready") {
      return [];
    }
    return items;
  }, [items, viewState]);

  function resetToDefault() {
    setViewState("loading");
    window.setTimeout(() => {
      setViewState(items.length ? "ready" : "empty");
    }, 650);
  }

  return (
    <main className="space-y-8">
      <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(6,182,212,0.14),transparent_30%),linear-gradient(140deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">{eyebrow}</p>
            <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">{title}</h2>
            <p className="mt-4 text-base text-slate-300">{description}</p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-slate-950"
              onClick={() =>
                pushToast({
                  title: primaryActionToast.title,
                  description: primaryActionToast.description,
                  tone: "success",
                })
              }
              type="button"
            >
              {primaryActionLabel}
            </button>
            <button
              className="rounded-full border border-white/10 bg-white/5 px-5 py-2.5 text-sm text-slate-200"
              onClick={() => setViewState("empty")}
              type="button"
            >
              Show empty state
            </button>
            <button
              className="rounded-full border border-white/10 bg-white/5 px-5 py-2.5 text-sm text-slate-200"
              onClick={() => setViewState("error")}
              type="button"
            >
              Show error state
            </button>
            <button
              className="rounded-full border border-white/10 bg-white/5 px-5 py-2.5 text-sm text-slate-200"
              onClick={resetToDefault}
              type="button"
            >
              Reload
            </button>
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {metrics.map((metric) => (
            <div
              key={metric.label}
              className="rounded-3xl border border-white/10 bg-white/[0.04] p-5"
            >
              <p className="text-sm text-slate-400">{metric.label}</p>
              <p className="mt-3 text-3xl font-semibold text-white">{metric.value}</p>
              <p className="mt-2 text-sm text-slate-500">{metric.hint}</p>
            </div>
          ))}
        </div>
      </section>

      {viewState === "loading" ? <LoadingGrid rows={4} /> : null}
      {viewState === "empty" ? (
        <EmptyState
          actionLabel={primaryActionLabel}
          description={emptyDescription}
          onAction={() =>
            pushToast({
              title: primaryActionToast.title,
              description: primaryActionToast.description,
              tone: "info",
            })
          }
          title={emptyTitle}
        />
      ) : null}
      {viewState === "error" ? (
        <ErrorState
          actionLabel="Retry loading"
          description={errorDescription}
          onAction={resetToDefault}
          title={errorTitle}
        />
      ) : null}

      {viewState === "ready" ? (
        <section className="grid gap-4 xl:grid-cols-2">
          {renderedItems.map((item) => (
            <article
              key={item.id}
              className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 transition hover:border-cyan-400/20 hover:bg-white/[0.06]"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                  <p className="mt-2 text-sm text-slate-400">{item.subtitle}</p>
                </div>
                {item.badge ? (
                  <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs font-medium text-cyan-100">
                    {item.badge}
                  </span>
                ) : null}
              </div>
              <div className="mt-6 flex items-center justify-between text-sm text-slate-500">
                <span>{item.meta}</span>
                <button
                  className="rounded-full border border-white/10 px-3 py-1.5 text-slate-300"
                  onClick={() =>
                    pushToast({
                      title: `${item.title} selected`,
                      description: "This action is wired for demo shell interactions.",
                      tone: "info",
                    })
                  }
                  type="button"
                >
                  Open
                </button>
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </main>
  );
}

