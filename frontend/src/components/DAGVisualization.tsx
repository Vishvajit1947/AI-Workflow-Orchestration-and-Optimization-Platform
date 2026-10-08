/**
 * Workflow dependency graph as SVG: one column per execution level (stages in a
 * column can run in parallel), arrows from each dependency, nodes colored by live
 * status. Without live status, the critical path is highlighted instead.
 */
import React from 'react';
import type { LiveStageStatus, WorkflowDAG } from '../types/execution';

const NODE_W = 176;
const NODE_H = 56;
const GAP_X = 72;
const GAP_Y = 20;
const PAD = 16;

// Static colors (SVG attributes) chosen to read on the dark surface
export const STATUS_STYLES: Record<string, { fill: string; stroke: string; label: string }> = {
  pending: { fill: '#1e293b', stroke: '#475569', label: 'Pending' },
  running: { fill: '#1e3a8a', stroke: '#60a5fa', label: 'Running' },
  completed: { fill: '#14532d', stroke: '#4ade80', label: 'Completed' },
  failed: { fill: '#7f1d1d', stroke: '#f87171', label: 'Failed' },
  skipped: { fill: '#451a03', stroke: '#f59e0b', label: 'Skipped' },
  cancelled: { fill: '#27272a', stroke: '#a1a1aa', label: 'Cancelled' },
};

interface DAGVisualizationProps {
  dag: WorkflowDAG;
  stageStatuses?: Record<string, LiveStageStatus>;
}

const truncate = (text: string, max: number) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

export const DAGVisualization: React.FC<DAGVisualizationProps> = ({ dag, stageStatuses }) => {
  const live = Boolean(stageStatuses && Object.keys(stageStatuses).length);
  const tallest = Math.max(1, ...dag.levels.map((level) => level.length));
  const height = PAD * 2 + tallest * NODE_H + (tallest - 1) * GAP_Y;
  const width = PAD * 2 + dag.levels.length * NODE_W + Math.max(0, dag.levels.length - 1) * GAP_X;

  // Center each column vertically
  const position: Record<string, { x: number; y: number }> = {};
  dag.levels.forEach((level, col) => {
    const columnHeight = level.length * NODE_H + (level.length - 1) * GAP_Y;
    const top = (height - columnHeight) / 2;
    level.forEach((id, row) => {
      position[id] = { x: PAD + col * (NODE_W + GAP_X), y: top + row * (NODE_H + GAP_Y) };
    });
  });

  const critical = new Set(dag.critical_path);
  const criticalEdge = (source: string, target: string) => {
    const i = dag.critical_path.indexOf(source);
    return i >= 0 && dag.critical_path[i + 1] === target;
  };

  return (
    <div className="overflow-x-auto">
      <svg
        role="img"
        aria-label={`Workflow graph: ${dag.nodes.length} stages in ${dag.levels.length} levels`}
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        className="max-w-none"
      >
        <defs>
          <marker id="dag-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill="#64748b" />
          </marker>
          <marker id="dag-arrow-hot" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill="#a78bfa" />
          </marker>
        </defs>

        {dag.edges.map(({ source, target }) => {
          const from = position[source];
          const to = position[target];
          if (!from || !to) return null;
          const x1 = from.x + NODE_W, y1 = from.y + NODE_H / 2;
          const x2 = to.x, y2 = to.y + NODE_H / 2;
          const mid = (x1 + x2) / 2;
          const running = live && stageStatuses?.[target]?.status === 'running';
          const hot = !live && criticalEdge(source, target);
          return (
            <path
              key={`${source}-${target}`}
              data-testid={`dag-edge-${source}-${target}`}
              d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2 - 2},${y2}`}
              fill="none"
              stroke={hot ? '#a78bfa' : running ? '#60a5fa' : '#475569'}
              strokeWidth={hot || running ? 2 : 1.5}
              strokeDasharray={running ? '6 4' : undefined}
              markerEnd={`url(#${hot ? 'dag-arrow-hot' : 'dag-arrow'})`}
            >
              {running && <animate attributeName="stroke-dashoffset" from="20" to="0" dur="0.8s" repeatCount="indefinite" />}
            </path>
          );
        })}

        {dag.nodes.map((node) => {
          const pos = position[node.stage_id];
          if (!pos) return null;
          const liveStage = stageStatuses?.[node.stage_id];
          const status = liveStage?.status ?? 'pending';
          const style = live ? STATUS_STYLES[status] ?? STATUS_STYLES.pending : STATUS_STYLES.pending;
          const onPath = !live && critical.has(node.stage_id);
          const subtitle = live
            ? liveStage?.cache_hit ? 'cache hit' : liveStage?.model ?? style.label.toLowerCase()
            : node.stage_type ?? 'untyped';
          return (
            <g key={node.stage_id} data-testid={`dag-node-${node.stage_id}`} data-status={live ? status : undefined}
               transform={`translate(${pos.x},${pos.y})`}>
              <title>
                {`${node.name}${live ? ` — ${style.label}` : ''}${liveStage?.error ? `: ${liveStage.error}` : ''}`}
              </title>
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={10}
                fill={style.fill}
                stroke={onPath ? '#a78bfa' : style.stroke}
                strokeWidth={onPath || status === 'running' ? 2 : 1.5}
              >
                {live && status === 'running' && (
                  <animate attributeName="stroke-opacity" values="1;0.35;1" dur="1.4s" repeatCount="indefinite" />
                )}
              </rect>
              <text x={12} y={23} fill="#f1f5f9" fontSize={13} fontWeight={600}>{truncate(node.name, 22)}</text>
              <text x={12} y={42} fill="#94a3b8" fontSize={11}>{truncate(subtitle, 26)}</text>
              {node.is_merge_point && (
                <text x={NODE_W - 10} y={18} fill="#94a3b8" fontSize={11} textAnchor="end">⤚ merge</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export const DAGLegend: React.FC<{ live: boolean }> = ({ live }) => (
  <div className="flex flex-wrap gap-3 text-xs text-surface-200/60">
    {live
      ? Object.entries(STATUS_STYLES).map(([key, s]) => (
          <span key={key} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm border" style={{ background: s.fill, borderColor: s.stroke }} />
            {s.label}
          </span>
        ))
      : (
        <>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm border-2" style={{ borderColor: '#a78bfa' }} /> Critical path
          </span>
          <span>Stages in the same column run in parallel</span>
        </>
      )}
  </div>
);
