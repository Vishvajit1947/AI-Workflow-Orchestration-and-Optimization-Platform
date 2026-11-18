/**
 * App-shell layout state: whether the sidebar is collapsed to its icon rail, and whether focus
 * mode (sidebar hidden, content at full width) is on.
 *
 * - Collapse is remembered per breakpoint (desktop expanded / tablet rail by default), so a
 *   choice made on a laptop doesn't squeeze a tablet and vice versa.
 * - Focus mode lasts for the session only: a reload always brings the navigation back.
 * - Ctrl/⌘+B toggles the sidebar, Ctrl/⌘+Shift+F toggles focus mode (md and up only; phones
 *   use the drawer).
 */
import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'ai-orchestrator.shell.collapsed';
const DESKTOP_QUERY = '(min-width: 1024px)';
const TABLET_UP_QUERY = '(min-width: 768px)';

type Breakpoint = 'lg' | 'md';
type CollapsePrefs = Partial<Record<Breakpoint, boolean>>;

const readPrefs = (): CollapsePrefs => {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? (parsed as CollapsePrefs) : {};
  } catch {
    return {};
  }
};

const writePrefs = (prefs: CollapsePrefs) => {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // Storage blocked (private mode etc.): the preference just isn't remembered
  }
};

const matches = (query: string, fallback: boolean) =>
  typeof window !== 'undefined' && typeof window.matchMedia === 'function' ? window.matchMedia(query).matches : fallback;

/** Tracks a media query; environments without matchMedia (tests) get `fallback`. */
export function useMediaQuery(query: string, fallback = true): boolean {
  const [value, setValue] = useState(() => matches(query, fallback));
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const mql = window.matchMedia(query);
    const onChange = () => setValue(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);
  return value;
}

export const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
export const MOD_KEY = IS_MAC ? '⌘' : 'Ctrl';

export interface ShellLayout {
  /** Sidebar shown as the icon rail */
  collapsed: boolean;
  /** Sidebar hidden entirely, content uses the full width */
  focusMode: boolean;
  /** Collapse/expand; in focus mode it brings the sidebar back instead */
  toggleSidebar: () => void;
  toggleFocusMode: () => void;
}

export function useShellLayout(): ShellLayout {
  const isDesktop = useMediaQuery(DESKTOP_QUERY, true);
  const breakpoint: Breakpoint = isDesktop ? 'lg' : 'md';
  const [prefs, setPrefs] = useState<CollapsePrefs>(readPrefs);
  const [focusMode, setFocusMode] = useState(false);

  const collapsed = prefs[breakpoint] ?? !isDesktop;

  const toggleSidebar = useCallback(() => {
    if (focusMode) {
      setFocusMode(false);
      return;
    }
    setPrefs((prev) => {
      const next = { ...prev, [breakpoint]: !(prev[breakpoint] ?? !isDesktop) };
      writePrefs(next);
      return next;
    });
  }, [focusMode, breakpoint, isDesktop]);

  const toggleFocusMode = useCallback(() => setFocusMode((on) => !on), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.repeat || e.altKey || !(e.metaKey || e.ctrlKey)) return;
      if (!matches(TABLET_UP_QUERY, true)) return;
      const key = e.key.toLowerCase();
      if (key === 'b' && !e.shiftKey) {
        e.preventDefault();
        toggleSidebar();
      } else if (key === 'f' && e.shiftKey) {
        e.preventDefault();
        toggleFocusMode();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [toggleSidebar, toggleFocusMode]);

  return { collapsed, focusMode, toggleSidebar, toggleFocusMode };
}
