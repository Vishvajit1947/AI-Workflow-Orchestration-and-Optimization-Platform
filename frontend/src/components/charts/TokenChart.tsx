/**
 * Daily tokens as stacked columns: input (slot 1) under output (slot 2), 2px surface
 * gap between segments, rounded data-end on top, per-column hover.
 */
import React, { useState } from 'react';
import type { TokenTrendPoint } from '../../types/analytics';
import { formatCompact, formatDay, niceTicks } from '../../lib/format';
import { CHART, ChartCard, ChartTooltip, DataTable, dayLabelIndexes, useWidth } from './chartKit';

const HEIGHT = 200;
const M = { top: 12, right: 8, bottom: 24, left: 48 };
const GAP = 2;

/** Column path with 4px rounded top corners and a square base. */
const topRounded = (x: number, y: number, w: number, h: number) => {
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
};

export const TokenChart: React.FC<{ data: TokenTrendPoint[] }> = ({ data }) => {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const total = data.reduce((sum, p) => sum + p.total_tokens, 0);

  const plotW = Math.max(width - M.left - M.right, 10);
  const plotH = HEIGHT - M.top - M.bottom;
  const ticks = niceTicks(Math.max(...data.map((p) => p.total_tokens), 0));
  const yMax = ticks[ticks.length - 1];
  const scale = (v: number) => (v / yMax) * plotH;
  const band = plotW / Math.max(data.length, 1);
  const barW = Math.min(24, Math.max(band - 4, 2));
  const labeled = dayLabelIndexes(data.length, plotW);
  const base = M.top + plotH;

  const point = hover !== null ? data[hover] : null;
  return (
    <ChartCard
      title="Tokens per day"
      subtitle={`${formatCompact(total)} tokens (LLM calls; cache hits use none)`}
      legend={[{ label: 'Input', color: CHART.series1 }, { label: 'Output', color: CHART.series2 }]}
      empty={total === 0}
      table={<DataTable headers={['Day', 'Input', 'Output', 'Total']} align={['left']}
        rows={data.map((p) => [p.date, p.input_tokens.toLocaleString(), p.output_tokens.toLocaleString(), p.total_tokens.toLocaleString()])} />}
    >
      <div ref={ref} className="relative">
        <svg width={width} height={HEIGHT} role="img" aria-label={`Daily token usage, ${formatCompact(total)} total`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={M.left + plotW} y1={base - scale(t)} y2={base - scale(t)} stroke={t === 0 ? CHART.baseline : CHART.grid} />
              <text x={M.left - 8} y={base - scale(t)} dy="0.32em" textAnchor="end" fill={CHART.muted} fontSize={11}>{formatCompact(t)}</text>
            </g>
          ))}
          {data.map((p, i) => {
            const cx = M.left + band * i + band / 2;
            const inH = scale(p.input_tokens);
            const outH = scale(p.output_tokens);
            const outVisible = outH > 0;
            return (
              <g key={p.date} data-testid={`token-column-${p.date}`} opacity={hover === null || hover === i ? 1 : 0.55}>
                {inH > 0 && (outVisible
                  ? <rect x={cx - barW / 2} y={base - inH} width={barW} height={inH} fill={CHART.series1} />
                  : <path d={topRounded(cx - barW / 2, base - inH, barW, inH)} fill={CHART.series1} />)}
                {outVisible && (
                  <path d={topRounded(cx - barW / 2, base - inH - GAP - outH, barW, outH)} fill={CHART.series2} />
                )}
                {labeled.has(i) && (
                  <text x={cx} y={HEIGHT - 6} fill={CHART.muted} fontSize={11}
                        textAnchor={i === data.length - 1 ? 'end' : i === 0 ? 'start' : 'middle'}>{formatDay(p.date)}</text>
                )}
                {/* Hit target: the whole band, taller than the mark */}
                <rect x={M.left + band * i} y={M.top} width={band} height={plotH} fill="transparent"
                      onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} />
              </g>
            );
          })}
        </svg>
        {point && hover !== null && (
          <ChartTooltip x={M.left + band * hover + band / 2} y={base - scale(point.total_tokens)} width={width}
            title={formatDay(point.date)} rows={[
              { label: 'input', value: point.input_tokens.toLocaleString(), color: CHART.series1 },
              { label: 'output', value: point.output_tokens.toLocaleString(), color: CHART.series2 },
            ]} />
        )}
      </div>
    </ChartCard>
  );
};
