import { useEffect, useRef, useState, useCallback } from 'react';
import api from '../api';

const CHIPS = [
  { label: '💳 What is my EMI?',            text: 'What is my EMI amount?' },
  { label: '📊 Outstanding balance',         text: 'What is my outstanding balance?' },
  { label: '⏱ Grace period eligibility',    text: 'Am I eligible for a grace period?' },
  { label: '🔄 Restructuring options',       text: 'What are my loan restructuring options?' },
  { label: '🆔 What is my loan ID?',         text: 'What is my loan ID?' },
];

function formatTime(ts) {
  if (!ts) return '';
  return ts.slice(11, 16);
}

function sentimentEmoji(label) {
  if (label === 'Positive') return '😊';
  if (label === 'Negative') return '😟';
  if (label === 'Neutral')  return '😐';
  return null;
}

function computeSessionSentiment(messages) {
  const userMsgs = messages.filter(m => m.role === 'user' && m.sentiment_score !== undefined);
  if (userMsgs.length === 0) return null;
  const avg = userMsgs.reduce((s, m) => s + m.sentiment_score, 0) / userMsgs.length;
  if (avg > 0.2)  return { label: 'Positive', emoji: '😊', color: 'bg-green-500', text: 'text-green-700', bg: 'bg-green-50' };
  if (avg < -0.2) return { label: 'Negative', emoji: '😟', color: 'bg-red-500',   text: 'text-red-700',   bg: 'bg-red-50'   };
  return           { label: 'Neutral',  emoji: '😐', color: 'bg-yellow-400', text: 'text-yellow-700', bg: 'bg-yellow-50' };
}

function isIntroMsg(msg) {
  return (
    msg.role === 'assistant' &&
    typeof msg.message_text === 'string' &&
    msg.message_text.toLowerCase().includes("i'm your ai banking assistant")
  );
}

/**
 * LoanChat – slide-over loan-scoped chat with:
 *   • Session reuse / new-chat / past-chats
 *   • Suggestion chips
 *   • loan_id sent to backend for scoped answers
 */
