/**
 * Lightweight hover/focus tooltip rendered in a portal, so it escapes scroll containers and the
 * clipped sidebar rail. Purely visual (aria-hidden): the trigger must carry its own accessible
 * name (aria-label), which keeps screen readers from hearing the label twice.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

interface TooltipProps {
  label: string;
  /** When false the children render untouched */
  enabled?: boolean;
  side?: 'right' | 'bottom';
  children: React.ReactNode;
}

const GAP = 10;

/** Show on keyboard focus only; a mouse click already showed it on hover */
const isKeyboardFocus = (el: HTMLElement) => {
  try {
    return el.matches(':focus-visible');
  } catch {
    return true;
  }
};

export const Tooltip: React.FC<TooltipProps> = ({ label, enabled = true, side = 'right', children }) => {
  const wrapper = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  const show = useCallback(() => {
    const target = wrapper.current?.firstElementChild;
    if (!target) return;
    const r = target.getBoundingClientRect();
    setPos(side === 'right' ? { x: r.right + GAP, y: r.top + r.height / 2 } : { x: r.left + r.width / 2, y: r.bottom + GAP });
  }, [side]);
  const hide = useCallback(() => setPos(null), []);

  // A scroll or resize moves the trigger; drop the tooltip rather than leave it floating
  useEffect(() => {
    if (!pos) return;
    window.addEventListener('scroll', hide, true);
    window.addEventListener('resize', hide);
    return () => {
      window.removeEventListener('scroll', hide, true);
      window.removeEventListener('resize', hide);
    };
  }, [pos, hide]);

  useEffect(() => {
    if (!enabled) setPos(null);
  }, [enabled]);

  if (!enabled) return <>{children}</>;

  return (
    <span
      ref={wrapper}
      className="contents"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={(e) => isKeyboardFocus(e.target as HTMLElement) && show()}
      onBlur={hide}
      onClick={hide}
    >
      {children}
      {pos &&
        createPortal(
          <span
            aria-hidden
            className="pointer-events-none fixed z-[60] animate-pop-in whitespace-nowrap rounded-[8px] border border-night-line bg-night-raised px-2.5 py-1.5 text-xs font-book text-on-dark shadow-pop"
            style={{
              left: pos.x,
              top: pos.y,
              translate: side === 'right' ? '0 -50%' : '-50% 0',
            }}
          >
            {label}
          </span>,
          document.body,
        )}
    </span>
  );
};
