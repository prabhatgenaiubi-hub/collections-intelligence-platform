import { useEffect, useState, useRef } from 'react';
import api from '../../api';

export default function OfficerChat() {
  const bottomRef = useRef(null);

  const [sessions,      setSessions]      = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages,      setMessages]      = useState([]);
  const [input,         setInput]         = useState('');
  const [sending,       setSending]       = useState(false);
  const [loadingMsg,    setLoadingMsg]    = useState(false);

  // Loan-wise mode
  const [mode,    setMode]    = useState('generic'); // 'generic' | 'loan'
  const [loanId,  setLoanId]  = useState('');
  const [loanErr, setLoanErr] = useState('');

  // Quick prompts
  const genericPrompts = [
    'What is the total outstanding portfolio?',
    'How many loans are in High risk segment?',
    'What are the best recovery strategies?',
    'Show me summary of overdue accounts',
  ];

  const loanPrompts = (id) => [
    `What is the recovery probability for ${id}?`,
    `Should I approve a grace request for ${id}?`,
    `What is the sentiment trend for customer of ${id}?`,
    `What outreach channel should I use for ${id}?`,
  ];

  useEffect(() => {
    api.get('/officer/chat/sessions')
      .then(r => setSessions(r.data.sessions || []))
      .catch(console.error);
  }, []);

  const loadSession = async (sid) => {
    setLoadingMsg(true);
    try {
      const r = await api.get(`/officer/chat/sessions/${sid}`);
      setActiveSession(r.data);
      setMessages(r.data.messages || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingMsg(false);
    }
  };

  const createSession = async () => {
    setLoanErr('');
    if (mode === 'loan' && !loanId.trim()) {
      setLoanErr('Please enter a Loan ID for loan-wise chat.');
      return;
    }
    const title = mode === 'loan'
      ? `Loan Analysis: ${loanId.trim().toUpperCase()}`
      : 'General Collections Chat';
    try {
      const r = await api.post('/officer/chat/sessions', { session_title: title });
      const sessR = await api.get('/officer/chat/sessions');
      setSessions(sessR.data.sessions || []);
      setActiveSession(r.data.session);
      setMessages([]);
    } catch (err) {
      console.error(err);
    }
  };

  const sendMessage = async (text) => {
    const msg = text || input.trim();
    if (!msg || !activeSession || sending) return;
    setInput('');
    setSending(true);

    // Prefix message with loan context if in loan mode
    const fullMsg = mode === 'loan' && loanId.trim()
      ? `[Loan: ${loanId.trim().toUpperCase()}] ${msg}`
      : msg;

    setMessages(m => [...m, { role: 'user', message_text: fullMsg, timestamp: new Date().toISOString() }]);

    try {
      const r = await api.post(`/officer/chat/sessions/${activeSession.session_id}/message`, {
        message: fullMsg,
        loan_id: mode === 'loan' && loanId.trim() ? loanId.trim().toUpperCase() : undefined,
      });
      setMessages(m => [...m, r.data.ai_response]);
      const sessR = await api.get('/officer/chat/sessions');
      setSessions(sessR.data.sessions || []);
    } catch (err) {
      console.error(err);
      setMessages(m => [...m, {
        role: 'assistant',
        message_text: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setSending(false);
    }
  };

  const deleteSession = async (sid) => {
    try {
      await api.delete(`/officer/chat/sessions/${sid}`);
      const sessR = await api.get('/officer/chat/sessions');
      setSessions(sessR.data.sessions || []);
      if (activeSession?.session_id === sid) {
        setActiveSession(null);
        setMessages([]);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const currentPrompts = mode === 'loan' && loanId.trim()
    ? loanPrompts(loanId.trim().toUpperCase())
    : genericPrompts;

  return (
    <div className="flex h-[calc(100vh-6rem)] gap-4">

      {/* ── Sidebar ── */}
      <div className="w-72 bg-white rounded-2xl shadow flex flex-col">
        <div className="p-4 border-b">
          <h2 className="font-semibold text-gray-800 mb-3">💬 AI Chat Assistant</h2>

          {/* Mode Selector */}
          <div className="flex rounded-xl overflow-hidden border border-gray-200 mb-3">
            <button
              onClick={() => setMode('generic')}
              className={`flex-1 py-2 text-xs font-semibold transition-colors ${
                mode === 'generic' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              🌐 Generic
            </button>
            <button
              onClick={() => setMode('loan')}
              className={`flex-1 py-2 text-xs font-semibold transition-colors ${
                mode === 'loan' ? 'bg-indigo-600 text-white' : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              📋 Loan-wise
            </button>
          </div>

          {/* Loan ID input (loan mode only) */}
          {mode === 'loan' && (
            <div className="mb-3">
              <input
                type="text"
                value={loanId}
                onChange={e => { setLoanId(e.target.value); setLoanErr(''); }}
                placeholder="Enter Loan ID (e.g. LOAN001)"
                className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
              {loanErr && <p className="text-red-500 text-xs mt-1">{loanErr}</p>}
            </div>
          )}

          <button
            onClick={createSession}
            className={`w-full py-2 rounded-xl text-white text-sm font-semibold transition-colors ${
              mode === 'loan' ? 'bg-indigo-600 hover:bg-indigo-700' : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            + New Chat
          </button>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {sessions.length === 0 && (
            <p className="text-xs text-gray-400 text-center mt-8">
              No chat sessions yet.<br/>Click "+ New Chat" to start.
            </p>
          )}
          {sessions.map(s => (
            <div
              key={s.session_id}
              onClick={() => loadSession(s.session_id)}
              className={`p-3 rounded-xl cursor-pointer group transition-all ${
                activeSession?.session_id === s.session_id
                  ? 'bg-blue-50 border border-blue-200'
                  : 'hover:bg-gray-50 border border-transparent'
              }`}
            >
              <div className="flex items-start justify-between">
                <p className="text-sm font-medium text-gray-800 truncate flex-1">{s.session_title}</p>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteSession(s.session_id); }}
                  className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 ml-1 text-xs"
                >
                  ✕
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-0.5 truncate">{s.last_message || 'No messages yet'}</p>
              <p className="text-xs text-gray-300 mt-0.5">{s.last_updated?.slice(0, 10)}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Chat Window ── */}
      <div className="flex-1 bg-white rounded-2xl shadow flex flex-col">
        {!activeSession ? (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-400 p-8">
            <span className="text-6xl mb-4">🏦</span>
            <p className="text-lg font-semibold text-gray-600">Collections Intelligence Chat</p>
            <p className="text-sm mt-2 text-center max-w-sm text-gray-400">
              {mode === 'loan'
                ? 'Enter a Loan ID and start a loan-specific analysis session.'
                : 'Ask about portfolio stats, recovery strategies, or customer insights.'}
            </p>

            {/* Quick prompts */}
            <div className="mt-6 w-full max-w-md space-y-2">
              <p className="text-xs text-gray-400 text-center font-semibold mb-2">QUICK QUESTIONS</p>
              {currentPrompts.map((q, i) => (
                <button
                  key={i}
                  onClick={() => { createSession(); }}
                  className="w-full text-left text-sm px-4 py-2.5 bg-gray-50 hover:bg-blue-50 border border-gray-200 hover:border-blue-200 rounded-xl text-gray-700 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {/* Chat Header */}
            <div className="px-5 py-4 border-b flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-800">{activeSession.session_title}</p>
                <p className="text-xs text-gray-400">{messages.length} messages</p>
              </div>
              <div className="flex items-center gap-3">
                {mode === 'loan' && loanId && (
                  <span className="text-xs bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full font-semibold">
                    📋 {loanId.toUpperCase()}
                  </span>
                )}
                <span className="flex items-center gap-1.5 text-xs text-green-600 bg-green-50 px-3 py-1 rounded-full">
                  <span className="w-1.5 h-1.5 bg-green-500 rounded-full inline-block"></span>
                  AI Online
                </span>
              </div>
            </div>

            {/* Quick prompts bar */}
            <div className="px-4 py-2 border-b bg-gray-50 flex gap-2 overflow-x-auto">
              {currentPrompts.map((q, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(q)}
                  className="flex-shrink-0 text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-full hover:bg-blue-50 hover:border-blue-300 text-gray-600 transition-colors"
                >
                  {q.length > 40 ? q.slice(0, 38) + '…' : q}
                </button>
              ))}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {loadingMsg && (
                <div className="flex justify-center">
                  <div className="animate-spin rounded-full h-6 w-6 border-2 border-blue-500 border-t-transparent"></div>
                </div>
              )}
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role !== 'user' && (
                    <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-white text-xs mr-2 flex-shrink-0 mt-1">
                      🤖
                    </div>
                  )}
                  <div className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-none'
                      : 'bg-gray-100 text-gray-800 rounded-tl-none'
                  }`}>
                    {msg.message_text}
                    <p className={`text-xs mt-1 ${msg.role === 'user' ? 'text-blue-200' : 'text-gray-400'}`}>
                      {msg.timestamp?.slice(11, 16)}
                    </p>
                  </div>
                </div>
              ))}

              {sending && (
                <div className="flex justify-start">
                  <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-white text-xs mr-2">🤖</div>
                  <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-tl-none">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t">
              <div className="flex gap-3">
                <textarea
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={mode === 'loan'
                    ? `Ask about ${loanId ? loanId.toUpperCase() : 'the loan'}...`
                    : 'Ask about portfolio, recovery, strategies...'}
                  rows={1}
                  className="flex-1 resize-none px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={() => sendMessage()}
                  disabled={!input.trim() || sending}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-5 py-3 rounded-xl font-semibold text-sm transition-colors"
                >
                  Send
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-2 text-center">
                Press Enter to send • Shift+Enter for new line
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
