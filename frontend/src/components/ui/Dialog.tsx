/**
 * Modal dialog shell (overlay, Escape to close, focus moved in and restored on close),
 * a confirmation dialog, and useConfirm() — a promise-based replacement for window.confirm.
 */
import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'motion/react';
import { TriangleAlert, X } from 'lucide-react';
import { EASE, transition } from '../../lib/motion';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
  /** id for the title element (tests and aria-labelledby) */
  titleId?: string;
}

const SIZES = { sm: 'sm:max-w-md', md: 'sm:max-w-lg', lg: 'sm:max-w-2xl' };

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export const Dialog: React.FC<DialogProps> = ({
  open, onClose, title, description, children, footer, size = 'md', titleId,
}) => {
  const generated = useId();
  const labelId = titleId ?? `dialog-${generated}`;
  const panel = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    // Prefer an element marked autoFocus, then the first focusable control
    const node = panel.current;
    const target = node?.querySelector<HTMLElement>('[data-autofocus]') ?? node?.querySelector<HTMLElement>(FOCUSABLE);
    target?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onCloseRef.current();
      }
      // Keep Tab inside the dialog
      if (e.key === 'Tab' && node) {
        const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE));
        if (items.length === 0) return;
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    window.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, [open]);

  // Stays mounted while closing so the exit animation can play
  return createPortal(
    <AnimatePresence>
      {open && (
        <div key="dialog" className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
          <motion.div
            className="absolute inset-0 bg-night/50 backdrop-blur-[2px]"
            onClick={onClose}
            aria-hidden
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { duration: 0.25, ease: EASE.soft } }}
            exit={{ opacity: 0, transition: { duration: 0.2, ease: EASE.standard } }}
          />
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby={labelId}
            className={`relative flex max-h-[92vh] w-full flex-col rounded-t-panel bg-surface shadow-pop sm:rounded-panel ${SIZES[size]}`}
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1, transition: { duration: 0.4, ease: EASE.out } }}
            exit={{ opacity: 0, y: 8, scale: 0.98, transition: transition.exit }}
          >
            <div className="flex items-start justify-between gap-4 px-6 pb-2 pt-6">
              <div className="min-w-0">
                <h2 id={labelId} className="text-lead font-medium text-ink">{title}</h2>
                {description && <div className="mt-1.5 text-sm leading-relaxed text-ink-secondary">{description}</div>}
              </div>
              <button type="button" onClick={onClose} aria-label="Close dialog" className="btn btn-ghost btn-icon btn-sm -mr-2 -mt-1">
                <X size={16} />
              </button>
            </div>
            {children && <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">{children}</div>}
            {footer && (
              <div className="flex flex-col-reverse gap-2 border-t border-hairline px-6 py-4 sm:flex-row sm:justify-end">
                {footer}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
};

export interface ConfirmOptions {
  title: string;
  message?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Destructive actions get a red confirm button */
  destructive?: boolean;
}

export const ConfirmDialog: React.FC<ConfirmOptions & {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({ open, title, message, confirmLabel = 'Confirm', cancelLabel = 'Cancel', destructive = false, onConfirm, onCancel }) => (
  <Dialog
    open={open}
    onClose={onCancel}
    size="sm"
    title={
      <span className="flex items-center gap-2.5">
        {destructive && (
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-danger-soft text-danger">
            <TriangleAlert size={16} aria-hidden />
          </span>
        )}
        {title}
      </span>
    }
    description={message}
    footer={
      <>
        <button type="button" onClick={onCancel} className="btn btn-outline">{cancelLabel}</button>
        <button
          type="button"
          onClick={onConfirm}
          data-autofocus
          className={`btn ${destructive ? 'btn-danger-solid' : 'btn-primary'}`}
        >
          {confirmLabel}
        </button>
      </>
    }
  />
);

/**
 * const [confirm, confirmDialog] = useConfirm();
 * if (await confirm({ title: 'Delete?', destructive: true })) ...
 * Render {confirmDialog} once in the component.
 */
export function useConfirm(): [(options: ConfirmOptions) => Promise<boolean>, React.ReactNode] {
  const [state, setState] = useState<(ConfirmOptions & { resolve: (ok: boolean) => void; open: boolean }) | null>(null);

  const confirm = useCallback(
    (options: ConfirmOptions) => new Promise<boolean>((resolve) => setState({ ...options, resolve, open: true })),
    [],
  );

  const settle = (ok: boolean) => {
    if (!state?.open) return;
    state.resolve(ok);
    // Keep the content while the dialog animates out
    setState({ ...state, open: false });
  };

  const dialog = state ? (
    <ConfirmDialog {...state} onConfirm={() => settle(true)} onCancel={() => settle(false)} />
  ) : null;

  return [confirm, dialog];
}
