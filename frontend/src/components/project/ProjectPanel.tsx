/**
 * A workflow's generated project: build status, the build pipeline (install / build / test)
 * with terminal logs, automatic repair attempts, the file explorer and the ZIP download.
 * Polls while the project is building.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle, CheckCircle2, ChevronRight, Download, Loader2, Terminal, Wrench, XCircle, FileDiff, Boxes,
} from 'lucide-react';
import { projectsApi, type Project, type ProjectFile, type ProjectRun, type ProjectStep } from '../../api/projectsApi';
import { ArtifactOutput, DownloadError, useDownload } from '../results/ArtifactOutput';
import { StatusBadge } from '../ui/StatusBadge';
import { safeFileStem } from '../../lib/download';
import { formatDuration } from '../../lib/format';
import { Collapse } from '../motion/Motion';
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

  if (error && !project) {
    return <p className="rounded-card border border-danger-line bg-danger-soft px-4 py-3 text-sm text-danger">Could not load the project: {error}</p>;
  }
  if (!project) {
    return active ? (
      <div className="card flex items-center gap-3 p-5 text-sm text-ink-secondary">
        <Boxes size={17} className="shrink-0 text-primary" aria-hidden />
        The project appears here once its files have been generated.
      </div>
    ) : null;
  }

  const run = project.latest_run;
  const textFiles = files.filter((f) => f.content !== null).map((f) => ({ path: f.path, content: f.content as string, language: f.language }));
  const zipName = `${safeFileStem(project.name, 'project')}.zip`;
  const attempts = run ? new Set(run.steps.map((s) => s.attempt)).size : 0;

  return (
    <section className="card min-w-0 overflow-hidden" aria-label="Generated project" data-testid="project-panel">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-hairline bg-surface-tint px-5 py-4 sm:px-6">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-night text-periwinkle" aria-hidden>
            <Boxes size={18} strokeWidth={1.75} />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-[17px] font-medium text-ink">Project</h2>
              <StatusBadge status={project.status} data-testid="project-status" />
              {project.project_type && project.project_type !== 'unknown' && (
                <span className="chip font-mono !text-[11px]">{project.project_type}</span>
              )}
            </div>
            <p className="mt-1 text-sm text-ink-secondary">{HEADLINE[project.status] ?? project.status}</p>
            {building && run?.current_step && (
              <p key={run.current_step} className="mt-1.5 flex animate-fade-in items-center gap-2 text-sm text-info" role="status">
                <Loader2 size={14} className="animate-spin" aria-hidden /> {run.current_step}
              </p>
            )}
          </div>
        </div>
        {files.length > 0 && (
          <button type="button" className="btn btn-secondary" disabled={busy !== null}
                  onClick={() => download('zip', () => projectsApi.download(project.id), zipName)}>
            <Download size={14} aria-hidden /> {busy === 'zip' ? 'Preparing…' : 'Download ZIP'}
          </button>
        )}
      </div>

      <div className="space-y-6 p-5 sm:p-6">
        <DownloadError message={downloadError} />

        {run && (
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Fact label="Steps run" value={run.steps.length} />
            <Fact label="Build attempts" value={attempts} />
            <Fact label="AI repairs" value={run.repairs.length} />
            <Fact label="Files" value={project.file_count} />
          </dl>
        )}

        {run && run.warnings.length > 0 && (
          <ul className="animate-fade-in-up space-y-1.5 rounded-card border border-warning-line bg-warning-soft px-4 py-3 text-xs text-warning">
            {run.warnings.map((w) => (
              <li key={w} className="flex gap-2"><AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden /> {w}</li>
            ))}
          </ul>
        )}

        {run && <RunDetails run={run} />}

        {textFiles.length > 0 && (
          <div>
            <p className="eyebrow mb-3">Files</p>
            <ArtifactOutput
              artifact={{ artifact_type: 'project', name: project.name, files: textFiles, conflicts: [] }}
            />
          </div>
        )}
      </div>
    </section>
  );
};

const Fact: React.FC<{ label: string; value: number }> = ({ label, value }) => (
  <div className="rounded-[10px] bg-lavender-soft px-3 py-2.5">
    <dt className="text-xs text-ink-muted">{label}</dt>
    <dd className="mt-0.5 text-base font-medium text-ink tabular">{value}</dd>
  </div>
);

const RunDetails: React.FC<{ run: ProjectRun }> = ({ run }) => {
  const attempts = [...new Set(run.steps.map((s) => s.attempt))].sort((a, b) => a - b);
  return (
    <div className="space-y-5">
      {attempts.map((attempt) => {
        const repair = run.repairs.find((r) => r.attempt === attempt);
        const steps = run.steps.filter((s) => s.attempt === attempt);
        const passed = steps.every((s) => s.status === 'passed');
        return (
          <div key={attempt} className="animate-fade-in-up space-y-3">
            {repair && <RepairCard repair={repair} />}
            <div className="flex items-center justify-between gap-2">
              <h3 className="eyebrow flex items-center gap-1.5">
                <Terminal size={12} aria-hidden />
                {attempt === 0 ? 'Build' : `Rebuild after repair ${attempt}`}
              </h3>
              <span className={`text-xs ${passed ? 'text-success' : 'text-danger'}`}>
                {steps.filter((s) => s.status === 'passed').length}/{steps.length} passed
              </span>
            </div>
            <ol className="overflow-hidden rounded-card border border-hairline">
              {steps.map((step, i) => <StepRow key={i} step={step} />)}
            </ol>
          </div>
        );
      })}
      {/* A repair whose rebuild has not started (or that proposed no change) */}
      {run.repairs.filter((r) => !attempts.includes(r.attempt)).map((r) => <RepairCard key={r.attempt} repair={r} />)}
      {run.error_summary && run.status !== 'succeeded' && (
        <div className="animate-fade-in-up overflow-hidden rounded-card border border-danger-line" role="alert">
          <p className="flex items-center gap-2 bg-danger-soft px-4 py-2.5 text-sm font-medium text-danger">
            <XCircle size={15} aria-hidden /> Remaining error
          </p>
          <pre className="terminal max-h-64 overflow-auto whitespace-pre-wrap break-words !rounded-none px-4 py-3">
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
    <li className="animate-fade-in border-b border-hairline bg-surface last:border-b-0">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
              className="flex w-full items-center gap-3 px-3.5 py-3 text-left text-sm transition-colors duration-200 ease-soft hover:bg-lavender-soft focus-visible:bg-lavender-soft sm:px-4">
        {passed
          ? <CheckCircle2 size={16} className="shrink-0 text-success" aria-label="Passed" />
          : <XCircle size={16} className="shrink-0 text-danger" aria-label="Failed" />}
        <span className="min-w-0 flex-1">
          <span className="font-book text-ink">{step.label}</span>
          <span className="ml-2 text-xs text-ink-muted">{step.component}</span>
          <span className="mt-0.5 block truncate font-mono text-xs text-ink-muted">$ {step.command}</span>
        </span>
        <span className={`hidden shrink-0 text-xs tabular sm:inline ${passed ? 'text-ink-muted' : 'text-danger'}`}>
          {step.timed_out ? 'timed out' : `exit ${step.exit_code ?? '–'}`} · {formatDuration(step.duration_ms)}
        </span>
        <ChevronRight size={15} aria-hidden
          className={`shrink-0 text-ink-muted transition-transform duration-300 ease-mercury ${open ? 'rotate-90' : ''}`} />
      </button>
      <Collapse open={open}>
        <div className="px-3.5 pb-3.5 sm:px-4">
          <p className="mb-1.5 text-xs text-ink-muted tabular sm:hidden">
            {step.timed_out ? 'timed out' : `exit ${step.exit_code ?? '–'}`} · {formatDuration(step.duration_ms)}
          </p>
          <pre className="terminal max-h-72 overflow-auto whitespace-pre-wrap break-words px-4 py-3">
            {step.output || '(no output)'}
          </pre>
        </div>
      </Collapse>
    </li>
  );
};

const RepairCard: React.FC<{ repair: ProjectRun['repairs'][number] }> = ({ repair }) => (
  <div className="animate-fade-in-up rounded-card border border-warning-line bg-warning-soft/60 p-4">
    <p className="mb-1.5 flex items-start gap-2 text-sm font-medium text-ink">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-warning-soft text-warning ring-1 ring-warning-line" aria-hidden>
        <Wrench size={12} />
      </span>
      <span className="pt-0.5">Automatic repair {repair.attempt} · after “{repair.failed_step}” failed</span>
    </p>
    <p className="pl-8 text-sm leading-relaxed text-ink-secondary">{repair.diagnosis}</p>
    <div className="mt-2.5 pl-8">
      {repair.files.length > 0 ? (
        <p className="flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
          <FileDiff size={13} aria-hidden /> Changed:
          {repair.files.map((f) => (
            <code key={f.path} className="rounded-md bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink">{f.path} ({f.action})</code>
          ))}
        </p>
      ) : (
        <p className="text-xs text-ink-muted">No file was changed.</p>
      )}
      {repair.error && <p className="mt-1.5 text-xs text-danger">{repair.error}</p>}
    </div>
  </div>
);
