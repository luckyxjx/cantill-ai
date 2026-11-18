import React, { useState } from 'react';
import { 
  CheckCircle, AlertTriangle, ChevronDown, ChevronRight, 
  Search, Filter, ShieldCheck, ArrowRight, X, ExternalLink, FileCheck 
} from 'lucide-react';
import { BuyerRequirement } from '../types';

interface BuyerWorkspaceProps {
  requirements: BuyerRequirement[];
  onRefresh: () => void;
}

export const BuyerWorkspace: React.FC<BuyerWorkspaceProps> = ({ requirements, onRefresh }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterPlant, setFilterPlant] = useState('ALL');
  const [filterRoute, setFilterRoute] = useState('ALL');
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Override Modal state
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [selectedReq, setSelectedReq] = useState<BuyerRequirement | null>(null);
  const [overrideReason, setOverrideReason] = useState('');
  const [overrideRoute, setOverrideRoute] = useState('');
  const [overrideSupplier, setOverrideSupplier] = useState('');
  const [submittingOverride, setSubmittingOverride] = useState(false);

  const filtered = requirements.filter((r) => {
    const matchesSearch = 
      r.group_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.item_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.item_description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.po_id && r.po_id.toLowerCase().includes(searchTerm.toLowerCase())) ||
      r.pr_lines.some((p) => p.pr_no.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesPlant = filterPlant === 'ALL' || r.plant === filterPlant;
    const matchesRoute = filterRoute === 'ALL' || r.route === filterRoute;
    const matchesStatus = filterStatus === 'ALL' || r.status === filterStatus;

    return matchesSearch && matchesPlant && matchesRoute && matchesStatus;
  });

  const handleApprove = async (groupId: string) => {
    try {
      const res = await fetch(`/api/buyer/approve/${groupId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_by: 'Buyer Officer' })
      });
      if (!res.ok) throw new Error('Approval failed');
      onRefresh();
    } catch (err: any) {
      alert(`Error approving requirement: ${err.message}`);
    }
  };

  const handleOpenOverride = (req: BuyerRequirement) => {
    setSelectedReq(req);
    setOverrideReason('');
    setOverrideRoute(req.route);
    setOverrideSupplier(req.supplier_id || '');
    setOverrideModalOpen(true);
  };

  const handleSubmitOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReq) return;
    if (!overrideReason.trim()) {
      alert('Mandatory explanation comment is required to override.');
      return;
    }

    setSubmittingOverride(true);
    try {
      const res = await fetch(`/api/buyer/override/${selectedReq.group_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          override_reason: overrideReason.trim(),
          new_route: overrideRoute !== selectedReq.route ? overrideRoute : null,
          new_supplier_id: overrideSupplier !== selectedReq.supplier_id ? overrideSupplier : null,
          action_by: 'Buyer Lead'
        })
      });
      if (!res.ok) throw new Error('Override failed');
      setOverrideModalOpen(false);
      onRefresh();
    } catch (err: any) {
      alert(`Error saving override: ${err.message}`);
    } finally {
      setSubmittingOverride(false);
    }
  };

  const getRouteBadge = (route: string) => {
    switch (route) {
      case 'CONTRACT_PO':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'SPOT_PO':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'EMERGENCY_PO':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'RFQ':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'RFP':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'CAPEX_SOURCING':
        return 'bg-indigo-50 text-indigo-700 border-indigo-200';
      case 'NEW_ITEM_SOURCING':
        return 'bg-cyan-50 text-cyan-700 border-cyan-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 space-y-6">
      {/* Filters & Search Header */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
        <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
          {/* Search Box */}
          <div className="relative w-full md:w-80">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by ID, item, PO or PR..."
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
            />
          </div>

          {/* Dropdown Filters */}
          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Filter className="w-3.5 h-3.5" /> Filter:
            </div>

            <select
              value={filterPlant}
              onChange={(e) => setFilterPlant(e.target.value)}
              className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none"
            >
              <option value="ALL">All Plants</option>
              <option value="PUN1">PUN1 (Bhosari)</option>
              <option value="CHK1">CHK1 (Chakan)</option>
            </select>

            <select
              value={filterRoute}
              onChange={(e) => setFilterRoute(e.target.value)}
              className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none"
            >
              <option value="ALL">All Routes</option>
              <option value="CONTRACT_PO">Contract PO</option>
              <option value="SPOT_PO">Spot PO</option>
              <option value="EMERGENCY_PO">Emergency PO</option>
              <option value="RFQ">RFQ (Quotes)</option>
              <option value="RFP">RFP (Formal)</option>
              <option value="CAPEX_SOURCING">Capex Sourcing</option>
              <option value="NEW_ITEM_SOURCING">New Item Sourcing</option>
              <option value="NOT_PROCESSED">Not Processed</option>
            </select>

            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="PENDING">Pending Review</option>
              <option value="APPROVED">Approved</option>
              <option value="OVERRIDDEN">Overridden</option>
            </select>
          </div>
        </div>
      </div>

      {/* Requirements List */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Procurement Requisitions & Decisions</h2>
            <p className="text-xs text-slate-500">Showing {filtered.length} clubbed requirements from active PR batch</p>
          </div>
        </div>

        <div className="divide-y divide-slate-100">
          {filtered.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-sm">
              No requirements found matching current filters.
            </div>
          ) : (
            filtered.map((req) => {
              const isExpanded = expandedId === req.group_id;
              return (
                <div key={req.group_id} className="p-5 hover:bg-slate-50/60 transition-colors">
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    {/* Left: Identifiers, Item & Clubbed stats */}
                    <div className="flex items-start gap-3">
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : req.group_id)}
                        className="p-1 rounded hover:bg-slate-200 text-slate-400 hover:text-slate-700 transition-colors mt-0.5"
                      >
                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                      </button>

                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                            {req.group_id}
                          </span>
                          <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full border ${getRouteBadge(req.route)}`}>
                            {req.route}
                          </span>
                          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                            {req.plant}
                          </span>
                          {req.is_emergency && (
                            <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-red-100 text-red-700 border border-red-200">
                              EMERGENCY
                            </span>
                          )}
                        </div>

                        <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                          {req.item_description}
                          <span className="text-xs font-mono font-normal text-slate-500">({req.item_code})</span>
                        </h3>

                        <p className="text-xs text-slate-500 mt-0.5">
                          Total: <span className="font-medium text-slate-700">{req.total_quantity.toLocaleString()} {req.uom}</span> · Value: <span className="font-semibold text-slate-900">₹{req.group_value_inr.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span> · {req.pr_lines.length} PR Line{req.pr_lines.length > 1 ? 's' : ''}
                        </p>
                      </div>
                    </div>

                    {/* Middle: Supplier / PO or Sourcing suggestions */}
                    <div className="lg:max-w-xs text-xs space-y-1">
                      {req.decision === 'PO' ? (
                        <div>
                          <div className="flex items-center gap-1.5 font-semibold text-emerald-700">
                            <FileCheck className="w-4 h-4" />
                            <span>Direct PO: {req.po_id || 'PO-Pending'}</span>
                          </div>
                          <p className="text-slate-600 truncate">
                            Supplier: <span className="font-medium text-slate-800">{req.supplier_id}</span> ({req.supplier_name || 'Active'}) @ ₹{req.unit_price?.toLocaleString()}
                          </p>
                        </div>
                      ) : (
                        <div>
                          <div className="font-semibold text-amber-700">
                            Sourcing Request ({req.decision})
                          </div>
                          <p className="text-slate-600 truncate" title={req.suggested_suppliers.map(s => s.supplier_id).join(', ')}>
                            Suggested: {req.suggested_suppliers.length > 0 ? (
                              req.suggested_suppliers.map((s) => s.supplier_id).join(', ')
                            ) : (
                              <span className="italic text-slate-400">Buyer to identify suppliers</span>
                            )}
                          </p>
                        </div>
                      )}
                      <div className="text-[11px] text-slate-400 italic truncate" title={req.reason}>
                        {req.reason} ({req.policy_version})
                      </div>
                    </div>

                    {/* Right: Status & Actions */}
                    <div className="flex items-center gap-3 self-end lg:self-center">
                      {req.status === 'APPROVED' && (
                        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 flex items-center gap-1">
                          <CheckCircle className="w-3.5 h-3.5" /> Approved
                        </span>
                      )}
                      {req.status === 'OVERRIDDEN' && (
                        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-purple-100 text-purple-800 flex items-center gap-1" title={req.override_reason}>
                          <AlertTriangle className="w-3.5 h-3.5" /> Overridden
                        </span>
                      )}

                      {req.status === 'PENDING' && (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleApprove(req.group_id)}
                            className="px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors flex items-center gap-1"
                          >
                            <CheckCircle className="w-3.5 h-3.5" /> Approve
                          </button>
                          <button
                            onClick={() => handleOpenOverride(req)}
                            className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 transition-colors"
                          >
                            Override
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Expandable PR Lines Table */}
                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-slate-100 bg-slate-50/70 rounded-xl p-4">
                      <h4 className="text-xs font-semibold text-slate-700 mb-2">
                        Contributing Purchase Requisition Lines ({req.pr_lines.length})
                      </h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs text-slate-600">
                          <thead>
                            <tr className="border-b border-slate-200 text-slate-400 uppercase text-[10px]">
                              <th className="py-1 px-2">PR Line</th>
                              <th className="py-1 px-2">Created</th>
                              <th className="py-1 px-2">Requester / Dept</th>
                              <th className="py-1 px-2 text-right">Qty</th>
                              <th className="py-1 px-2">Need By</th>
                              <th className="py-1 px-2">Urgency</th>
                            </tr>
                          </thead>
                          <tbody>
                            {req.pr_lines.map((p, pIdx) => (
                              <tr key={pIdx} className="border-b border-slate-100/50">
                                <td className="py-1 px-2 font-mono font-medium text-slate-900">{p.pr_no}/{p.pr_line}</td>
                                <td className="py-1 px-2">{p.created_at}</td>
                                <td className="py-1 px-2">{p.requester} ({p.department})</td>
                                <td className="py-1 px-2 text-right font-medium text-slate-900">{p.quantity.toLocaleString()} {p.uom}</td>
                                <td className="py-1 px-2">{p.need_by_date}</td>
                                <td className="py-1 px-2">
                                  <span className={p.urgency === 'Emergency' ? 'text-red-600 font-bold' : ''}>
                                    {p.urgency}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Override Modal */}
      {overrideModalOpen && selectedReq && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-4 border-b border-slate-100 pb-3">
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-purple-600" />
                Override Procurement Decision ({selectedReq.group_id})
              </h3>
              <button
                onClick={() => setOverrideModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmitOverride} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-600 font-medium mb-1">
                  System Policy Route
                </label>
                <div className="p-2.5 bg-slate-50 rounded-lg text-slate-800 font-medium border border-slate-200">
                  {selectedReq.route} ({selectedReq.decision}) · {selectedReq.reason}
                </div>
              </div>

              <div>
                <label className="block text-slate-600 font-medium mb-1">
                  Override Route To:
                </label>
                <select
                  value={overrideRoute}
                  onChange={(e) => setOverrideRoute(e.target.value)}
                  className="w-full p-2.5 bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500/30"
                >
                  <option value="CONTRACT_PO">CONTRACT_PO (Direct PO)</option>
                  <option value="SPOT_PO">SPOT_PO (Preferred Supplier)</option>
                  <option value="EMERGENCY_PO">EMERGENCY_PO</option>
                  <option value="RFQ">RFQ (3 Quotes)</option>
                  <option value="RFP">RFP (Formal 5 Quotes)</option>
                  <option value="CAPEX_SOURCING">CAPEX_SOURCING</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-600 font-medium mb-1">
                  Override Supplier (optional):
                </label>
                <input
                  type="text"
                  value={overrideSupplier}
                  onChange={(e) => setOverrideSupplier(e.target.value)}
                  placeholder="e.g. S001"
                  className="w-full p-2.5 bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500/30"
                />
              </div>

              <div>
                <label className="block text-slate-800 font-semibold mb-1">
                  Mandatory Explanation Comment <span className="text-red-500">*</span>:
                </label>
                <textarea
                  rows={3}
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="Explain why this decision is being overridden (Clause 8 requires written reasoning for audit trail)..."
                  className="w-full p-2.5 bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500/30"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setOverrideModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingOverride || !overrideReason.trim()}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-semibold rounded-lg shadow-xs"
                >
                  {submittingOverride ? 'Saving...' : 'Confirm Override'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

