/**
 * Generated files for a stage or execution: file explorer, preview, copy and downloads.
 * Rendered only when the backend returned a validated artifact; otherwise the plain
 * Markdown output is shown exactly as before.
 */
import React, { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Download, FileCode2, FileText, Folder, Package } from 'lucide-react';
import type { Artifact, ArtifactFile } from '../../types/execution';
import { downloadErrorMessage, saveBlob, saveTextFile } from '../../lib/download';
import { CopyButton, MarkdownRenderer } from './MarkdownRenderer';

// ---------- download state shared by every download button ----------

export const useDownload = () => {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = async (key: string, fetchBlob: () => Promise<Blob>, filename: string) => {
    setBusy(key);
    setError(null);
    try {
      saveBlob(await fetchBlob(), filename);
    } catch (e) {
      setError(await downloadErrorMessage(e));
    } finally {
      setBusy(null);
    }
  };
  return { busy, error, run };
};

const buttonClass =
  'inline-flex items-center gap-1.5 rounded-md border border-surface-700 px-2.5 py-1 text-xs font-medium text-surface-200/80 hover:border-primary-500/40 hover:text-white disabled:opacity-50';

export const DownloadError: React.FC<{ message: string | null }> = ({ message }) =>
  message ? (
    <p role="alert" className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-300">
      Download failed: {message}
    </p>
  ) : null;

// ---------- file tree ----------

export interface TreeNode {
  name: string;
  path: string;
  file?: ArtifactFile;
  children?: TreeNode[];
}

/** Nested folders from flat paths; folders first, then files, each alphabetical. */
export const buildFileTree = (files: ArtifactFile[]): TreeNode[] => {
  const root: TreeNode = { name: '', path: '', children: [] };
  for (const file of files) {
    const parts = file.path.split('/');
    let node = root;
    parts.forEach((part, i) => {
      const path = parts.slice(0, i + 1).join('/');
      if (i === parts.length - 1) {
        node.children!.push({ name: part, path, file });
        return;
      }
      let dir = node.children!.find((c) => c.children && c.name === part);
      if (!dir) {
        dir = { name: part, path, children: [] };
        node.children!.push(dir);
      }
      node = dir;
    });
  }
  const sort = (nodes: TreeNode[]): TreeNode[] =>
    nodes
      .map((n) => (n.children ? { ...n, children: sort(n.children) } : n))
      .sort((a, b) => Number(!!b.children) - Number(!!a.children) || a.name.localeCompare(b.name));
  return sort(root.children!);
};

