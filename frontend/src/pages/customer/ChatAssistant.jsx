import { useEffect, useState, useRef } from 'react';
import api from '../../api';

export default function ChatAssistant() {
  const bottomRef       = useRef(null);

  const [sessions,      setSessions]      = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages,      setMessages]      = useState([]);
  const [input,         setInput]         = useState('');
  const [sending,       setSending]       = useState(false);
  const [loading,       setLoading]       = useState(false);

  // Load sessions list on mount
  useEffect(() => {
    api.get('/chat/sessions')
      .then(r => setSessions(r.data.sessions || []))
      .catch(console.error);
  }, []);

  const loadSession = async (sid) => {
    setLoading(true);
    try {
      const r = await api.get(`/chat/sessions/${sid}`);
      setActiveSession(r.data);
      setMessages(r.data.messages || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const createSession = async () => {
    try {
      const r = await api.post('/chat/sessions', { session_title: 'New Chat' });
      const newSession = r.data;
      const sessR = await api.get('/chat/sessions');
      setSessions(sessR.data.sessions || []);
      setActiveSession(newSession);
      setMessages([]);
    } catch (err) {
      console.error(err);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || !activeSession || sending) return;
    const text = input.trim();
    setInput('');
    setSending(true);

    // Optimistic UI
    setMessages(m => [...m, { role: 'user', message_text: text, timestamp: new Date().toISOString() }]);

    try {
      const r = await api.post(`/chat/sessions/${activeSession.session_id}/message`, {
        message: text,
      });
      setMessages(m => [...m, r.data.ai_response]);

      // Refresh session list
      const sessR = await api.get('/chat/sessions');
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
      await api.delete(`/chat/sessions/${sid}`);
      const sessR = await api.get('/chat/sessions');
      setSessions(sessR.data.sessions || []);
      if (activeSession?.session_id === sid) {
        setActiveSession(null);
        setMessages([]);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Extract a friendly name from the first assistant intro message, if present
  const introMsg = messages.find(
    (m) =>
      m.role === 'assistant' &&
      typeof m.message_text === 'string' &&
      m.message_text.toLowerCase().includes("i'm your ai banking assistant")
  );
  let customerName = '';
  if (introMsg?.message_text) {
    const match = introMsg.message_text.match(/hello,?\s+([^!]+)!/i);
    if (match && match[1]) {
      customerName = match[1].trim();
    }
  }
  const filteredMessages = messages.filter(
    (m) =>
      !(
        m.role === 'assistant' &&
        typeof m.message_text === 'string' &&
        m.message_text.toLowerCase().includes("i'm your ai banking assistant")
      )
  );

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-[calc(100vh-6rem)] gap-4">

      {/* ── Sidebar: Sessions ── */}
      <div className="w-72 bg-white rounded-2xl shadow flex flex-col">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">🤖 AI Assistant</h2>
          <button
            onClick={createSession}
            className="bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1.5 rounded-xl font-semibold"
          >
            + New
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {sessions.length === 0 && (
            <p className="text-xs text-gray-400 text-center mt-8">
              No chat sessions yet.<br/>Click "+ New" to start.
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
          <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
            <span className="text-6xl mb-4">🤖</span>
            <p className="text-lg font-semibold text-gray-600">AI Banking Assistant</p>
            <p className="text-sm mt-2 text-center max-w-xs">
              Ask me about your EMI, outstanding balance, grace period eligibility, or loan restructuring options.
            </p>
            <button
              onClick={createSession}
              className="mt-6 bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-xl font-semibold text-sm"
            >
              Start New Chat
            </button>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="px-5 py-4 border-b flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-800">{activeSession.session_title}</p>
                <p className="text-xs text-gray-400">{messages.length} messages</p>
              </div>
              <span className="flex items-center gap-1.5 text-xs text-green-600 bg-green-50 px-3 py-1 rounded-full">
                <span className="w-1.5 h-1.5 bg-green-500 rounded-full inline-block"></span>
                AI Online
              </span>
            </div>

            {/* Assistant intro banner (kept out of chat messages) */}
            <div className="px-5 py-4 border-b bg-blue-50">
              <p className="text-sm font-semibold text-blue-800">
                Hello{customerName ? `, ${customerName}` : ''}! I'm your AI banking assistant.
              </p>
              <p className="text-xs text-blue-700 mt-1">
                I can help with EMI payment information, outstanding balance queries, grace period eligibility, and loan restructuring options.
              </p>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {loading && (
                <div className="flex justify-center">
                  <div className="animate-spin rounded-full h-6 w-6 border-2 border-blue-500 border-t-transparent"></div>
                </div>
              )}
              {filteredMessages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role !== 'user' && (
                    <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs mr-2 flex-shrink-0 mt-1">
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
                  <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs mr-2">🤖</div>
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
                  placeholder="Ask about your EMI, balance, grace period..."
                  rows={1}
                  className="flex-1 resize-none px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={sendMessage}
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