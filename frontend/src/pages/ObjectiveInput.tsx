import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Loader2, FileText } from 'lucide-react';
import { plannerApi, type ObjectiveAnalysisResponse } from '../api/plannerApi';
import PlanReview from '../components/PlanReview';

const EXAMPLE_OBJECTIVES = [
  "Design a machine learning pipeline for retail demand forecasting.",
  "Build a REST API for a task management application with authentication.",
  "Create a comprehensive documentation system for an open-source project.",
  "Develop a data processing workflow for customer analytics.",
];

export default function ObjectiveInput() {
  const navigate = useNavigate();
  const [objective, setObjective] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<ObjectiveAnalysisResponse | null>(null);

  const handleAnalyze = async () => {
    if (!objective.trim()) {
      setError('Please enter an objective');
      return;
    }

    setAnalyzing(true);
    setError(null);

    try {
      const result = await plannerApi.analyzeObjective(objective.trim());
      setPlan(result);
    } catch (err: any) {
      console.error('Analysis failed:', err);
      const detail = err.response?.data?.detail;
      // FastAPI validation errors (422) arrive as a list of objects, not a string
      setError(
        Array.isArray(detail)
          ? detail.map((d: any) => d.msg).join('; ')
          : (typeof detail === 'string' && detail) ||
            'Failed to analyze objective. Please check your provider configuration and try again.'
      );
    } finally {
      setAnalyzing(false);
    }
  };

  const handlePlanApproved = (workflowId: string) => {
    // Navigate to the newly created workflow
    navigate(`/workflows/${workflowId}`);
  };

  const handleEditManually = () => {
    navigate('/workflows/new');
  };

  if (plan) {
    return (
      <PlanReview
        objective={objective}
        plan={plan}
        onApproved={handlePlanApproved}
        onBack={() => setPlan(null)}
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="flex justify-center mb-4">
          <div className="p-3 bg-primary-600/10 rounded-2xl">
            <Sparkles size={32} className="text-primary-400" />
          </div>
        </div>
        <h1 className="text-4xl font-bold mb-3">What do you want to accomplish?</h1>
        <p className="text-lg text-surface-200/60">
          Describe your goal and let AI plan the workflow for you
        </p>
      </div>

      {/* Main Input */}
      <div className="glass rounded-xl p-8 mb-8">
        <label className="block text-sm font-medium text-surface-200/70 mb-3">
          Your Objective
        </label>
        <textarea
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              handleAnalyze();
            }
          }}
          placeholder="Example: Design a machine learning pipeline for retail demand forecasting with data preprocessing, feature engineering, model selection, and evaluation stages."
          rows={6}
          className="w-full px-4 py-3 bg-surface-800/50 border border-surface-700/50 rounded-lg text-white placeholder:text-surface-200/30 focus:outline-none focus:border-primary-500/50 transition-colors resize-none"
          disabled={analyzing}
        />
        
        <div className="flex items-center justify-between mt-4">
          <span className="text-xs text-surface-200/40">
            {objective.length} / 5000 characters
          </span>
          <span className="text-xs text-surface-200/40">
            Tip: Press Ctrl+Enter to analyze
          </span>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        <button
          onClick={handleAnalyze}
          disabled={analyzing || !objective.trim()}
          className="w-full mt-6 flex items-center justify-center gap-2 px-6 py-3.5 bg-primary-600 hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-base font-medium transition-all shadow-lg shadow-primary-600/25"
        >
          {analyzing ? (
            <>
              <Loader2 size={20} className="animate-spin" />
              Analyzing Objective...
            </>
          ) : (
            <>
              <Sparkles size={20} />
              Analyze Task
            </>
          )}
        </button>
      </div>

      {/* Examples */}
      <div className="glass rounded-xl p-6">
        <h3 className="text-sm font-medium text-surface-200/70 mb-4">Example Objectives</h3>
        <div className="grid gap-3">
          {EXAMPLE_OBJECTIVES.map((example, idx) => (
            <button
              key={idx}
              onClick={() => setObjective(example)}
              disabled={analyzing}
              className="text-left px-4 py-3 bg-surface-800/30 hover:bg-surface-800/50 border border-surface-700/30 hover:border-primary-500/30 rounded-lg transition-all group disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <p className="text-sm text-surface-200/80 group-hover:text-white transition-colors">
                {example}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Advanced Option */}
      <div className="text-center mt-8">
        <button
          onClick={handleEditManually}
          disabled={analyzing}
          className="inline-flex items-center gap-2 text-sm text-surface-200/50 hover:text-primary-400 transition-colors disabled:opacity-50"
        >
          <FileText size={16} />
          Or create workflow manually (Advanced)
        </button>
      </div>
    </div>
  );
}

