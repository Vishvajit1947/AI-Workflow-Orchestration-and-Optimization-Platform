/**
 * Workflow dependency graph as SVG: one column per execution level (stages in a
 * column can run in parallel), arrows from each dependency, nodes colored by live
 * status. Without live status, the critical path is highlighted instead.
 */
import React, { useEffect, useRef } from 'react';
import type { LiveStageStatus, WorkflowDAG } from '../types/execution';

const NODE_W = 176;
const NODE_H = 56;
const GAP_X = 72;
const GAP_Y = 20;
const PAD = 16;

// Static colors (SVG attributes) for Mercury's light canvas: tinted fills, status-coloured strokes
export const STATUS_STYLES: Record<string, { fill: string; stroke: string; label: string }> = {
  pending: { fill: '#ffffff', stroke: '#d9d8e5', label: 'Pending' },
  running: { fill: '#eef0fd', stroke: '#5266eb', label: 'Running' },
  completed: { fill: '#ebf6f0', stroke: '#2f9e6e', label: 'Completed' },
  failed: { fill: '#fcecea', stroke: '#c0392b', label: 'Failed' },
  skipped: { fill: '#fdf4e4', stroke: '#d08a1c', label: 'Skipped' },
  cancelled: { fill: '#f3f3f7', stroke: '#9a97ad', label: 'Cancelled' },
};

/** Edge and text colors */
export const DAG_COLORS = {
  edge: '#c9c8d8',
  critical: '#5266eb',
  running: '#5266eb',
  title: '#28253b',
  subtitle: '#6f6a8a',
};

interface DAGVisualizationProps {
  dag: WorkflowDAG;
  stageStatuses?: Record<string, LiveStageStatus>;
}

const truncate = (text: string, max: number) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

/** Seconds of stagger per graph level for the entry animation */
const LEVEL_DELAY = 0.07;
/** How long a node's completion/failure flash stays mounted (matches animate-flash-ring) */
const FLASH_MS = 900;

/**
 * Remembers when each stage last changed into a finished state, so the flash plays once at
 * the moment of the change (not on first render, and not again on later live updates).
 */
function useStatusFlashes(statuses: Record<string, string>) {
  const previous = useRef<Record<string, string> | null>(null);
  const flashes = useRef<Record<string, { status: string; at: number }>>({});
  const now = Date.now();
  if (previous.current) {
    for (const [id, status] of Object.entries(statuses)) {
      const before = previous.current[id];
      if (before && before !== status && (status === 'completed' || status === 'failed')) {
        flashes.current[id] = { status, at: now };
      }
    }
  }
  useEffect(() => {
    previous.current = statuses;
  });
  return (id: string, status: string) => {
    const flash = flashes.current[id];
    return Boolean(flash && flash.status === status && now - flash.at < FLASH_MS);
  };
}

