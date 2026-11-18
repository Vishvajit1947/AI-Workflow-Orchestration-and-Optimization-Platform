/**
 * Stat tile (Mercury stat-block): small label, large light-weight numeral, optional context line.
 * MetricGrid lays tiles out responsively.
 */
import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Stagger, StaggerItem } from '../motion/Motion';

interface MetricCardProps {
  label: string;
  value: string;
  detail?: string;
  icon?: LucideIcon;
  testId?: string;
  /** Smaller numerals for text values (model names) */
  compact?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({ label, value, detail, icon: Icon, testId, compact }) => (
  <div className="card min-w-0 px-4 py-4 sm:px-5" data-testid={testId}>
    <div className="flex min-w-0 items-center gap-2 overflow-hidden whitespace-nowrap text-[13px] text-ink-muted" title={label}>
      {Icon && <Icon size={14} strokeWidth={1.75} className="shrink-0 text-primary" aria-hidden />}
      {label}
    </div>
    <p
      className={`mt-2.5 truncate font-medium text-ink tabular ${compact ? 'text-lg leading-snug' : 'text-[26px] leading-none tracking-[0.01em]'}`}
      title={value}
    >
      {value}
    </p>
    {detail && <p className="mt-2 truncate text-xs text-ink-muted" title={detail}>{detail}</p>}
  </div>
);

/** Alias matching the design-system name */
export const StatCard = MetricCard;

/** KPI row: tiles settle in one after another the first time the grid mounts. */
export const MetricGrid: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Stagger inView={false} step={0.045} className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
    {React.Children.map(children, (child) => child && <StaggerItem className="min-w-0 [&>*]:h-full">{child}</StaggerItem>)}
  </Stagger>
);
