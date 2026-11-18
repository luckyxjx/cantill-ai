import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, Bot, User, CheckCircle2, AlertCircle, Sparkles, 
  UploadCloud, FileText, ArrowRight, CornerDownLeft, ShieldAlert 
} from 'lucide-react';

interface RequesterChatProps {
  onPRCreated?: () => void;
  onBatchProcessed?: () => void;
}

interface Message {
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  isConfirmation?: boolean;
}

export const RequesterChat: React.FC<RequesterChatProps> = ({ onPRCreated, onBatchProcessed }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: 'assistant',
      text: "👋 Hello! I am your **Corvo Procurement Copilot**.\n\nType your purchase request in plain language (e.g. *\"Need 200 nitrile gloves for Chakan by next Friday\"*), and I will match items, check rate contracts, and route your requisition according to **Corvo Procurement Policy v5.0**.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [chatState, setChatState] = useState<any>(null);
  const [uploadingBatch, setUploadingBatch] = useState(false);
  const [batchStatus, setBatchStatus] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const quickPrompts = [
    "Need 200 nitrile gloves for Chakan by next Friday",
    "Require 11 solenoid valves for CHK1 urgent by 2026-12-13",
    "Need 4 EOT cranes 5 ton for Pune by 2026-12-01",
    "Need 1 drinking water purifier 50 LPH for Bhosari by next week"
  ];

  const handleSendMessage = async (textToSend?: string) => {
    const msg = textToSend || input;
    if (!msg.trim()) return;

    const userMsg: Message = {
      sender: 'user',
      text: msg,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: msg,
          state: chatState,
          requester: 'A. Kumar'
        })
      });

      if (!res.ok) throw new Error('Failed to send message');
      const data = await res.json();

      setChatState(data.state);
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: data.reply,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isConfirmation: data.state?.is_ready_to_create && !data.state?.confirmed
        }
      ]);

      if (data.state?.confirmed && data.state?.created_pr_no) {
        if (onPRCreated) onPRCreated();
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: `❌ Error processing request: ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = () => {
    handleSendMessage('Confirm');
  };

  const handleBatchUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingBatch(true);
    setBatchStatus('Processing PR batch CSV against active policy...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/process-batch', {
        method: 'POST',
        body: formData
      });
      if (!res.ok) throw new Error('Batch processing failed');
      const data = await res.json();
      setBatchStatus(`✅ Batch processed! Evaluated ${data.metrics.total_pr_lines} PR lines into ${data.metrics.total_requirements} requirements and ${data.metrics.total_pos_formed} POs.`);
      if (onBatchProcessed) onBatchProcessed();
    } catch (err: any) {
      setBatchStatus(`❌ Error uploading batch: ${err.message}`);
    } finally {
      setUploadingBatch(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
      {/* Main Chat Stream (2 Cols) */}
      <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 flex flex-col h-[750px]">
        {/* Chat Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 rounded-t-2xl">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold">
              <Bot className="w-5 h-5 text-brand-600" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-800">Procurement Intake Assistant</h2>
              <p className="text-xs text-slate-500">Autonomous slot-filling & policy routing</p>
            </div>
          </div>
          <button
            onClick={() => {
              setMessages([
                {
                  sender: 'assistant',
                  text: "Chat context cleared. What would you like to purchase today?",
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                }
              ]);
              setChatState(null);
            }}
            className="text-xs text-slate-500 hover:text-slate-800 font-medium px-2.5 py-1 rounded border border-slate-200 hover:bg-slate-100 transition-colors"
          >
            New Session
          </button>
        </div>

        {/* Message Bubble List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex gap-3 max-w-[85%] ${
                m.sender === 'user' ? 'ml-auto flex-row-reverse' : ''
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs flex-shrink-0 ${
                  m.sender === 'user'
                    ? 'bg-slate-800 text-white'
                    : 'bg-brand-50 text-brand-600 border border-brand-200'
                }`}
              >
                {m.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.sender === 'user'
                    ? 'bg-brand-600 text-white shadow-xs rounded-tr-none'
                    : 'bg-slate-100 text-slate-800 rounded-tl-none border border-slate-200/60'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.text}</div>
                <div
                  className={`text-[10px] mt-1 text-right ${
                    m.sender === 'user' ? 'text-brand-100' : 'text-slate-400'
                  }`}
                >
                  {m.timestamp}
                </div>

                {/* Inline Confirmation Card */}
                {m.isConfirmation && (
                  <div className="mt-3 pt-3 border-t border-slate-200 flex items-center gap-2">
                    <button
                      onClick={handleConfirm}
                      className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white font-medium text-xs rounded-lg shadow-sm transition-colors flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" /> Confirm & Create PR
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 max-w-[80%] items-center text-slate-400 text-sm">
              <Bot className="w-5 h-5 animate-bounce text-brand-500" />
              <span>Analyzing policy & matching items...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Quick Prompts */}
        <div className="px-6 py-2 bg-slate-50 border-t border-slate-100 flex items-center gap-2 overflow-x-auto text-xs">
          <span className="text-slate-400 flex items-center gap-1 font-medium whitespace-nowrap">
            <Sparkles className="w-3 h-3 text-amber-500" /> Examples:
          </span>
          {quickPrompts.map((p, i) => (
            <button
              key={i}
              onClick={() => handleSendMessage(p)}
              className="px-2.5 py-1 bg-white hover:bg-slate-100 border border-slate-200 rounded-full text-slate-600 whitespace-nowrap transition-colors"
            >
              {p}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-slate-200 bg-white rounded-b-2xl">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. Need 50 solenoid valves for Chakan plant by next Friday..."
              className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 transition-all"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-4 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-xl font-medium text-sm flex items-center gap-1.5 transition-all shadow-xs"
            >
              <Send className="w-4 h-4" />
              <span className="hidden sm:inline">Send</span>
            </button>
          </form>
        </div>
      </div>

      {/* Right Column: Active Slot Extraction & Batch Uploader */}
      <div className="space-y-6">
        {/* Requisition Status Slot Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-brand-600" />
              Requisition Slots
            </h3>
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
              chatState?.is_ready_to_create
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-amber-50 text-amber-700 border border-amber-200'
            }`}>
              {chatState?.is_ready_to_create ? 'Ready for Confirmation' : 'In Progress'}
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Item Code:</span>
              <span className="font-mono font-medium text-slate-800">
                {chatState?.item_code || '—'}
              </span>
            </div>

            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Description:</span>
              <span className="font-medium text-slate-800 text-right max-w-[180px] truncate" title={chatState?.matched_description}>
                {chatState?.matched_description || '—'}
              </span>
            </div>

            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Quantity & UoM:</span>
              <span className="font-medium text-slate-800">
                {chatState?.quantity ? `${chatState.quantity} ${chatState.uom || 'NOS'}` : '—'}
              </span>
            </div>

            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Plant:</span>
              <span className="font-medium text-slate-800">
                {chatState?.plant ? (
                  <span className="px-2 py-0.5 rounded bg-slate-100 font-semibold text-slate-700">
                    {chatState.plant}
                  </span>
                ) : '—'}
              </span>
            </div>

            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Need-by Date:</span>
              <span className="font-medium text-slate-800">
                {chatState?.need_by_date || '—'}
              </span>
            </div>

            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Urgency:</span>
              <span className={`font-semibold ${
                chatState?.urgency === 'Emergency' ? 'text-red-600' : 'text-slate-700'
              }`}>
                {chatState?.urgency || 'Normal'}
              </span>
            </div>

            {chatState?.item_code === 'NEW' && (
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Est. Unit Price:</span>
                <span className="font-medium text-slate-800">
                  {chatState?.estimated_unit_price ? `₹${chatState.estimated_unit_price.toLocaleString()}` : 'Required for new item'}
                </span>
              </div>
            )}
          </div>

          {chatState?.is_ready_to_create && !chatState?.confirmed && (
            <button
              onClick={handleConfirm}
              className="w-full mt-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all flex items-center justify-center gap-1.5"
            >
              <CheckCircle2 className="w-4 h-4" /> Submit Requisition Now
            </button>
          )}
        </div>

        {/* Batch PR CSV Upload Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-2">
            <UploadCloud className="w-4 h-4 text-brand-600" />
            Upload PR Batch CSV
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            Upload a bulk PR batch CSV (e.g. 186-line batch) to evaluate against the active policy.
          </p>

          <label className="border-2 border-dashed border-slate-200 hover:border-brand-400 rounded-xl p-5 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-slate-50/50 hover:bg-slate-50">
            <FileText className="w-8 h-8 text-slate-400 mb-2" />
            <span className="text-xs font-semibold text-brand-600">Click to choose PR batch CSV</span>
            <span className="text-[11px] text-slate-400 mt-1">Accepts sample_pr_batch.csv format</span>
            <input
              type="file"
              accept=".csv"
              onChange={handleBatchUpload}
              disabled={uploadingBatch}
              className="hidden"
            />
          </label>

          {batchStatus && (
            <div className="mt-3 p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs leading-relaxed text-slate-700">
              {batchStatus}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

