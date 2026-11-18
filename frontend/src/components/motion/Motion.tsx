/**
 * Reusable motion building blocks. All of them animate only opacity and transform (plus height
 * for Collapse), run once per mount, and respect prefers-reduced-motion via MotionProvider.
 */
import React from 'react';
import { AnimatePresence, MotionConfig, motion as m } from 'motion/react';
import { fadeUp, staggerChildren, transition } from '../../lib/motion';

/** App-wide motion setup: default timing, and reduced motion when the OS asks for it. */
export const MotionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <MotionConfig reducedMotion="user" transition={transition.enter}>
    {children}
  </MotionConfig>
);

/**
 * Page entry: a short fade-and-settle when the route changes. Keyed by the caller, so it
 * plays on navigation only, never on re-renders or live data updates.
 */
export const PageTransition: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <m.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={transition.enter}>
    {children}
  </m.div>
);

interface RevealProps {
  children: React.ReactNode;
  className?: string;
  /** Seconds before the reveal starts */
  delay?: number;
  as?: 'div' | 'section' | 'li';
}

/** Fades content up the first time it scrolls into view. */
export const Reveal: React.FC<RevealProps> = ({ children, className, delay = 0, as = 'div' }) => {
  const Tag = m[as] as typeof m.div;
  return (
    <Tag
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.15, margin: '0px 0px -40px 0px' }}
      variants={fadeUp}
      transition={{ ...transition.enter, delay }}
    >
      {children}
    </Tag>
  );
};

interface StaggerProps {
  children: React.ReactNode;
  className?: string;
  /** Seconds between children */
  step?: number;
  delay?: number;
  /** Reveal when scrolled into view (default) or immediately on mount */
  inView?: boolean;
  as?: 'div' | 'ul' | 'ol';
  role?: string;
  'aria-label'?: string;
}

/** Container whose StaggerItem children fade up one after another. */
export const Stagger: React.FC<StaggerProps> = ({
  children, className, step = 0.05, delay = 0, inView = true, as = 'div', ...rest
}) => {
  const Tag = m[as] as typeof m.div;
  const trigger = inView
    ? { whileInView: 'show', viewport: { once: true, amount: 0.1 } }
    : { animate: 'show' };
  return (
    <Tag className={className} initial="hidden" variants={staggerChildren(step, delay)} {...trigger} {...rest}>
      {children}
    </Tag>
  );
};

export const StaggerItem: React.FC<{
  children: React.ReactNode;
  className?: string;
  as?: 'div' | 'li';
  layout?: boolean;
}> = ({ children, className, as = 'div', layout }) => {
  const Tag = m[as] as typeof m.div;
  return (
    <Tag className={className} variants={fadeUp} layout={layout ? 'position' : undefined}>
      {children}
    </Tag>
  );
};

/** Animated show/hide with height, so surrounding content moves instead of jumping. */
export const Collapse: React.FC<{ open: boolean; children: React.ReactNode; className?: string; id?: string }> = ({
  open, children, className, id,
}) => (
  <AnimatePresence initial={false}>
    {open && (
      <m.div
        key="collapse"
        id={id}
        className={className}
        // Clip only while animating, so sticky children and focus rings work once open
        initial={{ height: 0, opacity: 0, overflow: 'hidden' }}
        animate={{ height: 'auto', opacity: 1, transitionEnd: { overflow: 'visible' } }}
        exit={{ height: 0, opacity: 0, overflow: 'hidden', transition: transition.exit }}
        transition={transition.collapse}
      >
        {children}
      </m.div>
    )}
  </AnimatePresence>
);
