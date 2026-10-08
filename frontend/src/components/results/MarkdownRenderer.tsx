/**
 * Safe Markdown rendering for LLM stage output.
 *
 * react-markdown never renders raw HTML (it is escaped) and its default URL transform drops
 * unsafe protocols such as `javascript:`. Syntax highlighting comes from rehype-highlight,
 * which produces React elements, so nothing is injected as HTML.
 */
import React, { useMemo, useState } from 'react';
import Markdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { Check, ChevronDown, ChevronRight, Copy } from 'lucide-react';

// ---------- hast helpers (minimal shapes; avoids a direct @types/hast dependency) ----------

interface HastNode {
  type: string;
  tagName?: string;
  value?: string;
  properties?: Record<string, unknown>;
  children?: HastNode[];
}

const hastText = (node: HastNode | undefined): string =>
  !node ? '' : node.type === 'text' ? node.value ?? '' : (node.children ?? []).map(hastText).join('');

const walk = (node: HastNode, visit: (n: HastNode) => void) => {
  visit(node);
  node.children?.forEach((child) => walk(child, visit));
};

const reactText = (node: React.ReactNode): string => {
  if (node == null || typeof node === 'boolean') return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(reactText).join('');
  if (React.isValidElement(node)) return reactText((node.props as { children?: React.ReactNode }).children);
  return '';
};

// ---------- heading ids + table of contents ----------

export const slugify = (text: string): string =>
  text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'section';

const dedupe = () => {
  const seen = new Map<string, number>();
  return (slug: string) => {
    const n = (seen.get(slug) ?? 0) + 1;
    seen.set(slug, n);
    return n === 1 ? slug : `${slug}-${n}`;
  };
};

/** rehype plugin: give h1–h3 stable, prefixed ids so the outline can link to them. */
const rehypeHeadingIds = (prefix: string) => () => (tree: HastNode) => {
  const unique = dedupe();
  walk(tree, (node) => {
    if (node.type === 'element' && /^h[1-3]$/.test(node.tagName ?? '')) {
      node.properties = { ...node.properties, id: `${prefix}-${unique(slugify(hastText(node)))}` };
    }
  });
};

export interface OutlineEntry {
  level: number;
  text: string;
  id: string;
}

