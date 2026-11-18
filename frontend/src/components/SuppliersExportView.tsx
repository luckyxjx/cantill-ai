import React, { useState, useEffect } from 'react';
import { 
  Users, Download, FileSpreadsheet, Search, Calendar, 
  Award, ShieldAlert, CheckCircle2, Upload, FileText 
} from 'lucide-react';
import { PreferredSupplier } from '../types';

export const SuppliersExportView: React.FC = () => {
  const [asOfDate, setAsOfDate] = useState('2026-11-01');
  const [selectedItem, setSelectedItem] = useState('ITM-1048');
  const [suppliers, setSuppliers] = useState<PreferredSupplier[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadingContract, setUploadingContract] = useState(false);
  const [contractMsg, setContractMsg] = useState<string | null>(null);

  const popularItems = [
    { code: 'ITM-1048', name: 'Nitrile coated gloves (Worked Ex 5)' },
    { code: 'ITM-1036', name: 'Pneumatic cylinder 50x100 (Worked Ex 5)' },
    { code: 'ITM-1016', name: 'MIG wire ER70S-6 1.2mm (Worked Ex 5)' },
    { code: 'ITM-1022', name: 'Ball bearing 6308-ZZ (Worked Ex 3)' },
    { code: 'ITM-1034', name: 'Encoder for CNC spindle (Worked Ex 11)' }
  ];

  const fetchSuppliers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/suppliers/preferred?as_of_date=${asOfDate}&item_code=${selectedItem}`);
      const data = await res.json();
      setSuppliers(data.suppliers || []);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSuppliers();
  }, [asOfDate, selectedItem]);

  const handleDownloadDecisionsCSV = () => {
    window.location.href = '/api/export-decisions';
  };

  const handleDownloadPreferredCSV = () => {
    window.location.href = `/api/suppliers/preferred?as_of_date=${asOfDate}&format=csv`;
  };

  const handleContractUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingContract(true);
    setContractMsg(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/contracts/upload-pdf', {
        method: 'POST',
        body: formData
      });
      if (!res.ok) throw new Error('Failed to upload contract');
      const data = await res.json();
      setContractMsg(`✅ ${data.message} with ceiling ₹${data.contract.value_cap.toLocaleString()} and ${data.contract.lines.length} lines.`);
      fetchSuppliers();
    } catch (err: any) {
      setContractMsg(`❌ Error: ${err.message}`);
    } finally {
      setUploadingContract(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 space-y-8">
      {/* Downloads Action Bar */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-brand-600" />
            Evaluation Export Hub
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Export required CSV deliverables for Run 1, Run 2, and preferred supplier lists matching exact guidelines.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleDownloadDecisionsCSV}
            className="px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white rounded-xl text-xs font-semibold shadow-xs flex items-center gap-2 transition-colors"
          >
            <Download className="w-4 h-4" />
            Download Decisions CSV (12 Columns)
          </button>

          <button
            onClick={handleDownloadPreferredCSV}
            className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold shadow-xs flex items-center gap-2 transition-colors"
          >
            <Download className="w-4 h-4" />
            Export Preferred Suppliers CSV (Top 3)
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Preferred Supplier Explorer (2 Cols) */}
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Users className="w-5 h-5 text-brand-600" />
                Preferred Supplier List (Policy Section 6)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Automatically scored from PO history, contract history, on-time record, and quality rating.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-slate-400" />
              <input
                type="date"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
                className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700"
              />
            </div>
          </div>

          {/* Item Selector Pills */}
          <div className="space-y-2">
            <span className="text-xs font-semibold text-slate-600">Select Item:</span>
            <div className="flex flex-wrap gap-2">
              {popularItems.map((it) => (
                <button
                  key={it.code}
                  onClick={() => setSelectedItem(it.code)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                    selectedItem === it.code
                      ? 'bg-brand-600 text-white font-semibold shadow-xs'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  {it.code}
                </button>
              ))}
            </div>
          </div>

          {/* Suppliers Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead>
                <tr className="border-b border-slate-200 text-slate-400 uppercase text-[10px] bg-slate-50/50">
                  <th className="py-2.5 px-3">Rank</th>
                  <th className="py-2.5 px-3">Supplier</th>
                  <th className="py-2.5 px-3">Ref Price</th>
                  <th className="py-2.5 px-3 text-center">Score</th>
                  <th className="py-2.5 px-3 text-center">Recency</th>
                  <th className="py-2.5 px-3 text-center">POs (548d)</th>
                  <th className="py-2.5 px-3 text-center">Contract</th>
                  <th className="py-2.5 px-3 text-center">On-Time</th>
                  <th className="py-2.5 px-3 text-center">Quality</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {suppliers.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="text-center py-8 text-slate-400">
                      No preferred suppliers found for this item as of {asOfDate}.
                    </td>
                  </tr>
                ) : (
                  suppliers.map((s) => (
                    <tr key={s.supplier_id} className={`hover:bg-slate-50/60 ${s.rank === 1 ? 'bg-amber-50/30' : ''}`}>
                      <td className="py-2.5 px-3">
                        <span className={`w-6 h-6 rounded-full inline-flex items-center justify-center font-bold text-xs ${
                          s.rank === 1 
                            ? 'bg-amber-500 text-white shadow-xs' 
                            : 'bg-slate-100 text-slate-700'
                        }`}>
                          {s.rank}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-slate-900">{s.supplier_name}</div>
                        <div className="text-[11px] font-mono text-slate-400">{s.supplier_id}</div>
                      </td>
                      <td className="py-2.5 px-3 font-medium text-slate-900">
                        {s.reference_price ? `₹${s.reference_price.toLocaleString()}` : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-center font-bold text-slate-800">
                        {s.score.toFixed(3)}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="px-2 py-0.5 rounded bg-slate-100 font-mono text-[11px]">
                          {s.recency.toFixed(1)}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center font-semibold">
                        {s.po_count}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        {s.has_contract ? (
                          <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold text-[10px]">
                            YES
                          </span>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-center font-semibold text-slate-800">
                        {s.on_time_pct}%
                      </td>
                      <td className="py-2.5 px-3 text-center font-semibold text-slate-800">
                        {s.quality_rating.toFixed(1)} / 5.0
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: PDF Contract Ingestion */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Upload className="w-5 h-5 text-brand-600" />
              Ingest Signed Contract PDF
            </h3>
            <p className="text-xs text-slate-500">
              Upload PDF rate contracts signed after October 31 (e.g. RC-2026-031 or RC-2026-033). The system parses supplier, dates, value cap, and rates automatically.
            </p>

            <label className="border-2 border-dashed border-slate-200 hover:border-brand-400 rounded-xl p-5 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-slate-50/50 hover:bg-slate-50">
              <FileText className="w-8 h-8 text-slate-400 mb-2" />
              <span className="text-xs font-semibold text-brand-600">Select Contract PDF</span>
              <span className="text-[10px] text-slate-400 mt-1">Accepts signed rate contract PDFs</span>
              <input
                type="file"
                accept=".pdf"
                onChange={handleContractUpload}
                disabled={uploadingContract}
                className="hidden"
              />
            </label>

            {contractMsg && (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-700 leading-relaxed">
                {contractMsg}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

