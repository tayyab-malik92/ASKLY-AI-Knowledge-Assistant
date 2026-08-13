import React, { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://127.0.0.1:8000'; // 'http://localhost:8000' 

export default function AsklyEnterpriseApp() {
  // Navigation & User State
  const [step, setStep] = useState('landing'); // 'landing' | 'onboarding' | 'dashboard'
  const [userName, setUserName] = useState('');
  const [theme, setTheme] = useState('dark'); // 'dark' | 'light'

  // Dashboard State
  const [sessionId, setSessionId] = useState('demo-session-1');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [backendLatency, setBackendLatency] = useState('14ms');
  const [isCmdOpen, setIsCmdOpen] = useState(false);
  
  // Mouse Spotlight Effect State
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const chatEndRef = useRef(null);

  const handleMouseMove = (e) => {
    setMousePos({ x: e.clientX, y: e.clientY });
  };

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const fetchNotes = async () => {
    const start = performance.now();
    try {
      const res = await fetch(`${API_BASE}/notes?session_id=${sessionId}`);
      const end = performance.now();
      setBackendLatency(`${Math.round(end - start)}ms`);
      if (res.ok) {
        const data = await res.json();
        setNotes(data);
      }
    } catch (err) {
      console.error("Notes Sync Error:", err);
      setBackendLatency('Offline');
    }
  };

  useEffect(() => {
    if (step === 'dashboard') {
      fetchNotes();
      const handleKeyDown = (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
          e.preventDefault();
          setIsCmdOpen(prev => !prev);
        }
      };
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [sessionId, step]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userQuery = input;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userQuery }]);
    setLoading(true);

    const start = performance.now();
    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: userQuery,
        }),
      });

      const end = performance.now();
      setBackendLatency(`${Math.round(end - start)}ms`);
      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          sources: data.sources || [],
        },
      ]);

      if (data.saved_note_id || userQuery.toLowerCase().includes('save')) {
        fetchNotes();
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '❌ **System Offline:** Could not reach the FastAPI RAG backend. Verify backend service is live.' },
      ]);
      setBackendLatency('Offline');
    } finally {
      setLoading(false);
    }
  };

  // ================= 1. SILICON VALLEY LANDING PAGE =================
  if (step === 'landing') {
    return (
      <div 
        onMouseMove={handleMouseMove}
        className="relative h-screen w-full flex flex-col items-center justify-center bg-[#02040A] text-white overflow-hidden font-sans selection:bg-cyan-500 selection:text-slate-950"
      >
        <div 
          className="absolute pointer-events-none w-[600px] h-[600px] bg-gradient-to-tr from-cyan-500/10 via-indigo-600/10 to-transparent rounded-full blur-[120px] transition-transform duration-100 ease-out"
          style={{ transform: `translate(${mousePos.x - 300}px, ${mousePos.y - 300}px)` }}
        ></div>

        <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b12_1px,transparent_1px),linear-gradient(to_bottom,#1e293b12_1px,transparent_1px)] bg-[size:3.5rem_3.5rem] pointer-events-none"></div>

        <div className="relative z-10 text-center px-4 max-w-5xl mx-auto">
          <div className="inline-flex items-center gap-2.5 px-4 py-2 rounded-full bg-slate-900/90 border border-cyan-500/30 text-cyan-400 text-xs font-mono mb-8 shadow-[0_0_25px_rgba(6,182,212,0.15)] backdrop-blur-2xl">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="tracking-[0.2em] font-bold">NEURAL RAG PROTOCOL</span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-400">CHROMA + FAISS ACTIVE</span>
          </div>

          <h1 className="text-7xl md:text-9xl font-black tracking-[0.15em] mb-6 bg-gradient-to-r from-white via-cyan-100 to-indigo-500 bg-clip-text text-transparent drop-shadow-[0_15px_50px_rgba(6,182,212,0.35)]">
            ASKLY
          </h1>
          
          <p className="text-sm md:text-base text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed font-light tracking-wide">
            The definitive autonomous intelligence infrastructure. Enterprise vector search, zero-latency embeddings, and persistent SQLite knowledge architecture.
          </p>

          <button
            onClick={() => setStep('onboarding')}
            className="group relative inline-flex items-center gap-4 px-10 py-4 bg-gradient-to-r from-cyan-400 via-indigo-500 to-violet-600 hover:from-cyan-300 hover:to-violet-500 text-slate-950 font-black rounded-2xl shadow-[0_0_40px_rgba(6,182,212,0.4)] transition-all transform hover:-translate-y-1 active:translate-y-0 text-xs tracking-[0.25em] uppercase border border-white/20 cursor-pointer"
          >
            <span>Initialize Engine</span>
            <span className="group-hover:translate-x-2 transition-transform text-base text-slate-950 font-black">→</span>
          </button>
        </div>

        <div className="absolute bottom-6 text-center w-full text-[11px] text-slate-500 font-mono tracking-[0.3em]">
          ARCHITECT & LEAD ENGINEER: <span className="text-slate-300 font-bold">MUHAMMAD TAYYAB MALIK</span>
        </div>
      </div>
    );
  }

  // ================= 2. ONBOARDING GATEWAY =================
  if (step === 'onboarding') {
    return (
      <div className="relative h-screen w-full flex flex-col items-center justify-center bg-[#02040A] text-white overflow-hidden font-sans">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b12_1px,transparent_1px),linear-gradient(to_bottom,#1e293b12_1px,transparent_1px)] bg-[size:3.5rem_3.5rem] pointer-events-none"></div>
        <div className="absolute top-1/3 right-1/4 w-[500px] h-[500px] bg-cyan-500/10 rounded-full blur-[150px] pointer-events-none"></div>

        <div className="relative z-10 w-full max-w-md mx-auto p-8 bg-[#070B14]/90 backdrop-blur-2xl border border-cyan-500/30 rounded-3xl shadow-[0_0_50px_rgba(6,182,212,0.15)]">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 bg-gradient-to-tr from-cyan-400 to-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-cyan-500/30 text-xl text-slate-950 font-black border border-white/20">
              ⚡
            </div>
            <div>
              <h2 className="text-xl font-black tracking-tight text-white">Operator Authentication</h2>
              <p className="text-[11px] text-cyan-400 font-mono">Secure Enterprise Handshake</p>
            </div>
          </div>

          <p className="text-xs text-slate-400 mb-6 leading-relaxed">
            Please register your professional credentials to establish session encryption.
          </p>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (userName.trim()) setStep('dashboard');
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-[10px] font-mono text-cyan-400 mb-1.5 uppercase tracking-widest">Full Name / Operator ID</label>
              <input
                type="text"
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                placeholder="e.g. Muhammad Tayyab Malik"
                required
                className="w-full bg-[#03060C] border border-slate-700/80 rounded-xl px-4 py-3.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan-500 transition shadow-inner font-mono"
              />
            </div>

            <button
              type="submit"
              className="w-full bg-gradient-to-r from-cyan-400 to-indigo-600 hover:from-cyan-300 hover:to-indigo-500 text-slate-950 font-black py-3.5 rounded-xl transition shadow-[0_0_30px_rgba(6,182,212,0.3)] text-xs tracking-[0.2em] uppercase cursor-pointer"
            >
              Establish Session →
            </button>
          </form>
        </div>

        <div className="absolute bottom-6 text-center w-full text-[11px] text-slate-500 font-mono tracking-widest">
          DESIGNED BY <span className="text-slate-300 font-bold">MUHAMMAD TAYYAB MALIK</span>
        </div>
      </div>
    );
  }

  // ================= 3. MAIN DASHBOARD =================
  const isDark = theme === 'dark';

  return (
    <div className={`flex h-screen overflow-hidden font-sans transition-colors duration-300 ${
      isDark ? 'bg-[#03060C] text-slate-100' : 'bg-slate-100 text-slate-900'
    }`}>
      
      {/* COMMAND PALETTE MODAL (CTRL+K) */}
      {isCmdOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4">
          <div className={`w-full max-w-lg rounded-3xl border p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150 ${
            isDark ? 'bg-[#0A0F1D] border-cyan-500/40 text-slate-100' : 'bg-white border-slate-300 text-slate-900'
          }`}>
            <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-700/50">
              <span className="text-xs font-mono font-bold text-cyan-400 uppercase tracking-widest">⚡ Neural Command Center</span>
              <button onClick={() => setIsCmdOpen(false)} className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800 cursor-pointer">ESC</button>
            </div>
            <div className="space-y-2 text-xs">
              <button 
                onClick={() => { setInput("What is ChromaDB and FAISS?"); setIsCmdOpen(false); }}
                className="w-full text-left p-3 rounded-xl hover:bg-cyan-500/10 hover:border-cyan-500/30 border border-transparent transition flex items-center justify-between cursor-pointer"
              >
                <span>🔍 Query: Explain ChromaDB & FAISS Architecture</span>
                <span className="text-cyan-400 font-mono">Select</span>
              </button>
              <button 
                onClick={() => { setInput("Save a note titled 'SYSTEM SYNC' with content 'Operational readiness confirmed.'"); setIsCmdOpen(false); }}
                className="w-full text-left p-3 rounded-xl hover:bg-cyan-500/10 hover:border-cyan-500/30 border border-transparent transition flex items-center justify-between cursor-pointer"
              >
                <span>📝 Command: Record SQLite Persistence Note</span>
                <span className="text-cyan-400 font-mono">Select</span>
              </button>
              <button 
                onClick={() => { fetchNotes(); setIsCmdOpen(false); }}
                className="w-full text-left p-3 rounded-xl hover:bg-cyan-500/10 hover:border-cyan-500/30 border border-transparent transition flex items-center justify-between cursor-pointer"
              >
                <span>🔄 Sync: Refresh Persistent Vault State</span>
                <span className="text-cyan-400 font-mono">Select</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CHAT WORKSPACE */}
      <div className={`flex-1 flex flex-col h-full relative border-r transition-colors duration-300 ${
        isDark ? 'border-slate-800/60 bg-gradient-to-b from-[#070B14] to-[#03060C]' : 'border-slate-300 bg-gradient-to-b from-white to-slate-50'
      }`}>
        
        {/* TOP NAVBAR */}
        <header className={`h-16 px-6 border-b flex justify-between items-center backdrop-blur-2xl z-20 shadow-lg transition-colors duration-300 ${
          isDark ? 'border-slate-800/80 bg-[#070B14]/80' : 'border-slate-200 bg-white/80'
        }`}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-tr from-cyan-400 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-cyan-500/25 ring-1 ring-white/20 text-slate-950 font-black">
              ⚡
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className={`text-sm font-black tracking-wider bg-gradient-to-r bg-clip-text text-transparent ${
                  isDark ? 'from-white via-cyan-100 to-indigo-400' : 'from-slate-900 via-cyan-800 to-indigo-600'
                }`}>
                  ASKLY ENTERPRISE RAG
                </h1>
                <span className="px-1.5 py-0.5 text-[9px] font-mono bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded-md">
                  v6.0
                </span>
              </div>
              <p className={`text-[10px] font-mono tracking-wide ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Operator: <span className="font-bold text-cyan-400">{userName}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* LIVE TELEMETRY HUD */}
            <div className={`hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl border text-[11px] font-mono shadow-inner ${
              isDark ? 'bg-[#03060C] border-slate-800 text-slate-400' : 'bg-slate-200/70 border-slate-300 text-slate-700'
            }`}>
              <span className={`w-2 h-2 rounded-full ${backendLatency === 'Offline' ? 'bg-red-500' : 'bg-emerald-400 animate-pulse'}`}></span>
              <span>Latency:</span>
              <span className="text-cyan-400 font-bold">{backendLatency}</span>
            </div>

            {/* COMMAND PALETTE TOGGLE BUTTON */}
            <button
              onClick={() => setIsCmdOpen(true)}
              className={`p-2 rounded-xl border text-xs transition-all shadow-sm flex items-center gap-1.5 font-mono cursor-pointer ${
                isDark ? 'bg-[#03060C] border-slate-800 text-slate-300 hover:bg-slate-800' : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-100'
              }`}
              title="Open Command Center (Ctrl+K)"
            >
              <span>⌘K</span>
            </button>

            {/* THEME TOGGLE BUTTON */}
            <button
              onClick={() => setTheme(isDark ? 'light' : 'dark')}
              className={`p-2 rounded-xl border text-sm transition-all shadow-sm flex items-center gap-1.5 cursor-pointer ${
                isDark ? 'bg-[#03060C] border-slate-800 text-amber-400 hover:bg-slate-800' : 'bg-white border-slate-300 text-cyan-600 hover:bg-slate-100'
              }`}
              title="Toggle Light/Dark Theme"
            >
              <span>{isDark ? '☀️' : '🌙'}</span>
            </button>

            <div className={`flex items-center gap-2 border rounded-xl px-3 py-1.5 shadow-sm ${
              isDark ? 'bg-[#03060C] border-slate-800 text-slate-400' : 'bg-slate-200/70 border-slate-300 text-slate-700'
            }`}>
              <span className="text-xs">🛡️</span>
              <input
                type="text"
                value={sessionId}
                onChange={(e) => setSessionId(e.target.value)}
                className="bg-transparent text-xs text-cyan-400 font-mono font-semibold focus:outline-none w-20"
                title="Active Session ID"
              />
            </div>
          </div>
        </header>

        {/* CHAT MESSAGES STREAM */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto py-10">
              <div className="w-16 h-16 bg-gradient-to-b from-cyan-500/20 to-indigo-600/5 border border-cyan-500/30 rounded-3xl flex items-center justify-center mb-5 shadow-[0_0_30px_rgba(6,182,212,0.2)]">
                <span className="text-3xl">🔮</span>
              </div>
              <h3 className={`text-xl font-bold tracking-tight ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                Neural Engine Ready, {userName}
              </h3>
              <p className={`text-xs mt-2 leading-relaxed max-w-md ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Execute semantic vector searches across your document embeddings or command autonomous SQLite note logging.
              </p>
              
              <div className="mt-8 grid grid-cols-1 gap-3 w-full text-xs">
                <button 
                  onClick={() => setInput("What is ChromaDB and FAISS?")} 
                  className={`group p-3.5 border rounded-2xl text-left transition-all shadow-md flex items-center justify-between cursor-pointer ${
                    isDark ? 'bg-[#070B14] hover:bg-slate-800/90 border-slate-800/90 text-slate-300' : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-700'
                  }`}
                >
                  <span className="flex items-center gap-2.5">
                    <span className="text-cyan-400">💬</span> "What is ChromaDB and FAISS?"
                  </span>
                  <span className="text-slate-400 group-hover:translate-x-1 transition-transform">→</span>
                </button>
                <button 
                  onClick={() => setInput("Save a note titled 'AI PROJECT' with content 'Building Fullstack RAG engine'.")} 
                  className={`group p-3.5 border rounded-2xl text-left transition-all shadow-md flex items-center justify-between cursor-pointer ${
                    isDark ? 'bg-[#070B14] hover:bg-slate-800/90 border-slate-800/90 text-slate-300' : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-700'
                  }`}
                >
                  <span className="flex items-center gap-2.5">
                    <span className="text-cyan-400">📝</span> "Save a note titled 'AI PROJECT' with content..."
                  </span>
                  <span className="text-slate-400 group-hover:translate-x-1 transition-transform">→</span>
                </button>
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`flex gap-3.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-xl bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center shrink-0 mt-1 shadow-md text-sm">
                  🤖
                </div>
              )}

              <div className={`max-w-2xl rounded-2xl p-4 shadow-xl ${
                msg.role === 'user' 
                  ? 'bg-gradient-to-r from-cyan-400 to-indigo-600 text-slate-950 font-medium rounded-tr-none shadow-[0_0_20px_rgba(6,182,212,0.2)]' 
                  : isDark 
                    ? 'bg-[#0B101D]/90 border border-slate-700/60 text-slate-200 rounded-tl-none backdrop-blur-xl' 
                    : 'bg-white border border-slate-200 text-slate-800 rounded-tl-none'
              }`}>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                {msg.sources && msg.sources.length > 0 && (
                  <div className={`mt-4 pt-3 border-t ${isDark ? 'border-slate-700/60' : 'border-slate-200'}`}>
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold text-cyan-400 mb-2">
                      <span>📄</span>
                      <span>Retrieved Knowledge Sources</span>
                    </div>
                    <div className="space-y-1.5">
                      {msg.sources.map((src, i) => (
                        <div key={i} className={`p-2.5 rounded-lg text-xs border ${
                          isDark ? 'bg-[#03060C] border-slate-800/80 text-slate-300' : 'bg-slate-50 border-slate-200 text-slate-700'
                        }`}>
                          <span className="font-mono text-cyan-400 font-semibold">{src.document}</span>
                          <p className={`text-[11px] truncate mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>"{src.snippet}"</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 mt-1 shadow-md text-sm text-white">
                  👤
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3.5 justify-start items-center">
              <div className="w-8 h-8 rounded-xl bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center shadow-md animate-spin">
                ⏳
              </div>
              <div className={`p-3.5 rounded-xl border text-xs shadow-lg flex items-center gap-2 ${
                isDark ? 'bg-[#0B101D]/90 border-slate-700/60 text-slate-400' : 'bg-white border-slate-200 text-slate-600'
              }`}>
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
                Executing neural pipeline & vector similarity search...
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* BOTTOM INPUT BAR */}
        <div className={`p-4 border-t backdrop-blur-2xl transition-colors duration-300 ${
          isDark ? 'border-slate-800/80 bg-[#070B14]/90' : 'border-slate-200 bg-white/90'
        }`}>
          <div className="max-w-4xl mx-auto flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask a technical query or command 'Save a note...'"
              className={`flex-1 border rounded-2xl px-5 py-4 text-sm focus:outline-none focus:border-cyan-500 transition shadow-inner font-mono ${
                isDark ? 'bg-[#03060C] border-slate-700/80 text-slate-100 placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder-slate-400'
              }`}
            />
            <button
              onClick={handleSend}
              disabled={loading}
              className="bg-gradient-to-r from-cyan-400 to-indigo-600 hover:from-cyan-300 hover:to-indigo-500 text-slate-950 px-7 py-4 rounded-2xl font-black transition-all flex items-center gap-2 disabled:opacity-50 shadow-[0_0_25px_rgba(6,182,212,0.25)] text-xs tracking-wider cursor-pointer"
            >
              <span>🚀</span>
              <span>Send</span>
            </button>
          </div>
          <div className="text-center mt-3">
            <p className={`text-[10px] tracking-wider ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              ENTERPRISE AI ARCHITECTURE • DESIGNED & DEVELOPED BY <span className={`font-bold ${isDark ? 'text-slate-300' : 'text-slate-800'}`}>MUHAMMAD TAYYAB MALIK</span>
            </p>
          </div>
        </div>
      </div>

      {/* RIGHT SIDEBAR (SQLITE NOTES VAULT) */}
      <div className={`w-80 border-l p-5 flex flex-col h-full backdrop-blur-2xl transition-colors duration-300 ${
        isDark ? 'bg-[#050810]/95 border-slate-800/80' : 'bg-white border-slate-200'
      }`}>
        <div className={`flex items-center justify-between mb-5 pb-3 border-b ${isDark ? 'border-slate-800/80' : 'border-slate-200'}`}>
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-amber-500/10 border border-amber-500/20 rounded-lg">
              <span className="text-xs">📝</span>
            </div>
            <div>
              <h2 className={`text-xs font-bold tracking-wider ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>SQLITE STORAGE</h2>
              <p className="text-[9px] text-slate-400 font-mono">Persistent Notes Vault</p>
            </div>
          </div>
          <button 
            onClick={fetchNotes} 
            className={`px-2.5 py-1.5 rounded-xl text-xs transition border flex items-center gap-1 shadow-sm cursor-pointer ${
              isDark ? 'bg-[#03060C] hover:bg-slate-800 border-slate-800 text-slate-300' : 'bg-slate-100 hover:bg-slate-200 border-slate-200 text-slate-700'
            }`}
            title="Refresh Notes"
          >
            <span>🔄</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-3.5 pr-1">
          {notes.length === 0 ? (
            <div className="text-center py-20 px-2">
              <div className={`w-12 h-12 border rounded-2xl flex items-center justify-center mx-auto mb-3 shadow-inner ${
                isDark ? 'bg-[#03060C] border-slate-800 text-slate-500' : 'bg-slate-100 border-slate-200 text-slate-400'
              }`}>
                <span className="text-xl">🗄️</span>
              </div>
              <p className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Vault Empty</p>
              <p className="text-[11px] text-slate-400 leading-relaxed mt-1">
                No records found for session <br/><span className="font-mono text-cyan-400 font-semibold">{sessionId}</span>
              </p>
            </div>
          ) : (
            notes.map((note) => (
              <div
                key={note.id}
                className={`p-4 rounded-2xl border transition-all shadow-md group relative overflow-hidden ${
                  isDark ? 'bg-[#03060C] border-slate-800/90 hover:border-slate-700/80 text-slate-300' : 'bg-slate-50 border-slate-200 hover:border-slate-300 text-slate-700'
                }`}
              >
                <div className="absolute top-0 left-0 w-1 h-full bg-amber-400/80"></div>
                <div className="flex justify-between items-start mb-2">
                  <h4 className="text-xs font-bold text-amber-500 truncate pr-2">{note.title}</h4>
                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                    isDark ? 'bg-slate-800 border-slate-700/50 text-slate-400' : 'bg-slate-200 border-slate-300 text-slate-600'
                  }`}>
                    #{note.id}
                  </span>
                </div>
                <p className="text-xs leading-relaxed whitespace-pre-wrap">{note.content}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}




