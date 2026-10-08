/**
 * Gantt view of one execution: a row per stage run, bar from its start to its end on a
 * shared time axis, so parallel stages show as overlapping bars. Status color is always
 * paired with an icon + label.
 */
import React, { useEffect, useState } from 'react';
import { analyticsApi } from '../../api/analyticsApi';
import type { ExecutionTimeline, TimelineStage } from '../../types/analytics';
import { formatDuration, formatUSD, niceTicks } from '../../lib/format';
import { CHART, ChartTooltip, DataTable, statusStyle, useWidth } from './chartKit';

const ROW = 28;
const BAR = 14;
const LABEL_W = 170;
const AXIS_H = 22;

/** `dark` for dark pages; default styling suits the light execution-results card. */
export const TimelineChart: React.FC<{ timeline: ExecutionTimeline; dark?: boolean }> = ({ timeline, dark = false }) => {
  const strong = dark ? 'text-white' : 'text-gray-900';
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  const stages = timeline.stages;
  const trackW = Math.max(width - LABEL_W - 16, 20);
  const ticks = niceTicks(Math.max(timeline.total_duration_ms, 1), 5);
  const span = ticks[ticks.length - 1];
  const x = (ms: number) => LABEL_W + (ms / span) * trackW;
  const height = stages.length * ROW + AXIS_H;
  const statuses = [...new Set(stages.map((s) => (s.cache_hit ? 'cache' : s.status)))];

  const hovered: TimelineStage | null = hover !== null ? stages[hover] : null;
  return (
    <div>
      <div className={`flex flex-wrap items-center justify-between gap-2 mb-3 text-sm ${dark ? 'text-surface-200/60' : 'text-gray-600'}`}>
        <span>
          Wall-clock <strong className={strong}>{formatDuration(timeline.total_duration_ms)}</strong>
          {' · '}
          {timeline.parallelism > 1.05
            ? <>stages overlapped: <strong className={strong}>{timeline.parallelism.toFixed(2)}x</strong> work per unit of time</>
            : 'stages ran one after another'}
        </span>
        <button onClick={() => setShowTable(!showTable)} className={`text-xs ${dark ? 'text-primary-400 hover:text-primary-300' : 'text-blue-600 hover:text-blue-700'}`}>
          {showTable ? 'Show chart' : 'Show table'}
        </button>
      </div>

      {showTable ? (
        <DataTable headers={['Stage', 'Status', 'Model', 'Start', 'End', 'Duration', 'Cost']} align={['left', 'left', 'left']}
          rows={stages.map((s) => [
            s.stage_name, s.cache_hit ? 'cache hit' : s.status, s.model_used ?? '—',
            formatDuration(s.start_offset_ms ?? 0), formatDuration(s.end_offset_ms ?? 0),
            formatDuration(s.duration_ms ?? 0), formatUSD(s.estimated_cost),
          ])} />
      ) : (
        <div ref={ref} className={`relative rounded-lg p-3 ${dark ? 'bg-surface-900/60' : 'bg-slate-900'}`}>
          <div className="flex flex-wrap gap-4 mb-2 text-xs text-slate-300">
            {statuses.map((st) => {
              const style = st === 'cache' ? { color: CHART.series1, icon: '⚡', label: 'Cache hit' } : statusStyle(st);
              return (
                <span key={st} className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm" style={{ background: style.color }} />
                  {style.icon} {style.label}
                </span>
              );
            })}
          </div>
          <svg width={width} height={height} role="img" aria-label={`Execution timeline: ${stages.length} stage runs over ${formatDuration(timeline.total_duration_ms)}`}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={0} y2={stages.length * ROW} stroke={CHART.grid} />
                <text x={x(t)} y={height - 6} textAnchor="middle" fill={CHART.muted} fontSize={11}>{formatDuration(t)}</text>
              </g>
            ))}
            {stages.map((s, i) => {
              const style = s.cache_hit ? { color: CHART.series1, icon: '⚡', label: 'Cache hit' } : statusStyle(s.status);
              const start = s.start_offset_ms ?? 0;
              const end = s.end_offset_ms ?? start;
              const w = Math.max(x(end) - x(start), 3);
              const y = i * ROW + (ROW - BAR) / 2;
              return (
                <g key={`${s.stage_id}-${i}`} data-testid={`gantt-row-${i}`} data-status={s.status}
                   onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)}>
                  <rect x={0} y={i * ROW} width={width} height={ROW} fill={hover === i ? 'rgba(148,163,184,0.08)' : 'transparent'} />
                  <text x={8} y={y + BAR / 2} dy="0.32em" fill="#e2e8f0" fontSize={12}>
                    {style.icon} {s.stage_name.length > 20 ? `${s.stage_name.slice(0, 19)}…` : s.stage_name}
                  </text>
                  <rect x={x(start)} y={y} width={w} height={BAR} rx={4} fill={style.color} />
                </g>
              );
            })}
          </svg>
          {hovered && hover !== null && (
            <ChartTooltip x={x(hovered.end_offset_ms ?? 0)} y={hover * ROW} width={width} title={hovered.stage_name} rows={[
              { label: hovered.cache_hit ? 'cache hit' : statusStyle(hovered.status).label.toLowerCase(),
                value: formatDuration(hovered.duration_ms ?? 0) },
              { label: 'started', value: `+${formatDuration(hovered.start_offset_ms ?? 0)}` },
              ...(hovered.model_used ? [{ label: hovered.provider ?? 'model', value: hovered.model_used }] : []),
              { label: 'cost', value: formatUSD(hovered.estimated_cost) },
            ]} />
          )}
        </div>
      )}
    </div>
  );
};

/** Loads and renders the timeline for an execution id. */
export const ExecutionTimelineView: React.FC<{ executionId: string; dark?: boolean }> = ({ executionId, dark }) => {
  const [timeline, setTimeline] = useState<ExecutionTimeline | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTimeline(null);
    analyticsApi.getTimeline(executionId)
      .then((t) => { setTimeline(t); setError(null); })
      .catch((err) => setError(err.response?.data?.detail || err.message));
  }, [executionId]);

  if (error) return <p className="text-sm text-red-600">Could not load timeline: {error}</p>;
  if (!timeline) return <p className="text-sm text-gray-500">Loading timeline…</p>;
  return <TimelineChart timeline={timeline} dark={dark} />;
};
