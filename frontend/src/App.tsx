import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { RequesterChat } from './components/RequesterChat';
import { BuyerWorkspace } from './components/BuyerWorkspace';
import { PolicyManagerView } from './components/PolicyManagerView';
import { SuppliersExportView } from './components/SuppliersExportView';
import { AuditLogView } from './components/AuditLogView';
import { BuyerRequirement } from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState('workspace');
  const [policyVersion, setPolicyVersion] = useState('v5.0');
  const [requirements, setRequirements] = useState<BuyerRequirement[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchRequirementsAndPolicy = async () => {
    setLoading(true);
    try {
      // 1. Fetch active policy
      const pRes = await fetch('/api/policy/active');
      if (pRes.ok) {
        const pData = await pRes.json();
        setPolicyVersion(pData.version || 'v5.0');
      }

      // 2. Fetch buyer requirements
      const rRes = await fetch('/api/buyer/requirements');
      if (rRes.ok) {
        const rData = await rRes.json();
        setRequirements(rData || []);
      }
    } catch (err) {
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequirementsAndPolicy();
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        policyVersion={policyVersion}
        onRefresh={fetchRequirementsAndPolicy}
        loading={loading}
      />

      {/* Main Tab Content */}
      <main className="flex-1 pb-16">
        {activeTab === 'chat' && (
          <RequesterChat
            onPRCreated={fetchRequirementsAndPolicy}
            onBatchProcessed={fetchRequirementsAndPolicy}
          />
        )}

        {activeTab === 'workspace' && (
          <BuyerWorkspace
            requirements={requirements}
            onRefresh={fetchRequirementsAndPolicy}
          />
        )}

        {activeTab === 'policy' && (
          <PolicyManagerView
            onPolicyUpdated={fetchRequirementsAndPolicy}
          />
        )}

        {activeTab === 'suppliers' && (
          <SuppliersExportView />
        )}

        {activeTab === 'audit' && (
          <AuditLogView />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Corvo Engineering Pvt Ltd · PR-to-PO Procurement Copilot</span>
          <span className="font-mono text-slate-400">Policy {policyVersion} Active · Evaluation Ready</span>
        </div>
      </footer>
    </div>
  );
};

export default App;