const stripInline = (text: string) =>
  text
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1') // links / images → label
    .replace(/[*`]/g, '')
    .replace(/(^|\s)_+|_+(?=\s|$)/g, '$1')
    .trim();

/**
 * ATX headings (h1–h3) outside fenced code, with the same ids rehypeHeadingIds assigns.
 * Returns the entries of the most useful level for navigation, or [] when there are too few.
 */
export const buildOutline = (markdown: string, prefix: string): OutlineEntry[] => {
  const unique = dedupe();
  const all: OutlineEntry[] = [];
  let fence: string | null = null;
  for (const line of markdown.split('\n')) {
    const fenceMatch = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (fenceMatch) {
      if (!fence) fence = fenceMatch[1][0];
      else if (fenceMatch[1][0] === fence) fence = null;
      continue;
    }
    if (fence) continue;
    const heading = line.match(/^\s{0,3}(#{1,3})\s+(.+?)\s*#*\s*$/);
    if (heading) {
      const text = stripInline(heading[2]);
      all.push({ level: heading[1].length, text, id: `${prefix}-${unique(slugify(text))}` });
    }
  }
  for (const level of [1, 2, 3]) {
    const entries = all.filter((h) => h.level === level);
    if (entries.length >= 3) return entries;
  }
  return [];
};

// ---------- numeric table columns ----------

const NUMERIC = /^[\s$€£¥~≈<>+\-−]*\d[\d,.]*\s*(%|ms|s|x|k|m|b|gb|mb|kb|tb|h|min)?\s*$/i;

/** rehype plugin: right-align table columns whose body cells are all numeric (unless aligned in Markdown). */
const rehypeNumericColumns = () => (tree: HastNode) => {
  walk(tree, (table) => {
    if (table.type !== 'element' || table.tagName !== 'table') return;
    const rows: HastNode[] = [];
    walk(table, (n) => n.type === 'element' && n.tagName === 'tr' && rows.push(n));
    const cells = rows.map((r) => (r.children ?? []).filter((c) => c.type === 'element'));
    const [header, ...body] = cells;
    if (!header || body.length === 0) return;
    header.forEach((_, col) => {
      const column = body.map((row) => row[col]).filter(Boolean);
      const texts = column.map((c) => hastText(c).trim()).filter(Boolean);
      if (texts.length === 0 || !texts.every((t) => NUMERIC.test(t))) return;
      for (const cell of [header[col], ...column]) {
        if (!cell.properties?.align) cell.properties = { ...cell.properties, align: 'right' };
      }
    });
  });
};

// ---------- code blocks ----------

const LANGUAGE_LABELS: Record<string, string> = {
  py: 'Python', python: 'Python', sql: 'SQL', yaml: 'YAML', yml: 'YAML', json: 'JSON',
  js: 'JavaScript', javascript: 'JavaScript', jsx: 'JSX', ts: 'TypeScript', typescript: 'TypeScript',
  tsx: 'TSX', bash: 'Bash', sh: 'Shell', shell: 'Shell', zsh: 'Shell', powershell: 'PowerShell',
  ps1: 'PowerShell', html: 'HTML', xml: 'XML', css: 'CSS', java: 'Java', go: 'Go', rust: 'Rust',
  c: 'C', cpp: 'C++', csharp: 'C#', cs: 'C#', dockerfile: 'Dockerfile', ini: 'INI', toml: 'TOML',
  markdown: 'Markdown', md: 'Markdown', text: 'Text', plaintext: 'Text', mermaid: 'Mermaid',
};

const languageOf = (node: HastNode | undefined): string | null => {
  const code = node?.children?.find((c) => c.type === 'element' && c.tagName === 'code');
  const classes = (code?.properties?.className as string[] | undefined) ?? [];
  const lang = classes.find((c) => c.startsWith('language-'));
  return lang ? lang.slice('language-'.length) : null;
};

/** Code blocks longer than this get a collapse toggle... */
const COLLAPSIBLE_LINES = 30;
/** ...and start collapsed (as a preview) beyond this. */
const COLLAPSED_BY_DEFAULT_LINES = 80;

export const CopyButton: React.FC<{ text: string; label?: string; className?: string }> = ({
  text, label = 'Copy', className = '',
}) => {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable (insecure context / permissions) */
    }
  };
  return (
    <button
      type="button"
      onClick={copy}
      aria-label={copied ? 'Copied' : label}
      className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-surface-200/60 hover:text-white hover:bg-surface-700/60 transition-colors ${className}`}
    >
      {copied ? <Check size={13} className="text-primary-400" /> : <Copy size={13} />}
      {copied ? 'Copied' : label}
    </button>
  );
};

