/**
 * Daily cost: one series, 2px line over a 10% area wash, crosshair snapping to the nearest day.
 */
import React, { useState } from 'react';
import type { CostTrendPoint } from '../../types/analytics';
import { formatDay, formatUSD, niceTicks } from '../../lib/format';
import { CHART, ChartCard, ChartTooltip, DataTable, dayLabelIndexes, useWidth } from './chartKit';

const HEIGHT = 200;
const M = { top: 12, right: 12, bottom: 24, left: 56 };

export const CostChart: React.FC<{ data: CostTrendPoint[] }> = ({ data }) => {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const total = data.reduce((sum, p) => sum + p.cost, 0);

  const plotW = Math.max(width - M.left - M.right, 10);
  const plotH = HEIGHT - M.top - M.bottom;
  const ticks = niceTicks(Math.max(...data.map((p) => p.cost), 0));
  const yMax = ticks[ticks.length - 1];
  const x = (i: number) => M.left + (data.length > 1 ? (i / (data.length - 1)) * plotW : plotW / 2);
  const y = (v: number) => M.top + plotH - (v / yMax) * plotH;

  const line = data.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.cost)}`).join(' ');
  const area = `${line} L${x(data.length - 1)},${y(0)} L${x(0)},${y(0)} Z`;
  const labeled = dayLabelIndexes(data.length, plotW);
  const last = data.length - 1;

  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = (e.clientX - rect.left) / rect.width;
    setHover(Math.min(last, Math.max(0, Math.round(rel * last))));
  };

  const point = hover !== null ? data[hover] : null;
  return (
    <ChartCard
      title="Cost per day"
      subtitle={`${formatUSD(total)} over ${data.length} days (UTC)`}
      empty={total === 0}
      emptyText="No LLM spend in this range"
      table={<DataTable headers={['Day', 'Cost', 'Executions', 'LLM calls', 'Cache hits']} align={['left']}
        rows={data.map((p) => [p.date, formatUSD(p.cost), p.executions, p.llm_calls, p.cache_hits])} />}
    >
      <div ref={ref} className="relative">
        <svg width={width} height={HEIGHT} role="img" aria-label={`Daily cost line chart, total ${formatUSD(total)}`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={M.left + plotW} y1={y(t)} y2={y(t)} stroke={t === 0 ? CHART.baseline : CHART.grid} />
              <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fill={CHART.muted} fontSize={11} className="tabular-nums">
                {formatUSD(t)}
              </text>
            </g>
          ))}
          {data.map((p, i) => labeled.has(i) && (
            <text key={p.date} x={x(i)} y={HEIGHT - 6} textAnchor={i === last ? 'end' : i === 0 ? 'start' : 'middle'}
                  fill={CHART.muted} fontSize={11}>
              {formatDay(p.date)}
            </text>
          ))}
          <path d={area} fill={CHART.series1} opacity={0.1} />
          <path d={line} fill="none" stroke={CHART.series1} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {/* End marker + selective direct label on the latest day */}
          <circle cx={x(last)} cy={y(data[last].cost)} r={4} fill={CHART.series1} stroke={CHART.surface} strokeWidth={2} />
          {point && hover !== null && (
            <>
              <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + plotH} stroke={CHART.crosshair} />
              <circle cx={x(hover)} cy={y(point.cost)} r={4} fill={CHART.series1} stroke={CHART.surface} strokeWidth={2} />
            </>
          )}
          <rect x={M.left} y={M.top} width={plotW} height={plotH} fill="transparent" data-testid="cost-hit-area"
                onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
        </svg>
        {point && hover !== null && (
          <ChartTooltip x={x(hover)} y={y(point.cost)} width={width} title={formatDay(point.date)} rows={[
            { label: 'cost', value: formatUSD(point.cost), color: CHART.series1 },
            { label: 'executions', value: String(point.executions) },
            { label: 'LLM calls', value: String(point.llm_calls) },
          ]} />
        )}
      </div>
    </ChartCard>
  );
};
