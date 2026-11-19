import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, CheckCircle2, Upload, FileText } from 'lucide-react';

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

// Helper to strip emoji and clean markdown
const cleanText = (text: string): string => {
  // Remove emoji (Unicode ranges)
  let cleaned = text.replace(/[\u{1F600}-\u{1F64F}]/gu, ''); // Emoticons
  cleaned = cleaned.replace(/[\u{1F300}-\u{1F5FF}]/gu, ''); // Misc Symbols
  cleaned = cleaned.replace(/[\u{1F680}-\u{1F6FF}]/gu, ''); // Transport
  cleaned = cleaned.replace(/[\u{1F1E0}-\u{1F1FF}]/gu, ''); // Flags
  cleaned = cleaned.replace(/[\u{2600}-\u{26FF}]/gu, '');   // Misc symbols
  cleaned = cleaned.replace(/[\u{2700}-\u{27BF}]/gu, '');   // Dingbats
  // Strip markdown bold
  cleaned = cleaned.replace(/\*\*(.*?)\*\*/g, '$1');
  cleaned = cleaned.replace(/\*(.*?)\*/g, '$1');
  return cleaned.trim();
};

export const RequesterChat: React.FC<RequesterChatProps> = ({ onPRCreated, onBatchProcessed }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: 'assistant',
      text: "Hello! I am your Corvo Procurement Assistant. Type your purchase request in plain language (e.g. \"Need 200 nitrile gloves for Chakan by next Friday\"), and I will match items, check rate contracts, and route your requisition according to Corvo Procurement Policy v5.0.",
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

  const quickScenarios = [
    { label: 'Contract ceiling overflow', prompt: 'Need 200 nitrile gloves for Chakan by next Friday' },
    { label: 'Emergency procurement', prompt: 'Require 11 solenoid valves for CHK1 urgent by 2026-12-13' },
    { label: 'Capex item (crane)', prompt: 'Need 4 EOT cranes 5 ton for Pune by 2026-12-01' },
    { label: 'New item sourcing', prompt: 'Need 1 drinking water purifier 50 LPH for Bhosari by next week' }
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
      
      // Clean the assistant's reply
      const cleanedReply = cleanText(data.reply);
      
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: cleanedReply,
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
          text: `Error processing request: ${err.message}`,
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
    setBatchStatus('Processing PR batch CSV...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/process-batch', {
        method: 'POST',
        body: formData
      });
      if (!res.ok) throw new Error('Batch processing failed');
      const data = await res.json();
      setBatchStatus(`Batch processed: ${data.metrics.total_pr_lines} PR lines → ${data.metrics.total_requirements} requirements, ${data.metrics.total_pos_formed} POs`);
      if (onBatchProcessed) onBatchProcessed();
    } catch (err: any) {
      setBatchStatus(`Error: ${err.message}`);
    } finally {
      setUploadingBatch(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
      {/* Chat Column (2/3) */}
      <div className="lg:col-span-2 bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col h-[700px]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center">
              <Bot className="w-5 h-5 text-slate-700" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Procurement Assistant</h2>
              <p className="text-xs text-slate-500">Slot-filling and policy routing</p>
            </div>
          </div>
          <button
            onClick={() => {
              setMessages([
                {
                  sender: 'assistant',
                  text: "Chat cleared. What would you like to purchase today?",
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                }
              ]);
              setChatState(null);
            }}
            className="text-xs text-slate-500 hover:text-slate-800 font-medium px-3 py-1.5 rounded border border-slate-200 hover:bg-slate-50 transition-colors"
          >
            New Session
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex gap-3 ${
                m.sender === 'user' ? 'flex-row-reverse' : ''
              }`}
            >
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs flex-shrink-0 ${
                  m.sender === 'user'
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-700'
                }`}
              >
                {m.sender === 'user' ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
              </div>

              <div
                className={`rounded-lg px-4 py-3 text-sm max-w-[80%] ${
                  m.sender === 'user'
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-900 border border-slate-200'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.text}</div>
                <div
                  className={`text-[10px] mt-1 ${
                    m.sender === 'user' ? 'text-slate-400' : 'text-slate-500'
                  }`}
                >
                  {m.timestamp}
                </div>

                {/* Inline Confirmation */}
                {m.isConfirmation && (
                  <button
                    onClick={handleConfirm}
                    className="mt-3 px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs rounded transition-colors flex items-center gap-1.5"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" /> Confirm & Create PR
                  </button>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 items-center text-slate-500 text-sm">
              <Bot className="w-5 h-5 text-slate-700" />
              <span>Analyzing policy...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-slate-200">
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
              placeholder="e.g. Need 50 solenoid valves for Chakan by next Friday..."
              className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-slate-900"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white rounded-lg font-medium text-sm flex items-center gap-1.5 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>

      {/* Right Column */}
      <div className="space-y-6">
        {/* Slot Card */}
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-900">Extracted Slots</h3>
            <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${
              chatState?.is_ready_to_create
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-slate-100 text-slate-600 border border-slate-200'
            }`}>
              {chatState?.is_ready_to_create ? 'Ready' : 'In Progress'}
            </span>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Item Code:</span>
              <span className="font-mono font-medium text-slate-800">
                {chatState?.item_code || '—'}
              </span>
            </div>

            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Description:</span>
              <span className="font-medium text-slate-800 text-right max-w-[140px] truncate" title={chatState?.matched_description}>
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
          </div>

          {chatState?.is_ready_to_create && !chatState?.confirmed && (
            <button
              onClick={handleConfirm}
              className="w-full mt-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
            >
              <CheckCircle2 className="w-4 h-4" /> Submit Requisition
            </button>
          )}
        </div>

        {/* Batch Upload */}
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-3">
            <Upload className="w-4 h-4 text-slate-700" />
            Batch CSV Upload
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            Upload a PR batch CSV to evaluate against active policy.
          </p>

          <label className="border-2 border-dashed border-slate-200 hover:border-slate-400 rounded-lg p-5 flex flex-col items-center justify-center text-center cursor-pointer transition-colors">
            <FileText className="w-7 h-7 text-slate-400 mb-2" />
            <span className="text-xs font-semibold text-slate-700">Choose CSV file</span>
            <span className="text-[11px] text-slate-400 mt-1">sample_pr_batch.csv format</span>
            <input
              type="file"
              accept=".csv"
              onChange={handleBatchUpload}
              disabled={uploadingBatch}
              className="hidden"
            />
          </label>

          {batchStatus && (
            <div className="mt-3 p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700">
              {batchStatus}
            </div>
          )}
        </div>

        {/* Sample Scenarios */}
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">Sample Scenarios</h3>
          <div className="space-y-2">
            {quickScenarios.map((scenario, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(scenario.prompt)}
                className="w-full text-left px-3 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded text-xs text-slate-700 font-medium transition-colors"
              >
                {scenario.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
