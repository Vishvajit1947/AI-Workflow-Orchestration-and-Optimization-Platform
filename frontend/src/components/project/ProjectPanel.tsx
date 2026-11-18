/**
 * A workflow's generated project: build status, steps (install / build / test) with logs,
 * automatic repair attempts, the file explorer and the ZIP download.
 * Polls while the project is building.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Download, Loader2, Wrench, XCircle } from 'lucide-react';
import { projectsApi, type Project, type ProjectFile, type ProjectRun, type ProjectStep } from '../../api/projectsApi';
import { ArtifactOutput, DownloadError, useDownload } from '../results/ArtifactOutput';
import { StatusBadge } from '../ui/StatusBadge';
import { safeFileStem } from '../../lib/download';
import { formatDuration } from '../../lib/format';
import { getErrorMessage } from '../../lib/errors';

const POLL_MS = 2500;

const HEADLINE: Record<string, string> = {
  initializing: 'Preparing the project workspace…',
  building: 'Building and testing the project…',
  succeeded: 'Every install, build and test step passed.',
  failed: 'The project does not build yet. See the failing step and the repair attempts below.',
  cancelled: 'The build was cancelled.',
  unavailable: 'The project was generated, but the sandbox could not run it, so it has not been verified.',
};

export const ProjectPanel: React.FC<{ workflowId: string; active: boolean }> = ({ workflowId, active }) => {
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const filesFor = useRef<string | null>(null);
  const { busy, error: downloadError, run: download } = useDownload();

  const load = useCallback(async () => {
    try {
      const [latest] = await projectsApi.list(workflowId);
      setProject(latest ?? null);
      setError(null);
      // Refetch files when the project changed (new build or repair applied)
      const stamp = latest ? `${latest.id}:${latest.updated_at}:${latest.latest_run?.repairs.length ?? 0}` : null;
      if (latest && stamp !== filesFor.current) {
        filesFor.current = stamp;
        setFiles(await projectsApi.files(latest.id));
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    }
  }, [workflowId]);

  const building = active || project?.status === 'building' || project?.latest_run?.status === 'running';

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!building) return;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [building, load]);

  // When the build finishes, load the final state once more
  const wasBuilding = useRef(building);
  useEffect(() => {
    if (wasBuilding.current && !building) load();
    wasBuilding.current = building;
  }, [building, load]);

  if (error && !project) return <p className="text-sm text-red-400">Could not load the project: {error}</p>;
  if (!project) {
    return active ? (
      <div className="glass rounded-xl p-5 text-sm text-surface-200/50">
        The project appears here once its files have been generated.
      </div>
    ) : null;
  }

  const run = project.latest_run;
  const textFiles = files.filter((f) => f.content !== null).map((f) => ({ path: f.path, content: f.content as string, language: f.language }));
  const zipName = `${safeFileStem(project.name, 'project')}.zip`;

  return (
    <section className="glass space-y-5 rounded-xl p-5 sm:p-6" aria-label="Generated project" data-testid="project-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">Project</h2>
            <StatusBadge status={project.status} data-testid="project-status" />
            {project.project_type && project.project_type !== 'unknown' && (
              <span className="rounded bg-surface-700/50 px-2 py-0.5 text-xs text-surface-200/70">{project.project_type}</span>
            )}
          </div>
          <p className="mt-1 text-sm text-surface-200/60">{HEADLINE[project.status] ?? project.status}</p>
          {building && run?.current_step && (
            <p className="mt-1 flex items-center gap-2 text-sm text-blue-300" role="status">
              <Loader2 size={14} className="animate-spin" aria-hidden /> {run.current_step}
            </p>
          )}
        </div>
        {files.length > 0 && (
          <button type="button" className="btn btn-secondary" disabled={busy !== null}
                  onClick={() => download('zip', () => projectsApi.download(project.id), zipName)}>
            <Download size={14} aria-hidden /> {busy === 'zip' ? 'Preparing…' : 'Download ZIP'}
          </button>
        )}
      </div>
      <DownloadError message={downloadError} />

      {run && run.warnings.length > 0 && (
        <ul className="space-y-1 rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-xs text-amber-200">
          {run.warnings.map((w) => (
            <li key={w} className="flex gap-2"><AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden /> {w}</li>
          ))}
        </ul>
      )}

      {run && <RunDetails run={run} />}

      {textFiles.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-surface-200/80">Files</h3>
          <ArtifactOutput
            artifact={{ artifact_type: 'project', name: project.name, files: textFiles, conflicts: [] }}
          />
        </div>
      )}
    </section>
  );
};

const RunDetails: React.FC<{ run: ProjectRun }> = ({ run }) => {
  const attempts = [...new Set(run.steps.map((s) => s.attempt))].sort((a, b) => a - b);
  return (
    <div className="space-y-4">
      {attempts.map((attempt) => {
        const repair = run.repairs.find((r) => r.attempt === attempt);
        return (
          <div key={attempt} className="space-y-2">
            {repair && <RepairCard repair={repair} />}
            <h3 className="text-xs font-medium uppercase tracking-wider text-surface-200/40">
              {attempt === 0 ? 'Build' : `Rebuild after repair ${attempt}`}
            </h3>
            <ol className="space-y-1.5">
              {run.steps.filter((s) => s.attempt === attempt).map((step, i) => <StepRow key={i} step={step} />)}
            </ol>
          </div>
        );
      })}
      {/* A repair whose rebuild has not started (or that proposed no change) */}
      {run.repairs.filter((r) => !attempts.includes(r.attempt)).map((r) => <RepairCard key={r.attempt} repair={r} />)}
      {run.error_summary && run.status !== 'succeeded' && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4" role="alert">
          <p className="mb-1 text-sm font-medium text-red-300">Remaining error</p>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-xs text-red-200/90">
            {run.error_summary}
          </pre>
        </div>
      )}
    </div>
  );
};

