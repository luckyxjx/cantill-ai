import React, { useState } from 'react';
import { CheckCircle, X, Search } from 'lucide-react';
import { BuyerRequirement } from '../types';

interface BuyerWorkspaceProps {
  requirements: BuyerRequirement[];
  onRefresh: () => void;
}

// Helper to format INR with Indian grouping
const formatINR = (value: number) => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value).replace('₹', '₹ ');
};

export const BuyerWorkspace: React.FC<BuyerWorkspaceProps> = ({ requirements, onRefresh }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedReq, setSelectedReq] = useState<BuyerRequirement | null>(null);
  const [overrideMode, setOverrideMode] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');

  // Calculate metrics
  const totalReqs = requirements.length;
  const totalLines = requirements.reduce((sum, r) => sum + r.pr_lines.length, 0);
  const directPOs = requirements.filter(r => r.decision === 'PO').length;
  const sourcing = requirements.filter(r => r.decision !== 'PO').length;
  const pending = requirements.filter(r => r.status === 'PENDING').length;

  // Filter logic
  const filtered = requirements.filter((r) => {
    const matchesSearch = 
      r.group_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.item_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.item_description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.plant.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.supplier_id && r.supplier_id.toLowerCase().includes(searchTerm.toLowerCase()));

    if (!matchesSearch) return false;

    if (activeFilter === 'directpos') return r.decision === 'PO';
    if (activeFilter === 'sourcing') return r.decision !== 'PO';
    if (activeFilter === 'pending') return r.status === 'PENDING';
    return true;
  });

  const handleRowClick = (req: BuyerRequirement) => {
    setSelectedReq(req);
    setOverrideMode(false);
    setOverrideReason('');
    setDrawerOpen(true);
  };

  const handleApprove = async (groupId: string) => {
    try {
      const res = await fetch(`/api/buyer/approve/${groupId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_by: 'Buyer Officer' })
      });
      if (!res.ok) throw new Error('Approval failed');
      setDrawerOpen(false);
      onRefresh();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleBulkApprove = async () => {
    if (!confirm(`Approve all ${pending} pending requirements?`)) return;
    
    try {
      const pendingReqs = requirements.filter(r => r.status === 'PENDING');
      await Promise.all(
        pendingReqs.map(r => 
          fetch(`/api/buyer/approve/${r.group_id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action_by: 'Buyer Officer' })
          })
        )
      );
      onRefresh();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleOverrideSubmit = async () => {
    if (!selectedReq || !overrideReason.trim()) {
      alert('Justification is required.');
      return;
    }

    try {
      const res = await fetch(`/api/buyer/override/${selectedReq.group_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          override_reason: overrideReason.trim(),
          action_by: 'Buyer Lead'
        })
      });
      if (!res.ok) throw new Error('Override failed');
      setDrawerOpen(false);
      setOverrideMode(false);
      onRefresh();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleExportCSV = () => {
    window.location.href = '/api/export-decisions';
  };

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 space-y-4">
      {/* Summary Bar */}
      <div className="flex items-center justify-between text-sm">
        <div className="text-slate-700">
          Current Batch: <span className="font-semibold text-slate-900">{totalReqs} requirements</span> clubbed from{' '}
          <span className="font-semibold text-slate-900">{totalLines} lines</span> |{' '}
          <span className="font-semibold text-slate-900">{directPOs} Direct POs</span> |{' '}
          <span className="font-semibold text-slate-900">{sourcing} Sourcing</span> |{' '}
          <span className="font-semibold text-slate-900">{pending} pending review</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleBulkApprove}
            disabled={pending === 0}
            className="px-4 py-2 bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Bulk Approve Pending
          </button>
          <button
            onClick={handleExportCSV}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Export Decisions CSV
          </button>
        </div>
      </div>

      {/* Search and Filter Pills */}
      <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4">
        <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
          <div className="relative w-full md:w-96">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by Req ID, item, plant, supplier..."
              className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-slate-900"
            />
          </div>

          <div className="flex items-center gap-2">
            {[
              { id: 'all', label: 'All', count: totalReqs },
              { id: 'directpos', label: 'Direct POs', count: directPOs },
              { id: 'sourcing', label: 'Sourcing', count: sourcing },
              { id: 'pending', label: 'Pending Review', count: pending },
            ].map((filter) => (
              <button
                key={filter.id}
                onClick={() => setActiveFilter(filter.id)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors whitespace-nowrap ${
                  activeFilter === filter.id
                    ? 'bg-slate-900 text-white border-slate-900'
                    : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                }`}
              >
                {filter.label} ({filter.count})
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Dense Table */}
      <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-slate-700 text-xs font-medium whitespace-nowrap">
                <th className="text-left py-3 px-4">Req ID</th>
                <th className="text-left py-3 px-4">Item & Specification</th>
                <th className="text-left py-3 px-4">Plant</th>
                <th className="text-right py-3 px-4 tabular-nums">Quantity</th>
                <th className="text-right py-3 px-4 tabular-nums">Value (INR)</th>
                <th className="text-left py-3 px-4">Route</th>
                <th className="text-left py-3 px-4">Allocated Supplier / Quotes</th>
                <th className="text-left py-3 px-4">Status</th>
                <th className="text-left py-3 px-4">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-12 text-slate-400">
                    No requirements found.
                  </td>
                </tr>
              ) : (
                filtered.map((req) => (
                  <tr
                    key={req.group_id}
                    onClick={() => handleRowClick(req)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4 font-mono text-xs font-semibold text-slate-900 bg-slate-100 border border-slate-200">
                      {req.group_id}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900">{req.item_description}</div>
                      <div className="text-xs text-slate-500 font-mono">{req.item_code}</div>
                    </td>
                    <td className="py-3 px-4 font-medium">{req.plant}</td>
                    <td className="py-3 px-4 text-right tabular-nums font-medium">
                      {req.total_quantity.toLocaleString()} {req.uom}
                    </td>
                    <td className="py-3 px-4 text-right tabular-nums font-semibold text-slate-900">
                      {formatINR(req.group_value_inr)}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-xs font-mono font-medium bg-slate-100 text-slate-700 border border-slate-200">
                        {req.route}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {req.decision === 'PO' ? (
                        <div className="text-xs">
                          <div className="font-semibold text-slate-900">{req.supplier_id}</div>
                          <div className="text-slate-500">{req.supplier_name || 'Contracted'}</div>
                        </div>
                      ) : (
                        <div className="text-xs text-slate-600">
                          {req.suggested_suppliers.length > 0
                            ? req.suggested_suppliers.map(s => s.supplier_id).join(', ')
                            : 'Buyer to source'}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {req.status === 'APPROVED' && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                          Approved
                        </span>
                      )}
                      {req.status === 'PENDING' && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
                          Pending Review
                        </span>
                      )}
                      {req.status === 'OVERRIDDEN' && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                          Overridden
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {req.status === 'PENDING' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleApprove(req.group_id);
                          }}
                          className="px-3 py-1 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded transition-colors"
                        >
                          Approve
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Slide-over Drawer */}
      {drawerOpen && selectedReq && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={() => setDrawerOpen(false)} />
          
          <div className="fixed inset-y-0 right-0 max-w-2xl w-full bg-white shadow-2xl flex flex-col">
            {/* Drawer Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">{selectedReq.group_id}</h2>
                <p className="text-sm text-slate-600">{selectedReq.item_description}</p>
              </div>
              <button
                onClick={() => setDrawerOpen(false)}
                className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Content */}
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
              {/* Anti-splitting Section */}
              <div>
                <h3 className="text-sm font-semibold text-slate-900 mb-3">Anti-Splitting: Clubbed PR Lines</h3>
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 whitespace-nowrap">
                        <th className="text-left py-2 px-3">PR / Line</th>
                        <th className="text-right py-2 px-3">Quantity</th>
                        <th className="text-left py-2 px-3">Created</th>
                        <th className="text-left py-2 px-3">Need By</th>
                        <th className="text-left py-2 px-3">Reason Clubbed</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {selectedReq.pr_lines.map((line, idx) => (
                        <tr key={idx} className="text-slate-700">
                          <td className="py-2 px-3 font-mono">{line.pr_no}/{line.pr_line}</td>
                          <td className="py-2 px-3 text-right tabular-nums">{line.quantity} {line.uom}</td>
                          <td className="py-2 px-3">{line.created_at}</td>
                          <td className="py-2 px-3">{line.need_by_date}</td>
                          <td className="py-2 px-3 text-slate-500">Same item, plant, window</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Valuation Section */}
              <div>
                <h3 className="text-sm font-semibold text-slate-900 mb-3">Valuation</h3>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-600">Total Value:</span>
                    <span className="font-semibold text-slate-900 tabular-nums">{formatINR(selectedReq.group_value_inr)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Unit Price Source:</span>
                    <span className="text-slate-700">{selectedReq.unit_price ? `${formatINR(selectedReq.unit_price)} (Contract/History)` : 'Estimated'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Total Quantity:</span>
                    <span className="text-slate-700 tabular-nums">{selectedReq.total_quantity.toLocaleString()} {selectedReq.uom}</span>
                  </div>
                </div>
              </div>

              {/* Routing Section */}
              <div>
                <h3 className="text-sm font-semibold text-slate-900 mb-3">Routing</h3>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-700 border border-slate-200">
                      {selectedReq.route}
                    </span>
                    <span className="text-slate-600">→</span>
                    <span className="text-slate-700 font-medium">{selectedReq.decision}</span>
                  </div>
                  <p className="text-slate-600 italic">{selectedReq.reason}</p>
                </div>
              </div>

              {/* Override Form */}
              {overrideMode && (
                <div className="border border-slate-300 rounded-lg p-4 bg-slate-50">
                  <h3 className="text-sm font-semibold text-slate-900 mb-3">Override Decision</h3>
                  <textarea
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    rows={3}
                    placeholder="Enter justification for override (required)..."
                    className="w-full p-3 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-slate-900"
                    required
                  />
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 bg-slate-50">
              {!overrideMode ? (
                <>
                  {selectedReq.status === 'PENDING' && (
                    <button
                      onClick={() => handleApprove(selectedReq.group_id)}
                      className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      Approve Decision
                    </button>
                  )}
                  {selectedReq.status === 'APPROVED' && (
                    <span className="text-sm text-slate-500">Decision already approved</span>
                  )}
                  <button
                    onClick={() => setOverrideMode(true)}
                    className="ml-auto px-4 py-2 bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 text-sm font-medium rounded-lg transition-colors"
                  >
                    Override...
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => setOverrideMode(false)}
                    className="px-4 py-2 bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 text-sm font-medium rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleOverrideSubmit}
                    disabled={!overrideReason.trim()}
                    className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    Confirm Override
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


