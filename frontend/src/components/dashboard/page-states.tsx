type EmptyStateProps = {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
};

type ErrorStateProps = {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function LoadingGrid({ rows = 4 }: { rows?: number }) {
  return (
    <div className="grid gap-4">
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="h-24 animate-pulse rounded-3xl border border-white/10 bg-white/5"
        />
      ))}
    </div>
  );
}

export function EmptyState({ title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <section className="rounded-[2rem] border border-dashed border-white/15 bg-white/[0.03] p-10 text-center">
      <div className="mx-auto max-w-lg">
        <p className="text-sm uppercase tracking-[0.3em] text-cyan-200/70">Nothing here yet</p>
        <h3 className="mt-3 text-2xl font-semibold text-white">{title}</h3>
        <p className="mt-3 text-slate-400">{description}</p>
        {actionLabel && onAction ? (
          <button
            className="mt-6 rounded-full border border-cyan-400/25 bg-cyan-400/10 px-5 py-2.5 text-sm font-medium text-cyan-100"
            onClick={onAction}
            type="button"
          >
            {actionLabel}
          </button>
        ) : null}
      </div>
    </section>
  );
}

export function ErrorState({ title, description, actionLabel, onAction }: ErrorStateProps) {
  return (
    <section className="rounded-[2rem] border border-rose-400/20 bg-rose-500/10 p-8">
      <p className="text-sm uppercase tracking-[0.3em] text-rose-100/80">Attention needed</p>
      <h3 className="mt-3 text-2xl font-semibold text-white">{title}</h3>
      <p className="mt-3 max-w-2xl text-rose-100/80">{description}</p>
      {actionLabel && onAction ? (
        <button
          className="mt-6 rounded-full border border-rose-200/20 bg-rose-200/10 px-5 py-2.5 text-sm font-medium text-rose-50"
          onClick={onAction}
          type="button"
        >
          {actionLabel}
        </button>
      ) : null}
    </section>
  );
}

