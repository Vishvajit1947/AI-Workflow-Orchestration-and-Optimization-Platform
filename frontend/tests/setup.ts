import '@testing-library/jest-dom';
import { MotionGlobalConfig } from 'motion/react';

// Animations finish instantly in tests: assertions see final states, exits unmount promptly
MotionGlobalConfig.skipAnimations = true;

// jsdom has no IntersectionObserver; scroll reveals treat everything as already in view
if (typeof window !== 'undefined' && !('IntersectionObserver' in window)) {
  class ImmediateIntersectionObserver {
    readonly root = null;
    readonly rootMargin = '0px';
    readonly thresholds = [0];
    constructor(private callback: IntersectionObserverCallback) {}
    observe(target: Element) {
      this.callback(
        [{ isIntersecting: true, intersectionRatio: 1, target } as IntersectionObserverEntry],
        this as unknown as IntersectionObserver,
      );
    }
    unobserve() {}
    disconnect() {}
    takeRecords() { return []; }
  }
  (window as unknown as { IntersectionObserver: unknown }).IntersectionObserver = ImmediateIntersectionObserver;
  (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = ImmediateIntersectionObserver;
}