const StepRow: React.FC<{ step: ProjectStep }> = ({ step }) => {
  const [open, setOpen] = useState(step.status === 'failed');
  const passed = step.status === 'passed';
  return (
    <li className="rounded-lg border border-surface-700/60 bg-surface-900/40">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
              className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/60">
        {passed
          ? <CheckCircle2 size={16} className="shrink-0 text-primary-400" aria-label="Passed" />
          : <XCircle size={16} className="shrink-0 text-red-400" aria-label="Failed" />}
        <span className="min-w-0 flex-1">
          <span className="font-medium text-white">{step.label}</span>
          <span className="ml-2 text-xs text-surface-200/40">{step.component}</span>
          <span className="block truncate font-mono text-xs text-surface-200/50">{step.command}</span>
        </span>
        <span className="shrink-0 text-xs tabular-nums text-surface-200/50">
          {step.timed_out ? 'timed out' : `exit ${step.exit_code ?? '–'}`} · {formatDuration(step.duration_ms)}
        </span>
        {open ? <ChevronDown size={14} aria-hidden /> : <ChevronRight size={14} aria-hidden />}
      </button>
      {open && (
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words border-t border-surface-700/60 px-3 py-2 font-mono text-xs text-surface-200/80">
          {step.output || '(no output)'}
        </pre>
      )}
    </li>
  );
};

const RepairCard: React.FC<{ repair: ProjectRun['repairs'][number] }> = ({ repair }) => (
  <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
    <p className="mb-1 flex items-center gap-2 text-sm font-medium text-amber-200">
      <Wrench size={14} aria-hidden /> Automatic repair {repair.attempt} · after “{repair.failed_step}” failed
    </p>
    <p className="text-sm text-surface-200/80">{repair.diagnosis}</p>
    {repair.files.length > 0 ? (
      <p className="mt-2 text-xs text-surface-200/60">
        Changed: {repair.files.map((f) => <code key={f.path} className="mr-2 font-mono">{f.path} ({f.action})</code>)}
      </p>
    ) : (
      <p className="mt-2 text-xs text-surface-200/60">No file was changed.</p>
    )}
    {repair.error && <p className="mt-1 text-xs text-red-300">{repair.error}</p>}
  </div>
);