export const CodeBlock: React.FC<{ node?: HastNode; children?: React.ReactNode }> = ({ node, children }) => {
  const code = hastText(node).replace(/\n$/, '');
  const lines = code.split('\n').length;
  const lang = languageOf(node);
  const label = lang ? LANGUAGE_LABELS[lang.toLowerCase()] ?? lang : 'Code';
  const collapsible = lines > COLLAPSIBLE_LINES;
  const [expanded, setExpanded] = useState(lines <= COLLAPSED_BY_DEFAULT_LINES);

  return (
    <div className="md-code my-4 overflow-hidden rounded-lg border border-surface-700 bg-[#0d0d0d]">
      <div className="flex items-center justify-between gap-2 border-b border-surface-700 bg-surface-800/80 px-3 py-1.5">
        {collapsible ? (
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            aria-expanded={expanded}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-surface-200/80 hover:text-white"
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {label}
            <span className="font-normal text-surface-200/40">· {lines} lines</span>
          </button>
        ) : (
          <span className="text-xs font-semibold text-surface-200/70">{label}</span>
        )}
        <CopyButton text={code} />
      </div>
      <div className="relative">
        <pre
          className={`overflow-x-auto p-4 text-[13px] leading-6 font-mono ${expanded ? '' : 'max-h-56 overflow-y-hidden'}`}
        >
          {children}
        </pre>
        {!expanded && (
          <div className="absolute inset-x-0 bottom-0 flex justify-center bg-gradient-to-t from-[#0d0d0d] via-[#0d0d0d]/90 to-transparent pb-3 pt-10">
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="rounded-md border border-surface-700 bg-surface-800 px-3 py-1 text-xs font-medium text-surface-200/80 hover:text-white"
            >
              Show all {lines} lines
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

// ---------- element styling ----------

const components: Components = {
  h1: ({ node: _n, ...p }) => <h1 className="scroll-mt-16 mt-8 mb-3 text-xl font-semibold tracking-tight text-white first:mt-0" {...p} />,
  h2: ({ node: _n, ...p }) => (
    <h2 className="scroll-mt-16 mt-8 mb-3 border-b border-surface-700 pb-2 text-lg font-semibold tracking-tight text-white first:mt-0" {...p} />
  ),
  h3: ({ node: _n, ...p }) => <h3 className="scroll-mt-16 mt-6 mb-2 text-base font-semibold text-white first:mt-0" {...p} />,
  h4: ({ node: _n, ...p }) => <h4 className="mt-5 mb-2 text-sm font-semibold text-surface-100" {...p} />,
  h5: ({ node: _n, ...p }) => <h5 className="mt-4 mb-1 text-sm font-semibold text-surface-200/80" {...p} />,
  h6: ({ node: _n, ...p }) => <h6 className="mt-4 mb-1 text-xs font-semibold uppercase tracking-wide text-surface-200/60" {...p} />,
  p: ({ node: _n, ...p }) => <p className="my-3 leading-7 text-surface-200/90" {...p} />,
  strong: ({ node: _n, ...p }) => <strong className="font-semibold text-white" {...p} />,
  em: ({ node: _n, ...p }) => <em className="italic text-surface-100" {...p} />,
  a: ({ node: _n, ...p }) => (
    <a
      className="text-primary-400 underline decoration-primary-400/40 underline-offset-2 hover:decoration-primary-400 break-words"
      target="_blank"
      rel="noopener noreferrer nofollow"
      {...p}
    />
  ),
  ul: ({ node: _n, ...p }) => <ul className="my-3 list-disc space-y-1.5 pl-6 marker:text-surface-200/40" {...p} />,
  ol: ({ node: _n, ...p }) => <ol className="my-3 list-decimal space-y-1.5 pl-6 marker:text-surface-200/50" {...p} />,
  li: ({ node: _n, ...p }) => <li className="leading-7 text-surface-200/90 pl-1 [&>p]:my-1 [&>ul]:my-1.5 [&>ol]:my-1.5" {...p} />,
  blockquote: ({ node: _n, ...p }) => (
    <blockquote className="my-4 rounded-r-md border-l-2 border-primary-500/60 bg-surface-900/60 px-4 py-1 text-surface-200/80 [&>p]:my-2" {...p} />
  ),
  hr: () => <hr className="my-6 border-surface-700" />,
  pre: ({ node, children }) => <CodeBlock node={node as HastNode}>{children}</CodeBlock>,
  code: ({ node: _n, className, children, ...p }) => {
    const isBlock = /language-|hljs/.test(className ?? '') || reactText(children).includes('\n');
    if (isBlock) return <code className={className} {...p}>{children}</code>;
    return (
      <code
        className="rounded border border-surface-700 bg-surface-900 px-1.5 py-0.5 font-mono text-[0.85em] text-surface-100 break-words"
        {...p}
      >
        {children}
      </code>
    );
  },
  table: ({ node: _n, ...p }) => (
    <div className="my-4 overflow-x-auto rounded-lg border border-surface-700">
      <table className="w-full border-collapse text-sm tabular-nums" {...p} />
    </div>
  ),
  thead: ({ node: _n, ...p }) => <thead className="bg-surface-900" {...p} />,
  tbody: ({ node: _n, ...p }) => <tbody className="[&>tr:nth-child(even)]:bg-white/[0.025]" {...p} />,
  tr: ({ node: _n, ...p }) => <tr className="border-t border-surface-700/70" {...p} />,
  th: ({ node: _n, ...p }) => (
    <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-surface-200/60" {...p} />
  ),
  td: ({ node: _n, ...p }) => <td className="px-3 py-2 align-top leading-6 text-surface-200/90 min-w-[8rem] first:min-w-0" {...p} />,
  img: ({ node: _n, alt, ...p }) => <img alt={alt ?? ''} loading="lazy" className="my-3 max-w-full rounded" {...p} />,
};

// ---------- renderer ----------

export const MarkdownRenderer: React.FC<{ content: string; idPrefix: string }> = ({ content, idPrefix }) => {
  const rehypePlugins = useMemo(
    () => [[rehypeHighlight, { detect: false }], rehypeHeadingIds(idPrefix), rehypeNumericColumns] as never[],
    [idPrefix],
  );
  return (
    <div className="md-body min-w-0 text-[15px] break-words">
      <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={rehypePlugins} components={components}>
        {content}
      </Markdown>
    </div>
  );
};
