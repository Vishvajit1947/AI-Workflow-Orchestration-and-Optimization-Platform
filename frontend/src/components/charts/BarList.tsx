/**
 * Horizontal single-series bar chart (one color for every bar: the categories are
 * nominal, so hue carries nothing). Value at the bar tip; details on hover/focus.
 */
import React, { useState } from 'react';
import { CHART, ChartTooltip, TooltipRow, useWidth } from './chartKit';

export interface BarDatum {
  key: string;
  label: string;
  value: number;
  display: string;          // value label at the tip
  tooltip?: TooltipRow[];
}

const ROW = 30;
const BAR = 16;
const LABEL_W = 176;
const VALUE_W = 64;
const MAX_LABEL_CHARS = Math.floor((LABEL_W - 14) / 7);

export const BarList: React.FC<{ data: BarDatum[]; ariaLabel: string; color?: string }> = ({
  data, ariaLabel, color = CHART.series1,
}) => {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...data.map((d) => d.value), 0) || 1;
  const trackW = Math.max(width - LABEL_W - VALUE_W, 20);
  const height = data.length * ROW;

  const barPath = (w: number, y: number) => {
    const r = Math.min(4, w / 2);
    return `M${LABEL_W},${y} H${LABEL_W + w - r} Q${LABEL_W + w},${y} ${LABEL_W + w},${y + r} V${y + BAR - r} Q${LABEL_W + w},${y + BAR} ${LABEL_W + w - r},${y + BAR} H${LABEL_W} Z`;
  };

  const d = hover !== null ? data[hover] : null;
  return (
    <div ref={ref} className="relative">
      <svg width={width} height={height} role="img" aria-label={ariaLabel}>
        <line x1={LABEL_W} x2={LABEL_W} y1={0} y2={height} stroke={CHART.baseline} />
        {data.map((item, i) => {
          const y = i * ROW + (ROW - BAR) / 2;
          const w = Math.max((item.value / max) * trackW, item.value > 0 ? 2 : 0);
          return (
            <g key={item.key} data-testid={`bar-${item.key}`} tabIndex={0}
               onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)}
               onFocus={() => setHover(i)} onBlur={() => setHover(null)}>
              <rect x={0} y={i * ROW} width={width} height={ROW} fill="transparent" />
              <text x={LABEL_W - 10} y={y + BAR / 2} dy="0.32em" textAnchor="end" fill="#cbd5e1" fontSize={12}>
                <title>{item.label}</title>
                {item.label.length > MAX_LABEL_CHARS ? `${item.label.slice(0, MAX_LABEL_CHARS - 1)}…` : item.label}
              </text>
              {w > 0 && <path d={barPath(w, y)} fill={color} opacity={hover === null || hover === i ? 1 : 0.55} />}
              <text x={LABEL_W + w + 6} y={y + BAR / 2} dy="0.32em" fill="#e2e8f0" fontSize={12} className="tabular-nums">
                {item.display}
              </text>
            </g>
          );
        })}
      </svg>
      {d && hover !== null && d.tooltip && (
        <ChartTooltip x={LABEL_W + Math.max((d.value / max) * trackW, 2)} y={hover * ROW} width={width} title={d.label} rows={d.tooltip} />
      )}
    </div>
  );
};
