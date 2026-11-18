/**
 * Empty, loading and error states, plus inline notices. Every page uses these so the
 * same situation always looks the same.
 */
import React from 'react';
import { AlertCircle, CheckCircle2, Info, Loader2, TriangleAlert, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export const EmptyState: React.FC<{
  icon?: LucideIcon;
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  compact?: boolean;
  'data-testid'?: string;
}> = ({ icon: Icon, title, description, action, className = '', compact = false, ...rest }) => (
  <div
    className={`flex animate-fade-in flex-col items-center justify-center rounded-card bg-lavender-soft text-center ${
      compact ? 'px-6 py-8' : 'px-6 py-14 sm:py-16'
    } ${className}`}
    {...rest}
  >
    {Icon && (
      <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-surface text-primary shadow-soft">
        <Icon size={20} strokeWidth={1.75} aria-hidden />
      </span>
    )}
    <p className="text-[15px] font-medium text-ink">{title}</p>
    {description && <p className="mt-1.5 max-w-md text-sm leading-relaxed text-ink-secondary">{description}</p>}
    {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
  </div>
);

export const LoadingState: React.FC<{ label?: string; className?: string; inline?: boolean }> = ({
  label = 'Loading…', className = '', inline = false,
}) => (
  <div
    role="status"
    className={`flex items-center gap-2.5 text-sm text-ink-muted ${inline ? '' : 'justify-center py-14'} ${className}`}
  >
    <Loader2 size={16} className="animate-spin text-primary" aria-hidden />
    {label}
  </div>
);

/** Skeleton block for content whose shape is known. */
export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div aria-hidden className={`animate-pulse rounded-card bg-lavender ${className}`} />
);

type NoticeTone = 'info' | 'success' | 'warning' | 'danger';

const NOTICE: Record<NoticeTone, { icon: LucideIcon; box: string; icon_: string }> = {
  info: { icon: Info, box: 'border-info-line bg-info-soft text-ink', icon_: 'text-primary' },
  success: { icon: CheckCircle2, box: 'border-success-line bg-success-soft text-ink', icon_: 'text-success' },
  warning: { icon: TriangleAlert, box: 'border-warning-line bg-warning-soft text-ink', icon_: 'text-warning' },
  danger: { icon: AlertCircle, box: 'border-danger-line bg-danger-soft text-ink', icon_: 'text-danger' },
};

/** Inline message with an optional title and dismiss button. Errors announce as alerts. */
export const Notice: React.FC<{
  tone?: NoticeTone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
  action?: React.ReactNode;
}> = ({ tone = 'info', title, children, onDismiss, className = '', action }) => {
  const { icon: Icon, box, icon_ } = NOTICE[tone];
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={`flex animate-fade-in-up items-start gap-3 rounded-card border px-4 py-3 text-sm ${box} ${className}`}
    >
      <Icon size={17} className={`mt-px shrink-0 ${icon_}`} aria-hidden />
      <div className="min-w-0 flex-1 leading-relaxed">
        {title && <p className="font-medium text-ink">{title}</p>}
        {children && <div className={title ? 'mt-0.5 text-ink-secondary' : 'text-ink'}>{children}</div>}
      </div>
      {action}
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label="Dismiss" className="btn btn-ghost btn-icon btn-sm -my-1 -mr-1.5">
          <X size={15} />
        </button>
      )}
    </div>
  );
};

/** Error with an optional retry, for a failed load. */
export const ErrorState: React.FC<{
  title?: React.ReactNode;
  message: React.ReactNode;
  onRetry?: () => void;
  className?: string;
}> = ({ title = 'Something went wrong', message, onRetry, className = '' }) => (
  <Notice
    tone="danger"
    title={title}
    className={className}
    action={onRetry && (
      <button type="button" onClick={onRetry} className="btn btn-outline btn-sm -my-0.5">Retry</button>
    )}
  >
    {message}
  </Notice>
);