export default function LoanChat({ loan, onClose }) {
  const bottomRef = useRef(null);

  const [allSessions,  setAllSessions]  = useState([]);   // all sessions for this loan
  const [sessionId,    setSessionId]    = useState(null);
  const [messages,     setMessages]     = useState([]);
  const [input,        setInput]        = useState('');
  const [sending,      setSending]      = useState(false);
  const [loading,      setLoading]      = useState(true);
  const [showPast,     setShowPast]     = useState(false); // toggle past-chats dropdown
  const [sentimentMap, setSentimentMap] = useState({});   // { msgIndex → { score, label } }

  // ── Load all sessions for this loan ────────────────────────────
  const loadSessions = useCallback(async () => {
    const r = await api.get('/chat/sessions');
    const sessions = (r.data.sessions || []).filter(s =>
      s.session_title?.startsWith(loan.loan_id)
    );
    setAllSessions(sessions);
    return sessions;
  }, [loan.loan_id]);

  // ── Load messages for a given session ──────────────────────────
  const loadSessionMessages = useCallback(async (sid) => {
    const sr = await api.get(`/chat/sessions/${sid}`);
    const msgs = (sr.data.messages || []).filter(m => !isIntroMsg(m));
    setMessages(msgs);
    setSessionId(sid);
  }, []);

  // ── On mount: find latest session for this loan or create one ──
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const sessions = await loadSessions();
        if (sessions.length > 0) {
          // Load the most recent session
          await loadSessionMessages(sessions[0].session_id);
        } else {
          // Create first session
          const cr = await api.post('/chat/sessions', {
            session_title: `${loan.loan_id} – ${loan.loan_type}`,
          });
          setSessionId(cr.data.session_id);
          setMessages([]);
          await loadSessions();
        }
      } catch (err) {
        console.error('LoanChat init error:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [loan.loan_id]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Create a brand-new chat session for this loan ──────────────
  const handleNewChat = async () => {
    setLoading(true);
    try {
      const now = new Date().toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
      const cr = await api.post('/chat/sessions', {
        session_title: `${loan.loan_id} – ${now}`,
      });
      setSessionId(cr.data.session_id);
      setMessages([]);
      setShowPast(false);
      await loadSessions();
    } catch (err) {
      console.error('New chat error:', err);
    } finally {
      setLoading(false);
    }
  };

  // ── Switch to a past session ────────────────────────────────────
  const handleSelectPast = async (sid) => {
    setLoading(true);
    setShowPast(false);
    try {
      await loadSessionMessages(sid);
    } catch (err) {
      console.error('Load past session error:', err);
    } finally {
      setLoading(false);
    }
  };

  // ── Delete a past session ───────────────────────────────────────
  const handleDeleteSession = async (e, sid) => {
    e.stopPropagation(); // don't trigger the select
    if (!window.confirm('Delete this chat session?')) return;
    try {
      await api.delete(`/chat/sessions/${sid}`);
      // If we deleted the active session, reset to empty
      if (sid === sessionId) {
        setSessionId(null);
        setMessages([]);
      }
      const sessions = await loadSessions();
      // If we deleted the active session and there are others, load the latest
      if (sid === sessionId && sessions.length > 0) {
        await loadSessionMessages(sessions[0].session_id);
      }
    } catch (err) {
      console.error('Delete session error:', err);
    }
  };

  // ── Send a message ──────────────────────────────────────────────
  const sendMessage = async (text) => {
    const msg = (text || input).trim();
    if (!msg || !sessionId || sending) return;
    setInput('');
    setSending(true);

    const userMsg = {
      role: 'user',
      message_text: msg,
      timestamp: new Date().toISOString(),
    };
    setMessages(m => [...m, userMsg]);

    try {
      const r = await api.post(`/chat/sessions/${sessionId}/message`, {
        message: msg,
        loan_id: loan.loan_id,
      });
      // Attach sentiment from backend to the user message we just pushed
      const { sentiment_score, sentiment_label } = r.data.user_message || {};
      if (sentiment_score !== undefined) {
        setMessages(m => {
          const updated = [...m];
          // The last user message is at the end before AI reply
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'user' && updated[i].message_text === msg) {
              updated[i] = { ...updated[i], sentiment_score, sentiment_label };
              break;
            }
          }
          return updated;
        });
      }
      const aiMsg = r.data.ai_response;
      if (!isIntroMsg(aiMsg)) {
        setMessages(m => [...m, aiMsg]);
      }
    } catch (err) {
      console.error(err);
      setMessages(m => [...m, {
        role: 'assistant',
        message_text: 'Sorry, something went wrong. Please try again.',
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const showChips = messages.length === 0 && !loading;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[440px] bg-white shadow-2xl flex flex-col border-l border-gray-200">

      {/* ── Header ── */}
      <div className="px-5 py-3 border-b bg-blue-700 text-white flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-bold text-sm truncate">🤖 AI Chat – {loan.loan_id}</p>
          <p className="text-xs text-blue-200 truncate">
            {loan.loan_type} · EMI ₹{loan.emi_amount?.toLocaleString('en-IN')} · Due {loan.emi_due_date}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* New Chat */}
          <button
            onClick={handleNewChat}
            title="Start a new chat"
            className="bg-blue-500 hover:bg-blue-400 text-white text-xs px-2 py-1 rounded-lg font-semibold"
          >
            ＋ New
          </button>

          {/* Past Chats dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowPast(v => !v)}
              title="View past chats"
              className="bg-blue-500 hover:bg-blue-400 text-white text-xs px-2 py-1 rounded-lg font-semibold"
            >
              📂 Past {showPast ? '▲' : '▼'}
            </button>
            {showPast && (
              <div className="absolute right-0 top-8 w-64 bg-white border border-gray-200 rounded-xl shadow-lg z-10 overflow-hidden">
                {allSessions.length === 0 ? (
                  <p className="text-xs text-gray-400 p-3 text-center">No past chats.</p>
                ) : (
                  allSessions.map(s => (
                    <div
                      key={s.session_id}
                      className={`flex items-center gap-1 border-b border-gray-100 last:border-0 ${
                        s.session_id === sessionId ? 'bg-blue-50' : 'hover:bg-gray-50'
                      }`}
                    >
                      <button
                        onClick={() => handleSelectPast(s.session_id)}
                        className={`flex-1 text-left px-3 py-2.5 text-xs transition-colors ${
                          s.session_id === sessionId ? 'font-semibold text-blue-700' : 'text-gray-700'
                        }`}
                      >
                        <p className="truncate font-medium">{s.session_title}</p>
                        <p className="text-gray-400 mt-0.5">{s.last_updated?.slice(0, 16)}</p>
                      </button>
                      <button
                        onClick={(e) => handleDeleteSession(e, s.session_id)}
                        title="Delete this chat"
                        className="flex-shrink-0 px-2 py-2 text-gray-400 hover:text-red-500 transition-colors"
                      >
                        🗑
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Close */}
          <button onClick={onClose} className="text-white hover:text-blue-200 text-xl leading-none">✕</button>
        </div>
      </div>

      {/* ── Capabilities banner ── */}
      <div className="px-4 py-2 bg-blue-50 border-b text-xs text-blue-700">
        Ask about EMI, balance, grace eligibility, or restructuring for <strong>{loan.loan_id}</strong>.
      </div>

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading && (
          <div className="flex justify-center mt-8">
            <div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent" />
          </div>
        )}

        {/* Suggestion chips – only on empty chat */}
        {showChips && (
          <div className="mt-4">
            <p className="text-xs text-gray-400 text-center mb-3">Quick questions for {loan.loan_id}:</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {CHIPS.map(chip => (
                <button
                  key={chip.text}
                  onClick={() => sendMessage(chip.text)}
                  className="text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 px-3 py-1.5 rounded-full transition-colors"
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {!loading && messages.length === 0 && !showChips && (
          <p className="text-center text-xs text-gray-400 mt-8">No messages yet.</p>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role !== 'user' && (
              <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs mr-2 flex-shrink-0 mt-1">
                🤖
              </div>
            )}
            <div className={`max-w-[80%] px-3 py-2 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-tr-none'
                : 'bg-gray-100 text-gray-800 rounded-tl-none'
            }`}>
              {msg.message_text}
              <div className={`flex items-center gap-1 mt-1 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <p className={`text-[10px] ${msg.role === 'user' ? 'text-blue-200' : 'text-gray-400'}`}>
                  {formatTime(msg.timestamp)}
                </p>
                {msg.role === 'user' && msg.sentiment_label && (
                  <span title={`Sentiment: ${msg.sentiment_label}`} className="text-[11px] leading-none">
                    {sentimentEmoji(msg.sentiment_label)}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs mr-2">🤖</div>
            <div className="bg-gray-100 px-3 py-2 rounded-2xl rounded-tl-none">
              <div className="flex gap-1">
                {[0, 150, 300].map(d => (
                  <span key={d} className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: `${d}ms` }} />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Session Sentiment Bar ── */}
      {(() => {
        const s = computeSessionSentiment(messages);
        if (!s) return null;
        return (
          <div className={`px-4 py-2 border-t flex items-center gap-2 ${s.bg}`}>
            <span className="text-sm">{s.emoji}</span>
            <span className={`text-xs font-medium ${s.text}`}>Session sentiment: {s.label}</span>
            <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div className={`h-1.5 rounded-full ${s.color}`}
                style={{
                  width: `${Math.round(
                    (messages.filter(m => m.role === 'user' && m.sentiment_label === s.label).length /
                    Math.max(messages.filter(m => m.role === 'user' && m.sentiment_label !== undefined).length, 1)) * 100
                  )}%`
                }}
              />
            </div>
          </div>
        );
      })()}

      {/* ── Input ── */}
      <div className="p-3 border-t">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Ask about ${loan.loan_id}…`}
            rows={1}
            className="flex-1 resize-none px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || sending}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-xl font-semibold text-sm transition-colors"
          >
            Send
          </button>
        </div>
        <p className="text-[10px] text-gray-400 mt-1 text-center">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  );
}

