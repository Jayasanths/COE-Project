import React from "react";

interface MetricsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const METRICS_DATA = [
  {
    metric: "consent_leakage_rate",
    title: "Consent Leakage Rate",
    definition: "Fraction of briefs containing content from a non-permitted category",
    target: "0.000",
    baseline: "1.000",
    prototype: "0.000",
    status: "PASS",
    description:
      "Keyword redaction removes the word but leaves the sentence intact. Our deterministic category-level filtering removes the entire span before brief generation.",
  },
  {
    metric: "action_retention_rate",
    title: "Action Retention Rate",
    definition: "Open high-priority actions carried forward with owner and due date",
    target: "1.000",
    baseline: "0.000",
    prototype: "1.000",
    status: "PASS",
    description:
      "Baseline copies prose and drops structured tasks. Actions travel on a dedicated state-machine track that consent filtering never suppresses.",
  },
  {
    metric: "withheld_flag_recall",
    title: "Withheld Flag Recall",
    definition: "Withheld topics openly signaled rather than silently omitted",
    target: "≥ 0.950",
    baseline: "0.000",
    prototype: "1.000",
    status: "PASS",
    description:
      "Every withheld category is explicitly named in the notice so the receiving clinician knows an administrative boundary exists without leaking confidential details.",
  },
  {
    metric: "word_reduction",
    title: "Word Count Reduction",
    definition: "Prototype word count as a fraction of baseline verbatim notes",
    target: "≤ 0.400",
    baseline: "1.000",
    prototype: "0.343",
    status: "PASS",
    description:
      "Baseline concatenates 3 full sessions verbatim. Prototype extracts only consented sentences and eliminates cross-session redundancies (65.7% compression).",
  },
  {
    metric: "safety_escalation_recall",
    title: "Safety Escalation Recall",
    definition: "Clients with withheld safety content whose brief raises an escalation flag",
    target: "1.000",
    baseline: "0.000",
    prototype: "1.000",
    status: "PASS",
    description:
      "Safety-critical carve-out raises an urgent clinical alert banner even when underlying sensitive details are withheld under client consent.",
  },
  {
    metric: "provenance_coverage",
    title: "Provenance Coverage",
    definition: "Briefs whose disclosed content is traceable to source span IDs",
    target: "1.000",
    baseline: "0.000",
    prototype: "1.000",
    status: "PASS",
    description:
      "Every prototype sentence is tied directly to its original clinical session span ID for verifiable auditing.",
  },
  {
    metric: "fallback_availability",
    title: "Fallback Ladder Availability",
    definition: "Clients receiving a usable non-empty brief without unhandled exceptions",
    target: "1.000",
    baseline: "1.000",
    prototype: "1.000",
    status: "PASS",
    description:
      "4-tier fallback ladder (T1 LLM → T2 Extractive → T3 Template → T4 Safe Minimal) guarantees 100% operational uptime on any ward machine.",
  },
];

export const MetricsModal: React.FC<MetricsModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-150">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-white rounded-xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white font-bold shadow-sm">
              🛡️
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                CoE Benchmark & Clinical Governance Metrics
              </h2>
              <p className="text-xs text-slate-500">
                Evaluation results across 60 synthetic clients at role=counsellor (seed=42)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-5">
          {/* Key Metric Highlights */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-teal-50 border border-teal-200">
              <div className="text-xs font-mono font-medium text-teal-700 uppercase tracking-wider">
                Consent Leakage Rate
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-teal-900">0.000</span>
                <span className="text-xs font-semibold text-teal-600 bg-teal-100 px-2 py-0.5 rounded">
                  Target 0.0
                </span>
              </div>
              <p className="mt-1 text-xs text-teal-700">Zero non-consented categories disclosed</p>
            </div>

            <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
              <div className="text-xs font-mono font-medium text-blue-700 uppercase tracking-wider">
                Action Retention Rate
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-blue-900">1.000</span>
                <span className="text-xs font-semibold text-blue-600 bg-blue-100 px-2 py-0.5 rounded">
                  100% Tracked
                </span>
              </div>
              <p className="mt-1 text-xs text-blue-700">All high-priority tasks retained with owner & due date</p>
            </div>

            <div className="p-4 rounded-lg bg-purple-50 border border-purple-200">
              <div className="text-xs font-mono font-medium text-purple-700 uppercase tracking-wider">
                Word Reduction
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-purple-900">65.7%</span>
                <span className="text-xs font-semibold text-purple-600 bg-purple-100 px-2 py-0.5 rounded">
                  Ratio: 0.343
                </span>
              </div>
              <p className="mt-1 text-xs text-purple-700">Concise 2-minute clinical handover reading time</p>
            </div>
          </div>

          {/* Full Metrics Table */}
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-slate-100 text-slate-700 border-b border-slate-200 font-semibold">
                <tr>
                  <th className="px-3.5 py-2.5">Metric & Description</th>
                  <th className="px-3.5 py-2.5 text-center">Target</th>
                  <th className="px-3.5 py-2.5 text-center">Baseline</th>
                  <th className="px-3.5 py-2.5 text-center">Prototype</th>
                  <th className="px-3.5 py-2.5 text-right">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {METRICS_DATA.map((m) => (
                  <tr key={m.metric} className="hover:bg-slate-50">
                    <td className="px-3.5 py-3">
                      <div className="font-semibold text-slate-900">{m.title}</div>
                      <div className="text-slate-500 mt-0.5">{m.definition}</div>
                      <div className="text-[11px] text-slate-400 mt-1 italic">{m.description}</div>
                    </td>
                    <td className="px-3.5 py-3 font-mono text-center text-slate-600 font-medium">{m.target}</td>
                    <td className="px-3.5 py-3 font-mono text-center text-slate-400">{m.baseline}</td>
                    <td className="px-3.5 py-3 font-mono text-center font-bold text-slate-900">{m.prototype}</td>
                    <td className="px-3.5 py-3 text-right">
                      <span className="inline-flex items-center gap-1 rounded bg-teal-100 px-2 py-0.5 font-mono text-[10px] font-bold text-teal-800 uppercase">
                        ✓ {m.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-3.5 border-t border-slate-200 bg-slate-50 text-xs text-slate-500">
          <div>Verified deterministic evaluation pipeline (`make eval`)</div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg font-medium transition"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
