/**
 * Application shell. Mercury frames the light canvas with its night colour: a night sidebar and
 * a light top bar with breadcrumbs above the page.
 *
 * The sidebar has three states on md and up (see useShellLayout): expanded, collapsed to an
 * icon rail, and hidden in focus mode. All three are one element whose width eases between
 * 256px, 72px and 0; everything inside is laid out against the left edge so icons stay put
 * while labels fade. Phones use a drawer instead.
 *
 * The page <Outlet> keeps the same position in the tree in every state, so toggling never
 * remounts the page: form input, workflow state, live execution sockets and scroll survive.
 */
import { useEffect, useId, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Outlet, NavLink, Link, useLocation, matchPath } from 'react-router-dom';
import {
  Sparkles, LayoutDashboard, GitBranch, Database, Zap, Cpu, LogOut, Menu, X, Network, Boxes, ChevronRight, Plus,
  PanelLeftClose, PanelLeftOpen, Maximize2, Minimize2,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { MOD_KEY, useShellLayout } from '../hooks/useShellLayout';
import { PageTransition } from './motion/Motion';
import { Tooltip } from './ui/Tooltip';
import { EASE, transition } from '../lib/motion';

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
  end?: boolean;
}

const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Build',
    items: [
      { to: '/', icon: Sparkles, label: 'New Workflow', end: true },
      { to: '/workflows', icon: GitBranch, label: 'Workflows' },
      { to: '/executions', icon: Zap, label: 'Executions' },
      { to: '/projects', icon: Boxes, label: 'Projects' },
    ],
  },
  {
    title: 'Insights',
    items: [
      { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/cache', icon: Database, label: 'Cache' },
      { to: '/models', icon: Cpu, label: 'Models & Routing' },
    ],
  },
];

interface Crumb { label: string; to?: string }

/** Breadcrumb trail for the current route (route params have no names here, so ids read as "Workflow"). */
export const breadcrumbsFor = (pathname: string): Crumb[] => {
  const match = (pattern: string) => matchPath({ path: pattern, end: true }, pathname);
  let m;
  if (match('/')) return [{ label: 'Build' }, { label: 'New workflow' }];
  if (match('/workflows')) return [{ label: 'Build' }, { label: 'Workflows' }];
  if (match('/workflows/new')) return [{ label: 'Workflows', to: '/workflows' }, { label: 'Create manually' }];
  if ((m = match('/workflows/:id/edit'))) {
    return [{ label: 'Workflows', to: '/workflows' }, { label: 'Workflow', to: `/workflows/${m.params.id}` }, { label: 'Edit' }];
  }
  if (match('/workflows/:id')) return [{ label: 'Workflows', to: '/workflows' }, { label: 'Workflow' }];
  if (match('/executions')) return [{ label: 'Build' }, { label: 'Executions' }];
  if (match('/projects')) return [{ label: 'Build' }, { label: 'Projects' }];
  if (match('/dashboard')) return [{ label: 'Insights' }, { label: 'Dashboard' }];
  if (match('/cache')) return [{ label: 'Insights' }, { label: 'Semantic cache' }];
  if (match('/models')) return [{ label: 'Insights' }, { label: 'Models & routing' }];
  return [];
};

const BrandMark = () => (
  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-primary">
    <Network size={16} className="text-white" aria-hidden />
  </span>
);

/** Fades labels out when the rail collapses (they stay in place, clipped by the sidebar) */
const fadeLabel = (hidden: boolean) =>
  `whitespace-nowrap transition-opacity duration-200 ease-soft ${hidden ? 'pointer-events-none opacity-0' : 'opacity-100 delay-100'}`;

const navLinkClass = (compact: boolean) => ({ isActive }: { isActive: boolean }) =>
  // Fixed left padding in both states so the icon sits on the rail's centre line (36px)
  `group relative flex items-center gap-3 rounded-[10px] px-[15px] py-2 text-sm font-book
   transition-[width,background-color,color] duration-300 ease-mercury focus-visible:ring-2 focus-visible:ring-primary/60 ${
    compact ? 'w-12' : 'w-full'
  } ${
    isActive
      ? 'text-on-dark'
      : 'text-fog hover:bg-[rgba(175,178,206,0.08)] hover:text-on-dark'
  }`;

const Avatar = ({ name }: { name: string }) => (
  <span
    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[rgba(156,180,232,0.2)] text-sm font-medium text-on-dark"
    aria-hidden
  >
    {name.charAt(0).toUpperCase()}
  </span>
);

