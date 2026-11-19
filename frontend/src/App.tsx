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

  const fetchRequirementsAndPolicy = async () => {
    try {
      const pRes = await fetch('/api/policy/active');
      if (pRes.ok) {
        const pData = await pRes.json();
        setPolicyVersion(pData.version || 'v5.0');
      }

      const rRes = await fetch('/api/buyer/requirements');
      if (rRes.ok) {
        const rData = await rRes.json();
        setRequirements(rData || []);
      }
    } catch (err) {
      console.error('Error fetching data:', err);
    }
  };

  useEffect(() => {
    fetchRequirementsAndPolicy();
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        policyVersion={policyVersion}
      />

      <main className="flex-1">
        {activeTab === 'workspace' && (
          <BuyerWorkspace
            requirements={requirements}
            onRefresh={fetchRequirementsAndPolicy}
          />
        )}

        {activeTab === 'intake' && (
          <RequesterChat
            onPRCreated={fetchRequirementsAndPolicy}
            onBatchProcessed={fetchRequirementsAndPolicy}
          />
        )}

        {activeTab === 'config' && (
          <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
            <ConfigTabbedView onDataUpdated={fetchRequirementsAndPolicy} />
          </div>
        )}
      </main>
    </div>
  );
};

// Sub-tabs for the Policy, Suppliers & Audit view
const ConfigTabbedView: React.FC<{ onDataUpdated: () => void }> = ({ onDataUpdated }) => {
  const [activeSubTab, setActiveSubTab] = useState('rules');

  const subTabs = [
    { id: 'rules', label: 'Rules' },
    { id: 'suppliers', label: 'Suppliers' },
    { id: 'contracts', label: 'Contracts' },
    { id: 'audit', label: 'Audit Log' },
  ];

  return (
    <div className="space-y-6">
      {/* Sub-tab Navigation */}
      <div className="border-b border-slate-200">
        <nav className="flex gap-6">
          {subTabs.map((tab) => {
            const isActive = activeSubTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveSubTab(tab.id)}
                className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  isActive
                    ? 'border-slate-900 text-slate-900'
                    : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Sub-tab Content */}
      <div>
        {activeSubTab === 'rules' && <PolicyManagerView onPolicyUpdated={onDataUpdated} />}
        {activeSubTab === 'suppliers' && <SuppliersExportView />}
        {activeSubTab === 'contracts' && <SuppliersExportView />}
        {activeSubTab === 'audit' && <AuditLogView />}
      </div>
    </div>
  );
};

export default App;

