/**
 * Motion tokens and variants, shared by every animated component so timing stays consistent.
 *
 * Values follow the motion measured on mercury.com:
 *  - entrances/reveals: a long, soft deceleration  cubic-bezier(0.16, 0, 0.13, 1), 0.3–0.5s
 *  - state changes (tabs, toggles):                cubic-bezier(0.4, 0, 0.2, 1),  0.15s
 *  - hover colour shifts:                          cubic-bezier(0, 0, 0.2, 1),    0.3s
 *  - moving panels:                                cubic-bezier(0.76, 0, 0.24, 1)
 * The same curves are exposed to CSS as Tailwind `ease-*` utilities (tailwind.config.js).
 */
import type { Transition, Variants } from 'motion/react';

export const EASE = {
  out: [0.16, 0, 0.13, 1],
  standard: [0.4, 0, 0.2, 1],
  soft: [0, 0, 0.2, 1],
  inOut: [0.76, 0, 0.24, 1],
} as const satisfies Record<string, [number, number, number, number]>;

export const DURATION = {
  fast: 0.15,
  base: 0.3,
  slow: 0.5,
} as const;

/** Distance (px) content travels while fading in: small enough to read as settling, not sliding. */
export const RISE = 10;

export const transition = {
  enter: { duration: DURATION.slow, ease: EASE.out } satisfies Transition,
  exit: { duration: DURATION.fast, ease: EASE.standard } satisfies Transition,
  state: { duration: DURATION.base, ease: EASE.standard } satisfies Transition,
  /** Shared indicators (active nav pill, tab underline, segmented thumb) */
  indicator: { type: 'spring', stiffness: 520, damping: 42, mass: 0.9 } satisfies Transition,
  /** Height changes of collapsible panels */
  collapse: { duration: DURATION.base, ease: EASE.out } satisfies Transition,
} as const;

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: RISE },
  show: { opacity: 1, y: 0, transition: transition.enter },
};

export const fade: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: transition.enter },
};

/** Parent of a staggered group: children use `fadeUp` (or any variant with hidden/show). */
export const staggerChildren = (step = 0.05, delay = 0): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren: step, delayChildren: delay } },
});