function Sidebar({ compact = false, onClose }: { compact?: boolean; onClose?: () => void }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  // Each sidebar instance (desktop, drawer) slides its own active indicator
  const indicatorId = useId();
  return (
    <div className="flex h-full flex-col bg-night">
      <div className="flex h-16 shrink-0 items-center px-5">
        <Link
          to="/"
          aria-label="AI Orchestrator home"
          className="flex min-w-0 items-center gap-2.5 rounded-lg focus-visible:ring-2 focus-visible:ring-primary/50"
        >
          <BrandMark />
          <span className={`text-[15px] font-medium tracking-[0.01em] text-on-dark ${fadeLabel(compact)}`}>AI Orchestrator</span>
        </Link>
        {onClose && (
          <button onClick={onClose} className="btn btn-glass btn-icon btn-sm ml-auto" aria-label="Close navigation">
            <X size={16} />
          </button>
        )}
      </div>

      <nav className="flex-1 space-y-7 overflow-y-auto overflow-x-hidden px-3 pb-4 pt-3" aria-label="Main">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title}>
            <div className="relative mb-2 h-3">
              <p className={`px-3 text-eyebrow font-semibold uppercase text-slate ${fadeLabel(compact)}`}>{section.title}</p>
              <span
                aria-hidden
                className={`absolute left-3 top-1/2 h-px w-6 bg-night-line transition-opacity duration-200 ease-soft ${compact ? 'opacity-100' : 'opacity-0'}`}
              />
            </div>
            <div className="space-y-0.5">
              {section.items.map(({ to, icon: Icon, label, end }) => (
                <Tooltip key={to} label={label} enabled={compact}>
                  <NavLink to={to} end={end} className={navLinkClass(compact)} aria-label={compact ? label : undefined}>
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <>
                            <motion.span
                              layoutId={`${indicatorId}-bg`}
                              layoutDependency={pathname}
                              transition={transition.indicator}
                              aria-hidden
                              className="absolute inset-0 rounded-[10px] bg-[rgba(175,178,206,0.14)]"
                            />
                            <motion.span
                              layoutId={`${indicatorId}-bar`}
                              layoutDependency={pathname}
                              transition={transition.indicator}
                              aria-hidden
                              className="absolute -left-3 h-5 w-[3px] rounded-full bg-primary"
                            />
                          </>
                        )}
                        <Icon
                          size={17}
                          strokeWidth={1.75}
                          aria-hidden
                          className={`relative shrink-0 transition-[color,transform] duration-300 ease-mercury group-hover:scale-110 motion-reduce:group-hover:scale-100 ${
                            isActive ? 'text-periwinkle' : ''
                          }`}
                        />
                        <span className={`relative ${fadeLabel(compact)}`}>{label}</span>
                      </>
                    )}
                  </NavLink>
                </Tooltip>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {user && (
        <div className="shrink-0 border-t border-night-line">
          {compact ? (
            // Left-anchored on the rail's centre line, like the icons above
            <div key="compact" className="flex animate-fade-in flex-col items-start gap-2 py-3 pl-[18px]">
              <Tooltip label={`${user.full_name} · ${user.email}`}>
                <span tabIndex={0} aria-label={`Signed in as ${user.full_name}`} className="rounded-full focus-visible:ring-2 focus-visible:ring-primary/60">
                  <Avatar name={user.full_name} />
                </span>
              </Tooltip>
              <Tooltip label="Log out">
                <button onClick={logout} className="btn btn-glass btn-icon btn-sm ml-0.5" aria-label="Log out">
                  <LogOut size={15} />
                </button>
              </Tooltip>
            </div>
          ) : (
            <div key="full" className="animate-fade-in p-3">
              <div className="flex items-center gap-3 rounded-card px-2 py-1.5">
                <Avatar name={user.full_name} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-book text-on-dark">{user.full_name}</p>
                  <p className="truncate text-xs text-fog/80">{user.email}</p>
                </div>
                <button onClick={logout} className="btn btn-glass btn-icon btn-sm" aria-label="Log out" title="Log out">
                  <LogOut size={15} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  if (crumbs.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1.5 text-[13px]">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li key={`${c.label}-${i}`} className={`flex min-w-0 items-center gap-1.5 ${last ? '' : 'hidden sm:flex'}`}>
              {c.to && !last ? (
                <Link to={c.to} className="truncate text-ink-muted transition-colors hover:text-ink">{c.label}</Link>
              ) : (
                <span className={`truncate ${last ? 'font-book text-ink' : 'text-ink-muted'}`} aria-current={last ? 'page' : undefined}>
                  {c.label}
                </span>
              )}
              {!last && <ChevronRight size={13} className="shrink-0 text-ink-faint" aria-hidden />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** Icon that swaps with a short pop when its state flips */
const SwapIcon = ({ icon: Icon, swapKey }: { icon: LucideIcon; swapKey: string }) => (
  <span key={swapKey} className="flex animate-pop-in">
    <Icon size={18} strokeWidth={1.75} aria-hidden />
  </span>
);

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const { collapsed, focusMode, toggleSidebar, toggleFocusMode } = useShellLayout();
  const crumbs = breadcrumbsFor(location.pathname);
  // Pages whose own header already offers "New workflow" don't repeat it in the top bar
  const hideTopCta = location.pathname === '/' || location.pathname === '/workflows';

  // Close the mobile drawer after navigating
  useEffect(() => setMenuOpen(false), [location.pathname]);

  // Escape closes the drawer
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menuOpen]);

  const sidebarLabel = focusMode ? 'Show sidebar' : collapsed ? 'Expand sidebar' : 'Collapse sidebar';
  const focusLabel = focusMode ? 'Exit focus mode' : 'Enter focus mode';

  return (
    <div className="flex h-[100dvh] overflow-hidden bg-canvas">
      {/* Sidebar (md and up): expanded, icon rail, or hidden in focus mode */}
      <aside
        id="app-sidebar"
        data-state={focusMode ? 'hidden' : collapsed ? 'collapsed' : 'expanded'}
        className={`relative hidden shrink-0 overflow-hidden bg-night transition-[width,visibility] duration-300 ease-mercury md:block ${
          focusMode ? 'invisible w-0' : collapsed ? 'w-[72px]' : 'w-64'
        }`}
      >
        {/* Fixed inner width: the aside clips it, so nothing reflows mid-transition */}
        <div className="h-full w-64">
          <Sidebar compact={collapsed} />
        </div>
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {menuOpen && (
          <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
            <motion.div
              className="absolute inset-0 bg-night/60 backdrop-blur-[2px]"
              onClick={() => setMenuOpen(false)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: EASE.soft }}
            />
            <motion.aside
              className="relative h-full w-[min(18rem,85vw)] shadow-pop"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.4, ease: EASE.out }}
            >
              <Sidebar onClose={() => setMenuOpen(false)} />
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-hairline bg-canvas/90 px-4 backdrop-blur sm:px-6 lg:px-10">
          <button onClick={() => setMenuOpen(true)} className="btn btn-ghost btn-icon -ml-2 md:hidden" aria-label="Open navigation">
            <Menu size={19} />
          </button>
          <button
            onClick={toggleSidebar}
            className="btn btn-ghost btn-icon -ml-2 hidden md:inline-flex"
            aria-label={sidebarLabel}
            aria-controls="app-sidebar"
            aria-expanded={!focusMode && !collapsed}
            title={`${sidebarLabel} (${MOD_KEY}+B)`}
          >
            <SwapIcon icon={focusMode || collapsed ? PanelLeftOpen : PanelLeftClose} swapKey={focusMode || collapsed ? 'open' : 'close'} />
          </button>
          <div className={`items-center ${focusMode ? 'flex' : 'flex md:hidden'}`}>
            <Link to="/" aria-label="AI Orchestrator home" className="animate-fade-in"><BrandMark /></Link>
          </div>
          <div className="h-5 w-px shrink-0 bg-hairline max-md:hidden" aria-hidden />
          <div className="min-w-0 flex-1">
            <Breadcrumbs crumbs={crumbs} />
          </div>
          {!hideTopCta && (
            <Link to="/" className="btn btn-secondary btn-sm">
              <Plus size={14} aria-hidden />
              <span className="hidden sm:inline">New workflow</span>
              <span className="sr-only sm:hidden">New workflow</span>
            </Link>
          )}
          <button
            onClick={toggleFocusMode}
            className={`btn btn-icon -mr-2 hidden md:inline-flex ${focusMode ? 'btn-secondary' : 'btn-ghost'}`}
            aria-label={focusLabel}
            aria-pressed={focusMode}
            title={`${focusLabel} (${MOD_KEY}+Shift+F)`}
          >
            <SwapIcon icon={focusMode ? Minimize2 : Maximize2} swapKey={focusMode ? 'min' : 'max'} />
          </button>
        </header>

        <main className="flex-1 overflow-y-auto" id="main">
          <div
            className={`mx-auto w-full px-4 pb-16 pt-6 transition-[max-width] duration-500 ease-mercury sm:px-6 sm:pt-8 lg:px-10 lg:pt-10 ${
              focusMode ? 'max-w-[100vw]' : 'max-w-content'
            }`}
          >
            {/* Keyed by route: the entry plays on navigation, not on re-renders, live updates or layout toggles */}
            <PageTransition key={location.pathname}>
              <Outlet />
            </PageTransition>
          </div>
        </main>
      </div>
    </div>
  );
}
