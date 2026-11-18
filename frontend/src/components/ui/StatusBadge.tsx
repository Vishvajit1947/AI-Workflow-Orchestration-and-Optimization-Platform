/**
 * Pill showing a workflow, execution, stage or project status. One tone per status across the app;
 * a leading dot (pulsing while work is in progress) plus the text, so meaning never rests on colour alone.
 */
import React from 'react';

export type Tone = 'neutral' | 'info' | 'warning' | 'success' | 'danger';

export const STATUS_TONE: Record<string, Tone> = {
  draft: 'neutral',
  pending: 'neutral',
  queued: 'neutral',
  cancelled: 'neutral',
  initializing: 'neutral',
  running: 'info',
  building: 'info',
  active: 'info',
  paused: 'warning',
  skipped: 'warning',
  unavailable: 'warning',
  completed: 'success',
  succeeded: 'success',
  passed: 'success',
  failed: 'danger',
};

export const TONE_CLASSES: Record<Tone, { badge: string; dot: string; text: string }> = {
  neutral: { badge: 'bg-[rgba(112,115,147,0.1)] text-ink-secondary', dot: 'bg-ink-faint', text: 'text-ink-secondary' },
  info: { badge: 'bg-info-soft text-info', dot: 'bg-primary', text: 'text-info' },
  warning: { badge: 'bg-warning-soft text-warning', dot: 'bg-[#d08a1c]', text: 'text-warning' },
  success: { badge: 'bg-success-soft text-success', dot: 'bg-[#2f9e6e]', text: 'text-success' },
  danger: { badge: 'bg-danger-soft text-danger', dot: 'bg-danger', text: 'text-danger' },
};

const PULSING = new Set(['running', 'building', 'initializing', 'queued']);

export const toneFor = (status: string): Tone => STATUS_TONE[status] ?? 'neutral';

interface StatusBadgeProps {
  status: string;
  /** Text to show instead of the raw status */
  label?: string;
  className?: string;
  'data-testid'?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, className = '', ...rest }) => {
  const tone = toneFor(status);
  const classes = TONE_CLASSES[tone];
  return (
    <span
      data-tone={tone}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-pill px-2.5 py-1 text-xs font-book leading-none transition-colors duration-500 ease-standard ${classes.badge} ${className}`}
      {...rest}
    >
      <span aria-hidden className="relative flex h-1.5 w-1.5">
        {PULSING.has(status) && <span className={`absolute inset-0 animate-ping rounded-full opacity-60 ${classes.dot}`} />}
        <span className={`relative h-1.5 w-1.5 rounded-full transition-colors duration-500 ease-standard ${classes.dot}`} />
      </span>
      {label ?? status}
    </span>
  );
};
