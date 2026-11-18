import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, Upload, Sparkles, CheckCircle2, AlertCircle, 
  ArrowRight, History, FileText, Check, Layers 
} from 'lucide-react';
import { PolicyData } from '../types';

interface PolicyManagerViewProps {
  onPolicyUpdated: () => void;
}

export const PolicyManagerView: React.FC<PolicyManagerViewProps> = ({ onPolicyUpdated }) => {
  const [activePolicy, setActivePolicy] = useState<PolicyData | null>(null);
  const [policyHistory, setPolicyHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  // Amendment Input
  const [amendmentText, setAmendmentText] = useState('');
  const [amendmentFile, setAmendmentFile] = useState<File | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewDiff, setPreviewDiff] = useState<any | null>(null);
  const [activating, setActivating] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchPolicy = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/policy/active');
      const data = await res.json();
      setActivePolicy(data);

      const histRes = await fetch('/api/policy/history');
      const histData = await histRes.json();
      setPolicyHistory(histData);
    } catch (err: any) {
      console.error('Failed to load policy', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicy();
  }, []);

  const handlePreview = async () => {
    if (!amendmentText.trim() && !amendmentFile) {
      alert('Please provide amendment text or select an amendment document.');
      return;
    }

    setPreviewing(true);
    setStatusMessage(null);

    const formData = new FormData();
    if (amendmentFile) {
      formData.append('file', amendmentFile);
    } else {
      formData.append('text_description', amendmentText);
    }

    try {
      const res = await fetch('/api/policy/amend-preview', {
        method: 'POST',
        body: formData
      });
      if (!res.ok) throw new Error('Failed to generate amendment preview');
      const data = await res.json();
      setPreviewDiff(data);
    } catch (err: any) {
      alert(`Error generating diff: ${err.message}`);
    } finally {
      setPreviewing(false);
    }
  };

  const handleActivate = async () => {
    if (!previewDiff) return;

    setActivating(true);
    try {
      const res = await fetch('/api/policy/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposed_policy: previewDiff.proposed_policy,
          user_id: 'Head of Procurement'
        })
      });
      if (!res.ok) throw new Error('Failed to activate policy');
      const data = await res.json();
      setStatusMessage(`🎉 Policy ${data.policy.version} has been activated with effective date ${data.policy.effective_date}! Re-running batch now applies the amended rules.`);
      setPreviewDiff(null);
      setAmendmentText('');
      setAmendmentFile(null);
      fetchPolicy();
      onPolicyUpdated();
    } catch (err: any) {
      alert(`Error activating policy: ${err.message}`);
    } finally {
      setActivating(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 space-y-8">
      {/* Policy-as-Data Hero Card */}
      <div className="bg-gradient-to-r from-slate-900 via-brand-950 to-slate-900 rounded-3xl shadow-xl text-white p-8 border border-slate-800">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                ACTIVE POLICY IN DATABASE
              </span>
              <span className="text-xs text-slate-400 font-mono">Doc: {activePolicy?.document_ref}</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Corvo Procurement Policy <span className="text-brand-400">{activePolicy?.version}</span>
            </h1>
            <p className="text-sm text-slate-300 mt-1 max-w-2xl">
              All limits, rule sequences, anti-splitting windows, and category conditions are dynamically evaluated from database schema without any hardcoded code logic.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
            <div className="bg-white/5 border border-white/10 rounded-xl p-3">
              <span className="text-slate-400 block">Spot PO Limit</span>
              <span className="text-base font-bold text-white">₹{activePolicy?.parameters?.spot_po_limit?.toLocaleString() || '200,000'}</span>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-3">
              <span className="text-slate-400 block">Emergency Limit</span>
              <span className="text-base font-bold text-white">₹{activePolicy?.parameters?.emergency_po_limit?.toLocaleString() || '500,000'}</span>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-3">
              <span className="text-slate-400 block">RFQ/RFP Limit</span>
              <span className="text-base font-bold text-white">₹{activePolicy?.parameters?.rfq_limit?.toLocaleString() || '1,000,000'}</span>
            </div>
          </div>
        </div>
      </div>

      {statusMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-sm flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Side-by-Side: Amendment Intake vs Rule Sequence */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left: Amendment Ingestion */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-5">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-brand-600" />
              Upload Policy Amendment (Run 2 Ready)
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Upload a signed policy amendment document (PDF/text) or type a change in natural language. The engine parses diffs and updates thresholds dynamically.
            </p>
          </div>

          {/* File Upload Dropzone */}
          <div>
            <label className="border-2 border-dashed border-slate-200 hover:border-brand-400 rounded-xl p-4 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-slate-50/50 hover:bg-slate-50">
              <FileText className="w-6 h-6 text-slate-400 mb-1" />
              <span className="text-xs font-semibold text-brand-600">
                {amendmentFile ? amendmentFile.name : 'Upload Amendment Document (PDF/Text)'}
              </span>
              <span className="text-[10px] text-slate-400 mt-0.5">e.g. Corvo_Procurement_Policy_Amendment_v5.1.pdf</span>
              <input
                type="file"
                accept=".pdf,.txt,.md"
                onChange={(e) => {
                  if (e.target.files?.[0]) setAmendmentFile(e.target.files[0]);
                }}
                className="hidden"
              />
            </label>
          </div>

          <div className="relative flex py-1 items-center">
            <div className="flex-grow border-t border-slate-200"></div>
            <span className="flex-shrink mx-4 text-slate-400 text-xs uppercase font-medium">Or type amendment description</span>
            <div className="flex-grow border-t border-slate-200"></div>
          </div>

          {/* Textarea */}
          <div>
            <textarea
              rows={4}
              value={amendmentText}
              onChange={(e) => setAmendmentText(e.target.value)}
              placeholder="e.g. Effective 2026-11-20: Spot PO limit increased to ₹3,00,000; For CHK1 plant, items under ₹50,000 go to direct spot PO..."
              className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/30"
            />
          </div>

          {/* Quick preset buttons */}
          <div className="flex flex-wrap gap-2 text-xs">
            <button
              type="button"
              onClick={() => setAmendmentText("Version 5.1, Effective 2026-11-20: Spot PO limit increased to ₹3,00,000; Emergency limit raised to ₹7,50,000.")}
              className="px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium"
            >
              Preset: Spot PO to 3L
            </button>
            <button
              type="button"
              onClick={() => setAmendmentText("Version 5.1, Effective 2026-11-20: For CHK1 plant, items under ₹50,000 go to direct spot PO.")}
              className="px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium"
            >
              Preset: CHK1 Specific Rule
            </button>
          </div>

          <button
            onClick={handlePreview}
            disabled={previewing || (!amendmentText.trim() && !amendmentFile)}
            className="w-full py-2.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-xs transition-all flex items-center justify-center gap-2"
          >
            {previewing ? 'Parsing Amendment...' : 'Preview Plain-Language Diffs'}
          </button>

          {/* Diff Preview Card */}
          {previewDiff && (
            <div className="mt-4 p-5 bg-brand-50/50 border border-brand-200 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-brand-900 flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-brand-600" />
                  Proposed Diff: {previewDiff.old_version} ➔ {previewDiff.new_version}
                </span>
                <span className="text-[11px] font-semibold text-brand-700 bg-brand-100 px-2 py-0.5 rounded">
                  Effective: {previewDiff.effective_date}
                </span>
              </div>

              <div className="space-y-1.5 text-xs text-slate-700">
                {previewDiff.diffs.map((d: string, dIdx: number) => (
                  <div key={dIdx} className="flex items-start gap-2">
                    <span className="text-brand-600 font-bold">•</span>
                    <span>{d}</span>
                  </div>
                ))}
              </div>

              <button
                onClick={handleActivate}
                disabled={activating}
                className="w-full mt-3 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl shadow-xs transition-all flex items-center justify-center gap-1.5"
              >
                <Check className="w-4 h-4" />
                {activating ? 'Activating Policy...' : 'Approve & Activate New Policy Version'}
              </button>
            </div>
          )}
        </div>

        {/* Right: Active Rule Sequence Display */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Layers className="w-5 h-5 text-brand-600" />
              Active Policy Rules Execution Sequence
            </h2>
            <span className="text-xs font-semibold text-slate-500">
              Evaluated strictly top-to-bottom
            </span>
          </div>

          <div className="space-y-3">
            {activePolicy?.rules?.map((rule, rIdx) => (
              <div key={rule.id || rIdx} className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900">
                    Rule {rule.id}: {rule.name}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-white border border-slate-200 text-brand-700">
                    {rule.route}
                  </span>
                </div>
                <p className="text-slate-600 font-mono text-[11px]">
                  Condition: {JSON.stringify(rule.condition)}
                </p>
                <p className="text-slate-400 italic text-[11px]">
                  {rule.reason_template}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

