"use client";

import type { BreakdownItem, TimeSeriesPoint } from "@/lib/analytics";

type PanelProps = {
  title: string;
  subtitle: string;
  children: React.ReactNode;
};

type LineChartProps = {
  title: string;
  subtitle: string;
  data: TimeSeriesPoint[];
  color: string;
};

type BarChartProps = {
  title: string;
  subtitle: string;
  data: BreakdownItem[];
  color: string;
};

type DonutChartProps = {
  title: string;
  subtitle: string;
  data: BreakdownItem[];
  colors: string[];
};

export function ChartPanel({ title, subtitle, children }: PanelProps) {
  return (
    <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
        </div>
      </div>
      <div className="mt-6">{children}</div>
    </section>
  );
}

export function LineChartCard({ title, subtitle, data, color }: LineChartProps) {
  const width = 640;
  const height = 220;
  const left = 24;
  const bottom = 28;
  const top = 12;
  const right = 12;
  const max = Math.max(...data.map((point) => point.value), 1);
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  const points = data.length
    ? data
        .map((point, index) => {
          const x = left + (chartWidth * index) / Math.max(data.length - 1, 1);
          const y = top + chartHeight - (point.value / max) * chartHeight;
          return `${x},${y}`;
        })
        .join(" ")
    : "";

  return (
    <ChartPanel title={title} subtitle={subtitle}>
      {data.length ? (
        <svg className="h-56 w-full" viewBox={`0 0 ${width} ${height}`} role="img">
          <line x1={left} x2={width - right} y1={height - bottom} y2={height - bottom} stroke="rgba(148,163,184,0.35)" />
          <line x1={left} x2={left} y1={top} y2={height - bottom} stroke="rgba(148,163,184,0.2)" />
          <polyline
            fill="none"
            points={points}
            stroke={color}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="4"
          />
          {data.map((point, index) => {
            const x = left + (chartWidth * index) / Math.max(data.length - 1, 1);
            const y = top + chartHeight - (point.value / max) * chartHeight;
            return <circle key={`${point.bucket}-${index}`} cx={x} cy={y} fill={color} r="4.5" />;
          })}
          {data.map((point, index) => {
            const x = left + (chartWidth * index) / Math.max(data.length - 1, 1);
            return (
              <text
                key={`label-${point.bucket}-${index}`}
                fill="rgba(203,213,225,0.8)"
                fontSize="11"
                textAnchor="middle"
                x={x}
                y={height - 8}
              >
                {(point.label ?? point.bucket).slice(5)}
              </text>
            );
          })}
        </svg>
      ) : (
        <EmptyChartState />
      )}
    </ChartPanel>
  );
}

export function BarChartCard({ title, subtitle, data, color }: BarChartProps) {
  const max = Math.max(...data.map((item) => item.value), 1);
  return (
    <ChartPanel title={title} subtitle={subtitle}>
      {data.length ? (
        <div className="space-y-3">
          {data.map((item) => (
            <div key={item.label}>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-200">{item.label}</span>
                <span className="text-slate-400">{formatNumber(item.value)}</span>
              </div>
              <div className="mt-2 h-3 rounded-full bg-white/5">
                <div
                  className="h-3 rounded-full"
                  style={{ width: `${Math.max((item.value / max) * 100, 8)}%`, background: color }}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyChartState />
      )}
    </ChartPanel>
  );
}

export function DonutChartCard({ title, subtitle, data, colors }: DonutChartProps) {
  const total = data.reduce((sum, item) => sum + item.value, 0);
  let startAngle = -90;

  return (
    <ChartPanel title={title} subtitle={subtitle}>
      {data.length && total > 0 ? (
        <div className="grid gap-6 md:grid-cols-[220px_1fr] md:items-center">
          <svg className="mx-auto h-52 w-52" viewBox="0 0 220 220" role="img">
            {data.map((item, index) => {
              const sweep = (item.value / total) * 360;
              const path = describeArc(110, 110, 76, startAngle, startAngle + sweep);
              const fill = colors[index % colors.length];
              startAngle += sweep;
              return <path key={item.label} d={path} fill="none" stroke={fill} strokeWidth="28" />;
            })}
            <circle cx="110" cy="110" fill="#020617" r="52" />
            <text fill="white" fontSize="26" fontWeight="600" textAnchor="middle" x="110" y="104">
              {formatNumber(total)}
            </text>
            <text fill="rgba(148,163,184,0.85)" fontSize="12" textAnchor="middle" x="110" y="126">
              total
            </text>
          </svg>
          <div className="space-y-3">
            {data.map((item, index) => (
              <div key={item.label} className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span
                    className="h-3 w-3 rounded-full"
                    style={{ background: colors[index % colors.length] }}
                  />
                  <span className="text-sm text-slate-200">{item.label}</span>
                </div>
                <span className="text-sm text-slate-400">
                  {formatNumber(item.value)} ({Math.round((item.value / total) * 100)}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <EmptyChartState />
      )}
    </ChartPanel>
  );
}

function EmptyChartState() {
  return (
    <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/40 px-5 py-10 text-center text-sm text-slate-500">
      No data is available for the current filter set.
    </div>
  );
}

function polarToCartesian(centerX: number, centerY: number, radius: number, angleInDegrees: number) {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0;
  return {
    x: centerX + radius * Math.cos(angleInRadians),
    y: centerY + radius * Math.sin(angleInRadians),
  };
}

function describeArc(x: number, y: number, radius: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(x, y, radius, endAngle);
  const end = polarToCartesian(x, y, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return ["M", start.x, start.y, "A", radius, radius, 0, largeArcFlag, 0, end.x, end.y].join(" ");
}

function formatNumber(value: number) {
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(2);
}
