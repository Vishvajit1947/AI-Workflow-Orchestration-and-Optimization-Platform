/**
 * Shared chart building blocks: color roles, the chart card (title, legend,
 * chart/table toggle, empty state), a container-width hook and the hover tooltip.
 *
 * Colors: charts sit on Mercury's white card surface. Slot 1 is Mercury Indigo, slot 2 the
 * reference orange; validated (validate_palette.js --mode light --surface #ffffff): all checks
 * pass (adjacent CVD ΔE 29.4, normal-vision ΔE 35.3, both >= 3:1 contrast).
 */
import React, { useEffect, useRef, useState } from 'react';
import { motion, useInView } from 'motion/react';
import { fadeUp } from '../../lib/motion';
import { BarChart3, Table2 } from 'lucide-react';

export const CHART = {
  series1: '#5266eb',        // Mercury Indigo
  series2: '#eb6834',        // orange
  track: 'rgba(82,102,235,0.14)', // meter track: same hue as series1, receded
  grid: '#efeef5',           // hairline gridlines
  baseline: '#d9d8e5',       // axis baseline
  muted: '#6f6a8a',          // axis labels (ink-muted)
  text: '#28253b',           // value labels (ink)
  textSecondary: '#554e7b',  // category labels (ink-secondary)
  surface: '#ffffff',        // card surface (for surface gaps/rings)
  crosshair: '#9a97ad',
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
  // Marks animate in once the chart is visible; afterwards value changes glide (viz-live)
  const plot = useRef<HTMLDivElement>(null);
  const inView = useInView(plot, { once: true, amount: 0.3 });
  const [settled, setSettled] = useState(false);
  useEffect(() => {
    if (!inView) return;
    const timer = setTimeout(() => setSettled(true), 1200);
    return () => clearTimeout(timer);
  }, [inView]);
  return (
    <motion.section
      className={`card min-w-0 p-5 sm:p-6 ${className}`}
      aria-label={title}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.15 }}
      variants={fadeUp}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[15px] font-medium text-ink">{title}</h3>
          {subtitle && <p className="mt-1 text-xs leading-relaxed text-ink-muted">{subtitle}</p>}
        </div>
        {table && !empty && (
          <button
            onClick={() => setShowTable(!showTable)}
            className="btn btn-ghost btn-sm -mr-2 -mt-1 shrink-0"
            aria-pressed={showTable}
          >
            {showTable ? <><BarChart3 size={13} /> Chart</> : <><Table2 size={13} /> Table</>}
          </button>
        )}
      </div>
      {legend && legend.length > 1 && !empty && !showTable && (
        <div className="mb-3 flex flex-wrap gap-4 text-xs text-ink-secondary">
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
        <div className="flex h-40 items-center justify-center rounded-card bg-lavender-soft text-sm text-ink-muted">{emptyText}</div>
      ) : showTable ? (
        <div className="max-h-72 animate-fade-in overflow-x-auto">{table}</div>
      ) : (
        <div ref={plot} className={`viz-wait ${inView ? 'viz-in' : ''} ${settled ? 'viz-live' : ''}`}>{children}</div>
      )}
    </motion.section>
  );
};

/** Plain data table used as every chart's table view. */
export const DataTable: React.FC<{ headers: string[]; rows: (string | number)[][]; align?: ('left' | 'right')[] }> = ({
  headers, rows, align,
}) => (
  <div className="overflow-x-auto">
    <table className="w-full text-xs">
      <thead className="border-b border-hairline text-ink-muted">
        <tr>
          {headers.map((h, i) => (
            <th key={h} className={`whitespace-nowrap px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.05em] ${align?.[i] === 'left' ? 'text-left' : 'text-right'}`}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody className="tabular-nums">
        {rows.map((row, r) => (
          <tr key={r} className="border-b border-hairline text-ink last:border-b-0">
            {row.map((cell, i) => (
              <td key={i} className={`px-2 py-2 ${align?.[i] === 'left' ? 'text-left' : 'text-right'}`}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
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
      className="pointer-events-none absolute z-10 animate-pop-in rounded-[10px] border border-hairline bg-surface px-3 py-2 text-xs shadow-pop"
      style={{ left: flip ? undefined : x + 12, right: flip ? width - x + 12 : undefined, top: Math.max(0, y - 10) }}
    >
      <div className="mb-1 text-ink-muted">{title}</div>
      {rows.map((row) => (
        <div key={row.label} className="flex items-center gap-2 whitespace-nowrap">
          {row.color && <span className="w-3 h-0.5 rounded" style={{ background: row.color }} />}
          <span className="font-medium text-ink tabular-nums">{row.value}</span>
          <span className="text-ink-muted">{row.label}</span>
        </div>
      ))}
    </div>
  );
};
