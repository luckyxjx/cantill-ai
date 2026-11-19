import React from 'react';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  policyVersion: string;
}

export const Navbar: React.FC<NavbarProps> = ({ 
  activeTab, setActiveTab, policyVersion 
}) => {
  const navItems = [
    { id: 'workspace', label: 'Buyer Workspace' },
    { id: 'intake', label: 'Requisition Intake' },
    { id: 'config', label: 'Policy, Suppliers & Audit' },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo & Navigation */}
          <div className="flex items-center gap-8">
            <span className="font-semibold text-slate-900 whitespace-nowrap">Corvo Engineering</span>
            
            <nav className="flex items-center gap-1">
              {navItems.map((item) => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors whitespace-nowrap ${
                      isActive
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-700 hover:text-slate-900 hover:bg-slate-50'
                    }`}
                  >
                    {item.label}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Policy Status & User */}
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 text-slate-700 border border-slate-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span className="whitespace-nowrap font-medium">Active Policy: {policyVersion} (PUN1, CHK1)</span>
            </div>
            <div className="text-slate-500 whitespace-nowrap">
              Buyer Officer · <span className="font-medium text-slate-700">BO-04</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