export const DAGVisualization: React.FC<DAGVisualizationProps> = ({ dag, stageStatuses }) => {
  const live = Boolean(stageStatuses && Object.keys(stageStatuses).length);
  const tallest = Math.max(1, ...dag.levels.map((level) => level.length));
  const height = PAD * 2 + tallest * NODE_H + (tallest - 1) * GAP_Y;
  const width = PAD * 2 + dag.levels.length * NODE_W + Math.max(0, dag.levels.length - 1) * GAP_X;

  // Center each column vertically
  const position: Record<string, { x: number; y: number }> = {};
  const levelOf: Record<string, number> = {};
  dag.levels.forEach((level, col) => {
    const columnHeight = level.length * NODE_H + (level.length - 1) * GAP_Y;
    const top = (height - columnHeight) / 2;
    level.forEach((id, row) => {
      position[id] = { x: PAD + col * (NODE_W + GAP_X), y: top + row * (NODE_H + GAP_Y) };
      levelOf[id] = col;
    });
  });

  const critical = new Set(dag.critical_path);
  const criticalEdge = (source: string, target: string) => {
    const i = dag.critical_path.indexOf(source);
    return i >= 0 && dag.critical_path[i + 1] === target;
  };

  const statusById = Object.fromEntries(
    dag.nodes.map((n) => [n.stage_id, live ? stageStatuses?.[n.stage_id]?.status ?? 'pending' : 'pending']),
  );
  const flashing = useStatusFlashes(statusById);

  return (
    <div className="overflow-x-auto rounded-card bg-[radial-gradient(#e4e3ee_1px,transparent_1px)] p-2 [background-size:16px_16px]">
      <svg
        role="img"
        aria-label={`Workflow graph: ${dag.nodes.length} stages in ${dag.levels.length} levels`}
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        className="max-w-none overflow-visible"
      >
        <defs>
          <marker id="dag-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill={DAG_COLORS.edge} />
          </marker>
          <marker id="dag-arrow-hot" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill={DAG_COLORS.critical} />
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
              stroke={hot ? DAG_COLORS.critical : running ? DAG_COLORS.running : DAG_COLORS.edge}
              strokeWidth={hot || running ? 2 : 1.5}
              // Running edges flow toward the active stage; others draw in along their length once
              strokeDasharray={running ? '6 4' : undefined}
              pathLength={running ? undefined : 1}
              className={`transition-[stroke,stroke-width] duration-500 ease-standard ${
                running ? 'animate-flow-dash' : 'stroke-draw animate-draw'
              }`}
              style={running ? undefined : { animationDelay: `${(levelOf[source] ?? 0) * LEVEL_DELAY + 0.15}s` }}
              markerEnd={`url(#${hot ? 'dag-arrow-hot' : 'dag-arrow'})`}
            />
          );
        })}

        {dag.nodes.map((node) => {
          const pos = position[node.stage_id];
          if (!pos) return null;
          const liveStage = stageStatuses?.[node.stage_id];
          const status = liveStage?.status ?? 'pending';
          const style = live ? STATUS_STYLES[status] ?? STATUS_STYLES.pending : STATUS_STYLES.pending;
          const onPath = !live && critical.has(node.stage_id);
          const isRunning = live && status === 'running';
          const subtitle = live
            ? liveStage?.cache_hit ? 'cache hit' : liveStage?.model ?? style.label.toLowerCase()
            : node.stage_type ?? 'untyped';
          return (
            <g key={node.stage_id} data-testid={`dag-node-${node.stage_id}`} data-status={live ? status : undefined}
               transform={`translate(${pos.x},${pos.y})`}>
              <title>
                {`${node.name}${live ? ` — ${style.label}` : ''}${liveStage?.error ? `: ${liveStage.error}` : ''}`}
              </title>
              {/* Entry: nodes settle in level by level, once per mount */}
              <g className="animate-fade-in-up" style={{ animationDelay: `${(levelOf[node.stage_id] ?? 0) * LEVEL_DELAY}s` }}>
                {/* Running: a soft ring breathes outward from the active stage */}
                {isRunning && (
                  <rect width={NODE_W} height={NODE_H} rx={12} fill="none" stroke={style.stroke} strokeWidth={2}
                        className="fill-box origin-center animate-pulse-ring" aria-hidden />
                )}
                {/* Finished: one ring flash at the moment the stage completes or fails */}
                {live && flashing(node.stage_id, status) && (
                  <rect key={`flash-${status}`} width={NODE_W} height={NODE_H} rx={12} fill="none" stroke={style.stroke}
                        strokeWidth={2} className="fill-box origin-center animate-flash-ring" aria-hidden />
                )}
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={12}
                  fill={style.fill}
                  stroke={onPath ? DAG_COLORS.critical : style.stroke}
                  strokeWidth={onPath || status === 'running' ? 2 : 1.5}
                  className="transition-[fill,stroke,stroke-width] duration-500 ease-standard"
                />
                <text x={14} y={24} fill={DAG_COLORS.title} fontSize={13} fontWeight={480}>{truncate(node.name, 22)}</text>
                <text x={14} y={42} fill={DAG_COLORS.subtitle} fontSize={11}>{truncate(subtitle, node.is_merge_point ? 16 : 26)}</text>
                {node.is_merge_point && (
                  <text x={NODE_W - 12} y={42} fill={DAG_COLORS.subtitle} fontSize={10.5} textAnchor="end">⤚ merge</text>
                )}
              </g>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export const DAGLegend: React.FC<{ live: boolean }> = ({ live }) => (
  <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-ink-secondary">
    {live
      ? Object.entries(STATUS_STYLES).map(([key, s]) => (
          <span key={key} className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-[4px] border-[1.5px]" style={{ background: s.fill, borderColor: s.stroke }} />
            {s.label}
          </span>
        ))
      : (
        <>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-[4px] border-2" style={{ borderColor: DAG_COLORS.critical }} /> Critical path
          </span>
          <span className="text-ink-muted">Stages in the same column run in parallel</span>
        </>
      )}
  </div>
);
