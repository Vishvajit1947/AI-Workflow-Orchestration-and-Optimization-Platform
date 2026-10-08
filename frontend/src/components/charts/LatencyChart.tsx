/**
 * Latency percentiles of LLM calls (P50..P99) as single-hue columns, value on each cap.
 */
import React, { useState } from 'react';
import type { LatencyMetrics } from '../../types/analytics';
import { formatDuration, niceTicks } from '../../lib/format';
import { CHART, ChartCard, ChartTooltip, DataTable, useWidth } from './chartKit';

const HEIGHT = 200;
const M = { top: 20, right: 8, bottom: 24, left: 56 };
const KEYS = ['p50', 'p75', 'p90', 'p95', 'p99'] as const;

export const LatencyChart: React.FC<{ data: LatencyMetrics }> = ({ data }) => {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const points = KEYS.map((k) => ({ key: k, label: k.toUpperCase(), value: data[k] }));

  const plotW = Math.max(width - M.left - M.right, 10);
  const plotH = HEIGHT - M.top - M.bottom;
  const ticks = niceTicks(data.max_ms || Math.max(...points.map((p) => p.value), 0));
  const yMax = ticks[ticks.length - 1];
  const scale = (v: number) => (v / yMax) * plotH;
  const band = plotW / points.length;
  const barW = Math.min(24, band - 8);
  const base = M.top + plotH;

  const topRounded = (x: number, y: number, w: number, h: number) => {
    const r = Math.min(4, w / 2, h);
    return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
  };

  return (
    <ChartCard
      title="LLM latency percentiles"
      subtitle={`${data.sample_count} calls · avg ${formatDuration(data.avg_ms)} · range ${formatDuration(data.min_ms)}–${formatDuration(data.max_ms)}`}
      empty={data.sample_count === 0}
      emptyText="No LLM calls in this range"
      table={<DataTable headers={['Percentile', 'Latency']} align={['left']}
        rows={[...points.map((p) => [p.label, formatDuration(p.value)]), ['Average', formatDuration(data.avg_ms)], ['Max', formatDuration(data.max_ms)]]} />}
    >
      <div ref={ref} className="relative">
        <svg width={width} height={HEIGHT} role="img" aria-label="Latency percentiles column chart">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={M.left + plotW} y1={base - scale(t)} y2={base - scale(t)} stroke={t === 0 ? CHART.baseline : CHART.grid} />
              <text x={M.left - 8} y={base - scale(t)} dy="0.32em" textAnchor="end" fill={CHART.muted} fontSize={11}>{formatDuration(t)}</text>
            </g>
          ))}
          {points.map((p, i) => {
            const cx = M.left + band * i + band / 2;
            const h = Math.max(scale(p.value), p.value > 0 ? 2 : 0);
            return (
              <g key={p.key} data-testid={`latency-${p.key}`} onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)}>
                <rect x={M.left + band * i} y={M.top} width={band} height={plotH} fill="transparent" />
                {h > 0 && <path d={topRounded(cx - barW / 2, base - h, barW, h)} fill={CHART.series1}
                                opacity={hover === null || hover === i ? 1 : 0.55} />}
                <text x={cx} y={base - h - 6} textAnchor="middle" fill="#e2e8f0" fontSize={11}>{formatDuration(p.value)}</text>
                <text x={cx} y={HEIGHT - 6} textAnchor="middle" fill={CHART.muted} fontSize={11}>{p.label}</text>
              </g>
            );
          })}
        </svg>
        {hover !== null && (
          <ChartTooltip x={M.left + band * hover + band / 2} y={base - scale(points[hover].value)} width={width}
            title={`${points[hover].key.slice(1)}% of LLM calls finished within`}
            rows={[{ label: points[hover].label, value: formatDuration(points[hover].value), color: CHART.series1 }]} />
        )}
      </div>
    </ChartCard>
  );
};