const TreeLevel: React.FC<{
  nodes: TreeNode[];
  depth: number;
  selected: string;
  onSelect: (file: ArtifactFile) => void;
}> = ({ nodes, depth, selected, onSelect }) => {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const toggle = (path: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  return (
    <ul className="space-y-0.5">
      {nodes.map((node) => {
        const pad = { paddingLeft: `${depth * 14 + 6}px` };
        if (node.children) {
          const open = !collapsed.has(node.path);
          return (
            <li key={node.path}>
              <button
                type="button"
                onClick={() => toggle(node.path)}
                aria-expanded={open}
                style={pad}
                className="flex w-full items-center gap-1.5 rounded py-1 pr-2 text-left text-xs text-surface-200/80 hover:bg-surface-700/40"
              >
                {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                <Folder size={13} className="text-surface-200/50" />
                <span className="truncate">{node.name}</span>
              </button>
              {open && <TreeLevel nodes={node.children} depth={depth + 1} selected={selected} onSelect={onSelect} />}
            </li>
          );
        }
        const active = node.path === selected;
        return (
          <li key={node.path}>
            <button
              type="button"
              onClick={() => onSelect(node.file!)}
              aria-current={active ? 'true' : undefined}
              title={node.path}
              style={{ paddingLeft: `${depth * 14 + 25}px` }}
              className={`flex w-full items-center gap-1.5 rounded py-1 pr-2 text-left font-mono text-xs ${
                active ? 'bg-primary-500/15 text-primary-300' : 'text-surface-200/70 hover:bg-surface-700/40 hover:text-white'
              }`}
            >
              <FileCode2 size={13} className="shrink-0" />
              <span className="truncate">{node.name}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
};

export const FileTree: React.FC<{ files: ArtifactFile[]; selected: string; onSelect: (file: ArtifactFile) => void }> = ({
  files, selected, onSelect,
}) => {
  const tree = useMemo(() => buildFileTree(files), [files]);
  return (
    <nav aria-label="Generated files" className="max-h-[32rem] overflow-y-auto rounded-lg border border-surface-700 bg-surface-900/40 p-2">
      <TreeLevel nodes={tree} depth={0} selected={selected} onSelect={onSelect} />
    </nav>
  );
};

// ---------- file preview ----------

/** A fence longer than any backtick run in the file, so the content can never close it early. */
const fenced = (file: ArtifactFile) => {
  const longest = Math.max(0, ...(file.content.match(/`+/g) ?? []).map((run) => run.length));
  const fence = '`'.repeat(Math.max(3, longest + 1));
  const content = file.content.endsWith('\n') ? file.content : `${file.content}\n`;
  return `${fence}${file.language === 'text' ? '' : file.language}\n${content}${fence}`;
};

export const FileViewer: React.FC<{ file: ArtifactFile }> = ({ file }) => (
  <div data-testid="file-viewer" className="min-w-0">
    <div className="flex items-center justify-between gap-2">
      <p className="truncate font-mono text-xs text-surface-200/80" title={file.path}>{file.path}</p>
      <div className="flex shrink-0 items-center gap-1">
        <CopyButton text={file.content} label="Copy" />
        <button type="button" onClick={() => saveTextFile(file.content, file.path)} className={buttonClass}>
          <Download size={13} /> Download
        </button>
      </div>
    </div>
    <MarkdownRenderer content={fenced(file)} idPrefix={`file-${file.path.replace(/[^a-zA-Z0-9]+/g, "-")}`} />
  </div>
);

// ---------- artifact ----------

const TYPE_LABELS: Record<string, string> = { project: 'Project', code: 'Code file', structured: 'Data file' };

export const ArtifactOutput: React.FC<{
  artifact: Artifact;
  /** Fetches the ZIP; omitted → no ZIP button */
  getZip?: () => Promise<Blob>;
  zipName?: string;
}> = ({ artifact, getZip, zipName }) => {
  const [selected, setSelected] = useState<ArtifactFile>(artifact.files[0]);
  const { busy, error, run } = useDownload();
  const current = artifact.files.find((f) => f.path === selected?.path) ?? artifact.files[0];
  if (!current) return null;
  const multi = artifact.files.length > 1;

  return (
    <div data-testid="artifact-output" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Package size={15} className="shrink-0 text-primary-400" />
          <span className="text-[11px] font-semibold uppercase tracking-wider text-surface-200/50">
            {TYPE_LABELS[artifact.artifact_type] ?? 'Files'}
          </span>
          <span className="truncate text-sm font-semibold text-white">{artifact.name}</span>
          <span className="text-xs text-surface-200/40">
            {artifact.files.length} file{artifact.files.length === 1 ? '' : 's'}
          </span>
        </div>
        {getZip && multi && (
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => run('zip', getZip, zipName ?? 'project.zip')}
            className={buttonClass}
          >
            <Download size={13} /> {busy === 'zip' ? 'Preparing…' : 'Download ZIP'}
          </button>
        )}
      </div>
      <DownloadError message={error} />
      {artifact.conflicts.length > 0 && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          <p className="font-semibold">Some stages wrote the same file; the later stage's version is used:</p>
          <ul className="mt-1 list-disc pl-5">
            {artifact.conflicts.map((c, i) => (
              <li key={`${c.path}-${i}`}>
                <span className="font-mono">{c.path}</span>: {c.kept_from} replaced {c.overridden_from}
              </li>
            ))}
          </ul>
        </div>
      )}
      {multi ? (
        <div className="grid gap-3 md:grid-cols-[minmax(12rem,16rem)_minmax(0,1fr)]">
          <FileTree files={artifact.files} selected={current.path} onSelect={setSelected} />
          <FileViewer file={current} />
        </div>
      ) : (
        <FileViewer file={current} />
      )}
    </div>
  );
};

// ---------- PDF / TXT of a stage's output ----------

export const DocumentDownloads: React.FC<{
  getDocument: (format: 'pdf' | 'txt') => Promise<Blob>;
  baseName: string;
}> = ({ getDocument, baseName }) => {
  const { busy, error, run } = useDownload();
  return (
    <div data-testid="document-downloads">
      <div className="flex items-center gap-1.5">
        {(['pdf', 'txt'] as const).map((format) => (
          <button
            key={format}
            type="button"
            disabled={busy !== null}
            onClick={() => run(format, () => getDocument(format), `${baseName}.${format}`)}
            className={buttonClass}
          >
            <FileText size={13} /> {busy === format ? 'Preparing…' : format.toUpperCase()}
          </button>
        ))}
      </div>
      <DownloadError message={error} />
    </div>
  );
};
