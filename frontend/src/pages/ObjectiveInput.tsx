/**
 * Home page: describe an objective, let the AI planner propose a workflow, then review it.
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sparkles, Loader2, FileText, Boxes } from 'lucide-react';
import { plannerApi, type ObjectiveAnalysisResponse, type PlannerMode } from '../api/plannerApi';
import PlanReview from '../components/PlanReview';
import { getErrorMessage } from '../lib/errors';

const MAX_OBJECTIVE_LENGTH = 5000; // matches the planner API limit

const MODES: { value: PlannerMode; label: string; icon: typeof FileText; hint: string }[] = [
  {
    value: 'artifact', label: 'Individual artifact', icon: FileText,
    hint: 'Documents, explanations or code files you can review and download.',
  },
  {
    value: 'project', label: 'Complete project', icon: Boxes,
    hint: 'A multi-file project that is installed, built and tested in an isolated sandbox, with automatic fixes.',
  },
];

const EXAMPLE_OBJECTIVES = [
  'Build a student management system using React, FastAPI and PostgreSQL.',
  'Design a machine learning pipeline for retail demand forecasting.',
  'Build a REST API for a task management application with authentication.',
  'Create a documentation system for an open-source project.',
];

export default function ObjectiveInput() {
  const navigate = useNavigate();
  const [objective, setObjective] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<ObjectiveAnalysisResponse | null>(null);
  const [mode, setMode] = useState<PlannerMode>('artifact');

  const handleAnalyze = async () => {
    if (!objective.trim()) {
      setError('Please enter an objective');
      return;
    }
    setAnalyzing(true);
    setError(null);
    try {
      setPlan(await plannerApi.analyzeObjective(objective.trim(), mode));
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to analyze the objective. Check the LLM provider configuration and try again.'));
    } finally {
      setAnalyzing(false);
    }
  };

  if (plan) {
    return (
      <PlanReview
        objective={objective}
        plan={plan}
        mode={mode}
        onApproved={(workflowId) => navigate(`/workflows/${workflowId}`)}
        onBack={() => setPlan(null)}
      />
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">What do you want to accomplish?</h1>
        <p className="mt-1 text-sm text-surface-200/50">
          Describe your goal. The AI planner proposes a workflow of stages for you to review before anything runs.
        </p>
      </div>

      <div className="glass rounded-xl p-5 sm:p-6">
        <fieldset className="mb-5">
          <legend className="mb-2 block text-sm font-medium text-surface-200/80">What should the AI produce?</legend>
          <div className="grid gap-2 sm:grid-cols-2" role="radiogroup">
            {MODES.map(({ value, label, icon: Icon, hint }) => (
              <label
                key={value}
                className={`flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors focus-within:ring-2 focus-within:ring-primary-400/60 ${
                  mode === value ? 'border-primary-500/60 bg-primary-500/10' : 'border-surface-700/60 hover:border-surface-700'
                }`}
              >
                <input type="radio" name="mode" value={value} checked={mode === value}
                  onChange={() => setMode(value)} disabled={analyzing} className="sr-only" />
                <Icon size={18} className={mode === value ? 'mt-0.5 text-primary-400' : 'mt-0.5 text-surface-200/50'} aria-hidden />
                <span>
                  <span className="block text-sm font-medium text-white">{label}</span>
                  <span className="mt-0.5 block text-xs text-surface-200/50">{hint}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <label htmlFor="objective" className="mb-2 block text-sm font-medium text-surface-200/80">
          Objective
        </label>
        <textarea
          id="objective"
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleAnalyze();
          }}
          placeholder="e.g. Design a machine learning pipeline for retail demand forecasting, covering data preparation, feature engineering, model selection and evaluation."
          rows={6}
          maxLength={MAX_OBJECTIVE_LENGTH}
          className="input resize-none px-4 py-3 text-base"
          disabled={analyzing}
          aria-describedby="objective-meta"
        />
        <div id="objective-meta" className="mt-2 flex justify-between text-xs text-surface-200/40">
          <span>{objective.length.toLocaleString()} / {MAX_OBJECTIVE_LENGTH.toLocaleString()}</span>
          <span className="hidden sm:inline">Ctrl+Enter to plan</span>
        </div>

        {error && (
          <p role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
            {error}
          </p>
        )}

        <button onClick={handleAnalyze} disabled={analyzing || !objective.trim()} className="btn btn-primary mt-5 w-full py-3 text-base">
          {analyzing ? (
            <>
              <Loader2 size={18} className="animate-spin" aria-hidden />
              Planning workflow…
            </>
          ) : (
            <>
              <Sparkles size={18} aria-hidden />
              Plan workflow
            </>
          )}
        </button>
      </div>

      <div className="mt-6">
        <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-surface-200/40">Try an example</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {EXAMPLE_OBJECTIVES.map((example) => (
            <button
              key={example}
              onClick={() => setObjective(example)}
              disabled={analyzing}
              className="rounded-lg border border-surface-700/60 bg-surface-800/40 px-3.5 py-2.5 text-left text-sm text-surface-200/70 transition-colors hover:border-primary-500/40 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/60 disabled:opacity-50"
            >
              {example}
            </button>
          ))}
        </div>
      </div>

      <p className="mt-8 text-center text-sm text-surface-200/50">
        Prefer to define the stages yourself?{' '}
        <Link to="/workflows/new" className="font-medium text-primary-400 hover:text-primary-300">
          Create a workflow manually
        </Link>
      </p>
    </div>
  );
}
