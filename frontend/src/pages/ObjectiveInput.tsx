/**
 * Home page: describe an objective, let the AI planner propose a workflow, then review it.
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { Sparkles, Loader2, FileText, Boxes, ArrowRight, Check } from 'lucide-react';
import { RISE, transition } from '../lib/motion';
import { plannerApi, type ObjectiveAnalysisResponse, type PlannerMode } from '../api/plannerApi';
import PlanReview from '../components/PlanReview';
import { PlannerSteps } from '../components/planner/PlannerSteps';
import { Notice } from '../components/ui/States';
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

  const describe = (
    <div className="mx-auto max-w-3xl">
      <PlannerSteps current={0} />

      <div className="mb-8">
        <p className="eyebrow mb-3 flex items-center gap-1.5"><Sparkles size={13} className="text-primary" aria-hidden /> AI planner</p>
        <h1 className="text-[30px] font-medium leading-tight tracking-[0.01em] text-ink sm:text-display">
          What do you want to accomplish?
        </h1>
        <p className="mt-3 max-w-2xl text-[17px] font-light leading-relaxed text-ink-secondary">
          Describe your goal. The AI planner proposes a workflow of stages for you to review before anything runs.
        </p>
      </div>

      <div className="card p-5 shadow-soft sm:p-7">
        <fieldset className="mb-6">
          <legend className="label mb-3">What should the AI produce?</legend>
          <div className="grid gap-3 sm:grid-cols-2" role="radiogroup">
            {MODES.map(({ value, label, icon: Icon, hint }) => {
              const active = mode === value;
              return (
                <label
                  key={value}
                  className={`relative flex cursor-pointer gap-3 rounded-card border p-4 transition-colors focus-within:ring-2 focus-within:ring-primary/40 ${
                    active ? 'border-primary/50 bg-primary/[0.05]' : 'border-hairline bg-surface hover:border-hairline-strong hover:bg-lavender-soft'
                  } ${analyzing ? 'cursor-not-allowed opacity-60' : ''}`}
                >
                  <input type="radio" name="mode" value={value} checked={active}
                    onChange={() => setMode(value)} disabled={analyzing} className="sr-only" />
                  <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] transition-colors duration-300 ease-soft ${active ? 'bg-primary text-white' : 'bg-lavender text-primary'}`}>
                    <Icon size={17} strokeWidth={1.75} aria-hidden />
                  </span>
                  <span className="min-w-0 pr-5">
                    <span className="block text-sm font-medium text-ink">{label}</span>
                    <span className="mt-1 block text-xs leading-relaxed text-ink-secondary">{hint}</span>
                  </span>
                  {active && (
                    <span className="absolute right-3 top-3 flex h-5 w-5 animate-pop-in items-center justify-center rounded-full bg-primary text-white" aria-hidden>
                      <Check size={12} />
                    </span>
                  )}
                </label>
              );
            })}
          </div>
        </fieldset>

        <label htmlFor="objective" className="label">
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
          className="input resize-y px-4 py-3.5 text-[15px] leading-relaxed"
          disabled={analyzing}
          aria-describedby="objective-meta"
        />
        <div id="objective-meta" className="mt-2 flex justify-between text-xs text-ink-muted tabular">
          <span>{objective.length.toLocaleString()} / {MAX_OBJECTIVE_LENGTH.toLocaleString()}</span>
          <span className="hidden items-center gap-1 sm:flex"><kbd className="kbd">Ctrl</kbd>+<kbd className="kbd">Enter</kbd> to plan</span>
        </div>

        {error && <Notice tone="danger" className="mt-5">{error}</Notice>}

        <button onClick={handleAnalyze} disabled={analyzing || !objective.trim()} className="btn btn-primary mt-6 h-12 w-full text-[15px]">
          {analyzing ? (
            <>
              <Loader2 size={18} className="animate-spin" aria-hidden />
              Planning workflow…
            </>
          ) : (
            <>
              <Sparkles size={17} aria-hidden />
              Plan workflow
            </>
          )}
        </button>
        {analyzing && (
          <p className="mt-3 animate-fade-in text-center text-xs text-ink-muted" role="status">
            The planner is breaking your objective into stages. This usually takes a few seconds.
          </p>
        )}
      </div>

      <div className="mt-10">
        <h2 className="eyebrow mb-3">Try an example</h2>
        <div className="grid gap-2.5 sm:grid-cols-2">
          {EXAMPLE_OBJECTIVES.map((example) => (
            <button
              key={example}
              onClick={() => setObjective(example)}
              disabled={analyzing}
              className="group flex items-start justify-between gap-3 rounded-card bg-lavender-soft px-4 py-3.5 text-left text-sm leading-relaxed text-ink-secondary transition-colors hover:bg-lavender hover:text-ink focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-50"
            >
              {example}
              <ArrowRight size={15} className="mt-0.5 shrink-0 text-ink-faint transition-colors group-hover:text-primary" aria-hidden />
            </button>
          ))}
        </div>
      </div>

      <p className="mt-10 text-center text-sm text-ink-secondary">
        Prefer to define the stages yourself?{' '}
        <Link to="/workflows/new" className="link">
          Create a workflow manually
        </Link>
      </p>
    </div>
  );

  // Describe and Review cross-fade: the current screen settles out, the next settles in
  const screen = {
    initial: { opacity: 0, y: RISE },
    animate: { opacity: 1, y: 0, transition: transition.enter },
    exit: { opacity: 0, y: -6, transition: transition.exit },
  };
  return (
    <AnimatePresence mode="wait" initial={false}>
      {plan ? (
        <motion.div key="review" {...screen}>
          <PlanReview
            objective={objective}
            plan={plan}
            mode={mode}
            onApproved={(workflowId) => navigate(`/workflows/${workflowId}`)}
            onBack={() => setPlan(null)}
          />
        </motion.div>
      ) : (
        <motion.div key="describe" {...screen}>
          {describe}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
