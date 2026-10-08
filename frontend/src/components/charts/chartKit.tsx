/**
 * Shared chart building blocks: color roles, the chart card (title, legend,
 * chart/table toggle, empty state), a container-width hook and the hover tooltip.
 *
 * Colors: the app is dark-only; series slots are the dark steps of the reference
 * categorical palette, validated (validate_palette.js) against the card surface #0b1224.
 */
import React, { useEffect, useRef, useState } from 'react';
import { BarChart3, Table2 } from 'lucide-react';

export const CHART = {
  series1: '#3987e5',        // blue
  series2: '#d95926',        // orange
  track: 'rgba(57,135,229,0.18)', // meter track: same ramp as series1, receded
  grid: '#2e2e2e',           // hairline gridlines
  baseline: '#3e3e3e',       // axis baseline
  muted: '#94a3b8',          // axis labels
  surface: '#1c1c1c',        // card surface (for surface gaps/rings)
  crosshair: '#64748b',
};

/** Status palette (reserved for state; always paired with an icon + label). */
export const STATUS = {
  completed: { color: '#0ca30c', label: 'Completed', icon: '✓' },
  failed: { color: '#d03b3b', label: 'Failed', icon: '✕' },
  cancelled: { color: '#898781', label: 'Cancelled', icon: '■' },
  skipped: { color: '#fab219', label: 'Skipped', icon: '↷' },
} as const;

/** Which x positions get a day label: every `every`-th, plus the last, skipping ones too close to the last. */
export const dayLabelIndexes = (count: number, plotWidth: number, minGap = 70): Set<number> => {
  const every = Math.ceil(count / Math.max(Math.floor(plotWidth / minGap), 1));
  const last = count - 1;
  const picked = new Set<number>([last]);
  for (let i = 0; i < count; i += every) if (last - i >= every) picked.add(i);
  return picked;
};

export const statusStyle = (status: string) =>
  STATUS[status as keyof typeof STATUS] ?? { color: CHART.muted, label: status, icon: '•' };

/** Measures the container so SVG text stays at its real pixel size (no viewBox scaling). */
export function useWidth<T extends HTMLElement>(fallback = 560) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (el.clientWidth) setWidth(el.clientWidth);
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width) setWidth(Math.floor(entry.contentRect.width));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

export interface LegendItem {
  label: string;
  color: string;
  shape?: 'rect' | 'line';
}

interface ChartCardProps {
  title: string;
  subtitle?: string;
  legend?: LegendItem[];
  empty?: boolean;
  emptyText?: string;
  table?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export const ChartCard: React.FC<ChartCardProps> = ({
  title, subtitle, legend, empty, emptyText = 'No data in this range', table, children, className = '',
}) => {
  const [showTable, setShowTable] = useState(false);
  return (
    <section className={`glass rounded-xl p-5 ${className}`} aria-label={title}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="font-semibold">{title}</h3>
          {subtitle && <p className="text-xs text-surface-200/50 mt-0.5">{subtitle}</p>}
        </div>
        {table && !empty && (
          <button
            onClick={() => setShowTable(!showTable)}
            className="flex items-center gap-1 text-xs text-surface-200/50 hover:text-white transition-colors shrink-0"
            aria-pressed={showTable}
          >
            {showTable ? <><BarChart3 size={13} /> Chart</> : <><Table2 size={13} /> Table</>}
          </button>
        )}
      </div>
      {legend && legend.length > 1 && !empty && !showTable && (
        <div className="flex flex-wrap gap-4 mb-2 text-xs text-surface-200/70">
          {legend.map((item) => (
            <span key={item.label} className="flex items-center gap-1.5">
              {item.shape === 'line'
                ? <span className="w-3 h-0.5 rounded" style={{ background: item.color }} />
                : <span className="w-2.5 h-2.5 rounded-sm" style={{ background: item.color }} />}
              {item.label}
            </span>
          ))}
        </div>
      )}
      {empty ? (
        <div className="h-40 flex items-center justify-center text-sm text-surface-200/40">{emptyText}</div>
      ) : showTable ? (
        <div className="overflow-x-auto max-h-72">{table}</div>
      ) : (
        children
      )}
    </section>
  );
};

/** Plain data table used as every chart's table view. */
export const DataTable: React.FC<{ headers: string[]; rows: (string | number)[][]; align?: ('left' | 'right')[] }> = ({
  headers, rows, align,
}) => (
  <table className="w-full text-xs">
    <thead className="text-surface-200/50 border-b border-surface-700/60">
      <tr>
        {headers.map((h, i) => (
          <th key={h} className={`px-2 py-1.5 font-medium ${align?.[i] === 'left' ? 'text-left' : 'text-right'}`}>{h}</th>
        ))}
      </tr>
    </thead>
    <tbody className="tabular-nums">
      {rows.map((row, r) => (
        <tr key={r} className="border-b border-surface-700/30">
          {row.map((cell, i) => (
            <td key={i} className={`px-2 py-1.5 ${align?.[i] === 'left' ? 'text-left' : 'text-right'}`}>{cell}</td>
          ))}
        </tr>
      ))}
    </tbody>
  </table>
);

export interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

/** Hover readout: value first (strong), series name after; line keys, not boxes. */
export const ChartTooltip: React.FC<{ x: number; y: number; width: number; title: string; rows: TooltipRow[] }> = ({
  x, y, width, title, rows,
}) => {
  const flip = x > width - 180;
  return (
    <div
      role="tooltip"
      className="absolute z-10 pointer-events-none rounded-lg border border-surface-700 bg-surface-900/95 px-3 py-2 text-xs shadow-lg"
      style={{ left: flip ? undefined : x + 12, right: flip ? width - x + 12 : undefined, top: Math.max(0, y - 10) }}
    >
      <div className="text-surface-200/60 mb-1">{title}</div>
      {rows.map((row) => (
        <div key={row.label} className="flex items-center gap-2 whitespace-nowrap">
          {row.color && <span className="w-3 h-0.5 rounded" style={{ background: row.color }} />}
          <span className="font-semibold text-white tabular-nums">{row.value}</span>
          <span className="text-surface-200/60">{row.label}</span>
        </div>
      ))}
    </div>
  );
};
